"""
bcs_ehr_ingestion.py — Ingests FHIR clinical data + SDOH survey data,
calculates BMI, and updates the Knowledge Graph.

Data Sources:
  - bcs_mock_ehr_data.json  → Clinical (from hospital EHR systems)
  - bcs_mock_sdoh_data.json → Social Determinants (from member surveys)
"""
import os
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv
from bcs_logger import get_logger, log_step_start, log_step_end
from bcs_step2_matching import run_step2
from bcs_step3_inherit import run_step3
from bcs_step5_outreach import run_step5

load_dotenv()
logger = get_logger("bcs.ehr_ingest")
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

# ── BMI Calculation ────────────────────────────────────────────────────────

def calculate_bmi_category(height_inches, weight_lbs):
    """Calculate BMI from imperial units and return WHO category string."""
    if not height_inches or not weight_lbs:
        return "PENDING"
    if height_inches <= 0:
        logger.warning(f"Invalid height: {height_inches} inches — skipping BMI")
        return "PENDING"
    bmi = 703 * (weight_lbs / (height_inches ** 2))
    bmi = round(bmi, 1)

    if bmi < 18.5:
        return "Underweight"
    elif 18.5 <= bmi < 25:
        return "Normal"
    elif 25 <= bmi < 30:
        return "Overweight"
    else:
        return "Obese (BMI>30)"


# ── FHIR Bundle Parser ────────────────────────────────────────────────────

def parse_fhir_bundle(bundle):
    """Extract all clinical factors from a FHIR bundle."""
    member_id = bundle["id"].replace("bundle-", "")
    height = None
    weight = None

    # Default all fields to PENDING — only overwritten if data is found
    clinical_data = {
        "familyHistory":        "PENDING",
        "brcaStatus":           "PENDING",
        "alcoholUse":           "PENDING",
        "denseBreast":          "PENDING",
        "hrtUse":               "PENDING",
        "sedentary":            "PENDING",
        "priorBiopsy":          "PENDING",
        "earlyMenarche":        "PENDING",
        "firstPregnancyAfter30":"PENDING",
        "noBreastfeeding":      "PENDING",
    }

    for entry in bundle.get("entry", []):
        rtype = entry.get("resourceType")

        if rtype == "Observation":
            code = entry.get("code", {}).get("text", "")
            val  = entry.get("valueQuantity", {}).get("value")

            if code == "Body Height":
                height = val
            elif code == "Body Weight":
                weight = val
            elif code == "Alcohol Use":
                vstr = entry.get("valueString", "")
                if vstr.lower() == "none":
                    clinical_data["alcoholUse"] = "Non-drinker"
                elif vstr.lower() == "heavy":
                    clinical_data["alcoholUse"] = "Heavy"
                else:
                    clinical_data["alcoholUse"] = vstr

        elif rtype == "Condition":
            code   = entry.get("code", {}).get("text", "")
            status = entry.get("verificationStatus", {}).get("text", "")
            confirmed = (status == "Confirmed")

            if code == "Family History of Breast Cancer":
                clinical_data["familyHistory"] = "Yes" if confirmed else "No"
            elif code == "BRCA Gene Mutation":
                clinical_data["brcaStatus"] = "Positive" if confirmed else "Negative"
            elif code == "Dense Breasts":
                clinical_data["denseBreast"] = "True" if confirmed else "False"
            elif code == "HRT Use":
                clinical_data["hrtUse"] = "Yes (C)" if confirmed else "No"
            elif code == "Sedentary Lifestyle":
                clinical_data["sedentary"] = "Regular" if confirmed else "Never"
            elif code == "Prior Biopsy":
                if confirmed:
                    note = entry.get("note", "Yes")
                    clinical_data["priorBiopsy"] = note if note else "Yes"
                else:
                    clinical_data["priorBiopsy"] = "None"
            elif code == "Early Menarche":
                clinical_data["earlyMenarche"] = True if confirmed else False
            elif code == "First Pregnancy After 30":
                clinical_data["firstPregnancyAfter30"] = True if confirmed else False
            elif code == "No Breastfeeding":
                clinical_data["noBreastfeeding"] = True if confirmed else False

    # Calculate BMI
    clinical_data["bmi"] = calculate_bmi_category(height, weight)

    return member_id, clinical_data


# ── Neo4j Updaters ─────────────────────────────────────────────────────────

def update_clinical_data(member_id, data):
    """Update ClinicalHistory and Vitals nodes in Neo4j."""
    # Validate member exists
    with driver.session() as s:
        exists = s.run(
            "MATCH (m:Member {memberID: $mid}) RETURN count(m) AS c",
            mid=member_id
        ).single()["c"]
        if exists == 0:
            logger.warning(f"⚠ Member {member_id} not found in Neo4j — skipping")
            return False

        # Update Clinical History — all 11 fields
        s.run("""
            MATCH (m:Member {memberID: $mid})-[:HAS_CLINICAL_HISTORY]->(c:ClinicalHistory)
            SET c.familyHistory        = CASE WHEN $fh    <> 'PENDING' THEN $fh    ELSE c.familyHistory END,
                c.brcaStatus           = CASE WHEN $brca  <> 'PENDING' THEN $brca  ELSE c.brcaStatus END,
                c.alcoholUse           = CASE WHEN $alc   <> 'PENDING' THEN $alc   ELSE c.alcoholUse END,
                c.denseBreast          = CASE WHEN $db    <> 'PENDING' THEN $db    ELSE c.denseBreast END,
                c.hrtUse               = CASE WHEN $hrt   <> 'PENDING' THEN $hrt   ELSE c.hrtUse END,
                c.sedentary            = CASE WHEN $sed   <> 'PENDING' THEN $sed   ELSE c.sedentary END,
                c.priorBiopsy          = CASE WHEN $bio   <> 'PENDING' THEN $bio   ELSE c.priorBiopsy END,
                c.earlyMenarche        = $menarche,
                c.firstPregnancyAfter30= $preg30,
                c.noBreastfeeding      = $nobf,
                c.status               = 'Enriched via EHR'
        """, mid=member_id,
             fh=data["familyHistory"], brca=data["brcaStatus"],
             alc=data["alcoholUse"], db=data["denseBreast"],
             hrt=data["hrtUse"], sed=data["sedentary"],
             bio=data["priorBiopsy"],
             menarche=data["earlyMenarche"],
             preg30=data["firstPregnancyAfter30"],
             nobf=data["noBreastfeeding"])

        # Update Vitals — BMI
        s.run("""
            MATCH (m:Member {memberID: $mid})-[:HAS_VITALS]->(v:Vitals)
            SET v.bmi    = CASE WHEN $bmi <> 'PENDING' THEN $bmi ELSE v.bmi END,
                v.status = 'Enriched via EHR'
        """, mid=member_id, bmi=data["bmi"])

    return True


def update_sdoh_data(member_id, sdoh):
    """Update SDOH node with survey data."""
    with driver.session() as s:
        s.run("""
            MATCH (m:Member {memberID: $mid})-[:HAS_SDOH]->(sd:SDOH)
            SET sd.engagementLevel      = $eng,
                sd.knownBarrier         = $barrier,
                sd.transportationAccess = $transport,
                sd.languageBarrier      = $lang,
                sd.fearBarrier          = $fear,
                sd.costBarrier          = $cost,
                sd.status               = 'Enriched via Survey'
        """, mid=member_id,
             eng=sdoh["engagementLevel"],
             barrier=sdoh["knownBarrier"],
             transport=sdoh["transportationAccess"],
             lang=sdoh["languageBarrier"],
             fear=sdoh["fearBarrier"],
             cost=sdoh["costBarrier"])


def update_caregap_priority(member_id):
    """Copy the priority from CareGapRecommendation back to the CareGap node."""
    with driver.session() as s:
        s.run("""
            MATCH (m:Member {memberID: $mid})-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
            MATCH (m)-[:HAS_RECOMMENDATION]->(rec:CareGapRecommendation)
            WHERE rec.gapStatus = cg.gapStatus
            SET cg.priorityLevel = rec.priorityLevel,
                cg.riskCategory  = rec.riskCategory
        """, mid=member_id)


# ── Main Ingestion Runner ─────────────────────────────────────────────────

def run_ingestion():
    log_step_start(logger, "EHR", "EHR + SDOH Data Ingestion")

    # ── 1. Ingest Clinical EHR Data ──
    logger.info("--- PHASE 1: CLINICAL EHR DATA ---")
    with open("bcs_mock_ehr_data.json", "r") as f:
        bundles = json.load(f)

    logger.info(f"Loaded {len(bundles)} FHIR bundles.")
    ehr_updated = 0

    for bundle in bundles:
        mid, data = parse_fhir_bundle(bundle)
        logger.info(f"Parsed {mid}: BMI={data['bmi']}, FHx={data['familyHistory']}, "
                     f"BRCA={data['brcaStatus']}, Dense={data['denseBreast']}, "
                     f"Biopsy={data['priorBiopsy']}")
        if update_clinical_data(mid, data):
            ehr_updated += 1
            logger.info(f"✅ Updated {mid} clinical data in Neo4j")

    # ── 2. Ingest SDOH Survey Data ──
    logger.info("--- PHASE 2: SDOH SURVEY DATA ---")
    sdoh_file = "bcs_mock_sdoh_data.json"
    sdoh_updated = 0
    try:
        with open(sdoh_file, "r") as f:
            sdoh_records = json.load(f)
        logger.info(f"Loaded {len(sdoh_records)} SDOH survey records.")
        for rec in sdoh_records:
            mid = rec["memberID"]
            update_sdoh_data(mid, rec)
            sdoh_updated += 1
            logger.info(f"✅ Updated {mid} SDOH data | Engagement: {rec['engagementLevel']} | "
                         f"Barrier: {rec['knownBarrier']}")
    except FileNotFoundError:
        logger.warning(f"⚠ {sdoh_file} not found — SDOH data not ingested")

    # ── 3. Recalibrate Pipeline ──
    logger.info("--- TRIGGERING PIPELINE RECALIBRATION ---")
    logger.info("Running Step 2: Matching...")
    run_step2()
    logger.info("Running Step 3: Inherit...")
    run_step3()

    # ── 4. Update CareGap priority from recommendations ──
    logger.info("--- PHASE 4: SYNCING CAREGAP PRIORITY ---")
    with driver.session() as s:
        members = s.run("""
            MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
            WHERE cg.gapStatus = 'OPEN'
            RETURN m.memberID AS mid
        """)
        for row in members:
            update_caregap_priority(row["mid"])
    logger.info("✅ CareGap priority levels synced from recommendations")

    logger.info("Running Step 5: Outreach...")
    run_step5()

    log_step_end(logger, "EHR", "EHR + SDOH Data Ingestion", {
        "EHR Members Updated": ehr_updated,
        "SDOH Members Updated": sdoh_updated,
    })

if __name__ == "__main__":
    run_ingestion()
