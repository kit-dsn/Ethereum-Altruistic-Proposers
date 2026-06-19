"""
Purpose
    Re-downloads a subset of blocks with known slot mismatches and writes a
    corrected table for migration purposes.

Inputs
    - out/recheck_coinbase-results.json (recheck_coinbase.py writes this
      file to the working directory, not out/ - move/copy it there first)
    - DuckDB with a coinbase_blocks table (the older, pre-"_all" name)

Usage
    python3 collectors/recheck_coinbase_migrate.py

Notes
    Uses local EL/CL endpoints; cached JSON output is reused if present.
    One-off migration tool tied to a specific past data-quality fix: the
    corrected rows land in a new coinbase_blocks_fixed table, which then has
    to be merged into coinbase_blocks_all by hand.
"""

import pandas as pd
import duckdb
import requests
import os


CL_API_BASE = "http://localhost:5052"
EL_API_BASE = "http://localhost:8504"
DB = "/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb"


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

conn = duckdb.connect(DB)

df = pd.read_json('out/recheck_coinbase-results.json')
select_statement = ','.join(df[df.saved != df.correct]['block_number'].apply(str))

database = conn.execute(f'''SELECT * FROM coinbase_blocks WHERE block_number IN ({select_statement})''').df()

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

if not os.path.exists('out/recheck_coinbase_migrate.json'):
    database = database.merge(df, left_on='block_number', right_on='block_number')

    RESULTS = []
    for block_number in database['block_number']:
        print(block_number)
        RESULTS.append(download_block(block_number))

    results = pd.DataFrame(RESULTS)
    results.to_json('out/recheck_coinbase_migrate.json')
else:
    results = pd.read_json('out/recheck_coinbase_migrate.json')

try:
    conn.execute("CREATE TABLE IF NOT EXISTS coinbase_blocks_fixed AS SELECT * FROM results WHERE FALSE")
except:
    pass

conn.execute("INSERT INTO coinbase_blocks_fixed SELECT * FROM results")