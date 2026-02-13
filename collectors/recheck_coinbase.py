"""
Purpose
    Validates stored slot numbers against fresh CL headers and records any
    mismatches for later correction.

Usage
    python3 collectors/recheck_coinbase.py -d <db> --start <n> --end <n> <table>

Outputs
    recheck_coinbase-results.json with block_number, saved, correct.
"""

import argparse
import requests
import logging
import pandas as pd
import time
import duckdb
from duckdb import sql

argparser = argparse.ArgumentParser(
    prog="Recheck coinbase data",
    description="Checks the slot numbers again"
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

    # this has been missing in download_coinbase.py
    for block in r.json()["data"]:
        if block["canonical"]:
            return block

def fetch_saved_slot(block_number):
    result = conn.execute(
        f"SELECT slot FROM {DB_TABLE} WHERE block_number = {block_number}"
    ).fetchall()
    
    if len(result) > 0:
        return result[0][0]
    return None
    

BLOCK_CURRENT = int(args.start)
BLOCK_MIN = int(args.end)

RESULTS = []

def check_block_number(block_number):
    el_header = fetch_el_header(block_number)
    cl_header = fetch_cl_header(el_header["parentBeaconBlockRoot"])

    correct = int(cl_header["header"]["message"]["slot"])
    saved = fetch_saved_slot(block_number)

    if correct != saved:
        logger.error(f"Block number {block_number} is wrong, saved {saved}, should be {correct}")
    
    RESULTS.append([block_number, saved, correct])


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

while BLOCK_CURRENT >= BLOCK_MIN:
    logger.info(f"Checking block {BLOCK_CURRENT}")
    check_block_number(BLOCK_CURRENT)
    BLOCK_CURRENT = BLOCK_CURRENT - 1

df = pd.DataFrame(data=RESULTS, columns=["block_number", "saved", "correct"])
df.set_index("block_number")
df.to_json('recheck_coinbase-results.json')