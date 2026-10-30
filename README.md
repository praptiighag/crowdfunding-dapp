# Vouch — Blockchain-Based Crowdfunding Application

Vouch is a blockchain-based crowdfunding platform that enables users to create fundraising campaigns, contribute test ETH, and track transactions transparently using smart contracts.

The application uses a private Ganache blockchain to manage campaign funding, hold contributions in escrow, process withdrawals for successful campaigns, and allow refunds when campaigns fail.

## Features

- **Campaign Management:** Create and explore fundraising campaigns.
- **Smart Contract Escrow:** Hold contributions until campaign settlement conditions are satisfied.
- **Transparent Transactions:** Track contributions, withdrawals, and refunds.
- **Campaign Settlement:** Allow eligible organizers to withdraw funds and backers to claim refunds.
- **Transaction Receipts:** View transaction details and blockchain records.
- **Certificate Verification:** Generate and verify certificates using blockchain transaction data.
- **Wallet Dashboard:** Track balances, contributions, refunds, and transaction history.
- **Interactive Demo:** Explore sample campaigns and test different fundraising scenarios.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Backend logic |
| Flask | Web application framework |
| Solidity | Smart contract development |
| Ganache | Local blockchain |
| HTML | Web page structure |
| CSS | Styling |
| JavaScript | Frontend interactions |
| Bootstrap | Responsive user interface |
| JSON-RPC | Blockchain communication |
| Pytest | Automated testing |

## System Architecture

```text
User / Browser
      |
      v
Flask Application (app.py)
      |
      v
Business Logic (services.py)
      |
      v
Blockchain Client (chain.py)
      |
      v
Ganache Blockchain
      |
      v
Crowdfunding Smart Contract
```

Campaign presentation details, such as categories, descriptions, and updates, are stored separately in JSON format.

## Project Structure

```text
crowdfunding-dapp/
|
├── contracts/
│   └── Crowdfunding.sol
├── data/
├── docs/
├── static/
├── templates/
├── app.py
├── chain.py
├── deploy.py
├── services.py
├── requirements.txt
├── test_crowdfunding.py
├── README.md
└── .gitignore
```

## Installation and Setup

### Prerequisites

- Python 3.9 or later
- Node.js and npm
- Ganache
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/praptiighag/crowdfunding-dapp.git
cd crowdfunding-dapp
```

### 2. Create a Virtual Environment

For Windows:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Start Ganache

Start a local Ganache blockchain configured to use port `7545`.

If Ganache CLI is installed, run:

```bash
ganache --port 7545 --chain.chainId 1337 --wallet.deterministic --wallet.defaultBalance 100
```

Keep Ganache running in a separate terminal.

### 5. Deploy the Smart Contract

```bash
python deploy.py
```

### 6. Run the Application

```bash
python app.py
```

Open the application in your browser:

http://127.0.0.1:5000

### 7. Run Tests

```bash
pytest -v
```

Some smart contract tests require Ganache to be running.

## Security and Design

- **Escrow Mechanism:** Campaign contributions remain in the smart contract until withdrawal or refund conditions are satisfied.
- **Smart Contract Validation:** Funding goals and deadlines determine campaign settlement eligibility.
- **Pull-Based Refunds:** Eligible backers can claim refunds individually.
- **Blockchain Verification:** Certificates can be verified against blockchain transaction information.
- **Layered Architecture:** Application routes, business logic, and blockchain communication are separated into different modules.

## Limitations

- Uses a local private blockchain rather than a public production network.
- Uses test ETH with no real monetary value.
- Campaign metadata is stored in a local JSON file.
- The smart contract has not undergone a professional security audit.
- Demo wallet accounts are intended for local development and testing.

## Future Enhancements

- Integrate MetaMask for wallet connectivity.
- Deploy the smart contract to a public testnet.
- Use decentralized storage such as IPFS for campaign metadata.
- Add advanced campaign management features.
- Improve security testing and production deployment.

## Conclusion

Vouch demonstrates how blockchain technology can improve crowdfunding transparency through smart contract escrow, deadline-based settlement, refunds, transaction receipts, and certificate verification.

The project combines Python, Flask, Solidity, and Ganache to demonstrate decentralized fundraising and blockchain transaction management.

## Author

**Prapti Ghag**

GitHub: [@praptiighag](https://github.com/praptiighag)
