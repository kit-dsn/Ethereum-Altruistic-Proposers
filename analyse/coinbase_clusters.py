"""
Purpose
    Builds clusters of coinbase addresses among non-relaying proposers and
    exports proposer-coinbase counts.
"""

# depends_on: proposer_collaboration.py
import utils.query
from collections import defaultdict
import networkx as nx
import pandas as pd
import itertools
import json


# fetch all coinbase addresses and the associated number of blocks and relay blocks
df_coinbases = utils.query.query_cache(f"""
        SELECT
            coinbase_addr,
            COUNT(DISTINCT a.block_number) as count,
            COUNT(DISTINCT b.block_number) as relay_count
        FROM
        (
            SELECT
                proposer_index,
                block_number,
                slot,
                coinbase_addr
            FROM coinbase_blocks_all
        ) a
        LEFT JOIN (
            SELECT 
                DISTINCT coinbase_blocks_all.block_number 
            FROM relay_all 
            INNER JOIN coinbase_blocks_all 
            ON 
                (relay_all.slot = coinbase_blocks_all.slot 
                    AND relay_all.block_number = coinbase_blocks_all.block_number)
        ) b ON (a.block_number = b.block_number)
        GROUP BY a.coinbase_addr
        ORDER BY count DESC
    """)

df_no_relaying_coinbases = df_coinbases[df_coinbases['relay_count'] == 0]

# fetch all proposers that used non-relaying-coinbase-addresses
proposers_using_non_relaying_coinbase = utils.query.query_cache(f"""
    SELECT
        DISTINCT proposer_index, coinbase_addr
    FROM coinbase_blocks_all
    WHERE coinbase_addr IN (
        {','.join([f"'{x}'" for x in df_no_relaying_coinbases['coinbase_addr']])}
    )
""")

assert len(proposers_using_non_relaying_coinbase['coinbase_addr'].unique()) == len(df_no_relaying_coinbases)

# fetch all coinbases these proposers used
proposer_coinbases = utils.query.query_cache(f"""
    SELECT DISTINCT proposer_index, coinbase_addr
    FROM coinbase_blocks_all
    WHERE proposer_index IN (
        {','.join([str(x) for x in proposers_using_non_relaying_coinbase['proposer_index']])}
    )
""")

# make clusters
proposers_to_coinbase = defaultdict(set)
for _, row in proposer_coinbases.iterrows():
    proposers_to_coinbase[row['proposer_index']].add(row['coinbase_addr'])

graph = nx.Graph()
for a in proposer_coinbases['coinbase_addr'].unique():
    graph.add_node(a)

for coinbases in proposers_to_coinbase.values():
    coinbases = list(coinbases)
    if len(coinbases) > 1:
        for i in range(len(coinbases)):
            for j in range(i+1, len(coinbases)):
                graph.add_edge(coinbases[i], coinbases[j])

clusters = [] # only coinbase-addresses
for idx, cluster in enumerate(nx.connected_components(graph)):
    cluster = list(cluster)
    clusters.append(cluster)

# go through all clusters, and check if they are still completely non-relaying...?
non_relaying_clusters = []
for cluster in clusters:
    if set(cluster) <= set(df_no_relaying_coinbases['coinbase_addr']):
        non_relaying_clusters.append(cluster)
    
# check again all non-relaying clusters:
with utils.query.engine.connect() as connection:
    for cluster in non_relaying_clusters:
        df = pd.read_sql(f"""
            SELECT COUNT(*) 
                FROM coinbase_blocks_all
            INNER JOIN
                relay_all
            ON (coinbase_blocks_all.block_number = relay_all.block_number AND coinbase_blocks_all.slot = relay_all.slot)
            WHERE
                coinbase_addr IN (
                    {','.join([f"'{x}'" for x in cluster])}
                );
        """, connection)
        assert df.iloc[0]['count'] == 0

    all_non_relaying_coinbases = list(itertools.chain(*non_relaying_clusters))
    all_relaying_coinbases = df_coinbases[~df_coinbases['coinbase_addr'].isin(all_non_relaying_coinbases)]
    assert len(all_non_relaying_coinbases) + len(all_relaying_coinbases) == len(df_coinbases)


with open('out/coinbase_clusters-non-relaying-clusters.json', 'w') as file:
    out = json.dumps(non_relaying_clusters)
    file.write(out)

# generate 'proposer-coinbase' data
df_proposer_coinbase = utils.query.query_cache(f"""
    SELECT
        proposer_index,
        coinbase_addr,
        COUNT(coinbase_blocks_all.block_number) as count,
        COUNT(relay_all) as relay_count
    FROM coinbase_blocks_all
    LEFT JOIN relay_all
    ON (coinbase_blocks_all.block_number = relay_all.block_number AND coinbase_blocks_all.slot = relay_all.slot)
    WHERE coinbase_addr IN (
        {','.join([f"'{x}'" for x in all_non_relaying_coinbases])}
    )
    GROUP BY proposer_index, coinbase_addr
""")

assert len(df_proposer_coinbase[df_proposer_coinbase['relay_count'] > 0]) == 0
assert df_proposer_coinbase["count"].sum() == df_coinbases[df_coinbases['coinbase_addr'].isin(all_non_relaying_coinbases)]["count"].sum()

# check against our list of non-relaying proposers
with open("out/proposer_collaboration-overview.json") as file:
    df = pd.DataFrame.from_dict(json.load(file)['non_relaying_proposers'])
    assert df_proposer_coinbase['proposer_index'].isin(df['proposer_index']).all()

# check that number of blocks matches for each coinbase addr
for coinbase_addr in all_non_relaying_coinbases:
    assert df_proposer_coinbase[df_proposer_coinbase['coinbase_addr'] == coinbase_addr]['count'].sum() == df_coinbases[df_coinbases['coinbase_addr'] == coinbase_addr].iloc[0]['count']

df_proposer_coinbase.to_json("out/coinbase_clusters-non-relaying-proposer-coinbase.json")