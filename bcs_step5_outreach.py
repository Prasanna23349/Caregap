"""
Step 5: Outreach Workflow
Creates Outreach nodes for every OPEN gap member based on
their inherited CareGapRecommendation outputs.
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from datetime import date, timedelta
from bcs_logger import get_logger, log_step_start, log_step_end

load_dotenv()
logger = get_logger("bcs.step5")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

# Care manager pool — assign round-robin by priority
CM_POOL = {
    "VERY HIGH":  "CM-101",
    "HIGH":       "CM-102",
    "MEDIUM":     "CM-103",
    "LOW":        "CM-104",
    "N/A":        None,
}

def get_open_gap_members():
    with driver.session() as s:
        return list(s.run("""
        MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'OPEN'})
        MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
        MATCH (m)-[:HAS_RECOMMENDATION]->(rec:CareGapRecommendation)
        OPTIONAL MATCH (m)-[:HAS_CONSENT]->(con:Consent)
        RETURN m.memberID AS mid, m.fullName AS name,
               d.age AS age, d.state AS state,
               cg.careGapID AS gid,
               rec.priorityLevel AS priority,
               rec.outreachChannel AS channel,
               rec.followUpDays AS followUpDays,
               rec.escalationPath AS escalation,
               rec.recommendedActions AS actions,
               rec.riskCategory AS risk,
               con.optOutOfOutreach AS optOut
        ORDER BY
          CASE rec.priorityLevel
            WHEN 'VERY HIGH (CRITICAL)' THEN 1
            WHEN 'VERY HIGH' THEN 2
            WHEN 'HIGH' THEN 3
            WHEN 'MEDIUM' THEN 4
            WHEN 'LOW' THEN 5
            ELSE 6
          END, d.age DESC
    """))

def create_outreach_node(mid, name, priority, channel, follow_up_days, escalation, gid):
    today = date.today()
    try:
        fdays = int(follow_up_days)
    except (TypeError, ValueError):
        fdays = 21
    follow_up_date = today + timedelta(days=fdays)
    cm_id = CM_POOL.get(str(priority).split()[0] if priority else "N/A", "CM-103")

    out_id = f"OUT-BCS-{mid}"

    with driver.session() as s:
        # Merge CareManagers
        if cm_id:
            s.run("""
                MERGE (cm:CareManager {careManagerID: $cmid})
                SET cm.careManagerName = $name,
                    cm.specialty = 'BCS',
                    cm.status = 'Active'
            """, cmid=cm_id, name=f"Care Manager {cm_id}")

        # Create Outreach node
        s.run("""
            MERGE (o:Outreach {outreachID: $oid})
            SET o.memberID       = $mid,
                o.careGapID      = $gid,
                o.channel        = $channel,
                o.outreachDate   = date($today),
                o.followUpDate   = date($followUp),
                o.outreachStatus = 'Pending',
                o.outcome        = 'Not Attempted',
                o.priorityLevel  = $priority,
                o.escalationPath = $escalation,
                o.careManagerID  = $cmid,
                o.assignedDate   = date($today)
        """, oid=out_id, mid=mid, gid=gid, channel=channel or "SMS",
             today=str(today), followUp=str(follow_up_date),
             priority=priority, escalation=escalation, cmid=cm_id)

        # Link Member → Outreach
        s.run("""
            MATCH (m:Member {memberID: $mid})
            MATCH (o:Outreach {outreachID: $oid})
            MERGE (m)-[:HAS_OUTREACH]->(o)
        """, mid=mid, oid=out_id)

        # Link CareGap → Outreach
        s.run("""
            MATCH (m:Member {memberID: $mid})-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
            MATCH (o:Outreach {outreachID: $oid})
            MERGE (cg)-[:TRIGGERED_OUTREACH]->(o)
        """, mid=mid, oid=out_id)

        # Link Outreach → CareManager
        if cm_id:
            s.run("""
                MATCH (o:Outreach {outreachID: $oid})
                MATCH (cm:CareManager {careManagerID: $cmid})
                MERGE (o)-[:PERFORMED_BY]->(cm)
            """, oid=out_id, cmid=cm_id)

    return out_id, cm_id, follow_up_date

def run_step5():
    log_step_start(logger, 5, "Outreach Workflow")

    members = get_open_gap_members()
    logger.info(f"OPEN gap members to receive outreach: {len(members)}")

    created = []
    skipped = []

    for row in members:
        mid       = row["mid"]
        name      = row["name"]
        age       = row["age"]
        priority  = row["priority"]
        channel   = row["channel"]
        follow_up = row["followUpDays"]
        escalation= row["escalation"]
        gid       = row["gid"] or f"GAP-BCS-{mid}"
        opt_out   = row["optOut"]

        if opt_out:
            skipped.append((mid, name, "Opted out of outreach"))
            logger.warning(f"SKIPPED {mid} | {name} — opted out of outreach")
            continue

        out_id, cm_id, followup_date = create_outreach_node(
            mid, name, priority, channel, follow_up, escalation, gid
        )
        created.append((mid, name, age, priority, channel, cm_id, followup_date))
        logger.info(f"✅ Outreach created | {mid} | {name:<22} | Age {age} | "
                    f"{str(priority):<15} | {str(channel):<25} | "
                    f"CM: {cm_id} | Follow-up: {followup_date}")

    logger.info(f"--- OUTREACH SUMMARY ---")
    logger.info(f"Created:  {len(created)} outreach records")
    if skipped:
        logger.warning(f"Skipped:  {len(skipped)} (opt-out)")

    logger.info("--- PRIORITY QUEUE ---")
    for i, (mid, name, age, pri, ch, cm, fu) in enumerate(created, 1):
        logger.info(f"  {i:<3} {mid} | {name:<22} | {str(pri):<20} | {str(ch):<25} | {fu}")

    with driver.session() as s:
        r = s.run("MATCH (o:Outreach) RETURN count(o) AS c").single()
        logger.info(f"Total Outreach nodes in Neo4j: {r['c']}")
        r2 = s.run("""
            MATCH (o:Outreach)-[:PERFORMED_BY]->(cm:CareManager)
            RETURN cm.careManagerID AS cm, count(o) AS assignments ORDER BY assignments DESC
        """)
        logger.info("Care Manager Assignments:")
        for row in r2:
            logger.info(f"  {row['cm']}: {row['assignments']} records")

    log_step_end(logger, 5, "Outreach Workflow", {
        "Outreach records created": len(created),
        "Members skipped (opt-out)": len(skipped),
    })

if __name__ == "__main__":
    run_step5()
