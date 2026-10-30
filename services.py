"""Domain layer for Vouch: node connection, contract reads, derived views, off-chain
metadata and demo data. Routes and HTML live in app.py; nothing here renders anything.
Per-request caches use flask.g, so every page reads a consistent snapshot of the chain."""
import json
import os
import re
import threading
from decimal import Decimal, InvalidOperation

from flask import g

from chain import Chain, ChainError, Contract, checksum, keccak256

ROOT = os.path.dirname(os.path.abspath(__file__))
GANACHE_URL = os.environ.get("GANACHE_URL", "http://127.0.0.1:7545")
BUILD = os.path.join(ROOT, "build", "Crowdfunding.json")
META_PATH = os.path.join(ROOT, "data", "meta.json")

chain = Chain(GANACHE_URL)
if not chain.connected():
    raise SystemExit(f"Cannot reach Ganache at {GANACHE_URL}. Start Ganache first.")
if not os.path.exists(BUILD):
    raise SystemExit("build/Crowdfunding.json not found. Run: python deploy.py")
with open(BUILD) as f:
    _build = json.load(f)
if chain.code(_build["address"]) in ("0x", "0x0"):
    raise SystemExit("Contract not found on this chain (Ganache was reset?). Run: python deploy.py")
contract = Contract(chain, checksum(_build["address"]), _build["abi"])

NAMES = ["Alice", "Bob", "Carol", "Dan", "Erin", "Frank", "Grace", "Heidi", "Ivan", "Judy"]
CATEGORIES = {
    "Community": dict(icon="people-fill", colors=("#ff6b2c", "#ffb347")),
    "Education": dict(icon="mortarboard-fill", colors=("#5b3df5", "#a78bfa")),
    "Health": dict(icon="heart-pulse-fill", colors=("#e5446d", "#ff9fb2")),
    "Creative": dict(icon="palette-fill", colors=("#b02edc", "#ff7ae0")),
    "Technology": dict(icon="cpu-fill", colors=("#0b7285", "#5ee0f0")),
    "Environment": dict(icon="tree-fill", colors=("#12805c", "#7be0b0")),
    "Emergency": dict(icon="exclamation-triangle-fill", colors=("#c2410c", "#ffa564")),
}
DURATIONS = [(1, "1 minute (demo)"), (5, "5 minutes (demo)"), (60, "1 hour"), (1440, "1 day"),
             (10080, "7 days"), (43200, "30 days")]
STATUS_LABELS = {"active": "Active", "funded": "Goal reached", "failed": "Refunds open", "withdrawn": "Funds released"}
FN_KIND = {"createCampaign": "create", "pledge": "pledge", "withdrawFunds": "claim", "claimRefund": "refund"}
EVENT_KIND = {"CampaignCreated": "create", "Pledged": "pledge", "FundsClaimed": "claim", "Refunded": "refund"}
KIND_NAMES = {"create": "Campaign launched", "pledge": "Pledge", "claim": "Funds released", "refund": "Refund",
              "deploy": "Contract deployed", "other": "Transaction"}
HASH_RE = re.compile(r"0x[0-9a-fA-F]{64}")
ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}")


# ---------- node helpers ----------
def chain_now():
    """Ganache only moves block.timestamp when a block is mined, so mine one
    (once per request) to get an up-to-date chain clock."""
    if "now" not in g:
        chain.mine()
        g.now = chain.block()["timestamp"]
    return g.now


def accounts():
    if "accounts" not in g:
        g.accounts = chain.accounts()
    return g.accounts


def persona(addr):
    """Friendly name for a Ganache account, short address otherwise."""
    if addr == contract.address:
        return "Vouch contract"
    if addr in accounts():
        i = accounts().index(addr)
        return NAMES[i] if i < len(NAMES) else f"Account {i}"
    return f"{addr[:6]}…{addr[-4:]}"


def revert_reason(exc):
    m = re.search(r"revert(?:ed)?:?\s*([^'\"}\n]*)", str(exc))
    return (m.group(1).strip() if m else str(exc)) or "Transaction reverted"


def eth_to_wei(text):
    try:
        value = Decimal(text)
        return int(value * 10 ** 18) if value > 0 else None
    except (InvalidOperation, TypeError, ValueError, OverflowError):
        return None


def block_time(n):
    cache = g.setdefault("block_times", {})
    if n not in cache:
        cache[n] = chain.block(n)["timestamp"]
    return cache[n]


# ---------- off-chain metadata (category, tagline, organizer updates) ----------
# The chain keeps the money rules. Presentation data lives here, keyed by the campaign's creation tx hash.
_meta_lock = threading.Lock()


def _all_meta():
    if "meta" not in g:
        try:
            with open(META_PATH) as f:
                g.meta = json.load(f)
        except (FileNotFoundError, ValueError):
            g.meta = {}
    return g.meta


def get_meta(tx):
    m = _all_meta().get(tx or "", {})
    return {"category": m.get("category", "Community"), "tagline": m.get("tagline", ""), "updates": m.get("updates", [])}


def _write_meta(tx, mutate):
    with _meta_lock:
        try:
            with open(META_PATH) as f:
                data = json.load(f)
        except (FileNotFoundError, ValueError):
            data = {}
        mutate(data.setdefault(tx, {}))
        os.makedirs(os.path.dirname(META_PATH), exist_ok=True)
        with open(META_PATH, "w") as f:
            json.dump(data, f, indent=2)


def set_meta(tx, **fields):
    _write_meta(tx, lambda m: m.update(fields))


def add_update(tx, text, ts):
    _write_meta(tx, lambda m: m.setdefault("updates", []).insert(0, {"text": text, "time": ts}))


# ---------- derived views of on-chain state ----------
def all_events():
    """Every contract event, oldest first, normalised for the templates."""
    if "events" not in g:
        raw = contract.logs()
        creators = {e["args"]["id"]: e["args"]["creator"] for e in raw if e["event"] == "CampaignCreated"}
        g.events = [
            dict(kind=EVENT_KIND[e["event"]], cid=e["args"]["id"],
                 who=e["args"].get("backer") or e["args"].get("creator") or creators.get(e["args"]["id"]),
                 amount=e["args"].get("amount", 0), goal=e["args"].get("goal"), deadline=e["args"].get("deadline"),
                 tx=e["tx"], block=e["block"], order=(e["block"], e["index"]), time=block_time(e["block"]))
            for e in sorted(raw, key=lambda e: (e["block"], e["index"]))
        ]
    return g.events


def _build_campaign(cid):
    creator, title, desc, goal, deadline, raised, claimed = contract.call("campaigns", cid)
    now = chain_now()
    status = "withdrawn" if claimed else "active" if now < deadline else "funded" if raised >= goal else "failed"
    evs = [e for e in all_events() if e["cid"] == cid]
    created = next((e for e in evs if e["kind"] == "create"), None)
    refunded = sum(e["amount"] for e in evs if e["kind"] == "refund")
    meta = get_meta(created["tx"] if created else None)
    return dict(
        id=cid, creator=creator, title=title, description=desc, goal=goal, deadline=deadline, raised=raised,
        claimed=claimed, status=status, percent=int(raised * 100 / goal), remaining=max(0, deadline - now),
        refunded=refunded, escrow=0 if claimed else raised - refunded,  # ETH the contract still holds for it
        backers=len({e["who"] for e in evs if e["kind"] == "pledge"}),
        category=meta["category"], updates=meta["updates"],
        tagline=meta["tagline"] or (desc[:110] + ("…" if len(desc) > 110 else "")),
        created=created, claim=next((e for e in evs if e["kind"] == "claim"), None),
    )


def all_campaigns():
    """Newest first."""
    if "campaigns" not in g:
        g.campaigns = [_build_campaign(i) for i in range(contract.call("campaignCount"), 0, -1)]
    return g.campaigns


def get_campaign(cid):
    return next((c for c in all_campaigns() if c["id"] == cid), None)


def get_backers(cid):
    pledged, refunds = {}, {}
    for e in all_events():
        if e["cid"] != cid:
            continue
        if e["kind"] == "pledge":
            pledged[e["who"]] = pledged.get(e["who"], 0) + e["amount"]
        elif e["kind"] == "refund":
            refunds[e["who"]] = e
    return [dict(addr=a, pledged=amt, refund=refunds.get(a)) for a, amt in sorted(pledged.items(), key=lambda kv: -kv[1])]


def my_pledges(addr):
    """Campaigns an address has backed, with what it is owed back (if anything)."""
    camps = {c["id"]: c for c in all_campaigns()}
    pledged, refunded = {}, set()
    for e in all_events():
        if e["who"] != addr:
            continue
        if e["kind"] == "pledge":
            pledged[e["cid"]] = pledged.get(e["cid"], 0) + e["amount"]
        elif e["kind"] == "refund":
            refunded.add(e["cid"])
    return [dict(c=camps[cid], amount=amt, refunded=cid in refunded,
                 can_refund=camps[cid]["status"] == "failed" and cid not in refunded)
            for cid, amt in sorted(pledged.items(), reverse=True)]


def action_counts(addr):
    return dict(withdraw=sum(c["creator"] == addr and c["status"] == "funded" for c in all_campaigns()),
                refund=sum(p["can_refund"] for p in my_pledges(addr)))


def platform_stats(camps):
    return dict(total=len(camps), active=sum(c["status"] == "active" for c in camps),
                raised=sum(c["raised"] for c in camps), released=sum(c["raised"] for c in camps if c["claimed"]),
                returned=sum(c["refunded"] for c in camps), backers=len({e["who"] for e in all_events() if e["kind"] == "pledge"}))


def steps(c):
    s = c["status"]
    done = {"active": 1, "funded": 3, "failed": 3, "withdrawn": 4}[s]
    last = {"active": "Settlement", "funded": "Release funds", "failed": "Refund backers", "withdrawn": "Funds released"}[s]
    if s == "failed" and c["raised"] == 0:
        done, last = 4, "Closed, no pledges"
    elif s == "failed" and c["escrow"] == 0:
        done, last = 4, "All refunded"
    labels = ["Launched", "Funding", "Deadline", last]
    return [dict(label=l, state="done" if i < done else "current" if i == done else "todo") for i, l in enumerate(labels)]


def funding_series(c):
    """Coordinates for the cumulative-pledges chart (a step line from launch to deadline)."""
    W, H, PL, PR, PT, PB = 640, 190, 8, 8, 14, 8
    start = c["created"]["time"] if c["created"] else c["deadline"] - 1
    end = max(c["deadline"], start + 1)
    top = (max(c["goal"], c["raised"]) * 1.1) or 1
    x = lambda t: PL + (min(max(t, start), end) - start) / (end - start) * (W - PL - PR)
    y = lambda v: H - PB - v / top * (H - PT - PB)
    pts, total = [(x(start), y(0))], 0
    for e in all_events():
        if e["cid"] == c["id"] and e["kind"] == "pledge":
            total += e["amount"]
            pts += [(x(e["time"]), pts[-1][1]), (x(e["time"]), y(total))]
    now_x = x(min(chain_now(), end))
    pts.append((now_x, pts[-1][1]))
    line = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
    return dict(w=W, h=H, line=line, area=f"{line} {pts[-1][0]:.1f},{y(0):.1f} {pts[0][0]:.1f},{y(0):.1f}",
                goal_y=round(y(c["goal"]), 1), now_x=round(now_x, 1), left=PL, right=W - PR, base=round(y(0), 1))


# ---------- transactions, receipts and certificates ----------
_tx_cache = {}  # transactions never change, so cache by hash


def tx_details(h):
    if h not in _tx_cache:
        t, r = chain.tx(h), chain.receipt(h)
        if not t or not r:
            return None
        parsed = contract.decode_input(t["input"]) if t["to"] == contract.address else None
        kind = "deploy" if t["to"] is None else FN_KIND.get(parsed[0], "other") if parsed else "other"
        block = chain.block(t["block"])
        _tx_cache[h] = dict(t, hash=h, status=r["status"], gas_used=r["gas_used"], fee=r["gas_used"] * t["gas_price"],
                            contract_address=r["contract_address"], kind=kind, fn=parsed[0] if parsed else None,
                            params=parsed[1] if parsed else [], time=block["timestamp"], block_hash=block["hash"])
    return _tx_cache[h]


def fingerprint(d):
    """Hash binding a transaction to its block and this contract. Anyone can recompute it from the chain."""
    raw = bytes.fromhex(d["hash"][2:]) + bytes.fromhex(d["block_hash"][2:]) + bytes.fromhex(contract.address[2:])
    return keccak256(raw).hex()


def tx_context(h):
    d = tx_details(h) if HASH_RE.fullmatch(h or "") else None
    evs = [e for e in all_events() if e["tx"] == h] if d else []
    return d, evs, (get_campaign(evs[0]["cid"]) if evs else None)


# ---------- demo mode ----------
def demo_steps(verified):
    evs, camps = all_events(), all_campaigns()
    rows = [
        ("Load the sample campaigns", "Use the button below, or launch your own campaign.", bool(camps)),
        ("Back a campaign as someone else", "Open a campaign, switch to Bob in the account menu and pledge.", any(e["kind"] == "pledge" for e in evs)),
        ("Reach a funding goal", "Keep pledging until the bar passes the goal marker.", any(c["raised"] >= c["goal"] for c in camps)),
        ("Let a deadline pass", "Use Skip time in the top bar.", any(c["status"] != "active" for c in camps)),
        ("Release funds as the organizer", "Switch to the organizer of a funded campaign and click Withdraw.", any(e["kind"] == "claim" for e in evs)),
        ("Refund a backer", "On a failed campaign, switch to a backer and click Refund.", any(e["kind"] == "refund" for e in evs)),
        ("Verify a certificate", "Open any receipt, view its certificate and press Verify.", verified),
    ]
    return [dict(title=t, hint=h, done=bool(d)) for t, h, d in rows]


SEED = [  # creator, title, tagline, story, category, goal (ETH), minutes, [(backer, ETH), ...]
    (0, "Library on Wheels", "A bike-powered mobile library for villages with no reading room.",
     "We are converting three cargo bikes into mobile libraries that visit twelve villages every week. Funds buy the bikes, 900 children's books and a year of volunteer stipends.",
     "Education", "8", 7 * 1440, [(1, "2"), (2, "1.5"), (3, "3")]),
    (0, "Braille Keyboard for Everyone", "An open-source braille keyboard that costs a tenth of the market price.",
     "Our prototype prints on any 3D printer and works with every phone. Funding covers testing with 200 users and publishing the full design files.",
     "Technology", "5", 3 * 1440, [(1, "3"), (4, "2.5")]),
    (1, "Riverbank Cleanup Weekend", "Gloves, bags and lunch for 150 volunteers cleaning the river.",
     "One weekend, three kilometres of riverbank, 150 volunteers. We need safety gear, waste disposal and food for everyone who turns up.",
     "Environment", "3", 2 * 1440, [(2, "0.4"), (5, "0.6")]),
    (2, "Solar Lights for Night School", "Lamps so adults can learn after dark.",
     "The evening literacy class runs in a hall with no power. Twelve solar lamps and a charging station keep it open all year.",
     "Community", "4", 5 * 1440, [(3, "1"), (4, "1"), (6, "1.2")]),
    (3, "Neighbourhood Film Night", "A weekly outdoor cinema on the old car park.",
     "A projector, a screen and licences for 12 screenings. Ending soon: skip the clock forward an hour to watch what happens when a goal is missed.",
     "Creative", "2", 60, [(1, "0.5"), (2, "0.7")]),
    (4, "Mobile Clinic Fuel Fund", "Fuel for the clinic van that reaches remote hill villages.",
     "The van visits eight villages a month with a nurse and basic medicines. Fuel is the one cost grants do not cover.",
     "Health", "6", 1440, [(0, "1"), (5, "1.5")]),
]


def seed_demo():
    """Create the sample campaigns with real transactions from different accounts."""
    accts = accounts()
    for creator, title, tagline, story, cat, goal, minutes, backers in SEED:
        receipt = contract.transact("createCampaign", title, story, eth_to_wei(goal), minutes * 60, sender=accts[creator])
        set_meta(receipt["transactionHash"], category=cat, tagline=tagline)
        cid = contract.call("campaignCount")
        for who, amount in backers:
            contract.transact("pledge", cid, sender=accts[who], value=eth_to_wei(amount))
    return len(SEED)
