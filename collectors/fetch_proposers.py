"""
Purpose
    Recomputes proposer duties for a given epoch using the Ethereum spec
    shuffle and a public beacon API, serving as an independent cross-check.

Usage
    python3 collectors/fetch_proposers.py

Notes
    This script prints results to stdout. Adjust TARGET_EPOCH or API_BASE
    inside the file for other epochs or endpoints.
"""

import requests
from eth2spec.phase0 import spec
from eth2spec.utils.hash_function import hash
import hashlib

API_BASE = "http://unstable.mainnet.beacon-api.nimbus.team"
TARGET_EPOCH = 371448
SLOTS_PER_EPOCH = spec.SLOTS_PER_EPOCH
DOMAIN_BEACON_PROPOSER = spec.DOMAIN_BEACON_PROPOSER

def int_to_bytes(n, length):
    return n.to_bytes(length, 'little')

def get_randao_mix(slot):
    url = f"{API_BASE}/eth/v1/beacon/states/{slot}/randao"
    res = requests.get(url)
    res.raise_for_status()
    return bytes.fromhex(res.json()["data"]["randao"][2:])

def get_validators(slot):
    url = f"{API_BASE}/eth/v1/beacon/states/{slot}/validators"
    res = requests.get(url)
    res.raise_for_status()
    return res.json()["data"]

def get_active_validator_indices(validators, epoch):
    return [
        int(v["index"])
        for v in validators
        if int(v["validator"]["activation_epoch"]) <= epoch < int(v["validator"]["exit_epoch"])
    ]

def hash32(x: bytes) -> bytes:
    return hashlib.sha256(x).digest()

def get_seed(randao_mix: bytes, epoch: int) -> bytes:
    return hash32(DOMAIN_BEACON_PROPOSER + int_to_bytes(epoch, 8) + randao_mix)

def compute_proposer_index(active_indices, seed, slot):
    i = 0
    while True:
        shuffled_index = spec.compute_shuffled_index(i, len(active_indices), seed + int_to_bytes(slot, 8))
        return active_indices[shuffled_index]

def main():
    start_slot = TARGET_EPOCH * SLOTS_PER_EPOCH

    print(f"Fetching RANDAO for slot {start_slot}...")
    randao_mix = get_randao_mix(start_slot)
    print("Fetching validators...")
    validators = get_validators(start_slot)
    active_indices = get_active_validator_indices(validators, TARGET_EPOCH)
    seed = get_seed(randao_mix, TARGET_EPOCH)

    print(f"\nProposer duties for epoch {TARGET_EPOCH} (slots {start_slot} to {start_slot + 31}):")
    for i in range(SLOTS_PER_EPOCH):
        slot = start_slot + i
        proposer_index = compute_proposer_index(active_indices, seed, slot)
        print(f"  Slot {slot}: Validator {proposer_index}")

if __name__ == "__main__":
    main()
