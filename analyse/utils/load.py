import json
import pandas as pd

def non_relaying_coinbase_clusters():
    with open("out/coinbase_clusters-non-relaying-clusters.json") as file:
        return json.load(file)

def non_relaying_clusters_proposer_coinbase():
    return pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')