"""
Purpose
    Characterizes relay usage by proposers, exports proposer/coinbase
    datasets, and generates relay-related figures.

Outputs
    JSON exports and multiple PDF figures in out/.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import utils.query
import json

df_all_proposer = utils.query.query_cache("""
    SELECT 
        proposer_index, 
        COUNT(DISTINCT coinbase_addr) as coinbase_addrs,
        COUNT(slot) as slots
    FROM coinbase_blocks_all 
    GROUP BY proposer_index 
    ORDER BY COUNT(slot) DESC
""")
df_relay_proposer = utils.query.query_cache("""
    SELECT 
        proposer_index, 
        COUNT(DISTINCT coinbase_addr) as coinbase_addrs,
        COUNT(coinbase_blocks_all.slot) as slots
    FROM coinbase_blocks_all
    INNER JOIN (SELECT DISTINCT block_number, slot from relay_all) r ON (coinbase_blocks_all.block_number = r.block_number AND coinbase_blocks_all.slot = r.slot)
    GROUP BY proposer_index 
    ORDER BY COUNT(coinbase_blocks_all.slot) DESC
""")

assert df_all_proposer["slots"].sum() == 859313

df_no_relay_proposer = df_all_proposer[~df_all_proposer.proposer_index.isin(df_relay_proposer.proposer_index)]
df_relay_proposer = df_relay_proposer.rename(columns={"coinbase_addrs": "relay_coinbase_addrs", "slots": "relay_slots"})
df_relay_proposer = df_relay_proposer.merge(df_all_proposer, left_on='proposer_index', right_on='proposer_index')

assert len(df_no_relay_proposer) + len(df_relay_proposer) == len(df_all_proposer)
assert len(df_relay_proposer[df_relay_proposer['relay_slots'] > df_relay_proposer['slots']]) == 0

# print diagram of validators
y = np.array([
    len(df_no_relay_proposer), # does not use relays
    len(df_relay_proposer[df_relay_proposer['relay_slots'] == df_relay_proposer['slots']]), # always uses relays
    len(df_relay_proposer[df_relay_proposer['relay_slots'] != df_relay_proposer['slots']]) # sometimes uses relays
])
labels = ["No Relays", "Always Relays", "Sometimes Relays"]

assert y.sum() == len(df_all_proposer)

def writing(pct, allvals):
    absolute = int(np.round(pct/100.*np.sum(allvals)))
    return f"{pct:.1f}%\n({absolute:d} validators)"

fig, ax = plt.subplots(nrows=1, ncols=1)
wedges, texts, autotexts = ax.pie(y, autopct=lambda pct: writing(pct, y), textprops=dict(color="w"))
ax.set_title("Validators Relaying")
ax.legend(wedges, labels,
          loc="lower center")

fig.savefig("out/proposer_collaboration-relaying-pie.pdf")
plt.close(fig)

# export the proposers
with open('out/proposer_collaboration-overview.json', 'w') as file:
    file.write(json.dumps({
        "all_proposers": df_all_proposer.to_dict('records'),
        "non_relaying_proposers": df_no_relay_proposer.to_dict('records'),
        "always_relaying_proposers": df_relay_proposer[df_relay_proposer['relay_slots'] == df_relay_proposer['slots']].to_dict('records'),
        "sometimes_relaying_proposers": df_relay_proposer[df_relay_proposer['relay_slots'] != df_relay_proposer['slots']].to_dict('records'),
    }))

# what coinbase addresses are used by validators that *sometimes* use relays?
df_sometimes_relay_proposer = df_relay_proposer[df_relay_proposer['relay_slots'] != df_relay_proposer['slots']]
df_always_relay_proposer = df_relay_proposer[df_relay_proposer['relay_slots'] == df_relay_proposer['slots']]

def fetch_coinbase_addrs_used(df):
    proposer_idx = ",".join(df.proposer_index.apply(str))
    return utils.query.query_cache(f"""
        SELECT
            proposer_index,
            coinbase_addr,
            COUNT(DISTINCT a.block_number) as count,
            COUNT(DISTINCT b.block_number) as relay_count
        FROM
        (
            SELECT
                proposer_index,
                block_number,
                coinbase_addr
            FROM coinbase_blocks_all
            WHERE proposer_index IN ({proposer_idx})
        ) a
        LEFT JOIN (
            SELECT DISTINCT block_number FROM relay_all
        ) b ON (a.block_number = b.block_number)
        GROUP BY a.coinbase_addr, a.proposer_index
        ORDER BY count DESC
    """)

# find out which proposers used which coinbase addr
# not showing up in relays...

def reorg_proposer_index(df):
    proposer_index_unique = list(df['proposer_index'].sort_values().unique())
    proposer_index_unique = dict(zip(proposer_index_unique, range(1, len(proposer_index_unique) + 1)))
    df['proposer_index'] = df.proposer_index.apply(lambda x: proposer_index_unique[x])

def add_coinbase_reoccurence(df):
    vc = df['coinbase_addr'].value_counts().rename('rank')
    vc = vc.sort_values().unique()
    d = dict(zip(vc, range(1, len(vc) + 1)))
    vc = df['coinbase_addr'].value_counts().apply(lambda x: d[x]).rename("rank")
    return df.merge(vc, left_on="coinbase_addr", right_on="coinbase_addr")

# plot these proposer - coinbase pairs

CHECK_COUNT = 0

# sometimes relaying proposers
df = fetch_coinbase_addrs_used(df_sometimes_relay_proposer)
CHECK_COUNT += df['count'].sum()
assert len(df[df['count'] < df['relay_count']]) == 0
assert df.proposer_index.isin(df_sometimes_relay_proposer.proposer_index).all()

# export this data
df.to_json('out/proposer_collaboration-sometimes-relaying-proposer-coinbase.json')

reorg_proposer_index(df)

fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(60,20))
coinbase_addr_translated = df['coinbase_addr'].apply(int, base=16)

ax.scatter(df['proposer_index'], coinbase_addr_translated.values)
ax.set_xticks([], [])
ax.set_yticks([], [])
ax.set_xlabel("\"Proposer Index\"")
ax.set_ylabel("Coinbase Address")

fig.savefig("out/proposer_collaboration-scatter-sometimes-relaying-proposers.pdf")

# always relaying
df = fetch_coinbase_addrs_used(df_always_relay_proposer)
CHECK_COUNT += df['count'].sum()
assert len(df[df['count'] < df['relay_count']]) == 0

# export this data
df.to_json('out/proposer_collaboration-always-relaying-proposer-coinbase.json')

reorg_proposer_index(df)

fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(60,20))
coinbase_addr_translated = df['coinbase_addr'].apply(int, base=16)

ax.scatter(df['proposer_index'], coinbase_addr_translated.values)
ax.set_xticks([], [])
ax.set_yticks([], [])
ax.set_xlabel("\"Proposer Index\"")
ax.set_ylabel("Coinbase Address")

fig.savefig("out/proposer_collaboration-scatter-always-relaying-proposers.pdf")

# never relaying
df = fetch_coinbase_addrs_used(df_no_relay_proposer)
CHECK_COUNT += df['count'].sum()
df = add_coinbase_reoccurence(df)

# export this data
df.to_json('out/proposer_collaboration-no-relaying-proposer-coinbase.json')

assert len(df[df['count'] < df['relay_count']]) == 0
reorg_proposer_index(df)

fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(60,20))
coinbase_addr_translated = df['coinbase_addr'].apply(int, base=16)

color_map = LinearSegmentedColormap.from_list('asdf', ['grey', 'b', 'r'])

color = df['rank']/df['rank'].max()

ax.scatter(df['proposer_index'], coinbase_addr_translated.values, c=color, cmap=color_map)
ax.set_xticks([], [])
ax.set_yticks([], [])
ax.set_xlabel("\"Proposer Index\"")
ax.set_ylabel("Coinbase Address")

fig.savefig("out/proposer_collaboration-scatter-no-relaying-proposers.pdf")

print(f"Check Count: {CHECK_COUNT}")
print(f"Sum of Validators: {len(df_no_relay_proposer) + len(df_sometimes_relay_proposer) + len(df_always_relay_proposer)}")
print(f"Sum slots: {df_no_relay_proposer.slots.sum() + df_sometimes_relay_proposer.slots.sum() + df_always_relay_proposer.slots.sum()}")


# ============================
# Dig deeper into no-relaying
# ============================

df = pd.read_json('out/proposer_collaboration-no-relaying-proposer-coinbase.json')

df_coinbases = df.groupby('coinbase_addr')['count'].sum()
df_coinbases = utils.query.query_cache(f"""
    SELECT 
        coinbase_addr, 
        COUNT(DISTINCT coinbase_blocks_all.slot) as all_count, 
        COUNT(DISTINCT r.block_number) as relay_count
    FROM coinbase_blocks_all 
    LEFT JOIN (
        SELECT 
            DISTINCT relay_all.block_number 
        FROM relay_all 
        INNER JOIN coinbase_blocks_all 
        ON (
            relay_all.slot = coinbase_blocks_all.slot AND 
            relay_all.block_number = coinbase_blocks_all.block_number
        )
    ) r 
    ON (r.block_number = coinbase_blocks_all.block_number)
    WHERE coinbase_addr IN (
        {','.join(df_coinbases.index.map(lambda x: f"'{x}'"))}
    )
    GROUP BY coinbase_addr 
""").merge(df_coinbases.rename('count'), left_on='coinbase_addr', right_index=True)

assert len(df_coinbases[df_coinbases['all_count'] < df_coinbases['count']]) == 0
assert len(df_coinbases[df_coinbases['all_count'] < df_coinbases['relay_count']]) == 0
assert len(df_coinbases) == len(df['coinbase_addr'].unique())

df = df_coinbases.sort_values(by='count')
df = df.reset_index(drop=True)


fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(10,7))
ax.plot(df.index.to_list(), df['count'])
ax.scatter(df[df['relay_count'] != 0].index.to_list(), df[df['relay_count'] != 0]['relay_count'], c='red')
ax.set_yscale('log')
fig.savefig("out/proposer_collaboration-no-relaying-coinbases.pdf")