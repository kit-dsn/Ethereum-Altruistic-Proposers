"""
Purpose
    Imports monthly private transaction TSV data stored inside ZIP archives
    into a DuckDB database.

    Schema (private_transactions):
        block_number            BIGINT
        block_hash              VARCHAR
        transaction_hash        VARCHAR  (unique)
        transaction_index       INTEGER
        from_address            VARCHAR
        to_address              VARCHAR  (NULL for contract deployments)
        gas                     BIGINT
        gas_price_wei           UBIGINT  (NULL for EIP-1559 txs)
        tx_type                 TINYINT
        max_fee_per_gas_wei     UBIGINT  (NULL for legacy txs)
        max_priority_fee_wei    UBIGINT  (NULL for legacy txs)

    Strategy:
        - No staging table: rows are cast and inserted directly per chunk.
        - A small _imported_archives table tracks completed archives so the
          script can resume safely after a crash.
        - Indexes are created after all data is loaded.

    This only populates the central private_transactions table. The
    analyse/ pipeline expects mempool_private/private_blocks instead - a
    second, per-quarter aggregation step pulls the relevant block range out
    of here into that shape (see import_private_transactions_q1.py).

Usage
    python3 collectors/import_private_transactions.py
    python3 collectors/import_private_transactions.py \
        --input-dir /data/fast/historical_mempools/2025/private_transactions \
        --output-db /data/fast/historical_mempools/2025/private_transactions/private_transactions.duckdb
"""

import argparse
import logging
from pathlib import Path
from typing import List
import zipfile

import duckdb
import pandas as pd


FACT_TABLE = "private_transactions"
TRACKING_TABLE = "_imported_archives"

# TSV columns we keep (ordered as they appear in the source)
KEEP_COLS = [
    "blockNumber",
    "blockHash",
    "transactionHash",
    "transactionIndex",
    "from",
    "to",
    "gas",
    "gasPrice",
    "type",
    "maxFeePerGas",
    "maxPriorityFeePerGas",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Import private transactions",
        description="Import ZIP-compressed monthly TSVs into DuckDB",
    )
    parser.add_argument(
        "--input-dir",
        default="/data/fast/historical_mempools/2025/private_transactions",
        help="Directory containing ZIP archives without file extension",
    )
    parser.add_argument(
        "--output-db",
        default="/data/fast/historical_mempools/2025/private_transactions/private_transactions.duckdb",
        help="Target DuckDB file",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500_000,
        help="Rows per chunk when reading TSV from ZIP",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Optional cap for number of archives to ingest (0 = all)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {FACT_TABLE} (
            block_number            BIGINT  NOT NULL,
            block_hash              VARCHAR NOT NULL,
            transaction_hash        VARCHAR NOT NULL,
            transaction_index       INTEGER NOT NULL,
            from_address            VARCHAR NOT NULL,
            to_address              VARCHAR,
            gas                     BIGINT  NOT NULL,
            gas_price_wei           UBIGINT,
            tx_type                 TINYINT,
            max_fee_per_gas_wei     UBIGINT,
            max_priority_fee_wei    UBIGINT
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TRACKING_TABLE} (
            archive_name VARCHAR PRIMARY KEY
        )
        """
    )


def build_indexes(conn: duckdb.DuckDBPyConnection) -> None:
    logging.info("Building indexes …")
    conn.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_ptx_txhash ON {FACT_TABLE}(transaction_hash)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_ptx_block ON {FACT_TABLE}(block_number)"
    )
    logging.info("Indexes ready.")


def list_archives(input_dir: Path, max_files: int) -> List[Path]:
    archives = [
        p
        for p in sorted(input_dir.iterdir())
        if p.is_file() and zipfile.is_zipfile(p)
    ]
    if max_files > 0:
        archives = archives[:max_files]
    return archives


def archive_already_imported(conn: duckdb.DuckDBPyConnection, archive_name: str) -> bool:
    row = conn.execute(
        f"SELECT COUNT(*) FROM {TRACKING_TABLE} WHERE archive_name = ?",
        [archive_name],
    ).fetchone()
    return int(row[0]) > 0


def mark_imported(conn: duckdb.DuckDBPyConnection, archive_name: str) -> None:
    conn.execute(
        f"INSERT OR IGNORE INTO {TRACKING_TABLE} VALUES (?)",
        [archive_name],
    )


def infer_inner_filename(archive_path: Path) -> str:
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
    if len(names) != 1:
        raise ValueError(
            f"Archive {archive_path.name} contains {len(names)} files; expected exactly 1 TSV"
        )
    return names[0]


def load_archive(
    conn: duckdb.DuckDBPyConnection,
    archive_path: Path,
    chunk_size: int,
) -> int:
    infer_inner_filename(archive_path)  # validates single-file assumption

    total_rows = 0
    reader = pd.read_csv(
        archive_path,
        sep="\t",
        compression="zip",
        dtype=str,
        usecols=KEEP_COLS,
        chunksize=chunk_size,
    )

    for chunk_id, chunk in enumerate(reader, start=1):
        conn.register("ptx_chunk", chunk)
        conn.execute(
            f"""
            INSERT INTO {FACT_TABLE}
            SELECT
                CAST(blockNumber        AS BIGINT)  AS block_number,
                blockHash                           AS block_hash,
                transactionHash                     AS transaction_hash,
                CAST(transactionIndex   AS INTEGER) AS transaction_index,
                "from"                              AS from_address,
                NULLIF("to", '')                    AS to_address,
                CAST(gas                AS BIGINT)  AS gas,
                CAST(NULLIF(gasPrice,           '') AS UBIGINT) AS gas_price_wei,
                CAST(NULLIF(type,               '') AS TINYINT) AS tx_type,
                CAST(NULLIF(maxFeePerGas,       '') AS UBIGINT) AS max_fee_per_gas_wei,
                CAST(NULLIF(maxPriorityFeePerGas,'') AS UBIGINT) AS max_priority_fee_wei
            FROM ptx_chunk
            """
        )
        conn.unregister("ptx_chunk")
        total_rows += len(chunk)
        logging.info("%s  chunk %s  (%s rows)", archive_path.name, chunk_id, len(chunk))

    return total_rows


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    input_dir = Path(args.input_dir)
    output_db = Path(args.output_db)

    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    archives = list_archives(input_dir, args.max_files)
    if not archives:
        raise FileNotFoundError(f"No ZIP archives found in: {input_dir}")

    logging.info("Found %s archives", len(archives))

    conn = duckdb.connect(str(output_db))
    try:
        ensure_schema(conn)

        total_rows = 0

        for archive in archives:
            if archive_already_imported(conn, archive.name):
                logging.info("Skip (already done): %s", archive.name)
                continue

            rows = load_archive(conn, archive, args.chunk_size)
            mark_imported(conn, archive.name)
            total_rows += rows
            logging.info("Done: %s  (%s rows)", archive.name, rows)

        build_indexes(conn)

        summary = conn.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT block_number) FROM {FACT_TABLE}"
        ).fetchone()
        logging.info(
            "Finished. total_rows=%s distinct_blocks=%s",
            summary[0],
            summary[1],
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
