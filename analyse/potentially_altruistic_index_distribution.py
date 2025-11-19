# depends_on: proposer_collaboration.py,ordering_clusters.py,coinbase_clusters.py
import json
import pandas as pd
import numpy as np
from itertools import chain
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick


with open("out/proposer_collaboration-overview.json") as file:
    all_proposers = pd.DataFrame.from_dict(json.load(file)['all_proposers'])

with open('out/including_xof.json') as file:
    json_obj = json.load(file)
    not_including_xof_clusters = json_obj['not_including_xof_clusters']

non_relaying_clusters_proposer_coinbase = pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')

min_index = all_proposers['proposer_index'].min()
max_index = all_proposers['proposer_index'].max()

potentially_altruistic_proposer_index = non_relaying_clusters_proposer_coinbase[non_relaying_clusters_proposer_coinbase['coinbase_addr'].isin(chain(*not_including_xof_clusters))]['proposer_index'].unique()
print(f"# potentially ordering proposers: {len(potentially_altruistic_proposer_index)}")
print(f"Median index of potentially ordering proposers: {np.median(potentially_altruistic_proposer_index)}")

print(f"Min/Max proposer index: {min_index}-{max_index}")


counts, bins = np.histogram(potentially_altruistic_proposer_index, bins=50, range=(min_index, max_index))

fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(8,5))

plt.axvline(428308, color="black", linestyle="--", lw=1.0) # 428308 is the last validator before the Merge
plt.text(440000,600,'The Merge',rotation=90)

ax.stairs(counts, bins)
ax.set_xlim([min_index, max_index])
ax.set_xticks([min_index, 1_000_000, 1_900_000], [str(min_index), str(1_000_000), str(1_900_000)])
ax.set_xlabel("Proposer Index")
ax.set_ylabel("Number of potentially altruistic proposers")

fig.savefig("out/potentially_altruistic_index_distribution-histogram.png")
fig.savefig("out/potentially_altruistic_index_distribution-histogram.svg")


# calculate relative share
rel_counts = []
all_counts = []
for i in range(1, len(bins)):
    if i == len(bins) - 1:
        all_in_bin = all_proposers[all_proposers.proposer_index.between(bins[i-1],bins[i])]['proposer_index'].count()
    else:
        all_in_bin = all_proposers[all_proposers.proposer_index.between(bins[i-1],bins[i], inclusive='left')]['proposer_index'].count()

    all_counts.append(all_in_bin)
    rel_counts.append(counts[i-1] / all_in_bin)

fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(8,5))

plt.axvline(428308, color="black", linestyle="--", lw=1.0) # 428308 is the last validator before the Merge
plt.text(440000,0.088,'The Merge',rotation=90)

ax.stairs(rel_counts, bins, fill="orange")
ax.set_xlim([min_index, max_index])
ax.set_xticks([min_index, 1_000_000, 1_900_000], [str(min_index), str(1_000_000), str(1_900_000)])
ax.set_xlabel("Proposer Index")
ax.set_ylabel("Share of potentially altruistic proposers")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))

fig.savefig("out/potentially_altruistic_index_share-histogram.png")
fig.savefig("out/potentially_altruistic_index_share-histogram.svg")


fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(8,5))

plt.axvline(428308, color="black", linestyle="--", lw=1.0) # 428308 is the last validator before the Merge
ax.text(440000,600,'The Merge',rotation=90)

ax.stairs(counts, bins)
ax.set_xlim([min_index, max_index])
ax.set_xticks([min_index, 1_000_000, 1_900_000], [str(min_index), str(1_000_000), str(1_900_000)])
ax.set_xlabel("Proposer Index")
ax.set_ylabel("Number of potentially altruistic proposers")

ax2 = ax.twinx() 
ax2.stairs(all_counts, bins, color='orange')
ax2.set_ylabel("Number of all observed proposers")

fig.savefig("out/potentially_altruistic_index_both-histogram.png")
fig.savefig("out/potentially_altruistic_index_both-histogram.svg")


