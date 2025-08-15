# depends_on: non_mev_coinbase_clusters_eoa_ca.py
import json
import pandas as pd
import numpy as np
from datetime import datetime, UTC
from itertools import chain
from utils.query import query_cache

# Looking for non-MEV EOA clusters that are interacting with builders.
# This includes two types:
#   1) non-MEV-Boost proposers that build blocks with the coinbase address,
#      but include private transactions from/to builders
#   2) In a cluster, we only have proposers that use the coinbase address for block building.
#      However, there could be other proposers that only issued blocks via MEV-Boost/Relays
#      and had the coinbase address as "proposer_fee_recipient" (i.e.: they include a private
#      transaction from builder to coinbase address)

# get clusters
with open("out/non_mev_coinbase_clusters_eoa_ca.json") as file:
    eoa_clusters = json.load(file)['eoa_clusters']


# Part 1: Clusters with private transactions to/from builders
non_relaying_blocks_with_xof = query_cache(f"""
    SELECT block_number, coinbase_addr
    FROM private_blocks 
    WHERE num_private_transactions > 0 AND coinbase_addr IN (
        {','.join([f"'{x}'" for x in chain(*eoa_clusters)])}
    );
""")

# get (common) builder accounts
# https://etherscan.io/accounts/label/mev-builder
with open("analyse/interacting_with_builders-builder-addrs.json") as file:
    builder_addrs = json.load(file)

builder_xofs = []
clusters_with_builder_xofs = []
for c in eoa_clusters:
    # does this coinbase cluster have XOF?
    if non_relaying_blocks_with_xof['coinbase_addr'].isin(c).any():
        blks_with_xof = non_relaying_blocks_with_xof[non_relaying_blocks_with_xof['coinbase_addr'].isin(c)]
        
        # fetch the private transactions from mempool.guru
        xofs = query_cache(f"""
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
            clusters_with_builder_xofs.append(c)

if (len(builder_xofs) > 0):
    builder_xofs = pd.concat(builder_xofs)


# Part 2
# did the coinbase addresses show up as recipients announced by relays?

coinbases_as_relay_fee_recipient = query_cache(f"""
    SELECT proposer_fee_recipient, COUNT(DISTINCT coinbase_blocks_all.block_number)
    FROM relay_all
    INNER JOIN coinbase_blocks_all
    ON 
        (coinbase_blocks_all.block_number = relay_all.block_number AND coinbase_blocks_all.slot = relay_all.slot)
    WHERE proposer_fee_recipient IN (
        {','.join([f"'{x}'" for x in chain(*eoa_clusters)])}
    )
    GROUP BY proposer_fee_recipient
    ORDER BY count DESC;
""")

clusters_appearing_as_fee_recipient = []
block_numbers_with_cluster_as_fee_recipient = []
for c in eoa_clusters:
    if coinbases_as_relay_fee_recipient['proposer_fee_recipient'].isin(c).any():
        clusters_appearing_as_fee_recipient.append(c)

        df = query_cache(f"""
            SELECT DISTINCT coinbase_blocks_all.block_number
            FROM relay_all
            INNER JOIN coinbase_blocks_all
            ON 
                (coinbase_blocks_all.block_number = relay_all.block_number AND coinbase_blocks_all.slot = relay_all.slot)
            WHERE proposer_fee_recipient IN (
                {','.join([f"'{x}'" for x in chain(*c)])}
            );
        """)

        block_numbers_with_cluster_as_fee_recipient.append(list(df['block_number']))

# calculate non_interacting clusters
non_interacting_clusters = []
for c in eoa_clusters:
    if c not in clusters_appearing_as_fee_recipient and c not in clusters_with_builder_xofs:
        non_interacting_clusters.append(c)

assert len(non_interacting_clusters) + len(clusters_appearing_as_fee_recipient) + len(clusters_with_builder_xofs) == len(eoa_clusters)
assert len(set(chain(*non_interacting_clusters)) & set(chain(*clusters_appearing_as_fee_recipient))) == 0
assert len(set(chain(*non_interacting_clusters)) & set(chain(*clusters_with_builder_xofs))) == 0
assert len(set(chain(*clusters_appearing_as_fee_recipient)) & set(chain(*clusters_with_builder_xofs))) == 0

with open('out/interacting_with_builder.json', 'w') as file:
    json.dump({
        "eoa_clusters_with_private_builder_tx": clusters_with_builder_xofs,
        "eoa_clusters_appearing_as_fee_recipient": clusters_appearing_as_fee_recipient,
        "eoa_clusters_appearing_as_fee_recipient_block_numbers": block_numbers_with_cluster_as_fee_recipient,
        "non_interacting_eoa_clusters": non_interacting_clusters
    }, file)