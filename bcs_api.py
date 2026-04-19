"""
bcs_api.py — BCS Care Gap Engine REST API
Run: python bcs_api.py
Base URL: http://localhost:5000

Endpoints:
  GET  /health                    → API health check
  GET  /api/bcs/members           → All members with gap status
  GET  /api/bcs/members/<id>      → Single member full profile
  POST /api/bcs/check-member      → Instant gap check (no DB write required)
  POST /api/bcs/add-member        → Add member + run gap check + save to Neo4j
  POST /api/bcs/close-gap         → Close a gap with a mammogram claim
  GET  /api/bcs/outreach-queue    → All pending outreach records
  GET  /api/bcs/analytics         → Population-level compliance metrics
  GET  /api/bcs/personas          → List all 51 IdealPersonas
  GET  /api/bcs/personas/<id>     → Single persona details
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import date
from bcs_logger import get_logger
from bcs_step2_matching import find_best_persona
from bcs_check_member import (
    compute_age, check_eligibility, build_temp_profile,
    LOOKBACK_START, LOOKBACK_END, VALID_CPT
)

load_dotenv()
logger = get_logger("bcs.api")

app = Flask(__name__)
CORS(app)

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

# ── Helpers ────────────────────────────────────────────────────────────────

def neo4j_query(query, params=None):
    with driver.session() as s:
        return [dict(r) for r in s.run(query, params or {})]

def error(msg, code=400):
    return jsonify({"success": False, "error": msg}), code

def ok(data, msg="OK"):
    return jsonify({"success": True, "message": msg, "data": data})


# ── GET /health ────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    try:
        result = neo4j_query("RETURN 'connected' AS status")
        return ok({
            "api":    "BCS Care Gap Engine",
            "version":"1.2",
            "neo4j":  result[0]["status"],
            "timestamp": str(date.today())
        }, "API is healthy")
    except Exception as e:
        return error(f"Neo4j connection failed: {str(e)}", 503)


# ── GET /api/bcs/members ───────────────────────────────────────────────────

@app.route("/api/bcs/members", methods=["GET"])
def get_members():
    """List all members with their gap status. Optional filter: ?status=OPEN|CLOSED|NOT ELIGIBLE|EXCLUDED"""
    status_filter = request.args.get("status", "").upper()
    query = """
        MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
        MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
        OPTIONAL MATCH (m)-[:MATCHED_TO]->(p:IdealPersona)
        OPTIONAL MATCH (m)-[:HAS_RECOMMENDATION]->(rec:CareGapRecommendation)
        WHERE $status = '' OR cg.gapStatus = $status
        RETURN m.memberID AS memberID, m.fullName AS name,
               d.age AS age, d.administrativeGender AS gender,
               cg.gapStatus AS gapStatus,
               cg.gapClosedDate AS closedDate,
               p.personaID AS personaID, p.personaName AS personaName,
               rec.priorityLevel AS priority,
               rec.outreachChannel AS channel,
               rec.riskCategory AS riskCategory
        ORDER BY cg.gapStatus, d.age DESC
    """
    rows = neo4j_query(query, {"status": status_filter})
    logger.info(f"GET /api/bcs/members → {len(rows)} members (filter: '{status_filter or 'ALL'}')")
    return ok({"count": len(rows), "members": rows})


# ── GET /api/bcs/members/<id> ──────────────────────────────────────────────

@app.route("/api/bcs/members/<member_id>", methods=["GET"])
def get_member(member_id):
    """Full profile for a single member."""
    query = """
        MATCH (m:Member {memberID: $mid})
        OPTIONAL MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
        OPTIONAL MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
        OPTIONAL MATCH (m)-[:HAS_SCREENING_HISTORY]->(sh:ScreeningHistory)
        OPTIONAL MATCH (m)-[:MATCHED_TO]->(p:IdealPersona)
        OPTIONAL MATCH (m)-[:HAS_RECOMMENDATION]->(rec:CareGapRecommendation)
        OPTIONAL MATCH (m)-[:HAS_OUTREACH]->(o:Outreach)
        RETURN m, d, cg, sh, p, rec, o
    """
    rows = neo4j_query(query, {"mid": member_id})
    if not rows:
        return error(f"Member {member_id} not found", 404)

    r = rows[0]
    profile = {
        "member":      dict(r["m"]) if r["m"] else {},
        "demographics":dict(r["d"]) if r["d"] else {},
        "careGap":     dict(r["cg"]) if r["cg"] else {},
        "screening":   dict(r["sh"]) if r["sh"] else {},
        "persona":     dict(r["p"]) if r["p"] else {},
        "recommendation": dict(r["rec"]) if r["rec"] else {},
        "outreach":    dict(r["o"]) if r["o"] else {},
    }
    logger.info(f"GET /api/bcs/members/{member_id} → found")
    return ok(profile)


# ── POST /api/bcs/check-member ────────────────────────────────────────────

@app.route("/api/bcs/check-member", methods=["POST"])
def check_member():
    """
    Instant BCS gap check — does NOT save to Neo4j.
    Body (JSON):
    {
      "memberID": "M0031",
      "fullName": "Sarah Thompson",
      "dateOfBirth": "1970-05-14",
      "gender": "Female",
      "enrolled": true,
      "exclusions": {
        "bilateralMastectomy": false,
        "hospice": false,
        "frailty": false,
        "genderAffirmingSurgery": false
      },
      "lastMammogramDate": "2023-08-15",   // optional
      "cptCode": "77067"                    // optional
    }
    """
    body = request.get_json(silent=True)
    if not body:
        return error("Request body must be JSON")

    required = ["memberID", "fullName", "dateOfBirth", "gender", "enrolled"]
    for f in required:
        if f not in body:
            return error(f"Missing required field: '{f}'")

    try:
        dob = date.fromisoformat(body["dateOfBirth"])
    except ValueError:
        return error("dateOfBirth must be YYYY-MM-DD")

    mammo_date = None
    if body.get("lastMammogramDate"):
        try:
            mammo_date = date.fromisoformat(body["lastMammogramDate"])
        except ValueError:
            return error("lastMammogramDate must be YYYY-MM-DD")

    age = compute_age(dob)
    member = {
        "id":            body["memberID"],
        "name":          body["fullName"],
        "dob":           dob,
        "age":           age,
        "gender":        body["gender"],
        "enrolled":      body.get("enrolled", True),
        "exclusions":    body.get("exclusions", {
            "bilateralMastectomy": False, "hospice": False,
            "frailty": False, "genderAffirmingSurgery": False,
            "anyExclusionPresent": False
        }),
        "lastMammogram": mammo_date,
        "cptCode":       body.get("cptCode"),
        "clinicalRisk":  body.get("clinicalRisk", {}),
        "sdoh":          body.get("sdoh", {}),
        "engagementLevel": body.get("engagementLevel", "Unknown"),
        "knownBarrier":  body.get("knownBarrier", "None"),
    }

    gap_status, gap_reason = check_eligibility(member)
    profile   = build_temp_profile(member, gap_status)
    persona, score, top3 = find_best_persona(profile)

    persona_id   = persona["persona"]["personaID"]   if persona else "NONE"
    persona_name = persona["persona"]["personaName"] if persona else "No match"
    persona_out  = persona.get("output", {})         if persona else {}

    result = {
        "memberID":      body["memberID"],
        "fullName":      body["fullName"],
        "age":           age,
        "gender":        body["gender"],
        "gapStatus":     gap_status,
        "gapReason":     gap_reason,
        "matchedPersona": {
            "personaID":   persona_id,
            "personaName": persona_name,
            "matchScore":  score,
            "top3":        top3,
        },
        "recommendation": {
            "priorityLevel":      persona_out.get("priorityLevel"),
            "outreachChannel":    persona_out.get("outreachChannel"),
            "followUpDays":       persona_out.get("followUpDays"),
            "escalationPath":     persona_out.get("escalationPath"),
            "recommendedActions": persona_out.get("recommendedActions", []),
            "riskCategory":       persona_out.get("riskCategory"),
            "recommendedScreeningType": persona_out.get("recommendedScreeningType"),
        } if gap_status == "OPEN" else None,
        "hedisRules": {
            "lookbackWindow":    f"{LOOKBACK_START} to {LOOKBACK_END}",
            "validCPTCodes":     sorted(VALID_CPT),
            "eligibleAgeRange":  "42–74 (as of Dec 31, 2026)",
            "minAgeAtMammogram": 40,
        }
    }

    logger.info(f"POST /check-member → {body['memberID']} | {gap_status} | Persona: {persona_id} | Score: {score}")
    return ok(result, f"Gap check complete — Status: {gap_status}")


# ── POST /api/bcs/add-member ──────────────────────────────────────────────

@app.route("/api/bcs/add-member", methods=["POST"])
def add_member():
    """Same as check-member but SAVES to Neo4j graph."""
    from bcs_check_member import save_to_graph

    body = request.get_json(silent=True)
    if not body:
        return error("Request body must be JSON")

    required = ["memberID", "fullName", "dateOfBirth", "gender"]
    for f in required:
        if f not in body:
            return error(f"Missing required field: '{f}'")

    try:
        dob = date.fromisoformat(body["dateOfBirth"])
    except ValueError:
        return error("dateOfBirth must be YYYY-MM-DD")

    mammo_date = None
    if body.get("lastMammogramDate"):
        try:
            mammo_date = date.fromisoformat(body["lastMammogramDate"])
        except ValueError:
            return error("lastMammogramDate must be YYYY-MM-DD")

    age = compute_age(dob)
    member = {
        "id":            body["memberID"],
        "name":          body["fullName"],
        "dob":           dob,
        "age":           age,
        "gender":        body["gender"],
        "enrolled":      body.get("enrolled", True),
        "exclusions":    body.get("exclusions", {
            "bilateralMastectomy": False, "hospice": False,
            "frailty": False, "genderAffirmingSurgery": False,
            "anyExclusionPresent": False
        }),
        "lastMammogram": mammo_date,
        "cptCode":       body.get("cptCode"),
        "clinicalRisk":  body.get("clinicalRisk", {}),
        "sdoh":          body.get("sdoh", {}),
        "engagementLevel": body.get("engagementLevel", "Unknown"),
        "knownBarrier":  body.get("knownBarrier", "None"),
    }

    gap_status, gap_reason = check_eligibility(member)
    profile = build_temp_profile(member, gap_status)
    persona, score, top3 = find_best_persona(profile)

    persona_id   = persona["persona"]["personaID"]   if persona else "NONE"
    persona_name = persona["persona"]["personaName"] if persona else "No match"
    persona_out  = persona.get("output", {})         if persona else {}

    save_to_graph(member, gap_status, gap_reason, persona_id, score)

    result = {
        "memberID":    body["memberID"],
        "fullName":    body["fullName"],
        "age":         age,
        "gapStatus":   gap_status,
        "gapReason":   gap_reason,
        "savedToNeo4j": True,
        "matchedPersona": {
            "personaID": persona_id,
            "personaName": persona_name,
            "matchScore": score,
        },
        "recommendation": {
            "priorityLevel":   persona_out.get("priorityLevel"),
            "outreachChannel": persona_out.get("outreachChannel"),
            "followUpDays":    persona_out.get("followUpDays"),
            "escalationPath":  persona_out.get("escalationPath"),
        } if gap_status == "OPEN" else None,
    }

    logger.info(f"POST /add-member → {body['memberID']} SAVED | {gap_status} | {persona_id}")
    return ok(result, f"Member {body['memberID']} added and gap determined: {gap_status}"), 201


# ── POST /api/bcs/close-gap ───────────────────────────────────────────────

@app.route("/api/bcs/close-gap", methods=["POST"])
def close_gap_api():
    """
    Submit a mammogram claim to close a member's gap.
    Body:
    {
      "memberID": "M0009",
      "claimID": "CLM-2026-001",
      "cptCode": "77067",
      "serviceDate": "2026-03-15",
      "ageAtService": 71
    }
    """
    from bcs_step7_closure import validate_claim, close_gap

    body = request.get_json(silent=True)
    if not body:
        return error("Request body must be JSON")

    required = ["memberID", "claimID", "cptCode", "serviceDate", "ageAtService"]
    for f in required:
        if f not in body:
            return error(f"Missing required field: '{f}'")

    valid, reason = validate_claim(body["cptCode"], body["serviceDate"], body["ageAtService"])
    if not valid:
        logger.warning(f"POST /close-gap → REJECTED {body['memberID']} | {reason}")
        return jsonify({
            "success": False,
            "memberID": body["memberID"],
            "claimID":  body["claimID"],
            "accepted": False,
            "reason":   reason,
        }), 422

    status, close_reason = close_gap(
        body["memberID"], body["claimID"],
        body["cptCode"], body["serviceDate"],
        body["ageAtService"], "API claim submission"
    )

    logger.info(f"POST /close-gap → {body['memberID']} | {status} | {close_reason}")
    return ok({
        "memberID":    body["memberID"],
        "claimID":     body["claimID"],
        "gapStatus":   "CLOSED",
        "closeReason": close_reason,
    }, f"Gap closed for {body['memberID']}")


# ── GET /api/bcs/outreach-queue ───────────────────────────────────────────

@app.route("/api/bcs/outreach-queue", methods=["GET"])
def outreach_queue():
    """All pending outreach records ordered by priority."""
    query = """
        MATCH (m:Member)-[:HAS_OUTREACH]->(o:Outreach {outreachStatus:'Pending'})
        MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
        OPTIONAL MATCH (o)-[:PERFORMED_BY]->(cm:CareManager)
        RETURN m.memberID AS memberID, m.fullName AS name,
               d.age AS age,
               o.outreachID AS outreachID,
               o.channel AS channel,
               o.priorityLevel AS priority,
               o.outreachDate AS outreachDate,
               o.followUpDate AS followUpDate,
               o.outcome AS outcome,
               cm.careManagerID AS careManagerID,
               cm.careManagerName AS careManagerName
        ORDER BY
          CASE o.priorityLevel
            WHEN 'VERY HIGH (CRITICAL)' THEN 1
            WHEN 'VERY HIGH' THEN 2
            WHEN 'HIGH' THEN 3
            WHEN 'MEDIUM' THEN 4
            ELSE 5
          END, d.age DESC
    """
    rows = neo4j_query(query)
    logger.info(f"GET /api/bcs/outreach-queue → {len(rows)} pending records")
    return ok({"count": len(rows), "queue": rows})


# ── GET /api/bcs/analytics ────────────────────────────────────────────────

@app.route("/api/bcs/analytics", methods=["GET"])
def analytics():
    """Population-level BCS compliance metrics."""
    # Gap status distribution
    gap_dist = neo4j_query("""
        MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
        RETURN cg.gapStatus AS status, count(m) AS count
        ORDER BY count DESC
    """)

    # Compliance rate (eligible females 42–74)
    eligible = neo4j_query("""
        MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
        MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
        WHERE d.administrativeGender = 'Female' AND d.age >= 42 AND d.age <= 74
        RETURN cg.gapStatus AS status, count(m) AS count
    """)

    open_count   = sum(r["count"] for r in eligible if r["status"] == "OPEN")
    closed_count = sum(r["count"] for r in eligible if r["status"] == "CLOSED")
    total_eligible = open_count + closed_count
    compliance_rate = round((closed_count / total_eligible * 100), 1) if total_eligible > 0 else 0

    # Age band distribution
    age_bands = neo4j_query("""
        MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
        MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
        WHERE d.administrativeGender = 'Female' AND d.age >= 42 AND d.age <= 74
        RETURN
          CASE
            WHEN d.age <= 50 THEN '42-50'
            WHEN d.age <= 60 THEN '51-60'
            WHEN d.age <= 70 THEN '61-70'
            ELSE '71-74'
          END AS ageBand,
          cg.gapStatus AS status,
          count(m) AS count
        ORDER BY ageBand, status
    """)

    # Persona distribution
    persona_dist = neo4j_query("""
        MATCH (m:Member)-[:MATCHED_TO]->(p:IdealPersona)
        RETURN p.personaID AS personaID, p.personaName AS personaName,
               count(m) AS memberCount
        ORDER BY memberCount DESC
    """)

    # Risk distribution (OPEN gaps only)
    risk_dist = neo4j_query("""
        MATCH (m:Member)-[:HAS_RECOMMENDATION]->(rec:CareGapRecommendation)
        MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'OPEN'})
        RETURN rec.riskCategory AS riskCategory, count(m) AS count
        ORDER BY count DESC
    """)

    # Outreach channel distribution
    channel_dist = neo4j_query("""
        MATCH (m:Member)-[:HAS_OUTREACH]->(o:Outreach)
        RETURN o.channel AS channel, count(o) AS count
        ORDER BY count DESC
    """)

    result = {
        "gapStatusDistribution": gap_dist,
        "complianceMetrics": {
            "totalEligible":    total_eligible,
            "compliant":        closed_count,
            "nonCompliant":     open_count,
            "complianceRate":   f"{compliance_rate}%",
            "gapRate":          f"{round(100 - compliance_rate, 1)}%",
        },
        "ageBandDistribution":  age_bands,
        "personaDistribution":  persona_dist,
        "riskDistribution":     risk_dist,
        "outreachChannels":     channel_dist,
    }

    logger.info(f"GET /api/bcs/analytics → Compliance: {compliance_rate}%")
    return ok(result)


# ── GET /api/bcs/personas ─────────────────────────────────────────────────

@app.route("/api/bcs/personas", methods=["GET"])
def list_personas():
    """List all 51 IdealPersonas with their group and gap output summary."""
    group_filter = request.args.get("group", "")
    query = """
        MATCH (p:IdealPersona)
        OPTIONAL MATCH (p)-[:HAS_CARE_GAP_OUTPUT]->(out:CareGapOutput)
        WHERE $group = '' OR p.group CONTAINS $group
        RETURN p.personaID AS personaID, p.personaName AS personaName,
               p.group AS group,
               out.gapStatus AS gapStatus,
               out.priorityLevel AS priority,
               out.riskCategory AS riskCategory,
               out.outreachChannel AS outreachChannel
        ORDER BY p.personaID
    """
    rows = neo4j_query(query, {"group": group_filter})
    logger.info(f"GET /api/bcs/personas → {len(rows)} personas")
    return ok({"count": len(rows), "personas": rows})


# ── GET /api/bcs/personas/<id> ────────────────────────────────────────────

@app.route("/api/bcs/personas/<persona_id>", methods=["GET"])
def get_persona(persona_id):
    """Full 9-node details for a single persona."""
    query = """
        MATCH (p:IdealPersona {personaID: $pid})
        OPTIONAL MATCH (p)-[:HAS_AGE_RULE]->(age:AgeRuleCheck)
        OPTIONAL MATCH (p)-[:HAS_ENROLLMENT]->(enr:EnrollmentProfile)
        OPTIONAL MATCH (p)-[:HAS_SCREENING]->(scr:ScreeningProfile)
        OPTIONAL MATCH (p)-[:HAS_RISK]->(risk:RiskProfile)
        OPTIONAL MATCH (p)-[:HAS_COMORBIDITY]->(com:ComorbidityProfile)
        OPTIONAL MATCH (p)-[:HAS_EXCLUSION]->(exc:ExclusionProfile)
        OPTIONAL MATCH (p)-[:HAS_ENGAGEMENT]->(eng:EngagementProfile)
        OPTIONAL MATCH (p)-[:HAS_CARE_GAP_OUTPUT]->(out:CareGapOutput)
        RETURN p, age, enr, scr, risk, com, exc, eng, out
    """
    rows = neo4j_query(query, {"pid": persona_id})
    if not rows:
        return error(f"Persona {persona_id} not found", 404)

    r = rows[0]
    persona = {
        "persona":           dict(r["p"])   if r["p"]   else {},
        "ageRuleCheck":      dict(r["age"]) if r["age"] else {},
        "enrollmentProfile": dict(r["enr"]) if r["enr"] else {},
        "screeningProfile":  dict(r["scr"]) if r["scr"] else {},
        "riskProfile":       dict(r["risk"])if r["risk"]else {},
        "comorbidityProfile":dict(r["com"]) if r["com"] else {},
        "exclusionProfile":  dict(r["exc"]) if r["exc"] else {},
        "engagementProfile": dict(r["eng"]) if r["eng"] else {},
        "careGapOutput":     dict(r["out"]) if r["out"] else {},
    }
    logger.info(f"GET /api/bcs/personas/{persona_id} → found")
    return ok(persona)


# ── Error handlers ─────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"success": False, "error": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal error: {str(e)}")
    return jsonify({"success": False, "error": "Internal server error"}), 500


# ── Startup ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("=" * 55)
    logger.info("  BCS Care Gap Engine — REST API v1.2")
    logger.info("  http://localhost:5000")
    logger.info("=" * 55)
    logger.info("  GET  /health")
    logger.info("  GET  /api/bcs/members")
    logger.info("  GET  /api/bcs/members/<id>")
    logger.info("  POST /api/bcs/check-member")
    logger.info("  POST /api/bcs/add-member")
    logger.info("  POST /api/bcs/close-gap")
    logger.info("  GET  /api/bcs/outreach-queue")
    logger.info("  GET  /api/bcs/analytics")
    logger.info("  GET  /api/bcs/personas")
    logger.info("  GET  /api/bcs/personas/<id>")
    logger.info("=" * 55)
    app.run(debug=True, host="0.0.0.0", port=5000)
