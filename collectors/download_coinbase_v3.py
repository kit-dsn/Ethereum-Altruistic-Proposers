"""
Purpose
    Downloads coinbase address and proposer metadata in 100-block batches
    using EL headers and the beaconcha.in execution-to-consensus mapping.

Usage
    python3 collectors/download_coinbase_v3.py -d <db> --key <api_key> --start <n> --end <n> <table>

Notes
    Requires a beaconcha.in API key. Where download_coinbase_v2.py spends a
    CL round-trip per block, this batches 100 blocks into a single
    beaconcha.in /execution/block/{ids} lookup, then cross-checks each
    result's block number/hash against the EL header before trusting it.
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
argparser.add_argument('--key', help="beaconchain api key")
argparser.add_argument('--start', type=int, default=24130000)
argparser.add_argument('--end', type=int, default=23920000)
argparser.add_argument('table')

args = argparser.parse_args()

EL_API_BASE = "http://localhost:8504"
CL_API_BASE = "https://ethereum-beacon-api.publicnode.com"

DB = args.database
DB_TABLE = args.table
BATCH_SIZE = 100

if args.start < args.end:
    argparser.error("--start must be greater than or equal to --end")

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

def fetch_cl_headers(block_numbers):
    bnums = ",".join(str(block_num) for block_num in block_numbers)

    r = requests.get(
        f"https://beaconcha.in/api/v1/execution/block/{bnums}",
        headers={"apikey": args.key}
    )
    time.sleep(1)
    
    if r.status_code != 200:
        logger.error(f"API error: {r.status_code} - {r.text}")
        raise Exception(f"API returned status {r.status_code}: {r.text}")
    
    try:
        data = r.json()["data"]
        return sorted(data, key=lambda el: el["blockNumber"])
    except KeyError as e:
        logger.error(f"Invalid API response: {r.text}")
        raise Exception(f"Invalid API response structure: {e}")

def download_blocks(block_num):
    block_numbers = list(range(max(BLOCK_MIN, block_num - BATCH_SIZE + 1), block_num + 1))
    el_headers = [fetch_el_header(number) for number in block_numbers]
    cl_headers = fetch_cl_headers(block_numbers)

    blocks = []
    for i in range(len(block_numbers)):
        assert cl_headers[i]["blockNumber"] == int(el_headers[i]["number"], 16)
        assert cl_headers[i]["blockHash"] == el_headers[i]["hash"]

        blocks.append({
            "slot": int(cl_headers[i]["posConsensus"]["slot"]),
            "proposer_index": int(cl_headers[i]["posConsensus"]["proposerIndex"]),
            "coinbase_addr": el_headers[i]["miner"],
            "block_number": int(el_headers[i]["number"], 16),
            "block_hash": el_headers[i]["hash"],
            "extra_data": el_headers[i]["extraData"]
        })
    
    return blocks

def upload_data(blocks):
    df = pd.DataFrame(blocks)
    
    # Create table if it doesn't exist
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {DB_TABLE} AS SELECT * FROM df WHERE FALSE")
    except:
        pass
    
    # Insert data using SQL
    conn.execute(f"INSERT INTO {DB_TABLE} SELECT * FROM df")

BLOCK_CURRENT = args.start
BLOCK_MIN = args.end

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


while BLOCK_CURRENT >= BLOCK_MIN:
    logger.info(f"Downloading block {BLOCK_CURRENT}")
    bs = download_blocks(BLOCK_CURRENT)
    upload_data(bs)
    BLOCK_CURRENT = BLOCK_CURRENT - len(bs)
