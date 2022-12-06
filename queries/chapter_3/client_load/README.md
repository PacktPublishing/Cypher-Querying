# pyingest
A script for loading CSV and JSON files into a Neo4j database written in Python3.  It performs well due to several factors:
* Records are grouped into configurable-sized chunks before ingest
* For CSV files, we leverage the optimized CSV parsing capabilities of the Pandas library
* For JSON files, we use a streaming JSON parser (ijson) to avoid reading the entire document into memory

## Installation
* You will need to have Python 3 and compatible version of Pip installed.
* Then run `pip3 install -r requirements.txt` to obtain dependencies
* If you do not have a yaml module installed, you may need to run `pip3 install pyyaml`

## Usage
`python3 ingest.py config.yml

This script will load all the files one by one in sequence the files are specified.
This makes is easy to load batches of data and can be restarted as needed. 

## Reference

https://github.com/neo4j-field/pyingest

