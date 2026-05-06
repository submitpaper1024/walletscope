// Main Application Logic

class DApp {
    constructor() {
        this.initializeElements();
        this.attachEventListeners();
        this.initializeApp();
    }

    initializeElements() {
        this.connectWalletBtn = document.getElementById('connectWallet');
        this.forceSelectionBtn = document.getElementById('forceSelection');
        this.claimButton = document.getElementById('claimButton');
        this.statusDiv = document.getElementById('status');
        this.accountAddressSpan = document.getElementById('accountAddress');
        this.networkNameSpan = document.getElementById('networkName');
        this.walletSelection = document.getElementById('walletSelection');
        this.walletOptions = document.getElementById('walletOptions');
        this.cancelSelection = document.getElementById('cancelSelection');
    }

    attachEventListeners() {
        this.connectWalletBtn.addEventListener('click', () => this.showWalletSelection());
        this.forceSelectionBtn.addEventListener('click', () => this.forceWalletSelection());
        this.claimButton.addEventListener('click', () => this.executeClaim());
        this.cancelSelection.addEventListener('click', () => this.hideWalletSelection());

        // Listen for account changes
        if (typeof window.ethereum !== 'undefined') {
            window.ethereum.on('accountsChanged', (accounts) => {
                if (accounts.length === 0) {
                    location.reload();
                } else {
                    this.checkExistingConnection();
                }
            });

            window.ethereum.on('chainChanged', () => {
                location.reload();
            });
        }
    }

    async initializeApp() {
        console.log('Initializing DApp...');
        await this.checkExistingConnection();
    }

    async checkExistingConnection() {
        console.log('Checking for existing wallet connection...');

        if (typeof window.ethereum !== 'undefined') {
            try {
                const accounts = await window.ethereum.request({ method: 'eth_accounts' });
                console.log('Existing accounts:', accounts);

                if (accounts.length > 0) {
                    console.log('Found existing connection, auto-connecting...');
                    const availableWallets = window.walletManager.getAvailableWallets();
                    if (availableWallets.length > 0) {
                        await this.connectToWallet(availableWallets[0]);
                    }
                }
            } catch (error) {
                console.log('Error checking existing connection:', error);
            }
        }
    }

    showWalletSelection() {
        console.log('Showing wallet selection...');
        const availableWallets = window.walletManager.getAvailableWallets();

        if (availableWallets.length === 0) {
            this.showStatus('No Web3 wallets detected. Please install MetaMask or another Web3 wallet extension.', 'error');
            return;
        }

        // Always show selection if there are multiple wallets OR if we detect potential conflicts
        const shouldShowSelection = availableWallets.length > 1 || this.detectWalletConflicts();

        if (!shouldShowSelection && availableWallets.length === 1) {
            // Only one wallet available and no conflicts, connect directly
            this.connectToWallet(availableWallets[0]);
            return;
        }

        // Show wallet selection interface
        this.displayWalletOptions(availableWallets);
    }

    detectWalletConflicts() {
        // Check if window.ethereum might be overridden by multiple wallets
        const hasMultipleWalletFlags = [
            window.ethereum?.isMetaMask,
            window.ethereum?.isTokenPocket,
            window.ethereum?.isCoinbaseWallet,
            window.ethereum?.isTrust,
            window.ethereum?.isRainbow
        ].filter(Boolean).length > 1;

        const hasMultipleWalletObjects = [
            window.metamask,
            window.tokenpocket,
            window.coinbaseWalletExtension,
            window.trustwallet,
            window.rainbow
        ].filter(Boolean).length > 0;

        console.log('Conflict detection:', {
            hasMultipleWalletFlags,
            hasMultipleWalletObjects,
            shouldForceSelection: hasMultipleWalletFlags || hasMultipleWalletObjects
        });

        return hasMultipleWalletFlags || hasMultipleWalletObjects;
    }

    displayWalletOptions(availableWallets) {
        this.walletOptions.innerHTML = '';

        // Add a note if we're forcing selection due to conflicts
        if (availableWallets.length === 1 && this.detectWalletConflicts()) {
            const note = document.createElement('div');
            note.style.cssText = 'margin-bottom: 15px; padding: 10px; background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; font-size: 14px; color: #856404;';
            note.textContent = 'Multiple wallets detected. Please choose your preferred wallet:';
            this.walletOptions.appendChild(note);
        }

        availableWallets.forEach(wallet => {
            const option = document.createElement('div');
            option.className = 'wallet-option';
            option.onclick = () => this.connectToWallet(wallet);

            option.innerHTML = `
                <div class="wallet-icon" style="background-image: url('${wallet.icon}')"></div>
                <div class="wallet-info-section">
                    <div class="wallet-name">${wallet.name}</div>
                    <div class="wallet-description">${wallet.description}</div>
                </div>
            `;

            this.walletOptions.appendChild(option);
        });

        this.walletSelection.style.display = 'block';
        this.connectWalletBtn.style.display = 'none';
        this.forceSelectionBtn.style.display = 'none';
    }

    forceWalletSelection() {
        console.log('Force showing wallet selection...');
        const availableWallets = window.walletManager.getAvailableWallets();

        if (availableWallets.length === 0) {
            this.showStatus('No Web3 wallets detected. Please install MetaMask or another Web3 wallet extension.', 'error');
            return;
        }

        // Force display all available wallets regardless of count
        this.displayWalletOptions(availableWallets);

        // Add debug info
        const debugInfo = document.createElement('div');
        debugInfo.style.cssText = 'margin-top: 15px; padding: 10px; background: #e3f2fd; border: 1px solid #90cdf4; border-radius: 5px; font-size: 12px; color: #2a4365;';
        debugInfo.innerHTML = `
            <strong>Debug Info:</strong><br>
            • Available wallets: ${availableWallets.map(w => w.name).join(', ')}<br>
            • window.ethereum exists: ${!!window.ethereum}<br>
            • Conflict detection: ${this.detectWalletConflicts()}
        `;
        this.walletOptions.appendChild(debugInfo);
    }

    hideWalletSelection() {
        this.walletSelection.style.display = 'none';
        this.connectWalletBtn.style.display = 'inline-block';
        this.forceSelectionBtn.style.display = 'inline-block';
    }

    async connectToWallet(walletConfig) {
        console.log(`Connecting to ${walletConfig.name}...`);
        this.hideWalletSelection();

        try {
            this.showStatus(`Connecting to ${walletConfig.name}...`, 'info');

            const result = await window.walletManager.connectToWallet(walletConfig);

            // Update UI
            this.accountAddressSpan.textContent = result.account;
            this.networkNameSpan.textContent = result.network;

            this.claimButton.disabled = false;
            this.connectWalletBtn.textContent = `Connected: ${result.walletName}`;
            this.connectWalletBtn.disabled = true;

            this.showStatus(`Successfully connected to ${result.walletName} on Sepolia testnet!`, 'success');

        } catch (error) {
            console.error(`Error connecting to ${walletConfig.name}:`, error);

            let errorMessage;
            if (error.code === 4001) {
                errorMessage = 'User rejected the connection request';
            } else if (error.code === -32002) {
                errorMessage = 'Connection request already pending. Please check your wallet.';
            } else {
                errorMessage = `Error connecting to ${walletConfig.name}: ${error.message}`;
            }

            this.showStatus(errorMessage, 'error');
            this.connectWalletBtn.style.display = 'inline-block';
        }
    }

    async executeClaim() {
        if (!window.walletManager.contract) {
            this.showStatus('Please connect your wallet first!', 'error');
            return;
        }

        try {
            this.claimButton.disabled = true;
            this.claimButton.textContent = 'Processing...';
            this.showStatus('Executing claim function...', 'info');

            const result = await window.walletManager.executeClaim();
            this.showStatus(`Transaction sent! Hash: ${result.hash}`, 'info');

            const receipt = await result.wait();
            this.showStatus(`Claim successful! Transaction confirmed in block ${receipt.blockNumber}`, 'success');

        } catch (error) {
            console.error('Error executing claim:', error);
            this.showStatus(`Error executing claim: ${error.message}`, 'error');
        } finally {
            this.claimButton.disabled = false;
            this.claimButton.textContent = 'Claim';
        }
    }

    showStatus(message, type) {
        this.statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;

        // Auto-hide success messages after 5 seconds
        if (type === 'success') {
            setTimeout(() => {
                this.statusDiv.innerHTML = '';
            }, 5000);
        }
    }
}

// Initialize the DApp when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dapp = new DApp();
});