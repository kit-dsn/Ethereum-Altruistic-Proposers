# depends_on: including_xof.py
import utils.query
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from itertools import chain
import json


# Do the proposers that
# - do not use MEV-Boost
# - use EOAs as coinbase addresses
# - don't interact with builders 
# - and not include private transactions
# reorder their transactions? Or are their transactions strictly ordered?

with open("out/including_xof.json") as file:
    not_including_xof_clusters = json.load(file)['not_including_xof_clusters']


df_strictly_ordered = utils.query.query_cache(f"""
    SELECT 
        coinbase_addr,
        COUNT(DISTINCT block_number) as block_count,
        COUNT(DISTINCT block_number) FILTER (WHERE gas_decending = 'true' AND gas_ascending = 'false') as strictly_decending_blocks,
        COUNT(DISTINCT block_number) FILTER (WHERE gas_ascending = 'true' AND gas_decending = 'false') as strictly_ascending_blocks,
        COUNT(DISTINCT block_number) FILTER (WHERE gas_ascending = 'true' AND gas_decending = 'true') as empty_blocks
    FROM
        analyse_blocks3
    WHERE
        coinbase_addr IN (
            {','.join([f"'{x}'" for x in chain(*not_including_xof_clusters)])}
        )
    GROUP BY coinbase_addr
    ORDER BY block_count DESC;
""")


df_strictly_decending = df_strictly_ordered[df_strictly_ordered['block_count'] == df_strictly_ordered['strictly_decending_blocks']]
df_empty_blocks = df_strictly_ordered[df_strictly_ordered['block_count'] == df_strictly_ordered['empty_blocks']]

strictly_decending_clusters = []
empty_block_publisher = []
remaining_clusters = []
for c in not_including_xof_clusters:
    if df_strictly_decending['coinbase_addr'].isin(c).any():
        strictly_decending_clusters.append(c)
    elif df_empty_blocks['coinbase_addr'].isin(c).any():
        empty_block_publisher.append(c)
    else:
        remaining_clusters.append(c)

assert len(strictly_decending_clusters) + len(empty_block_publisher) + len(remaining_clusters) == len(not_including_xof_clusters)
assert set(chain(*strictly_decending_clusters)) & set(chain(*not_including_xof_clusters)) == set(chain(*strictly_decending_clusters))
assert set(chain(*empty_block_publisher)) & set(chain(*not_including_xof_clusters)) == set(chain(*empty_block_publisher))
assert set(chain(*remaining_clusters)) & set(chain(*not_including_xof_clusters)) == set(chain(*remaining_clusters))
assert set(chain(*strictly_decending_clusters)) & set(chain(*empty_block_publisher)) == set()
assert set(chain(*strictly_decending_clusters)) & set(chain(*remaining_clusters)) == set()
assert set(chain(*empty_block_publisher)) & set(chain(*remaining_clusters)) == set()

# let's look at the min/avg/max distribution of gas_price
# in the remaining clusters

df_remaining_correlation_coinbase = utils.query.query_cache(f"""
        SELECT 
            coinbase_addr,
            COUNT(*) as count,
            MIN(gas_spearman) as min_spearman, 
            AVG(gas_spearman) as avg_spearman, 
            MAX(gas_spearman) as max_spearman, 
            MIN(gas_kendall) as min_kendall, 
            AVG(gas_kendall) as avg_kendall, 
            MAX(gas_kendall) as max_kendall
        FROM analyse_blocks3
        WHERE coinbase_addr IN (
            {','.join([f"'{x}'" for x in chain(*remaining_clusters)])}
        )
        AND (gas_decending = 'false' OR gas_ascending = 'false')
        GROUP BY coinbase_addr
    """)

df_remaining_correlation_clusters = []
for cluster in remaining_clusters:
    df_cluster = df_remaining_correlation_coinbase[df_remaining_correlation_coinbase.apply(lambda x: x['coinbase_addr'] in cluster, axis=1)].copy()
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

    df_remaining_correlation_clusters.append(df)


df_remaining_correlation_clusters = pd.DataFrame(df_remaining_correlation_clusters)
df_remaining_correlation_clusters = df_remaining_correlation_clusters.sort_values(by='count', ascending=False).reset_index(drop=True)

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.hist(df_remaining_correlation_clusters['avg_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='AVG(gas_spearman)')
ax.hist(df_remaining_correlation_clusters['avg_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='AVG(gas_kendall)')
ax.legend()
ax.set_title("Ordering of Transactions for 'remaining' (per Cluster)")
fig.savefig("out/ordering_clusters-remaining-avg.png")

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.hist(df_remaining_correlation_clusters['min_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='MIN(gas_spearman)')
ax.hist(df_remaining_correlation_clusters['min_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='MIN(gas_kendall)')
ax.legend()
ax.set_title("Ordering of Transactions for 'remaining' (per Cluster)")
fig.savefig("out/ordering_clusters-remaining-min.png")

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.hist(df_remaining_correlation_clusters['max_spearman'], range=(-1,1), bins=100, color='red', histtype='step', label='MAX(gas_spearman)')
ax.hist(df_remaining_correlation_clusters['max_kendall'], range=(-1,1), bins=100, color='blue', histtype='step', label='MAX(gas_kendall)')
ax.legend()
ax.set_title("Ordering of Transactions for 'remaining' (per Cluster)")
fig.savefig("out/ordering_clusters-remaining-max.png")


with open('out/ordering_clusters.json', 'w') as file:
    json.dump({
        "strictly_decending_clusters": strictly_decending_clusters,
        "empty_block_publisher": empty_block_publisher,
        "remaining_clusters": remaining_clusters,
        "df_remaining_correlation_clusters": df_remaining_correlation_clusters.to_dict('records')
    }, file)