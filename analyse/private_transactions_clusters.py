"""
Purpose
    Measures private-transaction usage across non-relaying coinbase
    clusters and renders a block-vs-private-tx scatter.

Background
    An earlier, coarser look at the same question including_xof.py answers
    per individual proposer: does self-building still involve privately
    routed order flow? Here it's broken down per coinbase cluster instead,
    over the full non-relaying set (not yet narrowed to EOA-only / non-
    builder-interacting proposers), to see how widespread the behavior is
    before the later, stricter filters are applied.

Outputs
    PDF scatter plot and out/private_transactions_clusters-overview.html.
"""

# depends_on: coinbase_clusters.py
import utils.query
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import json

# analyze for each cluster
with open('out/coinbase_clusters-non-relaying-clusters.json') as file:
    coinbase_clusters = json.load(file)

df_by_coinbase = utils.query.query_cache(f"""
    SELECT 
        coinbase_addr,
        COUNT(block_number) as count,
        SUM(num_private_transactions) as num_private_tx 
    FROM private_blocks
    GROUP BY coinbase_addr
    """)

print(df_by_coinbase)

df_clusters = []
for cluster in coinbase_clusters[1:]:
    df_cluster = df_by_coinbase[df_by_coinbase.apply(lambda x: x['coinbase_addr'] in cluster, axis=1)].copy()
    df_clusters.append(pd.Series({
        'cluster': cluster,
        'count': df_cluster['count'].sum(),
        'num_private_tx': df_cluster['num_private_tx'].sum()
    }))

df_clusters = pd.DataFrame(df_clusters)
df_clusters = df_clusters.sort_values(by='num_private_tx', ascending=False).reset_index(drop=True)

num_cluster_no_private = df_clusters[df_clusters['num_private_tx'] == 0]['count'].count()
num_cluster_overall = len(df_clusters)

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.set_title("Private TXs in non-PBS clusters")
ax.scatter(df_clusters['count'], df_clusters['num_private_tx'], marker='o')
ax.set_yscale('log')
ax.set_xscale('log')
ax.set_xlabel("Number of Blocks published")
ax.set_ylabel("Number of private transactions")
fig.savefig("out/private_transactions_clusters-blocks-private-tx-scatter.pdf")


# generate an html doc
htmlOut = "<!DOCTYPE html><html><head><title>RFC - private_transactions_clusters</title></head><body>\n"
htmlOut += f"<p>Out of {num_cluster_overall} clusters, there are {num_cluster_no_private} clusters whose blocks did not contain private transactions.</p>"
htmlOut += f"""
    <figure>
        <a href="private_transactions_clusters-blocks-private-tx-scatter.pdf" target="_blank"><img src="private_transactions_clusters-blocks-private-tx-scatter.pdf"></a>
        <figcaption>Number of private transactions vs. block count for non-PBS clusters</figcaption>
    </figure>
"""
htmlOut += df_clusters.to_html(escape=False)
htmlOut += "</body></html>"

with open("out/private_transactions_clusters-overview.html", "w") as file:
    file.write(htmlOut)