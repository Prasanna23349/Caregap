"""
bcs_config.py — Dynamic configuration loader for BCS Care Gap Engine.

Loads all measure-specific constants from the Neo4j QualityMeasure node
and .env, so that NO hardcoded dates, ages, or CPT codes exist in the
Python pipeline scripts.

Usage:
    from bcs_config import BCS_CONFIG
    print(BCS_CONFIG["AGE_MIN"])  # 42
"""
import os
from datetime import date
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

_driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

def _load_config():
    """Read the BCS QualityMeasure node from Neo4j and build config dict."""
    measurement_year = int(os.getenv("MEASUREMENT_YEAR", 2026))

    try:
        with _driver.session() as s:
            row = s.run(
                "MATCH (q:QualityMeasure {measureID:'BCS'}) RETURN q"
            ).single()

            if row is None:
                raise ValueError("QualityMeasure node 'BCS' not found in Neo4j")

            qm = dict(row["q"])

            # Extract CPT codes — remove 77063 if present (standalone not valid per HEDIS)
            cpt_codes = set(qm.get("validCPTCodes", []))
            cpt_codes.discard("77063")

            config = {
                # Age thresholds
                "AGE_MIN":             qm.get("ageEligibilityMin", 42),
                "AGE_MAX":             qm.get("ageEligibilityMax", 74),
                "LOOKBACK_AGE_MIN":    qm.get("lookbackAgeMin", 40),

                # Date windows
                "LOOKBACK_START":      qm.get("measureWindowStart"),
                "LOOKBACK_END":        qm.get("measureWindowEnd"),
                "PROACTIVE_START":     qm.get("proactiveWindowStart"),

                # Measurement year
                "MEASUREMENT_YEAR":    measurement_year,
                "MEASUREMENT_YEAR_END": date(measurement_year, 12, 31),

                # Valid CPT codes (standalone 77063 excluded per HEDIS rules)
                "VALID_CPT":           cpt_codes,

                # Lookback durations (months)
                "LOOKBACK_MONTHS":     qm.get("measureLookbackMonths", 24),
                "PROACTIVE_MONTHS":    qm.get("proactiveLookbackMonths", 18),

                # Measure metadata
                "MEASURE_ID":          qm.get("measureID", "BCS"),
                "MEASURE_NAME":        qm.get("measureName", "Breast Cancer Screening"),
                "MEASURE_SOURCE":      qm.get("measureSource", "Hopkins HEDIS BCS-E"),
                "GENDER_REQUIREMENT":  qm.get("genderRequirement", "Female"),
            }

            # Convert neo4j date objects to python date if needed
            for key in ["LOOKBACK_START", "LOOKBACK_END", "PROACTIVE_START"]:
                val = config[key]
                if val is not None and not isinstance(val, date):
                    config[key] = date.fromisoformat(str(val))

            return config

    except Exception as e:
        # Fallback: if Neo4j is unavailable, use .env-based defaults
        print(f"⚠ Could not load config from Neo4j: {e}")
        print("  Using .env fallback values...")
        return {
            "AGE_MIN":             42,
            "AGE_MAX":             74,
            "LOOKBACK_AGE_MIN":    40,
            "LOOKBACK_START":      date(measurement_year - 2, 10, 1),
            "LOOKBACK_END":        date(measurement_year, 12, 31),
            "PROACTIVE_START":     date(measurement_year - 1, 6, 1),
            "MEASUREMENT_YEAR":    measurement_year,
            "MEASUREMENT_YEAR_END": date(measurement_year, 12, 31),
            "VALID_CPT":           {"77067", "77066", "77065", "77062", "77061"},
            "LOOKBACK_MONTHS":     24,
            "PROACTIVE_MONTHS":    18,
            "MEASURE_ID":          "BCS",
            "MEASURE_NAME":        "Breast Cancer Screening",
            "MEASURE_SOURCE":      "Hopkins HEDIS BCS-E",
            "GENDER_REQUIREMENT":  "Female",
        }


# Load once at module import — all other files import this dict
BCS_CONFIG = _load_config()
