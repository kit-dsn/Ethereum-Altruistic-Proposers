"""
Purpose
    Imports monthly private transaction TSV data stored inside ZIP archives
    into a DuckDB database with a staging table and a typed fact table.

Usage
    python3 collectors/import_private_transactions.py
    python3 collectors/import_private_transactions.py \
        --input-dir /data/fast/historical_mempools/2025/private_transactions \
        --output-db /data/fast/historical_mempools/2025/private_transactions/private_transactions.duckdb

Notes
    Expects each archive to contain exactly one TSV file named like YYYYMM.tsv.
"""

import argparse
import logging
from pathlib import Path
from typing import List
import zipfile

import duckdb
import pandas as pd


RAW_TABLE = "private_transactions_raw"
FACT_TABLE = "private_transactions"


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
        CREATE TABLE IF NOT EXISTS {RAW_TABLE} (
            source_month VARCHAR,
            source_archive VARCHAR,
            blockNumber VARCHAR,
            blockHash VARCHAR,
            transactionHash VARCHAR,
            transactionIndex VARCHAR,
            "from" VARCHAR,
            "to" VARCHAR,
            gas VARCHAR,
            gasPrice VARCHAR,
            type VARCHAR,
            maxFeePerGas VARCHAR,
            maxPriorityFeePerGas VARCHAR,
            maxFeePerBlobGas VARCHAR,
            blobVersionedHashes VARCHAR,
            ingested_at TIMESTAMP DEFAULT now()
        )
        """
    )

    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {FACT_TABLE} (
            source_month INTEGER NOT NULL,
            source_archive VARCHAR NOT NULL,
            block_number BIGINT NOT NULL,
            block_hash VARCHAR NOT NULL,
            transaction_hash VARCHAR NOT NULL,
            transaction_index INTEGER NOT NULL,
            from_address VARCHAR NOT NULL,
            to_address VARCHAR,
            gas BIGINT NOT NULL,
            gas_price_wei HUGEINT,
            tx_type TINYINT,
            max_fee_per_gas_wei HUGEINT,
            max_priority_fee_per_gas_wei HUGEINT,
            max_fee_per_blob_gas_wei HUGEINT,
            blob_versioned_hashes JSON,
            ingested_at TIMESTAMP DEFAULT now()
        )
        """
    )

    conn.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_{FACT_TABLE}_txhash
        ON {FACT_TABLE}(transaction_hash)
        """
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{FACT_TABLE}_block
        ON {FACT_TABLE}(block_number)
        """
    )
    conn.execute(
        f"""
        CREATE INDEX IF NOT EXISTS idx_{FACT_TABLE}_month
        ON {FACT_TABLE}(source_month)
        """
    )


def list_archives(input_dir: Path, max_files: int) -> List[Path]:
    archives = [p for p in sorted(input_dir.iterdir()) if p.is_file()]
    if max_files > 0:
        archives = archives[:max_files]
    return archives


def infer_month_from_inner_filename(inner_name: str) -> str:
    stem = Path(inner_name).stem
    if len(stem) == 6 and stem.isdigit():
        return stem
    raise ValueError(f"Could not infer YYYYMM from inner file name: {inner_name}")


def load_archive_to_raw(
    conn: duckdb.DuckDBPyConnection,
    archive_path: Path,
    chunk_size: int,
) -> int:
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if len(names) != 1:
            raise ValueError(
                f"Archive {archive_path.name} contains {len(names)} files; expected exactly 1 TSV"
            )
        inner_name = names[0]
        source_month = infer_month_from_inner_filename(inner_name)

    total_rows = 0
    reader = pd.read_csv(
        archive_path,
        sep="\t",
        compression="zip",
        dtype=str,
        chunksize=chunk_size,
    )

    for chunk_id, chunk in enumerate(reader, start=1):
        chunk["source_month"] = source_month
        chunk["source_archive"] = archive_path.name

        conn.register("ptx_chunk", chunk)
        conn.execute(
            f"""
            INSERT INTO {RAW_TABLE} (
                source_month,
                source_archive,
                blockNumber,
                blockHash,
                transactionHash,
                transactionIndex,
                "from",
                "to",
                gas,
                gasPrice,
                type,
                maxFeePerGas,
                maxPriorityFeePerGas,
                maxFeePerBlobGas,
                blobVersionedHashes
            )
            SELECT
                source_month,
                source_archive,
                blockNumber,
                blockHash,
                transactionHash,
                transactionIndex,
                "from",
                "to",
                gas,
                gasPrice,
                type,
                maxFeePerGas,
                maxPriorityFeePerGas,
                maxFeePerBlobGas,
                blobVersionedHashes
            FROM ptx_chunk
            """
        )
        conn.unregister("ptx_chunk")

        total_rows += len(chunk)
        logging.info(
            "Loaded %s chunk %s (%s rows)",
            archive_path.name,
            chunk_id,
            len(chunk),
        )

    return total_rows


def upsert_typed_from_raw(conn: duckdb.DuckDBPyConnection) -> int:
    before_count = conn.execute(f"SELECT COUNT(*) FROM {FACT_TABLE}").fetchone()[0]

    conn.execute(
        f"""
        INSERT INTO {FACT_TABLE}
        SELECT
            CAST(r.source_month AS INTEGER) AS source_month,
            r.source_archive AS source_archive,
            CAST(r.blockNumber AS BIGINT) AS block_number,
            r.blockHash AS block_hash,
            r.transactionHash AS transaction_hash,
            CAST(r.transactionIndex AS INTEGER) AS transaction_index,
            r."from" AS from_address,
            NULLIF(r."to", '') AS to_address,
            CAST(r.gas AS BIGINT) AS gas,
            CAST(NULLIF(r.gasPrice, '') AS HUGEINT) AS gas_price_wei,
            CAST(NULLIF(r.type, '') AS TINYINT) AS tx_type,
            CAST(NULLIF(r.maxFeePerGas, '') AS HUGEINT) AS max_fee_per_gas_wei,
            CAST(NULLIF(r.maxPriorityFeePerGas, '') AS HUGEINT) AS max_priority_fee_per_gas_wei,
            CAST(NULLIF(r.maxFeePerBlobGas, '') AS HUGEINT) AS max_fee_per_blob_gas_wei,
            CASE
                WHEN r.blobVersionedHashes IS NULL OR r.blobVersionedHashes = '' THEN NULL
                ELSE CAST(r.blobVersionedHashes AS JSON)
            END AS blob_versioned_hashes,
            now() AS ingested_at
        FROM {RAW_TABLE} r
        WHERE NOT EXISTS (
            SELECT 1
            FROM {FACT_TABLE} f
            WHERE f.transaction_hash = r.transactionHash
        )
        """
    )

    after_count = conn.execute(f"SELECT COUNT(*) FROM {FACT_TABLE}").fetchone()[0]
    return int(after_count - before_count)


def archive_already_imported(conn: duckdb.DuckDBPyConnection, archive_name: str) -> bool:
    row = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM {FACT_TABLE}
        WHERE source_archive = ?
        """,
        [archive_name],
    ).fetchone()
    return int(row[0]) > 0


def main() -> None:
    args = parse_args()
    setup_logging(args.log_level)

    input_dir = Path(args.input_dir)
    output_db = Path(args.output_db)

    if not input_dir.exists() or not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    archives = list_archives(input_dir, args.max_files)
    if not archives:
        raise FileNotFoundError(f"No files found in input directory: {input_dir}")

    logging.info("Found %s archive files", len(archives))

    conn = duckdb.connect(str(output_db))
    try:
        ensure_schema(conn)

        total_raw_rows = 0
        for archive in archives:
            if archive_already_imported(conn, archive.name):
                logging.info("Skipping already imported archive %s", archive.name)
                continue

            rows = load_archive_to_raw(conn, archive, args.chunk_size)
            total_raw_rows += rows
            logging.info("Finished archive %s with %s rows", archive.name, rows)

        inserted = upsert_typed_from_raw(conn)
        logging.info("Inserted %s new rows into %s", inserted, FACT_TABLE)
        logging.info("Loaded %s raw rows in this run", total_raw_rows)

        summary = conn.execute(
            f"""
            SELECT
                MIN(source_month) AS min_month,
                MAX(source_month) AS max_month,
                COUNT(*) AS rows_total,
                COUNT(DISTINCT source_month) AS months
            FROM {FACT_TABLE}
            """
        ).fetchone()
        logging.info(
            "Fact table summary: min_month=%s max_month=%s rows_total=%s months=%s",
            summary[0],
            summary[1],
            summary[2],
            summary[3],
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
