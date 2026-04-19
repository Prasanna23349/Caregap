"""
bcs_ehr_ingestion.py — Ingests mock FHIR data, calculates BMI, updates graph.
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

def calculate_bmi_category(height_inches, weight_lbs):
    if not height_inches or not weight_lbs:
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

def parse_fhir_bundle(bundle):
    """Extract clinical factors from a FHIR bundle."""
    member_id = bundle["id"].replace("bundle-", "")
    height = None
    weight = None
    
    # Defaults
    clinical_data = {
        "familyHistory": "PENDING",
        "brcaStatus": "PENDING",
        "alcoholUse": "PENDING",
        "denseBreast": "PENDING",
        "hrtUse": "PENDING",
        "sedentary": "PENDING"
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

        elif rtype == "Condition":
            code = entry.get("code", {}).get("text", "")
            status = entry.get("verificationStatus", {}).get("text", "")
            
            if code == "Family History of Breast Cancer":
                clinical_data["familyHistory"] = "Yes" if status == "Confirmed" else "No"
            elif code == "BRCA Gene Mutation":
                clinical_data["brcaStatus"] = "Positive" if status == "Confirmed" else "Negative"
            elif code == "Dense Breasts":
                clinical_data["denseBreast"] = "True" if status == "Confirmed" else "False"
            elif code == "HRT Use":
                clinical_data["hrtUse"] = "Yes (C)" if status == "Confirmed" else "No"
            elif code == "Sedentary Lifestyle":
                clinical_data["sedentary"] = "Regular" if status == "Confirmed" else "Never"

    # Calculate BMI
    bmi_cat = calculate_bmi_category(height, weight)
    clinical_data["bmi"] = bmi_cat
    
    return member_id, clinical_data

def update_neo4j(member_id, data):
    """Update ClinicalHistory and Vitals nodes in Neo4j."""
    with driver.session() as s:
        # Update Clinical History
        s.run("""
            MATCH (m:Member {memberID: $mid})-[:HAS_CLINICAL_HISTORY]->(c:ClinicalHistory)
            SET c.familyHistory = CASE WHEN $fh <> 'PENDING' THEN $fh ELSE c.familyHistory END,
                c.brcaStatus    = CASE WHEN $brca <> 'PENDING' THEN $brca ELSE c.brcaStatus END,
                c.alcoholUse    = CASE WHEN $alc <> 'PENDING' THEN $alc ELSE c.alcoholUse END,
                c.denseBreast   = CASE WHEN $db <> 'PENDING' THEN $db ELSE c.denseBreast END,
                c.hrtUse        = CASE WHEN $hrt <> 'PENDING' THEN $hrt ELSE c.hrtUse END,
                c.sedentary     = CASE WHEN $sed <> 'PENDING' THEN $sed ELSE c.sedentary END,
                c.status        = 'Enriched via EHR'
        """, mid=member_id, fh=data["familyHistory"], brca=data["brcaStatus"], 
             alc=data["alcoholUse"], db=data["denseBreast"], hrt=data["hrtUse"], sed=data["sedentary"])
        
        # Update Vitals
        s.run("""
            MATCH (m:Member {memberID: $mid})-[:HAS_VITALS]->(v:Vitals)
            SET v.bmi = CASE WHEN $bmi <> 'PENDING' THEN $bmi ELSE v.bmi END,
                v.status = 'Enriched via EHR'
        """, mid=member_id, bmi=data["bmi"])

def run_ingestion():
    log_step_start(logger, "EHR", "EHR Data Ingestion")
    
    with open("bcs_mock_ehr_data.json", "r") as f:
        bundles = json.load(f)
        
    logger.info(f"Loaded {len(bundles)} FHIR bundles.")
    
    for bundle in bundles:
        mid, data = parse_fhir_bundle(bundle)
        logger.info(f"Parsed {mid}: BMI={data['bmi']}, FHx={data['familyHistory']}, BRCA={data['brcaStatus']}")
        update_neo4j(mid, data)
        logger.info(f"✅ Updated {mid} in Neo4j")
        
    logger.info("--- TRIGGERING PIPELINE RECALIBRATION ---")
    logger.info("Running Step 2: Matching...")
    run_step2()
    logger.info("Running Step 3: Inherit...")
    run_step3()
    logger.info("Running Step 5: Outreach...")
    run_step5()
    
    log_step_end(logger, "EHR", "EHR Data Ingestion", {"Members Updated": len(bundles)})

if __name__ == "__main__":
    run_ingestion()
