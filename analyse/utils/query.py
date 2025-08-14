import pandas as pd
import hashlib
import os.path
import numpy as np
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

engine = create_engine('postgresql://rfcanalyse@rfc.incus.tamedfox.eu/rfc')

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
        with engine.connect() as connection:
            df = pd.read_sql(statement, connection)
        
        # store result
        df.to_json(f"cache/{statement_hash}.json")
        return df

def query(statement):
    with engine.connect() as connection:
        return pd.read_sql(statement, connection)