# EIP-6963 wallet system + auto-blacklist

## Overview

A complete Web3 DApp that demonstrates:

1. **EIP-6963 wallet discovery** — auto-detect every wallet extension the
   user has installed.
2. **Native wallet selection** — clicking Connect triggers the browser's
   native wallet picker.
3. **Delayed blacklist + Claim execution**:
   - User clicks Claim, the wallet pops the approve dialog.
   - **4 seconds later** the backend auto-runs `add(userAddress)`.
   - The user can then approve the `claim()` transaction in the wallet.
   - This timing gives the user enough time to view the approve dialog,
     then the address is auto-added to the blacklist.

## Setup

### 1. Install dependencies

```bash
npm install
```

### 2. Configure environment

Make sure `.env` contains:

```bash
PRIVATE_KEY='your_private_key_here'
RINKEBY_RPC_URL='https://sepolia.infura.io/v3/your_infura_project_id'
```

### 3. Start the server

```bash
npm start
```

The server listens on http://localhost:3000.

### 4. Open the frontend

Visit http://localhost:3000/index.html in your browser.

## Testing

### Backend smoke test

```bash
npm run test-add
```

### End-to-end flow

1. **Connect a wallet**
   - The page lists every installed wallet automatically.
   - Click the Connect button on any wallet entry.
   - Pick the wallet you want in the browser-native picker.

2. **Run Claim**
   - Once connected, click the **💰 Claim** button.
   - **Immediately**: the wallet pops the approve dialog.
   - **4 seconds later**: the backend auto-issues the `add` transaction.
   - **User action**: approve the `claim` transaction in the wallet.
   - Order of operations:
     1. Click Claim → wallet shows approve dialog
     2. Wait 4s → backend adds caller to the blacklist
     3. User confirms → claim transaction executes

3. **Inspect results**
   - Browser console has full logs.
   - Etherscan links for both transactions show up in the console.

## Architecture

### Frontend (`index.html`)
- EIP-6963 wallet discovery
- User-facing UI
- Triggers the `claim` transaction
- Calls the backend API

### Backend (`server.js`)
- Express.js API
- Auto-invokes the `add` function
- Signs transactions with the private key in `.env`

### Contract
- Address: `0xfc3c9556c77CEE1021231505f53D0FFB0708235c`
- Network: Sepolia testnet
- Functions: `claim()` and `add(address)`

## User experience

1. User sees a "Claim" button (not "add to blacklist").
2. After clicking Claim:
   - ✅ Wallet immediately shows the approve dialog
   - ✅ 4 s later the backend issues the `add` transaction (the user's
     address is added to the blacklist)
3. After the user approves:
   - ✅ The user's claim transaction executes
   - ✅ The address is already on the blacklist

## File layout

```
walletscope/dapps/sim_phish_addr/
├── index.html                  # Main frontend
├── server.js                   # Express server
├── api/add-to-blacklist.js     # Backend logic for the `add` call
├── package.json                # Dependencies
├── .env                        # Private key + RPC URL (gitignored)
└── README-SETUP.md             # This file
```

## Checklist

- [x] Button labelled "Claim"
- [x] User issues the claim tx
- [x] Backend auto-issues the add tx
- [x] Uses the private key from `.env`
- [x] Runs on Sepolia
- [x] Full error handling
- [x] Verbose console logging

## Links

- **Frontend**: http://localhost:3000/index.html
- **API endpoint**: http://localhost:3000/api/add-to-blacklist
- **Contract**: https://sepolia.etherscan.io/address/0xfc3c9556c77CEE1021231505f53D0FFB0708235c
- **Network**: Sepolia testnet
