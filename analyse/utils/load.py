"""Loaders for intermediate results produced by coinbase_clusters.py.

Several downstream scripts need the same clustering result, so it is
written to out/ once and re-read here instead of being recomputed.
"""

import json
import pandas as pd


def non_relaying_coinbase_clusters():
    """Coinbase address clusters that never appear in any relay's bids (see coinbase_clusters.py)."""
    with open("out/coinbase_clusters-non-relaying-clusters.json") as file:
        return json.load(file)


def non_relaying_clusters_proposer_coinbase():
    """Per-block (proposer, coinbase) pairs restricted to the non-relaying clusters above."""
    return pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')