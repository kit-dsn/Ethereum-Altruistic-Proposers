import requests
import time
import logging
import argparse
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, String, BigInteger, Numeric, Float, Index
from sqlalchemy.dialects.postgresql import insert

argparser = argparse.ArgumentParser(
    prog="Download Relay Data",
    description="Downloads proposer_payload_delivered from relay API and stores results inside PSQL database"
)
argparser.add_argument('url')
argparser.add_argument('-d', '--database', default="postgresql://root@rfc.incus.tamedfox.eu/rfc")
argparser.add_argument('--start', type=int, default=11602798)
argparser.add_argument('table')

args = argparser.parse_args()

URL = args.url
DB = args.database
DB_TABLE = args.table

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
    metadata = MetaData()
    
    columns = []

    for col_name, dtype in slots.dtypes.items():
        if pd.api.types.is_integer_dtype(dtype):
            col_type = BigInteger
        elif pd.api.types.is_float_dtype(dtype):
            col_type = Float
        else:
            col_type = String

        if col_name == "slot":
            columns.append(Column(col_name, col_type, unique=True))
        elif col_name == "value":
            columns.append(Column(col_name, Numeric))
        else:
            columns.append(Column(col_name, col_type))
    
    table = Table(DB_TABLE, 
                  metadata, 
                  *columns, 
                  Index(f"ix_{DB_TABLE}_slot", "slot"),
                  Index(f"ix_{DB_TABLE}_block_number", "block_number")
        )
    
    engine = create_engine(DB)

    metadata.create_all(engine, checkfirst=True)

    with engine.begin() as conn:
        conn.execute(table.insert(), slots.to_dict('records'))


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