"""
Purpose
    Measures temporal distribution (block numbers) of blocks produced by
    coinbase addresses used by few validators.

Outputs
    Histogram PDF and JSON block lists in out/.
"""

import pandas as pd
import numpy as np
import duckdb
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sql_query = """
    SELECT block_number FROM coinbase_blocks_all 
    WHERE coinbase_addr IN (
        SELECT coinbase_addr FROM (
            SELECT coinbase_addr, count(DISTINCT proposer_index) as count FROM coinbase_blocks_all
            GROUP BY coinbase_addr
        ) WHERE count = 1
    )
    ORDER BY block_number ASC
"""

sql_query2 = """
    SELECT block_number FROM coinbase_blocks_all 
    WHERE coinbase_addr IN (
        SELECT coinbase_addr FROM (
            SELECT coinbase_addr, count(DISTINCT proposer_index) as count FROM coinbase_blocks_all
            GROUP BY coinbase_addr
        ) WHERE count < 10
    )
    ORDER BY block_number ASC
"""

conn = duckdb.connect('/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb')
df = conn.execute(sql_query).df()
df2 = conn.execute(sql_query2).df()

# create a histogram
counts, bins = np.histogram(df["block_number"].values, bins=30)
counts2, bins2 = np.histogram(df2["block_number"].values, bins=30)

df_min, df_max = df["block_number"].min(), df["block_number"].max()


fig, ax = plt.subplots(nrows=1, ncols=1)
ax.stairs(counts, bins)
ax.set_xlim([df_min, df_max])
ax.set_xticks([df_min, (df_min+df_max)//2, df_max], [str(df_min), str((df_min + df_max)//2), str(df_max)])
ax.set_xlabel("Block number")
ax.set_ylabel("Number of Blocks with (per-validator) unique coinbase address")

ax2 = ax.twinx()
ax2.stairs(counts2, bins2, color="tab:red")
ax2.set_ylabel("Number of Blocks with coinbase address used by at most 10 validators")
fig.savefig("out/coinbase_time_distribution-histogram.pdf")

# export those block numbers
df.to_json("out/coinbase_time_distribution-data-unique-blocks.json")
df2.to_json("out/coinbase_time_distribution-data-max10-blocks.json")