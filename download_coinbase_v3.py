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
argparser.add_argument('--start', default="21767881")
argparser.add_argument('table')

args = argparser.parse_args()

EL_API_BASE = "http://localhost:8545"
CL_API_BASE = "https://ethereum-beacon-api.publicnode.com"

DB = args.database
DB_TABLE = args.table

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
    metadata = MetaData()
    
    columns = []

    for col_name, dtype in df.dtypes.items():
        if pd.api.types.is_integer_dtype(dtype):
            col_type = BigInteger
        elif pd.api.types.is_float_dtype(dtype):
            col_type = Float
        else:
            col_type = String

        if col_name == "slot":
            columns.append(Column(col_name, col_type, unique=True))
        elif col_name == "block_number":
            columns.append(Column(col_name, col_type, unique=True))
        else:
            columns.append(Column(col_name, col_type))
    
    table = Table(DB_TABLE, 
                  metadata, 
                  *columns, 
                  Index(f"ix_{DB_TABLE}_slot", "slot"),
                  Index(f"ix_{DB_TABLE}_block_number", "block_number"),
                  Index(f"ix_{DB_TABLE}_coinbase_addr", "coinbase_addr")
        )
    
    engine = create_engine(DB)
    metadata.create_all(engine, checkfirst=True)

    with engine.begin() as conn:
        conn.execute(table.insert(), df.to_dict('records'))

BLOCK_CURRENT = int(args.start)
BLOCK_MIN = 21525891

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


while BLOCK_CURRENT >= BLOCK_MIN:
    logger.info(f"Downloading block {BLOCK_CURRENT}")
    bs = download_blocks(BLOCK_CURRENT)
    upload_data(bs)
    BLOCK_CURRENT = BLOCK_CURRENT - len(bs)
