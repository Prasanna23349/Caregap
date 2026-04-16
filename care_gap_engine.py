"""
BCS-E Care Gap Engine — Guideline-Accurate Version

Fixes over previous version:
  1. 3 Gender Criteria priority waterfall (GC1 → GC2 → GC3)
  2. Exclusion priority hierarchy (deceased > hospice > bilateral > ...)
  3. Unilateral mastectomy side/date logic (single side ≠ exclusion)
  4. Date-sensitive exclusions (hospice/palliative/deceased = measurement year only)
  5. Enrollment continuity check
  6. Proper persona matching against 51 realistic personas
"""

import os
from datetime import date
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI      = os.getenv("NEO4J_URI")
USER     = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DB       = os.getenv("NEO4J_DATABASE")

MEASUREMENT_YEAR = 2026
LOOKBACK_START   = date(MEASUREMENT_YEAR - 2, 10, 1)
MEASUREMENT_END  = date(MEASUREMENT_YEAR, 12, 31)
MY_START         = date(MEASUREMENT_YEAR, 1, 1)
MY_END           = date(MEASUREMENT_YEAR, 12, 31)

BCS_COMPLIANCE_CPT = {"77062", "77061", "77066", "77065", "77063", "77067"}

# Unilateral mastectomy CPTs (need side/date logic)
UNILATERAL_MAST_CPT = {"19180", "19200", "19220", "19240", "19303", "19304", "19305", "19306", "19307"}

# Gender-affirming surgery CPT (needs gender dysphoria ICD co-occurrence)
GENDER_AFFIRMING_CPT = {"19318"}

GENDER_DYSPHORIA_ICD = {"F64.1", "F64.2", "F64.8", "F64.9", "Z87.890"}

# Bilateral mastectomy codes
BILATERAL_MAST_PCS = {"0HTV0ZZ"}
BILATERAL_MAST_ICD = {"Z90.13"}

# Unilateral mastectomy ICD/PCS
UNILATERAL_MAST_ICD = {"Z90.12", "Z90.11"}  # Z90.11=right absent, Z90.12=left absent
UNILATERAL_MAST_PCS = {"0HTU0ZZ", "0HTT0ZZ"}  # left, right resection

# Exclusion priority (highest first)
EXCLUSION_PRIORITY = [
    "deceased",
    "hospice_or_palliative",
    "bilateral_mastectomy",
    "unilateral_mastectomy_both_sides",
    "gender_affirming_chest_surgery",
    "frailty_advanced_illness",
    "institutional_snp_or_ltc_66plus",
]


def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


# ── Gender Criteria Priority Waterfall ────────────────────────────────────────

def resolve_gender_criteria(admin_gender=None, birth_sex=None, clinical_use_gender=None):
    """
    Returns (gc_code, gc_label) using priority: GC1 → GC2 → GC3.
    GC1/GC2: any time in history. GC3: measurement period only.
    """
    ag = (admin_gender or "").strip().upper()
    bs = (birth_sex or "").strip().upper()
    cu = (clinical_use_gender or "").strip().upper()

    if ag in ("F", "FEMALE"):
        return "GC1", "AdministrativeGender=Female"
    if bs in ("F", "FEMALE"):
        return "GC2", "SexAssignedAtBirth=Female"
    if cu in ("F", "FEMALE", "FEMALE-TYPICAL"):
        return "GC3", "SexParamClinicalUse=Female"
    return None, None


# ── Exclusion Detection (with priority, dates, side logic) ────────────────────

def check_exclusions(claims, age):
    """
    Returns the highest-priority exclusion reason, or None.
    Applies HEDIS date/age/side rules.
    """
    found_exclusions = set()

    # Track unilateral mastectomy sides and dates for side logic
    uni_sides = set()       # "LT", "RT", "50"
    uni_dates = []          # dates of unilateral claims without side specified
    has_gender_dysphoria = False

    for c in claims:
        cpt = (c.get("cpt_code") or "").strip()
        icd = (c.get("icd_code") or "").strip()
        modifier = (c.get("modifier") or "").strip().upper()
        svc = _parse_date(c.get("service_date"))

        # ── Bilateral mastectomy (any time through Dec 31 MY) ────────────
        if icd in BILATERAL_MAST_ICD or icd in BILATERAL_MAST_PCS:
            if not svc or svc <= MY_END:
                found_exclusions.add("bilateral_mastectomy")

        # ── Unilateral mastectomy CPT — need side/date logic ─────────────
        if cpt in UNILATERAL_MAST_CPT:
            if modifier == "50":
                # Modifier 50 = bilateral procedure
                found_exclusions.add("unilateral_mastectomy_both_sides")
            elif modifier in ("LT", "RT"):
                uni_sides.add(modifier)
            else:
                # No side specified — track date for 14-day rule
                if svc:
                    uni_dates.append(svc)

        # Unilateral ICD codes (Z90.11=right absent, Z90.12=left absent)
        if icd == "Z90.11":
            uni_sides.add("RT")
        elif icd == "Z90.12":
            uni_sides.add("LT")

        # Unilateral PCS codes
        if icd == "0HTU0ZZ":  # left breast resection
            uni_sides.add("LT")
        elif icd == "0HTT0ZZ":  # right breast resection
            uni_sides.add("RT")

        # ── Gender-affirming chest surgery (any time through Dec 31 MY) ──
        if icd in GENDER_DYSPHORIA_ICD:
            has_gender_dysphoria = True
        if cpt in GENDER_AFFIRMING_CPT:
            if has_gender_dysphoria and (not svc or svc <= MY_END):
                found_exclusions.add("gender_affirming_chest_surgery")

        # ── Hospice / Palliative (measurement year only) ─────────────────
        # These would be flagged via specific codes in real data;
        # here we check if claim has hospice/palliative indicator
        if (c.get("hospice") or c.get("palliative")):
            if svc and MY_START <= svc <= MY_END:
                found_exclusions.add("hospice_or_palliative")

        # ── Deceased (measurement year only) ─────────────────────────────
        if c.get("deceased"):
            if svc and MY_START <= svc <= MY_END:
                found_exclusions.add("deceased")

    # ── Unilateral side logic: both sides = exclusion ────────────────────
    if "LT" in uni_sides and "RT" in uni_sides:
        found_exclusions.add("unilateral_mastectomy_both_sides")

    # Two unilateral without side specified, 14+ days apart = exclusion
    if len(uni_dates) >= 2:
        uni_dates.sort()
        if (uni_dates[-1] - uni_dates[0]).days >= 14:
            found_exclusions.add("unilateral_mastectomy_both_sides")

    # ── Gender-affirming: also check if ICD appeared in any claim ────────
    # (CPT 19318 might be in a different claim than the ICD)
    if has_gender_dysphoria:
        for c in claims:
            cpt = (c.get("cpt_code") or "").strip()
            svc = _parse_date(c.get("service_date"))
            if cpt in GENDER_AFFIRMING_CPT and (not svc or svc <= MY_END):
                found_exclusions.add("gender_affirming_chest_surgery")

    # ── Frailty + advanced illness (66+ only) ────────────────────────────
    if age >= 66 and (c.get("frailty_advanced_illness") for c in claims):
        for c in claims:
            if c.get("frailty_advanced_illness"):
                found_exclusions.add("frailty_advanced_illness")

    # ── Institutional SNP/LTC (66+ only) ─────────────────────────────────
    if age >= 66:
        for c in claims:
            if c.get("institutional_snp") or c.get("ltc"):
                found_exclusions.add("institutional_snp_or_ltc_66plus")

    # Return highest-priority exclusion
    for excl in EXCLUSION_PRIORITY:
        if excl in found_exclusions:
            return excl
    return None


# ── Mammogram Compliance Check ────────────────────────────────────────────────

def check_mammogram_compliance(claims):
    for c in claims:
        cpt = (c.get("cpt_code") or "").strip()
        svc = _parse_date(c.get("service_date"))
        if cpt in BCS_COMPLIANCE_CPT and svc:
            if LOOKBACK_START <= svc <= MEASUREMENT_END:
                return True, {"cpt_code": cpt, "service_date": str(svc)}
    return False, None


# ── Enrollment Continuity Check ───────────────────────────────────────────────

def check_enrollment_continuity(enrollment_start, enrollment_end):
    """Verify continuous enrollment from Oct 1 two years prior through Dec 31 MY."""
    start = _parse_date(enrollment_start)
    end = _parse_date(enrollment_end)
    if not start or not end:
        return False
    return start <= LOOKBACK_START and end >= MEASUREMENT_END


# ── Persona Matching ─────────────────────────────────────────────────────────

def match_persona(session, gc_code, age_band_code, status, exclusion_reason, mammogram_found):
    """Match member to one of the 51 realistic personas."""
    if status == "NOT_ELIGIBLE":
        # Match by not_eligible_reason — but we don't know which one here,
        # so we skip persona matching for NOT_ELIGIBLE
        return None

    if status == "EXCLUDED":
        result = session.run("""
            MATCH (p:Persona {
                measure: 'BCS-E',
                care_gap_status: 'EXCLUDED',
                gender_criteria_code: $gc,
                age_band_code: $ab,
                exclusion_reason: $excl
            })
            RETURN p.persona_id AS persona_id LIMIT 1
        """, gc=gc_code, ab=age_band_code, excl=exclusion_reason)
    else:
        result = session.run("""
            MATCH (p:Persona {
                measure: 'BCS-E',
                care_gap_status: $status,
                gender_criteria_code: $gc,
                age_band_code: $ab,
                mammogram_found: $mammo
            })
            RETURN p.persona_id AS persona_id LIMIT 1
        """, status=status, gc=gc_code, ab=age_band_code, mammo=mammogram_found)

    row = result.single()
    return row["persona_id"] if row else None


# ── Write CareGap + Relationships ────────────────────────────────────────────

def write_care_gap(session, member_id, persona_id, gap_status, exclusion_reason, has_mammogram):
    gap_id = f"GAP-BCS-{member_id}"
    session.run("""
        MERGE (g:CareGap {gap_id: $gap_id})
        SET g.member_id        = $member_id,
            g.measure          = 'BCS-E',
            g.status           = $status,
            g.exclusion_reason = $exclusion_reason,
            g.has_mammogram    = $has_mammogram,
            g.created_on       = $today
        WITH g
        MATCH (m:Member {member_id: $member_id})
        MERGE (m)-[:HAS_CARE_GAP]->(g)
        WITH g
        MATCH (meas:Measure {measure_id: 'BCS-E'})
        MERGE (g)-[:FOR_MEASURE]->(meas)
    """, gap_id=gap_id, member_id=member_id,
         status=gap_status, exclusion_reason=exclusion_reason,
         has_mammogram=has_mammogram, today=str(date.today()))

    if persona_id:
        session.run("""
            MATCH (m:Member {member_id: $member_id})
            MATCH (p:Persona {persona_id: $persona_id})
            MERGE (m)-[:MATCHES_PERSONA]->(p)
        """, member_id=member_id, persona_id=persona_id)


# ── Neo4j Data Fetchers ─────────────────────────────────────────────────────

def get_all_members(session):
    result = session.run("""
        MATCH (m:Member)
        RETURN m.member_id AS member_id,
               m.gender AS gender,
               m.age_years AS age_years,
               m.enrollment_start AS enrollment_start,
               m.enrollment_end AS enrollment_end
    """)
    return [dict(r) for r in result]


def get_member_claims(session, member_id):
    result = session.run("""
        MATCH (m:Member {member_id: $member_id})-[:HAS_CLAIM]->(c:Claim)
        RETURN c.cpt_code AS cpt_code,
               c.icd_code AS icd_code,
               c.modifier AS modifier,
               c.service_date AS service_date,
               c.status AS status
    """, member_id=member_id)
    return [dict(r) for r in result]


# ── Main Engine ──────────────────────────────────────────────────────────────

def run_care_gap_engine(driver):
    with driver.session(database=DB) as session:
        members = get_all_members(session)
        results = []

        for member in members:
            mid    = member["member_id"]
            age    = member.get("age_years") or 0
            claims = get_member_claims(session, mid)

            # Step 1: Gender criteria (priority waterfall)
            # Current data has single gender field — map to GC1
            # In full implementation, would check admin_gender, birth_sex, clinical_use separately
            admin_gender = member.get("gender") or ""
            gc_code, gc_label = resolve_gender_criteria(
                admin_gender=admin_gender,
                birth_sex=member.get("birth_sex"),
                clinical_use_gender=member.get("clinical_use_gender"),
            )
            if not gc_code:
                results.append({"member_id": mid, "status": "NOT_ELIGIBLE", "reason": "Gender not Female"})
                continue

            # Step 2: Age eligibility
            if not (42 <= age <= 74):
                results.append({"member_id": mid, "status": "NOT_ELIGIBLE", "reason": f"Age {age} outside 42-74"})
                continue

            # Step 3: Enrollment continuity
            if not check_enrollment_continuity(member.get("enrollment_start"), member.get("enrollment_end")):
                results.append({"member_id": mid, "status": "NOT_ELIGIBLE", "reason": "Enrollment gap"})
                continue

            age_band_code = "AB1" if age <= 65 else "AB2"

            # Step 4: Exclusion check (priority-based)
            exclusion_reason = check_exclusions(claims, age)

            # Step 5: Mammogram compliance
            has_mammogram, compliant_claim = check_mammogram_compliance(claims)

            # Step 6: Determine status
            if exclusion_reason:
                gap_status = "EXCLUDED"
            elif has_mammogram:
                gap_status = "COMPLIANT"
            else:
                gap_status = "OPEN_GAP"

            # Step 7: Match persona
            persona_id = match_persona(session, gc_code, age_band_code, gap_status, exclusion_reason, has_mammogram)

            # Step 8: Write to graph
            write_care_gap(session, mid, persona_id, gap_status, exclusion_reason, has_mammogram)

            results.append({
                "member_id":        mid,
                "age":              age,
                "gender":           admin_gender,
                "gc_code":          gc_code,
                "persona_id":       persona_id,
                "exclusion_reason": exclusion_reason,
                "has_mammogram":    has_mammogram,
                "status":           gap_status,
            })

        return results


def main():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    try:
        driver.verify_connectivity()
        print("Neo4j connected.\n")
        results = run_care_gap_engine(driver)

        print(f"{'MemberID':<10} {'Age':<5} {'GC':<5} {'PersonaID':<12} {'Status':<14} {'Exclusion'}")
        print("-" * 75)
        for r in results:
            print(f"{r['member_id']:<10} {str(r.get('age','')):<5} {r.get('gc_code',''):<5} "
                  f"{str(r.get('persona_id','N/A')):<12} {r['status']:<14} "
                  f"{r.get('exclusion_reason') or '-'}")

        print(f"\nTotal: {len(results)} | "
              f"OPEN_GAP: {sum(1 for r in results if r['status']=='OPEN_GAP')} | "
              f"COMPLIANT: {sum(1 for r in results if r['status']=='COMPLIANT')} | "
              f"EXCLUDED: {sum(1 for r in results if r['status']=='EXCLUDED')} | "
              f"NOT_ELIGIBLE: {sum(1 for r in results if r['status']=='NOT_ELIGIBLE')}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
