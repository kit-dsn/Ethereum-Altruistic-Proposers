import pandas as pd
import hashlib
import os.path
import os
import numpy as np
import duckdb
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

DEFAULT_DB_PATH = '/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb'
DB_PATH = os.environ.get('ANALYSE_DUCKDB_PATH', DEFAULT_DB_PATH)
conn = duckdb.connect(DB_PATH)

WARNING_PRINTED = False

def query_cache(statement):
    global WARNING_PRINTED
    
    m = hashlib.sha256()
    m.update(statement.encode('ASCII'))
    statement_hash = m.hexdigest()

    # check if result is already stored
    if os.path.isfile(f"cache/{statement_hash}.json"):
        if not WARNING_PRINTED:
            print("Restoring queries from local cache...")
            WARNING_PRINTED = True
        df = pd.read_json(f"cache/{statement_hash}.json")
        return df
    else:
        df = conn.execute(statement).df()
        
        # store result
        df.to_json(f"cache/{statement_hash}.json")
        return df

def query(statement):
    return conn.execute(statement).df()