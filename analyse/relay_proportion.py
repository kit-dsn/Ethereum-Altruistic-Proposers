"""
Purpose
    Computes the share of blocks announced via relays and visualizes it as
    a pie chart.

Outputs
    out/relay_proportion-bar-chart.pdf
"""

import pandas as pd
import numpy as np
import duckdb
import matplotlib.pyplot as plt

sql_query = """
    SELECT 
        count(DISTINCT relay_all.block_number) as relay_blocks, 
        (SELECT count(*) FROM coinbase_blocks_all) as total_blocks 
    FROM relay_all 
    INNER JOIN coinbase_blocks_all ON (
        coinbase_blocks_all.slot = relay_all.slot AND
        coinbase_blocks_all.block_number = relay_all.block_number
    )
"""

conn = duckdb.connect('/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb')
df = conn.execute(sql_query).df()

# generate pie chart
y = np.array([
    int(df.iloc[0]["relay_blocks"]),
    int(df.iloc[0]["total_blocks"]) - int(df.iloc[0]["relay_blocks"])
])
labels = ["Blocks announced by relays", "Others"]
explode = [0.0, 0.1]

def writing(pct, allvals):
    absolute = int(np.round(pct/100.*np.sum(allvals)))
    return f"{pct:.1f}%\n({absolute:d} blocks)"

fig, ax = plt.subplots(nrows=1, ncols=1)
wedges, texts, autotexts = ax.pie(y, explode=explode, autopct=lambda pct: writing(pct, y), textprops=dict(color="w"))
ax.set_title("Blocks announced from relays")
ax.legend(wedges, labels, loc="lower center")

fig.savefig("out/relay_proportion-bar-chart.pdf")
plt.close(fig)
