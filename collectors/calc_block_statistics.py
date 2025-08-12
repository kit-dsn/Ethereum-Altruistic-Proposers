import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, UTC
from sqlalchemy import create_engine, MetaData, Table, Column, String, BigInteger, Numeric, Float, Index, DateTime
from sqlalchemy.dialects.postgresql import insert
from itertools import chain
from scipy.stats import spearmanr, kendalltau
import argparse
import warnings
import time

argparser = argparse.ArgumentParser(
    prog="Analyse blocks",
)
argparser.add_argument('-d', '--database', default="postgresql://root@rfc.incus.tamedfox.eu/rfc")
argparser.add_argument('-t', '--table', default="analyse_blocks")
argparser.add_argument('-s', '--start', default="1")

args = argparser.parse_args()

engine = create_engine(args.database)
connection = engine.connect()
def query(sql):
    return pd.read_sql(sql, connection)

EL_API_BASE = "http://localhost:8545"
DB_TABLE = args.table

# get clusters
with open("out/coinbase_clusters-non-relaying-clusters.json") as file:
    non_relaying_clusters = json.load(file)

non_relaying_proposer_coinbases = pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')

def fetch_block_numbers(coinbase_addrs, proposer_idxs):
    q = query(f"""
        SELECT DISTINCT block_number, coinbase_addr FROM coinbase_blocks_all
        WHERE 
            proposer_index IN ({','.join([str(x) for x in proposer_idxs])})
    """)

    assert set(q['coinbase_addr'].unique()) == set(coinbase_addrs)
    return list(q['block_number'])

def get_control_count(coinbase_addrs, proposer_idxs):
    return non_relaying_proposer_coinbases[
        non_relaying_proposer_coinbases['proposer_index'].isin(proposer_idxs) &
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
    return r.json()["result"]

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
    
    txs = []
    for tx_hash in header['transactions']:
        txs.append(fetch_transaction(tx_hash))

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
    tx_obs = query(f"""
        SELECT txn_hash, MIN(time_seen) as time FROM mempool_txobs2
        WHERE block_number = {block_number}
        GROUP BY txn_hash;
    """)
    timestamps = []
    for tx in txs:
        if len(tx_obs[tx_obs['txn_hash'] == tx['hash']]) > 0:
            ts = tx_obs[tx_obs['txn_hash'] == tx['hash']]['time'].iloc[0]
            if type(ts) == pd.Timestamp:
                ts = ts.timestamp()
                timestamps.append(ts)
            

    # when was block published
    block_timestamp = datetime.fromtimestamp(int(b_header['timestamp'], 16), UTC).timestamp()

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
        "coinbase_addr": b_header['miner'],
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
    metadata = MetaData()
    
    columns = []

    for col_name, dtype in df.dtypes.items():
        if pd.api.types.is_integer_dtype(dtype):
            col_type = BigInteger
        elif pd.api.types.is_float_dtype(dtype):
            col_type = Float
        elif pd.api.types.is_datetime64_dtype(dtype) or pd.api.types.is_datetime64_ns_dtype(dtype):
            col_type = DateTime
        else:
            col_type = String

        if col_name == "block_number":
            columns.append(Column(col_name, col_type, unique=True))
        else:
            columns.append(Column(col_name, col_type))
    
    table = Table(DB_TABLE, 
                  metadata, 
                  *columns, 
                  Index(f"ix_{DB_TABLE}_block_number", "block_number"),
                  Index(f"ix_{DB_TABLE}_coinbase_addr", "coinbase_addr")
        )
    
    metadata.create_all(engine, checkfirst=True)
    connection.execute(table.insert(), df.to_dict('records'))
    connection.commit()

# skip idx 1 -> lido
for cix in range(int(args.start),len(non_relaying_clusters)):
    # iterate over each cluster
    coinbase_addrs = non_relaying_clusters[cix]
    proposers = non_relaying_clusters_proposer[cix]

    print("Analyzing Cluster: ", coinbase_addrs, f"{cix}/{len(non_relaying_clusters)-1}")

    blocks = fetch_block_numbers(coinbase_addrs, proposers)
    assert len(blocks) == get_control_count(coinbase_addrs, proposers)

    results = []
    for b in blocks:
        try:
            print(f"Analyze block: {b}")
            txs, b_header = get_transactions(b)
            analysis = analyse_block(b, txs, b_header)
            results.append(analysis)
        except:
            pass

    
    with open(f"collectors/calc_block_statistics/analyze-{cix}.json", 'w') as file:
        file.write(json.dumps(results, default=str)) 

    try:
        upload_data(results)
    except:
        print(f"Could not upload cluster {cix}")
        with open("collectors/calc_block_statistics/error.log", 'a') as file:
            file.write(f"Error on cluster {cix}\n")
        
        connection.rollback()


# end sql connection
connection.close()