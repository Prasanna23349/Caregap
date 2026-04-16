"""
BCS-E Complete Knowledge Graph Builder
Loads 51 realistic Persona nodes (replaces old 3,072 brute-force model), then:
  1. Measure node
  2. ComplianceCode nodes
  3. ExclusionCode nodes
  4. 51 Realistic Persona nodes (GC priority waterfall, age-restricted exclusions)
  5. BenefitPlan node
  6. Provider nodes
  7. Member nodes
  8. Enrollment nodes + relationships
  9. Claim nodes + relationships
 10. CareGap nodes (guideline-accurate engine: GC waterfall, exclusion priority, side/date logic)
 11. Outreach nodes + relationships
"""

import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from datetime import date
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
URI  = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PWD  = os.getenv("NEO4J_PASSWORD")
DB   = os.getenv("NEO4J_DATABASE")

EXCEL = os.path.join(os.path.dirname(__file__),"Scenario 2_care_gap_multi_measure_dataset.xlsx")

MEASUREMENT_YEAR  = int(os.getenv("MEASUREMENT_YEAR", date.today().year))
LOOKBACK_START    = date(MEASUREMENT_YEAR - 2, 10, 1)
MEASUREMENT_END   = date(MEASUREMENT_YEAR, 12, 31)

# ── Code sets ────────────────────────────────────────────────────────────────
MAMMOGRAPHY_CPT = ["77062","77061","77066","77065","77063","77067"]
BCS_CPT_SET   = set(MAMMOGRAPHY_CPT)
EXCL_CPT_SET  = {"19180","19200","19220","19240","19303","19304","19305","19306","19307","19318"}
EXCL_ICD_SET  = {"Z90.13","Z90.12","Z90.11","F64.1","F64.2","F64.8","F64.9","Z87.890"}
EXCL_PCS_SET  = {"0HTV0ZZ","0HTU0ZZ","0HTT0ZZ"}

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

# ── Persona dimensions ────────────────────────────────────────────────────────
GENDER_CRITERIA = [
    {"code": "GC1", "label": "AdministrativeGender=Female",
     "description": "Administrative Gender of Female at any time in member history"},
    {"code": "GC2", "label": "SexAssignedAtBirth=Female",
     "description": "Sex Assigned at Birth (LOINC 76689-9) of Female (LOINC LA3-6)"},
    {"code": "GC3", "label": "SexParamClinicalUse=Female",
     "description": "Sex Parameter for Clinical Use of Female (female-typical) during measurement period"},
]
AGE_BANDS = [
    {"code": "AB1", "label": "Age 42-65", "min_age": 42, "max_age": 65},
    {"code": "AB2", "label": "Age 66-74", "min_age": 66, "max_age": 74},
]
# Exclusions per age band (frailty + SNP/LTC apply only to 66+)
EXCLUSIONS_AB1 = [
    "bilateral_mastectomy", "unilateral_mastectomy_both_sides",
    "gender_affirming_chest_surgery", "hospice_or_palliative", "deceased",
]
EXCLUSIONS_AB2 = [
    "bilateral_mastectomy", "unilateral_mastectomy_both_sides",
    "gender_affirming_chest_surgery", "hospice_or_palliative", "deceased",
    "frailty_advanced_illness", "institutional_snp_or_ltc_66plus",
]

EXCLUSION_PRIORITY = [
    "deceased", "hospice_or_palliative", "bilateral_mastectomy",
    "unilateral_mastectomy_both_sides", "gender_affirming_chest_surgery",
    "frailty_advanced_illness", "institutional_snp_or_ltc_66plus",
]

UNILATERAL_MAST_CPT = {"19180","19200","19220","19240","19303","19304","19305","19306","19307"}
GENDER_AFFIRMING_CPT = {"19318"}
GENDER_DYSPHORIA_ICD = {"F64.1","F64.2","F64.8","F64.9","Z87.890"}
BILATERAL_MAST_ICD = {"Z90.13"}
BILATERAL_MAST_PCS = {"0HTV0ZZ"}
UNILATERAL_MAST_ICD = {"Z90.12","Z90.11"}
UNILATERAL_MAST_PCS = {"0HTU0ZZ","0HTT0ZZ"}
MY_START = date(MEASUREMENT_YEAR, 1, 1)
MY_END   = date(MEASUREMENT_YEAR, 12, 31)


# ── Helpers ───────────────────────────────────────────────────────────────────
def to_str(val):
    if pd.isna(val):
        return None
    return str(val).strip()

# ── Step 1: Build 51 realistic personas ──────────────────────────────────────
def build_personas():
    personas, idx = [], 1

    # 3 NOT_ELIGIBLE
    for reason, desc in [
        ("gender_not_female", "None of GC1/GC2/GC3 criteria met"),
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
                    "description": f"{status}: {gc['label']} | {ab['label']} | Mammogram={'Yes' if mammo else 'No'}",
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


# ── Step 2: Guideline-accurate member evaluation ─────────────────────────────
def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def resolve_gender_criteria(gender):
    """Map single gender field to GC code (GC1 priority; extend for multi-field)."""
    g = (gender or "").strip().upper()
    if g in ("F", "FEMALE"):
        return "GC1"
    return None


def check_exclusions(claims, age):
    found = set()
    uni_sides, uni_dates = set(), []
    has_gender_dysphoria = False

    for c in claims:
        icd = (c.get("icd_code") or "").strip()
        if icd in GENDER_DYSPHORIA_ICD:
            has_gender_dysphoria = True

    for c in claims:
        cpt      = (c.get("cpt_code") or "").strip()
        icd      = (c.get("icd_code") or "").strip()
        modifier = (c.get("modifier") or "").strip().upper()
        svc      = _parse_date(c.get("service_date"))

        if icd in BILATERAL_MAST_ICD or icd in BILATERAL_MAST_PCS:
            if not svc or svc <= MY_END:
                found.add("bilateral_mastectomy")

        if cpt in UNILATERAL_MAST_CPT:
            if modifier == "50":
                found.add("unilateral_mastectomy_both_sides")
            elif modifier in ("LT", "RT"):
                uni_sides.add(modifier)
            elif svc:
                uni_dates.append(svc)

        if icd == "Z90.11": uni_sides.add("RT")
        elif icd == "Z90.12": uni_sides.add("LT")
        if icd == "0HTT0ZZ": uni_sides.add("RT")
        elif icd == "0HTU0ZZ": uni_sides.add("LT")

        if cpt in GENDER_AFFIRMING_CPT and has_gender_dysphoria:
            if not svc or svc <= MY_END:
                found.add("gender_affirming_chest_surgery")

        if c.get("hospice") or c.get("palliative"):
            if svc and MY_START <= svc <= MY_END:
                found.add("hospice_or_palliative")

        if c.get("deceased"):
            if svc and MY_START <= svc <= MY_END:
                found.add("deceased")

        if age >= 66 and c.get("frailty_advanced_illness"):
            found.add("frailty_advanced_illness")
        if age >= 66 and (c.get("institutional_snp") or c.get("ltc")):
            found.add("institutional_snp_or_ltc_66plus")

    if "LT" in uni_sides and "RT" in uni_sides:
        found.add("unilateral_mastectomy_both_sides")
    if len(uni_dates) >= 2:
        uni_dates.sort()
        if (uni_dates[-1] - uni_dates[0]).days >= 14:
            found.add("unilateral_mastectomy_both_sides")

    for excl in EXCLUSION_PRIORITY:
        if excl in found:
            return excl
    return None


def evaluate_member(member, claims):
    gender = (member.get("gender") or "").upper()
    age    = member.get("age_years") or 0

    gc_code = resolve_gender_criteria(gender)
    if not gc_code:
        return None, "NOT_ELIGIBLE", "Gender not Female", False, None

    if not (42 <= age <= 74):
        return None, "NOT_ELIGIBLE", f"Age {age} outside 42-74", False, None

    age_band     = "AB1" if age <= 65 else "AB2"
    excl_reason  = check_exclusions(claims, age)
    mammo_found  = False

    for c in claims:
        cpt = (c.get("cpt_code") or "").strip()
        svc = _parse_date(c.get("service_date"))
        if cpt in BCS_CPT_SET and svc and LOOKBACK_START <= svc <= MEASUREMENT_END:
            mammo_found = True
            break

    if excl_reason:
        status = "EXCLUDED"
    elif mammo_found:
        status = "COMPLIANT"
    else:
        status = "OPEN_GAP"

    return age_band, status, excl_reason, mammo_found, gc_code


# ── Main loader ───────────────────────────────────────────────────────────────
def load_all(driver):
    xl = pd.ExcelFile(EXCEL)
    members_df    = pd.read_excel(xl, "Members")
    providers_df  = pd.read_excel(xl, "Providers")
    claims_df     = pd.read_excel(xl, "Claims")[
                        ["ClaimID","MemberID","ProviderID","CPTCode","ICDCode","ServiceDate","Status"]]
    enroll_df     = pd.read_excel(xl, "Enrolment Eligibility")
    benefit_df    = pd.read_excel(xl, "BenefitPlan")
    outreach_df   = pd.read_excel(xl, "CareMngnt_Outreach_Dashboard")

    with driver.session(database=DB) as s:

        # ── Constraints ──────────────────────────────────────────────────────
        for label, prop in [
            ("Measure","measure_id"), ("Persona","persona_id"),
            ("ComplianceCode","code"), ("ExclusionCode","code"),
            ("Member","member_id"), ("Provider","provider_id"),
            ("Claim","claim_id"), ("BenefitPlan","plan_id"),
            ("Enrollment","enrollment_id"), ("CareGap","gap_id"),
            ("Outreach","outreach_id"),
        ]:
            s.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")
        print("Constraints: OK")

        # ── Clear stale Persona nodes (old 48) ───────────────────────────────
        s.run("MATCH (p:Persona) DETACH DELETE p")
        print("Cleared old Persona nodes")

        # ── Measure node ─────────────────────────────────────────────────────
        s.run("""
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
        print("Measure node: OK")

        # ── ComplianceCode nodes ──────────────────────────────────────────────
        for cpt in MAMMOGRAPHY_CPT:
            s.run("""
                MERGE (c:ComplianceCode {code: $code})
                SET c.type = 'CPT', c.measure = 'BCS-E', c.description = 'Mammography CPT'
                WITH c MATCH (m:Measure {measure_id: 'BCS-E'})
                MERGE (m)-[:HAS_COMPLIANCE_CODE]->(c)
            """, code=cpt)
        print(f"ComplianceCode nodes: {len(MAMMOGRAPHY_CPT)} CPT")

        # ── ExclusionCode nodes ───────────────────────────────────────────────
        for excl_name, code_map in EXCLUSION_CODES.items():
            for code_type, codes in code_map.items():
                for code in codes:
                    s.run("""
                        MERGE (e:ExclusionCode {code: $code})
                        SET e.type = $code_type, e.exclusion_reason = $excl_name, e.measure = 'BCS-E'
                        WITH e MATCH (m:Measure {measure_id: 'BCS-E'})
                        MERGE (m)-[:HAS_EXCLUSION_CODE]->(e)
                    """, code=code, code_type=code_type, excl_name=excl_name)
        print("ExclusionCode nodes: OK")

        # ── 51 Realistic Persona nodes ────────────────────────────────────────
        print("Building 51 realistic personas...")
        personas = build_personas()
        s.run("""
            UNWIND $personas AS p
            MERGE (n:Persona {persona_id: p.persona_id})
            SET n += p
            WITH n
            MATCH (m:Measure {measure_id: 'BCS-E'})
            MERGE (n)-[:BELONGS_TO_MEASURE]->(m)
        """, personas=personas)
        print(f"  Personas loaded: {len(personas)}")

        # save JSON snapshot
        out_json = os.path.join(os.path.dirname(__file__), "bcs_all_combinations.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(personas, f, indent=2)
        print(f"Persona JSON saved: {out_json} ({len(personas)} personas)")

        # ── BenefitPlan node ──────────────────────────────────────────────────
        for _, row in benefit_df.iterrows():
            s.run("""
                MERGE (b:BenefitPlan {plan_id: $plan_id})
                SET b.preventive_services = $prev,
                    b.copay               = $copay,
                    b.deductible          = $ded,
                    b.eligibility_rules   = $rules
            """, plan_id=to_str(row["PlanID"]),
                 prev=to_str(row["PreventiveServicesCovered"]),
                 copay=float(row["Copay"]) if pd.notna(row["Copay"]) else None,
                 ded=float(row["Deductible"]) if pd.notna(row["Deductible"]) else None,
                 rules=to_str(row["EligibilityRules"]))
        print("BenefitPlan node: OK")

        # ── Provider nodes ────────────────────────────────────────────────────
        for _, row in providers_df.iterrows():
            s.run("""
                MERGE (p:Provider {provider_id: $pid})
                SET p.name           = $name,
                    p.specialty      = $spec,
                    p.facility_type  = $ftype,
                    p.network_status = $net,
                    p.location       = $loc
            """, pid=to_str(row["ProviderID"]), name=to_str(row["Name"]),
                 spec=to_str(row["Specialty"]), ftype=to_str(row["FacilityType"]),
                 net=to_str(row["NetworkStatus"]), loc=to_str(row["Location"]))
        print(f"Provider nodes: {len(providers_df)}")

        # ── Member nodes ──────────────────────────────────────────────────────
        for _, row in members_df.iterrows():
            age_str   = to_str(row["Member Age"]) or ""
            age_years = int(age_str.split()[0]) if age_str else None
            s.run("""
                MERGE (m:Member {member_id: $mid})
                SET m.name             = $name,
                    m.dob              = $dob,
                    m.gender           = $gender,
                    m.zip              = $zip,
                    m.enrollment_start = $enr_start,
                    m.enrollment_end   = $enr_end,
                    m.age_years        = $age
            """, mid=to_str(row["MemberID"]), name=to_str(row["Name"]),
                 dob=str(row["DOB"])[:10] if pd.notna(row["DOB"]) else None,
                 gender=to_str(row["Gender"]),
                 zip=to_str(row["ZIP"]),
                 enr_start=str(row["EnrollmentStart"])[:10] if pd.notna(row["EnrollmentStart"]) else None,
                 enr_end=str(row["EnrollmentEnd"])[:10] if pd.notna(row["EnrollmentEnd"]) else None,
                 age=age_years)
            # Member → PCP
            pcp = to_str(row["PCPID"])
            if pcp:
                s.run("""
                    MATCH (m:Member {member_id: $mid})
                    MATCH (p:Provider {provider_id: $pcp})
                    MERGE (m)-[:HAS_PCP]->(p)
                """, mid=to_str(row["MemberID"]), pcp=pcp)
        print(f"Member nodes: {len(members_df)}")

        # ── Enrollment nodes ──────────────────────────────────────────────────
        for _, row in enroll_df.iterrows():
            eid = f"ENR-{to_str(row['MemberID'])}"
            s.run("""
                MERGE (e:Enrollment {enrollment_id: $eid})
                SET e.member_id      = $mid,
                    e.plan_id        = $plan,
                    e.pcp_id         = $pcp,
                    e.effective_from = $from_dt,
                    e.effective_to   = $to_dt
                WITH e
                MATCH (m:Member {member_id: $mid})
                MERGE (m)-[:HAS_ENROLLMENT]->(e)
                WITH e
                MATCH (b:BenefitPlan {plan_id: $plan})
                MERGE (e)-[:UNDER_PLAN]->(b)
            """, eid=eid,
                 mid=to_str(row["MemberID"]),
                 plan=to_str(row["PlanID"]),
                 pcp=to_str(row["PCPID"]),
                 from_dt=str(row["EffectiveFrom"])[:10] if pd.notna(row["EffectiveFrom"]) else None,
                 to_dt=to_str(row["EffectiveTo"]))
        print(f"Enrollment nodes: {len(enroll_df)}")

        # ── Claim nodes ───────────────────────────────────────────────────────
        for _, row in claims_df.iterrows():
            cpt = to_str(row["CPTCode"])
            icd = to_str(row["ICDCode"])
            svc = str(row["ServiceDate"])[:10] if pd.notna(row["ServiceDate"]) else None
            is_bcs  = cpt in BCS_CPT_SET if cpt else False
            is_excl = (
                (cpt in EXCL_CPT_SET if cpt else False) or
                (icd in EXCL_ICD_SET if icd else False) or
                (icd in EXCL_PCS_SET if icd else False)
            )
            s.run("""
                MERGE (c:Claim {claim_id: $cid})
                SET c.member_id     = $mid,
                    c.provider_id   = $pid,
                    c.cpt_code      = $cpt,
                    c.icd_code      = $icd,
                    c.service_date  = $svc,
                    c.status        = $status,
                    c.bcs_compliant = $bcs,
                    c.bcs_exclusion = $excl
                WITH c
                MATCH (m:Member {member_id: $mid})
                MERGE (m)-[:HAS_CLAIM]->(c)
                WITH c
                MATCH (p:Provider {provider_id: $pid})
                MERGE (c)-[:SERVICED_BY]->(p)
            """, cid=to_str(row["ClaimID"]),
                 mid=to_str(row["MemberID"]),
                 pid=to_str(row["ProviderID"]),
                 cpt=cpt, icd=icd, svc=svc,
                 status=to_str(row["Status"]),
                 bcs=is_bcs, excl=is_excl)
        print(f"Claim nodes: {len(claims_df)}")

        # ── CareGap nodes (engine logic only) ──────────────────────────────────
        # Build member→claims lookup
        member_claims = {}
        for _, row in claims_df.iterrows():
            mid = to_str(row["MemberID"])
            member_claims.setdefault(mid, []).append({
                "cpt_code":    to_str(row["CPTCode"]),
                "icd_code":    to_str(row["ICDCode"]),
                "service_date": str(row["ServiceDate"])[:10] if pd.notna(row["ServiceDate"]) else None,
            })

        gap_summary = {"OPEN_GAP": 0, "COMPLIANT": 0, "EXCLUDED": 0, "NOT_ELIGIBLE": 0}

        for _, row in members_df.iterrows():
            mid    = to_str(row["MemberID"])
            age_str = to_str(row["Member Age"]) or ""
            age    = int(age_str.split()[0]) if age_str else 0
            gender = to_str(row["Gender"]) or ""
            claims = member_claims.get(mid, [])

            member_dict = {"gender": gender, "age_years": age}
            age_band, status, excl_reason, mammo_cpt, gc_code = evaluate_member(member_dict, claims)

            gap_id = f"GAP-BCS-{mid}"
            s.run("""
                MERGE (g:CareGap {gap_id: $gap_id})
                SET g.member_id        = $mid,
                    g.measure          = 'BCS-E',
                    g.status           = $status,
                    g.exclusion_reason = $excl,
                    g.has_mammogram    = $mammo,
                    g.created_on       = $today
                WITH g
                MATCH (m:Member {member_id: $mid})
                MERGE (m)-[:HAS_CARE_GAP]->(g)
                WITH g
                MATCH (meas:Measure {measure_id: 'BCS-E'})
                MERGE (g)-[:FOR_MEASURE]->(meas)
            """, gap_id=gap_id, mid=mid, status=status,
                 excl=excl_reason, mammo=mammo_cpt,
                 today=str(date.today()))

            # Match to persona (51 model)
            if age_band and status != "NOT_ELIGIBLE":
                if status == "EXCLUDED":
                    s.run("""
                        MATCH (mem:Member {member_id: $mid})
                        MATCH (p:Persona {
                            measure: 'BCS-E', care_gap_status: 'EXCLUDED',
                            gender_criteria_code: $gc, age_band_code: $ab,
                            exclusion_reason: $excl
                        })
                        WITH mem, p LIMIT 1
                        MERGE (mem)-[:MATCHES_PERSONA]->(p)
                    """, mid=mid, gc=gc_code, ab=age_band, excl=excl_reason)
                else:
                    s.run("""
                        MATCH (mem:Member {member_id: $mid})
                        MATCH (p:Persona {
                            measure: 'BCS-E', care_gap_status: $status,
                            gender_criteria_code: $gc, age_band_code: $ab,
                            mammogram_found: $mammo
                        })
                        WITH mem, p LIMIT 1
                        MERGE (mem)-[:MATCHES_PERSONA]->(p)
                    """, mid=mid, gc=gc_code, ab=age_band,
                         status=status, mammo=mammo_cpt)

            gap_summary[status] = gap_summary.get(status, 0) + 1

        print(f"CareGap nodes: {sum(gap_summary.values())} | {gap_summary}")

        # ── Outreach nodes ────────────────────────────────────────────────────
        for _, row in outreach_df.iterrows():
            oid = to_str(row["OutreachID"])
            gid = to_str(row["CareGapID"])
            mid = to_str(row["MemberID"])
            s.run("""
                MERGE (o:Outreach {outreach_id: $oid})
                SET o.care_gap_id     = $gid,
                    o.member_id       = $mid,
                    o.care_manager_id = $cm,
                    o.channel         = $channel,
                    o.date            = $dt,
                    o.status          = $status
                WITH o
                MATCH (g:CareGap {gap_id: $gid})
                MERGE (o)-[:FOR_CARE_GAP]->(g)
                WITH o
                MATCH (m:Member {member_id: $mid})
                MERGE (o)-[:OUTREACH_TO]->(m)
            """, oid=oid, gid=gid, mid=mid,
                 cm=to_str(row["CareManagerID"]),
                 channel=to_str(row["Channel"]),
                 dt=to_str(row["Date"]),
                 status=to_str(row["Status"]))
        print(f"Outreach nodes: {len(outreach_df)}")


def print_final_counts(driver):
    with driver.session(database=DB) as s:
        rows = s.run("MATCH (n) RETURN labels(n)[0] AS lbl, count(n) AS cnt ORDER BY lbl").data()
        rels  = s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(r) AS cnt ORDER BY t").data()

    print(f"\n{'='*45}")
    print("FINAL GRAPH STATE")
    print(f"{'='*45}")
    print(f"{'Node Label':<22} {'Count':>8}")
    print("-" * 32)
    for r in rows:
        print(f"{str(r['lbl']):<22} {r['cnt']:>8}")
    print(f"\n{'Relationship':<32} {'Count':>8}")
    print("-" * 42)
    for r in rels:
        print(f"{r['t']:<32} {r['cnt']:>8}")
    print(f"{'='*45}")


def main():
    # Force reload .env to pick up latest URI
    load_dotenv(override=True)
    uri  = os.getenv("NEO4J_URI") or "bolt+s://4202a166.databases.neo4j.io"
    user = os.getenv("NEO4J_USERNAME")
    pwd  = os.getenv("NEO4J_PASSWORD")
    global DB
    DB = os.getenv("NEO4J_DATABASE")

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    driver.verify_connectivity()
    print("Neo4j connected\n")
    try:
        load_all(driver)
        print_final_counts(driver)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
