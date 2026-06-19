"""Shared graph-based address clustering.

coinbase_clusters.py and proposer_clusters.py both need the same idea: two
addresses belong to the same "cluster" if some proposer was ever paid out
to both of them. Implemented as union-find via a graph: addresses are
nodes, an edge between two addresses means some group (a proposer_index)
used both of them.
"""

import networkx as nx


def build_address_clusters(all_addresses, group_to_addresses):
    """Cluster addresses that share a group (e.g. a proposer_index).

    all_addresses
        Every address to consider, in the order they should be added as
        graph nodes. This order also determines the order clusters are
        returned in (nx.connected_components visits nodes in insertion
        order), which matters: some downstream scripts assume a specific
        cluster position (e.g. "the largest cluster comes first").
    group_to_addresses
        Mapping of group key to the addresses seen for that group; any two
        addresses appearing under the same key get linked.

    Returns a list of clusters, each a sorted list of addresses - sorted so
    that the address order within a cluster doesn't depend on Python's
    per-process hash seed for strings/sets, only the inputs.
    """
    graph = nx.Graph()
    for address in all_addresses:
        graph.add_node(address)

    for addresses in group_to_addresses.values():
        addresses = list(addresses)
        if len(addresses) > 1:
            for i in range(len(addresses)):
                for j in range(i + 1, len(addresses)):
                    graph.add_edge(addresses[i], addresses[j])

    return [sorted(cluster) for cluster in nx.connected_components(graph)]
