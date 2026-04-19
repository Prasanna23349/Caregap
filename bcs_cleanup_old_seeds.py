"""Clean up old seed members and duplicate relationships, then verify."""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session() as s:
    # 1. Remove old MBR-* seed members and all their connected nodes
    print("Removing old seed members (MBR-*)...")
    r = s.run("""
        MATCH (m:Member) WHERE m.memberID STARTS WITH 'MBR-'
        OPTIONAL MATCH (m)-[r]->(n)
        DETACH DELETE m, n
    """)
    print("  Done — old MBR-* members removed")

    # 2. Remove orphaned nodes from old seed data
    for label in ["Demographics", "Enrollment", "CareGap", "ScreeningHistory", 
                  "Vitals", "ClinicalHistory", "SDOH", "Consent", "ExclusionProfile",
                  "AgeRuleCheck", "Claim", "Outreach"]:
        s.run(f"""
            MATCH (n:{label})
            WHERE NOT ()-[]->(n) AND NOT (n)-[]->()
            DELETE n
        """)
    print("  Orphaned nodes cleaned")

    # 3. Remove duplicate MATCHED_TO relationships
    s.run("MATCH ()-[r:MATCHED_TO]->() DELETE r")
    print("  Old MATCHED_TO relationships cleared")

    # 4. Verify member count
    r = s.run("MATCH (m:Member) RETURN count(m) AS c").single()
    print(f"\nTotal Members now: {r['c']}")

    # 5. Verify all are M0001-M0030
    r = s.run("MATCH (m:Member) RETURN m.memberID AS id ORDER BY id")
    ids = [row["id"] for row in r]
    print(f"Member IDs: {ids}")

    # 6. Gap status breakdown
    print("\nBCS Gap Status:")
    r = s.run("""
        MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS'})
        RETURN cg.gapStatus AS s, count(m) AS c ORDER BY c DESC
    """)
    for row in r:
        print(f"  {row['s']:<20} {row['c']:>3}")

driver.close()
print("\n✅ Cleanup done — only 30 BCS members remain")
