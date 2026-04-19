"""
graph_builder.py — Loads BCS member data into Neo4j knowledge graph.
"""

import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from schema import apply_schema
from seed_data import MEMBERS, CARE_MANAGERS, QUALITY_MEASURES

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)


def _merge_node(tx, label, key_field, key_value, props):
    props[key_field] = key_value
    query = (
        f"MERGE (n:{label} {{{key_field}: ${key_field}}}) "
        f"SET n += $props RETURN n"
    )
    tx.run(query, **{key_field: key_value}, props=props)


def _merge_rel(tx, from_label, from_key, from_val, rel_type, to_label, to_key, to_val):
    query = (
        f"MATCH (a:{from_label} {{{from_key}: $from_val}}) "
        f"MATCH (b:{to_label} {{{to_key}: $to_val}}) "
        f"MERGE (a)-[:{rel_type}]->(b)"
    )
    tx.run(query, from_val=from_val, to_val=to_val)


def load_member(member_data: dict):
    m = member_data
    mid = m["member"]["memberID"]

    with driver.session() as session:
        # Member
        session.execute_write(_merge_node, "Member", "memberID", mid, m["member"])

        # Demographics
        demo = m.get("demographics")
        if demo:
            demo_id = f"{mid}-DEMO"
            session.execute_write(_merge_node, "Demographics", "demographicsID", demo_id, demo)
            session.execute_write(_merge_rel, "Member", "memberID", mid,
                                  "HAS_DEMOGRAPHICS", "Demographics", "demographicsID", demo_id)

        # Enrollment
        enr = m["enrollment"]
        session.execute_write(_merge_node, "Enrollment", "enrollmentID", enr["enrollmentID"], enr)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_ENROLLMENT", "Enrollment", "enrollmentID", enr["enrollmentID"])

        # BenefitPlan
        bp = m.get("benefit_plan")
        if bp:
            session.execute_write(_merge_node, "BenefitPlan", "planID", bp["planID"], bp)
            session.execute_write(_merge_rel, "Member", "memberID", mid,
                                  "ENROLLED_IN", "BenefitPlan", "planID", bp["planID"])

        # Vitals — keyed by memberID + vitalDate
        vitals = {**m["vitals"], "memberID": mid}
        vitals_key = f"{mid}-VIT"
        vitals["vitalsID"] = vitals_key
        session.execute_write(_merge_node, "Vitals", "vitalsID", vitals_key, vitals)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_VITALS", "Vitals", "vitalsID", vitals_key)

        # ClinicalHistory
        clin = {**m["clinical"], "clinicalID": f"{mid}-CLIN"}
        session.execute_write(_merge_node, "ClinicalHistory", "clinicalID",
                              clin["clinicalID"], clin)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_CLINICAL_HISTORY", "ClinicalHistory",
                              "clinicalID", clin["clinicalID"])

        # Medications
        for i, med in enumerate(m["medications"]):
            med_id = f"{mid}-MED-{i}"
            med["medID"] = med_id
            session.execute_write(_merge_node, "Medication", "medID", med_id, med)
            session.execute_write(_merge_rel, "Member", "memberID", mid,
                                  "TAKES_MEDICATION", "Medication", "medID", med_id)

        # ReproductiveHistory
        repro = {**m["reproductive"], "reproID": f"{mid}-REPRO"}
        session.execute_write(_merge_node, "ReproductiveHistory", "reproID",
                              repro["reproID"], repro)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_REPRODUCTIVE_HISTORY", "ReproductiveHistory",
                              "reproID", repro["reproID"])

        # LifestyleFactors
        life = {**m["lifestyle"], "lifestyleID": f"{mid}-LIFE"}
        session.execute_write(_merge_node, "LifestyleFactors", "lifestyleID",
                              life["lifestyleID"], life)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_LIFESTYLE", "LifestyleFactors",
                              "lifestyleID", life["lifestyleID"])

        # ScreeningRecord
        scr = m["screening"]
        session.execute_write(_merge_node, "ScreeningRecord", "screeningID",
                              scr["screeningID"], scr)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_SCREENING", "ScreeningRecord",
                              "screeningID", scr["screeningID"])

        # Claims
        for claim in m["claims"]:
            session.execute_write(_merge_node, "Claim", "claimID",
                                  claim["claimID"], claim)
            session.execute_write(_merge_rel, "Member", "memberID", mid,
                                  "HAS_CLAIM", "Claim", "claimID", claim["claimID"])

        # Providers
        for prov in m["providers"]:
            session.execute_write(_merge_node, "Provider", "npi", prov["npi"], prov)
            session.execute_write(_merge_rel, "Member", "memberID", mid,
                                  "ASSIGNED_TO_PROVIDER", "Provider",
                                  "npi", prov["npi"])

        # Exclusion
        excl = {**m["exclusion"], "exclusionID": f"{mid}-EXCL"}
        session.execute_write(_merge_node, "Exclusion", "exclusionID",
                              excl["exclusionID"], excl)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_EXCLUSION", "Exclusion",
                              "exclusionID", excl["exclusionID"])

        # RiskScore
        risk = {**m["risk_score"], "riskID": f"{mid}-RISK"}
        session.execute_write(_merge_node, "RiskScore", "riskID", risk["riskID"], risk)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_RISK_SCORE", "RiskScore", "riskID", risk["riskID"])

        # SDOH
        sdoh = {**m["sdoh"], "sdohID": f"{mid}-SDOH"}
        session.execute_write(_merge_node, "SDOH", "sdohID", sdoh["sdohID"], sdoh)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_SDOH", "SDOH", "sdohID", sdoh["sdohID"])

        # CareGap
        gap = m["care_gap"]
        session.execute_write(_merge_node, "CareGap", "careGapID",
                              gap["careGapID"], gap)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_CARE_GAP", "CareGap",
                              "careGapID", gap["careGapID"])
        if gap.get("measureID"):
            session.execute_write(_merge_rel, "CareGap", "careGapID", gap["careGapID"],
                                  "MEASURES", "QualityMeasure", "measureID", gap["measureID"])
        if gap.get("careManagerAssigned"):
            session.execute_write(_merge_rel, "CareGap", "careGapID", gap["careGapID"],
                                  "ASSIGNED_TO", "CareManager", "careManagerID", gap["careManagerAssigned"])

        # Outreach
        for out in m["outreach"]:
            session.execute_write(_merge_node, "Outreach", "outreachID",
                                  out["outreachID"], out)
            session.execute_write(_merge_rel, "CareGap", "careGapID",
                                  gap["careGapID"], "HAS_OUTREACH",
                                  "Outreach", "outreachID", out["outreachID"])
            if out.get("careManagerID"):
                session.execute_write(_merge_rel, "Outreach", "outreachID", out["outreachID"],
                                      "PERFORMED_BY", "CareManager", "careManagerID", out["careManagerID"])

        # Consent
        cons = {**m["consent"], "consentID": f"{mid}-CONS"}
        session.execute_write(_merge_node, "Consent", "consentID",
                              cons["consentID"], cons)
        session.execute_write(_merge_rel, "Member", "memberID", mid,
                              "HAS_CONSENT", "Consent",
                              "consentID", cons["consentID"])

    print(f"✅ Loaded member {mid}")


def load_statics():
    with driver.session() as session:
        for cm in CARE_MANAGERS:
            session.execute_write(_merge_node, "CareManager", "careManagerID", cm["careManagerID"], cm)
        for qm in QUALITY_MEASURES:
            session.execute_write(_merge_node, "QualityMeasure", "measureID", qm["measureID"], qm)
    print("✅ Loaded static Quality Measures and Care Managers")

if __name__ == "__main__":
    apply_schema(driver)
    load_statics()
    for member in MEMBERS:
        load_member(member)
    print("🎉 All members loaded into Neo4j.")
    driver.close()
