"""
Purpose
    Relates coinbase address reuse to relay usage and visualizes cluster
    sizes and relay fractions across validator groups.

Usage
    python3 analyse/coinbase_addr_and_relays.py
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import utils.query

df = utils.query.query_cache("""
    SELECT a.coinbase_addr, a.validator_count, a.block_count, b.relay_block_count FROM    
    (
        SELECT coinbase_addr, count(*) as validator_count, sum(repeat) as block_count 
        FROM 
            (SELECT proposer_index, coinbase_addr, count(*) as repeat FROM coinbase_blocks_all GROUP BY proposer_index, coinbase_addr ORDER BY proposer_index ASC) 
        GROUP BY coinbase_addr 
    ) a INNER JOIN (
        SELECT coinbase_addr, count(DISTINCT relay_all.block_number) as relay_block_count 
        FROM relay_all 
        RIGHT JOIN coinbase_blocks_all ON (coinbase_blocks_all.block_number = relay_all.block_number) 
        GROUP BY coinbase_addr 
    ) b ON (a.coinbase_addr = b.coinbase_addr)
    ORDER BY a.validator_count;
""")

assert len(df[df['block_count'] < df['relay_block_count']]) == 0

# scatter (cdf)
grouped = df.groupby('validator_count')
cdf = grouped['block_count'].sum().sort_index().cumsum()
cdf_normalized = cdf / cdf.iloc[-1]

# fraction of relay blocks
grouped_relay_sum = grouped['relay_block_count'].sum().sort_index()
grouped_all_sum = grouped['block_count'].sum().sort_index()
fraction_relay = grouped_relay_sum / grouped_all_sum

green_red_cmap = LinearSegmentedColormap.from_list('BlueRed', ['blue', 'red'])

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.scatter(cdf_normalized.index, cdf_normalized.values, marker='o', c=fraction_relay, cmap=green_red_cmap)
ax.plot(cdf_normalized.index, cdf_normalized.values, color="black")
ax.axhline(y=0.089, color='blue', linestyle='--', linewidth=1)
ax.axvline(x=cdf_normalized[cdf_normalized >= 0.089].index[0], color='blue', linestyle='--', linewidth=1)
ax.set_xscale('log')
fig.savefig("out/coinbase_addr_and_relays-scatter.pdf")
ax.set_yscale('log')
fig.savefig("out/coinbase_addr_and_relays-scatter-log.pdf")

# graph of validator addresses

fig, ax = plt.subplots(nrows=1, ncols=2, figsize=(40,10), sharey=True, width_ratios=[0.95,0.05])

coinbase_addr_translated = df['coinbase_addr'].apply(int, base=16)
fraction_relay = df['relay_block_count'] / df['block_count']

ax[0].scatter(coinbase_addr_translated.values, df['block_count'].values, c=fraction_relay, cmap=green_red_cmap)
ax[0].set_xticks([], [])
ax[0].set_yscale('log')
ax[0].set_xlabel("Coinbase Address")
ax[0].set_ylabel("Number of Blocks")

grouped = df.groupby('block_count')
grouped_all_sum = grouped['block_count'].sum().sort_index()
grouped_relay_sum = grouped['relay_block_count'].sum().sort_index()

fraction_relay = grouped_relay_sum / grouped_all_sum

ax[1].scatter([0 for i in range(len(grouped))], grouped["block_count"].first().values, c=fraction_relay, cmap=green_red_cmap)
ax[1].set_xticks([], [])
ax[1].set_xlabel("Combined")

fig.tight_layout()
fig.savefig("out/coinbase_addr_and_relays-real-scatter.pdf")

# export data
df.to_json("out/coinbase_addr_and_relays-coinbase-data.json")

# show size of clusters
df_groupby_validator_count = df.groupby('validator_count')
cluster_size_df = df_groupby_validator_count['coinbase_addr'].count()
y = cluster_size_df.values
x = cluster_size_df.index

cluster_relay_fraction = df_groupby_validator_count['relay_block_count'].sum() / df_groupby_validator_count['block_count'].sum()


# inspired from https://stackoverflow.com/questions/66988956/how-to-create-a-customizednon-linear-not-log-x-axis-in-plot
fig, (ax1, ax2, ax3) = plt.subplots(1, 3, gridspec_kw={'wspace': 0}, figsize=(30,5), width_ratios=[0.4,0.4,0.2])

ax1.spines.right.set_visible(False)
ax2.spines.left.set_visible(False)
ax2.spines.right.set_visible(False)
ax3.spines.left.set_visible(False)


xlim1 = (0, 80)
xlim2 = (80, 1150)
xlim3 = (1150, 300000)

ax1.axvline(xlim1[1], clip_on=False, color='gray')
ax2.axvline(xlim2[1], clip_on=False, color='gray')

ax1.scatter(x, y, c=cluster_relay_fraction, cmap=green_red_cmap)
ax2.scatter(x, y, c=cluster_relay_fraction, cmap=green_red_cmap)
ax3.scatter(x, y, c=cluster_relay_fraction, cmap=green_red_cmap)
ax3.set_xscale('log')
ax1.set_xlim(xlim1)
ax2.set_xlim(xlim2)
ax3.set_xlim(xlim3)
ax3.set_xticks([10**4, 10**5])


ax1.spines[['right', 'top']].set_visible(False)
ax2.spines[['left', 'right', 'top']].set_visible(False)
ax3.spines[['left', 'right', 'top']].set_visible(False)

ax1.set_yscale('log')
ax2.set_yscale('log')
ax3.set_yscale('log')
ax2.set_yticks([], [])
ax3.set_yticks([], [])

ax2.set_xlabel("Number of Validators sharing Coinbase")
ax1.set_ylabel("Number of Clusters")

fig.savefig("out/coinbase_addr_and_relays-cluster-sizes.pdf")
plt.close(fig)