"""
Purpose
    Downloads coinbase address and proposer metadata by combining EL block
    headers with local CL header data, then stores results in DuckDB.

Usage
    python3 collectors/download_coinbase.py
    python3 collectors/download_coinbase.py --table coinbase_data
    python3 collectors/download_coinbase.py --quarter q4

Notes
    Reads block numbers from relay payload data (table relay_payloads) for the
    requested quarter slot ranges and fills the corresponding q1-q4 databases.
"""

import argparse
import logging
import os
import time
from typing import Dict, List, Tuple

import duckdb
import pandas as pd
import requests

EL_API_BASE = "http://localhost:8504"
CL_API_BASE = "http://localhost:5052"

QUARTERS: Dict[str, Tuple[int, int]] = {
    "q1": (10738799, 11386798),
    "q2": (11386799, 12041998),
    "q3": (12041999, 12704398),
    "q4": (12704399, 13366798),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Download coinbase data",
        description="Download coinbase/proposer metadata into q1-q4 DuckDB files",
    )
    parser.add_argument(
        "--output-dir",
        default="/data/fast/historical_mempools/altruistic_proposers",
        help="Directory containing q1.duckdb..q4.duckdb",
    )
    parser.add_argument(
        "--source-table",
        default="relay_payloads",
        help="Source table that contains slot and block_number",
    )
    parser.add_argument(
        "--table",
        default="coinbase_data",
        help="Destination table for coinbase metadata",
    )
    parser.add_argument(
        "--quarter",
        choices=["q1", "q2", "q3", "q4", "all"],
        default="all",
        help="Process one quarter or all",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="How many blocks to collect before inserting",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=20,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.05,
        help="Sleep between block downloads",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=6,
        help="Retries per block download",
    )
    return parser.parse_args()


def fetch_el_header(block_num: int, timeout: int) -> dict:
    response = requests.post(
        EL_API_BASE,
        json={
            "method": "eth_getBlockByNumber",
            "jsonrpc": "2.0",
            "id": 67,
            "params": [hex(block_num), False],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["result"]


def fetch_cl_header(parent_beacon_root: str, timeout: int) -> dict:
    response = requests.get(
        f"{CL_API_BASE}/eth/v1/beacon/headers?parent_root={parent_beacon_root}",
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["data"][0]


def fetch_cl_header_by_slot(slot: int, timeout: int) -> dict:
    response = requests.get(
        f"{CL_API_BASE}/eth/v1/beacon/headers/{slot}",
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["data"]


def download_block(block_num: int, relay_slot: int, timeout: int, logger: logging.Logger) -> dict:
    el_header = fetch_el_header(block_num, timeout)

    slot = relay_slot
    proposer_index = None
    parent_root = el_header.get("parentBeaconBlockRoot")

    if parent_root:
        try:
            cl_header = fetch_cl_header(parent_root, timeout)
            slot = int(cl_header["header"]["message"]["slot"])
            proposer_index = int(cl_header["header"]["message"]["proposer_index"])
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
        except Exception:
            # Fall through to slot-based CL lookup.
            pass

    if proposer_index is None:
        try:
            cl_slot_header = fetch_cl_header_by_slot(relay_slot, timeout)
            slot = int(cl_slot_header["header"]["message"]["slot"])
            proposer_index = int(cl_slot_header["header"]["message"]["proposer_index"])
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 404:
                raise
            logger.debug("CL header missing for slot %s, continue without proposer_index", relay_slot)

    return {
        "slot": slot,
        "proposer_index": proposer_index,
        "coinbase_addr": el_header["miner"],
        "block_number": int(el_header["number"], 16),
        "block_hash": el_header["hash"],
        "extra_data": el_header["extraData"],
    }


def ensure_target_table(conn: duckdb.DuckDBPyConnection, table_name: str) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            slot BIGINT,
            proposer_index BIGINT,
            coinbase_addr VARCHAR,
            block_number BIGINT,
            block_hash VARCHAR,
            extra_data VARCHAR
        )
        """
    )


def upload_data(conn: duckdb.DuckDBPyConnection, table_name: str, blocks: List[dict]) -> int:
    if not blocks:
        return 0

    df = pd.DataFrame(blocks)
    conn.register("coinbase_batch", df)
    conn.execute(
        f"""
        INSERT INTO {table_name}
        SELECT b.*
        FROM coinbase_batch b
        WHERE NOT EXISTS (
            SELECT 1
            FROM {table_name} t
            WHERE t.block_number = b.block_number
               OR t.block_hash = b.block_hash
        )
        """
    )
    inserted = conn.execute("SELECT COUNT(*) FROM coinbase_batch").fetchone()[0]
    conn.unregister("coinbase_batch")
    return int(inserted)


def get_blocks_from_relay_table(
    conn: duckdb.DuckDBPyConnection,
    source_table: str,
    slot_start: int,
    slot_end: int,
) -> List[Tuple[int, int]]:
    rows = conn.execute(
        f"""
        SELECT block_number, MIN(slot) AS slot
        FROM {source_table}
        WHERE slot BETWEEN ? AND ?
        GROUP BY block_number
        ORDER BY block_number DESC
        """,
        [slot_start, slot_end],
    ).fetchall()
    return [(int(row[0]), int(row[1])) for row in rows]


def fill_quarter(
    quarter: str,
    slot_start: int,
    slot_end: int,
    output_dir: str,
    source_table: str,
    target_table: str,
    batch_size: int,
    request_timeout: int,
    sleep_seconds: float,
    max_retries: int,
    logger: logging.Logger,
) -> None:
    db_path = os.path.join(output_dir, f"{quarter}.duckdb")
    logger.info("Processing %s (%s-%s) in %s", quarter, slot_start, slot_end, db_path)

    conn = duckdb.connect(db_path)
    try:
        ensure_target_table(conn, target_table)
        block_refs = get_blocks_from_relay_table(conn, source_table, slot_start, slot_end)
        logger.info("%s: %s block numbers found in %s", quarter, len(block_refs), source_table)

        batch: List[dict] = []
        inserted_total = 0
        for idx, (block_num, relay_slot) in enumerate(block_refs, start=1):
            for attempt in range(1, max_retries + 1):
                try:
                    batch.append(download_block(block_num, relay_slot, request_timeout, logger))
                    break
                except Exception as exc:  # noqa: BLE001
                    wait_seconds = min(30, 2**attempt)
                    logger.warning(
                        "%s: block %s failed attempt %s/%s (%s), retry in %ss",
                        quarter,
                        block_num,
                        attempt,
                        max_retries,
                        exc,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
            else:
                logger.error("%s: skip block %s after %s retries", quarter, block_num, max_retries)

            if len(batch) >= batch_size:
                inserted_total += upload_data(conn, target_table, batch)
                batch = []

            if idx % 500 == 0:
                logger.info("%s: processed %s/%s blocks", quarter, idx, len(block_refs))

            time.sleep(sleep_seconds)

        if batch:
            inserted_total += upload_data(conn, target_table, batch)

        logger.info("%s: done, inserted %s rows into %s", quarter, inserted_total, target_table)
    finally:
        conn.close()


def main() -> None:
    args = parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("download_coinbase")

    if args.quarter == "all":
        to_process = [(q, *QUARTERS[q]) for q in ["q1", "q2", "q3", "q4"]]
    else:
        start, end = QUARTERS[args.quarter]
        to_process = [(args.quarter, start, end)]

    for quarter, slot_start, slot_end in to_process:
        fill_quarter(
            quarter=quarter,
            slot_start=slot_start,
            slot_end=slot_end,
            output_dir=args.output_dir,
            source_table=args.source_table,
            target_table=args.table,
            batch_size=args.batch_size,
            request_timeout=args.request_timeout,
            sleep_seconds=args.sleep_seconds,
            max_retries=args.max_retries,
            logger=logger,
        )


if __name__ == "__main__":
    main()