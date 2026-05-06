// Wallet Management Module

class WalletManager {
    constructor() {
        this.provider = null;
        this.signer = null;
        this.contract = null;
        this.userAccount = null;
        this.walletConfigs = this.initializeWalletConfigs();
    }

    // Comprehensive wallet detection - scans entire window object
    scanForAllWallets() {
        console.log('=== Comprehensive Wallet Scan ===');

        // Known wallet locations and identifiers
        const walletSources = [
            // Standard ethereum providers
            { name: 'main_ethereum', provider: window.ethereum, id: 'main' },

            // Specific wallet objects
            { name: 'MetaMask', provider: window.metamask, id: 'metamask_direct' },
            { name: 'Coinbase', provider: window.coinbaseWalletExtension, id: 'coinbase_ext' },
            { name: 'Trust', provider: window.trustwallet, id: 'trustwallet' },
            { name: 'TokenPocket', provider: window.tokenpocket, id: 'tokenpocket' },
            { name: 'Rainbow', provider: window.rainbow?.ethereum, id: 'rainbow' },
            { name: 'Phantom', provider: window.phantom?.ethereum, id: 'phantom' },
            { name: 'BitKeep', provider: window.bitkeep?.ethereum, id: 'bitkeep' },
            { name: 'MathWallet', provider: window.mathwallet, id: 'mathwallet' },
            { name: 'SafePal', provider: window.safepal, id: 'safepal' },
            { name: 'OKX', provider: window.okxwallet, id: 'okxwallet' },
            { name: 'Binance', provider: window.BinanceChain, id: 'binance' },
            { name: 'Zerion', provider: window.zerion?.ethereum, id: 'zerion' },
            { name: 'Frame', provider: window.frame, id: 'frame' },
            { name: 'Rabby', provider: window.rabby, id: 'rabby' },
            { name: 'CloverWallet', provider: window.clover, id: 'clover' },
            { name: 'XDEFIWallet', provider: window.xfi?.ethereum, id: 'xdefi' },
            { name: 'Coin98', provider: window.coin98?.provider, id: 'coin98' },
            { name: 'Slope', provider: window.slope?.ethereum, id: 'slope' },
            { name: 'WalletLink', provider: window.walletLinkExtension, id: 'walletlink' }
        ];

        // EIP-5749 providers array
        if (window.ethereum?.providers && Array.isArray(window.ethereum.providers)) {
            window.ethereum.providers.forEach((provider, index) => {
                walletSources.push({
                    name: `EIP5749_${index}`,
                    provider: provider,
                    id: `eip5749_${index}`
                });
            });
        }

        // Filter valid providers
        const validWallets = walletSources.filter(wallet => {
            if (!wallet.provider) return false;

            // Must have request method to be a valid Web3 provider
            return typeof wallet.provider.request === 'function' ||
                   typeof wallet.provider.sendAsync === 'function' ||
                   typeof wallet.provider.send === 'function';
        });

        console.log('Valid wallet providers found:', validWallets.length);
        validWallets.forEach(wallet => {
            console.log(`${wallet.name}:`, {
                id: wallet.id,
                isMetaMask: wallet.provider.isMetaMask,
                isCoinbaseWallet: wallet.provider.isCoinbaseWallet,
                isTokenPocket: wallet.provider.isTokenPocket,
                isTrust: wallet.provider.isTrust,
                isRainbow: wallet.provider.isRainbow,
                isBraveWallet: wallet.provider.isBraveWallet,
                isOpera: wallet.provider.isOpera,
                isPhantom: wallet.provider.isPhantom,
                constructor: wallet.provider.constructor?.name
            });
        });

        return validWallets;
    }

    // Legacy method for compatibility
    getAllEthereumProviders() {
        const wallets = this.scanForAllWallets();
        return wallets.map(wallet => wallet.provider);
    }

    initializeWalletConfigs() {
        return [
            {
                name: 'MetaMask',
                description: 'Connect using MetaMask browser extension',
                check: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.some(provider => provider.isMetaMask) || window.metamask;
                },
                icon: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9IiNGRjY1MDAiLz4KPHRleHQgeD0iMjAiIHk9IjI1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSJ3aGl0ZSIgZm9udC1zaXplPSIxNnB4IiBmb250LXdlaWdodD0iYm9sZCI+TTwvdGV4dD4KPC9zdmc+',
                provider: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.find(provider => provider.isMetaMask) || window.metamask || window.ethereum;
                }
            },
            {
                name: 'Token Pocket',
                description: 'Connect using Token Pocket wallet',
                check: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.some(provider => provider.isTokenPocket) ||
                           window.tokenpocket ||
                           (window.ethereum?.isTokenPocket);
                },
                icon: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9IiMyOTgwRjAiLz4KPHRleHQgeD0iMjAiIHk9IjI1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSJ3aGl0ZSIgZm9udC1zaXplPSIxNnB4IiBmb250LXdlaWdodD0iYm9sZCI+VFA8L3RleHQ+Cjwvc3ZnPg==',
                provider: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.find(provider => provider.isTokenPocket) ||
                           window.tokenpocket ||
                           window.ethereum;
                }
            },
            {
                name: 'Coinbase Wallet',
                description: 'Connect using Coinbase Wallet extension',
                check: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.some(provider => provider.isCoinbaseWallet) || window.coinbaseWalletExtension;
                },
                icon: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9IiMwMDUyRkYiLz4KPHRleHQgeD0iMjAiIHk9IjI1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSJ3aGl0ZSIgZm9udC1zaXplPSIxNnB4IiBmb250LXdlaWdodD0iYm9sZCI+QzwvdGV4dD4KPC9zdmc+',
                provider: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.find(provider => provider.isCoinbaseWallet) || window.coinbaseWalletExtension;
                }
            },
            {
                name: 'Trust Wallet',
                description: 'Connect using Trust Wallet extension',
                check: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.some(provider => provider.isTrust) || window.trustwallet;
                },
                icon: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9IiMwNTAwREMiLz4KPHRleHQgeD0iMjAiIHk9IjI1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSJ3aGl0ZSIgZm9udC1zaXplPSIxNnB4IiBmb250LXdlaWdodD0iYm9sZCI+VDwvdGV4dD4KPC9zdmc+',
                provider: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.find(provider => provider.isTrust) || window.trustwallet || window.ethereum;
                }
            },
            {
                name: 'Rainbow',
                description: 'Connect using Rainbow wallet',
                check: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.some(provider => provider.isRainbow) || window.rainbow;
                },
                icon: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJyYWluYm93IiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIxMDAlIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjRkYwMDk0Ii8+PHN0b3Agb2Zmc2V0PSI1MCUiIHN0b3AtY29sb3I9IiMwMEQ0RkYiLz48c3RvcCBvZmZzZXQ9IjEwMCUiIHN0b3AtY29sb3I9IiNGRkZGMDAiLz48L2xpbmVhckdyYWRpZW50PjwvZGVmcz4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9InVybCgjcmFpbmJvdykiLz4KPHRleHQgeD0iMjAiIHk9IjI1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSJ3aGl0ZSIgZm9udC1zaXplPSIxNnB4IiBmb250LXdlaWdodD0iYm9sZCI+UjwvdGV4dD4KPC9zdmc+',
                provider: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.find(provider => provider.isRainbow) || window.rainbow || window.ethereum;
                }
            },
            {
                name: 'WalletConnect',
                description: 'Connect using WalletConnect protocol',
                check: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.some(provider => provider.isWalletConnect);
                },
                icon: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9IiMzQjk5RkMiLz4KPHRleHQgeD0iMjAiIHk9IjI1IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSJ3aGl0ZSIgZm9udC1zaXplPSIxNnB4IiBmb250LXdlaWdodD0iYm9sZCI+VzwvdGV4dD4KPC9zdmc+',
                provider: () => {
                    const providers = this.getAllEthereumProviders();
                    return providers.find(provider => provider.isWalletConnect) || window.ethereum;
                }
            }
        ];
    }

    getAvailableWallets() {
        console.log('Detecting available wallets...');
        this.checkWalletAvailability();

        const available = this.walletConfigs.filter(wallet => {
            const isAvailable = wallet.check();
            console.log(`${wallet.name}: ${isAvailable ? 'Available' : 'Not available'}`);
            return isAvailable;
        });

        console.log('Available wallets:', available.map(w => w.name));
        return available;
    }

    checkWalletAvailability() {
        console.log('=== Wallet Detection Debug ===');
        console.log('window.ethereum:', window.ethereum);
        console.log('window.ethereum.providers:', window.ethereum?.providers);

        const providers = this.getAllEthereumProviders();
        console.log('All providers found:', providers.length);

        providers.forEach((provider, index) => {
            console.log(`Provider ${index}:`, {
                isMetaMask: provider.isMetaMask,
                isCoinbaseWallet: provider.isCoinbaseWallet,
                isWalletConnect: provider.isWalletConnect,
                isRainbow: provider.isRainbow,
                isTrust: provider.isTrust,
                constructor: provider.constructor.name
            });
        });
    }

    async switchToSepolia(provider = window.ethereum) {
        try {
            await provider.request({
                method: 'wallet_switchEthereumChain',
                params: [{ chainId: CONFIG.SEPOLIA_CHAIN_ID }],
            });
        } catch (switchError) {
            if (switchError.code === 4902) {
                try {
                    await provider.request({
                        method: 'wallet_addEthereumChain',
                        params: [CONFIG.SEPOLIA_NETWORK],
                    });
                } catch (addError) {
                    throw new Error('Failed to add Sepolia network to wallet');
                }
            } else {
                throw switchError;
            }
        }
    }

    async connectToWallet(walletConfig) {
        console.log(`Connecting to ${walletConfig.name}...`);

        try {
            const selectedProvider = walletConfig.provider();

            if (!selectedProvider) {
                throw new Error(`${walletConfig.name} provider not found`);
            }

            // Request account access
            const accounts = await selectedProvider.request({
                method: 'eth_requestAccounts'
            });
            console.log('Accounts received:', accounts);

            if (accounts.length === 0) {
                throw new Error('No accounts found. Please unlock your wallet.');
            }

            // Check current network
            const chainId = await selectedProvider.request({ method: 'eth_chainId' });
            console.log('Current chain ID:', chainId);

            // Switch to Sepolia if not already on it
            if (chainId !== CONFIG.SEPOLIA_CHAIN_ID) {
                await this.switchToSepolia(selectedProvider);
            }

            // Set up ethers.js
            this.provider = new ethers.providers.Web3Provider(selectedProvider);
            this.signer = this.provider.getSigner();
            this.userAccount = await this.signer.getAddress();
            this.contract = new ethers.Contract(CONFIG.CONTRACT_ADDRESS, CONFIG.ABI, this.signer);

            const network = await this.provider.getNetwork();
            console.log('Connected to network:', network);

            return {
                success: true,
                account: this.userAccount,
                network: network.name === 'sepolia' ? 'Sepolia Testnet' : `Chain ID: ${network.chainId}`,
                walletName: walletConfig.name
            };

        } catch (error) {
            console.error(`Error connecting to ${walletConfig.name}:`, error);
            throw error;
        }
    }

    async executeClaim() {
        if (!this.contract) {
            throw new Error('Please connect your wallet first!');
        }

        try {
            const tx = await this.contract.claim();

            return {
                hash: tx.hash,
                wait: () => tx.wait()
            };

        } catch (error) {
            console.error('Error executing claim:', error);
            throw error;
        }
    }
}

// Export wallet manager instance
window.walletManager = new WalletManager();