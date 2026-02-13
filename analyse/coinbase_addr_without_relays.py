"""
Purpose
    Identifies blocks proposed without relay announcements for coinbase
    addresses used by other validators, and exports the block lists.


Outputs
    JSON files under out/ with block_number lists.
"""

import pandas as pd
import numpy as np
import duckdb
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

conn = duckdb.connect('/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb')
df = conn.execute(sql_query).df()
df2 = conn.execute(sql_query2).df() 

df.to_json("out/coinbase_addr_without_relays-unique-blocks.json")
df2.to_json("out/coinbase_addr_without_relays-max10-blocks.json")