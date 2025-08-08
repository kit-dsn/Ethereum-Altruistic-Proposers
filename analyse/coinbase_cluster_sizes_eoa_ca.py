import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
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
df_ca = df[df['is_account'] == False]


# analyze cluster size frequencies
groupby_cluster_size_eoa = df_eoa.groupby('validator_count')
cluster_sizes_eoa = groupby_cluster_size_eoa['coinbase_addr'].count()
groupby_cluster_size_ca = df_ca.groupby('validator_count')
cluster_sizes_ca = groupby_cluster_size_ca['coinbase_addr'].count()

cluster_relay_fraction_eoa = groupby_cluster_size_eoa['relay_block_count'].sum() / groupby_cluster_size_eoa['block_count'].sum()
cluster_relay_fraction_ca = groupby_cluster_size_ca['relay_block_count'].sum() / groupby_cluster_size_ca['block_count'].sum()

cluster_block_number_cdf_eoa = groupby_cluster_size_eoa['block_count'].sum().cumsum()
cluster_block_number_cdf_eoa = cluster_block_number_cdf_eoa / cluster_block_number_cdf_eoa.iloc[-1]

cluster_block_number_cdf_ca = groupby_cluster_size_ca['block_count'].sum().cumsum()
cluster_block_number_cdf_ca = cluster_block_number_cdf_ca / cluster_block_number_cdf_ca.iloc[-1]


# render eoa sizes
y = cluster_sizes_eoa.values
x = cluster_sizes_eoa.index

fig, ax = plt.subplots(1, 1)
ax2 = ax.twinx()
blue_red_cmap = LinearSegmentedColormap.from_list('BlueRed', ['blue', 'red'])
ax.scatter(x, y, c=cluster_relay_fraction_eoa, cmap=blue_red_cmap)
ax.set_yscale('log')
ax.set_xscale('log')
ax.set_xlabel('Number of validators using a coinbase address')
ax.set_ylabel('Number of coinbase addresses')
ax.set_xlim(0.5, ax.get_xlim()[1])
ax2.set_ylim(0, 1)  # linear scale between 0 and 1
ax2.set_ylabel('Share of blocks')
ax2.fill_between(
    np.append(np.repeat(x, 2)[1:],ax.get_xlim()[1]),
    0,  # start from bottom
    np.append(np.repeat(cluster_block_number_cdf_eoa.values, 2)[:-1], 1),
    color='orange',
    alpha=0.2,
    zorder=0  # ensures it stays behind scatter
)
fig.savefig("out/coinbase_cluster_sizes_eao_ca-eoa-sizes.png")

# render ca sizes
y = cluster_sizes_ca.values
x = cluster_sizes_ca.index

fig, ax = plt.subplots(1, 1)
ax2 = ax.twinx()
blue_red_cmap = LinearSegmentedColormap.from_list('BlueRed', ['blue', 'red'])
ax.scatter(x, y, c=cluster_relay_fraction_ca, cmap=blue_red_cmap)
ax.set_yscale('log')
ax.set_xscale('log')
ax.set_xlabel('Number of validators using a coinbase address')
ax.set_ylabel('Number of coinbase addresses')
ax.set_xlim(0.5, ax.get_xlim()[1])
ax2.set_ylim(0, 1)  # linear scale between 0 and 1
ax2.set_ylabel('Share of blocks')
ax2.fill_between(
    np.append(np.repeat(x, 2)[1:],ax.get_xlim()[1]),
    0,  # start from bottom
    np.append(np.repeat(cluster_block_number_cdf_ca.values, 2)[:-1], 1),
    color='orange',
    alpha=0.2,
    zorder=0  # ensures it stays behind scatter
)
fig.savefig("out/coinbase_cluster_sizes_eao_ca-ca-sizes.png")
