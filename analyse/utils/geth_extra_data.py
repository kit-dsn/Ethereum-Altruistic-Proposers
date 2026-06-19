"""Heuristic decoder for geth's default block-header `extra_data` tag.

Shared by proposer_extra_data.py, proposer_extra_data_organize.py and
proposer_extra_data_overview.py, which all need to recognize a geth version
string embedded in a block's extra_data field. See those files for why this
matters (it's used to spot client upgrades and pre-release usage within a
coinbase-address cluster's timeline).
"""


def parse_version(extra_data):
    """Decode the (major, minor, patch) version triple from a default-geth
    extra_data tag, or None if `extra_data` doesn't look like one.

    Only recognizes the specific layout below; a different client, a
    customized extra_data, or a string too short to hold byte offsets 2-4
    after a recognized leading byte will raise IndexError rather than
    returning None - this mirrors the original, unguarded implementation.
    """
    if not isinstance(extra_data, str) or not extra_data.startswith('0x'):
        return None

    try:
        b = bytes.fromhex(extra_data[2:])
    except ValueError:
        return None

    if len(b) > 0:
        if b[0] == 0xd8 or b[0] == 0xda or b[0] == 0xd9:
            major = b[2]
            minor = b[3]
            patch = b[4]
            return f"{major}.{minor}.{patch}"

    return None


def parse_full(extra_data):
    """Decode (version, client, go_version, os) from a default-geth
    extra_data tag, or None. See parse_version for the version-only subset
    and the same caveat about malformed input raising instead of None.

    Layout: [marker][?][major][minor][patch][client RLP-string][go-version
    RLP-string][unused length byte][os bytes to the end]. RLP short strings
    are length-prefixed with 0x80 + length, hence the "- 0x80" below.
    """
    if not isinstance(extra_data, str) or not extra_data.startswith('0x'):
        return None

    try:
        b = bytes.fromhex(extra_data[2:])
    except ValueError:
        return None

    if len(b) > 0:
        if b[0] == 0xd8 or b[0] == 0xda or b[0] == 0xd9:
            major = b[2]
            minor = b[3]
            patch = b[4]

            client_end = 6 + b[5] - 0x80
            client = b[6:client_end]
            goversion_end = client_end + 1 + b[client_end] - 0x80
            goversion = b[client_end+1:goversion_end]

            os_ = b[goversion_end+1:]

            return (f"{major}.{minor}.{patch}", client, goversion, os_)

    return None
