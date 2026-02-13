"""
Purpose
    Downloads coinbase address and proposer metadata by combining EL block
    headers with local CL header data, then stores results in DuckDB.

Usage
    python3 collectors/download_coinbase.py -d <db> --start <n> --end <n> <table>

Notes
    Expects local EL and CL endpoints. Blocks are buffered and uploaded in
    batches to reduce database overhead.
"""

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
argparser.add_argument('--start', default="24130000")
argparser.add_argument('--end', default="23920000")
argparser.add_argument('table')

args = argparser.parse_args()

EL_API_BASE = "http://localhost:8504"
CL_API_BASE = "http://localhost:5052"

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

def fetch_cl_header(prev_beacon_root):
    r = requests.get(
        f"{CL_API_BASE}/eth/v1/beacon/headers?parent_root={prev_beacon_root}"
    )

    return r.json()["data"][0]

def download_block(block_num):
    el_header = fetch_el_header(block_num)
    cl_header = fetch_cl_header(el_header["parentBeaconBlockRoot"])

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
    
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {DB_TABLE} AS SELECT * FROM df WHERE FALSE")
    except:
        pass
    
    conn.execute(f"INSERT INTO {DB_TABLE} SELECT * FROM df")

BLOCK_CURRENT = int(args.start)
BLOCK_MIN = int(args.end)

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