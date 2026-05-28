"""
Purpose
    Download proposer_payload_delivered traces from all relay providers for
    four predefined slot ranges (Q1-Q4) and store each quarter in its own
    DuckDB database.

Usage
    python3 collectors/download_relay_data_quarters.py
    python3 collectors/download_relay_data_quarters.py --table relay_payloads
    python3 collectors/download_relay_data_quarters.py --output-dir /data/fast/historical_mempools/altruistic_proposers

Output
    Creates 4 DuckDB files in the output directory:
    - q1.duckdb
    - q2.duckdb
    - q3.duckdb
    - q4.duckdb
"""

import argparse
import json
import logging
import os
import time
from typing import Dict, List, Optional, Tuple

import duckdb
import pandas as pd
import requests


RELAYS: List[str] = [
    "https://aestus.live",
    "https://agnostic-relay.net",
    "https://bloxroute.max-profit.blxrbdn.com",
    "https://bloxroute.regulated.blxrbdn.com",
    "https://boost-relay.flashbots.net",
    #"https://titanrelay.xyz",
    "https://relay-analytics.ultrasound.money",
    "https://relay.ethgas.com",
]

# Inclusive ranges as provided.
QUARTERS: Dict[str, Tuple[int, int]] = {
    #"q1": (10738799, 11386798),
    #"q2": (11386799, 12041998),
    #"q3": (12041999, 12704398),
    "q4": (12704399, 13366798),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Download Relay Data (Q1-Q4)",
        description=(
            "Downloads proposer_payload_delivered from all relay APIs for Q1-Q4 "
            "and stores each quarter in its own DuckDB database."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="/data/fast/historical_mempools/altruistic_proposers",
        help="Directory where q1.duckdb..q4.duckdb will be created",
    )
    parser.add_argument(
        "--table",
        default="relay_payloads",
        help="Target table name inside each database",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Relay API page size",
    )
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.03,
        help="Sleep between successful API calls",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=10,
        help="Maximum retries per request",
    )
    parser.add_argument(
        "--failed-slots-file",
        default="titan_failed_slots.json",
        help="Filename (inside --output-dir) to append failed cursor slots to",
    )
    parser.add_argument(
        "--slot-end",
        type=int,
        default=None,
        help="Override the slot_end (starting cursor) for all quarters — useful to resume from a specific slot",
    )
    return parser.parse_args()


def create_table(conn: duckdb.DuckDBPyConnection, table_name: str) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            relay_url VARCHAR,
            slot BIGINT,
            block_number BIGINT,
            block_hash VARCHAR,
            builder_pk VARCHAR,
            proposer_pk VARCHAR,
            proposer_fee_recipient VARCHAR,
            gas_limit BIGINT,
            gas_used BIGINT,
            value HUGEINT,
            num_tx INTEGER
        )
        """
    )


def fetch_batch(
    relay: str,
    cursor_slot: int,
    limit: int,
    timeout: int,
    max_retries: int,
    logger: logging.Logger,
) -> Optional[List[dict]]:
    endpoint = (
        f"{relay}/relay/v1/data/bidtraces/proposer_payload_delivered"
        f"?cursor={cursor_slot}&limit={limit}"
    )

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(endpoint, timeout=timeout)
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, list):
                raise ValueError("Unexpected response format (expected list)")

            rows: List[dict] = []
            for item in payload:
                rows.append(
                    {
                        "relay_url": relay,
                        "slot": int(item["slot"]),
                        "block_number": int(item["block_number"]),
                        "block_hash": item["parent_hash"],
                        "builder_pk": item["builder_pubkey"],
                        "proposer_pk": item["proposer_pubkey"],
                        "proposer_fee_recipient": item["proposer_fee_recipient"],
                        "gas_limit": int(item["gas_limit"]),
                        "gas_used": int(item["gas_used"]),
                        "value": int(item["value"]),
                        "num_tx": int(item["num_tx"]),
                    }
                )
            return rows  # [] means HTTP 200 but relay has no data for this cursor
        except Exception as exc:  # noqa: BLE001
            wait_seconds = min(2, 2**attempt)
            logger.warning(
                "Relay request failed (%s, attempt %s/%s): %s. Retrying in %ss",
                relay,
                attempt,
                max_retries,
                exc,
                wait_seconds,
            )
            time.sleep(wait_seconds)

    logger.error("Giving up on request for relay %s at cursor %s", relay, cursor_slot)
    return None  # None means all retries exhausted (real network failure)


def insert_rows(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    rows: List[dict],
) -> int:
    if not rows:
        return 0

    df = pd.DataFrame(rows)
    conn.register("batch_df", df)

    # Avoid duplicate inserts when rerunning or when relay pages overlap.
    conn.execute(
        f"""
        INSERT INTO {table_name}
        SELECT b.*
        FROM batch_df b
        WHERE NOT EXISTS (
            SELECT 1
            FROM {table_name} t
            WHERE t.relay_url = b.relay_url
              AND t.slot = b.slot
              AND t.block_hash = b.block_hash
        )
        """
    )
    inserted = conn.execute("SELECT COUNT(*) FROM batch_df").fetchone()[0]
    conn.unregister("batch_df")
    return int(inserted)


def collect_relay_for_range(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    relay: str,
    slot_start: int,
    slot_end: int,
    limit: int,
    timeout: int,
    max_retries: int,
    sleep_seconds: float,
    logger: logging.Logger,
) -> Tuple[int, List[int]]:
    total_inserted = 0
    failed_cursors: List[int] = []
    cursor = slot_end

    logger.info("Relay %s | range %s-%s", relay, slot_start, slot_end)

    while cursor >= slot_start:
        batch = fetch_batch(
            relay=relay,
            cursor_slot=cursor,
            limit=limit,
            timeout=timeout,
            max_retries=max_retries,
            logger=logger,
        )

        if batch is None:
            # Real network failure after all retries — record cursor and skip ahead.
            logger.warning(
                "Request failed for relay %s at cursor %s — skipping ahead by %s slots",
                relay, cursor, limit,
            )
            failed_cursors.append(cursor)
            cursor -= limit
            continue

        if not batch:
            # HTTP 200 but empty list — relay simply has no data here.
            logger.info("Relay %s has no data at cursor %s — stopping", relay, cursor)
            break

        # Keep only rows inside the inclusive quarter range.
        in_range = [row for row in batch if slot_start <= row["slot"] <= slot_end]
        total_inserted += insert_rows(conn, table_name, in_range)

        min_slot_batch = min(row["slot"] for row in batch)

        if min_slot_batch < slot_start:
            # We crossed below the target range; this relay is done for this quarter.
            break

        next_cursor = min_slot_batch - 1
        if next_cursor >= cursor:
            # Guard against unexpected non-decreasing pagination behavior.
            next_cursor = cursor - 1
        cursor = next_cursor

        time.sleep(sleep_seconds)

    return total_inserted, failed_cursors


def collect_quarter(
    quarter: str,
    slot_start: int,
    slot_end: int,
    output_dir: str,
    table_name: str,
    limit: int,
    timeout: int,
    max_retries: int,
    sleep_seconds: float,
    logger: logging.Logger,
) -> Dict[str, List[int]]:
    db_path = os.path.join(output_dir, f"{quarter}.duckdb")
    logger.info("Starting %s -> %s", quarter, db_path)

    conn = duckdb.connect(db_path)
    try:
        create_table(conn, table_name)

        quarter_inserted = 0
        all_failed: Dict[str, List[int]] = {}
        for relay in RELAYS:
            inserted, failed = collect_relay_for_range(
                conn=conn,
                table_name=table_name,
                relay=relay,
                slot_start=slot_start,
                slot_end=slot_end,
                limit=limit,
                timeout=timeout,
                max_retries=max_retries,
                sleep_seconds=sleep_seconds,
                logger=logger,
            )
            quarter_inserted += inserted
            if failed:
                key = f"{quarter}|{relay}"
                all_failed[key] = failed
            logger.info("%s | %s | %s inserted rows, %s failed cursors", quarter, relay, inserted, len(failed))

        logger.info("Finished %s with %s inserted rows", quarter, quarter_inserted)
    finally:
        conn.close()

    return all_failed


def main() -> None:
    args = parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("download_relay_data_quarters")

    for quarter, (slot_start, slot_end) in QUARTERS.items():
        effective_slot_end = args.slot_end if args.slot_end is not None else slot_end
        failed = collect_quarter(
            quarter=quarter,
            slot_start=slot_start,
            slot_end=effective_slot_end,
            output_dir=args.output_dir,
            table_name=args.table,
            limit=args.limit,
            timeout=args.request_timeout,
            max_retries=args.max_retries,
            sleep_seconds=args.sleep_seconds,
            logger=logger,
        )
        if failed:
            failed_path = os.path.join(args.output_dir, args.failed_slots_file)
            existing: Dict[str, List[int]] = {}
            if os.path.exists(failed_path):
                with open(failed_path) as fh:
                    existing = json.load(fh)
            for key, slots in failed.items():
                existing.setdefault(key, []).extend(slots)
            with open(failed_path, "w") as fh:
                json.dump(existing, fh, indent=2)
            logger.info("Appended failed cursors to %s", failed_path)

    logger.info("All quarters finished. Databases are in %s", args.output_dir)


if __name__ == "__main__":
    main()
