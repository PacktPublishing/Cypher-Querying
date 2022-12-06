:auto LOAD CSV WITH HEADERS from "https://raw.githubusercontent.com/PacktPublishing/Cypher-Querying/main/data/csv/careplans.csv" as row
CALL {
    WITH row
    MATCH (p:Patient {id:row.PATIENT})
    MERGE (cp:CarePlan {code:row.Id})
    MERGE (c:SNOMED_CT {code:row.CODE})
      SET c.description=row.DESCRIPTION, c:Care
    MERGE (cp)-[:HAS_CARE_TYPE]->(c)
    MERGE (cs:Encounter {id:row.ENCOUNTER, isEnd: false})
      ON CREATE
      SET cs.date=datetime(row.START)
    MERGE (cs)-[:HAS_CARE_TYPE]->(c)
    MERGE (p)-[:HAS_ENCOUNTER]->(cs)
    MERGE (cs)-[:CARE_PLAN_START]->(cp)
    WITH p,cp,cs,row
      WHERE row.STOP IS NOT NULL and row.STOP <> ''
    CREATE (ce:Encounter {id:row.ENCOUNTER, date:datetime(row.STOP)})
      SET ce.code=row.CODE, ce.isEnd=true
    MERGE (p)-[:HAS_ENCOUNTER]->(ce)
    MERGE (ce)-[:CARE_PLAN_END]->(cp)
    MERGE (cs)-[:HAS_END]->(ce)
} IN TRANSACTIONS OF 1000 ROWS