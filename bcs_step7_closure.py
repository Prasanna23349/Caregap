"""
Step 7: Gap Closure Tracking
Simulates closure when a valid mammogram claim arrives.
Also flags members approaching the 24-month re-screening window.
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import date, timedelta
from bcs_logger import get_logger, log_step_start, log_step_end

load_dotenv()
logger = get_logger("bcs.step7")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

VALID_CPT   = {"77067", "77066", "77065", "77062", "77061"}
WINDOW_START = date(2024, 10, 1)
WINDOW_END   = date(2026, 12, 31)
LOOKBACK_AGE_MIN = 40

def validate_claim(cpt, service_date_str, age_at_service):
    """Return (valid, reason) for a mammogram claim."""
    if cpt not in VALID_CPT:
        return False, f"CPT {cpt} not in valid BCS codes (77063 standalone not accepted)"
    try:
        sd = date.fromisoformat(str(service_date_str))
    except (ValueError, TypeError):
        return False, "Invalid service date"
    if sd < WINDOW_START or sd > WINDOW_END:
        return False, f"Date {sd} outside lookback window {WINDOW_START}–{WINDOW_END}"
    try:
        age = int(age_at_service)
    except (TypeError, ValueError):
        age = 99  # unknown age — allow
    if age < LOOKBACK_AGE_MIN:
        return False, f"Age {age} at service below lookback minimum of {LOOKBACK_AGE_MIN}"
    return True, "Valid BCS mammogram claim"

def close_gap(member_id, claim_id, cpt, service_date, age_at_service, source="New Claim"):
    """Attempt to close a BCS gap for a member given a claim."""
    valid, reason = validate_claim(cpt, service_date, age_at_service)

    with driver.session() as s:
        if valid:
            # Close the gap
            s.run("""
                MATCH (m:Member {memberID: $mid})-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
                SET cg.gapStatus    = 'CLOSED',
                    cg.gapClosedDate = date($closeDate),
                    cg.closingClaimID = $claimID,
                    cg.closingCPT    = $cpt,
                    cg.closureSource = $source,
                    cg.closureNote   = $reason
            """, mid=member_id, closeDate=str(date.today()),
                 claimID=claim_id, cpt=cpt, source=source, reason=reason)

            # Update outreach outcome
            s.run("""
                MATCH (m:Member {memberID: $mid})-[:HAS_OUTREACH]->(o:Outreach)
                SET o.outreachStatus = 'Completed',
                    o.outcome        = 'Gap Closed',
                    o.gapClosedDate  = date($closeDate)
            """, mid=member_id, closeDate=str(date.today()))

            # Update recommendation status
            s.run("""
                MATCH (m:Member {memberID: $mid})-[:HAS_RECOMMENDATION]->(r:CareGapRecommendation)
                SET r.gapStatus = 'CLOSED',
                    r.closedDate = date($closeDate)
            """, mid=member_id, closeDate=str(date.today()))

            return "✅ CLOSED", reason

        else:
            # Flag the gap — do not close
            s.run("""
                MATCH (m:Member {memberID: $mid})-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
                SET cg.invalidClaimNote = $note
            """, mid=member_id, note=f"Claim {claim_id} invalid: {reason}")
            return "❌ REJECTED", reason

def flag_approaching_window():
    """Flag CLOSED members whose next screening is due in ≤ 6 months."""
    approaching = []
    cutoff = date.today() + timedelta(days=180)
    with driver.session() as s:
        rows = s.run("""
            MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'CLOSED'})
            MATCH (m)-[:HAS_SCREENING_HISTORY]->(sh:ScreeningHistory)
            MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
            WHERE sh.lastMammogramDate IS NOT NULL
            RETURN m.memberID AS mid, m.fullName AS name, d.age AS age,
                   sh.lastMammogramDate AS lastDate
        """)
        for row in rows:
            try:
                last = date.fromisoformat(str(row["lastDate"]))
                next_due = last + timedelta(days=730)  # 24 months
                months_remaining = round((next_due - date.today()).days / 30, 1)
                approaching.append({
                    "mid": row["mid"], "name": row["name"],
                    "age": row["age"], "lastDate": last,
                    "nextDue": next_due, "monthsRemaining": months_remaining,
                    "proactiveFlag": next_due <= cutoff
                })
            except Exception:
                pass
    return approaching

def run_step7():
    log_step_start(logger, 7, "Gap Closure Tracking")

    # ── 7A: Claim validation test cases ──
    logger.info("--- 7A: SIMULATED CLAIM VALIDATION ---")
    test_cases = [
        ("M0011", "C-TEST-001", "77067", "2026-04-15", 42, "Valid claim — CPT 77067, in window, age 42"),
        ("M0011", "C-TEST-002", "77063", "2026-04-15", 42, "Rejected — standalone 77063 not valid"),
        ("M0011", "C-TEST-003", "77067", "2023-09-01", 39, "Rejected — outside window AND age 39"),
        ("M0011", "C-TEST-004", "77067", "2025-06-01", 41, "Valid date, age 41 — accepted (≥40)"),
    ]
    for mid, cid, cpt, sdate, age, desc in test_cases:
        result, reason = validate_claim(cpt, sdate, age)
        symbol = "✅" if result else "❌"
        logger.info(f"  {symbol} [{cid}] {desc}")
        logger.debug(f"     Reason: {reason}")

    # ── 7B: Apply closure for M0011 ──
    logger.info("--- 7B: APPLYING CLOSURE: M0011 (Quinn Iyer) ---")
    status, reason = close_gap("M0011", "C-SIM-001", "77067", "2026-04-15", 42, "Simulated closure")
    logger.info(f"  {status} — M0011 Quinn Iyer | {reason}")

    # ── 7C: Gap status after closure ──
    logger.info("--- 7C: GAP STATUS AFTER CLOSURE ---")
    with driver.session() as s:
        rows = s.run("""
            MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
            MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
            WHERE d.administrativeGender = 'Female' AND d.age >= 42 AND d.age <= 74
            RETURN m.memberID, m.fullName, d.age, cg.gapStatus,
                   cg.gapClosedDate, cg.closingClaimID
            ORDER BY cg.gapStatus, d.age DESC
        """)
        for row in rows:
            logger.info(f"  {row['m.memberID']:<10} {str(row['m.fullName']):<22} "
                        f"Age {str(row['d.age']):<4} {row['cg.gapStatus']:<14} "
                        f"Closed: {str(row['cg.gapClosedDate'] or '-'):<14} "
                        f"Claim: {str(row['cg.closingClaimID'] or '-')}")

    # ── 7D: Proactive re-screening alerts ──
    logger.info("--- 7D: PROACTIVE RE-SCREENING WINDOW ---")
    approaching = flag_approaching_window()
    for a in approaching:
        if a["proactiveFlag"]:
            logger.warning(f"🔔 PROACTIVE ALERT | {a['mid']} {a['name']} | "
                           f"Age {a['age']} | Last: {a['lastDate']} | "
                           f"Next due: {a['nextDue']} | {a['monthsRemaining']} months remaining")
        else:
            logger.info(f"  📅 On schedule | {a['mid']} {a['name']} | "
                        f"Last: {a['lastDate']} | Next due: {a['nextDue']} | "
                        f"{a['monthsRemaining']} months remaining")

    # ── 7E: Final state ──
    logger.info("--- FINAL SYSTEM STATE ---")
    final_stats = {}
    with driver.session() as s:
        rows = s.run("""
            MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
            RETURN cg.gapStatus AS Status, count(m) AS Count ORDER BY Count DESC
        """)
        total = 0
        for row in rows:
            final_stats[row["Status"]] = row["Count"]
            logger.info(f"  {row['Status']:<20} {row['Count']:>3}")
            total += row["Count"]

        r  = s.run("MATCH (o:Outreach) RETURN count(o) AS c").single()
        r2 = s.run("MATCH (r:CareGapRecommendation) RETURN count(r) AS c").single()
        r3 = s.run("MATCH ()-[r:MATCHED_TO]->() RETURN count(r) AS c").single()
        r4 = s.run("MATCH (n:IdealPersona) RETURN count(n) AS c").single()
        logger.info(f"  Outreach records:        {r['c']}")
        logger.info(f"  Recommendations created: {r2['c']}")
        logger.info(f"  Persona matches:         {r3['c']}")
        logger.info(f"  Persona rulebook size:   {r4['c']} personas")

    driver.close()
    log_step_end(logger, 7, "Gap Closure Tracking", {
        **{f"Gap {k}": v for k, v in final_stats.items()},
        "Proactive alerts": sum(1 for a in approaching if a["proactiveFlag"]),
        "M0011 closure": status,
    })
    logger.info("🎉 ALL 7 STEPS COMPLETE — BCS Care Gap Engine fully operational")

if __name__ == "__main__":
    run_step7()
