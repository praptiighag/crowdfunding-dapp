"""Tests. The first four run offline; the rest need Ganache running:  pytest -v"""
import os

import pytest

from chain import Chain, ChainError, Contract, checksum, decode, encode, keccak256
from deploy import GANACHE_URL, compile_contract

ETH = 10 ** 18


# ---------- offline: the hand-written client pieces ----------
def test_keccak_known_vectors():
    assert keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert keccak256(b"transfer(address,uint256)")[:4].hex() == "a9059cbb"


def test_checksum_address():
    assert checksum("0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed") == "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"


def test_abi_roundtrip():
    types = ["string", "string", "uint256", "uint256", "bool", "address"]
    values = ["Title", "A longer description", 5 * ETH, 60, True, "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"]
    assert decode(types, encode(types, values)) == values


def test_decode_calldata():
    abi = [{"type": "function", "name": "pledge", "inputs": [{"name": "_id", "type": "uint256"}], "outputs": []}]
    c = Contract(None, "0x" + "00" * 20, abi)
    assert c.decode_input(c._calldata("pledge", (7,))) == ("pledge", [("_id", "uint256", 7)])


# ---------- on-chain: contract behaviour ----------
@pytest.fixture(scope="session")
def node():
    node = Chain(os.environ.get("GANACHE_URL", GANACHE_URL))
    if not node.connected():
        pytest.skip("Ganache is not running")
    return node


@pytest.fixture(scope="session")
def compiled():
    return compile_contract()


@pytest.fixture()
def cf(node, compiled):
    """A freshly deployed contract for every test."""
    abi, bytecode = compiled
    return Contract(node, node.deploy(bytecode, node.accounts()[0]), abi)


def skip_time(node, seconds):
    node.increase_time(seconds)
    node.mine()


def run(cf, name, *args, sender, value=0):
    return cf.transact(name, *args, sender=sender, value=value)


def new_campaign(cf, creator, goal=5 * ETH, duration=60):
    run(cf, "createCampaign", "Test", "desc", goal, duration, sender=creator)
    return cf.call("campaignCount")


def test_create_campaign_stores_fields(node, cf):
    creator = node.accounts()[0]
    cid = new_campaign(cf, creator)
    c = cf.call("campaigns", cid)
    assert c[0] == creator and c[1] == "Test" and c[3] == 5 * ETH and c[5] == 0 and c[6] is False


def test_create_rejects_zero_goal_and_duration(node, cf):
    a = node.accounts()
    with pytest.raises(ChainError):
        run(cf, "createCampaign", "T", "d", 0, 60, sender=a[0])
    with pytest.raises(ChainError):
        run(cf, "createCampaign", "T", "d", ETH, 0, sender=a[0])


def test_pledge_updates_totals(node, cf):
    a = node.accounts()
    cid = new_campaign(cf, a[0])
    run(cf, "pledge", cid, sender=a[1], value=3 * ETH)
    run(cf, "pledge", cid, sender=a[2], value=3 * ETH)
    assert cf.call("campaigns", cid)[5] == 6 * ETH  # overfunding is allowed
    assert cf.call("pledges", cid, a[1]) == 3 * ETH


def test_pledge_rejects_zero_unknown_and_after_deadline(node, cf):
    a = node.accounts()
    cid = new_campaign(cf, a[0])
    with pytest.raises(ChainError):
        run(cf, "pledge", cid, sender=a[1], value=0)
    with pytest.raises(ChainError):
        run(cf, "pledge", 99, sender=a[1], value=ETH)
    skip_time(node, 120)
    with pytest.raises(ChainError):
        run(cf, "pledge", cid, sender=a[1], value=ETH)


def test_creator_withdraws_after_success(node, cf):
    a = node.accounts()
    cid = new_campaign(cf, a[0])
    run(cf, "pledge", cid, sender=a[1], value=6 * ETH)
    skip_time(node, 120)
    before = node.balance(a[0])
    run(cf, "withdrawFunds", cid, sender=a[0])
    assert node.balance(a[0]) > before + 5 * ETH  # minus a little gas
    assert node.balance(cf.address) == 0
    assert cf.call("campaigns", cid)[6] is True


def test_withdraw_blocked_cases(node, cf):
    a = node.accounts()
    cid = new_campaign(cf, a[0])
    run(cf, "pledge", cid, sender=a[1], value=6 * ETH)
    with pytest.raises(ChainError):  # still running
        run(cf, "withdrawFunds", cid, sender=a[0])
    skip_time(node, 120)
    with pytest.raises(ChainError):  # not the creator
        run(cf, "withdrawFunds", cid, sender=a[1])
    run(cf, "withdrawFunds", cid, sender=a[0])
    with pytest.raises(ChainError):  # double withdraw
        run(cf, "withdrawFunds", cid, sender=a[0])


def test_withdraw_blocked_when_goal_missed(node, cf):
    a = node.accounts()
    cid = new_campaign(cf, a[0], goal=10 * ETH)
    run(cf, "pledge", cid, sender=a[1], value=2 * ETH)
    skip_time(node, 120)
    with pytest.raises(ChainError):
        run(cf, "withdrawFunds", cid, sender=a[0])


def test_refund_after_failure_and_only_once(node, cf):
    a = node.accounts()
    cid = new_campaign(cf, a[0], goal=10 * ETH)
    run(cf, "pledge", cid, sender=a[1], value=2 * ETH)
    with pytest.raises(ChainError):  # still running
        run(cf, "claimRefund", cid, sender=a[1])
    skip_time(node, 120)
    before = node.balance(a[1])
    run(cf, "claimRefund", cid, sender=a[1])
    assert node.balance(a[1]) > before + 19 * ETH // 10  # about 2 ETH minus gas
    with pytest.raises(ChainError):  # second refund
        run(cf, "claimRefund", cid, sender=a[1])
    with pytest.raises(ChainError):  # never pledged
        run(cf, "claimRefund", cid, sender=a[3])


def test_no_refund_when_goal_met(node, cf):
    a = node.accounts()
    cid = new_campaign(cf, a[0])
    run(cf, "pledge", cid, sender=a[1], value=6 * ETH)
    skip_time(node, 120)
    with pytest.raises(ChainError):
        run(cf, "claimRefund", cid, sender=a[1])
