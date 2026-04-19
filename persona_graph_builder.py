import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from bcs_personas import PERSONAS

load_dotenv()
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")))

def _merge_node(tx, label, key, val, props):
    tx.run(f"MERGE (n:{label} {{{key}: $v}}) SET n += $p", v=val, p={k: str(v) if isinstance(v, list) else v for k, v in props.items()})

def _merge_rel(tx, l1, k1, v1, rel, l2, k2, v2):
    tx.run(f"MATCH (a:{l1} {{{k1}: $v1}}) MATCH (b:{l2} {{{k2}: $v2}}) MERGE (a)-[:{rel}]->(b)", v1=v1, v2=v2)

def load_persona(persona):
    pid = persona["persona"]["personaID"]
    with driver.session() as s:
        s.execute_write(_merge_node, "IdealPersona", "personaID", pid, persona["persona"])
        for node_key, label, rel, id_suffix in [
            ("age_rule",    "AgeRuleCheck",      "HAS_AGE_RULE",        "AGE"),
            ("enrollment",  "EnrollmentProfile", "HAS_ENROLLMENT",      "ENR"),
            ("screening",   "ScreeningProfile",  "HAS_SCREENING",       "SCR"),
            ("risk",        "RiskProfile",       "HAS_RISK",            "RISK"),
            ("comorbidity", "ComorbidityProfile","HAS_COMORBIDITY",     "COM"),
            ("exclusion",   "ExclusionProfile",  "HAS_EXCLUSION",       "EXC"),
            ("engagement",  "EngagementProfile", "HAS_ENGAGEMENT",      "ENG"),
            ("output",      "CareGapOutput",     "HAS_CARE_GAP_OUTPUT", "OUT"),
        ]:
            nid = f"{pid}-{id_suffix}"
            props = {**persona[node_key], "nodeID": nid}
            s.execute_write(_merge_node, label, "nodeID", nid, props)
            s.execute_write(_merge_rel, "IdealPersona", "personaID", pid, rel, label, "nodeID", nid)

if __name__ == "__main__":
    from schema import apply_schema
    apply_schema(driver)
    # Remove old Persona nodes first
    with driver.session() as s:
        s.run("MATCH (n:Persona) DETACH DELETE n")
        for lbl in ["PersonaDemographics","PersonaEnrollment","PersonaClinical","PersonaScreening","PersonaExclusion","PersonaRiskProfile","PersonaExpectedOutcome"]:
            s.run(f"MATCH (n:{lbl}) DETACH DELETE n")
    print(f"Loading {len(PERSONAS)} personas...")
    for persona in PERSONAS:
        load_persona(persona)
        print(f"  Loaded {persona['persona']['personaID']} — {persona['persona']['personaName']}")
    print(f"\u2705 All {len(PERSONAS)} personas loaded as isolated subgraph.")
    driver.close()
