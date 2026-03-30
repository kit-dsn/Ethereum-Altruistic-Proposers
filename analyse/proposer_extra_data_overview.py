"""
Purpose
    Produces an HTML overview of extra_data behavior across non-relaying
    coinbase clusters, including global vs non-global patterns.

Outputs
    out/proposer_extra_data_overview.html and linked assets.
"""

# depends_on: proposer_extra_data.py,proposer_extra_data_organize.py,coinbase_clusters.py
import pandas as pd
import json

# generate an html doc from the proposer_extra_data

htmlOut = "<!DOCTYPE html><html><head><title>RFC - proposer_extra_data_overview</title></head><body>\n"

# overview
htmlOut += "<h1>Overview</h1>\n"
htmlOut += "<p>We are only looking at non_relaying validators!</p>\n"

with open('out/coinbase_clusters-non-relaying-clusters.json') as file:
    non_relaying_clusters = json.load(file)

non_relaying_coinbase = pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')

proposer_extra_overall = pd.read_json('out/proposer_extra_data-overall.json')

trivial_cases = pd.concat([
    proposer_extra_overall[proposer_extra_overall['num_proposers'] == 1],
    proposer_extra_overall[proposer_extra_overall['num_extra_data'] == 1],
    proposer_extra_overall[proposer_extra_overall['num_proposers'] == proposer_extra_overall['num_extra_data']]
])
trivial_cases = trivial_cases[~trivial_cases.index.duplicated(keep='first')]

mask_non_trivial = (
    (proposer_extra_overall['num_proposers'] > 1)
    & (proposer_extra_overall['num_extra_data'] > 1)
    & (proposer_extra_overall['num_extra_data'] != proposer_extra_overall['num_proposers'])
)
non_trivial_cases = proposer_extra_overall[mask_non_trivial]
non_trivial_cases = non_trivial_cases.sort_values(by='num_proposers', ascending=False).reset_index(drop=True)

htmlOut += f"""
    <table border=1>
        <tr>
            <td><a href='#h1-trivial'><b>Trivial Cases</b></a></td>
            <td>{len(trivial_cases)} ({len(trivial_cases)/len(non_relaying_clusters) * 100}%) <br> coinbase-addr clusters</td>
            <td>{trivial_cases['num_blocks'].sum()} blocks</td>
            <td>{trivial_cases['num_proposers'].sum()} validators</td>
        </tr>
        <tr>
            <td><a href='#h1-non-trivial'><b>Non-Trivial Cases</b></a></td>
            <td>{len(non_trivial_cases)} ({len(non_trivial_cases)/len(non_relaying_clusters) * 100}%) <br> coinbase-addr clusters</td>
            <td>{non_trivial_cases['num_blocks'].sum()} blocks</td>
            <td>{non_trivial_cases['num_proposers'].sum()} validators</td>
        </tr>
        <tr>
            <td>Σ</td>
            <td>{len(non_relaying_clusters)} <br> coinbase-addr clusters</td>
            <td>{non_relaying_coinbase['count'].sum()} blocks</td>
            <td>{len(non_relaying_coinbase['proposer_index'].unique())} validators</td>
        <tr>
    </table>    
"""

# Trivial Cases
htmlOut += f"""
    <h1 id="h1-trivial">Trivial Cases</h1>
    <p>Coinbase-addr clusters that ...</p>
    <ul>
        <li>Only have one validator: {len(trivial_cases[trivial_cases['num_proposers'] == 1])}</li>
        <li>Only have one extra-data value: {len(trivial_cases[trivial_cases['num_extra_data'] == 1])}</li>
        <li>Have a 1:1 mapping between validator/extra-data: {len(trivial_cases[trivial_cases['num_proposers'] == trivial_cases['num_extra_data']])}</li>
    </ul>
"""

# Non-Trivial Cases
htmlOut += f"""
    <h1 id="h1-non-trivial">Non-Trivial Cases</h1>
    <p>There are {len(non_trivial_cases)} coinbase-addr clusters that show a non-trivial proposer/extra-data behavior.</p>
"""


# table of all non-trivial cases
htmlOut += "<details><summary>Table of non-trivial cases</summary>"
non_trivial_cases['Graph'] = [f"<a href='proposer_extra_data/coinbase-{i}.pdf'>Link</a>" for i in non_trivial_cases.index]
htmlOut += non_trivial_cases.to_html(escape=False)
htmlOut += "</details>"

# sub-categories
with open("out/proposer_extra_data_organize-categories.json") as file:
    organize_categories = json.load(file)

def valid_positions(pos_list, df_len):
    return [p for p in pos_list if isinstance(p, int) and 0 <= p < df_len]

global_positions = valid_positions(organize_categories.get('global', []), len(non_trivial_cases))
other_positions = valid_positions(organize_categories.get('other', []), len(non_trivial_cases))
pre_usage_positions = valid_positions(organize_categories.get('pre-usage', []), len(non_trivial_cases))

example_global_idx = global_positions[0] if len(global_positions) > 0 else None
example_other_idx = other_positions[1] if len(other_positions) > 1 else (other_positions[0] if len(other_positions) > 0 else None)
example_global_html = f"<img src=\"proposer_extra_data/coinbase-{example_global_idx}.pdf\"/>" if example_global_idx is not None else "n/a"
example_other_html = f"<img src=\"proposer_extra_data/coinbase-{example_other_idx}.pdf\"/>" if example_other_idx is not None else "n/a"

htmlOut += f"""
    <h2>Global Patterns</h2>
    <p>Of these {len(non_trivial_cases)} coinbase-addr clusters, we found that {len(global_positions)} show a "global" behavior, while {len(other_positions)} did not.</p>
    <p>A "global" behavior means that there is a clear temporal distribution of extra_data values within that coinbase-addr cluster.</p>
    <table>
        <tr>
            <td>Example global behavior</td>
            <td>Example non-global behavior</td>
        </tr>
        <tr>
            <td>{example_global_html}</td>
            <td>{example_other_html}</td>
        </tr>
    </table>
    """

global_coinbase = non_trivial_cases.iloc[global_positions]
other_coinbase = non_trivial_cases.iloc[other_positions]
other_without_lido = other_coinbase[1:]

htmlOut += f"""
    <table border=1>
        <tr>
            <td>Global behavior</td>
            <td>{len(global_positions)} ({(len(global_positions)/len(non_trivial_cases) * 100) if len(non_trivial_cases) > 0 else 0}%) <br> coinbase-addr clusters</td>
            <td>{global_coinbase['num_blocks'].sum()} blocks</td>
            <td>{global_coinbase['num_proposers'].sum()} validators</td>
        </tr>
        <tr>
            <td>No global behavior</td>
            <td>{len(other_positions)} ({(len(other_positions)/len(non_trivial_cases) * 100) if len(non_trivial_cases) > 0 else 0}%) <br> coinbase-addr clusters</td>
            <td>{other_coinbase['num_blocks'].sum()} blocks</td>
            <td>{other_coinbase['num_proposers'].sum()} validators</td>
        </tr>
        <tr>
            <td>No global behavior (excluding Lido)</td>
            <td>{max(len(other_positions)-1, 0)} ({(max(len(other_positions)-1, 0)/len(non_trivial_cases) * 100) if len(non_trivial_cases) > 0 else 0}%) <br> coinbase-addr clusters</td>
            <td>{other_without_lido['num_blocks'].sum()} blocks</td>
            <td>{other_without_lido['num_proposers'].sum()} validators</td>
        </tr>
    </table>    
"""

# all_patterns + all_follow_ups
if len(organize_categories.get('global_patterns', [])) > 0:
    all_patterns = pd.concat([pd.DataFrame.from_dict(x) for x in organize_categories['global_patterns']])
    all_patterns["pattern_index"] = (all_patterns.index == 0).cumsum()
    all_patterns = all_patterns.reset_index(drop=True)
else:
    all_patterns = pd.DataFrame(columns=['start_block', 'end_block', 'extra_data', 'pattern_index'])

# table of all global behaviors
htmlOut += "<details><summary>Table of global behavior</summary>"

def parse_extra_data(x):
    if not isinstance(x, str) or not x.startswith('0x'):
        return None

    try:
        b = bytes.fromhex(x[2:])
    except ValueError:
        return None

    if (len(b) > 0):
        if b[0] == 0xd8 or b[0] == 0xda or b[0] == 0xd9:
            # this is a geth extra_data
            major = b[2]
            minor = b[3]
            patch = b[4]

            client_end = 6+b[5]-0x80
            client = b[6:client_end]
            goversion_end = client_end+1+b[client_end]-0x80
            goversion = b[client_end+1:goversion_end]

            os = b[goversion_end+1:]

            return (f"{major}.{minor}.{patch}", client, goversion, os)
    
    return None

# parsing geth version strings
def parse_extra_data_version(x):
    if not isinstance(x, str) or not x.startswith('0x'):
        return None

    try:
        b = bytes.fromhex(x[2:])
    except ValueError:
        return None

    if (len(b) > 0):
        if b[0] == 0xd8 or b[0] == 0xda or b[0] == 0xd9:
            major = b[2]
            minor = b[3]
            patch = b[4]
            return f"{major}.{minor}.{patch}"
    
    return None


def summarize_extra_data_use(idx):
    df = all_patterns[all_patterns['pattern_index'] == idx]
    out = ""
    for _, row in df.iterrows():
        if parse_extra_data(row['extra_data']) is not None:
            out += f"{row['extra_data']} {parse_extra_data(row['extra_data'])}<br>"
        else:
            out += f"{row['extra_data']}<br>"

    return out

df = global_coinbase.copy()
df['extra_data'] = [summarize_extra_data_use(idx) for idx in range(1,len(df)+1)]
htmlOut += df.to_html(escape=False)
htmlOut += "</details>"

# table of all other behaviors
htmlOut += "<details><summary>Table of no global behavior</summary>"
htmlOut += other_coinbase.to_html(escape=False)
htmlOut += "</details>"

extra_data_occurence_global = all_patterns.groupby(by='extra_data')['pattern_index'].count().sort_values(ascending=False).reset_index()
extra_data_occurence_global['extra_data_decoded'] = extra_data_occurence_global['extra_data'].apply(lambda x: bytes.fromhex(x[2:]))
extra_data_occurence_global = extra_data_occurence_global.rename(columns={"pattern_index": "cluster_count"})


extra_data_occurence_global['extra_data_parsed'] = extra_data_occurence_global['extra_data'].apply(lambda x: parse_extra_data(x))

extra_data_otherwise = pd.read_json('out/proposer_extra_data_organize-extra-data-otherwise.json')

htmlOut += f"""
    <h3>extra-data in global behaviors</h3>
    <p>In the {len(all_patterns['pattern_index'].unique())} coinbase addr clusters with global behavior, we see {len(all_patterns['extra_data'].unique())} different extra_data values.</p>
"""

# table of extra data values
htmlOut += "<details><summary>Table of extra data values</summary>"
htmlOut += extra_data_occurence_global.to_html(escape=False)
htmlOut += "</details>"


# follow ups
all_follow_ups = pd.read_json('out/proposer_extra_data_organize-follow-ups.json')
all_follow_ups = all_follow_ups.sort_values(by='count', ascending=False)
all_follow_ups = all_follow_ups.rename(columns={'count': 'cluster_count'})
all_follow_ups = all_follow_ups[all_follow_ups.columns.tolist()[-1:] + all_follow_ups.columns.tolist()[:-1]]

all_follow_ups['extra_data'] = all_follow_ups['extra_data'].apply(lambda x: f"{x}<br>{bytes.fromhex(x[2:])}<br>{parse_extra_data(x)}")
all_follow_ups['next_extra_data'] = all_follow_ups['next_extra_data'].apply(lambda x: f"{x}<br>{bytes.fromhex(x[2:])}<br>{parse_extra_data(x)}")

all_follow_ups['graph'] = [f"<a href='proposer_extra_data_organize/changes/change-{i}.pdf'>Link</a>" for i in all_follow_ups.index]

htmlOut += f"""
    <h3>pairs of extra-data values</h3>
    <p>Within our clusters with global behavior, we can observe some frequent changes between extra-data values across clusters.</p>
"""

htmlOut += "<details><summary>Table of extra data value changes</summary>"
htmlOut += all_follow_ups.to_html(escape=False)
htmlOut += "</details>"

# Clusters that use geth versions before release
htmlOut += "<h1>Pre-Release Geth</h1>"

htmlOut += f"""
    <p>There are {len(organize_categories['pre-usage'])} non-trivial clusters that use a geth version pre-release.</p>
"""

with open(f"analyse/proposer_extra_data_organize_geth_releases.json") as file:
    geth_releases = json.load(file)

def summarize_pre_usage(idx):
    with open(f"out/proposer_extra_data/coinbase-{idx}.json") as file:
        blocks = pd.DataFrame(json.load(file)['blocks'])
    
    out = ""
    
    eds = blocks['extra_data'].unique()
    for ed in eds:
        if parse_extra_data_version(ed) is not None:
            version = parse_extra_data_version(ed)
            publication_block = geth_releases.get(version)
            if publication_block is None:
                continue
            usage_block = blocks[blocks['extra_data'] == ed]['block_number'].min()
            if usage_block < publication_block:
                out += f"Geth {version} used {publication_block - usage_block} blocks ahead<br>"
    
    return out

pre_usage_clusters = non_trivial_cases.iloc[pre_usage_positions].copy()
print(pre_usage_clusters)
pre_usage_clusters['Graph'] = [f"<a href='proposer_extra_data/coinbase-{i}.pdf'>Link</a>" for i in pre_usage_clusters.index]
pre_usage_clusters["pre-usage"] = [summarize_pre_usage(idx) for idx in pre_usage_clusters.index]

htmlOut += "<details><summary>Table of clusters that pre-use geth versions</summary>"
htmlOut += pre_usage_clusters.to_html(escape=False)
htmlOut += "</details>"

htmlOut += "</body></html>"

with open("out/proposer_extra_data_overview.html", "w") as file:
    file.write(htmlOut)