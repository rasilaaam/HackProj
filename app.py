"""Streamlit user product for DietDB draft-rule planning."""
import json
import shutil
from pathlib import Path

import streamlit as st

from dietdb.__main__ import build_database
from dietdb.engine.db import connect_readonly
from dietdb.engine.planner import make_plan
from dietdb.llm import explain, extract_patient
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
    prefill = st.session_state.get("patient_prefill", {})
    for name, label, data_type, allowed in rows:
        if name.startswith("dx_") or data_type == "BOOLEAN":
            values[name] = st.checkbox(label, value=bool(prefill.get(name, False)), key=name)
        elif name == "allergy_list":
            values[name] = st.multiselect(label, allergens, default=prefill.get(name, []), key=name)
        elif data_type == "ENUM":
            options = json.loads(allowed or "[]")
            default = prefill.get(name, options[0] if options else "")
            values[name] = st.selectbox(label, options, index=options.index(default) if default in options else 0, key=name) if options else ""
        elif data_type == "REAL":
            values[name] = st.number_input(label, min_value=0.0, value=float(prefill.get(name, 0.0)), key=name)
        elif data_type == "STRING":
            values[name] = st.text_input(label, value=str(prefill.get(name, "")), key=name)
    return {k: v for k, v in values.items() if v not in ("", [], 0.0)}


def main() -> None:
    st.set_page_config(page_title="DietDB", layout="wide")
    db = prepare_database()
    with connect_readonly(db) as conn:
        approved_count = conn.execute("SELECT count(*) FROM rules WHERE status = 'APPROVED'").fetchone()[0]
    if approved_count:
        st.info("Approved rules are loaded. This is not medical advice.")
    else:
        st.warning("Draft rules are unreviewed and this is not medical advice. Plans require clinician review.")
    page = st.sidebar.radio("Page", ["Patient intake", "Plan", "Explore foods"])
    if page == "Patient intake":
        st.title("Patient intake")
        st.warning("Report text is sent to Google's Gemini API. On the free tier Google may use it to improve its products and human reviewers may read it. Do not paste identifying data.")
        report = st.text_area("Paste a lab report for optional field extraction", key="lab_report")
        if st.button("Extract fields from report"):
            extracted = extract_patient(report, db)
            st.session_state.patient_prefill = extracted["values"]
            st.session_state.extraction_result = extracted
            st.rerun()
        if st.session_state.get("extraction_result"):
            extraction = st.session_state.extraction_result
            st.info("Extracted fields are suggestions only. Confirm every value before generating a plan.")
            if extraction.get("missing_fields"): st.caption("Not found: " + ", ".join(extraction["missing_fields"]))
            if extraction.get("unknown_fields"): st.caption("Ignored unknown fields: " + ", ".join(extraction["unknown_fields"]))
            if extraction.get("rejected_fields"): st.error("Rejected fields: " + json.dumps(extraction["rejected_fields"]))
        values = intake(db)
        if st.button("Generate plan"):
            st.session_state.patient = values
            st.session_state.page = "Plan"
            st.rerun()
    elif page == "Plan":
        with connect_readonly(db) as conn:
            approved_count = conn.execute("SELECT count(*) FROM rules WHERE status = 'APPROVED'").fetchone()[0]
        rules_mode = "production" if approved_count else "draft-review"
        st.title("Plan")
        values = st.session_state.get("patient")
        if not values:
            st.info("Enter patient information first.")
            return
        try:
            result = make_plan(db, values, rules_mode)
            st.session_state.plan_result = result
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
                if rule.get("status") == "APPROVED":
                    st.caption(f"Rules reviewed by {rule.get('reviewed_by', 'unlisted reviewer')} on {rule.get('reviewed_at', 'unlisted date')}")
            if st.button("Explain this result"):
                st.write(explain(result, language="English"))
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
