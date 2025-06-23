import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

engine = create_engine('postgresql://rfcanalyse@rfc.incus.tamedfox.eu/rfc')

sql_query = """
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
"""

with engine.connect() as connection:
    df = pd.read_sql(sql_query, connection)

print(df)

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
ax.axhline(y=0.089, color='blue', linestyle='--', linewidth=1)
ax.axvline(x=cdf_normalized[cdf_normalized >= 0.089].index[0], color='blue', linestyle='--', linewidth=1)
ax.set_xscale('log')
fig.savefig("out/coinbase_addr_and_relays-scatter.png")

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
fig.savefig("out/coinbase_addr_and_relays-real-scatter.png")