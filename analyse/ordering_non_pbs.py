"""
Purpose
    Analyzes transaction ordering metrics for non-relaying blocks and
    produces per-cluster summaries and an HTML overview.

Background
    Same gas-price ordering question as ordering_clusters.py, but here
    aggregated per coinbase-address cluster (from proposer_clusters.py)
    rather than per individual proposer/proposer-filter-stage - a coarser,
    earlier-stage view that includes clusters later analyses go on to
    exclude (e.g. for builder interaction or private tx usage).

Outputs
    PDF histograms and out/ordering_non_pbs-overview.html.
"""

# depends_on: proposer_clusters.py
import utils.query
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import json

df_correlation_only = utils.query.query_cache("""
    SELECT gas_spearman, gas_kendall FROM analyse_blocks;
""")

# data samples:
total_number_blocks = len(df_correlation_only)
print(f"Number of blocks: {total_number_blocks}")

# an overview over the ordering
fig, ax = plt.subplots(nrows=1, ncols=1)

gas_spearman = df_correlation_only[df_correlation_only['gas_spearman'].notna()]['gas_spearman']
ax.hist(gas_spearman, range=(-1,1), bins=100, color='red', histtype='step', label='Gas (spearman correlation)')

gas_kendall = df_correlation_only[df_correlation_only['gas_kendall'].notna()]['gas_kendall']
ax.hist(gas_kendall, range=(-1,1), bins=100, color='blue', histtype='step', label='Gas (kendall correlation)')

ax.legend()
ax.set_title("Ordering of Transactions for non-relaying proposers")
fig.savefig("out/ordering_non_pbs-histogram.pdf")

print(f"Number of blocks with meaningful data: {len(gas_spearman)} (spearman) / {len(gas_kendall)} (kendall)")

# how many blocks are "strict"?
df_strict = utils.query.query_cache("""
    SELECT 
        (SELECT COUNT(*) FROM analyse_blocks WHERE gas_decending = 'true' and gas_ascending = 'false') as decending_blocks,
        (SELECT COUNT(*) FROM analyse_blocks WHERE gas_ascending = 'true' and gas_decending = 'false') as ascending_blocks;
""")

num_decending_blocks = df_strict['decending_blocks'].iloc[0]
num_ascending_blocks = df_strict['ascending_blocks'].iloc[0]

print(f"Decending blocks: {num_decending_blocks}\nAscending blocks: {num_ascending_blocks}")

# analyze for each cluster
with open('out/proposer_clusters-non-relaying-clusters.json') as file:
    coinbase_clusters = json.load(file)

df_by_coinbase = utils.query.query_cache(f"""
        SELECT 
            coinbase_addr,
            COUNT(*) as count,
            MIN(gas_spearman) as min_spearman, 
            AVG(gas_spearman) as avg_spearman, 
            MAX(gas_spearman) as max_spearman, 
            MIN(gas_kendall) as min_kendall, 
            AVG(gas_kendall) as avg_kendall, 
            MAX(gas_kendall) as max_kendall
        FROM analyse_blocks
        WHERE gas_ascending = 'false' OR gas_decending = 'false'
        GROUP BY coinbase_addr
    """)

df_clusters = []
for cluster in coinbase_clusters[1:]:
    df_cluster = df_by_coinbase[df_by_coinbase.apply(lambda x: x['coinbase_addr'] in cluster, axis=1)].copy()
    if len(df_cluster) == 1:
        df = df_cluster.iloc[0]
        df = df.drop('coinbase_addr')
        df['cluster'] = cluster
    elif len(df_cluster) == 0:
        df = pd.Series({
            'cluster': cluster,
            'count': 0,
            'min_spearman': None,
            'max_spearman': None,
            'min_kendall': None,
            'max_kendall': None,
            'avg_spearman': None,
            'avg_kendall': None
        })
    else:
        df = pd.Series({
            'cluster': cluster,
            'count': df_cluster['count'].sum(),
            'min_spearman': df_cluster['min_spearman'].min(),
            'max_spearman': df_cluster['max_spearman'].max(),
            'min_kendall': df_cluster['min_kendall'].min(),
            'max_kendall': df_cluster['max_kendall'].max(),
            'avg_spearman': (df_cluster['avg_spearman'] * df_cluster['count']).sum() / df_cluster['count'].sum(),
            'avg_kendall': (df_cluster['avg_kendall'] * df_cluster['count']).sum() / df_cluster['count'].sum()
        })

    df_clusters.append(df)

df_clusters = pd.DataFrame(df_clusters)
df_clusters = df_clusters.sort_values(by='count', ascending=False).reset_index(drop=True)
# df_clusters['count'].sum() does NOT equal len(gas_spearman): the latter is
# over all non-relaying blocks, the former excludes the Lido cluster skipped
# above, so this is intentionally left unasserted rather than a forgotten check


fig, ax = plt.subplots(nrows=1, ncols=1)

ax.hist(df_clusters['avg_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='AVG(gas_spearman)')
ax.hist(df_clusters['avg_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='AVG(gas_kendall)')

ax.legend()
ax.set_title("Ordering of Transactions for non-relaying proposers (per Cluster)")
fig.savefig("out/ordering_non_pbs-histogram-per-cluster-avg.pdf")

fig, ax = plt.subplots(nrows=1, ncols=1)

ax.hist(df_clusters['min_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='MIN(gas_spearman)')
ax.hist(df_clusters['min_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='MIN(gas_kendall)')

ax.legend()
ax.set_title("Ordering of Transactions for non-relaying proposers (per Cluster)")
fig.savefig("out/ordering_non_pbs-histogram-per-cluster-min.pdf")

fig, ax = plt.subplots(nrows=1, ncols=1)

ax.hist(df_clusters['max_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='MAX(gas_spearman)')
ax.hist(df_clusters['max_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='MAX(gas_kendall)')

ax.legend()
ax.set_title("Ordering of Transactions for non-relaying proposers (per Cluster)")
fig.savefig("out/ordering_non_pbs-histogram-per-cluster-max.pdf")


# generate an html doc
htmlOut = "<!DOCTYPE html><html><head><title>RFC - ordering_non_pbs</title></head><body>\n"

# overview
htmlOut += "<h1>Overview</h1>\n"
htmlOut += f"""
    <table border=1>
        <tr>
            <td><b>Blocks Analysed</b></td>
            <td>{total_number_blocks}</td>
        </tr>
        <tr>
            <td><b>Blocks with meaningful data</b></td>
            <td>{len(gas_spearman)} (spearman)<br>{len(gas_kendall)} (kendall)</td>
        </tr>
        <tr>
            <td><b>Strictly decending blocks</b></td>
            <td>{num_decending_blocks}</td>
        </tr>
        <tr>
            <td><b>Strictly ascending blocks</b></td>
            <td>{num_ascending_blocks}</td>
        </tr>
    </table>    
"""

htmlOut += f"""
    <h1>All Blocks</h1>
    <figure>
        <a href="ordering_non_pbs-histogram.pdf" target="_blank"><img src="ordering_non_pbs-histogram.pdf"></a>
        <figcaption>Histogram over the Spearman/Kendall correlation for all meaningful blocks</figcaption>
    </figure>
"""

htmlOut += f"""
    <h1>Per-Cluster</h1>
    <p>We categorized the blocks into the {len(df_clusters)} clusters (excluding Lido) and took the minimum, average and maximum of the spearman/kendall correlation.</p>
    <figure>
        <a href="ordering_non_pbs-histogram-per-cluster-min.pdf" target="_blank"><img src="ordering_non_pbs-histogram-per-cluster-min.pdf"></a>
        <figcaption>Histogram over the minimum Spearman/Kendall correlation per cluster</figcaption>
    </figure>
    <figure>
        <a href="ordering_non_pbs-histogram-per-cluster-avg.pdf" target="_blank"><img src="ordering_non_pbs-histogram-per-cluster-avg.pdf"></a>
        <figcaption>Histogram over the average Spearman/Kendall correlation per cluster</figcaption>
    </figure>
    <figure>
        <a href="ordering_non_pbs-histogram-per-cluster-max.pdf" target="_blank"><img src="ordering_non_pbs-histogram-per-cluster-max.pdf"></a>
        <figcaption>Histogram over the maximum Spearman/Kendall correlation per cluster</figcaption>
    </figure>
"""

# export df_clusters
htmlOut += "<details><summary>Table of all clusters analyzed</summary>"
htmlOut += df_clusters.to_html(escape=False)
htmlOut += "</details>"

htmlOut += "</body></html>"

with open("out/ordering_non_pbs-overview.html", "w") as file:
    file.write(htmlOut)