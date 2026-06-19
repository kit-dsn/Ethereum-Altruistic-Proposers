"""
Purpose
    Identifies blocks proposed without relay announcements for coinbase
    addresses used by other validators, and exports the block lists.

Background
    Two variants of the same query at different reuse thresholds: addresses
    used by exactly one proposer (sql_query) vs. by fewer than ten
    (sql_query2). Both ask, for blocks built with such an address, whether
    that specific block ever shows up in relay_all - an early, per-block
    version of the relay-overlap check coinbase_clusters.py later applies
    at the cluster level.

Outputs
    JSON files under out/ with block_number lists.
"""

import pandas as pd
import numpy as np
import duckdb
import os
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

sql_query = """
    SELECT coinbase_blocks_all.block_number 
    FROM coinbase_blocks_all 
    LEFT JOIN relay_all ON (relay_all.block_number = coinbase_blocks_all.block_number) 
    WHERE coinbase_addr IN (
        SELECT coinbase_addr FROM (
            SELECT coinbase_addr, count(DISTINCT proposer_index) as count FROM coinbase_blocks_all
            GROUP BY coinbase_addr
        ) WHERE count = 1
    )
    AND relay_all.block_number IS NULL
"""

sql_query2 = """
    SELECT coinbase_blocks_all.block_number 
    FROM coinbase_blocks_all 
    LEFT JOIN relay_all ON (relay_all.block_number = coinbase_blocks_all.block_number) 
    WHERE coinbase_addr IN (
        SELECT coinbase_addr FROM (
            SELECT coinbase_addr, count(DISTINCT proposer_index) as count FROM coinbase_blocks_all
            GROUP BY coinbase_addr
        ) WHERE count < 10
    )
    AND relay_all.block_number IS NULL
"""

DEFAULT_DB_PATH = '/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb'
conn = duckdb.connect(os.environ.get('ANALYSE_DUCKDB_PATH', DEFAULT_DB_PATH))
df = conn.execute(sql_query).df()
df2 = conn.execute(sql_query2).df() 

df.to_json("out/coinbase_addr_without_relays-unique-blocks.json")
df2.to_json("out/coinbase_addr_without_relays-max10-blocks.json")