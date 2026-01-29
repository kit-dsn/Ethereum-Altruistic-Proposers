import requests
import time
import logging
import argparse
import pandas as pd
import duckdb

argparser = argparse.ArgumentParser(
    prog="Download Relay Data",
    description="Downloads proposer_payload_delivered from relay API and stores results inside DuckDB database"
)
argparser.add_argument('url')
argparser.add_argument('-d', '--database', default="/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb")
argparser.add_argument('--start', type=int, default=11602798)
argparser.add_argument('table')

args = argparser.parse_args()

URL = args.url
DB = args.database
DB_TABLE = args.table

conn = duckdb.connect(DB)

def query_payloads(idx_slot, relay, limit):
    while True:
        try:
            r = requests.get(f"{relay}/relay/v1/data/bidtraces/proposer_payload_delivered?cursor={idx_slot}&limit={limit}")

            slots = []
            for s in r.json():
                slots.append({
                    "slot": int(s["slot"]),
                    "block_number": int(s["block_number"]),
                    "block_hash": s["parent_hash"],
                    "builder_pk": s["builder_pubkey"],
                    "proposer_pk": s["proposer_pubkey"],
                    "proposer_fee_recipient": s["proposer_fee_recipient"],
                    "gas_limit": int(s["gas_limit"]),
                    "gas_used": int(s["gas_used"]),
                    "value": int(s["value"]),
                    "num_tx": int(s["num_tx"])
            })
            break
        except:
            time.sleep(60)

    df = pd.DataFrame(slots)
    return df

def upload_data(slots):
    # Create table if it doesn't exist
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {DB_TABLE} AS SELECT * FROM slots WHERE FALSE")
    except:
        pass
    
    conn.insert(DB_TABLE, slots)
    conn.commit()


SLOT_CURRENT = args.start
SLOT_MIN = 10738799

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')


while SLOT_CURRENT > SLOT_MIN:
    logger.info(f"Downloading at slot {SLOT_CURRENT}")
    slots = query_payloads(SLOT_CURRENT, URL, 100)
    SLOT_CURRENT = slots["slot"].min() - 1
    logger.info(f"Downloaded {len(slots.index)} blocks")
    logger.info(f"Set current slot {SLOT_CURRENT}")
    upload_data(slots)
    logger.info(f"Dataset uploaded to database...")
    time.sleep(10)