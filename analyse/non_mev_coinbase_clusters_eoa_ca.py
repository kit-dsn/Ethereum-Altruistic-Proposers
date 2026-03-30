"""
Purpose
    Classifies non-relaying coinbase clusters into EOA or contract-address
    groups and summarizes proposer counts and contract types.

Outputs
    out/non_mev_coinbase_clusters_eoa_ca.json
"""

# depends_on: coinbase_clusters.py
import pandas as pd
from itertools import chain
import json
import utils.load
import utils.query

# After we clustered proposers based on sharing coinbase addresses,
# how many of the clusters use EOAs and how many use CAs?

# import clusters
non_relaying_clusters = utils.load.non_relaying_coinbase_clusters()
account_types = utils.query.query_cache(f"""
        SELECT * FROM accounts
        WHERE coinbase_addr IN (
            {','.join([f"'{x}'" for x in chain(*non_relaying_clusters)])}
        );
    """)

eoa_clusters = []
ca_clusters = []
mix = []
for cluster in non_relaying_clusters:
    cluster_account_types = account_types[account_types['coinbase_addr'].isin(cluster)]

    if len(cluster_account_types[cluster_account_types['is_account'] == True]) == len(cluster):
        eoa_clusters.append(cluster)
    elif len(cluster_account_types[cluster_account_types['is_account'] == False]) == len(cluster):
        ca_clusters.append(cluster)
    else:
        mix.append(cluster)

assert len(eoa_clusters) + len(ca_clusters) + len(mix) == len(non_relaying_clusters)

# there are two clusters where proposers used both CAs and EOAs as coinbase addresses
# decision: the proposers that sometimes use CAs should be grouped with CAs
ca_clusters += mix

assert len(eoa_clusters) + len(ca_clusters) == len(non_relaying_clusters)
assert set(chain(*(eoa_clusters + ca_clusters))) == set(chain(*non_relaying_clusters))

# load proposer sizes
proposer_coinbases = utils.load.non_relaying_clusters_proposer_coinbase()
eoa_proposers = proposer_coinbases[proposer_coinbases['coinbase_addr'].isin(chain(*eoa_clusters))]
ca_proposers = proposer_coinbases[proposer_coinbases['coinbase_addr'].isin(chain(*ca_clusters))]

print(len(eoa_proposers['coinbase_addr'].unique()), len(list(chain(*eoa_clusters))))

assert eoa_proposers['proposer_index'].isin(ca_proposers['proposer_index']).any() == False # make sure proposers are distinct
assert ca_proposers['proposer_index'].isin(eoa_proposers['proposer_index']).any() == False

print(f"EOA: {len(eoa_clusters)} clusters / {len(eoa_proposers)} proposers")
print(f"CA: {len(ca_clusters)} clusters / {len(ca_proposers)} proposers")
print(f"MIX: {len(mix)} (in CA included)")

# associate ca coinbase addresses with Patrick's analysis:
with open('analyse/non_mev_coinbase_clusters_eoa_ca-ca-analysis-patrick.json') as file:
    ca_analysis = json.load(file)


ca_contract_types = []
for ca in ca_analysis:
    df = proposer_coinbases[proposer_coinbases['coinbase_addr'].isin(ca['coinbase_addr'])]
    assert df['coinbase_addr'].isin(chain(*ca_clusters)).all()

    ca_contract_types.append({
        "name": ca['name'],
        "num_blocks": df['count'].sum(),
        "num_proposers": len(df['proposer_index'].unique())
    })

ca_contract_types = pd.DataFrame(ca_contract_types)
ca_contract_types = ca_contract_types[ca_contract_types['num_blocks'] > 0].reset_index(drop=True)
ca_contract_types = ca_contract_types.sort_values('num_blocks', ascending=False)

# from the "mix", we inserted two coinbase addresses that
# were EOAs, which of course cannot have a contract type
# assert ca_contract_types['num_proposers'].sum() == len(ca_proposers[~ca_proposers['coinbase_addr'].isin(['0xedfadca29b47fe199916bdae4b784d29b158c7dc','0x71efe79d37b30b2881416c5dfb0fe4c715dac2f6'])])

with open("out/non_mev_coinbase_clusters_eoa_ca.json", 'w') as file:
    json.dump({
        "eoa_clusters": eoa_clusters,
        "eoa_proposers": eoa_proposers.to_dict('records'),
        "ca_clusters": ca_clusters,
        "ca_proposers": ca_proposers.to_dict('records'),
        "ca_contract_types": ca_contract_types.to_dict('records')
    }, file)