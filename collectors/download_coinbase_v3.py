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

def fetch_cl_headers(block_num):
    bnums = f"{block_num}"
    for i in range(1,100):
        bnums = bnums + f",{block_num + i}"
    
    r = requests.get(
        f"https://beaconcha.in/api/v1/execution/block/{bnums}",
        headers={"apikey": args.key}
    )
    data = r.json()["data"]
    return sorted(data, key=lambda el: el["blockNumber"])

def download_blocks(block_num):
    el_headers = []
    
    for i in range(100):
        el_headers.append(fetch_el_header(block_num + i))
    
    cl_headers = fetch_cl_headers(block_num)

    blocks = []
    for i in range(100):
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
    
    conn.insert(DB_TABLE, df)
    conn.commit()

BLOCK_CURRENT = int(args.start)
BLOCK_MIN = 21525891

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


while BLOCK_CURRENT >= BLOCK_MIN:
    logger.info(f"Downloading block {BLOCK_CURRENT}")
    bs = download_blocks(BLOCK_CURRENT)
    upload_data(bs)
    BLOCK_CURRENT = BLOCK_CURRENT - len(bs)
