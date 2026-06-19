"""
Purpose
    Summarizes relay usage for blocks whose coinbase address is unique per
    validator, using outputs from the distribution analysis.

Background
    A first sanity check on the coinbase_addr_distribution.py "unique
    addresses" set: if an address is genuinely only used by one validator,
    do its blocks still occasionally show up via a relay? If so, "unique
    coinbase address" alone isn't proof of self-building either - the same
    gap that motivates the proper graph-based clustering in
    coinbase_clusters.py.
"""

# depends_on: coinbase_addr_distribution.py
import pandas as pd
import utils.query

unique_coinbases = list(
    pd.read_json("out/coinbase_addr_distribution-unique-coinbase-addrs.json")['coinbase_addr'].unique()
)

block_number = utils.query.query_cache(f"""
    SELECT block_number FROM coinbase_blocks_all
    WHERE coinbase_addr IN (
        {','.join([f"'{x}'" for x in unique_coinbases])}
    );
""")

print("Number of unique-per-validator coinbase addresses:", len(unique_coinbases))
print("Number of blocks from these coinbase addresses:", len(block_number))

relay_blocks = utils.query.query_cache(f"""
    SELECT DISTINCT block_number FROM relay_all
    WHERE block_number IN (
        {','.join(list([str(x) for x in block_number['block_number'].unique()]))}
    )
""")

print("Number of relay block from these coinbase addresses:", len(relay_blocks))