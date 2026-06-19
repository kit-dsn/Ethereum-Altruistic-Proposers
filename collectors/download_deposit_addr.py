"""
Purpose
    Resolves validator deposit metadata and maps public keys to proposer
    indices, then stores the results in DuckDB.

Usage
    python3 collectors/download_deposit_addr.py -d <db> --key <api_key> <table>

Notes
    Requires a beaconcha.in API key and a local CL endpoint for validator
    pubkeys. Validators are processed in chunks to respect API limits.
    Reads its list of validators straight out of coinbase_blocks_all
    (DISTINCT proposer_index), so coinbase data has to be loaded into the
    target database before this can run. proposer_deposit.py is the
    consumer: it compares each proposer's deposit from_address against the
    coinbase address(es) it later built blocks with.
"""

import argparse
import logging
import time

import pandas as pd
import requests
import duckdb

argparser = argparse.ArgumentParser(
    prog="Download coinbase data",
    description="Downloads the coinbase addr of blocks from geth/prism"
)
argparser.add_argument('-d', '--database', default="/data/fast/historical_mempools/altruistic_proposers/q4.duckdb")
argparser.add_argument('--key', help="beaconchain api key")
argparser.add_argument('--chunk-size', type=int, default=100)
argparser.add_argument('--deposit-delay', type=float, default=1.0)
argparser.add_argument('table')

args = argparser.parse_args()

DB = args.database
DB_TABLE = args.table
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
DEPOSIT_CHUNK_SIZE = args.chunk_size
DEPOSIT_DELAY = args.deposit_delay

conn = duckdb.connect(DB)

CL_API_BASE = "http://localhost:5052"
BEACONCHAIN_API_BASE = "https://beaconcha.in/api/v1"
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
last_beaconchain_request_at = None


def maybe_sleep_for_beaconchain_rate_limit(url):
    global last_beaconchain_request_at

    if not url.startswith(BEACONCHAIN_API_BASE) or last_beaconchain_request_at is None:
        return

    elapsed = time.monotonic() - last_beaconchain_request_at
    if elapsed >= DEPOSIT_DELAY:
        return

    wait_seconds = DEPOSIT_DELAY - elapsed
    logger.info("Sleeping %.2fs before next beaconcha.in request", wait_seconds)
    time.sleep(wait_seconds)


def mark_beaconchain_request(url):
    global last_beaconchain_request_at

    if url.startswith(BEACONCHAIN_API_BASE):
        last_beaconchain_request_at = time.monotonic()


def get_retry_delay(response, attempt):
    return DEPOSIT_DELAY


def get_json(url, headers=None):
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        response = None
        try:
            maybe_sleep_for_beaconchain_rate_limit(url)
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            mark_beaconchain_request(url)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            wait_seconds = get_retry_delay(response, attempt)
            body_preview = ""
            if response is not None:
                body_preview = response.text[:200].replace("\n", " ")
            logger.warning(
                "Request failed for %s (attempt %s/%s): %s. Response preview: %r. Retrying in %ss",
                url,
                attempt,
                MAX_RETRIES,
                exc,
                body_preview,
                wait_seconds,
            )
            time.sleep(wait_seconds)

    raise RuntimeError(f"Failed to fetch JSON from {url} after {MAX_RETRIES} attempts") from last_error

def fetch_deposits(validator_list):
    assert len(validator_list) <= DEPOSIT_CHUNK_SIZE

    v = ",".join(pd.Series(validator_list).apply(str))

    payload = get_json(
        f"{BEACONCHAIN_API_BASE}/validator/{v}/deposits",
        headers={"apikey": args.key}
    )
    return payload["data"]

def fetch_validator_pubkey(validator_idx):
    payload = get_json(
        f"{CL_API_BASE}/eth/v1/beacon/states/head/validators/{validator_idx}",
    )
    data = payload["data"]

    assert data["index"] == str(validator_idx)
    return data["validator"]["pubkey"]

def fetch_chunk(validator_list):
    assert len(validator_list) <= DEPOSIT_CHUNK_SIZE

    pubkey_to_idx = {}
    for vix in validator_list:
        pubkey_to_idx[fetch_validator_pubkey(vix)] = vix
    
    deposits = fetch_deposits(validator_list)
    deposits = pd.DataFrame(deposits).drop(['merkletree_index', 'signature'], axis=1)
    deposits['proposer_index'] = deposits['publickey'].apply(lambda x: pubkey_to_idx[x])

    return deposits

def upload_data(df):
    # Create table if it doesn't exist
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {DB_TABLE} AS SELECT * FROM df WHERE FALSE")
    except:
        pass
    
    # Insert data using SQL
    conn.execute(f"INSERT INTO {DB_TABLE} SELECT * FROM df")
    logger.info("Inserted %s rows into %s", len(df), DB_TABLE)
 


# load all proposer idx
proposer_idx = conn.execute(f'''SELECT DISTINCT proposer_index FROM coinbase_blocks_all;''').df()

# https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

for chunk in chunks(list(proposer_idx['proposer_index']), DEPOSIT_CHUNK_SIZE):
    logger.info("Loading chunk with validators %s (size=%s)", chunk[0], len(chunk))
    df = fetch_chunk(chunk)
    logger.info("Fetched %s deposit rows for chunk starting with validator %s", len(df), chunk[0])
    upload_data(df)