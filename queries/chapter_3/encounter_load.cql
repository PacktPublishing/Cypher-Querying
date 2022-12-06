:auto LOAD CSV WITH HEADERS from "https://raw.githubusercontent.com/PacktPublishing/Cypher-Querying/main/data/csv/encounters.csv" as row
CALL {
    WITH row
    MERGE(e:Encounter {id: row.Id})
    SET
    e.date=datetime(row.START),
    e.description=row.DESCRIPTION,
    e.isEnd = false
    FOREACH (ignore in CASE WHEN row.STOP IS NOT NULL AND row.STOP <> '' THEN [1] ELSE [] END |
      SET e.end=datetime(row.STOP)
    )
    FOREACH (ignore in CASE WHEN row.CODE IS NOT NULL AND row.CODE <> '' THEN [1] ELSE [] END |
      MERGE(s:SNOMED_CT {code:row.CODE})
      MERGE(e)-[:OF_TYPE]->(s)
    )
    WITH row,e
    CALL apoc.create.setLabels( e, [ 'Encounter', row.ENCOUNTERCLASS ] ) YIELD node
    WITH row,e
    MERGE(p:Patient {id: row.PATIENT})
    MERGE (p)-[:HAS_ENCOUNTER]->(e)
    WITH row,e
    MERGE (provider:Provider {id:row.PROVIDER})
    MERGE(e)-[:HAS_PROVIDER]->(provider)
    FOREACH (ignore in CASE WHEN row.ORGANIZATION IS NOT
    NULL AND row.ORGANIZATION <> '' THEN [1] ELSE [] END |
      MERGE (o:Organization {id: row.ORGANIZATION})
      MERGE (e)-[:HAS_ORGANIZATION]->(o))
} IN TRANSACTIONS OF 1000 ROWS