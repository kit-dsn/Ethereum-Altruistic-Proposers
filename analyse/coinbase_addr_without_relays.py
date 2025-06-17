import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

engine = create_engine('postgresql://rfcanalyse@rfc.incus.tamedfox.eu/rfc')

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

with engine.connect() as connection:
    df = pd.read_sql(sql_query, connection)
    df2 = pd.read_sql(sql_query2, connection) 

df.to_json("out/coinbase_addr_without_relays-unique-blocks.json")
df2.to_json("out/coinbase_addr_without_relays-max10-blocks.json")