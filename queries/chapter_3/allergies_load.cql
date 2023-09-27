:auto LOAD CSV WITH HEADERS from "https://raw.githubusercontent.com/PacktPublishing/Cypher-Querying/main/data/csv/allergies.csv" as row
CALL {
    WITH row
    MATCH (p:Patient {id:row.PATIENT})
    MERGE (c:SNOMED_CT {code:row.CODE})
    SET c.description=row.DESCRIPTION, c:Allergy
    MERGE (cs:Encounter {id:row.ENCOUNTER, isEnd: false})
      ON CREATE
      SET cs.date=datetime(row.START)
    MERGE (p)-[:HAS_ENCOUNTER]->(cs)
    MERGE (cs)-[:ALLERGY_STARTED]->(c)
    WITH p,c,cs,row
      WHERE row.STOP IS NOT NULL and row.STOP <> ''
    MERGE (ce:Encounter {id:row.ENCOUNTER,
                         date:datetime(row.STOP)})
    SET ce.isEnd=true
    MERGE (p)-[:HAS_ENCOUNTER]->(ce)
    MERGE (ce)-[:ALLERGY_ENDED]->(c)
    MERGE (cs)-[:HAS_END]->(ce)
} IN TRANSACTIONS OF 1000 ROWS
