"""
Step 2: BCS Matching Algorithm
Match each eligible member to their best-fit IdealPersona.
Writes MATCHED_TO relationship and inherits CareGapOutput properties.
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from bcs_personas import PERSONAS
from bcs_logger import get_logger, log_step_start, log_step_end, log_member

load_dotenv()
logger = get_logger("bcs.step2")
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

# ── STEP 2A: Fetch all member profiles from Neo4j ──────────────────────────

def get_all_member_profiles():
    """Fetch full profile for every member with a BCS CareGap."""
    query = """
    MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS'})
    MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
    OPTIONAL MATCH (m)-[:HAS_ENROLLMENT]->(e:Enrollment)
    OPTIONAL MATCH (m)-[:HAS_AGE_RULE_CHECK]->(arc:AgeRuleCheck)
    OPTIONAL MATCH (m)-[:HAS_EXCLUSION_PROFILE]->(ep:ExclusionProfile)
    OPTIONAL MATCH (m)-[:HAS_SCREENING_HISTORY]->(sh:ScreeningHistory)
    OPTIONAL MATCH (m)-[:HAS_CLINICAL_HISTORY]->(ch:ClinicalHistory)
    OPTIONAL MATCH (m)-[:HAS_SDOH]->(sd:SDOH)
    OPTIONAL MATCH (m)-[:HAS_CONSENT]->(con:Consent)
    RETURN m, d, e, arc, ep, sh, ch, sd, con, cg
    """
    profiles = []
    with driver.session() as session:
        result = session.run(query)
        for row in result:
            m = dict(row["m"]) if row["m"] else {}
            d = dict(row["d"]) if row["d"] else {}
            e = dict(row["e"]) if row["e"] else {}
            arc = dict(row["arc"]) if row["arc"] else {}
            ep = dict(row["ep"]) if row["ep"] else {}
            sh = dict(row["sh"]) if row["sh"] else {}
            ch = dict(row["ch"]) if row["ch"] else {}
            sd = dict(row["sd"]) if row["sd"] else {}
            con = dict(row["con"]) if row["con"] else {}
            cg = dict(row["cg"]) if row["cg"] else {}
            profiles.append({
                "member": m, "demographics": d, "enrollment": e,
                "age_rule": arc, "exclusion": ep, "screening": sh,
                "clinical": ch, "sdoh": sd, "consent": con, "care_gap": cg
            })
    return profiles


# ── STEP 2B: Determine member's BCS group ──────────────────────────────────

def determine_group(profile):
    """
    Classify member into one of the 10 persona groups.
    Returns: group name string
    """
    d = profile["demographics"]
    arc = profile["age_rule"]
    ep = profile["exclusion"]
    sh = profile["screening"]
    cg = profile["care_gap"]
    gender = d.get("administrativeGender", "")

    # 1. Check exclusions first
    if ep.get("anyExclusionPresent") == True:
        return "Excluded"
    if ep.get("bilateralMastectomy") == True:
        return "Excluded"
    if ep.get("hospice") == True or ep.get("palliativeCare") == True:
        return "Excluded"
    if ep.get("frailty") == True:
        return "Excluded"
    if ep.get("genderAffirmingSurgery") == True:
        return "Excluded"
    if ep.get("medicare66PlusInSNP_LTC") == True:
        return "Excluded"

    # 2. Check eligibility (gender + age)
    if gender != "Female":
        return "Not Eligible"
    
    age = d.get("age", 0)
    age_pass = arc.get("eligibilityAgeCheck", None)
    if age_pass == False or age < 42 or age > 74:
        return "Not Eligible"

    # 3. Check gap status from loaded data
    gap_status = cg.get("gapStatus", "OPEN")
    
    if gap_status == "CLOSED":
        return "Compliant"
    if gap_status == "EXCLUDED":
        return "Excluded"

    # 4. Determine screening status
    last_mammo = sh.get("lastMammogramDate")
    screening_status = sh.get("screeningStatus", "")
    falls_in_window = sh.get("fallsInLookbackWindow", False)

    if last_mammo is None or str(last_mammo) == "" or screening_status == "No mammogram claim found":
        return "Never Screened"

    # Has a mammogram but check if in window
    if falls_in_window:
        months_str = sh.get("monthsSinceLastScreen", "")
        try:
            months = int(str(months_str).replace(" months", ""))
        except (ValueError, TypeError):
            months = 99
        if 18 <= months <= 24:
            return "Proactive Window"
        return "Compliant"
    
    return "Overdue"


# ── STEP 2C: Score a member against a persona ──────────────────────────────

def safe_str(val):
    """Normalize value to lowercase string for comparison."""
    if val is None:
        return ""
    return str(val).strip().lower()

def match_field(member_val, persona_val):
    """
    Score a single field match.
    'Any' in persona = wildcard (always matches).
    'N/A' in persona = not applicable (skip).
    'PENDING' in member = unknown data (partial match).
    Exact match = 1.0, PENDING = 0.3, no match = 0.0
    """
    pv = safe_str(persona_val)
    mv = safe_str(member_val)
    
    if pv in ("any", "n/a", ""):
        return 1.0  # Wildcard — always matches
    if mv in ("pending", "pending — awaiting ehr data", "pending — awaiting member data", ""):
        return 0.3  # Unknown — partial credit
    if mv == pv:
        return 1.0  # Exact match
    if pv in mv or mv in pv:
        return 0.7  # Partial match (substring)
    return 0.0


def score_persona(profile, persona):
    """
    Score how well a member profile matches a given persona.
    Higher score = better match. Max theoretical = ~30.
    """
    score = 0.0
    
    # ── Group match (most important — 10 points) ──
    member_group = determine_group(profile)
    persona_group = persona["persona"]["group"]
    
    # Map member group to persona group names
    group_map = {
        "Excluded": ["Excluded"],
        "Not Eligible": ["Not Eligible"],
        "Never Screened": ["Never Screened"],
        "Overdue": ["Overdue — Very High Risk", "Overdue — High Risk", 
                     "Overdue — Medium Risk", "Overdue — Low Risk"],
        "Proactive Window": ["Proactive Window"],
        "Compliant": ["Compliant", "Compliant (False)"],
    }
    
    matching_groups = group_map.get(member_group, [])
    if persona_group in matching_groups:
        score += 10.0
    else:
        return 0.0  # Wrong group — skip entirely

    # ── Exclusion profile (3 points) ──
    ep = profile["exclusion"]
    pe = persona["exclusion"]
    for field in ["bilateralMastectomy", "hospice", "palliativeCare", "frailty", "genderAffirmingSurgery"]:
        score += match_field(ep.get(field), pe.get(field)) * 0.6

    # ── Screening profile (3 points) ──
    sh = profile["screening"]
    ps = persona["screening"]
    score += match_field(sh.get("screeningStatus"), ps.get("screeningStatus")) * 1.0
    score += match_field(sh.get("fallsInLookbackWindow"), ps.get("fallsInLookbackWindow")) * 0.5
    score += match_field(sh.get("cptCode"), ps.get("cptValid")) * 0.5
    score += match_field(sh.get("mammogramType"), ps.get("lastMammogramType")) * 0.5
    score += match_field(sh.get("hedisCompliant"), ps.get("cptValid")) * 0.5

    # ── Risk profile (5 points) — mostly PENDING for these members ──
    ch = profile["clinical"]
    pr = persona["risk"]
    for field in ["brcaStatus", "familyHistory", "denseBreast", "hrtUse", "bmi",
                  "priorBiopsy", "earlyMenarche", "firstPregnancyAfter30",
                  "noBreastfeeding", "sedentary", "alcoholUse"]:
        m_val = ch.get(field, "PENDING")
        p_val = pr.get(field, "Any")
        score += match_field(m_val, p_val) * 0.45

    # ── Engagement / SDOH (2 points) ──
    sd = profile["sdoh"]
    pg = persona["engagement"]
    score += match_field(sd.get("engagementLevel"), pg.get("engagementLevel")) * 0.5
    score += match_field(sd.get("knownBarrier"), pg.get("knownBarrier")) * 0.5
    score += match_field(sd.get("transportationAccess"), pg.get("transportationAccess")) * 0.5
    score += match_field(sd.get("preferredContact"), pg.get("preferredContact")) * 0.5

    # ── Age boundary bonus ──
    age = profile["demographics"].get("age", 0)
    pid = persona["persona"]["personaID"]
    if age == 42 and pid == "P-012":  # Newly eligible
        score += 2.0
    if age == 42 and pid in ("P-049", "P-050"):  # Edge cases
        score += 2.0

    return round(score, 2)


# ── STEP 2D: Find best matching persona ────────────────────────────────────

def find_best_persona(profile):
    """Find the persona with the highest match score for a member."""
    best_score = -1
    best_persona = None
    all_scores = []

    for persona in PERSONAS:
        s = score_persona(profile, persona)
        all_scores.append((persona["persona"]["personaID"], s))
        if s > best_score:
            best_score = s
            best_persona = persona

    # Sort for debugging
    all_scores.sort(key=lambda x: -x[1])
    top3 = all_scores[:3]

    return best_persona, best_score, top3


# ── STEP 2E: Write match to Neo4j ─────────────────────────────────────────

def write_match(member_id, persona_id, score, top3):
    """
    Create MATCHED_TO relationship between Member and IdealPersona.
    Also update CareGap with inherited output from persona.
    """
    with driver.session() as session:
        # Create the match relationship
        session.run("""
            MATCH (m:Member {memberID: $mid})
            MATCH (p:IdealPersona {personaID: $pid})
            MERGE (m)-[r:MATCHED_TO]->(p)
            SET r.matchScore = $score,
                r.matchDate = date(),
                r.top3Matches = $top3,
                r.algorithm = 'BCS-Step2-v1'
        """, mid=member_id, pid=persona_id, score=score,
             top3=str(top3))

        # Inherit CareGapOutput from persona to member's CareGap
        session.run("""
            MATCH (m:Member {memberID: $mid})-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS'})
            MATCH (p:IdealPersona {personaID: $pid})-[:HAS_CARE_GAP_OUTPUT]->(out:CareGapOutput)
            SET cg.matchedPersonaID = $pid,
                cg.matchScore = $score,
                cg.inheritedPriority = out.priorityLevel,
                cg.inheritedRiskCategory = out.riskCategory,
                cg.inheritedScreeningType = out.recommendedScreeningType,
                cg.inheritedActions = out.recommendedActions,
                cg.inheritedOutreachChannel = out.outreachChannel,
                cg.inheritedEscalationPath = out.escalationPath,
                cg.inheritedFollowUpDays = out.followUpDays
        """, mid=member_id, pid=persona_id, score=score)


# ── MAIN ──────────────────────────────────────────────────────────────────

def run_step2():
    log_step_start(logger, 2, "BCS Matching Algorithm")
    logger.info(f"Loaded persona rulebook: {len(PERSONAS)} personas")

    profiles = get_all_member_profiles()
    logger.info(f"Members with BCS CareGap fetched: {len(profiles)}")

    results = []
    group_counts = {}

    for profile in profiles:
        mid    = profile["member"].get("memberID", "?")
        name   = profile["member"].get("fullName", "?")
        age    = profile["demographics"].get("age", "?")
        gender = profile["demographics"].get("administrativeGender", "?")
        group  = determine_group(profile)
        gap    = profile["care_gap"].get("gapStatus", "?")

        group_counts[group] = group_counts.get(group, 0) + 1
        logger.debug(f"Classified {mid} | Age {age} | {gender} → Group: {group}")

        persona, score, top3 = find_best_persona(profile)

        if persona:
            pid   = persona["persona"]["personaID"]
            pname = persona["persona"]["personaName"]
            write_match(mid, pid, score, top3)
            results.append((mid, name, age, gender, group, gap, pid, pname, score))
            log_member(logger, mid, name,
                       f"matched → {pid} (score: {score})",
                       f"Gap: {gap} | Group: {group}")
            logger.debug(f"  Top-3: {top3}")
        else:
            results.append((mid, name, age, gender, group, gap, "NONE", "No match", 0))
            logger.warning(f"NO MATCH — {mid} | {name} | Group: {group}")

    # ── Summary ──
    logger.info("--- MATCHING SUMMARY ---")
    for g, c in sorted(group_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {g:<25} {c:>3} members")

    matched   = sum(1 for r in results if r[6] != "NONE")
    unmatched = len(results) - matched
    logger.info(f"Total matched:   {matched}/{len(results)}")
    if unmatched:
        logger.warning(f"Total unmatched: {unmatched}/{len(results)}")

    # ── Neo4j verification ──
    logger.info("--- NEO4J VERIFICATION ---")
    with driver.session() as session:
        result = session.run("""
            MATCH (m:Member)-[:MATCHED_TO]->(p:IdealPersona)
            MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS'})
            RETURN m.memberID AS mid, p.personaID AS pid,
                   cg.inheritedPriority AS priority,
                   cg.inheritedRiskCategory AS risk,
                   cg.inheritedOutreachChannel AS channel
            ORDER BY m.memberID
        """)
        for row in result:
            logger.info(f"  {row['mid']} → {row['pid']} | "
                        f"Priority: {str(row['priority']):<20} | "
                        f"Risk: {str(row['risk']):<12} | "
                        f"Channel: {row['channel']}")

    driver.close()
    log_step_end(logger, 2, "Matching Algorithm", {
        "Members processed": len(results),
        "Matched": matched,
        "Unmatched": unmatched,
        **{f"Group — {g}": c for g, c in group_counts.items()},
    })

if __name__ == "__main__":
    run_step2()
