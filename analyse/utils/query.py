import pandas as pd
import hashlib
import os.path
import numpy as np
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

engine = create_engine('postgresql://rfcanalyse@rfc.incus.tamedfox.eu/rfc')

def query_cache(statement):
    m = hashlib.sha256()
    m.update(statement.encode('ASCII'))
    statement_hash = m.hexdigest()

    # check if result is already stored
    if os.path.isfile(f"cache/{statement_hash}.json"):
        print("Restoring Query from local cache...")
        df = pd.read_json(f"cache/{statement_hash}.json")
        return df
    else:
        with engine.connect() as connection:
            df = pd.read_sql(statement, connection)
        
        # store result
        df.to_json(f"cache/{statement_hash}.json")
        return df