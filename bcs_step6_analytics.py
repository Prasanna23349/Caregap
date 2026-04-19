"""
Step 6: Population Analytics
Generates aggregate BCS quality metrics across the 30-member cohort.
"""
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from bcs_logger import get_logger, log_step_start, log_step_end

load_dotenv()
logger = get_logger("bcs.step6")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

def q(session, query):
    return [dict(r) for r in session.run(query)]

def run_step6():
    log_step_start(logger, 6, "Population Analytics")

    with driver.session() as s:

        # ── 1. Overall gap status distribution ──
        print("\n📊 1. BCS GAP STATUS DISTRIBUTION")
        rows = q(s, """
            MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
            RETURN cg.gapStatus AS Status, count(m) AS Count
            ORDER BY Count DESC
        """)
        total = sum(r["Count"] for r in rows)
        for r in rows:
            pct = round(r["Count"] / total * 100, 1)
            bar = "█" * int(pct / 5)
            print(f"  {r['Status']:<20} {r['Count']:>3}  ({pct:>5}%)  {bar}")
        print(f"  {'TOTAL':<20} {total:>3}")

        # ── 2. BCS Compliance Rate (eligible females only) ──
        print("\n📊 2. BCS COMPLIANCE RATE (Eligible Females 42–74)")
        rows = q(s, """
            MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
            MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
            WHERE d.administrativeGender = 'Female' AND d.age >= 42 AND d.age <= 74
            RETURN cg.gapStatus AS Status, count(m) AS Count
            ORDER BY Count DESC
        """)
        elig_total = sum(r["Count"] for r in rows)
        closed = next((r["Count"] for r in rows if r["Status"] == "CLOSED"), 0)
        open_  = next((r["Count"] for r in rows if r["Status"] == "OPEN"), 0)
        rate   = round(closed / elig_total * 100, 1) if elig_total else 0
        for r in rows:
            print(f"  {r['Status']:<15} {r['Count']:>2} / {elig_total}")
        print(f"\n  ⭐ BCS COMPLIANCE RATE: {closed}/{elig_total} = {rate}%")
        print(f"  ⚠️  GAP RATE:            {open_}/{elig_total} = {round(100-rate,1)}%")

        # ── 3. Age band distribution (eligible females) ──
        print("\n📊 3. AGE BAND DISTRIBUTION (Eligible Females)")
        rows = q(s, """
            MATCH (m:Member)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
            MATCH (m)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS'})
            WHERE d.administrativeGender = 'Female' AND d.age >= 42 AND d.age <= 74
            RETURN
              CASE
                WHEN d.age <= 50 THEN '42–50'
                WHEN d.age <= 60 THEN '51–60'
                WHEN d.age <= 70 THEN '61–70'
                ELSE '71–74'
              END AS AgeBand,
              cg.gapStatus AS Status,
              count(m) AS Count
            ORDER BY AgeBand, Status
        """)
        bands = {}
        for r in rows:
            b = r["AgeBand"]
            if b not in bands:
                bands[b] = {}
            bands[b][r["Status"]] = r["Count"]
        for band, statuses in sorted(bands.items()):
            o = statuses.get("OPEN", 0)
            c = statuses.get("CLOSED", 0)
            print(f"  Age {band:<8} → OPEN: {o}  CLOSED: {c}  (Total: {o+c})")

        # ── 4. Persona match distribution ──
        print("\n📊 4. PERSONA MATCH DISTRIBUTION")
        rows = q(s, """
            MATCH (m:Member)-[:MATCHED_TO]->(p:IdealPersona)
            RETURN p.personaID AS Persona, p.personaName AS Name,
                   p.group AS Group, count(m) AS Members
            ORDER BY Members DESC
        """)
        for r in rows:
            print(f"  {r['Persona']} ({r['Group']:<20}) → {r['Members']} members  |  {r['Name'][:50]}")

        # ── 5. Risk category breakdown (OPEN gaps only) ──
        print("\n📊 5. RISK CATEGORY (OPEN gaps only)")
        rows = q(s, """
            MATCH (m:Member)-[:HAS_RECOMMENDATION]->(rec:CareGapRecommendation)
            WHERE rec.gapStatus = 'OPEN'
            RETURN rec.riskCategory AS Risk, count(m) AS Count
            ORDER BY Count DESC
        """)
        for r in rows:
            print(f"  {str(r['Risk']):<20} {r['Count']:>2} members")

        # ── 6. Outreach channel distribution ──
        print("\n📊 6. OUTREACH CHANNEL DISTRIBUTION (OPEN gaps)")
        rows = q(s, """
            MATCH (m:Member)-[:HAS_OUTREACH]->(o:Outreach)
            RETURN o.channel AS Channel, count(o) AS Count
            ORDER BY Count DESC
        """)
        if rows:
            for r in rows:
                print(f"  {str(r['Channel']):<35} {r['Count']:>2} members")
        else:
            print("  (No outreach nodes yet — run Step 5 first)")

        # ── 7. Data completeness ──
        print("\n📊 7. DATA COMPLETENESS STATUS")
        rows = q(s, """
            MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID:'BCS', gapStatus:'OPEN'})
            OPTIONAL MATCH (m)-[:HAS_CLINICAL_HISTORY]->(ch:ClinicalHistory)
            OPTIONAL MATCH (m)-[:HAS_VITALS]->(v:Vitals)
            OPTIONAL MATCH (m)-[:HAS_SDOH]->(sd:SDOH)
            RETURN
              count(CASE WHEN ch.status STARTS WITH 'PENDING' THEN 1 END) AS ClinHxPending,
              count(CASE WHEN v.status STARTS WITH 'PENDING' THEN 1 END) AS VitalsPending,
              count(CASE WHEN sd.status STARTS WITH 'PENDING' THEN 1 END) AS SDOHPending,
              count(m) AS TotalOpen
        """)
        if rows:
            r = rows[0]
            logger.info(f"  Total OPEN gap members:          {r['TotalOpen']}")
            logger.info(f"  Clinical History PENDING:        {r['ClinHxPending']}")
            logger.info(f"  Vitals PENDING:                  {r['VitalsPending']}")
            logger.info(f"  SDOH PENDING:                    {r['SDOHPending']}")
            logger.warning("After EHR enrichment, re-run Step 2 for precise persona matching")

        # ── 8. Urgent action list ──
        logger.info("\n--- 8. URGENT ACTION (<=7-day follow-up) ---")
        rows = q(s, """
            MATCH (m:Member)-[:HAS_OUTREACH]->(o:Outreach)
            MATCH (m)-[:HAS_DEMOGRAPHICS]->(d:Demographics)
            WHERE o.priorityLevel IN ['VERY HIGH','VERY HIGH (CRITICAL)']
            RETURN m.memberID AS MemberID, m.fullName AS Name,
                   d.age AS Age, o.channel AS Channel,
                   o.followUpDate AS FollowUp, o.careManagerID AS CM
            ORDER BY d.age DESC
        """)
        if rows:
            for r in rows:
                logger.info(f"  {r['MemberID']} | {str(r['Name']):<22} | Age {r['Age']} | "
                            f"{str(r['Channel']):<25} | Follow-up: {r['FollowUp']} | CM: {r['CM']}")
        else:
            logger.warning("No urgent outreach records found — run Step 5 first")

    driver.close()
    log_step_end(logger, 6, "Population Analytics", {
        "Total members": total,
        "BCS Compliance Rate": f"{rate}%",
        "OPEN gap members": open_,
        "CLOSED (compliant)": closed,
    })

if __name__ == "__main__":
    run_step6()
