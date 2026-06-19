"""
Purpose
    Builds clusters of coinbase addresses among non-relaying proposers and
    exports proposer-coinbase counts.

Background
    A proposer that never lets its fee recipient (coinbase) show up in a
    relay's bids is not necessarily building its own blocks - it may simply
    be rotating between several private coinbase addresses while still
    delegating construction to an external builder/relay off the record.
    To tell the two apart we connect coinbase addresses that were ever paid
    out to the same proposer into a graph and treat connected components as
    one entity ("cluster"). A cluster only counts as genuinely non-relaying
    if every address in it is non-relaying - a single relayed address pulls
    the whole cluster (and thus the proposer) back into the "delegates to a
    relay" bucket.
"""

# depends_on: proposer_collaboration.py
import utils.query
from collections import defaultdict
import networkx as nx
import pandas as pd
import itertools
import json


# Block count and relay-block count per coinbase address, used below to split
# addresses into "ever seen in a relay bid" vs. "never seen in a relay bid".
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

# proposers that ever used at least one of these non-relaying addresses -
# the starting point for the cluster graph below
proposers_using_non_relaying_coinbase = utils.query.query_cache(f"""
    SELECT
        DISTINCT proposer_index, coinbase_addr
    FROM coinbase_blocks_all
    WHERE coinbase_addr IN (
        {','.join([f"'{x}'" for x in df_no_relaying_coinbases['coinbase_addr']])}
    )
""")

assert len(proposers_using_non_relaying_coinbase['coinbase_addr'].unique()) == len(df_no_relaying_coinbases)

# every coinbase address these proposers have *ever* used, relaying or not -
# this is what gets connected into clusters below
proposer_coinbases = utils.query.query_cache(f"""
    SELECT DISTINCT proposer_index, coinbase_addr
    FROM coinbase_blocks_all
    WHERE proposer_index IN (
        {','.join([str(x) for x in proposers_using_non_relaying_coinbase['proposer_index']])}
    )
""")

# Union-find via networkx: two coinbase addresses are linked if the same
# proposer was ever paid out to both of them.
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
for cluster in nx.connected_components(graph):
    clusters.append(sorted(cluster))

# Keep only clusters where EVERY address is non-relaying. A cluster that
# also contains a relaying address means the proposer(s) behind it do
# delegate to a relay at least some of the time, so the whole cluster is
# disqualified, not just the relaying address.
non_relaying_clusters = []
for cluster in clusters:
    if set(cluster) <= set(df_no_relaying_coinbases['coinbase_addr']):
        non_relaying_clusters.append(cluster)

# Manual cross-check (inspected during development, not asserted here): re-run
# the relay join per surviving cluster and confirm the count comes back zero.
for cluster in non_relaying_clusters:
    df = utils.query.conn.execute(f"""
        SELECT COUNT(*) as count
            FROM coinbase_blocks_all
        INNER JOIN
            relay_all
        ON (coinbase_blocks_all.block_number = relay_all.block_number AND coinbase_blocks_all.slot = relay_all.slot)
        WHERE
            coinbase_addr IN (
                {','.join([f"'{x}'" for x in cluster])}
            );
    """).df()

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

with open("out/proposer_collaboration-overview.json") as file:
    df = pd.DataFrame.from_dict(json.load(file)['non_relaying_proposers'])

df_proposer_coinbase.to_json("out/coinbase_clusters-non-relaying-proposer-coinbase.json")