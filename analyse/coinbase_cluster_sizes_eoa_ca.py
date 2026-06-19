"""
Purpose
    Compares coinbase cluster sizes for EOA vs contract addresses and
    visualizes relay fractions and cumulative block shares.

Notes
    Requires precomputed account classifications and contract cluster JSON.
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

print(cluster_relay_fraction_eoa)

fig, ax = plt.subplots(1, 1)
ax2 = ax.twinx()
blue_red_cmap = LinearSegmentedColormap.from_list('BlueRed', ['blue', 'gray'])

def get_marker_style(relay_fraction):
    if relay_fraction > 0 and relay_fraction < 0.5:
        return 'x'
    return 'o'

ax.scatter(x, y, c=cluster_relay_fraction_eoa, cmap=blue_red_cmap)
ax.set_yscale('log')
ax.set_xscale('log')
ax.set_xlabel('Number of validators using a coinbase address')
ax.set_ylabel('Number of coinbase addresses')
ax.set_xlim(0.5, ax.get_xlim()[1])
ax2.set_ylim(0, 1)  # linear scale between 0 and 1
ax2.set_ylabel('Share of blocks')
ax2.fill_between(
    np.append(x, ax2.get_xlim()[1]),
    np.append(cluster_block_number_cdf_eoa.values, 1),
    step="post",
    alpha=0.2,
    color="orange",
    zorder=0,
)
fig.savefig("out/coinbase_cluster_sizes_eao_ca-eoa-sizes.pdf")

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
    np.append(x, ax2.get_xlim()[1]),
    np.append(cluster_block_number_cdf_ca.values, 1),
    step="post",
    alpha=0.2,
    color="orange",
    zorder=0,
)
fig.savefig("out/coinbase_cluster_sizes_eao_ca-ca-sizes.pdf")

with open("analyse/coinbase_cluster_sizes_eoa_ca-contract-cluster.json") as file:
    contract_clusters = json.load(file)

df_ca_cluster = []
for ccl in contract_clusters:
    df_c = df_ca[df_ca['coinbase_addr'].isin(ccl)]
    # assert len(df_c) == len(ccl)

    df_ca_cluster.append({
        "coinbase_addr": ccl,
        "validator_count": df_c['validator_count'].sum(),
        "block_count": df_c['block_count'].sum(),
        "relay_block_count": df_c['relay_block_count'].sum()
    })

df_cac = pd.DataFrame(df_ca_cluster)
df_cac = df_cac.sort_values(by='validator_count')
# Only CA addresses mentioned in contract-cluster.json end up in df_cac at
# all - anything not listed there is silently absent from the "cac" plot
# below, not counted as its own size-1 cluster. block_count/validator_count/
# relay_block_count sums over df_cac would only equal the df_ca sums if that
# manual file covered every CA address.
df_cac.to_csv('/tmp/cac.csv')  # debug dump outside out/; not part of the regular output set

groupby_cluster_size_cac = df_cac.groupby('validator_count')
cluster_sizes_cac = groupby_cluster_size_cac['coinbase_addr'].count()
cluster_relay_fraction_cac = groupby_cluster_size_cac['relay_block_count'].sum() / groupby_cluster_size_cac['block_count'].sum()
cluster_block_number_cdf_cac = groupby_cluster_size_cac['block_count'].sum().cumsum()
cluster_block_number_cdf_cac = cluster_block_number_cdf_cac / cluster_block_number_cdf_cac.iloc[-1]

print(cluster_sizes_cac)

# render cac sizes
y = cluster_sizes_cac.values
x = cluster_sizes_cac.index

print(x,y)

fig, ax = plt.subplots(1, 1)
ax2 = ax.twinx()
blue_red_cmap = LinearSegmentedColormap.from_list('BlueRed', ['blue', 'red'])
ax.scatter(x, y, c=cluster_relay_fraction_cac, cmap=blue_red_cmap)
ax.set_yscale('log')
ax.set_xscale('log')
ax.set_xlabel('Number of validators in a coinbase-contract-cluster')
ax.set_ylabel('Number of coinbase addresses')
ax.set_xlim(0.5, ax.get_xlim()[1])
ax2.set_ylim(0, 1)  # linear scale between 0 and 1
ax2.set_ylabel('Share of blocks')
ax2.fill_between(
    np.append(x, ax2.get_xlim()[1]),
    np.append(cluster_block_number_cdf_cac.values, 1),
    step="pre",
    alpha=0.2,
    color="orange",
    zorder=0,
)
fig.savefig("out/coinbase_cluster_sizes_eao_ca-cac-sizes.pdf")
