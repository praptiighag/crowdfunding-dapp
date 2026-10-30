# Vouch: fundraising that proves itself

A decentralized crowdfunding platform on a private Ganache chain. Backers pledge test ETH into escrow inside a smart contract. Reach the goal by the deadline and the organizer withdraws the pool; miss it and every backer can refund themselves. No intermediary holds the money, and every step produces a receipt and a certificate anyone can verify against the chain.

**Stack:** Ganache (private chain) · Solidity 0.8.19 · a small pure-Python JSON-RPC client · Flask + Bootstrap

```
Browser ──> Flask routes (app.py) ──> services.py ──chain.py (JSON-RPC)──> Ganache :7545 ──> Crowdfunding.sol
                                          └──> data/meta.json   (off-chain: category, summary, updates)
```

## What you get

- **Explore and campaign pages** in the style of a fundraising platform: generated cover art, categories, search, filters, progress bar with a goal marker, funding-over-time chart, story / updates / backers / proof-trail tabs.
- **Escrow and settlement made visible:** how much the contract still holds, a progress stepper, "funds released to the organizer" (with receipt and certificate) or a per-backer refund table.
- **Personas, not account numbers:** Alice, Bob, Carol… with avatars and balances, switched from a wallet-style menu. Dashboards for **My campaigns** (withdraw when funded) and **My pledges** (refund when failed), with action-needed badges.
- **Launch wizard** with a live preview card (title, category, goal, duration).
- **Transaction experience:** confirm dialog before pledging, a "sending" overlay, then a receipt page with a Submitted → Mined → Confirmed progress strip, decoded function input, events and fee.
- **Certificates and a Verify page:** printable certificates for launch, contribution, disbursement and refund. The fingerprint is recomputed from the chain, so tampered certificates fail.
- **Wallet page** per address: balance, ETH pledged, refunded, released, network fees, every transaction.
- **Demo guide:** a checklist that ticks off by itself as the chain records each step, plus one click to load sample campaigns.

## Files

| Path | Purpose |
|---|---|
| `contracts/Crowdfunding.sol` | Escrow contract: create, pledge, withdraw, refund |
| `deploy.py` | Compiles with py-solc-x, deploys, writes `build/Crowdfunding.json` |
| `chain.py` | JSON-RPC client, ABI encoder/decoder, keccak-256 (replaces web3.py, nothing to compile) |
| `services.py` | Domain layer: contract reads, campaigns, backers, funding series, receipts, fingerprints, metadata store, demo seeding |
| `app.py` | Flask routes and template helpers (identicons, cover art, formatting) |
| `templates/`, `static/` | UI (13 templates, one stylesheet, one script) |
| `data/meta.json` | Created at runtime: off-chain campaign metadata |
| `docs/DESIGN.md` | Architecture, data model, user journeys, UX decisions, test plan |
| `test_crowdfunding.py` | 4 offline tests of `chain.py` + 9 contract tests on Ganache |

## Setup

1. Install Ganache and start it:
   `ganache --port 7545 --chain.chainId 1337 --wallet.deterministic --wallet.defaultBalance 100`
   For another port, set `GANACHE_URL`.
2. Install dependencies. Everything is pure Python, so any Python 3.9+ works with no C compiler. The first compile downloads solc, so you need internet once:
   ```
   python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Deploy: `python deploy.py`
4. Tests (optional): `pytest -v` (13 tests)
5. Run: `python app.py` and open http://127.0.0.1:5000

After restarting Ganache, run `python deploy.py` again. You can also delete `data/meta.json` to clear old metadata. The page loads Bootstrap and fonts from CDNs, so the browser needs internet.

## Live demo script (about 6 minutes)

1. Open the app. Point out the persona menu (top right) and the **Demo guide** button.
2. Open the Demo guide and click **Load sample campaigns**. Browse **Explore**: filter by category, sort by ending soon.
3. Open *Library on Wheels* as Alice. Show the escrow figure, the funding chart and the Proof trail tab.
4. Switch to **Bob** and pledge 1 ETH (confirm dialog → receipt with the progress strip). Open the certificate and press **Verify**.
5. Switch to **Alice** → **Start a campaign**. Walk the three-step wizard and watch the preview. Choose the 1-minute duration and launch.
6. Time travel (clock icon) **+1 day** a few times. *Braille Keyboard* is funded: as Alice open **My campaigns**, click **Withdraw**, and show the disbursement certificate.
7. *Riverbank Cleanup* missed its goal: switch to **Carol**, open **My pledges** and click **Refund**. The campaign page shows the refund progress and the other backer still waiting.
8. Open **Wallet and spending** for Carol, then **Activity**. The Demo guide should now read 7/7.

## Design notes (for the viva)

- **Escrow, not trust:** the organizer cannot reach pledged ETH before the deadline, and only after a successful campaign.
- **Checks-effects-interactions** and **`call` instead of `transfer`** in the contract; **pull-based refunds**, so there is no loop over all backers.
- **On-chain vs off-chain:** the chain holds money rules (goal, deadline, pledges, payouts). Presentation data (category, one-line summary, organizer updates) lives in `data/meta.json`, keyed by the creation transaction hash, as real dapps do with IPFS or a database.
- **Certificates need no authority:** the fingerprint is the keccak-256 of transaction hash + block hash + contract address. Anyone can recompute it from the chain.
- **Why not web3.py?** Its dependencies (`lru-dict`, `ckzg`) are C extensions that often fail to build. `chain.py` covers only what the project needs; swapping to web3.py later means replacing that one file.
- **Chain clock:** `block.timestamp` only moves when a block is mined. The app mines one block per request, and Time travel uses `evm_increaseTime`.
- **Wallets:** Ganache accounts are unlocked, so the app sends transactions "from" the selected persona. A production dapp would sign in the browser with MetaMask.
- Layering: routes (`app.py`) → domain logic (`services.py`) → node client (`chain.py`). Nothing below the routes knows about HTML.

## Known limitations

- Single-node private chain: no real consensus or decentralization.
- Miners can skew `block.timestamp` slightly; acceptable for deadlines of minutes or longer.
- No campaign cancellation or editing on-chain; no pagination (each page reads all events).
- Off-chain metadata is not tamper-proof (a JSON file); it affects presentation only, never money.
- Test ETH only; the contract has not been audited.
