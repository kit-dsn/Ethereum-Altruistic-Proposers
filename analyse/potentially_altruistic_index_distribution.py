"""
Purpose
    Visualizes the proposer index distribution for potentially altruistic
    proposers and compares it to the overall proposer population.

Outputs
    Histogram PDFs in out/.
"""

# depends_on: proposer_collaboration.py,ordering_clusters.py,coinbase_clusters.py
import json
import pandas as pd
import numpy as np
from itertools import chain
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick


MERGE_INDEX = 428308


def format_int_de(value):
    return f"{int(value):,}".replace(",", ".")


def apply_index_ticks(ax, min_index, max_index):
    ticks = [min_index, 1_000_000, 2_000_000]
    labels = [format_int_de(x) for x in ticks]
    ax.set_xticks(ticks, labels)


def set_uniform_ylabel_position(axes, x_position=-0.11):
    for ax in axes:
        ax.yaxis.set_label_coords(x_position, 0.5)


def add_merge_line(ax, with_label=False, y_pos=None, label_left=False):
    ax.axvline(MERGE_INDEX, color="black", linestyle="--", lw=1.0)
    if with_label:
        if y_pos is None:
            y_pos = 0.74
        x_offset = -8 if label_left else 8
        horizontal_alignment = "right" if label_left else "left"
        ax.annotate(
            "The Merge",
            xy=(MERGE_INDEX, y_pos),
            xycoords=("data", "axes fraction"),
            xytext=(x_offset, 0),
            textcoords="offset points",
            rotation=90,
            va="center",
            ha=horizontal_alignment,
            clip_on=True,
        )


with open("out/proposer_collaboration-overview.json") as file:
    all_proposers = pd.DataFrame.from_dict(json.load(file)['all_proposers'])

with open('out/including_xof.json') as file:
    json_obj = json.load(file)
    including_xof_proposers = json_obj['including_xof_proposers']
    not_including_xof_proposers = json_obj['not_including_xof_proposers']

with open('out/ordering_clusters.json') as file:
    json_obj = json.load(file)
    altruistic_proposers = json_obj['remaining_proposers']

min_index = all_proposers['proposer_index'].min()
max_index = all_proposers['proposer_index'].max()

potentially_altruistic_proposer_index = not_including_xof_proposers
print(f"# potentially ordering proposers: {len(potentially_altruistic_proposer_index)}")
print(f"Median index of potentially ordering proposers: {np.median(potentially_altruistic_proposer_index)}")

print(f"Min/Max proposer index: {min_index}-{max_index}")


counts, bins = np.histogram(potentially_altruistic_proposer_index, bins=50, range=(min_index, max_index))
altruistic_counts, _ = np.histogram(altruistic_proposers, bins=bins)
validators_per_bin = int(round(bins[1] - bins[0]))

fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(8,5))

ax.stairs(counts, bins)
add_merge_line(ax, with_label=False)
ax.set_xlim([min_index, max_index])
apply_index_ticks(ax, min_index, max_index)
ax.set_xlabel("Proposer Index")
ax.set_ylabel("Number of potentially altruistic proposers")

fig.savefig("out/potentially_altruistic_index_distribution-histogram.pdf")


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

ax.stairs(rel_counts, bins, fill="orange")
add_merge_line(ax, with_label=False)
ax.set_xlim([min_index, max_index])
apply_index_ticks(ax, min_index, max_index)
ax.set_xlabel("Proposer Index")
ax.set_ylabel("Share of potentially altruistic proposers")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0))

fig.savefig("out/potentially_altruistic_index_share-histogram.pdf")


fig, ax = plt.subplots(nrows=1, ncols=1, figsize=(8,5))

ax.stairs(counts, bins)
add_merge_line(ax, with_label=False)
ax.set_xlim([min_index, max_index])
apply_index_ticks(ax, min_index, max_index)
ax.set_xlabel("Validator Index")
ax.set_ylabel("Potentially altruistic proposers")

ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: format_int_de(x)))

fig_three, (ax_all, ax_potential, ax_altruistic) = plt.subplots(
    nrows=3,
    ncols=1,
    sharex=True,
    figsize=(8,9),
    height_ratios=[3, 3, 2],
)

ax_all.stairs(all_counts, bins, color='blue')
add_merge_line(ax_all, with_label=False)
ax_all.set_ylabel("Distinctive proposers in Q1-Q3 2025")
ax_all.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: format_int_de(x)))

ax_potential.stairs(counts, bins, color='orange')
add_merge_line(ax_potential, with_label=True, label_left=True)
ax_potential.set_ylabel("Potentially altruistic proposers")
ax_potential.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: format_int_de(x)))

ax_altruistic.stairs(altruistic_counts, bins, color='green')
add_merge_line(ax_altruistic, with_label=False)
ax_altruistic.set_title("Altruistic proposers")
ax_altruistic.set_ylabel("Altruistic proposers")
ax_altruistic.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: format_int_de(x)))
ax_altruistic.set_xlabel(f"Validator Index ({format_int_de(validators_per_bin)} validators per bin)", fontsize=11)

for axis in (ax_all, ax_potential, ax_altruistic):
    axis.set_xlim([min_index, max_index])

ax_all.set_title("All observed proposers")
ax_potential.set_title("Potentially altruistic proposers")
apply_index_ticks(ax_altruistic, min_index, max_index)
set_uniform_ylabel_position((ax_all, ax_potential, ax_altruistic))

fig.savefig("out/potentially_altruistic_index_both-histogram.pdf")
fig_three.savefig("out/potentially_altruistic_index_three-histogram.pdf")


fig, (ax, ax2) = plt.subplots(sharex=True, nrows=2, ncols=1, height_ratios=[3,5])

ax.stairs(all_counts, bins, color='orange')
add_merge_line(ax, with_label=False)
ax.set_title("All observed proposers")
ax.set_ylabel("# proposers")
ax.set_xlim([min_index, max_index])
ax.set_ylim([2_000, 21_000])
ax.set_yticks([2_000, 10_000, 20_000])
ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: format_int_de(x)))

ax2.stairs(counts, bins)
add_merge_line(ax2, with_label=True)
ax2.set_title("Potentially altruistic proposers")
ax2.set_xlim([min_index, max_index])
apply_index_ticks(ax2, min_index, max_index)
ax2.set_xlabel("Proposer Index")
ax2.set_ylabel("# proposers")
ax2.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: format_int_de(x)))
set_uniform_ylabel_position((ax, ax2))

fig.savefig("out/potentially_altruistic_index_both-side-histogram.pdf")

