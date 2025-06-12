import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import matplotlib.pyplot as plt

engine = create_engine('postgresql://rfcanalyse@rfc.incus.tamedfox.eu/rfc')

sql_query = """
SELECT coinbase_addr, count(*) as count, sum(repeat) as amount FROM (SELECT proposer_index, coinbase_addr, count(*) as repeat FROM coinbase_blocks_all GROUP BY proposer_index, coinbase_addr ORDER BY proposer_index ASC) group by coinbase_addr ORDER BY count DESC;
"""

with engine.connect() as connection:
    df = pd.read_sql(sql_query, connection)


# generate pie chart
y = np.array([
    int(df[df["count"] > 1]["amount"].sum()), # coinbase_addresses used by more than one validator
    int(df[df["count"] <= 1]["amount"].sum()) # coinbase_addresses used by only one validator
])
labels = ["Reused coinbase addresses", "Unique coinbase addresses"]
explode = [0.0, 0.1]

def writing(pct, allvals):
    absolute = int(np.round(pct/100.*np.sum(allvals)))
    return f"{pct:.1f}%\n({absolute:d} slots)"

fig, ax = plt.subplots(nrows=1, ncols=1)
wedges, texts, autotexts = ax.pie(y, explode=explode, autopct=lambda pct: writing(pct, y), textprops=dict(color="w"))
ax.set_title("Coinbase Uniqueness")
ax.legend(wedges, labels,
          loc="lower center")

fig.savefig("charts/coinbase_addr_distribution.png")
plt.close(fig)

# generate bar chart
y = []
x = []
for i in range(1, 20):
    y.append(int(df[df["count"] == i]["amount"].sum()))
    x.append(i)

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.bar(x, y)
ax.set_xticks(x)
fig.savefig("charts/coinbase_addr_distribution-bar-chart.png")
plt.close(fig)


# line-chart (cdf)

grouped = df.groupby('count')['amount'].sum().sort_index()
cdf = grouped.cumsum()
cdf_normalized = cdf / cdf.iloc[-1]

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.plot(cdf_normalized.index, cdf_normalized.values, marker='o')
ax.axhline(y=0.1, color='blue', linestyle='--', linewidth=1)
ax.axvline(x=cdf_normalized[cdf_normalized >= 0.1].index[0], color='blue', linestyle='--', linewidth=1)
ax.set_xscale('log')
fig.savefig("charts/coinbase_addr_distribution-line-chart.png")
