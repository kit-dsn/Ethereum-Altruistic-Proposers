import utils.query
import pandas as ps
import matplotlib.pyplot as plt
import numpy as np

df = utils.query.query_cache("""
    SELECT gas_spearman, gas_kendall FROM analyse_blocks2;
""")

# an overview over the ordering
fig, ax = plt.subplots(nrows=1, ncols=1)

gas_spearman = df[df['gas_spearman'].notna()]['gas_spearman']
ax.hist(gas_spearman, range=(-1,1), bins=100, color='red', histtype='step', label='Gas (spearman correlation)')

gas_kendall = df[df['gas_kendall'].notna()]['gas_kendall']
ax.hist(gas_kendall, range=(-1,1), bins=100, color='blue', histtype='step', label='Gas (kendall correlation)')

ax.legend()
ax.set_title("Ordering of Transactions for non-relaying proposers")
fig.savefig("out/ordering_non_pbs-histogram.png")
