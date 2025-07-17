# depends_on: proposer_collaboration.py,proposer_clusters.py
import pandas as pd
import json
import utils.query
import os.path
import matplotlib.pyplot as plt
import numpy as np
from binascii import crc32

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
    df_proposer_coinbase = pd.read_json('out/proposer_collaboration-no-relaying-proposer-coinbase.json')
    result_df = pd.read_json('out/proposer_extra_data-overall.json')


# draw a scatterplot with changes of extra_data
# df = result_df[result_df['num_blocks'] > 50].sort_values(by='num_proposers', ascending=False)
df = result_df[result_df['num_proposers'] > 1][result_df['num_extra_data'] > 1][result_df['num_extra_data'] != result_df['num_proposers']]
df = df.sort_values(by='num_proposers', ascending=False)
df = df.reset_index(drop=True)

items = []

for index,row in df.iterrows():
    row_df = utils.query.query_cache(f"""
            SELECT block_number, extra_data, proposer_index
            FROM coinbase_blocks_all
            WHERE 
                coinbase_addr IN ({','.join([f"'{x}'" for x in row['cluster']])})
            AND
                proposer_index IN (
                    {','.join(
                        df_proposer_coinbase[df_proposer_coinbase['coinbase_addr'].apply(lambda x: x in row['cluster'])]['proposer_index'].apply(lambda x: str(x))
                    )}
                )
    """)

    row_df = row_df.sort_values(by='block_number', ascending=True)

    proposers = sorted(row_df['proposer_index'].unique().tolist())
    index_items = []
    for _,block_row in row_df.iterrows():
        index_items.append({"index": index, "block_number": block_row['block_number'], "proposer": proposers.index(block_row['proposer_index']), "extra_data": block_row['extra_data']})

    items.append(index_items)

for index, blocks in enumerate(items):
    X = np.array([d['block_number'] for d in blocks])
    Y = np.array([d['proposer'] for d in blocks])

    # copied from https://github.com/dimostenis/color-hash-python/blob/main/src/colorhash/colorhash.py
    # licensed under MIT
    def colorhash(data):
        lightness = (0.35, 0.5, 0.65)
        saturation = (0.45, 0.5, 0.65)

        hash_val = crc32(str(data).encode('utf-8')) & 0xFFFFFFFF
        h = hash_val % 359
        hash_val //= 360
        s = saturation[hash_val % len(saturation)]
        hash_val //= len(saturation)
        l = lightness[hash_val % len(lightness)]

        h /= 360

        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q

        def hue_to_rgb(p: float, q: float, t: float):
            if t < 0:
                t += 1
            elif t > 1:
                t -= 1

            if t < 1 / 6:
                return p + (q - p) * 6 * t
            if t < 1 / 2:
                return q
            if t < 2 / 3:
                return p + (q - p) * (2 / 3 - t) * 6
            return p

        r = round(hue_to_rgb(p, q, h + 1 / 3) * 255)
        g = round(hue_to_rgb(p, q, h) * 255)
        b = round(hue_to_rgb(p, q, h - 1 / 3) * 255)

        return "#{:02x}{:02x}{:02x}".format(*(r,g,b))


    C = [colorhash(d['extra_data']) for d in blocks]

    # generate scatter plot
    fig, ax = plt.subplots(nrows=1, ncols=1)
    ax.scatter(X, Y, c=C, alpha=0.8, s=5)
    ax.set_xlabel("Block Number")
    ax.set_ylabel("Proposer Index")
    ax.set_title(f"Cluster {df.iloc[index]['cluster']}")

    fig.savefig(f"out/proposer_extra_data/coinbase-{index}.png")

    # add lines for blocks from same validator
    block_df = pd.DataFrame(blocks)
    proposer_group = block_df.groupby(by='proposer').count()
    multi_proposers = proposer_group[proposer_group['block_number'] > 1].index

    for p in list(multi_proposers):
        pb = block_df[block_df['proposer'] == p]['block_number'].values

        for a, b in zip(pb, pb[1:]):
            ax.plot([a, b], [p, p], c='black', alpha=0.2)
        
    fig.savefig(f"out/proposer_extra_data/coinbase-{index}-lines.png")
    
    plt.close(fig)

    # generate json
    with open(f'out/proposer_extra_data/coinbase-{index}.json', 'w') as file:
        out = json.dumps({"cluster": df.iloc[index]['cluster'], "blocks": blocks})
        file.write(out)
    
    with open(f'out/proposer_extra_data/coinbase-{index}.txt', 'w') as file:
        out = '\n'.join(df.iloc[index]['cluster'])

        out += '\n\n'
        out += f"Number of extra_data values: {len(block_df['extra_data'].unique())}"

        file.write(out)

