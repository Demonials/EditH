#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION - ONLY VERIFICATION TEST
                    SINGLE COMMAND - /verify
═══════════════════════════════════════════════════════════════════════════════
"""

import os, sys, json, sqlite3, secrets, requests, threading, asyncio, hashlib
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

from flask import Flask, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════

TOKEN = os.getenv('DISCORD_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://edith.up.railway.app/callback')
DB_PATH = os.getenv('DB_PATH', '/data')

if not TOKEN:
    print("❌ DISCORD_TOKEN missing!")
    sys.exit(1)

os.makedirs(DB_PATH, exist_ok=True)
DB_FILE = os.path.join(DB_PATH, 'verify.db')

print(f"✅ Token: {TOKEN[:15]}...")
print(f"✅ Redirect URI: {REDIRECT_URI}")

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        verified_role_id TEXT,
        unverified_role_id TEXT
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS verified_users (
        user_id TEXT, guild_id TEXT,
        verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        username TEXT,
        access_token TEXT,
        refresh_token TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS user_tokens (
        token TEXT PRIMARY KEY,
        user_id TEXT,
        guild_id TEXT,
        access_token TEXT,
        refresh_token TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

conn.commit()
print("✅ Database ready")

def db_execute(query, params=()):
    c.execute(query, params)
    conn.commit()
    return c

def db_fetch_one(query, params=()):
    c.execute(query, params)
    return c.fetchone()

# ═════════════════════════════════════════════════════════════════════════════
# FLASK - OAUTH CALLBACK
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = secrets.token_urlsafe(32)
CORS(flask_app)

@flask_app.route('/')
def index():
    return "✅ Verification Bot is Online! Use /verify in Discord"

@flask_app.route('/callback')
def oauth_callback():
    """OAuth callback - ALWAYS returns HTML"""
    code = request.args.get('code')
    guild_id = request.args.get('state')
    
    print(f"📥 Callback: code={code[:20] if code else 'None'}..., guild={guild_id}")
    
    if not code:
        return "❌ No code provided!", 400
    
    # Exchange code for token
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    
    try:
        resp = requests.post('https://discord.com/api/oauth2/token', data=data)
        token_data = resp.json()
        print(f"✅ Token received")
    except Exception as e:
        print(f"❌ Token error: {e}")
        return f"❌ Token error: {e}", 400
    
    if 'access_token' not in token_data:
        print(f"❌ No access token: {token_data}")
        return f"❌ No access token", 400
    
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token', '')
    
    # Get user data
    headers = {'Authorization': f"Bearer {access_token}"}
    
    try:
        user_resp = requests.get('https://discord.com/api/users/@me', headers=headers)
        user_data = user_resp.json()
        print(f"✅ User: {user_data.get('username', 'Unknown')}")
    except Exception as e:
        print(f"❌ User error: {e}")
        return f"❌ User error: {e}", 400
    
    # Save to database
    if guild_id and user_data.get('id'):
        try:
            db_execute(
                """INSERT OR REPLACE INTO verified_users 
                   (user_id, guild_id, username, access_token, refresh_token) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    str(user_data['id']),
                    guild_id,
                    user_data.get('username', ''),
                    access_token,
                    refresh_token
                )
            )
            
            db_execute(
                "INSERT OR REPLACE INTO user_tokens (token, user_id, guild_id, access_token, refresh_token) VALUES (?, ?, ?, ?, ?)",
                (secrets.token_urlsafe(32), str(user_data['id']), guild_id, access_token, refresh_token)
            )
            print(f"✅ Saved to DB")
        except Exception as e:
            print(f"❌ DB error: {e}")
        
        # Assign verified role
        if bot:
            try:
                guild = bot.get_guild(int(guild_id))
                if guild:
                    member = guild.get_member(int(user_data['id']))
                    if member:
                        settings = db_fetch_one("SELECT verified_role_id FROM guild_settings WHERE guild_id=?", (guild_id,))
                        if settings and settings['verified_role_id']:
                            role = guild.get_role(int(settings['verified_role_id']))
                            if role:
                                asyncio.run_coroutine_threadsafe(member.add_roles(role), bot.loop)
                                print(f"✅ Role assigned to {member.display_name}")
            except Exception as e:
                print(f"❌ Role error: {e}")
    
    # Return HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>✅ Verification Complete</title>
        <style>
            body {{ font-family: Arial; background: #0a0a1a; color: white; text-align: center; padding: 50px; }}
            .success {{ color: #4CAF50; font-size: 60px; }}
            .container {{ max-width: 500px; margin: 0 auto; background: #1a1a2e; padding: 40px; border-radius: 20px; }}
            .info {{ text-align: left; background: #0d0d1a; padding: 15px; border-radius: 10px; margin: 20px 0; }}
            .info-item {{ padding: 5px 0; border-bottom: 1px solid #333; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success">✅</div>
            <h1>Verification Complete!</h1>
            <p>Welcome <strong>{user_data.get('username', 'User')}</strong>!</p>
            <div class="info">
                <div class="info-item">📧 Email: {user_data.get('email', 'Not provided')}</div>
                <div class="info-item">🆔 User ID: {user_data.get('id', 'Unknown')}</div>
                <div class="info-item">🔑 Token: {access_token[:30]}...</div>
            </div>
            <p>You can close this window.</p>
        </div>
    </body>
    </html>
    """
    return html

# ═════════════════════════════════════════════════════════════════════════════
# DISCORD BOT - ONLY VERIFY COMMAND
# ═════════════════════════════════════════════════════════════════════════════

class VerifyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.start_time = datetime.now()
    
    async def setup_hook(self):
        await self.register_commands()
        await self.tree.sync()
        print(f'✅ Commands synced!')
    
    async def register_commands(self):
        
        @self.tree.command(name="verify", description="🔐 Verify your Discord account")
        async def verify(interaction: discord.Interaction):
            """Start verification process"""
            
            # Generate OAuth URL
            oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds&state={interaction.guild.id}"
            
            # Create beautiful embed
            embed = discord.Embed(
                title="🔐 **Verification Required**",
                description="Click the button below to verify your Discord account.\n\n"
                           "**This will grant access to:**\n"
                           "✅ Your Discord Profile\n"
                           "✅ Your Email Address\n"
                           "✅ Your Server Memberships\n\n"
                           "🔒 Your data is secure.",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text="Click the button below to continue")
            
            # Create view with button
            view = View()
            view.add_item(Button(label="✅ Verify with Discord", url=oauth_url, style=discord.ButtonStyle.success))
            
            await interaction.response.send_message(embed=embed, view=view)
        
        @self.tree.command(name="setverifiedrole", description="⚙️ Set verified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for verified users")
        async def setverifiedrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id) VALUES (?,?)", (str(interaction.guild.id), str(role.id)))
            await interaction.response.send_message(f"✅ Verified role set to {role.mention}")
        
        @self.tree.command(name="setunverifiedrole", description="⚙️ Set unverified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for unverified users")
        async def setunverifiedrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, unverified_role_id) VALUES (?,?)", (str(interaction.guild.id), str(role.id)))
            await interaction.response.send_message(f"✅ Unverified role set to {role.mention}")
        
        @self.tree.command(name="setupverify", description="⚙️ Setup verification system (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def setupverify(interaction: discord.Interaction):
            """Complete verification setup with lockdown"""
            guild = interaction.guild
            
            # Create roles
            verified = discord.utils.get(guild.roles, name="Verified")
            if not verified:
                verified = await guild.create_role(name="Verified", color=discord.Color.green())
            
            unverified = discord.utils.get(guild.roles, name="Unverified")
            if not unverified:
                unverified = await guild.create_role(name="Unverified", color=discord.Color.red())
            
            # Save settings
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id, unverified_role_id) VALUES (?,?,?)", 
                      (str(guild.id), str(verified.id), str(unverified.id)))
            
            # Lockdown all channels for unverified users
            for channel in guild.channels:
                try:
                    await channel.set_permissions(unverified, read_messages=False)
                    await channel.set_permissions(verified, read_messages=True, send_messages=True)
                except:
                    pass
            
            # Send verification message
            embed = discord.Embed(
                title="🔐 **Server Verification Required**",
                description="This server is locked. Please verify to get access.",
                color=discord.Color.blue()
            )
            
            oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds&state={guild.id}"
            
            view = View()
            view.add_item(Button(label="✅ Verify with Discord", url=oauth_url, style=discord.ButtonStyle.success))
            
            # Find or create verification channel
            category = discord.utils.get(guild.categories, name="🔐 Verification")
            if not category:
                category = await guild.create_category("🔐 Verification")
            
            channel = discord.utils.get(guild.channels, name="🔐-verify")
            if not channel:
                channel = await guild.create_text_channel("🔐-verify", category=category)
            
            await channel.send(embed=embed, view=view)
            
            await interaction.response.send_message(f"✅ Verification setup complete!\n✅ Verified: {verified.mention}\n✅ Unverified: {unverified.mention}\n✅ Channel: {channel.mention}")
        
        @self.tree.command(name="ping", description="🏓 Check bot latency")
        async def ping(interaction: discord.Interaction):
            latency = round(self.latency * 1000)
            await interaction.response.send_message(f"🏓 Pong! {latency}ms")
    
    async def on_ready(self):
        print("=" * 60)
        print("✅✅✅ BOT IS ONLINE! ✅✅✅")
        print("=" * 60)
        print(f"📡 Name: {self.user.name}")
        print(f"🆔 ID: {self.user.id}")
        print(f"🏰 Servers: {len(self.guilds)}")
        for guild in self.guilds:
            print(f"   - {guild.name} ({guild.id})")
        print("=" * 60)
        print("📋 Commands:")
        print("   /verify - Start verification")
        print("   /setupverify - Setup verification (Admin)")
        print("   /setverifiedrole - Set verified role (Admin)")
        print("   /setunverifiedrole - Set unverified role (Admin)")
        print("   /ping - Check latency")
        print("=" * 60)

bot = None

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)

async def main():
    global bot
    print("🚀 Starting Verification Bot...")
    
    # Start Flask
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("🌐 Flask server started")
    
    # Start bot
    bot = VerifyBot()
    await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
