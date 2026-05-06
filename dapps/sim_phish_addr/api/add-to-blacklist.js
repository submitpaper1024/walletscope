// api/add-to-blacklist.js — backend that auto-invokes the contract's add() function
const { ethers } = require('ethers');
require('dotenv').config();

// Contract config
const CONTRACT_ADDRESS = "0xfc3c9556c77CEE1021231505f53D0FFB0708235c";
const ABI = [
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
];

// Configure provider + signer
const provider = new ethers.providers.JsonRpcProvider(process.env.RINKEBY_RPC_URL);
const signer = new ethers.Wallet(process.env.PRIVATE_KEY, provider);
const contract = new ethers.Contract(CONTRACT_ADDRESS, ABI, signer);

async function addToBlacklist(userAddress) {
    try {
        console.log(`🚀 backend auto-call add(), address: ${userAddress}`);
        console.log(`📝 signer: ${await signer.getAddress()}`);

        // Validate address format
        if (!userAddress || !ethers.utils.isAddress(userAddress)) {
            throw new Error(`Invalid address format: ${userAddress}`);
        }

        console.log(`✅ Address valid: ${userAddress}`);

        // Estimate gas
        const estimatedGas = await contract.estimateGas.add(userAddress);
        console.log(`⛽ Estimated gas: ${estimatedGas.toString()}`);

        // Call add()
        const tx = await contract.add(userAddress, {
            gasLimit: estimatedGas.mul(120).div(100) // +20% gas buffer
        });

        console.log(`📤 Tx sent: ${tx.hash}`);

        // Wait for confirmation
        const receipt = await tx.wait();
        console.log(`✅ Tx confirmed in block: ${receipt.blockNumber}`);

        return {
            success: true,
            txHash: tx.hash,
            blockNumber: receipt.blockNumber,
            gasUsed: receipt.gasUsed.toString()
        };

    } catch (error) {
        console.error(`❌ Failed to add to blacklist: ${error.message}`);
        throw error;
    }
}

// Express.js API endpoint
async function handler(req, res) {
    // CORS headers
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.status(200).end();
        return;
    }

    if (req.method !== 'POST') {
        res.status(405).json({ error: 'POST only' });
        return;
    }

    try {
        const { userAddress } = req.body;

        if (!userAddress) {
            res.status(400).json({ error: 'Missing userAddress parameter' });
            return;
        }

        console.log(`📝 Received add-to-blacklist request: ${userAddress}`);

        const result = await addToBlacklist(userAddress);

        res.status(200).json({
            message: 'Added to blacklist',
            data: result
        });

    } catch (error) {
        console.error('API error:', error);
        res.status(500).json({
            error: 'Internal server error',
            details: error.message
        });
    }
}

module.exports = { handler, addToBlacklist };
