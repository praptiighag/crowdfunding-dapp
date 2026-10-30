"""Compile contracts/Crowdfunding.sol and deploy it to Ganache.

Usage:  python deploy.py
Output: build/Crowdfunding.json  (abi, bytecode, address)
"""
import json
import os
import sys

from solcx import compile_standard, install_solc
from chain import Chain

GANACHE_URL = os.environ.get("GANACHE_URL", "http://127.0.0.1:7545")
SOLC_VERSION = "0.8.19"
ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(ROOT, "contracts", "Crowdfunding.sol")
BUILD = os.path.join(ROOT, "build", "Crowdfunding.json")


def compile_contract():
    """Return (abi, bytecode) for the Crowdfunding contract."""
    install_solc(SOLC_VERSION)  # no-op if already installed
    with open(SOURCE) as f:
        source = f.read()
    out = compile_standard(
        {
            "language": "Solidity",
            "sources": {"Crowdfunding.sol": {"content": source}},
            "settings": {
                "evmVersion": "paris",  # safe for Ganache's EVM
                "optimizer": {"enabled": True, "runs": 200},
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
            },
        },
        solc_version=SOLC_VERSION,
    )
    c = out["contracts"]["Crowdfunding.sol"]["Crowdfunding"]
    return c["abi"], c["evm"]["bytecode"]["object"]


def main():
    chain = Chain(GANACHE_URL)
    if not chain.connected():
        sys.exit(f"Cannot reach Ganache at {GANACHE_URL}. Start Ganache first.")

    print("Compiling...")
    abi, bytecode = compile_contract()
    print("Deploying...")
    address = chain.deploy(bytecode, chain.accounts()[0])  # from account 0

    os.makedirs(os.path.dirname(BUILD), exist_ok=True)
    with open(BUILD, "w") as f:
        json.dump({"address": address, "abi": abi, "bytecode": bytecode}, f, indent=2)
    print(f"Deployed at {address}\nSaved to build/Crowdfunding.json")


if __name__ == "__main__":
    main()
