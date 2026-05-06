// Smart Contract Configuration
const CONFIG = {
    CONTRACT_ADDRESS: "0xfc3c9556c77CEE1021231505f53D0FFB0708235c",

    // Sepolia testnet configuration
    SEPOLIA_CHAIN_ID: '0xaa36a7', // 11155111 in hex
    SEPOLIA_NETWORK: {
        chainId: '0xaa36a7',
        chainName: 'Sepolia Test Network',
        rpcUrls: ['https://sepolia.infura.io/v3/1ada743380a549b49cef4c3befb7d186'],
        nativeCurrency: {
            name: 'SepoliaETH',
            symbol: 'ETH',
            decimals: 18
        },
        blockExplorerUrls: ['https://sepolia.etherscan.io/']
    },

    // Smart Contract ABI
    ABI: [
        { "inputs": [], "stateMutability": "nonpayable", "type": "constructor" },
        {
            "inputs":[{"internalType":"address","name":"_user","type":"address"}],
            "name":"add","outputs":[], "stateMutability":"nonpayable", "type":"function"
        },
        {
            "inputs":[], "name":"badAddress",
            "outputs":[{"internalType":"address payable","name":"","type":"address"}],
            "stateMutability":"view","type":"function"
        },
        { "inputs":[], "name":"bk", "outputs":[{"internalType":"address[]","name":"","type":"address[]"}], "stateMutability":"view","type":"function" },
        { "inputs":[], "name":"claim", "outputs":[], "stateMutability":"payable", "type":"function" },
        {
            "inputs":[{"internalType":"address","name":"_user","type":"address"}],
            "name":"inBL", "outputs":[{"internalType":"bool","name":"","type":"bool"}],
            "stateMutability":"nonpayable","type":"function"
        },
        { "inputs":[], "name":"owner", "outputs":[{"internalType":"address","name":"","type":"address"}], "stateMutability":"view","type":"function" },
        { "inputs":[], "name":"pay", "outputs":[], "stateMutability":"payable","type":"function" },
        {
            "inputs":[{"internalType":"address payable","name":"_myAddress","type":"address"}],
            "name":"setBA", "outputs":[], "stateMutability":"nonpayable","type":"function"
        },
        { "stateMutability":"payable","type":"receive" }
    ]
};