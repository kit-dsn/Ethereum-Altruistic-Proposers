# Ethereum's Fairness Mechanisms Should Not Depend on Participants' Altruism (Paper)

This repository contains the code and data-processing pipeline for a research paper on altruistic behavior among Ethereum block proposers.

Original script author: Nils Henrik Beyer (usmos@student.kit.edu).

Modifications and contact person: Patrick Spiesberger (patrick.spiesberger@kit.edu)

## Abstract

Ethereum's ideal of censorship resistance, along with other fairness properties, is undermined in practice, motivating fairness mechanisms designed to restore them.
Recent proposals rely on a 1-of-n honest assumption: at least one proposer follows such a mechanism even when deviation would increase personal revenue.
We refer to such proposers as altruistic.
Prior work, however, shows that approximately 91 % of blocks were constructed by centralized block-building services that demonstrably carry out user-adverse actions for financial gain.
The proposers the protocol holds responsible for these blocks sign them blindly, without any possibility of intervention, which gives rise to the common assumption that 9 % of proposers forgo these gains and act altruistically.
Our empirical analysis of the full year 2025 finds that this share is substantially smaller: at most 1.4 % could plausibly be considered altruistic, while 98.6 % of proposers depend on these centralized builders.
We interpret this share of 1.4 % as an upper bound on the prevalence of altruistic proposers.
These results imply that committee-based fairness mechanisms that rely on altruistic members would require substantially larger committees than currently proposed.
This raises concerns about their practical viability and motivates mechanisms in which fair behavior is the rational choice.

## Repository Structure

- `collectors/`: scripts that pull raw blockchain/relay/deposit data from EL/CL nodes and third-party APIs into DuckDB. Several files are successive iterations of the same idea (e.g. `download_coinbase.py` → `_v2` → `_v3`) kept for provenance; see [Rebuilding the dataset from scratch](#2-rebuilding-the-dataset-from-scratch-advanced) for which one to actually run. A few others (`fetch_proposers.py`, `recheck_coinbase.py`, `recheck_coinbase_migrate.py`, `import_private_transactions_q1.py`) are one-off tools tied to the authors' own infrastructure rather than reusable pipeline steps - see [One-off / internal scripts](#one-off--internal-scripts).
- `analyse/`: the actual paper pipeline - reads from one DuckDB database and produces every figure and statistic. This is the part anyone can re-run, given a populated database (see [Reproducing the figures](#1-reproducing-the-figures-from-an-existing-database)).
- `run_scripts.py`: runs every script in `analyse/` in dependency order (declared via a `# depends_on:` header in each file).
- `out/`: generated outputs (PDF figures, JSON intermediate results, HTML reports).
- `cache/`: query result cache keyed by the SQL text (see `analyse/utils/query.py`). Safe to delete; delete it whenever the underlying database changes, since a stale cache entry would otherwise be reused for an unchanged query text even though the data behind it changed.

## Installation

A virtual environment is recommended. The pipeline is developed against Python 3.12 and should work on any 3.11+ interpreter (it relies on `datetime.UTC`, added in 3.11).

1) Create and activate a virtual environment:

   ```
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2) Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3) `analyse/interacting_with_builders.py` needs a list of known MEV-builder addresses. Export https://etherscan.io/accounts/label/mev-builder as JSON (Etherscan login required) and save it as `analyse/interacting_with_builders-builder-addrs.json`.

4) Create empty `cache/` and `out/` directories if they don't already exist - the analysis scripts write into them but don't create them.

## 1) Reproducing the figures from an existing database

This is the realistic "just run it" path: you already have (or were given) one DuckDB file containing the full, merged dataset described in [Database Schema](#database-schema) below.

```
export ANALYSE_DUCKDB_PATH=/path/to/your.duckdb
python3 run_scripts.py
```

`run_scripts.py` topologically sorts `analyse/*.py` by their `# depends_on:` header and runs each one with `ANALYSE_DUCKDB_PATH` set in its environment, so they all read from the same database. Figures (PDF), intermediate results (JSON) and HTML overviews land in `out/` (see [Outputs and HTML Reports](#outputs-and-html-reports)).

You can also pass the path explicitly instead of using the environment variable:

```
python3 run_scripts.py -d /path/to/your.duckdb
```

**Do not run an individual `analyse/*.py` script directly without setting `ANALYSE_DUCKDB_PATH` (or going through `run_scripts.py`).** Each script falls back to its own hardcoded default path if the variable is unset.

## 2) Rebuilding the dataset from scratch (advanced)

Rebuilding the database from public sources needs an Ethereum execution-layer node (full historical `eth_getBlockByNumber`/`eth_getCode` history) and consensus-layer node, a beaconcha.in API key, and (for the private-transaction analysis) a private order-flow / mempool-observation dataset that isn't included in this repository. What follows documents how the included collectors fit together; treat it as a reference for re-collecting your own slice of data, not a one-shot script.

### Infrastructure

- Execution-layer (EL) JSON-RPC endpoint, default `http://localhost:8504` (overridden via `EL_API_BASE` inside each script, no CLI flag).
- Consensus-layer (CL) REST endpoint, default `http://localhost:5052` (`CL_API_BASE`, same caveat).
- A beaconcha.in API key for `download_coinbase_v3.py --key` and `download_deposit_addr.py --key`.

Every collector takes its own `-d/--database` (or, in the newer ones, `--output-dir`) argument - **always pass it explicitly.**

### Collection pipeline

The collectors fill several **per-quarter** DuckDB files (`q1.duckdb` .. `q4.duckdb`) with raw tables; the `analyse/` pipeline then expects one merged database with the combined `*_all` tables described below.

1. **Relay data** → raw `relay_payloads` table, one row per delivered bid.
   - `python3 collectors/download_relay_data_quarters.py --output-dir <dir>` - the current batch tool; queries every relay listed in its `RELAYS` list for all four quarters.
   - `python3 collectors/download_titan_relay.py --output-dir <dir>` - re-run only against the Titan relay if it rate-limited the run above (titanrelay.xyz tends to return HTTP 429 under the default pacing).
   - `download_relay_data.py <relay_url> -d <db> --start <slot> --end <slot> <table>` is the older single-relay/single-database version of the same idea; kept for provenance.
2. **Coinbase / proposer data** → raw `coinbase_data` table (block number, slot, proposer_index, coinbase_addr, extra_data).
   - `python3 collectors/download_coinbase_v3.py <table> -d <db> --key <beaconcha.in-key> --start <block> --end <block>` - current version.
   - `download_coinbase_v2.py` is the same without the beaconcha.in key (less complete proposer-index resolution).
3. **Account classification** (EOA vs. contract) → `accounts` table.
   - `python3 collectors/fetch_account_code.py -d <db> -t accounts` - calls `eth_getCode` per coinbase address found in `coinbase_blocks_all`, so run this after the coinbase/relay merge.
4. **Validator deposits** → `validator_deposits` table.
   - `python3 collectors/download_deposit_addr.py <table> -d <db> --key <beaconcha.in-key>` - reads `proposer_index` values straight out of `coinbase_blocks_all`, so this also needs the merge from step 2/3 done first.
5. **Private transactions** → `mempool_private` / `private_blocks` tables.
6. **Per-block ordering/privacy statistics** → `analyse_blocks` table.
   - `python3 collectors/calc_block_statistics.py -d <db> -t analyse_blocks` - run this last; it reads the non-relaying cluster JSON files that `analyse/coinbase_clusters.py` and `analyse/proposer_clusters.py` produce, so part of the `analyse/` pipeline has to run first (see `analyse/ordering_clusters.py`/`ordering_non_pbs.py`, which in turn consume `analyse_blocks`).

### One-off / internal scripts

These exist for provenance and are not meant to be re-run as general-purpose tools:

- `fetch_proposers.py` - recomputes proposer duties for one fixed epoch from a public beacon API as an independent sanity check of the beacon-chain shuffle logic. No database, no CLI arguments; edit `TARGET_EPOCH`/`API_BASE` in the file if you want to check a different epoch.
- `recheck_coinbase.py` / `recheck_coinbase_migrate.py` - re-validate and patch slot numbers for a known batch of mismatched blocks; both hardcode the (misspelled) `altrusitic_proposers.duckdb` path from an earlier stage of the project.
- `import_private_transactions_q1.py` - one-off Q1 migration with hardcoded source/target paths and block range (see step 5 above).

## Database Schema

The `analyse/` pipeline expects a single DuckDB database with these tables. "Source" says how the table gets populated; "merged" tables are not created directly by any one collector (see [Collection pipeline](#collection-pipeline)).

| Table | Source | Notes |
|---|---|---|
| `coinbase_blocks_all` | merged from `coinbase_data` across quarters | block_number, slot, proposer_index, coinbase_addr, extra_data |
| `relay_all` | merged from `relay_payloads` across quarters/relays | one row per bid a relay delivered |
| `accounts` | `fetch_account_code.py` | coinbase_addr → is_account (EOA vs. contract) |
| `validator_deposits` | `download_deposit_addr.py` | proposer_index → deposit `from_address` etc. |
| `mempool_private` | private-tx pipeline (step 5) | one row per private transaction |
| `private_blocks` | private-tx pipeline (step 5) | per-block private-transaction counts |
| `analyse_blocks` | `calc_block_statistics.py` | per-block ordering/privacy indicators, used by `ordering_clusters.py`/`ordering_non_pbs.py` |

## Outputs and HTML Reports

Results are written to `out/`. This includes:

- PDF figures (used in the paper)
- JSON summary files (intermediate results, also re-read by downstream scripts)
- Self-contained HTML reports you can open directly in a browser:
  - `out/ordering_non_pbs-overview.html`
  - `out/private_transactions_clusters-overview.html`
  - `out/proposer_extra_data_overview.html`
  - `out/meta-overview.html`

## Reproducibility Notes

- Re-running the full pipeline against an unchanged database reproduces the same figures and JSON content; cluster ordering (coinbase/proposer clustering) is sorted before being written out specifically so re-runs are byte-identical rather than depending on Python's per-process hash seed.
- `cache/` persists query results across runs to avoid re-scanning the (multi-GB) database on every tweak of a downstream script. Delete it after replacing the underlying database - the cache key is only the SQL text, not the data.
- The analysis order is controlled through each script's `# depends_on:` header and resolved by `run_scripts.py`.

## Quick Start

If you already have a populated database:

```
pip install -r requirements.txt
export ANALYSE_DUCKDB_PATH=/path/to/your.duckdb
python3 run_scripts.py
```

Open any of the HTML files in `out/` (see above) or the PDF figures to inspect the results. If you need to build that database yourself first, see [Rebuilding the dataset from scratch](#2-rebuilding-the-dataset-from-scratch-advanced).
