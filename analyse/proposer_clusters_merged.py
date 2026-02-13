"""
Purpose
    Maps non-relaying coinbase clusters to their associated proposers and
    exports merged cluster-proposer lists.

Outputs
    out/proposer_clusters_merged.json
"""

# depends_on: proposer_clusters.py,proposer_collaboration.py
import pandas as pd
import json
from itertools import chain

# get clusters
with open("out/proposer_clusters-non-relaying-clusters.json") as file:
    non_relaying_clusters = json.load(file)

# get associated proposers
non_relaying_proposers = pd.read_json("out/proposer_collaboration-no-relaying-proposer-coinbase.json")

non_relaying_clusters_proposer = []
for idx, c in enumerate(non_relaying_clusters):
    p = set()
    for ca in c:
        p.update(list(non_relaying_proposers[non_relaying_proposers['coinbase_addr'] == ca]['proposer_index']))
    
    non_relaying_clusters_proposer.append(list(p))

# make sure that no proposer appears double
assert len(list(chain(*(non_relaying_clusters_proposer)))) == len(non_relaying_proposers['proposer_index'].unique())
assert len(non_relaying_clusters_proposer) == len(non_relaying_clusters)

with open("out/proposer_clusters_merged.json", 'w') as file:
    file.write(json.dumps({
        'clusters': non_relaying_clusters,
        'proposers': non_relaying_clusters_proposer
    }))