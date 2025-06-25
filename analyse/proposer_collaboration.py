import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import utils.query

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
    INNER JOIN relay_all ON (coinbase_blocks_all.block_number = relay_all.block_number)
    GROUP BY proposer_index 
    ORDER BY COUNT(coinbase_blocks_all.slot) DESC
""")

assert df_all_proposer["slots"].sum() == 859413

df_no_relay_proposer = df_all_proposer[~df_all_proposer.proposer_index.isin(df_relay_proposer.proposer_index)]
df_relay_proposer = df_relay_proposer.rename(columns={"coinbase_addrs": "relay_coinbase_addrs", "slots": "relay_slots"})
df_relay_proposer = df_relay_proposer.merge(df_all_proposer, left_on='proposer_index', right_on='proposer_index')

assert len(df_no_relay_proposer) + len(df_relay_proposer) == len(df_all_proposer)

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

fig.savefig("out/proposer_collaboration-relaying-pie.png")
plt.close(fig)

# what coinbase addresses are used by validators that *sometimes* use relays?
df_sometimes_relay_proposer = df_relay_proposer[df_relay_proposer['relay_slots'] != df_relay_proposer['slots']]
sometimes_relay_proposer_idxs = ",".join(df_sometimes_relay_proposer.proposer_index.apply(str))

df_sometimes_relay_proposer_coinbase = utils.query.query_cache(f"""
    SELECT
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
        WHERE proposer_index IN ({sometimes_relay_proposer_idxs})
    ) a
    LEFT JOIN (
        SELECT DISTINCT block_number FROM relay_all
    ) b ON (a.block_number = b.block_number)
    GROUP BY a.coinbase_addr
    ORDER BY count DESC
""")

assert len(df_sometimes_relay_proposer_coinbase[df_sometimes_relay_proposer_coinbase['count'] < df_sometimes_relay_proposer_coinbase['relay_count']]) == 0


print(df_sometimes_relay_proposer_coinbase)
