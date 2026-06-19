"""
Purpose
    Builds connections between coinbase addresses used by non-relaying
    proposers, producing clusters.

Background
    Same clustering idea as coinbase_clusters.py (connect coinbase addresses
    sharing a proposer, take connected components), applied here to the
    never-relaying proposer set from proposer_collaboration.py instead of
    the broader non-relaying-coinbase set. ordering_non_pbs.py and
    private_transactions_clusters.py both treat the first entry of the
    exported cluster list as a known large entity (Lido) and skip it -
    the cluster ORDER is stable across runs (it follows the DataFrame's
    column order, not a hashed set), only the address order WITHIN each
    cluster is sorted below for the same reason as in coinbase_clusters.py.
"""

# depends_on: proposer_collaboration.py
import networkx as nx
from collections import defaultdict
import pandas as pd
import numpy as np
import json


# How many validator groups are there?
df = pd.read_json('out/proposer_collaboration-no-relaying-proposer-coinbase.json')

proposer_to_coinbase = defaultdict(set)
for _, row in df[['proposer_index', 'coinbase_addr']].iterrows():
    proposer_to_coinbase[row['proposer_index']].add(row['coinbase_addr'])

graph = nx.Graph()
for a in df['coinbase_addr'].unique():
    graph.add_node(a)

for coinbases in proposer_to_coinbase.values():
    coinbases = list(coinbases)
    if len(coinbases) > 1:
        for i in range(len(coinbases)):
            for j in range(i+1, len(coinbases)):
                graph.add_edge(coinbases[i], coinbases[j])

con_components = nx.connected_components(graph)

results = [] # dataframes
clusters = [] # only coinbase-addresses
for idx, cluster in enumerate(con_components):
    # sort: connected_components yields a plain set, whose iteration order is
    # subject to Python's hash-seed randomization for strings
    cluster = sorted(cluster)
    clusters.append(cluster)
    if len(cluster) > 1:
        print(f"Cluster {idx}: {cluster}")
        for addr in cluster:
            results.append(df[df["coinbase_addr"] == addr])

# some statistics
results = pd.concat(results)
print(results['count'].sum(), df['count'].sum()) # number of blocks
print(len(results['proposer_index'].unique()), len(df['proposer_index'].unique())) # number of proposers

# export cluster
with open('out/proposer_clusters-non-relaying-clusters.json', 'w') as file:
    out = json.dumps(clusters)
    file.write(out)