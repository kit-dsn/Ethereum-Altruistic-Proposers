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

engine = create_engine("postgresql://rfcanalyse@rfc.incus.tamedfox.eu/rfc")
connection = engine.connect()
def query(sql):
    return pd.read_sql(sql, connection)

# get clusters
with open("out/proposer_clusters_merged.json") as file:
    f = json.load(file)
    non_relaying_clusters = f['clusters']
    non_relaying_clusters_proposer = f['proposers']

non_relaying_proposer_coinbases = pd.read_json('out/proposer_collaboration-no-relaying-proposer-coinbase.json')

assert set(non_relaying_proposer_coinbases['proposer_index'].unique()) == set(chain(*(non_relaying_clusters_proposer)))

# get blocks with private transactions
non_relaying_blocks_with_xof = query(f"""
    SELECT block_number, coinbase_addr FROM analyse_blocks2 WHERE num_private_tx > 0;
""")

# get (common) builder accounts
# https://etherscan.io/accounts/label/mev-builder
with open("analyse/private_builder_tx-builder-addrs.json") as file:
    builder_addrs = json.load(file)

builder_xofs = []
for c in non_relaying_clusters:
    # does this coinbase cluster have XOF?
    if non_relaying_blocks_with_xof['coinbase_addr'].isin(c).any():
        blks_with_xof = non_relaying_blocks_with_xof[non_relaying_blocks_with_xof['coinbase_addr'].isin(c)]
        
        # fetch the private transactions from mempool.guru
        xofs = query(f"""
            SELECT block_number, txn_hash, txn_index, lower(addr_from) as addr_from, lower(addr_to) as addr_to FROM mempool_private
            WHERE block_number IN (
                {','.join([str(x) for x in blks_with_xof['block_number'].tolist()])}
            )
        """)

        if xofs['addr_from'].isin(builder_addrs).any() or xofs['addr_to'].isin(builder_addrs).any():
            # the cluster issued blocks with a private tx with a builder addr
            tx = pd.concat([
                xofs[xofs['addr_from'].isin(builder_addrs)],
                xofs[xofs['addr_to'].isin(builder_addrs)]
            ])
            tx['coinbase_addr'] = [c] * len(tx)
            builder_xofs.append(tx)

builder_xofs = pd.concat(builder_xofs)
builder_xofs.to_csv('out/private_builder_tx.csv')
