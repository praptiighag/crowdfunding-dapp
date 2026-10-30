# Vouch: Fundraising That Proves Itself

A decentralized crowdfunding platform built on a private Ganache blockchain. Backers pledge test ETH into escrow inside a smart contract. If a campaign reaches its funding goal before the deadline, the organizer can withdraw the funds. If the campaign fails, every backer can claim a refund.

No intermediary holds the money, and every transaction produces a receipt and a certificate that can be verified against the blockchain.

## Tech Stack

- **Blockchain:** Ganache (Private Blockchain)
- **Smart Contracts:** Solidity 0.8.19
- **Backend:** Python, Flask
- **Blockchain Communication:** Custom Python JSON-RPC client
- **Frontend:** HTML, CSS, JavaScript, Bootstrap
- **Off-chain Storage:** JSON
- **Testing:** Pytest

## System Architecture

```text
Browser
   |
   v
Flask Routes (app.py)
   |
   v
Services Layer (services.py)
   |
   v
Blockchain Client (chain.py)
   |
   v
Ganache Private Blockchain (:7545)
   |
   v
Crowdfunding Smart Contract
```

Campaign presentation data, such as categories, summaries, and updates, is stored separately in `data/meta.json`.

## Features

### 1. Campaign Exploration and Details
- Browse crowdfunding campaigns.
- View campaign categories and generated cover art.
- Search and filter campaigns.
- Track fundraising progress using progress bars and charts.
- View campaign stories, updates, backers, and transaction proof trails.

### 2. Smart Contract Escrow
- Contributions are held inside a smart contract.
- Organizers can withdraw funds after a successful campaign.
- Backers can claim refunds when a campaign fails.
- Campaign deadlines and funding goals determine settlement eligibility.
- Transaction receipts provide evidence of blockchain activity.

### 3. User Personas and Dashboards
- Switch between demo personas such as Alice, Bob, and Carol.
- View account balances and contribution details.
- Manage campaigns through the **My Campaigns** dashboard.
- Track contributions and eligible refunds through **My Pledges**.
- View badges indicating actions that require attention.

### 4. Campaign Creation Wizard
- Create a new fundraising campaign.
- Enter the campaign title, category, funding goal, and duration.
- Preview campaign details before launching.

### 5. Transaction Management
- Confirm contributions before submitting transactions.
- View transaction status and receipts.
- Track transaction progress from submission to confirmation.
- Inspect decoded transaction inputs, events, and transaction fees.

### 6. Certificates and Verification
- Generate printable certificates for campaign creation, contributions, withdrawals, and refunds.
- Verify certificates against blockchain transaction information.
- Detect certificate tampering through fingerprint verification.

### 7. Wallet and Transaction History
- View wallet balances.
- Track ETH pledged, refunded, and released.
- View transaction history and network fees.

### 8. Interactive Demo Guide
- Follow a step-by-step demonstration of the application.
- Load sample campaigns.
- Test successful and unsuccessful fundraising scenarios.
- Demonstrate withdrawals, refunds, certificates, and transaction history.

## Project Structure

```text
crowdfunding-dapp/
│
├── contracts/
│   └── Crowdfunding.sol
│
├── data/
│   ├── .gitkeep
│   └── meta.json
│
├── docs/
│   └── DESIGN.md
│
├── static/
│   ├── app.js
│   └── style.css
│
├── templates/
│   ├── _macros.html
│   ├── account.html
│   ├── activity.html
│   ├── base.html
│   ├── campaign.html
│   ├── certificate.html
│   ├── explore.html
│   ├── index.html
│   ├── me_campaigns.html
│   ├── me_pledges.html
│   ├── start.html
│   ├── tx.html
│   └── verify.html
│
├── app.py
├── chain.py
├── deploy.py
├── services.py
├── requirements.txt
├── test_crowdfunding.py
├── README.md
└── .gitignore
```

### Important Files

| File | Purpose |
|---|---|
| `contracts/Crowdfunding.sol` | Smart contract for campaign creation, contributions, withdrawals, and refunds |
| `deploy.py` | Compiles and deploys the smart contract |
| `chain.py` | Communicates with the blockchain through JSON-RPC and handles ABI encoding and decoding |
| `services.py` | Contains campaign logic, blockchain reads, backer information, receipts, certificates, and demo data |
| `app.py` | Implements Flask routes and application functionality |
| `templates/` | Contains the HTML templates |
| `static/` | Contains JavaScript and CSS files |
| `data/meta.json` | Stores off-chain campaign metadata |
| `docs/DESIGN.md` | Describes the architecture, data model, user journeys, and design decisions |
| `test_crowdfunding.py` | Contains automated tests for blockchain utilities and the smart contract |

## Prerequisites

Install the following software before running the application:

- Python 3.9 or later
- Node.js and npm
- Ganache
- Git (optional for running locally, required for Git-based version control)

An internet connection is required for the initial Solidity compiler download and for loading external frontend resources.

## Installation and Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/praptiighag/crowdfunding-dapp.git
```

Navigate into the project folder:

```bash
cd crowdfunding-dapp
```

### Step 2: Create a Python Virtual Environment

**Windows:**

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, use an appropriate temporary execution policy for the current terminal session.

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Start Ganache

Start a local Ganache blockchain on port `7545`.

If Ganache CLI is installed, run:

```bash
ganache --port 7545 --chain.chainId 1337 --wallet.deterministic --wallet.defaultBalance 100
```

Keep Ganache running in a separate terminal.

### Step 5: Deploy the Smart Contract

Open another terminal in the project directory, activate the virtual environment, and run:

```bash
python deploy.py
```

The deployment script compiles the contract and writes the generated contract information to the build directory.

### Step 6: Run the Application

```bash
python app.py
```

Open the following address in your browser:

http://127.0.0.1:5000

**Note:** If Ganache restarts and resets its blockchain state, deploy the contract again using `python deploy.py`.

## Running Tests

To run the automated tests, execute:

```bash
pytest -v
```

The test suite includes offline blockchain-client tests and smart contract tests that require a running Ganache instance.

## Demo Guide

The following workflow demonstrates the main features of the application.

1. Open the application and explore the persona menu and Demo Guide.
2. Load the sample campaigns and explore the campaign listings.
3. Open a sample campaign and inspect its funding progress, chart, and proof trail.
4. Switch to another persona and contribute test ETH to a campaign.
5. Open the transaction receipt and verify the associated certificate.
6. Create a new campaign using the campaign creation wizard.
7. Advance the Ganache blockchain time to test deadline-based settlement.
8. Withdraw funds from a successful campaign.
9. Claim a refund from a failed campaign using the eligible backer account.
10. Inspect wallet balances, transaction history, and the Demo Guide checklist.

The exact sample campaigns and available actions depend on the demo data and current blockchain state.

## Design and Implementation

### 1. Smart Contract Escrow

The smart contract holds contributed funds until the campaign reaches a terminal state. Organizers cannot withdraw contributions before the campaign deadline and successful completion of the funding goal.

### 2. Checks-Effects-Interactions Pattern

The smart contract uses the Checks-Effects-Interactions pattern to reduce reentrancy risk. It uses low-level `call` for ETH transfers and pull-based refunds instead of iterating over every backer.

### 3. On-chain and Off-chain Data

The blockchain stores the financial rules and transaction records, including funding goals, deadlines, contributions, and payouts.

Campaign presentation data, such as categories, summaries, and organizer updates, is stored in `data/meta.json`.

This separation reduces unnecessary on-chain storage.

### 4. Certificate Verification

Certificate fingerprints are calculated using blockchain transaction information, including the transaction hash, block hash, and contract address.

The verification process recomputes the fingerprint using blockchain data to identify tampered certificates.

### 5. Custom JSON-RPC Client

The project uses a custom Python blockchain client instead of relying on `web3.py`. The client handles the blockchain operations required by the application, including JSON-RPC communication and ABI encoding and decoding.

### 6. Blockchain Time

Campaign deadlines depend on the blockchain's `block.timestamp`. Time advances as blocks are mined. Ganache's time-manipulation functionality can be used to test deadline-dependent scenarios.

### 7. Demo Wallets

Ganache provides local test accounts that can be used by the application's demo personas. These accounts are intended for local development and testing.

A production application would require a secure wallet integration, such as MetaMask, and proper transaction signing.

### 8. Layered Architecture

The application separates responsibilities into three main layers:

- **Presentation and routing:** `app.py`
- **Business logic:** `services.py`
- **Blockchain communication:** `chain.py`

This separation makes the application easier to understand, maintain, and test.

## Limitations

- The application uses a local private blockchain rather than a public production blockchain.
- Test ETH has no real monetary value.
- Blockchain timestamps may be influenced slightly by block producers.
- Campaign cancellation, editing, and pagination are not fully implemented.
- Off-chain metadata is stored in a local JSON file and is not independently tamper-proof.
- The smart contract has not undergone a professional security audit.
- Ganache's unlocked demo accounts are intended only for development and testing.

## Future Enhancements

- Integrate MetaMask for wallet connectivity.
- Deploy the smart contract to a public testnet.
- Store campaign metadata using IPFS or another decentralized storage system.
- Add campaign editing and cancellation functionality.
- Improve automated testing and security auditing.
- Introduce a production-ready database for off-chain data.
- Improve deployment, monitoring, and transaction error handling.

## Conclusion

Vouch demonstrates how blockchain smart contracts can support transparent crowdfunding through escrow, deadline-based settlement, refunds, transaction receipts, and certificate verification.

By combining Solidity, Ganache, Python, Flask, and a browser-based interface, the project provides a practical demonstration of decentralized fundraising and blockchain transaction management.
