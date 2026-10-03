"""Streamlit user product for DietDB draft-rule planning."""
import json
import shutil
from pathlib import Path

import streamlit as st

from dietdb.__main__ import build_database
from dietdb.engine.constraints import Patient, resolve
from dietdb.engine.db import connect_readonly
from dietdb.engine.planner import make_plan
from dietdb.rules import load_conditions, load_rules


ROOT = Path(__file__).parent
APP_DB = ROOT / "data/app.db"


@st.cache_resource
def prepare_database() -> str:
    if not APP_DB.exists():
        build_database(str(APP_DB))
        load_rules(APP_DB, ROOT / "data/rules/draft", "draft-review")
        load_conditions(APP_DB, ROOT / "data/conditions/draft_conditions.json")
    return str(APP_DB)


def intake(db: str) -> dict:
    with connect_readonly(db) as conn:
        rows = conn.execute("SELECT variable_name, display_name, data_type, allowed_values FROM patient_variables ORDER BY id").fetchall()
        allergens = [r[0] for r in conn.execute("SELECT code FROM allergens ORDER BY code")]
    values = {}
    for name, label, data_type, allowed in rows:
        if name.startswith("dx_") or data_type == "BOOLEAN":
            values[name] = st.checkbox(label, value=False, key=name)
        elif name == "allergy_list":
            values[name] = st.multiselect(label, allergens, key=name)
        elif data_type == "ENUM":
            options = json.loads(allowed or "[]")
            values[name] = st.selectbox(label, options, key=name) if options else ""
        elif data_type == "REAL":
            values[name] = st.number_input(label, min_value=0.0, value=0.0, key=name)
        elif name not in {"medication_classes", "region", "dietary_pattern"}:
            values[name] = st.text_input(label, key=name)
    return {k: v for k, v in values.items() if v not in ("", [], 0.0)}


def main() -> None:
    st.set_page_config(page_title="DietDB", layout="wide")
    st.warning("Draft rules are unreviewed and this is not medical advice. Plans require clinician review.")
    db = prepare_database()
    page = st.sidebar.radio("Page", ["Patient intake", "Plan", "Explore foods"])
    if page == "Patient intake":
        st.title("Patient intake")
        values = intake(db)
        if st.button("Generate plan"):
            st.session_state.patient = values
            st.session_state.page = "Plan"
            st.rerun()
    elif page == "Plan":
        st.title("Draft plan")
        values = st.session_state.get("patient")
        if not values:
            st.info("Enter patient information first.")
            return
        try:
            result = make_plan(db, values, "draft-review")
            st.warning(result.get("banner") or "RULES ARE UNREVIEWED DRAFTS: not clinical advice")
            st.subheader(f"Status: {result['status']}")
            if result.get("needs_info"):
                st.info("More information is needed: " + "; ".join(sorted({v for n in result["needs_info"] for v in n.get("variables", [])})))
            if result.get("message"):
                st.error(result["message"])
            for slot, items in (result.get("plan") or {}).get("slots", {}).items():
                st.markdown(f"**{slot.title()}**: " + ", ".join(f"{i['name']} {i['grams']} g" for i in items))
            if result.get("plan"):
                st.caption(f"Added salt allowance: {result['plan']['added_salt_allowance_g']} g per day. Weights are raw edible portion.")
                st.json(result["verification"]["totals"])
            st.json({k: result.get(k) for k in ("assumptions", "advisories", "diagnostics")})
            for rule in result.get("rules_applied", []):
                st.caption(f"{rule['slug']} ({rule['status']}): {rule['rationale']} [{rule['source_locator']}]")
            st.download_button("Download JSON", json.dumps(result, indent=2, default=list), "dietdb-plan.json", "application/json")
        except ValueError as exc:
            st.error(str(exc))
    else:
        st.title("Explore foods")
        query = st.text_input("Search foods")
        if query:
            with connect_readonly(db) as conn:
                try:
                    rows = conn.execute("""SELECT DISTINCT f.id, f.english_name FROM food_aliases_fts x
                        JOIN food_aliases a ON a.id=x.rowid JOIN foods f ON f.id=a.food_id
                        WHERE food_aliases_fts MATCH ? ORDER BY f.id LIMIT 30""", (query,)).fetchall()
                except Exception:
                    rows = conn.execute("SELECT id, english_name FROM foods WHERE english_name LIKE ? LIMIT 30", (f"%{query}%",)).fetchall()
            st.dataframe([dict(r) for r in rows], use_container_width=True)


if __name__ == "__main__":
    main()
