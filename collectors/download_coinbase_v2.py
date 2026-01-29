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
argparser.add_argument('--start', default="21767881")
argparser.add_argument('table')

args = argparser.parse_args()

EL_API_BASE = "http://localhost:8504"
CL_API_BASE = "https://ethereum-beacon-api.publicnode.com"

DB = args.database
DB_TABLE = args.table

conn = duckdb.connect(DB)

def fetch_el_header(block_num):
    r = requests.post(
        EL_API_BASE,
        json={
            "method": "eth_getBlockByNumber",
            "jsonrpc": "2.0",
            "id": 67,
            "params": [hex(block_num), False]
        }
    )
    return r.json()["result"]

def fetch_cl_header(prev_beacon_root, block_num, extra_data):
    r = requests.get(
        f"{CL_API_BASE}/eth/v1/beacon/headers?parent_root={prev_beacon_root}"
    )
    
    root = r.json()["data"][0]["root"]

    # just to be sure, let us check the extra_data to be confident enough
    # that this is the correct block
    r_check = requests.get(
        f"{CL_API_BASE}/eth/v1/beacon/blocks/{root}"
    ).json()

    assert r_check["data"]["message"]["body"]["execution_payload"]["extra_data"] == extra_data
    assert int(r_check["data"]["message"]["body"]["execution_payload"]["block_number"]) == block_num

    return r.json()["data"][0]

def download_block(block_num):
    el_header = fetch_el_header(block_num)
    cl_header = fetch_cl_header(
        el_header["parentBeaconBlockRoot"],
        int(el_header["number"], 16),
        el_header["extraData"]
    )

    return {
        "slot": int(cl_header["header"]["message"]["slot"]),
        "proposer_index": int(cl_header["header"]["message"]["proposer_index"]),
        "coinbase_addr": el_header["miner"],
        "block_number": int(el_header["number"], 16),
        "block_hash": el_header["hash"],
        "extra_data": el_header["extraData"]
    }

def upload_data(blocks):
    df = pd.DataFrame(blocks)
    
    # Create table if it doesn't exist
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {DB_TABLE} AS SELECT * FROM df WHERE FALSE")
    except:
        pass
    
    conn.insert(DB_TABLE, df)
    conn.commit()

BLOCK_CURRENT = int(args.start)
BLOCK_MIN = 21525891

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


block_buffer = []
while BLOCK_CURRENT >= BLOCK_MIN:
    logger.info(f"Downloading block {BLOCK_CURRENT}")
    b = download_block(BLOCK_CURRENT)
    block_buffer.append(b)

    if len(block_buffer) > 100:
        logger.info("Uploading blocks to database...")
        upload_data(block_buffer)
        block_buffer = []

    BLOCK_CURRENT = BLOCK_CURRENT - 1

if len(block_buffer) > 0:
    upload_data(block_buffer)