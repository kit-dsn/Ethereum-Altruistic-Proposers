"""
Purpose
    Collects proposer_payload_delivered traces from a relay API and stores
    them in DuckDB for PBS analyses.

Usage
    python3 collectors/download_relay_data.py <relay_url> -d <db> --start <slot> --end <slot> <table>

Notes
    Implements retry-on-failure with backoff. Data are inserted incrementally
    to allow long-range collection runs.

Relay providers queried in this study:
    - https://aestus.live
    - https://agnostic-relay.net
    - https://bloxroute.max-profit.blxrbdn.com
    - https://bloxroute.regulated.blxrbdn.com
    - https://boost-relay.flashbots.net
    - https://titanrelay.xyz
    - https://relay-analytics.ultrasound.money
    - https://relay.ethgas.com
"""

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
argparser.add_argument('-d', '--database', default="/data/fast/historical_mempools/altruistic_proposers/q4.duckdb")
argparser.add_argument('--start', type=int, default=13366798)
argparser.add_argument('--end', type=int, default=12704399)
argparser.add_argument('table')

args = argparser.parse_args()

URL = args.url
DB = args.database
DB_TABLE = args.table
TARGET_TABLE = "relay_payloads" if DB_TABLE == "relay_all" else DB_TABLE

conn = duckdb.connect(DB)

if DB_TABLE == "relay_all":
    logging.warning("relay_all is treated as a derived view; writing raw relay rows into relay_payloads instead")

# Create table if it doesn't exist
conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
        relay_url VARCHAR,
        slot BIGINT,
        block_number BIGINT,
        block_hash VARCHAR,
        builder_pk VARCHAR,
        proposer_pk VARCHAR,
        proposer_fee_recipient VARCHAR,
        gas_limit BIGINT,
        gas_used BIGINT,
        value HUGEINT,
        num_tx INTEGER
    )
""")

def query_payloads(idx_slot, relay, limit):
    while True:
        try:
            r = requests.get(f"{relay}/relay/v1/data/bidtraces/proposer_payload_delivered?cursor={idx_slot}&limit={limit}")

            slots = []
            for s in r.json():
                slots.append({
                    "relay_url": relay,
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
    # Insert data using SQL
    conn.register("slots_upload", slots[[
        "relay_url",
        "slot",
        "block_number",
        "block_hash",
        "builder_pk",
        "proposer_pk",
        "proposer_fee_recipient",
        "gas_limit",
        "gas_used",
        "value",
        "num_tx",
    ]])
    conn.execute(f"""
        INSERT INTO {TARGET_TABLE} (
            relay_url,
            slot,
            block_number,
            block_hash,
            builder_pk,
            proposer_pk,
            proposer_fee_recipient,
            gas_limit,
            gas_used,
            value,
            num_tx
        )
        SELECT
            relay_url,
            slot,
            block_number,
            block_hash,
            builder_pk,
            proposer_pk,
            proposer_fee_recipient,
            gas_limit,
            gas_used,
            value,
            num_tx
        FROM slots_upload
    """)


SLOT_CURRENT = args.start
SLOT_MIN = args.end

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
    time.sleep(0.5)