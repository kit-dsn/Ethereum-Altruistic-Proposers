"""
Purpose
    Analyse whether proposer deposit addresses match coinbase clusters.

Usage
    python3 analyse/proposer_deposit.py

Outputs
    out/proposer_deposit-results.json
"""

# depends_on: proposer_clusters.py,proposer_collaboration.py,proposer_clusters_merged.py
from itertools import chain
import utils.query
import pandas as pd
import json

# get clusters
with open("out/proposer_clusters_merged.json") as file:
    f = json.load(file)
    non_relaying_clusters = f['clusters']
    non_relaying_clusters_proposer = f['proposers']

# how many clusters have proposers that used the coinbase addr
# to deposit their funds?

def fetch_deposit_addr(proposer_idxs):
    return list(utils.query.query_cache(f"""
        SELECT DISTINCT from_address FROM validator_deposits
        WHERE proposer_index IN (
            {','.join([str(x) for x in proposer_idxs])}
        )
    """)['from_address'])

matches = []
partial_matches = []
for idx, c in enumerate(non_relaying_clusters):
    proposers = non_relaying_clusters_proposer[idx]
    deposit_addrs = fetch_deposit_addr(proposers)

    if c == deposit_addrs:
        matches.append(c)
    
    for ca in c:
        if ca in deposit_addrs:
            partial_matches.append(c)
            break

for m in matches:
    assert m in partial_matches

print("Full Matches: ", len(matches))
print("Partial Matches: ", len(partial_matches))

with open("out/proposer_deposit-results.json", 'w') as file:
    file.write(json.dumps({
        "full-matches": matches,
        "partial-matches": partial_matches
    }))