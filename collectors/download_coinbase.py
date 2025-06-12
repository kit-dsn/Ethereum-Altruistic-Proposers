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
argparser.add_argument('--start', default="22385293")
argparser.add_argument('table')

args = argparser.parse_args()

EL_API_BASE = "http://localhost:8545"
CL_API_BASE = "http://localhost:3500"

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