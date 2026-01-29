"""
    Problem:
# curl localhost:3500/eth/v1/beacon/headers?parent_root=0x7417497b58b0cd2e0e5f77736f6554ad7744d485b3ca175b247bbf3cfb86d62f | jq
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  1292  100  1292    0     0  52103      0 --:--:-- --:--:-- --:--:-- 53833
{
  "data": [
    {
      "header": {
        "message": {
          "slot": "11052946",
          "proposer_index": "799107",
          "parent_root": "0x7417497b58b0cd2e0e5f77736f6554ad7744d485b3ca175b247bbf3cfb86d62f",
          "state_root": "0xd8acd133308d196a21505275b84920d062552b1d9004c439db8340cfdd52d963",
          "body_root": "0xf1aef64a0ad2d59e56f281eb4788c09ba45c1dde5f68ca3defd6f3cf0296868f"
        },
        "signature": "0x91672cfaad5014adf5c27feae2d599993160953a2afdfa46c5db4565e3e9d7231e5c11591fd8161a0244fd04aa1378e10e25c01dd128aa5e39dc4f0853fbaf7d9dec5143a69b393fd22711e940d88749d4dbf6f3599eda4922e95851352870aa"
      },
      "root": "0xe14c45149a589accb748eac323517c02d251bd11bd75dd5e2b579f23980a895b",
      "canonical": false
    },
    {
      "header": {
        "message": {
          "slot": "11052947",
          "proposer_index": "560319",
          "parent_root": "0x7417497b58b0cd2e0e5f77736f6554ad7744d485b3ca175b247bbf3cfb86d62f",
          "state_root": "0xff818bcba505f6ba9efee1aaa9e859c16b1c5d9f29e49a38848f595406c125a5",
          "body_root": "0xf08f5f1421154cf1058e5485a15b200fe652edc9f4eac574b6560cc399ddcada"
        },
        "signature": "0x917e9a67027d062ea1718906dc44b8a72dfba2084c307154f7ead8fc42c570b5882a994b682d55fb80b5f20a27aee22208e4ae706e74b0bf5920e0253165f68d14e53e66314a84ddecf8dc13c535b6421c2b3ef533e550114f3ed3250dfb7ee1"
      },
      "root": "0xaf185f330afc57274f793a9db8901e342b9802bf29ee3da53118e03f514962ca",
      "canonical": true
    }
  ],
  "execution_optimistic": true,
  "finalized": false
}

-> we fetched the wrong slot number from the Beacon API...

Example: SELECT slot FROM coinbase_blocks WHERE block_number = 21838359;
=> 11052946 (WRONG, should be 11052947)

Let's go through all of them again...
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
argparser.add_argument('--start', default="22385293")
argparser.add_argument('table')

args = argparser.parse_args()

EL_API_BASE = "http://localhost:8504"
CL_API_BASE = "http://localhost:3500"

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
BLOCK_MIN = 21767881

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