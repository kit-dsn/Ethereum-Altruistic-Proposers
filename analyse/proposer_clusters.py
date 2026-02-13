"""
Purpose
    Builds connections betweencoinbase addresses used by non-relaying
    proposers, producing cluster.

Usage
    python3 analyse/proposer_clusters.py
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
    cluster = list(cluster)
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