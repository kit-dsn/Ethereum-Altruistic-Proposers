# depends_on: proposer_collaboration.py,proposer_clusters.py
import pandas as pd
import json
import utils.query
import os.path

# which extra data do non-relaying proposers use?

if not os.path.isfile('out/proposer_extra_data-overall.json'):
    df_proposer_coinbase = pd.read_json('out/proposer_collaboration-no-relaying-proposer-coinbase.json')
    coinbase_clusters = []
    with open('out/proposer_clusters-non-relaying-clusters.json') as file:
        coinbase_clusters = json.load(file)

    results = []
    for cluster in coinbase_clusters:
        df = utils.query.query_cache(f"""
            SELECT block_number, extra_data, proposer_index
            FROM coinbase_blocks_all
            WHERE 
                coinbase_addr IN ({','.join([f"'{x}'" for x in cluster])})
            AND
                proposer_index IN (
                    {','.join(
                        df_proposer_coinbase[df_proposer_coinbase['coinbase_addr'].apply(lambda x: x in cluster)]['proposer_index'].apply(lambda x: str(x))
                    )}
                )
        """)

        # print(len(df['proposer_index'].unique()))
        # print(df.groupby('extra_data')['proposer_index'].unique().apply(lambda x: len(x)).sum())

        results.append(
            [
                cluster,
                len(df['proposer_index'].unique()),
                len(df['extra_data'].unique()),
                len(df['block_number'].unique())
            ]
        )

    result_df = pd.DataFrame(data=results, columns=["cluster", "num_proposers", "num_extra_data", "num_blocks"])
    result_df.to_json("out/proposer_extra_data-overall.json")
else: 
    result_df = pd.read_json('out/proposer_extra_data-overall.json')

print(result_df[result_df['num_proposers'] > 1].sort_values(by='num_proposers', ascending=False)) 