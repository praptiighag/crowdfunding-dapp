"""Minimal Ethereum JSON-RPC client for Ganache. Replaces web3.py.

Pure Python (only `requests`), so there is nothing to compile: no lru-dict, no ckzg.
It covers exactly what this project needs: calls, transactions from Ganache's
unlocked accounts, event logs, and Ganache's time helpers. It includes a small
ABI encoder/decoder (uint, address, bool, string) and a keccak-256 implementation
used for function selectors and event topics.
"""
import time

import requests


class ChainError(Exception):
    """RPC failure or reverted transaction (message holds the revert reason)."""


# ---------- keccak-256 (Ethereum's hash; not the same as NIST SHA3) ----------
_MASK = (1 << 64) - 1
_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]


def _rol(v, n):
    return ((v << n) | (v >> (64 - n))) & _MASK


def _keccak_f(A):
    for rc in _RC:
        C = [A[x][0] ^ A[x][1] ^ A[x][2] ^ A[x][3] ^ A[x][4] for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rol(C[(x + 1) % 5], 1) for x in range(5)]
        A = [[A[x][y] ^ D[x] for y in range(5)] for x in range(5)]
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rol(A[x][y], _ROT[x][y])
        A = [[B[x][y] ^ (~B[(x + 1) % 5][y] & B[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        A[0][0] ^= rc
    return A


def keccak256(data: bytes) -> bytes:
    rate = 136
    padded = bytearray(data) + b"\x01"
    padded += bytes(-len(padded) % rate)
    padded[-1] |= 0x80
    A = [[0] * 5 for _ in range(5)]
    for off in range(0, len(padded), rate):
        for i in range(rate // 8):
            A[i % 5][i // 5] ^= int.from_bytes(padded[off + 8 * i: off + 8 * i + 8], "little")
        A = _keccak_f(A)
    return b"".join(A[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


def checksum(addr: str) -> str:
    """EIP-55 mixed-case address."""
    a = addr.lower().removeprefix("0x")
    h = keccak256(a.encode()).hex()
    return "0x" + "".join(c.upper() if int(h[i], 16) >= 8 else c for i, c in enumerate(a))


# ---------- ABI encoding (uint*, address, bool, string) ----------
def _dynamic(t):
    return t in ("string", "bytes")


def _enc_static(t, v):
    if t.startswith("uint"):
        return int(v).to_bytes(32, "big")
    if t == "address":
        raw = bytes.fromhex(v.lower().removeprefix("0x"))
        if len(raw) != 20:
            raise ValueError(f"bad address: {v}")
        return bytes(12) + raw
    if t == "bool":
        return int(bool(v)).to_bytes(32, "big")
    raise ValueError(f"unsupported ABI type: {t}")


def encode(types, values):
    head, tail = [], []
    for t, v in zip(types, values):
        if _dynamic(t):
            raw = v.encode() if isinstance(v, str) else bytes(v)
            tail.append(len(raw).to_bytes(32, "big") + raw + bytes(-len(raw) % 32))
            head.append(None)  # offset filled in below
        else:
            head.append(_enc_static(t, v))
    offset, out_head, ti = 32 * len(types), [], 0
    for h in head:
        if h is None:
            out_head.append(offset.to_bytes(32, "big"))
            offset += len(tail[ti])
            ti += 1
        else:
            out_head.append(h)
    return b"".join(out_head) + b"".join(tail)


def _dec_static(t, word):
    if t.startswith("uint"):
        return int.from_bytes(word, "big")
    if t == "address":
        return checksum("0x" + word[12:].hex())
    if t == "bool":
        return int.from_bytes(word, "big") != 0
    raise ValueError(f"unsupported ABI type: {t}")


def decode(types, data):
    out = []
    for i, t in enumerate(types):
        word = data[32 * i: 32 * i + 32]
        if _dynamic(t):
            off = int.from_bytes(word, "big")
            n = int.from_bytes(data[off: off + 32], "big")
            raw = data[off + 32: off + 32 + n]
            out.append(raw.decode() if t == "string" else raw)
        else:
            out.append(_dec_static(t, word))
    return out


# ---------- JSON-RPC ----------
class Chain:
    def __init__(self, url):
        self.url = url
        self._id = 0

    def rpc(self, method, params=None):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or []}
        try:
            body = requests.post(self.url, json=payload, timeout=30).json()
        except (requests.RequestException, ValueError) as e:
            raise ChainError(f"Cannot reach the node at {self.url}: {e}")
        if "error" in body:
            raise ChainError(body["error"].get("message", "RPC error"))
        return body["result"]

    def connected(self):
        try:
            self.rpc("eth_chainId")
            return True
        except ChainError:
            return False

    def chain_id(self):
        return int(self.rpc("eth_chainId"), 16)

    def accounts(self):
        return [checksum(a) for a in self.rpc("eth_accounts")]

    def balance(self, addr):
        return int(self.rpc("eth_getBalance", [addr, "latest"]), 16)

    def code(self, addr):
        return self.rpc("eth_getCode", [addr, "latest"])

    def block(self, number="latest"):
        tag = number if number == "latest" else hex(number)
        b = self.rpc("eth_getBlockByNumber", [tag, False])
        return {"number": int(b["number"], 16), "timestamp": int(b["timestamp"], 16), "hash": b["hash"]}

    def tx(self, tx_hash):
        t = self.rpc("eth_getTransactionByHash", [tx_hash])
        if not t:
            return None
        return {"from": checksum(t["from"]), "to": checksum(t["to"]) if t.get("to") else None,
                "value": int(t["value"], 16), "gas": int(t["gas"], 16), "gas_price": int(t["gasPrice"], 16),
                "nonce": int(t["nonce"], 16), "input": t["input"],
                "block": int(t["blockNumber"], 16), "block_hash": t["blockHash"]}

    def receipt(self, tx_hash):
        r = self.rpc("eth_getTransactionReceipt", [tx_hash])
        if not r:
            return None
        return {"status": int(r["status"], 16) == 1, "gas_used": int(r["gasUsed"], 16),
                "contract_address": checksum(r["contractAddress"]) if r.get("contractAddress") else None}

    # Ganache helpers: block.timestamp only moves when a block is mined
    def mine(self):
        self.rpc("evm_mine")

    def increase_time(self, seconds):
        self.rpc("evm_increaseTime", [seconds])

    def wait_receipt(self, tx_hash, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            receipt = self.rpc("eth_getTransactionReceipt", [tx_hash])
            if receipt:
                return receipt
            time.sleep(0.2)
        raise ChainError("Timed out waiting for the transaction to be mined")

    def send(self, tx):
        """Estimate first, so a revert raises ChainError carrying the reason."""
        gas = int(self.rpc("eth_estimateGas", [tx]), 16)
        tx = {**tx, "gas": hex(min(int(gas * 1.3) + 1000, 6_000_000))}
        receipt = self.wait_receipt(self.rpc("eth_sendTransaction", [tx]))
        if int(receipt["status"], 16) != 1:
            raise ChainError("Transaction reverted")
        return receipt

    def deploy(self, bytecode, sender):
        data = bytecode if bytecode.startswith("0x") else "0x" + bytecode
        return self.send({"from": sender, "data": data})["contractAddress"]


class Contract:
    def __init__(self, chain, address, abi):
        self.chain, self.address = chain, address
        self.functions = {x["name"]: x for x in abi if x["type"] == "function"}
        self.events = {x["name"]: x for x in abi if x["type"] == "event"}
        self._by_selector = {keccak256(self._signature(f).encode())[:4].hex(): f for f in self.functions.values()}
        self._topic0 = {n: "0x" + keccak256(self._signature(e).encode()).hex() for n, e in self.events.items()}
        self._by_topic = {self._topic0[n]: e for n, e in self.events.items()}

    @staticmethod
    def _signature(item):
        return f'{item["name"]}({",".join(i["type"] for i in item["inputs"])})'

    def _calldata(self, name, args):
        fn = self.functions[name]
        if len(args) != len(fn["inputs"]):
            raise TypeError(f"{name} expects {len(fn['inputs'])} arguments")
        selector = keccak256(self._signature(fn).encode())[:4]
        return "0x" + (selector + encode([i["type"] for i in fn["inputs"]], args)).hex()

    def call(self, name, *args):
        """Read-only call. One return value is unwrapped, several come back as a tuple."""
        fn = self.functions[name]
        out = self.chain.rpc("eth_call", [{"to": self.address, "data": self._calldata(name, args)}, "latest"])
        values = decode([o["type"] for o in fn["outputs"]], bytes.fromhex(out[2:]))
        return values[0] if len(values) == 1 else tuple(values)

    def transact(self, name, *args, sender, value=0):
        return self.chain.send({"from": sender, "to": self.address,
                                "data": self._calldata(name, args), "value": hex(value)})

    def decode_input(self, data):
        """Calldata -> (function name, [(param, type, value), ...]) or None."""
        fn = self._by_selector.get(data[2:10])
        if fn is None:
            return None
        values = decode([i["type"] for i in fn["inputs"]], bytes.fromhex(data[10:]))
        return fn["name"], [(i["name"], i["type"], v) for i, v in zip(fn["inputs"], values)]

    def decode_log(self, log):
        ev = self._by_topic.get(log["topics"][0]) if log["topics"] else None
        if ev is None:
            return None
        indexed = [i for i in ev["inputs"] if i["indexed"]]
        plain = [i for i in ev["inputs"] if not i["indexed"]]
        args = {i["name"]: _dec_static(i["type"], bytes.fromhex(t[2:]))
                for i, t in zip(indexed, log["topics"][1:])}
        data = decode([i["type"] for i in plain], bytes.fromhex(log["data"][2:]))
        args.update({i["name"]: v for i, v in zip(plain, data)})
        return {"event": ev["name"], "args": args, "block": int(log["blockNumber"], 16),
                "block_hash": log["blockHash"], "index": int(log["logIndex"], 16), "tx": log["transactionHash"]}

    def logs(self, name=None):
        """Decoded logs of one event type, or of every event when name is None."""
        flt = {"address": self.address, "fromBlock": "0x0", "toBlock": "latest"}
        if name:
            flt["topics"] = [self._topic0[name]]
        rows = (self.decode_log(log) for log in self.chain.rpc("eth_getLogs", [flt]))
        return [r for r in rows if r]
