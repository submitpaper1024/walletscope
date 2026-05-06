// server.js — minimal Express server
const express = require('express');
const cors = require('cors');
const path = require('path');
const { addToBlacklist } = require('./api/add-to-blacklist');

require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('.'));

// API route
app.post('/api/add-to-blacklist', async (req, res) => {
    try {
        const { userAddress } = req.body;

        if (!userAddress) {
            return res.status(400).json({ error: 'Missing userAddress parameter' });
        }

        console.log(`📝 Received add-to-blacklist request: ${userAddress}`);

        const result = await addToBlacklist(userAddress);

        res.json({
            success: true,
            message: 'Added to blacklist',
            data: result
        });

    } catch (error) {
        console.error('API error:', error);
        res.status(500).json({
            success: false,
            error: 'Add-to-blacklist failed',
            details: error.message
        });
    }
});

// Health check
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', message: 'Server is up' });
});

// Start server
app.listen(PORT, () => {
    console.log(`🚀 Server listening on port ${PORT}`);
    console.log(`📱 Frontend: http://localhost:${PORT}/index.html`);
    console.log(`🔧 API: http://localhost:${PORT}/api/add-to-blacklist`);
});
