import pandas as pd
from neo4j import GraphDatabase
import yaml
import datetime
import sys
import gzip
from zipfile import ZipFile
from urllib.parse import urlparse
import boto3
from smart_open import open
import io
import pathlib
import ijson
import pyarrow
import awswrangler as wr

config = dict()
supported_compression_formats = ['gzip', 'zip', 'none']


class LocalServer(object):

    def __init__(self):
        self._driver = GraphDatabase.driver(config['server_uri'],
                                            auth=(config['admin_user'],
                                                  config['admin_pass']), encrypted=False)

    def close(self):
        self._driver.close()

    def load_file(self, file):
        # Set up parameters/defaults
        # Check skip_file first so we can exit early
        skip = file.get('skip_file') or False
        if skip:
            print("Skipping this file: {}", file['url'])
            return

        print("{} : Reading file", datetime.datetime.utcnow())

        # If file type is specified, use that.  Else check the extension.  Else, treat as csv
        type = file.get('type') or 'NA'
        if type != 'NA':
            if type == 'csv':
                self.load_csv(file)
            elif type == 'json':
                self.load_json(file)
            elif type == 'parquet':
                self.load_parquet(file)
            else:
                print("Error! Can't process file because unknown type", type, "was specified")
        else:
            file_suffixes = pathlib.Path(file['url']).suffixes
            if '.csv' in file_suffixes:
                self.load_csv(file)
            elif '.json' in file_suffixes:
                self.load_json(file)
            elif '.parquet' in file_suffixes:
                self.load_parquet(file)
            else:
                self.load_csv(file)

    # Tells ijson to return decimal number as float.  Otherwise, it wraps them in a Decimal object,
    # which angers the Neo4j driver
    @staticmethod
    def ijson_decimal_as_float(events):
        for prefix, event, value in events:
            if event == 'number':
                value = str(value)
            yield prefix, event, value

    def load_json(self, file):
        with self._driver.session() as session:
            params = self.get_params(file)
            openfile = file_handle(params['url'], params['compression'])
            # 'item' is a magic word in ijson.  It just means the next-level element of an array
            items = ijson.common.items(self.ijson_decimal_as_float(ijson.parse(openfile)), 'item')
            # Next, pool these into array of 'chunksize'
            halt = False
            rec_num = 0
            chunk_num = 0
            rows = []
            while not halt:
                row = next(items, None)
                if row is None:
                    halt = True
                else:
                    rec_num = rec_num + 1
                    if rec_num > params['skip_records']:
                        rows.append(row)
                        if len(rows) == params['chunk_size']:
                            print(file['url'], chunk_num, datetime.datetime.utcnow(), flush=True)
                            chunk_num = chunk_num + 1
                            rows_dict = {'rows': rows}
                            session.run(params['cql'], dict=rows_dict).consume()
                            rows = []

            if len(rows) > 0:
                print(file['url'], chunk_num, datetime.datetime.utcnow(), flush=True)
                rows_dict = {'rows': rows}
                session.run(params['cql'], dict=rows_dict).consume()

        print("{} : Completed file", datetime.datetime.utcnow())

    @staticmethod
    def get_params(file):
        params = dict()
        params['skip_records'] = file.get('skip_records') or 0
        params['compression'] = file.get('compression') or 'none'
        if params['compression'] not in supported_compression_formats:
            print("Unsupported compression format: {}", params['compression'])

        params['url'] = file['url']
        print("File {}", params['url'])
        params['cql'] = file['cql']
        params['chunk_size'] = file.get('chunk_size') or 1000
        params['field_sep'] = file.get('field_separator') or ','

        params['parquet_suffix_whitelist'] = file.get('parquet_suffix_whitelist') or None
        params['parquet_suffix_blacklist'] = file.get('parquet_suffix_blacklist') or None
        params['parquet_partition_filter'] = file.get('parquet_partition_filter') or None
        params['parquet_columns'] = file.get('parquet_columns') or None
        params['parquet_start_from_mod_date'] = file.get('parquet_start_from_mod_date') or None
        params['parquet_up_to_mod_date'] = file.get('parquet_up_to_mod_date') or None
        params['parquet_s3_additional_args'] = file.get('parquet_s3_additional_args') or None
        params['parquet_as_dataset'] = file.get('parquet_as_dataset') or False
        return params

    def load_csv(self, file):
        with self._driver.session() as session:
            params = self.get_params(file)
            openfile = file_handle(params['url'], params['compression'])

            # - The file interfaces should be consistent in Python but they aren't
            if params['compression'] == 'zip':
                header = openfile.readline().decode('UTF-8')
            else:
                header = str(openfile.readline())

            # Grab the header from the file and pass that to pandas.  This allow the header
            # to be applied even if we are skipping lines of the file
            header = header.strip().split(params['field_sep'])

            # Pandas' read_csv method is highly optimized and fast :-)
            row_chunks = pd.read_csv(openfile, dtype=str, sep=params['field_sep'], error_bad_lines=False,
                                     index_col=False, skiprows=params['skip_records'], names=header,
                                     low_memory=False, engine='c', compression='infer', header=None,
                                     chunksize=params['chunk_size'])

            for i, rows in enumerate(row_chunks):
                print(params['url'], i, datetime.datetime.utcnow(), flush=True)
                # Chunk up the rows to enable additional fastness :-)
                rows_dict = {'rows': rows.fillna(value="").to_dict('records')}
                session.run(params['cql'],
                            dict=rows_dict).consume()

        print("{} : Completed file", datetime.datetime.utcnow())

    def load_parquet(self, file):
        with self._driver.session() as session:
            params = self.get_params(file)
            path = file['url']
            chunksize = params['chunk_size']
            skiprows = params['skip_records']
            path_suffix = params['parquet_suffix_whitelist']
            path_ignore_suffix = params['parquet_suffix_blacklist']
            partition_filter = params['parquet_partition_filter']
            columns = params['parquet_columns']
            last_modified_begin = params['parquet_start_from_mod_date']
            last_modified_end = params['parquet_up_to_mod_date']
            s3_additional_kwargs = params['parquet_s3_additional_args']
            dataset = params['parquet_as_dataset']

            filter = None
            if partition_filter is not None:
                exec(partition_filter)
                filter = getattr(self, 'filter')

            collist =None
            if columns is not None :
                collist = []
                colsplit = columns.split(',')
                for x in colsplit:
                    collist.append(x.strip())
                print(collist)

            start_date = None
            if last_modified_begin is not None:
                start_date = datetime.datetime.strptime(last_modified_begin, "%m/%d/%y %H:%M:%S%z")

            end_date = None
            if last_modified_end is not None:
                end_date = datetime.datetime.strptime(last_modified_end, "%m/%d/%y %H:%M:%S%z")

            addl_args = None
            if s3_additional_kwargs is not None:
                addl_args = {}
                entries = s3_additional_kwargs.split(',')
                for e in entries:
                    kv = e.strip().split(':')
                    addl_args[kv[0]] = kv[1]

            print(addl_args)

            if path.upper().startswith('S3') :
                dfs = wr.s3.read_parquet(path=path, chunked=chunksize, path_suffix=path_suffix,
                                     path_ignore_suffix=path_ignore_suffix, partition_filter=filter,
                                     columns=collist, last_modified_begin=start_date,
                                     last_modified_end=end_date, s3_additional_kwargs=addl_args,
                                     dataset=dataset)
            else:
                dfs = [pd.read_parquet(path)]

            batchRows = 0
            totalRows = 0
            for df in dfs:

                batchRows += 1
                print(params['url'], batchRows, datetime.datetime.utcnow(), flush=True)
                iter = df.iterrows()
                chunk = []
                while True:
                    try:
                        row = next(iter)
                        print(row)
                        totalRows += 1
                        if totalRows > skiprows:
                            content = row[1]
                            content = content.fillna(value="")
                            content_dict = content.to_dict()
                            chunk.append(content_dict)

                    except StopIteration:
                        break
                dict = {'rows':chunk}
                print(dict)
                session.run(params['cql'], dict=dict).consume()

        print("{} : Completed file", datetime.datetime.utcnow())

    def pre_ingest(self):
        if 'pre_ingest' in config:
            statements = config['pre_ingest']

            with self._driver.session() as session:
                for statement in statements:
                    session.run(statement)

    def post_ingest(self):
        if 'post_ingest' in config:
            statements = config['post_ingest']

            with self._driver.session() as session:
                for statement in statements:
                    session.run(statement)


def file_handle(url, compression):
    parsed = urlparse(url)
    if parsed.scheme == 's3':
        path = get_s3_client().get_object(Bucket=parsed.netloc, Key=parsed.path[1:])['Body']
    elif parsed.scheme == 'file':
        path = parsed.path
    else:
        path = url
    if compression == 'gzip':
        return gzip.open(path, 'rt')
    elif compression == 'zip':
        # Only support single file in ZIP archive for now
        if isinstance(path, str):
            buffer = path
        else:
            buffer = io.BytesIO(path.read())
        zf = ZipFile(buffer)
        filename = zf.infolist()[0].filename
        return zf.open(filename)
    else:
        return open(path)


def get_s3_client():
    return boto3.Session().client('s3')


def load_config(configuration):
    global config
    with open(configuration) as config_file:
        config = yaml.SafeLoader(config_file).get_data()


def main():
    configuration = sys.argv[1]
    load_config(configuration)
    server = LocalServer()
    server.pre_ingest()
    file_list = config['files']
    for file in file_list:
        server.load_file(file)
    server.post_ingest()
    server.close()


if __name__ == "__main__":
    main()
