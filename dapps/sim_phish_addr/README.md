# Smart Contract Claim DApp

A modern decentralized application (DApp) that allows users to interact with smart contracts on the Sepolia testnet. Features multi-wallet support and a clean, responsive interface.

## Features

- 🔗 **Multi-Wallet Support**: Connect with MetaMask, Coinbase Wallet, WalletConnect, Rainbow, Trust Wallet, and more
- 🌐 **Sepolia Testnet**: Automatically switches to Sepolia testnet for testing
- 📱 **Responsive Design**: Works on desktop and mobile devices
- ⚡ **Fast & Secure**: Built with modern web technologies
- 🔍 **Auto-Detection**: Automatically detects installed wallet extensions

## Quick Start

### Local Development

1. Clone the repository:
   ```bash
   git clone <your-repo-url>
   cd wallet-test-dapp
   ```

2. Start the local development server:
   ```bash
   python3 serve.py
   ```

3. Open your browser and navigate to `http://localhost:8000`

### Vercel Deployment

1. Install Vercel CLI:
   ```bash
   npm install -g vercel
   ```

2. Deploy to Vercel:
   ```bash
   vercel --prod
   ```

## Project Structure

```
wallet-test-dapp/
├── public/
│   └── index.html          # Main HTML file
├── static/
│   ├── css/
│   │   └── styles.css      # Application styles
│   ├── js/
│   │   ├── config.js       # Smart contract configuration
│   │   ├── wallet.js       # Wallet management logic
│   │   └── app.js          # Main application logic
│   └── favicon.svg         # Site favicon
├── vercel.json             # Vercel deployment configuration
├── package.json            # Project metadata
├── serve.py                # Local development server
└── README.md               # This file
```

## Smart Contract Configuration

The DApp is configured to interact with a smart contract on Sepolia testnet:

- **Contract Address**: `0xfc3c9556c77CEE1021231505f53D0FFB0708235c`
- **Network**: Sepolia Testnet
- **Function**: `claim()` - A payable function for claiming tokens/rewards

## Supported Wallets

- **MetaMask**: Most popular Ethereum wallet browser extension
- **Coinbase Wallet**: Coinbase's official wallet extension
- **WalletConnect**: Protocol for connecting mobile wallets
- **Rainbow**: Ethereum wallet with beautiful interface
- **Trust Wallet**: Multi-cryptocurrency wallet
- **Generic Wallets**: Any other Web3-compatible wallet

## Usage

1. **Connect Wallet**: Click "Connect Wallet" and select your preferred wallet
2. **Network Switch**: The app will automatically prompt to switch to Sepolia testnet
3. **Claim**: Once connected, click the "Claim" button to execute the smart contract function
4. **Transaction**: Confirm the transaction in your wallet and wait for confirmation

## Development

### File Structure

- `config.js`: Contains smart contract ABI, addresses, and network configuration
- `wallet.js`: Handles wallet detection, connection, and smart contract interaction
- `app.js`: Main application logic and UI management
- `styles.css`: Responsive CSS styling with modern design

### Adding New Wallets

To add support for a new wallet, modify the `walletConfigs` array in `wallet.js`:

```javascript
{
    name: 'New Wallet',
    description: 'Connect using New Wallet extension',
    check: () => window.ethereum?.isNewWallet,
    icon: 'data:image/svg+xml;base64,...',
    provider: () => window.ethereum
}
```

## Environment Variables

No environment variables are required for the frontend. The smart contract configuration is included in the client-side code.

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Security

- Never commit private keys or sensitive data
- Always verify contract addresses before interacting
- Use testnet for development and testing
- Keep wallet extensions updated