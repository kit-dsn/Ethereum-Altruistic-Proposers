# depends_on: interacting_with_builders.py
import json
import pandas as pd
import numpy as np
from datetime import datetime, UTC
from itertools import chain
from utils.query import query_cache

# For the EOA-proposers not interacting with builders, which
# clusters do include XOF? And how many?

with open("out/interacting_with_builder.json") as file:
    non_interacting_eoa_clusters = json.load(file)['non_interacting_eoa_clusters']

# fetch all coinbase_addr which issued blocks with private transactions
df_xof_coinbases = query_cache(f"""
    SELECT DISTINCT coinbase_addr, COUNT(DISTINCT block_number) as blocks_with_xof
    FROM private_blocks
    WHERE coinbase_addr IN (
        {','.join([f"'{x}'" for x in chain(*non_interacting_eoa_clusters)])}
    ) AND num_private_transactions > 0
    GROUP BY coinbase_addr
    ORDER BY blocks_with_xof DESC;
""")

# go throuh all clusters
not_including_xof_clusters = []
including_xof_clusters = []
for c in non_interacting_eoa_clusters:
    if not df_xof_coinbases['coinbase_addr'].isin(c).any():
        not_including_xof_clusters.append(c)
    else:
        including_xof_clusters.append(c)
    
assert len(not_including_xof_clusters) + len(including_xof_clusters) == len(non_interacting_eoa_clusters)
assert set(chain(*including_xof_clusters)) & set(chain(*non_interacting_eoa_clusters)) == set(chain(*including_xof_clusters))
assert set(chain(*not_including_xof_clusters)) & set(chain(*non_interacting_eoa_clusters)) == set(chain(*not_including_xof_clusters))
assert set(chain(*not_including_xof_clusters)) & set(chain(*including_xof_clusters)) == set()

# Take a short look into the private transactions — where does the ether go to/from?
xof_transaction_adresses = query_cache(f"""
    SELECT addr_from, addr_to, COUNT(*)
    FROM mempool_private
    INNER JOIN coinbase_blocks_all
    ON (mempool_private.block_number = coinbase_blocks_all.block_number)
    WHERE coinbase_addr IN (
        {','.join([f"'{x}'" for x in chain(*including_xof_clusters)])}
    )
    GROUP BY addr_from, addr_to
    ORDER BY count DESC;
""")


with open("analyse/interacting_with_builders-builder-addrs.json") as file:
    builder_addr = json.load(file)

# the dataset should already exclude proposers with private transactions to builders!
assert len(xof_transaction_adresses[xof_transaction_adresses['addr_from'].isin(builder_addr) | xof_transaction_adresses['addr_to'].isin(builder_addr)]) == 0

# how many clusters would we still include if we allow
# private transactions that transfer Ether to oneself?
xof_without_self_transactions_coinbases = query_cache(f"""
    SELECT coinbase_addr, COUNT(DISTINCT coinbase_blocks_all.block_number) as block_count
    FROM mempool_private
    INNER JOIN coinbase_blocks_all
    ON (mempool_private.block_number = coinbase_blocks_all.block_number)
    WHERE coinbase_addr IN (
        {','.join([f"'{x}'" for x in chain(*including_xof_clusters)])}
    ) AND addr_from != addr_to
    GROUP BY coinbase_addr
    ORDER BY block_count DESC;
""")
not_including_xof_and_self_transactions_clusters = []
for c in non_interacting_eoa_clusters:
    if not xof_without_self_transactions_coinbases['coinbase_addr'].isin(c).any():
        not_including_xof_and_self_transactions_clusters.append(c)

assert set(chain(*not_including_xof_clusters)) & set(chain(*not_including_xof_and_self_transactions_clusters)) == set(chain(*not_including_xof_clusters))
assert set(chain(*not_including_xof_clusters)) | set(chain(*not_including_xof_and_self_transactions_clusters)) == set(chain(*not_including_xof_and_self_transactions_clusters))

only_self_transactions_clusters = [x for x in not_including_xof_and_self_transactions_clusters if x not in not_including_xof_clusters]

assert set(chain(*only_self_transactions_clusters)) & set(chain(*not_including_xof_clusters)) == set()

with open('out/including_xof.json', 'w') as file:
    json.dump({
        "including_xof_clusters": including_xof_clusters,
        "not_including_xof_clusters": not_including_xof_clusters,
        "xof_coinbases": df_xof_coinbases.to_dict('records'),
        "xof_transaction_addresses": xof_transaction_adresses.to_dict('records'),
        "xof_only_self_transactions_clusters": only_self_transactions_clusters
    }, file)