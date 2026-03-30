"""
Purpose
    Computes block-level ordering and privacy indicators for non-relaying
    proposer clusters and stores the results in DuckDB for downstream
    analysis.

Inputs
    - DuckDB with mempool and coinbase tables.
    - JSON files in out/ describing non-relaying clusters.
    - Execution-layer RPC at http://localhost:8504.
Notes
    Fail-fast assertions ensure data consistency between cluster metadata
    and observed coinbase blocks.
"""

import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, UTC
import duckdb
from itertools import chain
from scipy.stats import spearmanr, kendalltau
import argparse
import warnings
import time
import logging
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

argparser = argparse.ArgumentParser(
    prog="Analyse blocks",
)
argparser.add_argument('-d', '--database', default="/data/fast/historical_mempools/altruistic_proposers/q3.duckdb")
argparser.add_argument('-t', '--table', default="analyse_blocks")
argparser.add_argument('-s', '--start', default="1")
argparser.add_argument('-o', '--output-json', default="collectors/calc_block_statistics/analyze-all.json")

args = argparser.parse_args()

EL_API_BASE = "http://localhost:8504"
DB_TABLE = args.table

logger.info(f"Starting block statistics calculation")
logger.info(f"Database: {args.database}")
logger.info(f"Table: {args.table}")
logger.info(f"EL RPC: {EL_API_BASE}")
logger.info(f"Starting from cluster: {args.start}")
logger.info(f"JSON output: {args.output_json}")

conn = duckdb.connect(args.database)
def query(sql):
    return conn.execute(sql).df()

# get clusters
with open("out/coinbase_clusters-non-relaying-clusters.json") as file:
    non_relaying_clusters = json.load(file)

with open("out/coinbase_clusters-non-relaying-proposer-coinbase.json") as file:
    clusters_data = json.load(file)
    # Convert proposer_index dict to list indexed by cluster index
    proposer_index_dict = clusters_data.get('proposer_index', {})
    non_relaying_clusters_proposer = [
        [proposer_index_dict.get(str(i))] 
        for i in range(len(non_relaying_clusters))
    ]

non_relaying_proposer_coinbases = pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')

def fetch_block_numbers(coinbase_addrs, proposer_idxs):
    # Filter to only blocks with the expected coinbase addresses
    q = query(f"""
        SELECT DISTINCT block_number, coinbase_addr FROM coinbase_blocks_all
        WHERE coinbase_addr IN ({','.join([f"'{x}'" for x in coinbase_addrs])})
    """)
    
    logger.debug(f"Query found {len(q)} blocks for coinbase addresses: {coinbase_addrs}")
    return list(q['block_number'])

def get_control_count(coinbase_addrs, proposer_idxs):
    return non_relaying_proposer_coinbases[
        non_relaying_proposer_coinbases['coinbase_addr'].isin(coinbase_addrs)
    ]['count'].sum()

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
    result = r.json()["result"]
    if result:
        logger.info(f"✓ EL RPC: Retrieved block header for block {block_num}")
    else:
        logger.warning(f"✗ EL RPC: No data for block {block_num}")
    return result

def fetch_transaction(tx_hash):
    r = requests.post(
        EL_API_BASE,
        json={
            "method": "eth_getTransactionByHash",
            "jsonrpc": "2.0",
            "id": 67,
            "params": [tx_hash]
        }
    )
    return r.json()["result"]

def get_transactions(block_number):
    header = fetch_el_header(block_number)
    
    if not header:
        logger.error(f"✗ EL RPC: Failed to fetch header for block {block_number}")
        raise Exception(f"Failed to fetch block {block_number} from EL RPC")
    
    txs = []
    for tx_hash in header['transactions']:
        txs.append(fetch_transaction(tx_hash))
    
    logger.info(f"✓ EL RPC: Successfully retrieved {len(txs)} transactions for block {block_number}")
    return txs, header

def is_ascending(lst):
    for i in range(len(lst) - 1):
        if lst[i] > lst[i + 1]:
            return False
    return True

def is_descending(lst):
    for i in range(len(lst) - 1):
        if lst[i] < lst[i + 1]:
            return False
    return True


def analyse_block(block_number, txs, block_header):
    assert block_number == int(block_header['number'], 16)
    
    # does the block have private transactions
    private_txs = query(f"""
        SELECT DISTINCT txn_hash FROM mempool_private
        WHERE block_number = {block_number};
    """)
    private_txs = private_txs[private_txs['txn_hash'].isin([x['hash'] for x in txs])]

    # is the gas linear = ascending/decending?
    gas_prices = [int(x['gasPrice'],16) for x in txs]
    ascending = is_ascending(gas_prices)
    decending = is_descending(gas_prices)

    # are the timestamps ascending/decending?
    timestamps = []
    try:
        tx_obs = query(f"""
            SELECT txn_hash, MIN(time_seen) as time FROM mempool_txobs2
            WHERE block_number = {block_number}
            GROUP BY txn_hash;
        """)
        for tx in txs:
            if len(tx_obs[tx_obs['txn_hash'] == tx['hash']]) > 0:
                ts = tx_obs[tx_obs['txn_hash'] == tx['hash']]['time'].iloc[0]
                if type(ts) == pd.Timestamp:
                    ts = ts.timestamp()
                    timestamps.append(ts)
    except Exception as e:
        logger.debug(f"Could not fetch transaction timestamps for block {block_number}: {e}")
        timestamps = []
            

    # when was block published
    block_timestamp = datetime.fromtimestamp(int(block_header['timestamp'], 16), UTC).timestamp()

    with warnings.catch_warnings(action="ignore"):
        gas_spearman = spearmanr(list(range(len(txs))), gas_prices).statistic
        if np.isnan(gas_spearman):
            gas_spearman = None
        
        gas_kendall = kendalltau(list(range(len(txs))), gas_prices).statistic
        if np.isnan(gas_kendall):
            gas_kendall = None

        if len(timestamps) == len(txs):
            time_spearman = spearmanr(list(range(len(txs))), timestamps).statistic
            if np.isnan(time_spearman):
                time_spearman = None

            time_kendall = kendalltau(list(range(len(txs))), timestamps).statistic
            if np.isnan(time_kendall):
                time_kendall = None
        else:
            time_spearman = None
            time_kendall = None

        

    return {
        "block_number": block_number,
        "coinbase_addr": block_header['miner'],
        "num_private_tx": len(private_txs),
        "gas_decending": decending,
        "gas_ascending": ascending,
        "gas_spearman": gas_spearman,
        "gas_kendall": gas_kendall,
        "time_block": block_timestamp,
        "time_min": min(timestamps) if len(timestamps) > 0 else None,
        "time_max": max(timestamps) if len(timestamps) > 0 else None,
        "time_spearman": time_spearman,
        "time_kendall": time_kendall
    }

def upload_data(blocks):
    df = pd.DataFrame(blocks)
    
    if len(df) == 0:
        return

    table_columns = conn.execute(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = '{DB_TABLE}'
        ORDER BY ordinal_position
    """).fetchdf()['column_name'].tolist()

    insert_columns = [col for col in table_columns if col in df.columns]
    if len(insert_columns) == 0:
        raise Exception(f"No overlapping columns between dataframe and table {DB_TABLE}")

    insert_cols_sql = ", ".join(insert_columns)
    conn.register("df_upload", df[insert_columns])
    conn.execute(f"INSERT INTO {DB_TABLE} ({insert_cols_sql}) SELECT {insert_cols_sql} FROM df_upload")

# Create table before processing clusters
conn.execute(f"""
    CREATE TABLE IF NOT EXISTS {DB_TABLE} (
        block_number BIGINT,
        coinbase_addr VARCHAR,
        num_private_tx BIGINT,
        gas_decending BOOLEAN,
        gas_ascending BOOLEAN,
        gas_spearman DOUBLE,
        gas_kendall DOUBLE,
        time_block DOUBLE,
        time_min DOUBLE,
        time_max DOUBLE,
        time_spearman DOUBLE,
        time_kendall DOUBLE
    )
""")

# skip idx 1 -> lido
all_results = []
output_dir = os.path.dirname(args.output_json)
if output_dir:
    os.makedirs(output_dir, exist_ok=True)

# Ensure the single JSON output file exists from the beginning.
with open(args.output_json, 'w') as file:
    file.write('[]')

for cix in range(int(args.start),len(non_relaying_clusters)):
    # iterate over each cluster
    coinbase_addrs = non_relaying_clusters[cix]
    proposers = non_relaying_clusters_proposer[cix]

    logger.info(f"📊 Analyzing Cluster {cix}/{len(non_relaying_clusters)-1}: {coinbase_addrs}")

    blocks = fetch_block_numbers(coinbase_addrs, proposers)
    #assert len(blocks) == get_control_count(coinbase_addrs, proposers)
    logger.info(f"📦 Found {len(blocks)} blocks to analyze in cluster {cix}")

    results = []
    successful_blocks = 0
    failed_blocks = 0
    
    for b in blocks:
        try:
            txs, b_header = get_transactions(b)
            analysis = analyse_block(b, txs, b_header)
            results.append(analysis)
            successful_blocks += 1
        except Exception as e:
            logger.error(f"✗ Error analyzing block {b}: {e}")
            failed_blocks += 1

    logger.info(f"✓ Cluster {cix} analysis complete: {successful_blocks} successful, {failed_blocks} failed")

    all_results.extend(results)
    with open(args.output_json, 'w') as file:
        file.write(json.dumps(all_results, default=str))

    try:
        upload_data(results)
        logger.info(f"✓ Uploaded {len(results)} analysis results to database")
    except Exception as e:
        logger.error(f"✗ Could not upload cluster {cix}: {e}")
        with open("collectors/calc_block_statistics/error.log", 'a') as file:
            file.write(f"Error on cluster {cix}: {e}\n")

logger.info(f"Wrote {len(all_results)} rows to {args.output_json}")

conn.close()