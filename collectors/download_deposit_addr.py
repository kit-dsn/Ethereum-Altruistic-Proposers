import argparse
import requests
import logging
import pandas as pd
import time
from sqlalchemy import create_engine, MetaData, Table, Column, String, BigInteger, Numeric, Float, Index
from sqlalchemy.dialects.postgresql import insert

argparser = argparse.ArgumentParser(
    prog="Download coinbase data",
    description="Downloads the coinbase addr of blocks from geth/prism"
)
argparser.add_argument('-d', '--database', default="postgresql://root@rfc.incus.tamedfox.eu/rfc")
argparser.add_argument('--key', help="beaconchain api key")
argparser.add_argument('table')

args = argparser.parse_args()

DB = args.database
DB_TABLE = args.table

CL_API_BASE = "http://localhost:3500"

def fetch_deposits(validator_list):
    assert len(validator_list) <= 100

    v = ",".join(pd.Series(validator_list).apply(str))
    
    r = requests.get(
        f"https://beaconcha.in/api/v1/validator/{v}/deposits",
        headers={"apikey": args.key}
    )
    
    return r.json()["data"]

def fetch_validator_pubkey(validator_idx):
    r = requests.get(
        f"{CL_API_BASE}/eth/v1/beacon/states/head/validators/{validator_idx}",
    )
    data = r.json()["data"]

    assert data["index"] == str(validator_idx)
    return data["validator"]["pubkey"]

def fetch_chunk(validator_list):
    assert len(validator_list) <= 100

    pubkey_to_idx = {}
    for vix in validator_list:
        pubkey_to_idx[fetch_validator_pubkey(vix)] = vix
    
    deposits = fetch_deposits(validator_list)
    deposits = pd.DataFrame(deposits).drop(['merkletree_index', 'signature'], axis=1)
    deposits['proposer_index'] = deposits['publickey'].apply(lambda x: pubkey_to_idx[x])

    return deposits

def upload_data(df):
    columns = []
    metadata = MetaData()

    for col_name, dtype in df.dtypes.items():
        if pd.api.types.is_integer_dtype(dtype):
            col_type = BigInteger
        elif pd.api.types.is_float_dtype(dtype):
            col_type = Float
        else:
            col_type = String

        columns.append(Column(col_name, col_type))

    table = Table(DB_TABLE, 
                  metadata, 
                  *columns, 
                  Index(f"ix_{DB_TABLE}_proposer_index", "proposer_index"),
                  Index(f"ix_{DB_TABLE}_block_number", "block_number")
        )

    engine = create_engine(DB)
    metadata.create_all(engine, checkfirst=True)

    with engine.begin() as conn:
        conn.execute(table.insert(), df.to_dict('records'))
 


# load all proposer idx
engine = create_engine(DB)
with engine.connect() as connection:
    proposer_idx = pd.read_sql(f'''SELECT DISTINCT proposer_index FROM coinbase_blocks_all;''', connection)

# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

for chunk in chunks(list(proposer_idx['proposer_index']), 100):
    print(f"Loading chunk with validators {chunk[0]}...")
    df = fetch_chunk(chunk)
    upload_data(df)