"""
Purpose
    Re-collect proposer_payload_delivered traces from https://titanrelay.xyz
    for all four quarters and insert them into the existing q1-q4 DuckDB
    databases.  Already-inserted rows are skipped via duplicate detection.

    Use this script when the main download_relay_data_quarters.py run was
    rate-limited (HTTP 429) for the Titan relay.

Usage
    python3 collectors/download_titan_relay.py
    python3 collectors/download_titan_relay.py --sleep-seconds 10
    python3 collectors/download_titan_relay.py --output-dir /data/fast/historical_mempools/altruistic_proposers

Q -> Slot ranges
    Q1   10738799 - 11386798
    Q2   11386799 - 12041998
    Q3   12041999 - 12704398
    Q4   12704399 - 13366798
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


TITAN_RELAY = "https://titanrelay.xyz/"

QUARTERS: Dict[str, Tuple[int, int]] = {
#    "q1": (10738799, 11386798),
#    "q2": (11386799, 12041998),
#    "q3": (12041999, 12704398),
    "q4": (12704399, 13366798),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Download Titan Relay Data",
        description=(
            "Re-downloads proposer_payload_delivered from https://titanrelay.xyz "
            "for Q1-Q4 with a higher request delay to avoid rate-limiting."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="/data/fast/historical_mempools/altruistic_proposers",
        help="Directory containing q1.duckdb..q4.duckdb",
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
        default=60,
        help="HTTP timeout in seconds (higher than default to cope with Titan latency)",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=2,
        help="Sleep between successful API calls (increase if still rate-limited)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries per request",
    )
    parser.add_argument(
        "--failed-slots-file",
        default="titan_failed_slots.json",
        help="Filename (inside --output-dir) to write failed cursor slots to",
    )
    parser.add_argument(
        "--slot-end",
        type=int,
        default=None,
        help="Override the slot_end (starting cursor) for all quarters — useful to resume from a specific slot",
    )
    return parser.parse_args()


def create_table_if_missing(conn: duckdb.DuckDBPyConnection, table_name: str) -> None:
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
    cursor_slot: int,
    limit: int,
    timeout: int,
    max_retries: int,
    sleep_on_retry: float,
    logger: logging.Logger,
) -> Optional[List[dict]]:
    endpoint = (
        f"{TITAN_RELAY}/relay/v1/data/bidtraces/proposer_payload_delivered"
        f"?cursor={cursor_slot}&limit={limit}"
    )

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(endpoint, timeout=timeout)
            response.raise_for_status()
            payload = response.json()

            if not isinstance(payload, list):
                raise ValueError(f"Unexpected response format: {type(payload)}")

            rows: List[dict] = []
            for item in payload:
                rows.append(
                    {
                        "relay_url": TITAN_RELAY,
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
            return rows  # [] means HTTP 200 but no data for this cursor

        except Exception as exc:  # noqa: BLE001
            # Use a longer base wait on 429 to respect rate limits.
            if hasattr(exc, "response") and getattr(exc.response, "status_code", None) == 429:
                wait_seconds = min(2, max(sleep_on_retry * 2, 2**attempt))
            else:
                wait_seconds = min(2, 2**attempt)
            logger.warning(
                "Request failed (attempt %s/%s): %s. Retrying in %ss",
                attempt,
                max_retries,
                exc,
                wait_seconds,
            )
            time.sleep(wait_seconds)

    logger.error("Giving up on Titan request at cursor %s", cursor_slot)
    return None  # None means all retries exhausted (real network failure)


def insert_rows(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    rows: List[dict],
) -> int:
    if not rows:
        return 0

    df = pd.DataFrame(rows)
    conn.register("titan_batch", df)

    conn.execute(
        f"""
        INSERT INTO {table_name}
        SELECT b.*
        FROM titan_batch b
        WHERE NOT EXISTS (
            SELECT 1
            FROM {table_name} t
            WHERE t.relay_url = b.relay_url
              AND t.slot      = b.slot
              AND t.block_hash = b.block_hash
        )
        """
    )
    inserted = conn.execute("SELECT COUNT(*) FROM titan_batch").fetchone()[0]
    conn.unregister("titan_batch")
    return int(inserted)


def collect_titan_for_quarter(
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
) -> Tuple[int, List[int]]:
    db_path = os.path.join(output_dir, f"{quarter}.duckdb")
    logger.info("Opening %s for Titan data (%s-%s)", db_path, slot_start, slot_end)

    conn = duckdb.connect(db_path)
    total_inserted = 0
    failed_cursors: List[int] = []
    try:
        create_table_if_missing(conn, table_name)

        cursor = slot_end
        while cursor >= slot_start:
            batch = fetch_batch(
                cursor_slot=cursor,
                limit=limit,
                timeout=timeout,
                max_retries=max_retries,
                sleep_on_retry=sleep_seconds,
                logger=logger,
            )

            if batch is None:
                logger.warning(
                    "Request failed at cursor %s — skipping ahead by %s slots (%s)",
                    cursor, limit, quarter,
                )
                failed_cursors.append(cursor)
                cursor -= limit
                continue

            if not batch:
                # HTTP 200 but empty — Titan has no data here.
                logger.info("No data at cursor %s — stopping %s", cursor, quarter)
                break

            in_range = [row for row in batch if slot_start <= row["slot"] <= slot_end]
            newly_inserted = insert_rows(conn, table_name, in_range)
            total_inserted += newly_inserted

            min_slot_batch = min(row["slot"] for row in batch)
            logger.info(
                "%s | cursor=%s min_slot=%s in_range=%s inserted=%s",
                quarter, cursor, min_slot_batch, len(in_range), newly_inserted,
            )

            if min_slot_batch < slot_start:
                break

            next_cursor = min_slot_batch - 1
            if next_cursor >= cursor:
                next_cursor = cursor - 1
            cursor = next_cursor

            time.sleep(sleep_seconds)

    finally:
        conn.close()

    return total_inserted, failed_cursors


def main() -> None:
    args = parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("download_titan_relay")

    logger.info(
        "Starting Titan relay collection with %.1fs sleep between requests",
        args.sleep_seconds,
    )

    total = 0
    all_failed: Dict[str, List[int]] = {}
    for quarter, (slot_start, slot_end) in QUARTERS.items():
        effective_slot_end = args.slot_end if args.slot_end is not None else slot_end
        inserted, failed = collect_titan_for_quarter(
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
        total += inserted
        if failed:
            all_failed[quarter] = failed
        logger.info(
            "Finished %s — %s new rows from Titan, %s failed cursors",
            quarter, inserted, len(failed),
        )

    if all_failed:
        failed_path = os.path.join(args.output_dir, args.failed_slots_file)
        with open(failed_path, "w") as fh:
            json.dump(all_failed, fh, indent=2)
        logger.info("Wrote failed cursors to %s", failed_path)

    logger.info("Done. Total Titan rows inserted across all quarters: %s", total)


if __name__ == "__main__":
    main()
