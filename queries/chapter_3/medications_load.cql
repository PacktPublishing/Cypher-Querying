:auto LOAD CSV WITH HEADERS from "https://raw.githubusercontent.com/PacktPublishing/Cypher-Querying/main/data/csv/medications.csv" as row
CALL {
    WITH row
    MERGE (p:Patient {id:row.PATIENT})
    MERGE (d:Drug {code:row.CODE})
    SET d.description=row.DESCRIPTION
    MERGE (ps:Encounter {id:row.ENCOUNTER, isEnd: false})
    MERGE (ps)-[:HAS_DRUG]->(d)
    MERGE (p)-[:HAS_ENCOUNTER]->(ps)
    FOREACH( ignore in CASE WHEN row.REASONCODE IS NOT NULL AND
    row.REASONCODE <> '' THEN [1] ELSE [] END |
      MERGE(s:SNOMED_CT {code:row.CODE})
      SET s:Diagnosis, s.description = row.REASONDESCRIPTION
      MERGE (ps)-[:HAS_DIAGNOSIS]->(s)
    )
    WITH row,ps,p
      WHERE row.STOP IS NOT NULL and row.STOP <> ''
    CREATE (pe:Encounter {id:row.ENCOUNTER, date:datetime(row.
      STOP)})
    SET pe.isEnd=true
    CREATE (p)-[:HAS_ENCOUNTER]->(pe)
    CREATE (pe)-[:HAS_DRUG]->(d)
    CREATE (ps)-[:HAS_END]->(pe)
} IN TRANSACTIONS OF 1000 ROWS
