import utils.query
from collections import defaultdict
import networkx as nx


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

con_components = nx.connected_components(graph)

clusters = [] # only coinbase-addresses
for idx, cluster in enumerate(con_components):
    cluster = list(cluster)
    clusters.append(cluster)
    if len(cluster) > 1:
        print(f"Cluster {idx}: {cluster}")