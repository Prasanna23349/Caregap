"""
Step 3: Inherit Care Gap Outputs
For each matched member, pull the full CareGapOutput + RiskProfile + EngagementProfile
from their matched IdealPersona and write a structured CareGapRecommendation node.
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import date
from bcs_logger import get_logger, log_step_start, log_step_end, log_member

load_dotenv()
logger = get_logger("bcs.step3")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

# ── 3A: Fetch all matched members with persona outputs ─────────────────────

def get_matched_members():
    """Fetch every member that has a MATCHED_TO persona relationship."""
    query = """
    MATCH (m:Member)-[rel:MATCHED_TO]->(p:IdealPersona)
    MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS'})
    MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
    MATCH (p)-[:HAS_CARE_GAP_OUTPUT]->(out:CareGapOutput)
    MATCH (p)-[:HAS_RISK]->(risk:RiskProfile)
    MATCH (p)-[:HAS_ENGAGEMENT]->(eng:EngagementProfile)
    MATCH (p)-[:HAS_COMORBIDITY]->(com:ComorbidityProfile)
    MATCH (p)-[:HAS_EXCLUSION]->(exc:ExclusionProfile)
    OPTIONAL MATCH (m)-[:HAS_SCREENING_HISTORY]->(sh:ScreeningHistory)
    RETURN m, d, cg, p, out, risk, eng, com, exc, sh, rel.matchScore AS score
    ORDER BY m.memberID
    """
    rows = []
    with driver.session() as s:
        result = s.run(query)
        for row in result:
            rows.append({
                "member":   dict(row["m"]),
                "demo":     dict(row["d"]),
                "cg":       dict(row["cg"]),
                "persona":  dict(row["p"]),
                "output":   dict(row["out"]),
                "risk":     dict(row["risk"]),
                "eng":      dict(row["eng"]),
                "com":      dict(row["com"]),
                "exc":      dict(row["exc"]),
                "sh":       dict(row["sh"]) if row["sh"] else {},
                "score":    row["score"],
            })
    return rows


# ── 3B: Build recommendation record ───────────────────────────────────────

def build_recommendation(row):
    """
    Construct a full recommendation dict from the persona outputs.
    Applies overrides where member data is known (e.g. consent opt-out).
    """
    mid    = row["member"]["memberID"]
    out    = row["output"]
    eng    = row["eng"]
    risk   = row["risk"]
    com    = row["com"]
    cg     = row["cg"]
    demo   = row["demo"]
    sh     = row["sh"]
    persona_id   = row["persona"]["personaID"]
    persona_name = row["persona"]["personaName"]
    gap_status   = cg.get("gapStatus", "OPEN")

    # Actions: use inherited list from Step 2 if present, else from persona
    actions = out.get("recommendedActions", [])
    if isinstance(actions, str):
        actions = actions.strip("[]").split(",")

    # Channel override: if gap is CLOSED or NOT ELIGIBLE → no outreach needed
    if gap_status in ("CLOSED", "NOT ELIGIBLE", "EXCLUDED"):
        channel   = "None — gap already resolved or not applicable"
        priority  = "N/A"
        follow_up = "N/A"
        escalation= "N/A"
        actions   = ["No outreach action required"]
    else:
        channel    = out.get("outreachChannel", eng.get("preferredContact", "SMS"))
        priority   = out.get("priorityLevel", "MEDIUM")
        follow_up  = out.get("followUpDays", 21)
        escalation = out.get("escalationPath", "PCP")

    # Risk narrative
    risk_flags = []
    if risk.get("brcaStatus") == "Positive":
        risk_flags.append("BRCA+")
    if risk.get("familyHistory") not in (False, None, "None", "N/A", "Any"):
        risk_flags.append("Family History")
    if risk.get("denseBreast") not in (False, None, "No", "N/A", "Any"):
        risk_flags.append("Dense Breast")
    if risk.get("hrtUse") == True:
        risk_flags.append("HRT Use")
    if risk.get("priorBiopsy") not in (False, None, "None", "N/A", "Any"):
        risk_flags.append(f"Prior Biopsy ({risk.get('priorBiopsy')})")
    if com.get("mentalHealthCondition") not in (False, None, "None", "N/A", "Any", False):
        risk_flags.append(f"Mental Health: {com.get('mentalHealthCondition')}")

    barriers = []
    if eng.get("knownBarrier") not in (None, "None", "N/A", "Any"):
        barriers.append(eng.get("knownBarrier"))
    if not eng.get("transportationAccess", True):
        barriers.append("No transportation")

    return {
        "recID":              f"REC-BCS-{mid}",
        "memberID":           mid,
        "memberName":         row["member"].get("fullName", ""),
        "age":                demo.get("age", ""),
        "gender":             demo.get("administrativeGender", ""),
        "gapStatus":          gap_status,
        "matchedPersonaID":   persona_id,
        "matchedPersonaName": persona_name,
        "matchScore":         row["score"],
        "priorityLevel":      priority,
        "riskCategory":       out.get("riskCategory", "Unknown"),
        "riskFlags":          risk_flags if risk_flags else ["None identified (clinical data pending)"],
        "knownBarriers":      barriers if barriers else ["None"],
        "recommendedScreeningType": out.get("recommendedScreeningType", "2D Mammogram"),
        "recommendedActions": actions,
        "outreachChannel":    channel,
        "escalationPath":     escalation,
        "followUpDays":       follow_up,
        "recommendationDate": str(date.today()),
        "dataCompleteness":   "COMPLETE" if gap_status != "OPEN" else "COMPLETE — EHR Enriched",
    }


# ── 3C: Write recommendation node to Neo4j ────────────────────────────────

def write_recommendation(rec):
    """
    MERGE a CareGapRecommendation node linked to the member and their CareGap.
    """
    with driver.session() as s:
        s.run("""
            MERGE (r:CareGapRecommendation {recID: $recID})
            SET r.memberID               = $memberID,
                r.gapStatus              = $gapStatus,
                r.matchedPersonaID       = $matchedPersonaID,
                r.matchScore             = $matchScore,
                r.priorityLevel          = $priorityLevel,
                r.riskCategory           = $riskCategory,
                r.riskFlags              = $riskFlags,
                r.knownBarriers          = $knownBarriers,
                r.recommendedScreeningType = $recommendedScreeningType,
                r.recommendedActions     = $recommendedActions,
                r.outreachChannel        = $outreachChannel,
                r.escalationPath         = $escalationPath,
                r.followUpDays           = $followUpDays,
                r.recommendationDate     = $recommendationDate,
                r.dataCompleteness       = $dataCompleteness
        """, **rec)

        # Link: Member → CareGapRecommendation
        s.run("""
            MATCH (m:Member {memberID: $memberID})
            MATCH (r:CareGapRecommendation {recID: $recID})
            MERGE (m)-[:HAS_RECOMMENDATION]->(r)
        """, memberID=rec["memberID"], recID=rec["recID"])

        # Link: CareGap → CareGapRecommendation and update priority
        s.run("""
            MATCH (cg:CareGap {measureID: 'BCS'})
            WHERE cg.memberID = $memberID OR
                  exists { (m:Member {memberID: $memberID})-[:HAS_CARE_GAP]->(cg) }
            MATCH (r:CareGapRecommendation {recID: $recID})
            MERGE (cg)-[:GENERATED_RECOMMENDATION]->(r)
            SET cg.priorityLevel = $priorityLevel
        """, memberID=rec["memberID"], recID=rec["recID"], priorityLevel=rec["priorityLevel"])


# ── 3D: Print care plan for OPEN gap members ──────────────────────────────

def print_care_plan(rec):
    if rec["gapStatus"] not in ("OPEN",):
        return
    print(f"\n  ┌── {rec['memberID']} | {rec['memberName']} | Age {rec['age']}")
    print(f"  │  Persona  : {rec['matchedPersonaID']} — {rec['matchedPersonaName']}")
    print(f"  │  Priority : {rec['priorityLevel']}  |  Risk: {rec['riskCategory']}")
    print(f"  │  Screening: {rec['recommendedScreeningType']}")
    print(f"  │  Channel  : {rec['outreachChannel']}")
    print(f"  │  Barriers : {', '.join(rec['knownBarriers'])}")
    print(f"  │  Risk Flags: {', '.join(rec['riskFlags'])}")
    print(f"  │  Follow-up: {rec['followUpDays']} days")
    print(f"  │  Escalation: {rec['escalationPath']}")
    print(f"  │  Actions:")
    for a in rec["recommendedActions"]:
        if isinstance(a, str):
            a = a.strip().strip("'")
        print(f"  │    → {a}")
    print(f"  └── Data: {rec['dataCompleteness']}")


# ── MAIN ──────────────────────────────────────────────────────────────────

def run_step3():
    log_step_start(logger, 3, "Inherit Care Gap Outputs")

    matched = get_matched_members()
    logger.info(f"Total matched members fetched: {len(matched)}")

    recommendations = []
    for row in matched:
        rec = build_recommendation(row)
        write_recommendation(rec)
        recommendations.append(rec)
        log_member(logger, rec["memberID"], rec["memberName"],
                   f"Rec created → {rec['matchedPersonaID']} | Priority: {rec['priorityLevel']}",
                   f"Gap: {rec['gapStatus']} | Risk: {rec['riskCategory']}")
        if rec["gapStatus"] == "OPEN":
            logger.debug(f"  Actions: {rec['recommendedActions']}")
            logger.debug(f"  Barriers: {rec['knownBarriers']}")

    # ── Open care plans ──
    open_recs = [r for r in recommendations if r["gapStatus"] == "OPEN"]
    logger.info(f"--- CARE PLANS GENERATED: {len(open_recs)} OPEN gap members ---")
    for rec in open_recs:
        logger.info(f"  {rec['memberID']} | {rec['memberName']} | Age {rec['age']} | "
                    f"{rec['priorityLevel']} | Channel: {rec['outreachChannel']} | "
                    f"Follow-up: {rec['followUpDays']} days")

    # ── Priority breakdown ──
    priorities = {}
    for r in open_recs:
        p = str(r["priorityLevel"])
        priorities[p] = priorities.get(p, 0) + 1
    logger.info("--- PRIORITY BREAKDOWN (OPEN gaps) ---")
    for p, c in sorted(priorities.items(), key=lambda x: -x[1]):
        logger.info(f"  {p:<35} {c:>2} members")

    # ── Neo4j verify ──
    with driver.session() as s:
        r  = s.run("MATCH (r:CareGapRecommendation) RETURN count(r) AS c").single()
        r2 = s.run("MATCH (m:Member)-[:HAS_RECOMMENDATION]->(r:CareGapRecommendation) RETURN count(r) AS c").single()
        logger.info(f"CareGapRecommendation nodes created:     {r['c']}")
        logger.info(f"HAS_RECOMMENDATION relationships:        {r2['c']}")

    log_step_end(logger, 3, "Inherit Care Gap Outputs", {
        "Total recommendations created": len(recommendations),
        "OPEN gap care plans": len(open_recs),
        "Priority breakdown": priorities,
    })

if __name__ == "__main__":
    run_step3()
