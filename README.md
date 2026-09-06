# EDITH Bot - Ultimate Discord Management Bot

## Features
- 🔐 Verification System
- 🎫 Ticket System
- 🎁 Giveaway System
- 🛡️ Moderation System
- 👑 Role Management

## Deployment on Railway

1. **Fork/Clone this repository to GitHub**

2. **Get Discord Bot Token:**
   - Go to https://discord.com/developers/applications
   - Create new application
   - Go to Bot tab → Create Bot
   - Copy token

3. **Deploy on Railway:**
   - Go to https://railway.app
   - New Project → Deploy from GitHub repo
   - Select your repository

4. **Add Environment Variables in Railway:**
   - DISCORD_TOKEN
   - CLIENT_ID
   - CLIENT_SECRET
   - WEBSITE_URL

5. **Invite Bot to Server:**
   - Discord Developer Portal → OAuth2 → URL Generator
   - Select bot and administrator permissions
   - Use generated URL to invite

## Commands
- `!setup` - Setup all systems (Admin only)
- `!verify` - Start verification
- `!confirm <code>` - Complete verification
- `!ping` - Check bot status
- `!help` - Show commands

## Support
For issues, create a GitHub issue or contact support.
