"""
Step 4: HEDIS Validation Queries
Verifies the correctness of gap determinations before outreach.
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from bcs_logger import get_logger, log_step_start, log_step_end, log_validation

load_dotenv()
logger = get_logger("bcs.step4")
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

def run_check(session, label, query, expect_empty=True):
    result = session.run(query)
    rows = [dict(r) for r in result]
    passed = (len(rows) == 0) == expect_empty
    log_validation(logger, label, passed,
                   str(rows[:3]) if rows and not expect_empty else "")
    if rows and expect_empty:
        for r in rows[:3]:
            logger.warning(f"  Unexpected row: {r}")
    return rows, "✅ PASS" if passed else "❌ FAIL"

def run_step4():
    log_step_start(logger, 4, "HEDIS BCS-E Validation")

    passes = 0
    fails  = 0

    with driver.session() as s:
        checks = [
            ("All 30 members have a BCS CareGap",
             "MATCH (m:Member) WHERE NOT exists { (m)-[:HAS_CARE_GAP]->(:CareGap {measureID:'BCS'}) } RETURN m.memberID AS missing"),
            ("No male member has OPEN/CLOSED BCS gap",
             "MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics) MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'}) WHERE d.administrativeGender = 'Male' AND cg.gapStatus IN ['OPEN','CLOSED'] RETURN m.memberID, d.administrativeGender, cg.gapStatus"),
            ("No female under age 42 has OPEN gap",
             "MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics) MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'}) WHERE d.administrativeGender = 'Female' AND d.age < 42 AND cg.gapStatus = 'OPEN' RETURN m.memberID, d.age, cg.gapStatus"),
            ("No female over age 74 has OPEN gap",
             "MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics) MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'}) WHERE d.administrativeGender = 'Female' AND d.age > 74 AND cg.gapStatus = 'OPEN' RETURN m.memberID, d.age, cg.gapStatus"),
            ("Every CLOSED gap backed by valid in-window mammogram",
             "MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'CLOSED'}) MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics) WHERE d.administrativeGender = 'Female' AND d.age >= 42 AND d.age <= 74 OPTIONAL MATCH (m)-[:HAS_SCREENING_HISTORY]->(sh:ScreeningHistory) WHERE sh.fallsInLookbackWindow = true WITH m, cg, sh WHERE sh IS NULL RETURN m.memberID AS member_missing_valid_claim, cg.gapStatus"),
            ("M0011 (Quinn Iyer, age 39 at mammogram) is correctly OPEN",
             "MATCH (m:Member {memberID:'M0011'})-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'}) WHERE cg.gapStatus <> 'OPEN' RETURN m.memberID, cg.gapStatus AS wrongStatus"),
            ("M0016 (age 28, CLOSED) flagged as data anomaly",
             "MATCH (m:Member {memberID:'M0016'})-[:HAS_DEMOGRAPHICS]->(d:Demographics) MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'}) WHERE d.age < 42 AND cg.gapStatus = 'CLOSED' AND cg.note IS NULL RETURN m.memberID, d.age, cg.gapStatus, 'Missing anomaly note' AS issue"),
            ("All OPEN eligible females matched to a persona",
             "MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics) MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'OPEN'}) WHERE d.administrativeGender = 'Female' AND d.age >= 42 AND d.age <= 74 AND NOT exists { (m)-[:MATCHED_TO]->(:IdealPersona) } RETURN m.memberID AS unmatched"),
            ("No standalone CPT 77063 closes a BCS gap",
             "MATCH (m:Member)-[:HAS_CLAIM]->(c:Claim) MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'CLOSED'}) WHERE c.cptCode = '77063' AND c.hedisCompliant = true AND NOT exists { MATCH (m)-[:HAS_CLAIM]->(c2:Claim) WHERE c2.cptCode IN ['77067','77066','77065'] AND c2.hedisCompliant = true } RETURN m.memberID, c.claimID, c.cptCode"),
            ("Every OPEN gap member has a CareGapRecommendation",
             "MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'OPEN'}) WHERE NOT exists { (m)-[:HAS_RECOMMENDATION]->(:CareGapRecommendation) } RETURN m.memberID AS missing_recommendation"),
        ]

        for label, query in checks:
            rows, status = run_check(s, label, query)
            if status.startswith("✅"):
                passes += 1
            else:
                fails += 1

    logger.info(f"--- VALIDATION RESULT: {passes} PASSED | {fails} FAILED ---")
    if fails == 0:
        logger.info("🎉 All HEDIS validations passed — safe to proceed with outreach!")
    else:
        logger.warning(f"⚠️  {fails} check(s) FAILED — fix before generating outreach")

    driver.close()
    log_step_end(logger, 4, "HEDIS Validation", {"Checks Passed": passes, "Checks Failed": fails})

if __name__ == "__main__":
    run_step4()
