import json
import pandas as pd
import numpy as np
from itertools import chain
import matplotlib.pyplot as plt


with open("out/proposer_collaboration-overview.json") as file:
    all_proposers = pd.DataFrame.from_dict(json.load(file)['all_proposers'])

with open('out/ordering_clusters.json') as file:
    strictly_decending_clusters = json.load(file)['strictly_decending_clusters']

non_relaying_clusters_proposer_coinbase = pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')

min_index = all_proposers['proposer_index'].min()
max_index = all_proposers['proposer_index'].max()

strictly_proposer_index = non_relaying_clusters_proposer_coinbase[non_relaying_clusters_proposer_coinbase['coinbase_addr'].isin(chain(*strictly_decending_clusters))]['proposer_index'].unique()
print(f"# strictly odering proposers: {len(strictly_proposer_index)}")
print(f"Median index of strictly ordering proposers: {np.median(strictly_proposer_index)}")

print(f"Min/Max proposer index: {min_index}-{max_index}")


counts, bins = np.histogram(strictly_proposer_index, bins=100, range=(min_index, max_index))

fig, ax = plt.subplots(nrows=1, ncols=1)
ax.stairs(counts, bins)
ax.set_xlim([min_index, max_index])
ax.set_xticks([min_index, (min_index+max_index)//2, max_index], [str(min_index), str((min_index+max_index)//2), str(max_index)])
ax.set_xlabel("Proposer Index")
ax.set_ylabel("Number of strictly ordering proposers")

fig.savefig("out/altruistic_index_distribution-histogram.png")
fig.savefig("out/altruistic_index_distribution-histogram.svg")
