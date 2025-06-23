import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import utils.query

sql_query = """
    SELECT DISTINCT coinbase_blocks_all.proposer_index, all_blocks, private_blocks, relay_blocks FROM coinbase_blocks_all
        JOIN (
            SELECT proposer_index, COUNT(block_number) as all_blocks FROM coinbase_blocks_all GROUP BY proposer_index
        ) a 
        ON (coinbase_blocks_all.proposer_index = a.proposer_index)

        JOIN (
            SELECT proposer_index, COUNT(DISTINCT mempool_private.block_number) as private_blocks FROM coinbase_blocks_all 
            LEFT JOIN mempool_private ON (coinbase_blocks_all.block_number = mempool_private.block_number)
            GROUP BY proposer_index
        ) b
        ON (coinbase_blocks_all.proposer_index = b.proposer_index)

        JOIN (
            SELECT proposer_index, COUNT(DISTINCT relay_all.block_number) as relay_blocks FROM coinbase_blocks_all
            LEFT JOIN relay_all ON (coinbase_blocks_all.block_number = relay_all.block_number)
            GROUP BY proposer_index
        ) c 
        ON (coinbase_blocks_all.proposer_index = c.proposer_index)
"""

df = utils.query.query_cache(sql_query)
print(df) # 600135 rows

# (nested) pie chart
# inspired by https://matplotlib.org/stable/gallery/pie_and_polar_charts/nested_pie.html

tab20c = plt.color_sequences["tab20c"]
outer_colors = [tab20c[i] for i in [0, 4]]
inner_colors = [tab20c[i] for i in [1, 2, 5, 6]]

y = np.array([
    len(df[df['private_blocks'] == 0]), # validators without private blocks
    len(df[df['private_blocks'] > 0]) # validators with private blocks
])
labels = ["Only public transactions", "Including private transactions"]

def writing(pct, allvals):
    absolute = int(np.round(pct/100.*np.sum(allvals)))
    return f"{pct:.1f}%"

fig, ax = plt.subplots(nrows=1, ncols=1)
wedges, texts, autotexts = ax.pie(y, autopct='%1.1f%%', pctdistance=0.78, textprops=dict(color="w"), wedgeprops=dict(width=0.3, edgecolor='w'), radius=1-0.3, colors=outer_colors)


# outer circle

y2 = np.array([
    len(df[df['private_blocks'] == 0][df['relay_blocks'] > 0]),
    len(df[df['private_blocks'] == 0][df['relay_blocks'] == 0]),
    len(df[df['private_blocks'] > 0][df['relay_blocks'] == 0]),
    len(df[df['private_blocks'] > 0][df['relay_blocks'] > 0]),
])
wedges, texts = ax.pie(y2, radius=1, wedgeprops=dict(width=0.3, edgecolor='w'), colors=inner_colors)
ax.legend(wedges, labels, loc="lower center")



bbox_props = dict(boxstyle="square,pad=0.3", fc="w", ec="k", lw=0.72)
kw = dict(arrowprops=dict(arrowstyle="-"),
          bbox=bbox_props, zorder=0, va="center")

out_text = [
    "Using Relays",
    "No Relays",
    "No Relays",
    "Using Relays",
]

for i, p in enumerate(wedges):
    ang = (p.theta2 - p.theta1)/2. + p.theta1
    y = np.sin(np.deg2rad(ang))
    x = np.cos(np.deg2rad(ang))
    horizontalalignment = {-1: "right", 1: "left"}[int(np.sign(x))]
    connectionstyle = f"angle,angleA=0,angleB={ang}"
    kw["arrowprops"].update({"connectionstyle": connectionstyle})
    ax.annotate(f"{out_text[i]}: {y2[i]}", xy=(x, y), xytext=(1.3*np.sign(x), 1.3*y),
                horizontalalignment=horizontalalignment, **kw)

ax.set_title("Validator Distribution")

fig.tight_layout()
fig.subplots_adjust(left=0.3, right=0.7)
fig.savefig("out/private_transactions_validators-pie-pubpriv-relay.png")
plt.close(fig)