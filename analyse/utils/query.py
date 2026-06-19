"""Shared DuckDB access for the analyse/ scripts.

Every analysis script imports this module rather than opening its own
connection, so the database path only needs to be configured once (via
ANALYSE_DUCKDB_PATH) and all scripts see the same data.
"""

import pandas as pd
import hashlib
import os
import duckdb

DEFAULT_DB_PATH = '/data/fast/historical_mempools/altruistic_proposers/q1.duckdb'
DB_PATH = os.environ.get('ANALYSE_DUCKDB_PATH', DEFAULT_DB_PATH)
conn = duckdb.connect(DB_PATH)

WARNING_PRINTED = False


def query_cache(statement):
    """Run `statement` against DuckDB, caching the result by query text.

    The full pipeline re-runs the same aggregations over a multi-GB
    database every time a downstream script or a figure is tweaked, which
    gets slow fast. Since the SQL text fully determines the result, we key
    the cache on a hash of the statement itself instead of inventing names
    for every query. This means the cache is invalidated automatically
    whenever a query changes, but NOT when the underlying database is
    updated with new data - delete cache/ after a database refresh.
    """
    global WARNING_PRINTED

    statement_hash = hashlib.sha256(statement.encode('ASCII')).hexdigest()
    cache_path = f"cache/{statement_hash}.json"

    if os.path.isfile(cache_path):
        if not WARNING_PRINTED:
            print("Restoring queries from local cache...")
            WARNING_PRINTED = True
        return pd.read_json(cache_path)

    df = conn.execute(statement).df()
    df.to_json(cache_path)
    return df


def query(statement):
    """Run `statement` directly, bypassing the cache (for one-off / cheap queries)."""
    return conn.execute(statement).df()