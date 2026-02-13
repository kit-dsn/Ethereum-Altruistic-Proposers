"""
Purpose
    Generates cluster-size distribution for EOA coinbase clusters
    with relay fraction overlays.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import json
import utils.query

# first analyze EOA coinbase addresses
df = utils.query.query_cache("""
    SELECT a.coinbase_addr, a.validator_count, a.block_count, b.relay_block_count, c.is_account FROM    
    (
        SELECT coinbase_addr, count(*) as validator_count, sum(repeat) as block_count 
        FROM (
            SELECT proposer_index, coinbase_addr, count(*) as repeat 
            FROM coinbase_blocks_all 
            GROUP BY proposer_index, coinbase_addr
        ) 
        GROUP BY coinbase_addr 
    ) a INNER JOIN (
        SELECT coinbase_addr, count(DISTINCT relay_all.block_number) as relay_block_count 
        FROM relay_all 
        RIGHT JOIN coinbase_blocks_all ON (
            coinbase_blocks_all.block_number = relay_all.block_number AND
            coinbase_blocks_all.slot = relay_all.slot
        ) 
        GROUP BY coinbase_addr 
    ) b ON (a.coinbase_addr = b.coinbase_addr)
    INNER JOIN (
        SELECT coinbase_addr, is_account FROM accounts
    ) c ON (a.coinbase_addr = c.coinbase_addr)
    ORDER BY a.validator_count;
""")

df_eoa = df[df['is_account'] == True]

groupby_cluster_size_eoa = df_eoa.groupby('validator_count')
cluster_sizes_eoa = groupby_cluster_size_eoa['coinbase_addr'].count()
cluster_relay_fraction_eoa = groupby_cluster_size_eoa['relay_block_count'].sum() / groupby_cluster_size_eoa['block_count'].sum()

cluster_block_number_cdf_eoa = groupby_cluster_size_eoa['block_count'].sum().cumsum()
cluster_block_number_cdf_eoa = cluster_block_number_cdf_eoa / cluster_block_number_cdf_eoa.iloc[-1]


fig, ax = plt.subplots(figsize=(10,5))
ax2 = ax.twinx()

def get_color(relay_fraction):
    if relay_fraction > 0 and relay_fraction < 0.5:
        return 'red'
    elif relay_fraction > 0.5:
        return 'gray'
    return 'blue'

ax.scatter(cluster_sizes_eoa.index, cluster_sizes_eoa.values, c=[get_color(x) for x in cluster_relay_fraction_eoa])
ax.set_yscale('log')
ax.set_xscale('log')
ax.set_xlabel('Cluster Size: Number of Proposer Sharing a Coinbase Address')
ax.set_ylabel('Number of Clusters')
ax.set_xlim(0.5, ax.get_xlim()[1])

ax2.set_ylim(0, 1)
ax2.set_ylabel('Share of Proposed Blocks')
ax2.fill_between(
    np.append(cluster_sizes_eoa.index, ax2.get_xlim()[1]),
    np.append(cluster_block_number_cdf_eoa.values, 1),
    step="post",
    alpha=0.2,
    color="orange",
    zorder=0,
)
fig.savefig("out/cluster_size_distribution.pdf")
