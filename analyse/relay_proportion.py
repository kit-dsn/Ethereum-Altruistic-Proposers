import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import matplotlib.pyplot as plt

engine = create_engine('postgresql://rfcanalyse@rfc.incus.tamedfox.eu/rfc')

sql_query = """
SELECT count(DISTINCT block_number) as relay_blocks, (SELECT count(*) FROM coinbase_blocks) as total_blocks FROM relay_all WHERE block_number >= (SELECT min(block_number) FROM coinbase_blocks) AND block_number <= (SELECT max(block_number) FROM coinbase_blocks);
"""

with engine.connect() as connection:
    df = pd.read_sql(sql_query, connection)

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

fig.savefig("out/relay_proportion-bar-chart.png")
plt.close(fig)
