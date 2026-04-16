"""
BCS-E Breast Cancer Screening — 51 Realistic Persona Builder

Replaces old 48-persona model (is_excluded boolean) with 51 clinically valid
personas based on HEDIS BCS-E guidelines:

  NOT_ELIGIBLE:       3  (gender / age / enrollment)
  COMPLIANT/OPEN_GAP: 12 (3 GC × 2 age bands × 2 mammogram)
  EXCLUDED 42-65:     15 (3 GC × 5 exclusions — no frailty/SNP for <66)
  EXCLUDED 66-74:     21 (3 GC × 7 exclusions)
  Total:              51
"""

import os, json
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI      = os.getenv("NEO4J_URI")
USER     = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DB       = os.getenv("NEO4J_DATABASE")

GENDER_CRITERIA = [
    {"code": "GC1", "label": "AdministrativeGender=Female",
     "description": "Administrative Gender of Female at any time in member history"},
    {"code": "GC2", "label": "SexAssignedAtBirth=Female",
     "description": "Sex Assigned at Birth (LOINC 76689-9) of Female (LOINC LA3-6) at any time in member history"},
    {"code": "GC3", "label": "SexParamClinicalUse=Female",
     "description": "Sex Parameter for Clinical Use of Female (female-typical) during measurement period"},
]

AGE_BANDS = [
    {"code": "AB1", "label": "Age 42-65", "min_age": 42, "max_age": 65},
    {"code": "AB2", "label": "Age 66-74", "min_age": 66, "max_age": 74},
]

EXCLUSIONS_AB1 = [
    "bilateral_mastectomy", "unilateral_mastectomy_both_sides",
    "gender_affirming_chest_surgery", "hospice_or_palliative", "deceased",
]

EXCLUSIONS_AB2 = [
    "bilateral_mastectomy", "unilateral_mastectomy_both_sides",
    "gender_affirming_chest_surgery", "hospice_or_palliative", "deceased",
    "frailty_advanced_illness", "institutional_snp_or_ltc_66plus",
]

MAMMOGRAPHY_CPT = ["77062", "77061", "77066", "77065", "77063", "77067"]

EXCLUSION_CODES = {
    "bilateral_mastectomy": {
        "ICD10PCS": ["0HTV0ZZ"],
        "ICD10CM":  ["Z90.13"],
    },
    "unilateral_mastectomy_both_sides": {
        "CPT":      ["19180","19200","19220","19240","19303","19304","19305","19306","19307"],
        "Modifier": ["50","LT","RT"],
        "ICD10CM":  ["Z90.12","Z90.11"],
        "ICD10PCS": ["0HTU0ZZ","0HTT0ZZ"],
    },
    "gender_affirming_chest_surgery": {
        "CPT":     ["19318"],
        "ICD10CM": ["F64.1","F64.2","F64.8","F64.9","Z87.890"],
    },
}


def build_personas():
    personas, idx = [], 1

    # 3 NOT_ELIGIBLE
    for reason, desc in [
        ("gender_not_female", "None of GC1/GC2/GC3 criteria met — gender not Female"),
        ("age_outside_range", "Age outside eligible range 42-74"),
        ("not_enrolled",      "Continuous enrollment requirement not met"),
    ]:
        personas.append({
            "persona_id": f"BCS_P{idx:03d}", "measure": "BCS-E",
            "care_gap_status": "NOT_ELIGIBLE", "not_eligible_reason": reason,
            "gender_criteria_code": None, "age_band_code": None,
            "exclusion_reason": None, "mammogram_found": None,
            "description": f"NOT_ELIGIBLE: {desc}",
        })
        idx += 1

    # 12 COMPLIANT / OPEN_GAP
    for gc in GENDER_CRITERIA:
        for ab in AGE_BANDS:
            for mammo in [True, False]:
                status = "COMPLIANT" if mammo else "OPEN_GAP"
                personas.append({
                    "persona_id": f"BCS_P{idx:03d}", "measure": "BCS-E",
                    "care_gap_status": status, "not_eligible_reason": None,
                    "gender_criteria_code": gc["code"], "gender_criteria_label": gc["label"],
                    "age_band_code": ab["code"], "age_band_label": ab["label"],
                    "min_age": ab["min_age"], "max_age": ab["max_age"],
                    "exclusion_reason": None, "mammogram_found": mammo,
                    "description": (
                        f"{status}: {gc['label']} | {ab['label']} | "
                        f"Enrolled | No exclusion | Mammogram={'Yes' if mammo else 'No'}"
                    ),
                })
                idx += 1

    # 15 EXCLUDED (AB1) + 21 EXCLUDED (AB2)
    for gc in GENDER_CRITERIA:
        for ab in AGE_BANDS:
            exclusions = EXCLUSIONS_AB1 if ab["code"] == "AB1" else EXCLUSIONS_AB2
            for excl in exclusions:
                personas.append({
                    "persona_id": f"BCS_P{idx:03d}", "measure": "BCS-E",
                    "care_gap_status": "EXCLUDED", "not_eligible_reason": None,
                    "gender_criteria_code": gc["code"], "gender_criteria_label": gc["label"],
                    "age_band_code": ab["code"], "age_band_label": ab["label"],
                    "min_age": ab["min_age"], "max_age": ab["max_age"],
                    "exclusion_reason": excl, "mammogram_found": None,
                    "description": f"EXCLUDED: {gc['label']} | {ab['label']} | {excl}",
                })
                idx += 1

    return personas


def load_graph(driver, personas):
    with driver.session(database=DB) as session:
        for label, prop in [
            ("Persona","persona_id"), ("Measure","measure_id"),
            ("ComplianceCode","code"), ("ExclusionCode","code"),
        ]:
            session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")

        session.run("MATCH (p:Persona) DETACH DELETE p")

        session.run("""
            MERGE (m:Measure {measure_id: 'BCS-E'})
            SET m.name             = 'Breast Cancer Screening',
                m.product_lines    = 'Advantage MD, EHP, Priority Partners, USFHP',
                m.eligible_age_min = 42,
                m.eligible_age_max = 74,
                m.eligible_gender  = 'Female',
                m.lookback_start   = 'Oct 1 two years prior to measurement year',
                m.lookback_end     = 'Dec 31 of measurement year',
                m.measurement_year = 2026
        """)

        for cpt in MAMMOGRAPHY_CPT:
            session.run("""
                MERGE (c:ComplianceCode {code: $code})
                SET c.type = 'CPT', c.measure = 'BCS-E', c.description = 'Mammography CPT'
                WITH c MATCH (m:Measure {measure_id: 'BCS-E'})
                MERGE (m)-[:HAS_COMPLIANCE_CODE]->(c)
            """, code=cpt)

        for excl_name, code_map in EXCLUSION_CODES.items():
            for code_type, codes in code_map.items():
                for code in codes:
                    session.run("""
                        MERGE (e:ExclusionCode {code: $code})
                        SET e.type = $code_type, e.exclusion_reason = $excl_name, e.measure = 'BCS-E'
                        WITH e MATCH (m:Measure {measure_id: 'BCS-E'})
                        MERGE (m)-[:HAS_EXCLUSION_CODE]->(e)
                    """, code=code, code_type=code_type, excl_name=excl_name)

        session.run("""
            UNWIND $personas AS p
            MERGE (n:Persona {persona_id: p.persona_id})
            SET n += p
            WITH n
            MATCH (m:Measure {measure_id: 'BCS-E'})
            MERGE (n)-[:BELONGS_TO_MEASURE]->(m)
        """, personas=personas)

        print(f"Loaded {len(personas)} realistic BCS-E personas into Neo4j.")


def main():
    personas = build_personas()
    from collections import Counter
    counts = Counter(p["care_gap_status"] for p in personas)
    print(f"Generated {len(personas)} personas: {dict(counts)}")

    out_path = os.path.join(os.path.dirname(__file__), "bcs_all_combinations.json")
    with open(out_path, "w") as f:
        json.dump(personas, f, indent=2)
    print(f"Saved to: {out_path}")

    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    try:
        driver.verify_connectivity()
        print("Neo4j connected. Loading personas...")
        load_graph(driver, personas)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
