:auto LOAD CSV WITH HEADERS from "https://raw.githubusercontent.com/PacktPublishing/Cypher-Querying/main/data/csv/organizations.csv" as row
CALL {
  WITH row
    MERGE (o:Organization {id: row.Id})
    SET o.name=row.NAME,
    o.address = row.ADDRESS,
    o.state = row.STATE,
    o.location = point({latitude:toFloat(row.LAT),
                        longitude:toFloat(row.LON)})
    WITH row,o
      WHERE row.ZIP IS NOT NULL
    MERGE (z:ZipCode {zip: row.ZIP})
    MERGE (o)-[:HAS_ZIPCODE]->(z)
} IN TRANSACTIONS OF 1000 ROWS