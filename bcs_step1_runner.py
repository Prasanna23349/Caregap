"""
Step 1 Runner — Executes bcs_step1_neo4j_load.cypher against Neo4j
Splits on semicolons to run each statement individually.
"""
import os, re
from neo4j import GraphDatabase
from dotenv import load_dotenv
from bcs_logger import get_logger, log_step_start, log_step_end

load_dotenv()
logger = get_logger("bcs.step1")

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

CYPHER_FILE = os.path.join(os.path.dirname(__file__), "bcs_step1_neo4j_load.cypher")

def strip_comments(text):
    """Remove // line comments and blank lines."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        lines.append(line)
    return "\n".join(lines)

def split_statements(text):
    """Split on semicolons, skip empty statements."""
    raw = text.split(";")
    stmts = []
    for s in raw:
        clean = s.strip()
        if clean:
            stmts.append(clean)
    return stmts

def run_step1():
    log_step_start(logger, 1, "Load 30 Members into Neo4j")
    logger.info(f"Reading Cypher file: {CYPHER_FILE}")

    with open(CYPHER_FILE, "r", encoding="utf-8") as f:
        raw = f.read()

    text = strip_comments(raw)
    statements = split_statements(text)
    logger.info(f"Total statements to execute: {len(statements)}")

    ok = 0
    errors = []
    with driver.session() as session:
        for i, stmt in enumerate(statements, 1):
            try:
                session.run(stmt)
                ok += 1
                logger.debug(f"Statement {i:>3} OK")
            except Exception as e:
                errors.append((i, stmt[:80].replace('\n', ' '), str(e)))
                logger.error(f"❌ Statement {i}: {str(e)[:120]}")

    if errors:
        logger.warning(f"Completed: {ok}/{len(statements)} succeeded | {len(errors)} failed")
        for idx, snippet, err in errors:
            logger.warning(f"   [{idx}] {snippet}... => {err[:80]}")
    else:
        logger.info(f"✅ All {ok} statements executed without errors")

    # ── Node verification ──
    logger.info("--- VERIFICATION SUMMARY ---")
    node_counts = {}
    with driver.session() as session:
        labels = ["Member", "Demographics", "AgeRuleCheck", "Enrollment",
                  "ExclusionProfile", "ScreeningHistory", "CareGap",
                  "Claim", "Provider", "BenefitPlan", "QualityMeasure",
                  "Outreach", "CareManager"]
        for label in labels:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c").single()
            count = result["c"] if result else 0
            node_counts[label] = count
            logger.info(f"  {label:<20} {count:>4} nodes")

    # ── Gap status breakdown ──
    logger.info("--- BCS GAP STATUS BREAKDOWN ---")
    gap_stats = {}
    with driver.session() as session:
        result = session.run("""
            MATCH (m:Member)-[:HAS_CARE_GAP]->(cg:CareGap {measureID: 'BCS'})
            RETURN cg.gapStatus AS Status, count(m) AS Count
            ORDER BY Count DESC
        """)
        for row in result:
            gap_stats[row["Status"]] = row["Count"]
            logger.info(f"  {row['Status']:<20} {row['Count']:>4} members")

    driver.close()
    log_step_end(logger, 1, "Load Complete", {
        "Statements OK": f"{ok}/{len(statements)}",
        "Statement Errors": len(errors),
        **{f"Nodes — {k}": v for k, v in node_counts.items()},
        **{f"Gap — {k}": v for k, v in gap_stats.items()},
    })

if __name__ == "__main__":
    run_step1()
