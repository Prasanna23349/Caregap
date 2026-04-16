"""
BCS-E Care Gap API — Guideline-Accurate Version

Supports:
  - 3 Gender Criteria fields (admin_gender, birth_sex, clinical_use_gender)
  - CPT modifier support (50, LT, RT) for unilateral mastectomy
  - Exclusion priority hierarchy
  - Date-sensitive exclusions (hospice/deceased = measurement year only)
  - Unilateral mastectomy side/date logic (14-day rule)
  - Enrollment continuity check
  - Persona matching against 51 realistic personas
"""

from flask import Flask, request, jsonify
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os
from datetime import date

load_dotenv()

app = Flask(__name__)

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)
DB = os.getenv("NEO4J_DATABASE")

MEASUREMENT_YEAR = int(os.getenv("MEASUREMENT_YEAR", date.today().year))
LOOKBACK_START   = date(MEASUREMENT_YEAR - 2, 10, 1)
MEASUREMENT_END  = date(MEASUREMENT_YEAR, 12, 31)
MY_START         = date(MEASUREMENT_YEAR, 1, 1)
MY_END           = date(MEASUREMENT_YEAR, 12, 31)

if not os.getenv("MEASUREMENT_YEAR"):
    print(f"[WARNING] MEASUREMENT_YEAR not set in .env — defaulting to {MEASUREMENT_YEAR}. Set it explicitly for HEDIS audit accuracy.")
else:
    print(f"[INFO] Measurement year: {MEASUREMENT_YEAR} | Lookback: {LOOKBACK_START} to {MEASUREMENT_END}")

BCS_COMPLIANCE_CPT   = {"77061", "77062", "77063", "77065", "77066", "77067"}
UNILATERAL_MAST_CPT  = {"19180", "19200", "19220", "19240", "19303", "19304", "19305", "19306", "19307"}
GENDER_AFFIRMING_CPT = {"19318"}
GENDER_DYSPHORIA_ICD = {"F64.1", "F64.2", "F64.8", "F64.9", "Z87.890"}
BILATERAL_MAST_ICD   = {"Z90.13"}
BILATERAL_MAST_PCS   = {"0HTV0ZZ"}
UNILATERAL_MAST_ICD  = {"Z90.12", "Z90.11"}
UNILATERAL_MAST_PCS  = {"0HTU0ZZ", "0HTT0ZZ"}

EXCLUSION_PRIORITY = [
    "deceased", "hospice_or_palliative", "bilateral_mastectomy",
    "unilateral_mastectomy_both_sides", "gender_affirming_chest_surgery",
    "frailty_advanced_illness", "institutional_snp_or_ltc_66plus",
]


def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def resolve_gender_criteria(admin_gender=None, birth_sex=None, clinical_use_gender=None):
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


def check_exclusions(claims, age):
    found = set()
    uni_sides = set()
    uni_dates = []
    has_gender_dysphoria = False

    # First pass: collect gender dysphoria flag
    for c in claims:
        icd = (c.get("icd_code") or "").strip()
        if icd in GENDER_DYSPHORIA_ICD:
            has_gender_dysphoria = True

    for c in claims:
        cpt = (c.get("cpt_code") or "").strip()
        icd = (c.get("icd_code") or "").strip()
        modifier = (c.get("modifier") or "").strip().upper()
        svc = _parse_date(c.get("service_date"))

        # Bilateral mastectomy (any time through Dec 31 MY)
        if icd in BILATERAL_MAST_ICD or icd in BILATERAL_MAST_PCS:
            if not svc or svc <= MY_END:
                found.add("bilateral_mastectomy")

        # Unilateral mastectomy CPT — side/date logic
        if cpt in UNILATERAL_MAST_CPT:
            if modifier == "50":
                found.add("unilateral_mastectomy_both_sides")
            elif modifier in ("LT", "RT"):
                uni_sides.add(modifier)
            else:
                if svc:
                    uni_dates.append(svc)

        # Unilateral ICD
        if icd == "Z90.11":
            uni_sides.add("RT")
        elif icd == "Z90.12":
            uni_sides.add("LT")

        # Unilateral PCS
        if icd == "0HTU0ZZ":
            uni_sides.add("LT")
        elif icd == "0HTT0ZZ":
            uni_sides.add("RT")

        # Gender-affirming surgery (CPT 19318 + gender dysphoria ICD)
        if cpt in GENDER_AFFIRMING_CPT and has_gender_dysphoria:
            if not svc or svc <= MY_END:
                found.add("gender_affirming_chest_surgery")

        # Hospice/palliative (measurement year only)
        if c.get("hospice") or c.get("palliative"):
            if svc and MY_START <= svc <= MY_END:
                found.add("hospice_or_palliative")

        # Deceased (measurement year only)
        if c.get("deceased"):
            if svc and MY_START <= svc <= MY_END:
                found.add("deceased")

        # Frailty + advanced illness (66+ only)
        if age >= 66 and c.get("frailty_advanced_illness"):
            found.add("frailty_advanced_illness")

        # Institutional SNP/LTC (66+ only)
        if age >= 66 and (c.get("institutional_snp") or c.get("ltc")):
            found.add("institutional_snp_or_ltc_66plus")

    # Unilateral both sides
    if "LT" in uni_sides and "RT" in uni_sides:
        found.add("unilateral_mastectomy_both_sides")

    # Two unilateral without side, 14+ days apart
    if len(uni_dates) >= 2:
        uni_dates.sort()
        if (uni_dates[-1] - uni_dates[0]).days >= 14:
            found.add("unilateral_mastectomy_both_sides")

    for excl in EXCLUSION_PRIORITY:
        if excl in found:
            return excl
    return None


def check_mammogram(claims):
    for c in claims:
        cpt = (c.get("cpt_code") or "").strip()
        svc = _parse_date(c.get("service_date"))
        if cpt in BCS_COMPLIANCE_CPT and svc:
            if LOOKBACK_START <= svc <= MEASUREMENT_END:
                return True, {"cpt_code": cpt, "service_date": str(svc)}
    return False, None


def check_enrollment(enrollment_start, enrollment_end):
    start = _parse_date(enrollment_start)
    end = _parse_date(enrollment_end)
    if not start or not end:
        return False
    return start <= LOOKBACK_START and end >= MEASUREMENT_END


def build_response(member, status, reason=None, compliant_claim=None, claims=None,
                   gc_code=None, gc_label=None, exclusion_reason=None, persona_id=None):
    mammogram_cpts = [
        {"cpt_code": c.get("cpt_code"), "service_date": str(c.get("service_date", ""))}
        for c in (claims or [])
        if (c.get("cpt_code") or "").strip() in BCS_COMPLIANCE_CPT
    ]
    return {
        "member_id":          member.get("member_id"),
        "admin_gender":       member.get("admin_gender"),
        "birth_sex":          member.get("birth_sex"),
        "clinical_use_gender": member.get("clinical_use_gender"),
        "age":                member.get("age"),
        "measure":            "BCS-E",
        "measurement_year":   MEASUREMENT_YEAR,
        "gender_criteria":    {"code": gc_code, "label": gc_label} if gc_code else None,
        "care_gap_status":    status,
        "reason":             reason,
        "exclusion_reason":   exclusion_reason,
        "persona_id":         persona_id,
        "compliant_mammogram": compliant_claim,
        "mammogram_claims_found": mammogram_cpts,
        "recommendation": (
            "Schedule a mammogram screening — no qualifying mammogram found in the lookback window."
            if status == "OPEN_GAP" else None
        ),
        "lookback_window": {"start": str(LOOKBACK_START), "end": str(MEASUREMENT_END)},
        "total_claims": len(claims) if claims else 0,
    }


def _match_persona_db(gc_code, age_band, status, exclusion_reason, mammogram_found):
    with driver.session(database=DB) as session:
        if status == "EXCLUDED":
            result = session.run("""
                MATCH (p:Persona {
                    measure: 'BCS-E', care_gap_status: 'EXCLUDED',
                    gender_criteria_code: $gc, age_band_code: $ab,
                    exclusion_reason: $excl
                }) RETURN p.persona_id AS pid LIMIT 1
            """, gc=gc_code, ab=age_band, excl=exclusion_reason)
        elif status in ("COMPLIANT", "OPEN_GAP"):
            result = session.run("""
                MATCH (p:Persona {
                    measure: 'BCS-E', care_gap_status: $status,
                    gender_criteria_code: $gc, age_band_code: $ab,
                    mammogram_found: $mammo
                }) RETURN p.persona_id AS pid LIMIT 1
            """, status=status, gc=gc_code, ab=age_band, mammo=mammogram_found)
        else:
            return None
        row = result.single()
        return row["pid"] if row else None


def _persist_member(member, claims, status, reason, gc_code, persona_id):
    with driver.session(database=DB) as session:
        session.run("""
            MERGE (m:Member {member_id: $mid})
            SET m.admin_gender = $ag, m.birth_sex = $bs,
                m.clinical_use_gender = $cu, m.age_years = $age
        """, mid=member["member_id"], ag=member.get("admin_gender"),
             bs=member.get("birth_sex"), cu=member.get("clinical_use_gender"),
             age=member.get("age"))

        for i, c in enumerate(claims):
            session.run("""
                MERGE (cl:Claim {claim_id: $cid})
                SET cl.cpt_code = $cpt, cl.icd_code = $icd,
                    cl.modifier = $mod, cl.service_date = $svc, cl.status = $st
                WITH cl MATCH (m:Member {member_id: $mid})
                MERGE (m)-[:HAS_CLAIM]->(cl)
            """, cid=f"{member['member_id']}_claim_{i}",
                 cpt=c.get("cpt_code", ""), icd=c.get("icd_code", ""),
                 mod=c.get("modifier", ""), svc=c.get("service_date", ""),
                 st=c.get("status", ""), mid=member["member_id"])

        gap_id = f"CG_{member['member_id']}_BCS"
        session.run("""
            MATCH (m:Member {member_id: $mid})
            MATCH (meas:Measure {measure_id: 'BCS-E'})
            MERGE (cg:CareGap {gap_id: $gid})
            SET cg.status = $status, cg.reason = $reason, cg.measure = 'BCS-E'
            MERGE (m)-[:HAS_CARE_GAP]->(cg)
            MERGE (cg)-[:FOR_MEASURE]->(meas)
        """, mid=member["member_id"], gid=gap_id, status=status, reason=reason or "")

        if persona_id:
            session.run("""
                MATCH (m:Member {member_id: $mid})
                MATCH (p:Persona {persona_id: $pid})
                MERGE (m)-[:MATCHES_PERSONA]->(p)
            """, mid=member["member_id"], pid=persona_id)


# ── Predict endpoint (external member data) ──────────────────────────────────

@app.route("/care-gap/bcs/predict", methods=["POST"])
def predict_care_gap():
    data = request.get_json()
    member_id = data.get("member_id")
    if not member_id:
        return jsonify({"error": "member_id is required"}), 400

    # Accept 3 gender fields (backward-compatible: falls back to "gender" field)
    admin_gender       = data.get("admin_gender") or data.get("gender", "")
    birth_sex          = data.get("birth_sex", "")
    clinical_use_gender = data.get("clinical_use_gender", "")
    age                = data.get("age")
    claims             = data.get("claims") or []
    enrollment_start   = data.get("enrollment_start")
    enrollment_end     = data.get("enrollment_end")
    save               = data.get("save", False)

    if age is None:
        return jsonify({"error": "age is required"}), 400

    member = {
        "member_id": member_id,
        "admin_gender": admin_gender,
        "birth_sex": birth_sex,
        "clinical_use_gender": clinical_use_gender,
        "age": age,
    }

    # Step 1: Gender criteria waterfall
    gc_code, gc_label = resolve_gender_criteria(admin_gender, birth_sex, clinical_use_gender)
    if not gc_code:
        return jsonify(build_response(member, "NOT_ELIGIBLE", reason="Gender not Female (none of GC1/GC2/GC3 met)"))

    # Step 2: Age check
    if not (42 <= age <= 74):
        return jsonify(build_response(member, "NOT_ELIGIBLE", reason=f"Age {age} outside 42-74",
                                       gc_code=gc_code, gc_label=gc_label))

    # Step 3: Enrollment continuity
    if enrollment_start and enrollment_end:
        if not check_enrollment(enrollment_start, enrollment_end):
            return jsonify(build_response(member, "NOT_ELIGIBLE",
                                           reason="Continuous enrollment not met",
                                           gc_code=gc_code, gc_label=gc_label))

    age_band = "AB1" if age <= 65 else "AB2"

    # Step 4: Exclusion check (priority-based, date/side-aware)
    exclusion_reason = check_exclusions(claims, age)
    if exclusion_reason:
        persona_id = _match_persona_db(gc_code, age_band, "EXCLUDED", exclusion_reason, None)
        result = build_response(member, "EXCLUDED", reason=exclusion_reason, claims=claims,
                                gc_code=gc_code, gc_label=gc_label,
                                exclusion_reason=exclusion_reason, persona_id=persona_id)
        if save:
            _persist_member(member, claims, "EXCLUDED", exclusion_reason, gc_code, persona_id)
        return jsonify({**result, "saved": save})

    # Step 5: Mammogram compliance
    has_mammogram, compliant_claim = check_mammogram(claims)
    status = "COMPLIANT" if has_mammogram else "OPEN_GAP"
    reason = None if has_mammogram else (
        f"No mammography CPT (77061-77067) found between {LOOKBACK_START} and {MEASUREMENT_END}"
    )
    persona_id = _match_persona_db(gc_code, age_band, status, None, has_mammogram)
    result = build_response(member, status, reason=reason, compliant_claim=compliant_claim,
                            claims=claims, gc_code=gc_code, gc_label=gc_label,
                            persona_id=persona_id)
    if save:
        _persist_member(member, claims, status, reason, gc_code, persona_id)
    return jsonify({**result, "saved": save})


# ── Check endpoint (member already in graph) ─────────────────────────────────

@app.route("/care-gap/bcs", methods=["POST"])
def check_care_gap():
    data = request.get_json()
    member_id = data.get("member_id")
    if not member_id:
        return jsonify({"error": "member_id is required"}), 400

    with driver.session(database=DB) as session:
        row = session.run("""
            MATCH (m:Member {member_id: $mid})
            RETURN m.member_id AS member_id,
                   m.gender AS admin_gender,
                   m.birth_sex AS birth_sex,
                   m.clinical_use_gender AS clinical_use_gender,
                   m.age_years AS age,
                   m.enrollment_start AS enrollment_start,
                   m.enrollment_end AS enrollment_end
        """, mid=member_id).single()

        if not row:
            return jsonify({"error": f"Member '{member_id}' not found"}), 404

        member = dict(row)

        gc_code, gc_label = resolve_gender_criteria(
            member.get("admin_gender"), member.get("birth_sex"), member.get("clinical_use_gender"))
        if not gc_code:
            return jsonify(build_response(member, "NOT_ELIGIBLE", reason="Gender not Female"))

        age = member.get("age") or 0
        if not (42 <= age <= 74):
            return jsonify(build_response(member, "NOT_ELIGIBLE", reason=f"Age {age} outside 42-74",
                                           gc_code=gc_code, gc_label=gc_label))

        if not check_enrollment(member.get("enrollment_start"), member.get("enrollment_end")):
            return jsonify(build_response(member, "NOT_ELIGIBLE", reason="Enrollment gap",
                                           gc_code=gc_code, gc_label=gc_label))

        claims = [dict(c) for c in session.run("""
            MATCH (m:Member {member_id: $mid})-[:HAS_CLAIM]->(c:Claim)
            RETURN c.cpt_code AS cpt_code, c.icd_code AS icd_code,
                   c.modifier AS modifier, c.service_date AS service_date,
                   c.status AS status
        """, mid=member_id)]

        age_band = "AB1" if age <= 65 else "AB2"

        exclusion_reason = check_exclusions(claims, age)
        if exclusion_reason:
            persona_id = _match_persona_db(gc_code, age_band, "EXCLUDED", exclusion_reason, None)
            return jsonify(build_response(member, "EXCLUDED", reason=exclusion_reason, claims=claims,
                                           gc_code=gc_code, gc_label=gc_label,
                                           exclusion_reason=exclusion_reason, persona_id=persona_id))

        has_mammogram, compliant_claim = check_mammogram(claims)
        status = "COMPLIANT" if has_mammogram else "OPEN_GAP"
        reason = None if has_mammogram else (
            f"No mammography CPT (77061-77067) found between {LOOKBACK_START} and {MEASUREMENT_END}"
        )
        persona_id = _match_persona_db(gc_code, age_band, status, None, has_mammogram)
        return jsonify(build_response(member, status, reason=reason, compliant_claim=compliant_claim,
                                       claims=claims, gc_code=gc_code, gc_label=gc_label,
                                       persona_id=persona_id))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
