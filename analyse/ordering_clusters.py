"""
Purpose
    Evaluates transaction ordering behavior for non-relaying proposers that
    do not include private transactions, and summarizes correlation metrics.

Usage
    python3 analyse/ordering_clusters.py

Outputs
    Histogram PDFs and out/ordering_clusters.json.
"""

# depends_on: including_xof.py
import utils.query
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from itertools import chain
import json
import sys


# Do the proposers that
# - do not use MEV-Boost
# - use EOAs as coinbase addresses
# - don't interact with builders 
# - and not include private transactions
# reorder their transactions? Or are their transactions strictly ordered?

with open("out/including_xof.json") as file:
    json_obj = json.load(file)
    not_including_xof_proposers = json_obj['not_including_xof_proposers']

df_strictly_ordered = utils.query.query_cache(f"""
    SELECT 
        proposer_index,
        COUNT(DISTINCT analyse_blocks3.block_number) as block_count,
        COUNT(DISTINCT analyse_blocks3.block_number) FILTER (WHERE gas_decending = 'true' AND gas_ascending = 'false') as strictly_decending_blocks,
        COUNT(DISTINCT analyse_blocks3.block_number) FILTER (WHERE gas_ascending = 'true' AND gas_decending = 'false') as strictly_ascending_blocks,
        COUNT(DISTINCT analyse_blocks3.block_number) FILTER (WHERE gas_ascending = 'true' AND gas_decending = 'true') as empty_blocks
    FROM
        analyse_blocks3
    JOIN coinbase_blocks_all ON
        (coinbase_blocks_all.block_number = analyse_blocks3.block_number)
    WHERE
        proposer_index IN (
            {','.join([f'{x}' for x in not_including_xof_proposers])}
        )
    GROUP BY proposer_index
    ORDER BY block_count DESC;
""")


df_strictly_decending = df_strictly_ordered[df_strictly_ordered['block_count'] == df_strictly_ordered['strictly_decending_blocks']]
df_empty_blocks = df_strictly_ordered[df_strictly_ordered['block_count'] == df_strictly_ordered['empty_blocks']]
df_remaining = df_strictly_ordered[(df_strictly_ordered['block_count'] != df_strictly_ordered['strictly_decending_blocks']) & (df_strictly_ordered['block_count'] != df_strictly_ordered['empty_blocks'])]

# calculate correlations (spearman/kendall) for block ordering per proposer
df_remaining_correlation = utils.query.query_cache(f"""
        SELECT 
            proposer_index,
            COUNT(*) as count,
            MIN(gas_spearman) as min_spearman, 
            AVG(gas_spearman) as avg_spearman, 
            MAX(gas_spearman) as max_spearman, 
            MIN(gas_kendall) as min_kendall, 
            AVG(gas_kendall) as avg_kendall, 
            MAX(gas_kendall) as max_kendall
        FROM analyse_blocks3
        JOIN coinbase_blocks_all ON
            (coinbase_blocks_all.block_number = analyse_blocks3.block_number)
        WHERE
            proposer_index IN (
                {','.join([f'{x}' for x in list(df_remaining['proposer_index'])])}
            )
        AND (gas_decending = 'false' OR gas_ascending = 'false')
        GROUP BY proposer_index
    """)

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.hist(df_remaining_correlation['avg_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='AVG(gas_spearman)')
ax.hist(df_remaining_correlation['avg_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='AVG(gas_kendall)')
ax.legend()
ax.set_title("Ordering of Transactions for 'remaining' (per proposer)")
fig.savefig("out/ordering_clusters-remaining-avg.pdf")

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.hist(df_remaining_correlation['min_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='MIN(gas_spearman)')
ax.hist(df_remaining_correlation['min_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='MIN(gas_kendall)')
ax.legend()
ax.set_title("Ordering of Transactions for 'remaining' (per proposer)")
fig.savefig("out/ordering_clusters-remaining-min.pdf")

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.hist(df_remaining_correlation['max_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='MAX(gas_spearman)')
ax.hist(df_remaining_correlation['max_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='MAX(gas_kendall)')
ax.legend()
ax.set_title("Ordering of Transactions for 'remaining' (per proposer)")
fig.savefig("out/ordering_clusters-remaining-max.pdf")

assert len(df_remaining_correlation) == len(list(df_remaining['proposer_index']))

print("Spearman always higher than 0.99:", len(df_remaining_correlation[df_remaining_correlation['max_spearman'] < -0.99]), "proposers")
print("Spearman always higher than 0.7:", len(df_remaining_correlation[df_remaining_correlation['max_spearman'] < -0.7]), "proposers")

with open('out/ordering_clusters.json', 'w') as file:
    json.dump({
        "strictly_decending_proposers": list(df_strictly_decending['proposer_index']),
        "empty_block_proposer": list(df_empty_blocks['proposer_index']),
        "remaining_proposers": list(df_remaining['proposer_index']),
    }, file)