import argparse
import requests
import logging
import pandas as pd
import time
import duckdb

argparser = argparse.ArgumentParser(
    prog="Download coinbase data",
    description="Downloads the coinbase addr of blocks from geth/prism"
)
argparser.add_argument('-d', '--database', default="/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb")
argparser.add_argument('--key', help="beaconchain api key")
argparser.add_argument('table')

args = argparser.parse_args()

DB = args.database
DB_TABLE = args.table

conn = duckdb.connect(DB)

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
    # Create table if it doesn't exist
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {DB_TABLE} AS SELECT * FROM df WHERE FALSE")
    except:
        pass
    
    conn.insert(DB_TABLE, df)
    conn.commit()
 


# load all proposer idx
proposer_idx = conn.execute(f'''SELECT DISTINCT proposer_index FROM coinbase_blocks_all;''').df()

# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

for chunk in chunks(list(proposer_idx['proposer_index']), 100):
    print(f"Loading chunk with validators {chunk[0]}...")
    df = fetch_chunk(chunk)
    upload_data(df)