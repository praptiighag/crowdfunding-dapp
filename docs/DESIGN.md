# Vouch: design document

## 1. Problem and idea
Crowdfunding platforms ask backers to trust the platform with their money and with the claim that goals were met. Vouch moves both into a smart contract: pledges sit in escrow, the contract alone decides whether the organizer is paid or backers are refunded, and every step leaves a verifiable record.

## 2. Users and journeys
| Persona | Goal | Journey |
|---|---|---|
| **Organizer** (e.g. Alice) | Raise money for a project, get paid only if the goal is met | Launch (wizard) → share → post updates → after the deadline **My campaigns → Withdraw** |
| **Backer** (e.g. Bob) | Support a project safely | Explore → campaign page → pledge (confirm) → receipt and certificate → **My pledges → Refund** if it fails |
| **Evaluator / auditor** | Check that the system does what it claims | Activity feed → transaction page → certificate → **Verify** |

## 3. Architecture
```
Browser
  │  HTML, Bootstrap, app.js
Flask routes (app.py)           template filters: avatars, generated cover art, formatting
  │
services.py                     campaigns, backers, funding series, receipts, fingerprints,
  │                             metadata store, demo seeding   (per-request cache in flask.g)
chain.py                        JSON-RPC, ABI encode/decode, keccak-256
  │  HTTP JSON-RPC
Ganache (private chain)  ──  Crowdfunding.sol
```

## 4. Data model
**On-chain (source of truth for money):** `Campaign {creator, title, description, goal, deadline, totalRaised, claimed}`, `pledges[campaignId][backer]`, events `CampaignCreated`, `Pledged`, `FundsClaimed`, `Refunded`.

**Derived (computed from events and state, never stored):** status (active / goal reached / refunds open / funds released), escrow held, refunded total, backers, funding timeline, account spending, demo-guide progress.

**Off-chain (`data/meta.json`, keyed by creation tx hash):** category, one-line summary, organizer updates.

Escrow held = `totalRaised − refunded`, or 0 once the organizer has withdrawn.

## 5. Campaign lifecycle
`Launched → Funding → Deadline → Settlement`, where settlement is either *release funds* (goal met) or *refund backers* (goal missed). The campaign page shows this as a stepper and a settlement panel.

## 6. Pages and routes
| Route | Purpose |
|---|---|
| `/` | Landing: hero, platform totals, campaigns to back, how it works |
| `/explore` | Search, category chips, status and sort filters |
| `/campaign/<id>` | Cover, funding card, story, chart, updates, backers, proof trail |
| `/start` | Three-step launch wizard with live preview |
| `/me/campaigns`, `/me/pledges` | Role dashboards with action-needed prompts |
| `/account/<addr>` | Wallet view: balance, pledged, refunded, released, fees, transactions |
| `/activity` | All contract transactions |
| `/tx/<hash>`, `/tx/<hash>/certificate` | Receipt and printable certificate |
| `/verify` | Recompute a certificate fingerprint from the chain |
| `POST /demo/seed`, `/skip-time`, `/select-account` | Demo helpers |

## 7. UX decisions
- **Looks like a fundraising product:** cover art, category chips, progress with a goal marker, "days left", backer counts.
- **Identity:** violet ink and tangerine on white; every cover carries a faint verification seal; the tagline is the product promise.
- **Make blockchain legible:** personas instead of hex addresses, a confirm dialog before sending, a visible pending state, a Submitted → Mined → Confirmed strip, a plain-language settlement panel.
- **Always show the next step:** badges on the account menu, "Action needed" rows, state-specific funding card.
- **Demo-ability:** one-click sample data, time travel, and a self-ticking guide.
- **Accessibility basics:** skip link, labelled controls, visible focus, reduced-motion support, print stylesheet for certificates.

## 8. Test plan
| Level | What | How |
|---|---|---|
| Unit (offline) | keccak vectors, EIP-55 checksum, ABI round-trip, calldata decoding | `pytest` (4 tests) |
| Contract | create validation, pledge rules, withdraw rules, double-withdraw, refund rules, double-refund, no refund after success | `pytest` on Ganache (9 tests) |
| Manual | The demo script in the README, end to end | Browser |

## 9. Limitations and future work
Private single-node chain; MetaMask signing instead of unlocked accounts; IPFS for metadata; campaign cancellation; pagination; milestone-based release.
