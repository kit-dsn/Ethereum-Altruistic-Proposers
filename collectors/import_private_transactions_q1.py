"""
Purpose
    Imports private transaction data for Q1 (blocks 21525891-22170334) from the
    central private_transactions.duckdb into q1.duckdb.

    Creates two tables as expected by the analysis scripts:

    - private_blocks (block_number, coinbase_addr, num_private_transactions)
        Aggregated per block: how many private transactions were included.

    - mempool_private (block_number, txn_hash, txn_index, addr_from, addr_to)
        One row per private transaction, used to identify builder interactions.

Usage
    python3 collectors/import_private_transactions_q1.py
"""

import duckdb

SOURCE_DB = "/data/fast/historical_mempools/2025/private_transactions/private_transactions.duckdb"
TARGET_DB = "/data/fast/historical_mempools/altruistic_proposers/q4.duckdb"
BLOCK_START = 23479244
BLOCK_END   = 24136052

src = duckdb.connect(SOURCE_DB, read_only=True)
tgt = duckdb.connect(TARGET_DB)

print(f"Connected to source: {SOURCE_DB}")
print(f"Connected to target: {TARGET_DB}")

# ── mempool_private ──────────────────────────────────────────────────────────
# Columns used by analysis: block_number, txn_hash, txn_index, addr_from, addr_to

print("Fetching mempool_private...")
mempool_private = src.execute(f"""
    SELECT
        block_number,
        transaction_hash AS txn_hash,
        transaction_index AS txn_index,
        lower(from_address) AS addr_from,
        lower(to_address)   AS addr_to
    FROM private_transactions
    WHERE block_number BETWEEN {BLOCK_START} AND {BLOCK_END}
""").df()
print(f"  {len(mempool_private):,} rows fetched")

tgt.execute("""
    CREATE TABLE IF NOT EXISTS mempool_private (
        block_number  BIGINT,
        txn_hash      VARCHAR,
        txn_index     INTEGER,
        addr_from     VARCHAR,
        addr_to       VARCHAR
    )
""")
tgt.register("mempool_private_data", mempool_private)
tgt.execute("INSERT INTO mempool_private SELECT * FROM mempool_private_data")
print(f"  Inserted {len(mempool_private):,} rows into mempool_private")

# ── private_blocks ───────────────────────────────────────────────────────────
# Columns used by analysis: block_number, coinbase_addr, num_private_transactions
# coinbase_addr comes from coinbase_blocks_all in q1.duckdb (joined by block_number)

print("Building private_blocks from coinbase_blocks_all + private_transactions...")
private_blocks = tgt.execute(f"""
    SELECT
        pt.block_number,
        lower(cb.coinbase_addr) AS coinbase_addr,
        COUNT(*)                AS num_private_transactions
    FROM (
        SELECT block_number
        FROM (VALUES {', '.join(f'({r})' for r in mempool_private['block_number'].unique())})
             AS t(block_number)
    ) pt
    JOIN coinbase_blocks_all cb USING (block_number)
    GROUP BY pt.block_number, cb.coinbase_addr
""").df()
print(f"  {len(private_blocks):,} rows built")

tgt.execute("""
    CREATE TABLE IF NOT EXISTS private_blocks (
        block_number          BIGINT,
        coinbase_addr         VARCHAR,
        num_private_transactions BIGINT
    )
""")
tgt.register("private_blocks_data", private_blocks)
tgt.execute("INSERT INTO private_blocks SELECT * FROM private_blocks_data")
print(f"  Inserted {len(private_blocks):,} rows into private_blocks")

src.close()
tgt.close()
print("Done.")
