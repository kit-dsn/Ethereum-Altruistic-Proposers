"""
Purpose
    Quantifies reuse of coinbase addresses across validators and produces
    distribution plots and a list of unique coinbase addresses.

Background
    An early, coarse look at the same reuse question coinbase_clusters.py
    later answers properly via graph clustering: here, "reuse" is just
    "how many distinct proposer_index values share this one coinbase
    address", with no attempt to chain addresses together through shared
    proposers. The 8.9% reference line marks the literature's "9% of
    proposers don't delegate to relays" figure for visual comparison.

Outputs
    PDF figures and out/coinbase_addr_distribution-unique-coinbase-addrs.json.
"""

import pandas as pd
import numpy as np
import duckdb
import matplotlib.pyplot as plt
import utils.query

df = utils.query.query_cache("""
    SELECT 
        coinbase_addr, count(*) as count, sum(repeat) as amount 
    FROM (
        SELECT 
            proposer_index, 
            coinbase_addr, 
            count(*) as repeat 
        FROM coinbase_blocks_all 
        GROUP BY proposer_index, coinbase_addr 
        ORDER BY proposer_index ASC
    )
    GROUP BY coinbase_addr 
    ORDER BY count DESC;
""")

# generate pie chart (slots)
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

fig.savefig("out/coinbase_addr_distribution-slots.pdf")
plt.close(fig)

# export unique coinbase addresses
df[df["count"] <= 1].to_json('out/coinbase_addr_distribution-unique-coinbase-addrs.json')

# generate pie chart (validators)
y = np.array([
    int(df[df["count"] > 1]["count"].sum()), # coinbase_addresses used by more than one validator
    int(df[df["count"] <= 1]["count"].sum()) # coinbase_addresses used by only one validator
])
labels = ["Reused coinbase addresses", "Unique coinbase addresses"]
explode = [0.0, 0.1]

def writing(pct, allvals):
    absolute = int(np.round(pct/100.*np.sum(allvals)))
    return f"{pct:.1f}%\n({absolute:d} validators)"

fig, ax = plt.subplots(nrows=1, ncols=1)
wedges, texts, autotexts = ax.pie(y, explode=explode, autopct=lambda pct: writing(pct, y), textprops=dict(color="w"))
ax.set_title("Coinbase Uniqueness")
ax.legend(wedges, labels,
          loc="lower center")

fig.savefig("out/coinbase_addr_distribution-validators.pdf")
plt.close(fig)

# generate bar chart
y = []
x = []
for i in range(1, 20):
    y.append(int(df[df["count"] == i]["amount"].sum()))
    x.append(i)

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.set_xlabel("Number of validators sharing coinbase address")
ax.set_ylabel("Number of blocks")
ax.bar(x, y)
ax.set_xticks(x)
fig.savefig("out/coinbase_addr_distribution-bar-chart.pdf")
plt.close(fig)


# line-chart (cdf)
grouped = df.groupby('count')['amount'].sum().sort_index()
print(grouped)
cdf = grouped.cumsum()
cdf_normalized = cdf / cdf.iloc[-1]

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.plot(cdf_normalized.index, cdf_normalized.values, marker='o')
ax.axhline(y=0.089, color='blue', linestyle='--', linewidth=1)  # see Background: literature's ~9% non-delegating figure
ax.axvline(x=cdf_normalized[cdf_normalized >= 0.089].index[0], color='blue', linestyle='--', linewidth=1)
ax.set_xscale('log')
fig.savefig("out/coinbase_addr_distribution-line-chart.pdf")

ax.set_yscale('log')
fig.savefig("out/coinbase_addr_distribution-line-chart-log.pdf")