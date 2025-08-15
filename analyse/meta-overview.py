# depends_on: coinbase_clusters.py,non_mev_coinbase_clusters_eoa_ca.py,proposer_collaboration.py,interacting_with_builders.py,including_xof.py
import pandas as pd
from itertools import chain
import json

# generate an html doc from the proposer_extra_data

htmlOut = "<!DOCTYPE html><html><head><title>RFC/Paper Meta-Overview</title></head><body>\n"

# Secion overview
htmlOut += "<h1>Sections</h1>\n"

htmlOut += f"""
    <ol>
        <li><a href='#h1-relaying-proposers'>Relaying Proposers</a></li>
        <li><a href='#h1-clustering'>Clustering</a></li>
        <li><a href='#h1-outsourcing'>Outsourcing Proposers</a></li>
        <li><a href='#h1-potentially-altruistic'>Potentially Altruistic Proposers</a></li>
    </ol>  
"""

# Section: Relaying Proposers
htmlOut += "<h1 id='h1-relaying-proposers'>Relaying Proposers</h1>"

with open("out/proposer_collaboration-overview.json") as file:
    json_obj = json.load(file)
    all_proposers = pd.DataFrame.from_dict(json_obj['all_proposers'])
    non_relaying_proposers = pd.DataFrame.from_dict(json_obj['non_relaying_proposers'])
    always_relaying_proposers = pd.DataFrame.from_dict(json_obj['always_relaying_proposers'])
    sometimes_relaying_proposers = pd.DataFrame.from_dict(json_obj['sometimes_relaying_proposers'])

total_num_proposers = all_proposers['proposer_index'].count()

htmlOut += f"""
    <table border=1>
        <tr>
            <th></th>
            <th># proposers</th>
            <th>%</th>
        <tr>
        <tr>
            <td>All Proposers</td>
            <td>{all_proposers['proposer_index'].count()}</td>
            <td>100 %</td>
        </tr>
        <tr>
            <td>└ Always Relaying Proposers</td>
            <td>{always_relaying_proposers['proposer_index'].count()}</td>
            <td>{always_relaying_proposers['proposer_index'].count() / all_proposers['proposer_index'].count() * 100} %</td>
        </tr>
        <tr>
            <td>└ Sometimes Relaying Proposers</td>
            <td>{sometimes_relaying_proposers['proposer_index'].count()}</td>
            <td>{sometimes_relaying_proposers['proposer_index'].count() / all_proposers['proposer_index'].count() * 100} %</td>
        </tr>
        <tr>
            <td>└ Never Relaying Proposers</td>
            <td>{non_relaying_proposers['proposer_index'].count()}</td>
            <td>{non_relaying_proposers['proposer_index'].count() / all_proposers['proposer_index'].count() * 100} %</td>
        </tr>
    </table>    
"""

htmlOut += f"""
    <details>
        <summary>Data</summary>
        <pre>
with open("out/proposer_collaboration-overview.json") as file:
    json_obj = json.load(file)
    all_proposers = pd.DataFrame.from_dict(json_obj['all_proposers'])
    non_relaying_proposers = pd.DataFrame.from_dict(json_obj['non_relaying_proposers'])
    always_relaying_proposers = pd.DataFrame.from_dict(json_obj['always_relaying_proposers'])
    sometimes_relaying_proposers = pd.DataFrame.from_dict(json_obj['sometimes_relaying_proposers'])
        </pre>
    </details>
"""


# Section: Clustering
htmlOut += "<h1 id='h1-clustering'>Clustering</h1>"

htmlOut += "<p>We clustered proposers based if they were using the same coinbase address. Currently limited to non-relaying proposers.</p>"
htmlOut += "<p>At this point, we loose some non-relaying proposers if their coinbase address has also been used by relaying proposers.</p>"

# load all non-relaying clusters
with open("out/coinbase_clusters-non-relaying-clusters.json") as file:
    non_relaying_clusters = json.load(file)

# load the associated proposer-coinbases
non_relaying_clusters_proposer_coinbase = pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')

assert non_relaying_clusters_proposer_coinbase['coinbase_addr'].isin(chain(*non_relaying_clusters)).all() # additional check

# load eoa/ca clusters
with open("out/non_mev_coinbase_clusters_eoa_ca.json") as file:
    json_obj = json.load(file)
    eoa_clusters = json_obj['eoa_clusters']
    ca_clusters = json_obj['ca_clusters']
    eoa_proposers = pd.DataFrame.from_dict(json_obj['eoa_proposers'])
    ca_proposers = pd.DataFrame.from_dict(json_obj['ca_proposers'])
    ca_contract_types = pd.DataFrame.from_dict(json_obj['ca_contract_types'])

htmlOut += f"""
    <table border=1>
        <tr>
            <th></th>
            <th># proposers</th>
            <th># clusters</th>
            <th>%</th>
        <tr>
        <tr>
            <td>Proposers in Clusters never relaying</td>
            <td>{len(non_relaying_clusters_proposer_coinbase['proposer_index'].unique())}</td>
            <td>{len(non_relaying_clusters)}</td>
            <td>{len(non_relaying_clusters_proposer_coinbase['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
        <tr>
            <td>└ EOA-Clusters</td>
            <td>{len(eoa_proposers['proposer_index'].unique())}</td>
            <td>{len(eoa_clusters)}</td>
            <td>{len(eoa_proposers['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
        <tr>
            <td>└ CA-Clusters</td>
            <td>{len(ca_proposers['proposer_index'].unique())}</td>
            <td>{len(ca_clusters)}</td>
            <td>{len(ca_proposers['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
    </table>    
"""

non_relaying_cluster_summary = []
non_relaying_eoa_cluster_summary = []
non_relaying_ca_cluster_summary = []
for cluster in non_relaying_clusters:
    obj = {
        "coinbase_addr": cluster,
        "num_proposer": len(non_relaying_clusters_proposer_coinbase[non_relaying_clusters_proposer_coinbase['coinbase_addr'].isin(cluster)]['proposer_index'].unique()),
        "num_blocks": non_relaying_clusters_proposer_coinbase[non_relaying_clusters_proposer_coinbase['coinbase_addr'].isin(cluster)]['count'].sum(),
    }
    non_relaying_cluster_summary.append(obj)
    if cluster in eoa_clusters:
        non_relaying_eoa_cluster_summary.append(obj)
    if cluster in ca_clusters: 
        non_relaying_ca_cluster_summary.append(obj)
    
non_relaying_cluster_summary = pd.DataFrame(non_relaying_cluster_summary).sort_values('num_blocks', ascending=False).reset_index(drop=True)
non_relaying_eoa_cluster_summary = pd.DataFrame(non_relaying_eoa_cluster_summary).sort_values('num_blocks', ascending=False).reset_index(drop=True)
non_relaying_ca_cluster_summary = pd.DataFrame(non_relaying_ca_cluster_summary).sort_values('num_blocks', ascending=False).reset_index(drop=True)

assert len(non_relaying_ca_cluster_summary) + len(non_relaying_eoa_cluster_summary) == len(non_relaying_cluster_summary)
print(non_relaying_eoa_cluster_summary['num_proposer'].sum(), len(eoa_proposers['proposer_index'].unique()))
print(non_relaying_ca_cluster_summary['num_proposer'].sum(), len(ca_proposers['proposer_index'].unique()))

assert non_relaying_eoa_cluster_summary['num_proposer'].sum() == len(eoa_proposers['proposer_index'].unique())
assert non_relaying_ca_cluster_summary['num_proposer'].sum() == len(ca_proposers['proposer_index'].unique())


htmlOut += f"""
    <details>
        <summary>Data</summary>
        <pre>
# load all non-relaying clusters
with open("out/coinbase_clusters-non-relaying-clusters.json") as file:
    non_relaying_clusters = json.load(file)

# load the associated proposer-coinbases
non_relaying_clusters_proposer_coinbase = pd.read_json('out/coinbase_clusters-non-relaying-proposer-coinbase.json')

# load eoa/ca clusters
with open("out/non_mev_coinbase_clusters_eoa_ca.json") as file:
    json_obj = json.load(file)
    eoa_clusters = json_obj['eoa_clusters']
    ca_clusters = json_obj['ca_clusters']
    eoa_proposers = pd.DataFrame.from_dict(json_obj['eoa_proposers'])
    ca_proposers = pd.DataFrame.from_dict(json_obj['ca_proposers'])
        </pre>

    <details><summary>All Clusters</summary>{non_relaying_cluster_summary.to_html()}</details>
    <details><summary>EOA Clusters</summary>{non_relaying_eoa_cluster_summary.to_html()}</details>
    <details><summary>CA Clusters</summary>{non_relaying_ca_cluster_summary.to_html()}</details>
    </details>
"""

htmlOut += "<h2>CA Contract Types</h2>"
htmlOut += "<p>Patrick analysed the contracts</p>"

htmlOut += ca_contract_types.to_html()

# Section: Outsourcing
htmlOut += "<h1 id='h1-outsourcing'>Outsourcing Proposers</h1>"
htmlOut += "<p>We are interested in two cases for EOA clusters:</p>"

htmlOut += """
    <ol>
        <li>Does a proposer in a cluster include a private transaction to/from builders?</li>
        <li>A cluster only contains proposers that share this coinbase address. However, there could other proposers that also <i>belong</i> to this coinbase address (e.g., same governance), but always used relays. Relays annouce the <code>proposer_fee_recipient</code>, which is the address where builders send the bid to. Does a cluster appear as <code>proposer_fee_recipient</code>?</li>
    </ol>
"""

with open("out/interacting_with_builder.json") as file:
    json_obj = json.load(file)
    eoa_clusters_with_private_builder_tx = json_obj['eoa_clusters_with_private_builder_tx']
    eoa_clusters_appearing_as_fee_recipient = json_obj['eoa_clusters_appearing_as_fee_recipient']
    eoa_clusters_appearing_as_fee_recipient_block_numbers = json_obj['eoa_clusters_appearing_as_fee_recipient_block_numbers']
    non_interacting_eoa_clusters = json_obj['non_interacting_eoa_clusters']

htmlOut += f"""
    <table border=1>
        <tr>
            <th></th>
            <th># proposers</th>
            <th># clusters</th>
            <th>%</th>
        <tr>
        <tr>
            <td>EOA-Clusters</td>
            <td>{len(eoa_proposers['proposer_index'].unique())}</td>
            <td>{len(eoa_clusters)}</td>
            <td>{len(eoa_proposers['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
        <tr>
            <td>└ Clusters including private TXs with builders</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*eoa_clusters_with_private_builder_tx))]['proposer_index'].unique())}</td>
            <td>{len(eoa_clusters_with_private_builder_tx)}</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*eoa_clusters_with_private_builder_tx))]['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
        <tr>
            <td>└ Clusters appearing as <code>proposer_fee_recipient</code></td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*eoa_clusters_appearing_as_fee_recipient))]['proposer_index'].unique())}</td>
            <td>{len(eoa_clusters_appearing_as_fee_recipient)}</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*eoa_clusters_appearing_as_fee_recipient))]['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
        <tr>
            <td>EOA-Clusters not interacting with Builders</code></td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*non_interacting_eoa_clusters))]['proposer_index'].unique())}</td>
            <td>{len(non_interacting_eoa_clusters)}</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*non_interacting_eoa_clusters))]['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
    </table>    
"""

htmlOut += f"""
    <details>
        <summary>Data</summary>
        <pre>
with open("out/interacting_with_builder.json") as file:
    json_obj = json.load(file)
    eoa_clusters_with_private_builder_tx = json_obj['eoa_clusters_with_private_builder_tx']
    eoa_clusters_appearing_as_fee_recipient = json_obj['eoa_clusters_appearing_as_fee_recipient']
    eoa_clusters_appearing_as_fee_recipient_block_numbers = json_obj['eoa_clusters_appearing_as_fee_recipient_block_numbers']
    non_interacting_eoa_clusters = json_obj['non_interacting_eoa_clusters']
        </pre>

    <details><summary>Clusters including private TXs with proposers</summary><ul>{'\n'.join([f"<li><pre>{c}</pre></li>" for c in eoa_clusters_with_private_builder_tx])}</ol></details>
    <details><summary>Clusters appearing as <code>proposer_fee_recipient</code></summary><ul>{'\n'.join([f"<li><pre>{c}</pre></li>" for c in eoa_clusters_appearing_as_fee_recipient])}</ol></details>
    </details>
"""

# Section: Potentially Altruistic Proposers
htmlOut += "<h1 id='h1-potentially-altruistic'>Potentially Altruistic Proposers</h1>"
htmlOut += "<h2>XOF Inclusion</h2>"

with open("out/including_xof.json") as file:
    json_obj = json.load(file)
    including_xof_clusters = json_obj['including_xof_clusters']
    not_including_xof_clusters = json_obj['not_including_xof_clusters']
    xof_coinbases = pd.DataFrame.from_dict(json_obj['xof_coinbases'])
    xof_transaction_addresses = pd.DataFrame.from_dict(json_obj['xof_transaction_addresses'])
    xof_only_self_transactions_clusters = json_obj['xof_only_self_transactions_clusters']


htmlOut += f"""
    <table border=1>
        <tr>
            <th></th>
            <th># proposers</th>
            <th># clusters</th>
            <th>%</th>
        <tr>
        <tr>
            <td>EOA-Clusters not interacting with Builders</code></td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*non_interacting_eoa_clusters))]['proposer_index'].unique())}</td>
            <td>{len(non_interacting_eoa_clusters)}</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*non_interacting_eoa_clusters))]['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
        <tr>
            <td>└ Proposers including XOF</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*including_xof_clusters))]['proposer_index'].unique())}</td>
            <td>{len(including_xof_clusters)}</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*including_xof_clusters))]['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
        <tr>
            <td style='padding-left: 14pt'>└ Only private self-transactions</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*xof_only_self_transactions_clusters))]['proposer_index'].unique())}</td>
            <td>{len(xof_only_self_transactions_clusters)}</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*xof_only_self_transactions_clusters))]['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
        <tr>
            <td>└ Proposers not including XOF</code></td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*not_including_xof_clusters))]['proposer_index'].unique())}</td>
            <td>{len(not_including_xof_clusters)}</td>
            <td>{len(eoa_proposers[eoa_proposers['coinbase_addr'].isin(chain(*not_including_xof_clusters))]['proposer_index'].unique()) / total_num_proposers * 100} %</td>
        </tr>
    </table>    
"""

htmlOut += f"""
    <details>
        <summary>Data</summary>
        <pre>
with open("out/including_xof.json") as file:
    json_obj = json.load(file)
    including_xof_clusters = json_obj['including_xof_clusters']
    not_including_xof_clusters = json_obj['not_including_xof_clusters']
    xof_coinbases = pd.DataFrame.from_dict(json_obj['xof_coinbases'])
        </pre>

    <details><summary>Clusters including XOF</summary><ul>{'\n'.join([f"<li><pre>{c}</pre></li>" for c in including_xof_clusters])}</ol></details>
    <details><summary>Clusters not including XOF</summary><ul>{'\n'.join([f"<li><pre>{c}</pre></li>" for c in not_including_xof_clusters])}</ol></details>
    <details><summary>Coinbases (of proposers not interacting with builders) using XOF)</summary>{xof_coinbases.to_html()}</details>
    <details><summary>Transaction Addresses of XOF</summary>{xof_transaction_addresses.to_html()}</details>
    <details><summary>Clusters only including XOF with self-transactions</summary><ul>{'\n'.join([f"<li><pre>{c}</pre></li>" for c in xof_only_self_transactions_clusters])}</ol></details>
    </details>
"""

with open("out/meta-overview.html", "w") as file:
    file.write(htmlOut)