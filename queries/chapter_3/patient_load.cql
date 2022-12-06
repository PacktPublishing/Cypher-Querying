:auto LOAD CSV WITH HEADERS from "https://raw.githubusercontent.com/PacktPublishing/Cypher-Querying/main/data/csv/patients.csv" as row
CALL {
  WITH row
  MERGE(p:Patient {id: row.Id})
  SET
  p.marital = row.MARITAL,
  p.ssn = row.SSN,
  p.firstName = row.FIRST,
  p.lastName = row.LAST,
  p.suffix = row.SUFFIX,
  p.prefix = row.PREFIX,
  p.city = row.CITY,
  p.county = row.COUNTY,
  p.location = point({latitude:toFloat(row.LAT),
                      longitude:toFloat(row.LON)}),
  p.drivers=row.DRIVERS,
  p.birthDate=date(row.BIRTHDATE)
  WITH row,p
  MERGE (r:Race {type: row.RACE})
  MERGE (p)-[:HAS_RACE]->(r)
  WITH row,p
  MERGE (e:Ethnicity {type: row.ETHNICITY})
  MERGE (p)-[:HAS_ETHNICITY]->(e)
  WITH row,p
    WHERE row.ZIP IS NOT NULL
  MERGE (z:ZipCode {zip: row.ZIP})
  MERGE (p)-[:HAS_ZIPCODE]->(z)
} IN TRANSACTIONS OF 1000 ROWS
