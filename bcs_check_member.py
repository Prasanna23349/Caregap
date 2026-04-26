"""
bcs_check_member.py — Add a single member and instantly check BCS care gap.
Usage: python bcs_check_member.py
       (Interactive CLI — enter member details when prompted)
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import date, datetime
from bcs_personas import PERSONAS
from bcs_logger import get_logger
from bcs_config import BCS_CONFIG
from bcs_step2_matching import (
    determine_group, score_persona, find_best_persona
)

load_dotenv()
logger = get_logger("bcs.check_member")
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

# All constants loaded dynamically from Neo4j QualityMeasure node
LOOKBACK_START       = BCS_CONFIG["LOOKBACK_START"]
LOOKBACK_END         = BCS_CONFIG["LOOKBACK_END"]
PROACTIVE_START      = BCS_CONFIG["PROACTIVE_START"]
VALID_CPT            = BCS_CONFIG["VALID_CPT"]
MEASUREMENT_YEAR_END = BCS_CONFIG["MEASUREMENT_YEAR_END"]
AGE_MIN              = BCS_CONFIG["AGE_MIN"]
AGE_MAX              = BCS_CONFIG["AGE_MAX"]
LOOKBACK_AGE_MIN     = BCS_CONFIG["LOOKBACK_AGE_MIN"]


# ── Helpers ────────────────────────────────────────────────────────────────

def ask(prompt, default=None, choices=None):
    while True:
        suffix = f" [{default}]" if default else ""
        if choices:
            suffix += f" ({'/'.join(choices)})"
        val = input(f"  {prompt}{suffix}: ").strip()
        if not val and default is not None:
            return default
        if choices and val.lower() not in [c.lower() for c in choices]:
            print(f"    ⚠  Please enter one of: {', '.join(choices)}")
            continue
        if val:
            return val

def ask_date(prompt, required=False):
    while True:
        val = input(f"  {prompt} (YYYY-MM-DD, or press Enter to skip): ").strip()
        if not val:
            if required:
                print("    ⚠  This field is required.")
                continue
            return None
        try:
            return date.fromisoformat(val)
        except ValueError:
            print("    ⚠  Invalid date. Use YYYY-MM-DD format.")


# ── Eligibility engine ─────────────────────────────────────────────────────

def compute_age(dob: date) -> int:
    today = MEASUREMENT_YEAR_END
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def check_eligibility(member):
    """Run BCS-E eligibility and gap determination logic."""
    age    = member["age"]
    gender = member["gender"]
    dob    = member["dob"]
    excl   = member["exclusions"]
    mammo  = member["lastMammogram"]
    cpt    = member["cptCode"]
    enrolled = member["enrolled"]

    reasons = []

    # ── Exclusion check ──
    if excl.get("bilateralMastectomy"):
        return "EXCLUDED", "Bilateral mastectomy — excluded from BCS measure"
    if excl.get("hospice"):
        return "EXCLUDED", "Hospice or palliative care — excluded from BCS measure"
    if excl.get("frailty"):
        return "EXCLUDED", "Frailty + advanced illness — excluded from BCS measure"
    if excl.get("genderAffirmingSurgery"):
        return "EXCLUDED", "Gender-affirming surgery — excluded from BCS measure"

    # ── Enrollment check ──
    if not enrolled:
        return "NOT ELIGIBLE", "Not continuously enrolled"

    # ── Gender check ──
    if gender.lower() != "female":
        return "NOT ELIGIBLE", f"Administrative gender is {gender} — BCS applies to females only"

    # ── Age check ──
    if age < AGE_MIN:
        return "NOT ELIGIBLE", f"Age {age} — below BCS minimum of {AGE_MIN} (as of Dec 31, {MEASUREMENT_YEAR_END.year})"
    if age > AGE_MAX:
        return "NOT ELIGIBLE", f"Age {age} — above BCS maximum of {AGE_MAX} (as of Dec 31, {MEASUREMENT_YEAR_END.year})"

    # ── Mammogram check ──
    if mammo is None:
        return "OPEN", f"No mammogram claim found in lookback window ({LOOKBACK_START.strftime('%b %d, %Y')} — {LOOKBACK_END.strftime('%b %d, %Y')})"

    # CPT validation
    if cpt not in VALID_CPT:
        return "OPEN", f"CPT {cpt} is not a valid BCS mammogram code. Valid: {', '.join(sorted(VALID_CPT))}"

    # Date window check
    if mammo < LOOKBACK_START or mammo > LOOKBACK_END:
        return "OPEN", (f"Mammogram on {mammo} falls outside lookback window "
                        f"({LOOKBACK_START} — {LOOKBACK_END})")

    # Age at mammogram check
    age_at_mammo = mammo.year - dob.year - ((mammo.month, mammo.day) < (dob.month, dob.day))
    if age_at_mammo < LOOKBACK_AGE_MIN:
        return "OPEN", (f"Member was {age_at_mammo} years old at mammogram on {mammo}. "
                        f"HEDIS requires age ≥ {LOOKBACK_AGE_MIN} at time of service.")

    # Proactive window check
    if mammo >= PROACTIVE_START:
        months_since = round((LOOKBACK_END - mammo).days / 30.4, 1)
        return "CLOSED", (f"Valid mammogram on {mammo} (CPT {cpt}). "
                          f"In proactive window ({months_since} months ago). Gap is CLOSED.")

    months_since = round((LOOKBACK_END - mammo).days / 30.4, 1)
    return "CLOSED", (f"Valid mammogram on {mammo} (CPT {cpt}). "
                      f"{months_since} months ago. Gap is CLOSED.")


# ── Persona matcher ────────────────────────────────────────────────────────

def build_temp_profile(member, gap_status):
    """Build a profile dict matching the format expected by bcs_step2_matching."""
    risk = member.get("clinicalRisk", {})
    sdoh = member.get("sdoh", {})
    
    return {
        "member": {"memberID": member["id"], "fullName": member["name"]},
        "demographics": {
            "administrativeGender": member["gender"],
            "age": member["age"],
        },
        "enrollment": {"continuouslyEnrolled": member["enrolled"]},
        "age_rule": {
            "eligibilityAgeCheck": AGE_MIN <= member["age"] <= AGE_MAX,
            "lookbackAgeCheck": True,
        },
        "exclusion": member["exclusions"],
        "screening": {
            "screeningStatus": "No mammogram claim found" if member["lastMammogram"] is None
                               else "Mammogram found",
            "fallsInLookbackWindow": gap_status == "CLOSED",
            "cptCode": member["cptCode"],
            "lastMammogramDate": str(member["lastMammogram"]) if member["lastMammogram"] else None,
            "hedisCompliant": gap_status == "CLOSED",
        },
        "clinical": {
            "brcaStatus":          risk.get("brcaStatus",       "PENDING"),
            "familyHistory":       risk.get("familyHistory",    "PENDING"),
            "denseBreast":         risk.get("denseBreast",      "PENDING"),
            "hrtUse":              risk.get("hrtUse",           "PENDING"),
            "bmi":                 risk.get("bmi",              "PENDING"),
            "priorBiopsy":         risk.get("priorBiopsy",      "PENDING"),
            "earlyMenarche":       risk.get("earlyMenarche",    "PENDING"),
            "firstPregnancyAfter30": risk.get("firstPregnancyAfter30", "PENDING"),
            "noBreastfeeding":     risk.get("noBreastfeeding",  "PENDING"),
            "sedentary":           risk.get("sedentary",        "PENDING"),
            "alcoholUse":          risk.get("alcoholUse",       "PENDING"),
        },
        "sdoh": {
            "engagementLevel":      sdoh.get("engagementLevel",     member.get("engagementLevel", "PENDING")),
            "knownBarrier":         sdoh.get("knownBarrier",        member.get("knownBarrier", "None")),
            "transportationAccess": sdoh.get("transportationAccess", True),
            "languageBarrier":      sdoh.get("languageBarrier",     False),
            "fearBarrier":          sdoh.get("fearBarrier",         False),
            "costBarrier":          sdoh.get("costBarrier",         False),
        },
        "consent": {"optOutOfOutreach": False},
        "care_gap": {"gapStatus": gap_status, "measureID": "BCS"},
    }


# ── Save to Neo4j (optional) ───────────────────────────────────────────────

def save_to_graph(member, gap_status, gap_reason, persona_id, score):
    """Write the new member and their gap result into Neo4j."""
    mid = member["id"]
    with driver.session() as s:
        s.run("""
            MERGE (m:Member {memberID: $mid})
            SET m.fullName = $name, m.source = 'manual_check'
        """, mid=mid, name=member["name"])

        s.run("""
            MERGE (m:Member {memberID: $mid})-[:HAS_DEMOGRAPHICS]->(d:Demographics)
            SET d.dateOfBirth         = date($dob),
                d.age                 = $age,
                d.administrativeGender = $gender
        """, mid=mid, dob=str(member["dob"]), age=member["age"], gender=member["gender"])

        s.run("""
            MERGE (m:Member {memberID: $mid})-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS'})
            SET cg.careGapID       = $cgid,
                cg.gapStatus       = $status,
                cg.gapReason       = $reason,
                cg.matchedPersonaID= $pid,
                cg.matchScore      = $score,
                cg.createdDate     = date($today),
                cg.source          = 'manual_check'
        """, mid=mid, cgid=f"GAP-BCS-{mid}", status=gap_status,
             reason=gap_reason, pid=persona_id, score=score,
             today=str(date.today()))

        if gap_status == "OPEN":
            s.run("""
                MATCH (m:Member {memberID: $mid})-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
                MATCH (p:IdealPersona {personaID: $pid})-[:HAS_CARE_GAP_OUTPUT]->(out:CareGapOutput)
                SET cg.inheritedPriority     = out.priorityLevel,
                    cg.inheritedActions      = out.recommendedActions,
                    cg.inheritedChannel      = out.outreachChannel,
                    cg.inheritedFollowUpDays = out.followUpDays
            """, mid=mid, pid=persona_id)

        s.run("""
            MATCH (m:Member {memberID: $mid})-[:MATCHED_TO]->(p) DELETE (m)-[:MATCHED_TO]->(p)
        """, mid=mid)
        s.run("""
            MATCH (m:Member {memberID: $mid}), (p:IdealPersona {personaID: $pid})
            MERGE (m)-[:MATCHED_TO]->(p)
        """, mid=mid, pid=persona_id)

    logger.info(f"✅ Member {mid} saved to Neo4j graph")


# ── Main interactive check ─────────────────────────────────────────────────

def run_check():
    print("\n" + "=" * 62)
    print("  BCS CARE GAP CHECK — Add a Member & Detect Gap Instantly")
    print("=" * 62)

    # ── Collect member details ──
    print("\n📋 MEMBER DETAILS")
    mid    = ask("Member ID (e.g. M0031)")
    name   = ask("Full name")
    dob    = ask_date("Date of birth", required=True)
    gender = ask("Administrative gender", choices=["Female", "Male", "Other"])
    enrolled = ask("Continuously enrolled?", default="yes", choices=["yes", "no"]) == "yes"

    age = compute_age(dob)
    print(f"      → Age as of Dec 31, {MEASUREMENT_YEAR_END.year}: {age}")

    # ── Exclusions ──
    print("\n🚫 EXCLUSIONS (press Enter to skip each)")
    excl_mastectomy = ask("Bilateral mastectomy?", default="no", choices=["yes", "no"]) == "yes"
    excl_hospice    = ask("Hospice / palliative care?", default="no", choices=["yes", "no"]) == "yes"
    excl_frailty    = ask("Frailty + advanced illness?", default="no", choices=["yes", "no"]) == "yes"
    excl_gender_surg= ask("Gender-affirming surgery?", default="no", choices=["yes", "no"]) == "yes"

    exclusions = {
        "bilateralMastectomy":  excl_mastectomy,
        "hospice":              excl_hospice,
        "frailty":              excl_frailty,
        "genderAffirmingSurgery": excl_gender_surg,
        "anyExclusionPresent":  any([excl_mastectomy, excl_hospice, excl_frailty, excl_gender_surg]),
    }

    # ── Mammogram history ──
    print("\n🩻 MAMMOGRAM HISTORY")
    has_mammo = ask("Has had a mammogram?", default="no", choices=["yes", "no"]) == "yes"
    mammo_date = None
    cpt_code   = None
    if has_mammo:
        mammo_date = ask_date("Date of last mammogram")
        cpt_code   = ask("CPT code", default="77067")

    member = {
        "id":              mid,
        "name":            name,
        "dob":             dob,
        "age":             age,
        "gender":          gender,
        "enrolled":        enrolled,
        "exclusions":      exclusions,
        "lastMammogram":   mammo_date,
        "cptCode":         cpt_code,
        "engagementLevel": "Unknown",
        "knownBarrier":    "None",
    }

    # ── Run eligibility ──
    gap_status, gap_reason = check_eligibility(member)

    # ── Run persona match ──
    profile = build_temp_profile(member, gap_status)
    persona, score, top3 = find_best_persona(profile)
    persona_id   = persona["persona"]["personaID"] if persona else "NONE"
    persona_name = persona["persona"]["personaName"] if persona else "No match"
    persona_out  = persona.get("output", {}) if persona else {}

    # ── Print result ──
    print("\n" + "=" * 62)
    print("  ✅ BCS CARE GAP RESULT")
    print("=" * 62)
    status_icons = {
        "OPEN":         "🔴 OPEN GAP",
        "CLOSED":       "🟢 CLOSED (Compliant)",
        "NOT ELIGIBLE": "⚪ NOT ELIGIBLE",
        "EXCLUDED":     "🟡 EXCLUDED",
    }
    print(f"\n  Member     : {mid} — {name}")
    print(f"  Age        : {age}  |  Gender: {gender}  |  DOB: {dob}")
    print(f"  Enrolled   : {'Yes' if enrolled else 'No'}")
    print(f"\n  GAP STATUS : {status_icons.get(gap_status, gap_status)}")
    print(f"  REASON     : {gap_reason}")
    print(f"\n  MATCHED PERSONA : {persona_id} — {persona_name}")
    print(f"  MATCH SCORE     : {score}")
    print(f"  TOP-3 MATCHES   : {top3}")

    if gap_status == "OPEN":
        print(f"\n  📌 RECOMMENDED ACTIONS:")
        actions = persona_out.get("recommendedActions", [])
        if isinstance(actions, list):
            for a in actions:
                print(f"     → {str(a).strip()}")
        print(f"\n  📞 OUTREACH CHANNEL : {persona_out.get('outreachChannel', 'N/A — no persona output')}")
        print(f"  ⏱  FOLLOW-UP DAYS   : {persona_out.get('followUpDays', 'N/A')}")
        print(f"  🚨 PRIORITY         : {persona_out.get('priorityLevel', 'N/A — persona output missing')}")
        print(f"  ⬆️  ESCALATION PATH  : {persona_out.get('escalationPath', 'N/A')}")

    # ── Save to Neo4j? ──
    print("\n" + "-" * 62)
    save = ask("Save this member to Neo4j graph?", default="yes", choices=["yes", "no"])
    if save == "yes":
        save_to_graph(member, gap_status, gap_reason, persona_id, score)
        print(f"  ✅ Saved to Neo4j — Member: {mid} | Gap: {gap_status}")
    else:
        print("  ℹ  Not saved — check only.")

    # Note: driver.close() removed — only close in __main__ block to avoid
    # breaking chained pipeline calls
    print("\n" + "=" * 62)
    print("  Done! Re-run the script to check another member.")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    run_check()
