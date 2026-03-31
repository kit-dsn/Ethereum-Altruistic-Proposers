"""
Purpose
    Identifies proposers in non-interacting EOA clusters that include
    private transactions (XOF) and exports the proposer lists.
"""

# depends_on: interacting_with_builders.py
import json
import pandas as pd
import numpy as np
from datetime import datetime, UTC
from itertools import chain
from utils.query import query_cache

MAX_PRIVATE_TX_WITHOUT_EXCLUSION = 1

# For the proposers not interacting with builders, which
# do include XOF? And how many?

with open("out/interacting_with_builder.json") as file:
    non_interacting_eoa_clusters = json.load(file)['non_interacting_eoa_clusters']

# fetch blocks with private transactions
df_xof_proposer = query_cache(f"""
    SELECT proposer_index, COUNT(DISTINCT private_blocks.block_number) as blocks_with_xof
        FROM private_blocks
        JOIN coinbase_blocks_all ON
            (private_blocks.block_number = coinbase_blocks_all.block_number)
        WHERE private_blocks.coinbase_addr IN (
                {','.join([f"'{x}'" for x in chain(*non_interacting_eoa_clusters)])}
            ) AND num_private_transactions > {MAX_PRIVATE_TX_WITHOUT_EXCLUSION}
        GROUP BY proposer_index;
""")

# fetch all proposers
df_all_proposers = query_cache(f"""
    SELECT DISTINCT proposer_index
        FROM coinbase_blocks_all
        WHERE coinbase_blocks_all.coinbase_addr IN (
                {','.join([f"'{x}'" for x in chain(*non_interacting_eoa_clusters)])}
            );
""")

print(len(list(df_all_proposers['proposer_index'])))
print(len(list(df_xof_proposer['proposer_index'])))

df_not_xof_proposers = df_all_proposers[~df_all_proposers['proposer_index'].isin(list(df_xof_proposer['proposer_index']))]

# strict altruistic set: proposers with zero private transactions in all their blocks
df_any_private_tx_proposers = query_cache(f"""
    SELECT DISTINCT proposer_index
        FROM private_blocks
        JOIN coinbase_blocks_all ON
            (private_blocks.block_number = coinbase_blocks_all.block_number)
        WHERE private_blocks.coinbase_addr IN (
                {','.join([f"'{x}'" for x in chain(*non_interacting_eoa_clusters)])}
            ) AND num_private_transactions > 0;
""")

df_altruistic_proposers = df_all_proposers[
    ~df_all_proposers['proposer_index'].isin(list(df_any_private_tx_proposers['proposer_index']))
]

print("Not-XOF proposers:", len(df_not_xof_proposers))
print("XOF proposers:", len(df_xof_proposer))
print("Altruistic proposers (0 private tx):", len(df_altruistic_proposers))
print("All proposers:", len(df_all_proposers))

with open('out/including_xof.json', 'w') as file:
    json.dump({
        "including_xof_proposers": list(df_xof_proposer['proposer_index']),
        "not_including_xof_proposers": list(df_not_xof_proposers['proposer_index']),
        "altruistic_proposers": list(df_altruistic_proposers['proposer_index'])
    }, file)