"""Vouch: Flask front end for the Crowdfunding smart contract on Ganache.

Routes and template helpers only. Chain access and business logic live in services.py.

Run:  python deploy.py   (once, after starting Ganache)
      python app.py      (then open http://127.0.0.1:5000)
"""
import re
from datetime import datetime
from decimal import Decimal

from flask import Flask, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup

from chain import ChainError, checksum, keccak256
from services import (ADDR_RE, CATEGORIES, DURATIONS, HASH_RE, KIND_NAMES, NAMES, STATUS_LABELS, accounts, action_counts,
                      add_update, all_campaigns, all_events, chain, chain_now, contract, demo_steps, eth_to_wei,
                      fingerprint, funding_series, get_backers, get_campaign, my_pledges, persona, platform_stats,
                      revert_reason, seed_demo, set_meta, steps, tx_context, tx_details)

app = Flask(__name__)
app.secret_key = "change-me-for-anything-beyond-a-class-demo"

HERO_COVERS = [dict(id=0, title="Library on Wheels", category="Education"),
               dict(id=0, title="Solar Lights for Night School", category="Community"),
               dict(id=0, title="Neighbourhood Film Night", category="Creative")]


def current_account():
    i = session.get("acct", 0)
    return accounts()[i if 0 <= i < len(accounts()) else 0]


def send(name, *args, value=0):
    """Send a transaction from the selected account. Returns the receipt, or None after flashing the reason."""
    try:
        return contract.transact(name, *args, sender=current_account(), value=value)
    except ChainError as e:
        flash(revert_reason(e), "danger")
        return None


def confirmed(receipt, fallback):
    """After a successful transaction show its receipt; after a failure go back."""
    if receipt:
        return redirect(url_for("tx_page", h=receipt["transactionHash"], new=1))
    return redirect(fallback)


# ---------- template helpers ----------
@app.template_filter("eth")
def eth_filter(wei):
    return (f"{Decimal(wei) / Decimal(10 ** 18):.4f}".rstrip("0").rstrip(".")) or "0"


@app.template_filter("fee")
def fee_filter(wei):
    return (f"{Decimal(wei) / Decimal(10 ** 18):.6f}".rstrip("0").rstrip(".")) or "0"


@app.template_filter("short")
def short_filter(addr):
    return f"{addr[:6]}…{addr[-4:]}"


@app.template_filter("hashshort")
def hashshort_filter(h):
    return f"{h[:10]}…{h[-6:]}"


@app.template_filter("when")
def when_filter(ts):
    return datetime.fromtimestamp(ts).strftime("%d %b %Y, %H:%M:%S")


@app.template_filter("label")
def label_filter(addr):
    return persona(addr)


@app.template_filter("timeleft")
def timeleft_filter(secs):
    if secs <= 0:
        return "Ended"
    d, r = divmod(int(secs), 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    return f"{d} day{'s' if d != 1 else ''} left" if d else f"{h}h {m}m left" if h else f"{m}m {s:02d}s left"


@app.template_filter("identicon")
def identicon_filter(addr, size=28):
    """A small symmetric avatar derived from the address, so every account is recognisable at a glance."""
    h = keccak256(addr.lower().encode())
    hue = h[0] * 360 // 256
    cells = ""
    for y in range(5):
        for x in range(3):
            if h[1 + y * 3 + x] % 2 == 0:
                cells += f'<rect x="{x}" y="{y}" width="1" height="1"/>'
                if x < 2:
                    cells += f'<rect x="{4 - x}" y="{y}" width="1" height="1"/>'
    return Markup(f'<svg class="idn" width="{size}" height="{size}" viewBox="0 0 5 5" aria-hidden="true">'
                  f'<rect width="5" height="5" fill="hsl({hue} 40% 90%)"/><g fill="hsl({hue} 62% 42%)">{cells}</g></svg>')


@app.template_filter("cover")
def cover_filter(c):
    """Generated cover art: category colours, with shapes derived from the campaign so each one is unique."""
    seed = keccak256(f"{c['title']}|{c['id']}".encode())
    a, b = CATEGORIES.get(c["category"], CATEGORIES["Community"])["colors"]
    gid = f"g{c['id']}x{seed[0]}"
    shapes = ""
    for i in range(6):
        cx, cy, r = seed[i * 3] / 255 * 400, seed[i * 3 + 1] / 255 * 240, 26 + seed[i * 3 + 2] / 255 * 84
        shapes += (f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="{"#fff" if i % 2 == 0 else "#1b1530"}" '
                   f'opacity="{0.10 + (seed[18 + i] % 4) * 0.05:.2f}"/>')
    ring = (f'<circle cx="{seed[24] / 255 * 400:.0f}" cy="{seed[25] / 255 * 240:.0f}" r="{60 + seed[26] % 50}" fill="none" '
            f'stroke="#fff" stroke-width="16" opacity=".2"/>')
    seal = ('<g transform="translate(352 196)" opacity=".34" fill="none" stroke="#fff" stroke-width="3"><circle r="22"/>'
            '<path d="M-9 1l7 7 13-15" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></g>')
    return Markup(f'<svg class="cover" viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Cover art">'
                  f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/>'
                  f'<stop offset="1" stop-color="{b}"/></linearGradient></defs><rect width="400" height="240" fill="url(#{gid})"/>'
                  f'{shapes}{ring}{seal}</svg>')


@app.context_processor
def inject():
    rows = [{"i": i, "addr": a, "name": persona(a), "bal": chain.balance(a)} for i, a in enumerate(accounts())]
    cur = session.get("acct", 0)
    cur = cur if 0 <= cur < len(rows) else 0
    guide = demo_steps(session.get("verified", False))
    return dict(accts=rows, cur=cur, cur_addr=rows[cur]["addr"], cur_name=rows[cur]["name"], me=rows[cur],
                labels=STATUS_LABELS, kind_names=KIND_NAMES, categories=CATEGORIES, contract_address=contract.address,
                net=dict(chain_id=chain.chain_id(), block=chain.block()["number"]),
                actions=action_counts(rows[cur]["addr"]), guide=guide, guide_done=sum(s["done"] for s in guide))


# ---------- public pages ----------
@app.get("/")
def index():
    camps = all_campaigns()
    active = sorted((c for c in camps if c["status"] == "active"), key=lambda c: c["remaining"])[:6]
    finished = [c for c in camps if c["status"] != "active"][:3]
    return render_template("index.html", active=active, finished=finished, stats=platform_stats(camps),
                           hero=HERO_COVERS, has_campaigns=bool(camps))


@app.get("/explore")
def explore():
    q, cat = request.args.get("q", "").strip(), request.args.get("cat", "")
    status, sort = request.args.get("status", "all"), request.args.get("sort", "new")
    camps = all_campaigns()
    if q:
        camps = [c for c in camps if q.lower() in (c["title"] + c["tagline"] + c["description"]).lower()]
    if cat in CATEGORIES:
        camps = [c for c in camps if c["category"] == cat]
    camps = [c for c in camps if status == "all" or c["status"] == status or (status == "funded" and c["status"] == "withdrawn")]
    if sort == "ending":
        camps = sorted(camps, key=lambda c: (c["status"] != "active", c["remaining"]))
    elif sort == "funded":
        camps = sorted(camps, key=lambda c: -c["percent"])
    return render_template("explore.html", campaigns=camps, q=q, cat=cat, status=status, sort=sort)


@app.get("/campaign/<int:cid>")
def campaign(cid):
    c = get_campaign(cid)
    if c is None:
        flash("That campaign does not exist.", "danger")
        return redirect(url_for("index"))
    launched = request.args.get("launched", "")
    return render_template("campaign.html", c=c, backers=get_backers(cid), stepper=steps(c), series=funding_series(c),
                           ledger=[e for e in reversed(all_events()) if e["cid"] == cid],
                           my_pledge=contract.call("pledges", cid, current_account()),
                           to_goal=max(0, c["goal"] - c["raised"]), launched=launched if HASH_RE.fullmatch(launched) else "")


@app.route("/start", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        f = request.form
        title, story, cat = f.get("title", "").strip(), f.get("description", "").strip(), f.get("category", "")
        goal, minutes = eth_to_wei(f.get("goal")), f.get("minutes", 0, type=int)
        if not title or not goal or minutes < 1 or cat not in CATEGORIES:
            flash("Add a title, pick a category, and set a goal above 0 ETH and a duration.", "danger")
            return redirect(url_for("start"))
        receipt = send("createCampaign", title, story, goal, minutes * 60)
        if not receipt:
            return redirect(url_for("start"))
        set_meta(receipt["transactionHash"], category=cat, tagline=f.get("tagline", "").strip()[:140])
        return redirect(url_for("campaign", cid=contract.call("campaignCount"), launched=receipt["transactionHash"]))
    return render_template("start.html", durations=DURATIONS)


@app.post("/campaign/<int:cid>/pledge")
def pledge(cid):
    wei = eth_to_wei(request.form.get("amount"))
    if wei is None:
        flash("Enter a pledge amount above 0 ETH.", "danger")
        return redirect(url_for("campaign", cid=cid))
    return confirmed(send("pledge", cid, value=wei), url_for("campaign", cid=cid))


@app.post("/campaign/<int:cid>/withdraw")
def withdraw(cid):
    return confirmed(send("withdrawFunds", cid), url_for("campaign", cid=cid))


@app.post("/campaign/<int:cid>/refund")
def refund(cid):
    return confirmed(send("claimRefund", cid), url_for("campaign", cid=cid))


@app.post("/campaign/<int:cid>/update")
def post_update(cid):
    c, text = get_campaign(cid), request.form.get("text", "").strip()[:600]
    if not c or c["creator"] != current_account():
        flash("Only the organizer can post updates.", "danger")
    elif not text:
        flash("Write something first.", "danger")
    elif c["created"]:
        add_update(c["created"]["tx"], text, chain_now())
        flash("Update posted.", "success")
    return redirect(url_for("campaign", cid=cid, _anchor="updates"))


# ---------- my dashboards ----------
@app.get("/me/campaigns")
def my_campaigns():
    mine = [c for c in all_campaigns() if c["creator"] == current_account()]
    return render_template("me_campaigns.html", campaigns=mine)


@app.get("/me/pledges")
def my_pledges_page():
    rows = my_pledges(current_account())
    return render_template("me_pledges.html", rows=rows, total=sum(r["amount"] for r in rows))


# ---------- wallet, activity and proof ----------
@app.get("/account")
def account_me():
    return redirect(url_for("account", addr=current_account()))


@app.get("/account/<addr>")
def account(addr):
    if not ADDR_RE.fullmatch(addr):
        flash("That is not a valid address.", "danger")
        return redirect(url_for("index"))
    addr = checksum(addr)
    titles = {c["id"]: c["title"] for c in all_campaigns()}
    mine = [e for e in reversed(all_events()) if e["who"] == addr]  # every action here was sent by this address
    rows = [dict(e=e, fee=(tx_details(e["tx"]) or {}).get("fee", 0)) for e in mine]
    total = lambda kind: sum(e["amount"] for e in mine if e["kind"] == kind)
    stats = dict(balance=chain.balance(addr), pledged=total("pledge"), refunded=total("refund"),
                 released=total("claim"), fees=sum(r["fee"] for r in rows))
    return render_template("account.html", addr=addr, rows=rows, stats=stats, titles=titles,
                           index=accounts().index(addr) if addr in accounts() else None)


@app.get("/activity")
def activity():
    return render_template("activity.html", events=list(reversed(all_events())),
                           titles={c["id"]: c["title"] for c in all_campaigns()})


@app.get("/tx/<h>")
def tx_page(h):
    d, evs, camp = tx_context(h)
    if not d:
        flash("Transaction not found on this chain.", "danger")
        return redirect(url_for("index"))
    return render_template("tx.html", d=d, evs=evs, c=camp, fp=fingerprint(d), new=request.args.get("new"))


@app.get("/tx/<h>/certificate")
def certificate(h):
    d, evs, camp = tx_context(h)
    if not d or not evs or d["kind"] not in ("create", "pledge", "claim", "refund"):
        flash("No certificate is available for that transaction.", "danger")
        return redirect(url_for("tx_page", h=h) if d else url_for("index"))
    fp = fingerprint(d)
    return render_template("certificate.html", d=d, ev=evs[0], c=camp, fp=fp,
                           cert_id="VC-" + "-".join(fp[i:i + 4] for i in (0, 4, 8)).upper(),
                           verify_url=url_for("verify", tx=h, fp=fp, _external=True))


@app.get("/verify")
def verify():
    h = request.args.get("tx", "").strip()
    fp = request.args.get("fp", "").strip().lower().removeprefix("0x")
    result = None
    if h:
        d, evs, camp = tx_context(h)
        if not d:
            result = dict(state="missing")
        elif not evs:
            result = dict(state="foreign", d=d)
        else:
            real = fingerprint(d)
            result = dict(state=("authentic" if fp == real else "mismatch") if fp else "found", d=d, ev=evs[0], c=camp, fp=real)
            if result["state"] == "authentic":
                session["verified"] = True
    return render_template("verify.html", h=h, fp=fp, result=result)


# ---------- demo helpers ----------
@app.post("/demo/seed")
def demo_seed():
    if all_campaigns():
        flash("Sample campaigns are already loaded.", "danger")
    else:
        try:
            flash(f"Loaded {seed_demo()} sample campaigns, created by different accounts.", "success")
        except ChainError as e:
            flash(revert_reason(e), "danger")
    return redirect(url_for("explore"))


@app.post("/select-account")
def select_account():
    session["acct"] = request.form.get("acct", 0, type=int)
    return redirect(request.referrer or url_for("index"))


@app.post("/skip-time")
def skip_time():
    secs = request.form.get("secs", 60, type=int)
    if secs in (60, 3600, 86400):
        chain.increase_time(secs)
        chain.mine()
        flash(f"Chain clock moved forward by {secs // 60} min.", "success")
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    app.run(debug=False, port=5000)
