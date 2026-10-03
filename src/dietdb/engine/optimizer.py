"""Deterministic one-day meal-plan optimizer (linear programming, no language model).

Every number comes from the database. HARD bounds are strict constraints (with a small safety margin so
that rounding to whole grams cannot break them); SOFT bounds are constraints too but are relaxed with a
heavy penalty when the plan would otherwise be impossible. Added salt is a decision variable, so the plan
reports how much salt the patient may add on top of the (natural) sodium in IFCT foods.
"""
from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

SALT_SODIUM_MG_PER_G = 393.4  # sodium mass fraction of NaCl (22.99 / 58.44)
REPORT_NUTRIENTS = ("energy_kcal", "protein", "carbohydrate", "fat_total", "fiber_total", "sodium",
                    "potassium", "phosphorus", "calcium", "magnesium", "iron")
MARGIN = 0.01
MIN_PORTION_G = 10.0
DIET_TAG = {"vegetarian": "VEGETARIAN", "vegan": "VEGETARIAN", "eggetarian": "EGGETARIAN",
            "fishetarian": "FISHETARIAN", "non_vegetarian": None}


@dataclass
class Candidate:
    food_id: int
    code: str
    name: str
    group: str
    values: dict[str, float]
    approximate: bool = False


@dataclass
class PlanResult:
    status: str                      # OK | INFEASIBLE_PLAN | NO_CANDIDATES
    items: list[dict[str, Any]] = field(default_factory=list)
    salt_g: float = 0.0
    diagnostics: dict[str, Any] = field(default_factory=dict)


def load_template(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def allergen_codes(value: Any) -> list[str]:
    if value is None: return []
    items = value if isinstance(value, (list, tuple)) else str(value).split(",")
    return sorted({str(x).strip().lower() for x in items if str(x).strip()})


def bounds_of(resolved: dict[str, Any]) -> dict[str, dict[str, dict[str, float | None]]]:
    """Split a ResolvedConstraints.nutrients entry into hard and soft bound dicts."""
    out: dict[str, dict[str, dict[str, float | None]]] = {}
    for nutrient, entry in resolved.items():
        hard = entry.get("hard")
        soft = entry.get("soft")
        if hard is None and soft is None:
            hard = {"min": entry.get("min"), "max": entry.get("max")}
        out[nutrient] = {"hard": hard or {"min": None, "max": None}, "soft": soft or {"min": None, "max": None}}
    return out


def load_candidates(conn: sqlite3.Connection, needed: set[str], max_bounded: set[str], template: dict[str, Any],
                    allergens: list[str], pattern: str, allowed_codes: set[str] | None = None) -> tuple[list[Candidate], dict[str, int]]:
    if pattern not in DIET_TAG:
        raise ValueError(f"unsupported dietary_pattern: {pattern}")
    slot_groups = {g for s in template["slots"].values() for g, (_, hi) in s["groups"].items() if hi > 0}
    skip = set(template.get("excluded_groups", []))
    names = sorted(needed)
    marks = ",".join("?" for _ in names)
    nut_rows: dict[int, dict[str, tuple[float | None, str]]] = {}
    for fid, nname, val, status in conn.execute(
        f"SELECT fn.food_id, n.canonical_name, fn.value_canonical, fn.value_status FROM food_nutrients fn "
        f"JOIN nutrients n ON n.id = fn.nutrient_id WHERE n.canonical_name IN ({marks})", names):
        nut_rows.setdefault(fid, {})[nname] = (val, status)
    tags: dict[int, set[str]] = {}
    for fid, code in conn.execute("SELECT t.food_id, d.code FROM diet_type_tags t JOIN diet_types d ON d.id = t.diet_type_id WHERE t.is_compatible = 1"):
        tags.setdefault(fid, set()).add(code)
    allergy_ids = {code: aid for aid, code in conn.execute("SELECT id, code FROM allergens")}
    unknown_allergens = [a for a in allergens if a not in allergy_ids]
    if unknown_allergens:
        raise ValueError(f"unknown allergen codes: {', '.join(unknown_allergens)}")
    presence: dict[tuple[int, str], str] = {}
    if allergens:
        marks_a = ",".join("?" for _ in allergens)
        for fid, code, pres in conn.execute(
            f"SELECT fa.food_id, a.code, fa.presence FROM food_allergens fa JOIN allergens a ON a.id = fa.allergen_id WHERE a.code IN ({marks_a})", allergens):
            presence[(fid, code)] = pres
    excluded: dict[str, int] = {}
    def drop(reason: str) -> None: excluded[reason] = excluded.get(reason, 0) + 1
    out: list[Candidate] = []
    for fid, code, name, group in conn.execute(
        "SELECT f.id, f.source_code, f.english_name, g.code FROM foods f JOIN food_groups g ON g.id = f.food_group_id ORDER BY f.id"):
        if group in skip or group not in slot_groups: drop("GROUP_NOT_USED"); continue
        if allowed_codes is not None and code not in allowed_codes: drop("NOT_IN_COMMON_FOODS"); continue
        if pattern == "vegan" and group == "L": drop("DIET_PATTERN"); continue
        wanted = DIET_TAG[pattern]
        if wanted is not None and wanted not in tags.get(fid, set()): drop("DIET_PATTERN"); continue
        if any(presence.get((fid, a), "UNKNOWN") != "ABSENT" for a in allergens): drop("ALLERGEN_NOT_ABSENT"); continue
        row = nut_rows.get(fid, {})
        energy = row.get("energy_kcal", (None, "NOT_ANALYSED"))
        if energy[0] is None: drop("NO_ENERGY"); continue
        values: dict[str, float] = {}
        approx = False
        bad = None
        for n in needed:
            val, status = row.get(n, (None, "NOT_ANALYSED"))
            if val is None:
                if status == "NOT_DETECTED": values[n] = 0.0; approx = True
                elif n in max_bounded: bad = n; break
                else: values[n] = 0.0; approx = True
            else: values[n] = float(val)
        if bad: drop(f"UNKNOWN_{bad.upper()}"); continue
        out.append(Candidate(fid, code, name, group, values, approx))
    return out, excluded


def solve(candidates: list[Candidate], bounds: dict[str, dict[str, dict[str, float | None]]], energy_kcal: float,
          template: dict[str, Any], salt_min_g: float, salt_max_g: float, relax_hard: bool = False,
          forbid: set[tuple[int, str]] | None = None) -> tuple[Any, dict[str, Any]]:
    forbid = forbid or set()
    tol = float(template.get("energy_tolerance", 0.10))
    slots = list(template["slots"])
    var: list[tuple[int, str]] = []  # (candidate index, slot)
    for si, s in enumerate(slots):
        groups = template["slots"][s]["groups"]
        for ci, c in enumerate(candidates):
            if c.group in groups and groups[c.group][1] > 0 and (c.food_id, s) not in forbid:
                var.append((ci, s))
    nx = len(var)
    SALT, DP, DM, MX = nx, nx + 1, nx + 2, nx + 3
    extra_cols: list[tuple[str, str, str, float]] = []   # (nutrient, kind, class, bound) slack columns
    rows: list[tuple[dict[int, float], float, str]] = []  # (coeffs, rhs, tag)  meaning coeffs . x <= rhs
    slack_info: list[tuple[int, float, str]] = []         # (column, weight, label)
    n_cols = nx + 4
    def add_slack(weight: float, label: str) -> int:
        nonlocal n_cols
        col = n_cols; n_cols += 1
        slack_info.append((col, weight, label))
        return col
    def nutrient_row(name: str) -> dict[int, float]:
        row = {i: candidates[ci].values[name] / 100.0 for i, (ci, _) in enumerate(var) if candidates[ci].values.get(name, 0.0) != 0.0}
        if name == "sodium": row[SALT] = SALT_SODIUM_MG_PER_G
        return row
    for name in sorted(bounds):
        for cls in ("hard", "soft"):
            b = bounds[name][cls]
            for kind in ("max", "min"):
                v = b.get(kind)
                if v is None: continue
                row = nutrient_row(name)
                if cls == "hard" and not relax_hard:
                    rhs = v * (1 - MARGIN) if kind == "max" else v * (1 + MARGIN)
                    rows.append((row, rhs, f"{name}:{cls}:{kind}") if kind == "max" else ({k: -x for k, x in row.items()}, -rhs, f"{name}:{cls}:{kind}"))
                else:
                    weight = (1000.0 if cls == "hard" else 100.0) / max(abs(v), 1e-9)
                    col = add_slack(weight, f"{name}:{cls}:{kind}")
                    if kind == "max": r = dict(row); r[col] = -1.0; rows.append((r, v, f"{name}:{cls}:{kind}"))
                    else: r = {k: -x for k, x in row.items()}; r[col] = -1.0; rows.append((r, -v, f"{name}:{cls}:{kind}"))
    energy_row = {i: candidates[ci].values["energy_kcal"] / 100.0 for i, (ci, _) in enumerate(var)}
    rows.append((dict(energy_row), energy_kcal * (1 + tol), "energy:window:max"))
    rows.append(({k: -x for k, x in energy_row.items()}, -energy_kcal * (1 - tol), "energy:window:min"))
    for s in slots:
        spec = template["slots"][s]
        sel = {i: candidates[ci].values["energy_kcal"] / 100.0 for i, (ci, sl) in enumerate(var) if sl == s}
        if not sel: continue
        lo, hi = spec["energy_share"]
        rows.append((dict(sel), hi * energy_kcal, f"slot:{s}:energy:max"))
        rows.append(({k: -x for k, x in sel.items()}, -lo * energy_kcal, f"slot:{s}:energy:min"))
        for g, (glo, ghi) in spec["groups"].items():
            members = {i: 1.0 for i, (ci, sl) in enumerate(var) if sl == s and candidates[ci].group == g}
            if not members: continue
            rows.append((dict(members), ghi, f"slot:{s}:group:{g}:max"))
            if glo > 0: rows.append(({k: -1.0 for k in members}, -glo, f"slot:{s}:group:{g}:min"))
    by_food: dict[int, list[int]] = {}
    for i, (ci, _) in enumerate(var): by_food.setdefault(ci, []).append(i)
    caps = template.get("per_food_max_g_by_group", {}); default_cap = float(template.get("per_food_max_g_default", 200))
    for ci, idx in by_food.items():
        cap = float(caps.get(candidates[ci].group, default_cap))
        rows.append(({i: 1.0 for i in idx}, cap, f"food:{candidates[ci].food_id}:cap"))
    A = lil_matrix((len(rows), n_cols)); b = np.zeros(len(rows))
    for ri, (coeffs, rhs, _) in enumerate(rows):
        for ci_, v in coeffs.items(): A[ri, ci_] = v
        b[ri] = rhs
    Aeq = lil_matrix((1, n_cols)); beq = np.array([energy_kcal])
    for i, v in energy_row.items(): Aeq[0, i] = v
    Aeq[0, DP] = -1.0; Aeq[0, DM] = 1.0
    c = np.zeros(n_cols)
    c[:nx] = 0.001 / 1000.0
    c[DP] = c[DM] = 10.0 / energy_kcal
    c[MX] = 0.0
    c[SALT] = -0.2 / max(salt_max_g, 1e-9)
    for col, weight, _ in slack_info: c[col] = weight
    lower = np.zeros(n_cols); upper = np.full(n_cols, np.inf)
    upper[:nx] = [float(caps.get(candidates[ci].group, default_cap)) for ci, _ in var]
    lower[SALT], upper[SALT] = salt_min_g, salt_max_g
    res = linprog(c, A_ub=A.tocsr(), b_ub=b, A_eq=Aeq.tocsr(), b_eq=beq, bounds=list(zip(lower, upper)), method="highs")
    info = {"var": var, "slots": slots, "n_rows": len(rows), "slack": slack_info, "SALT": SALT}
    return res, info


def optimize(conn: sqlite3.Connection, resolved_nutrients: dict[str, Any], energy_kcal: float, template: dict[str, Any],
             allergens: list[str], pattern: str, salt_min_g: float = 1.0, salt_max_g: float = 5.0,
             allowed_codes: set[str] | None = None) -> PlanResult:
    bounds = bounds_of(resolved_nutrients)
    needed = set(REPORT_NUTRIENTS) | set(bounds)
    max_bounded = {n for n, b in bounds.items() if b["hard"].get("max") is not None or b["soft"].get("max") is not None}
    candidates, excluded = load_candidates(conn, needed, max_bounded, template, allergens, pattern, allowed_codes)
    diag: dict[str, Any] = {"candidates": len(candidates), "excluded_foods_by_reason": dict(sorted(excluded.items()))}
    if not candidates:
        return PlanResult("NO_CANDIDATES", diagnostics=diag)
    forbid: set[tuple[int, str]] = set()
    res, info = solve(candidates, bounds, energy_kcal, template, salt_min_g, salt_max_g, False, forbid)
    if res.status != 0:
        relax, rinfo = solve(candidates, bounds, energy_kcal, template, salt_min_g, salt_max_g, True, forbid)
        gives = []
        if relax.status == 0:
            for col, weight, label in rinfo["slack"]:
                if relax.x[col] > 1e-6 and ":hard:" in label:
                    gives.append({"constraint": label, "violation": round(float(relax.x[col]), 3)})
        diag["would_need_to_relax"] = sorted(gives, key=lambda g: g["constraint"])
        diag["solver_message"] = res.message
        return PlanResult("INFEASIBLE_PLAN", diagnostics=diag)
    max_per_group = int(template.get("max_foods_per_slot_group", 2))
    for _ in range(6):  # prune tiny portions and keep at most K foods per slot/group, then re-solve
        var = info["var"]
        drop_now: set[tuple[int, str]] = set()
        by_sg: dict[tuple[str, str], list[tuple[float, int, int]]] = {}
        for i, (ci, s_) in enumerate(var):
            if res.x[i] <= 1e-6: continue
            if res.x[i] < MIN_PORTION_G: drop_now.add((candidates[ci].food_id, s_))
            else: by_sg.setdefault((s_, candidates[ci].group), []).append((float(res.x[i]), -candidates[ci].food_id, ci))
        for (s_, g_), lst in by_sg.items():
            for _, _, ci in sorted(lst, reverse=True)[max_per_group:]: drop_now.add((candidates[ci].food_id, s_))
        if not drop_now: break
        res2, info2 = solve(candidates, bounds, energy_kcal, template, salt_min_g, salt_max_g, False, forbid | drop_now)
        if res2.status != 0: break
        forbid |= drop_now; res, info = res2, info2
    var = info["var"]
    soft_relaxed = [{"constraint": label, "violation": round(float(res.x[col]), 3)} for col, _, label in info["slack"] if res.x[col] > 1e-6]
    diag["soft_bounds_relaxed"] = sorted(soft_relaxed, key=lambda g: g["constraint"])
    items = []
    for i, (ci, s) in enumerate(var):
        grams = int(round(float(res.x[i])))
        if grams <= 0: continue
        c = candidates[ci]
        items.append({"slot": s, "food_id": c.food_id, "source_code": c.code, "name": c.name, "group": c.group,
                      "grams": grams, "approximate": c.approximate})
    order = {s: k for k, s in enumerate(info["slots"])}
    items.sort(key=lambda x: (order[x["slot"]], x["group"], x["food_id"]))
    salt = math.floor(float(res.x[info["SALT"]]) * 10 + 1e-9) / 10.0
    diag["objective"] = round(float(res.fun), 6)
    return PlanResult("OK", items, max(salt, 0.0), diag)
