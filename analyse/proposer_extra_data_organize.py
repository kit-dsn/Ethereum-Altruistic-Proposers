# depends_on: proposer_extra_data.py
import pandas as pd
import os
import json
import utils.query

# this script tries to detect a 'global' pattern
# of extra data within the clusters

result = {'other': [], 'global': [], 'global_patterns': []}

i = 0 # current cluster index
while os.path.exists(f"out/proposer_extra_data/coinbase-{i}.json"):
    
    with open(f"out/proposer_extra_data/coinbase-{i}.json") as file:
        data = json.load(file)

        # cluster = coinbase addrs of the cluster (might be multiple ones)
        cluster = data['cluster']
        # blocks = produced blocks
        blocks = pd.DataFrame(data['blocks']).drop('index', axis=1)
        blocks = blocks.sort_values(by='block_number')

        # when did the extra_data change when we sort over block_number?
        changes = blocks['extra_data'].ne(blocks['extra_data'].shift()).cumsum()
        changes = blocks.groupby(changes).apply(lambda g: 
            pd.Series({
                "start_block": g.iloc[0]['block_number'], 
                "end_block": g.iloc[-1]['block_number'], 
                "extra_data": g['extra_data'].iloc[0]
            })
        ).reset_index(drop=True)

    
        # when number changes equals number of extra_data values
        # then we have a 'global' pattern (i.e., each extra_data value has a 'timeframe')
        if len(changes) == len(blocks['extra_data'].unique()):
            result['global'].append(i)
            result['global_patterns'].append(changes)
        else:
            result['other'].append(i)

    i += 1

print(f"Analyzed {len(result['global']) + len(result['other'])} clusters.")
print(f"{len(result['global'])} have a global pattern: {result['global']}")
print(f"{len(result['other'])} have an unknown pattern: {result['other']}")

with open("out/proposer_extra_data_organize-categories.json", "w") as file:
    file.write(json.dumps({
        "global": result['global'],
        "other": result['other'],
        "global_patterns": [x.to_dict('records') for x in result['global_patterns']]
    }))

# take a look at the global patterns...

all_patterns = pd.concat(result['global_patterns'])
all_patterns["pattern_index"] = (all_patterns.index == 0).cumsum()
all_patterns = all_patterns.reset_index(drop=True)

all_follow_ups = []

## in which patterns did the extra_data appear?
##print(all_patterns.groupby(by="extra_data")['pattern_index'].unique().apply(lambda x: len(x)).sort_values(ascending=False))
##pidx = list(all_patterns[all_patterns['extra_data'] == extra_data]['pattern_index'].unique())

for extra_data in all_patterns['extra_data'].unique():
    # what extra_data did follow?
    all_patterns['next_extra_data'] = all_patterns['extra_data'].shift(-1)
    all_patterns['next_index'] = all_patterns['pattern_index'].shift(-1)
    all_patterns.loc[all_patterns['pattern_index'] != all_patterns['next_index'], 'next_extra_data'] = None
    all_patterns.drop(columns="next_index", inplace=True)

    followups = all_patterns[all_patterns['extra_data'] == extra_data].groupby(by='next_extra_data')["extra_data"].count()
    followups = followups.sort_values(ascending=False)
    
    if len(followups) > 1:
        # print(extra_data, followups.index[0], followups.iloc[0])
        followups = followups.reset_index()
        followups.columns = ["next_extra_data", "count"]
        followups["extra_data"] = extra_data

        all_follow_ups.append(followups)

all_follow_ups = pd.concat(all_follow_ups)
print(all_follow_ups[all_follow_ups["count"] > 2].sort_values(by="count", ascending=False))

all_follow_ups.reset_index(drop=True).to_json('out/proposer_extra_data_organize-follow-ups.json')

# did the extra_data appear in other blocks?
# did they appear in other clusters?

non_relaying_proposers = pd.read_json('out/proposer_collaboration-no-relaying-proposer-coinbase.json')['proposer_index'].unique()

extra_data_otherwise = []
for extra_data in all_patterns['extra_data'].unique():
    res = utils.query.query_cache(f"""
        SELECT * FROM (
            SELECT COUNT(*) as non_relaying_blocks FROM coinbase_blocks_all
            WHERE 
                extra_data = '{extra_data}' 
            AND
                proposer_index IN (
                    {','.join([str(x) for x in non_relaying_proposers])}
                )
        ), (
            SELECT COUNT(*) as all_blocks FROM coinbase_blocks_all
            WHERE extra_data = '{extra_data}'
        )
    """)
    
    pidxs = all_patterns[all_patterns['extra_data'] == extra_data]['pattern_index'].unique()
    clusters = []
    for pidx in pidxs:
        with open(f'out/proposer_extra_data/coinbase-{pidx}.json') as file:
            clusters.append(json.load(file)['cluster'])

    extra_data_otherwise.append({
        "extra_data": extra_data,
        "only_non_relaying_validators": res.iloc[0]['non_relaying_blocks'] == res.iloc[0]['all_blocks'],
        "total_blocks": res.iloc[0]['all_blocks'],
        "total_blocks_from_non_relaying_validators": res.iloc[0]['non_relaying_blocks'],
        "total_non_relaying_coinbase_clusters": all_patterns[all_patterns['extra_data'] == extra_data]['pattern_index'].count(),
        "clusters": clusters
    })
    
extra_data_otherwise = pd.DataFrame(extra_data_otherwise)
extra_data_otherwise = extra_data_otherwise.sort_values(by='total_blocks_from_non_relaying_validators', ascending=False)
print(extra_data_otherwise)

extra_data_otherwise.to_json('out/proposer_extra_data_organize-extra-data-otherwise.json')