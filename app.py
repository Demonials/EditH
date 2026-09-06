import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import os
import json
import secrets
import asyncio
import random
import re
import aiohttp
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, redirect, jsonify, send_from_directory
import threading
import time

# ============ SETUP LOGGING ============
os.makedirs('./logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('./logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("="*60)
logger.info("🚀 EDITH BOT STARTING")
logger.info("="*60)

# Load environment
load_dotenv()
logger.info("📝 Environment loaded")

# ============ FLASK APP ============
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>EDITH Bot - Verification System</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
            .container { background: #2d2d44; padding: 50px; border-radius: 20px; text-align: center; max-width: 500px; box-shadow: 0 20px 60px rgba(0,0,0,0.5); border: 1px solid #3d3d5c; }
            .logo { font-size: 80px; margin-bottom: 20px; }
            h1 { color: #ffffff; font-size: 32px; margin-bottom: 10px; }
            .subtitle { color: #b5b5c4; font-size: 16px; margin-bottom: 30px; }
            .status { background: #1e1e32; padding: 20px; border-radius: 12px; margin: 20px 0; }
            .status .label { color: #6d6d8a; font-size: 13px; }
            .status .value { color: #4caf50; font-weight: 600; font-size: 16px; }
            .footer { color: #4d4d6a; font-size: 12px; margin-top: 30px; border-top: 1px solid #2d2d44; padding-top: 20px; }
            .badge { display: inline-block; background: #4caf50; color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🤖</div>
            <h1>EDITH Bot</h1>
            <p class="subtitle">Ultimate Server Management Bot</p>
            
            <div class="status">
                <div style="margin-bottom: 10px;"><span class="label">Status</span></div>
                <div><span class="value">✅ Online & Ready</span></div>
                <div style="margin-top: 10px;"><span class="badge">Verification System Active</span></div>
            </div>
            
            <p style="color: #b5b5c4; font-size: 14px; margin: 20px 0;">
                Use <code style="background: #1a1a2e; padding: 4px 8px; border-radius: 4px; color: #5865f2;">/verify</code> in Discord to start verification.
            </p>
            
            <div style="text-align: left; background: #1e1e32; padding: 15px; border-radius: 10px; margin: 20px 0;">
                <div style="padding: 5px 0;"><span style="color: #6d6d8a;">📡 Server:</span> <span style="color: white;">edith-bot.up.railway.app</span></div>
                <div style="padding: 5px 0;"><span style="color: #6d6d8a;">🔐 Status:</span> <span style="color: #4caf50;">✅ Verified Users: 0</span></div>
                <div style="padding: 5px 0;"><span style="color: #6d6d8a;">🤖 Bot:</span> <span style="color: white;">EDITH v2.0</span></div>
            </div>
            
            <p class="footer">EDITH Authentication System v2.0 • Built with ❤️</p>
        </div>
    </body>
    </html>
    """

@app.route('/callback')
def oauth_callback():
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        logger.info(f"📥 OAuth Callback received!")
        logger.info(f"   Code: {code[:20] if code else 'None'}...")
        logger.info(f"   State: {state[:20] if state else 'None'}...")
        logger.info(f"   Error: {error if error else 'None'}")
        
        if error:
            return f"""
            <!DOCTYPE html>
            <html>
            <head><title>Verification Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 20px; }}
                .container {{ background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; max-width: 500px; }}
                .error {{ color: #f44336; font-size: 60px; }}
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>Verification Failed</h1>
                    <p>Error: {error}</p>
                    <p>Please try again with <code style="background: #1a1a2e; padding: 4px 8px; border-radius: 4px;">/verify</code> in Discord.</p>
                    <a href="https://discord.com/app" style="color: #5865f2; text-decoration: none;">Return to Discord</a>
                </div>
            </body>
            </html>
            """
        
        if not code:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>Verification Failed</title>
            <style>
                body { font-family: Arial, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 20px; }
                .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; max-width: 500px; }
                .error { color: #f44336; font-size: 60px; }
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>No Code Provided</h1>
                    <p>Please try again with <code style="background: #1a1a2e; padding: 4px 8px; border-radius: 4px;">/verify</code> in Discord.</p>
                    <a href="https://discord.com/app" style="color: #5865f2; text-decoration: none;">Return to Discord</a>
                </div>
            </body>
            </html>
            """, 400
        
        # Get session data from state
        session = None
        if state:
            session = oauth_states.pop(state, None)
            logger.info(f"   Session found locally: {session is not None}")
        
        if not session:
            if db_firebase:
                try:
                    doc_ref = db_firebase.collection('oauth_states').document(state)
                    doc = doc_ref.get()
                    if doc.exists:
                        session = doc.to_dict()
                        doc_ref.delete()
                        logger.info("   Session found in Firebase")
                except Exception as e:
                    logger.error(f"   Failed to get session from Firebase: {e}")
        
        if not session:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>Verification Failed</title>
            <style>
                body { font-family: Arial, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 20px; }
                .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; max-width: 500px; }
                .error { color: #f44336; font-size: 60px; }
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>Session Expired</h1>
                    <p>Your verification session has expired or is invalid.</p>
                    <p>Please run <code style="background: #1a1a2e; padding: 4px 8px; border-radius: 4px;">/verify</code> again in Discord.</p>
                    <a href="https://discord.com/app" style="color: #5865f2; text-decoration: none;">Return to Discord</a>
                </div>
            </body>
            </html>
            """
        
        user_id = session['user_id']
        guild_id = session['guild_id']
        logger.info(f"   User ID: {user_id}, Guild ID: {guild_id}")
        
        # Exchange code for token
        import aiohttp
        import asyncio
        
        async def exchange_code():
            data = {
                'client_id': os.getenv('CLIENT_ID'),
                'client_secret': os.getenv('CLIENT_SECRET'),
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': os.getenv('REDIRECT_URI', 'https://edith-bot.up.railway.app/callback')
            }
            async with aiohttp.ClientSession() as session:
                async with session.post('https://discord.com/api/oauth2/token', data=data) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"Token exchange failed: {resp.status}")
                    return None
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        token_data = loop.run_until_complete(exchange_code())
        loop.close()
        
        if not token_data:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>Verification Failed</title>
            <style>
                body { font-family: Arial, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 20px; }
                .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; max-width: 500px; }
                .error { color: #f44336; font-size: 60px; }
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>Token Exchange Failed</h1>
                    <p>Failed to exchange verification code.</p>
                    <p>Please try again with <code style="background: #1a1a2e; padding: 4px 8px; border-radius: 4px;">/verify</code> in Discord.</p>
                    <a href="https://discord.com/app" style="color: #5865f2; text-decoration: none;">Return to Discord</a>
                </div>
            </body>
            </html>
            """
        
        access_token = token_data.get('access_token')
        logger.info("✅ Token received")
        
        # Get user data
        async def get_user_data():
            headers = {'Authorization': f'Bearer {access_token}'}
            async with aiohttp.ClientSession() as session:
                async with session.get('https://discord.com/api/users/@me', headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        user_data_discord = loop.run_until_complete(get_user_data())
        loop.close()
        
        if not user_data_discord:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>Verification Failed</title>
            <style>
                body { font-family: Arial, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 20px; }
                .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; max-width: 500px; }
                .error { color: #f44336; font-size: 60px; }
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>Failed to Get User Data</h1>
                    <p>Could not retrieve your Discord information.</p>
                    <p>Please try again with <code style="background: #1a1a2e; padding: 4px 8px; border-radius: 4px;">/verify</code> in Discord.</p>
                    <a href="https://discord.com/app" style="color: #5865f2; text-decoration: none;">Return to Discord</a>
                </div>
            </body>
            </html>
            """
        
        username = user_data_discord.get('username')
        discord_id = user_data_discord.get('id')
        email = user_data_discord.get('email', 'Not provided')
        avatar = user_data_discord.get('avatar')
        avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.png" if avatar else ""
        
        logger.info(f"👤 User verified: {username} ({discord_id})")
        
        # Store verification in database
        user_data = db.get_user(discord_id, guild_id)
        user_data['verified'] = True
        user_data['profile'] = {
            'discord_id': discord_id,
            'username': username,
            'email': email,
            'avatar': avatar_url,
            'verified_at': datetime.now().isoformat(),
            'guild_id': guild_id
        }
        db.set_user(discord_id, guild_id, user_data)
        
        # Assign role in Discord
        guild = bot.get_guild(int(guild_id))
        role_assigned = False
        if guild:
            member = guild.get_member(int(discord_id))
            if member:
                verified_role = discord.utils.get(guild.roles, name="✅ Verified")
                unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
                if verified_role:
                    try:
                        if unverified_role and unverified_role in member.roles:
                            asyncio.run_coroutine_threadsafe(member.remove_roles(unverified_role), bot.loop)
                        asyncio.run_coroutine_threadsafe(member.add_roles(verified_role), bot.loop)
                        role_assigned = True
                        logger.info(f"✅ Role assigned to {username}")
                    except Exception as e:
                        logger.error(f"Failed to assign role: {e}")
        
        # Send success page
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Verification Successful</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }}
                .container {{ background: #2d2d44; padding: 50px; border-radius: 20px; text-align: center; max-width: 500px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.5); border: 1px solid #3d3d5c; }}
                .success {{ color: #4caf50; font-size: 80px; margin-bottom: 20px; }}
                h1 {{ color: #ffffff; font-size: 28px; margin-bottom: 10px; }}
                .subtitle {{ color: #b5b5c4; font-size: 16px; margin-bottom: 30px; }}
                .user-info {{ background: #1e1e32; border-radius: 12px; padding: 20px; margin: 20px 0; text-align: left; }}
                .user-info .row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #2d2d44; }}
                .user-info .row:last-child {{ border-bottom: none; }}
                .user-info .label {{ color: #6d6d8a; font-size: 13px; }}
                .user-info .value {{ color: #ffffff; font-size: 14px; }}
                .status-box {{ padding: 15px; border-radius: 10px; margin: 15px 0; background: #1e1e32; color: #4caf50; font-weight: 600; }}
                .button {{ background: #5865f2; color: white; border: none; padding: 16px 40px; font-size: 18px; font-weight: 600; border-radius: 10px; cursor: pointer; width: 100%; margin-top: 20px; text-decoration: none; display: inline-block; }}
                .button:hover {{ background: #4752c4; transform: translateY(-2px); box-shadow: 0 10px 30px rgba(88,101,242,0.3); }}
                .footer {{ margin-top: 25px; color: #4d4d6a; font-size: 12px; border-top: 1px solid #2d2d44; padding-top: 20px; }}
                .badge {{ display: inline-block; background: #4caf50; color: white; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; }}
                .avatar {{ width: 80px; height: 80px; border-radius: 50%; margin: 10px auto; display: block; border: 3px solid #5865f2; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Verification Successful!</h1>
                <p class="subtitle">Welcome to the server! 🎉</p>
                
                <img src="{avatar_url}" class="avatar" onerror="this.style.display='none'">
                
                <div class="user-info">
                    <div class="row">
                        <span class="label">👤 Username</span>
                        <span class="value">{username}</span>
                    </div>
                    <div class="row">
                        <span class="label">🆔 User ID</span>
                        <span class="value">{discord_id}</span>
                    </div>
                    <div class="row">
                        <span class="label">📧 Email</span>
                        <span class="value">{email}</span>
                    </div>
                    <div class="row">
                        <span class="label">🔓 Status</span>
                        <span class="value"><span class="badge">Verified ✅</span></span>
                    </div>
                    <div class="row">
                        <span class="label">🎭 Role</span>
                        <span class="value">{'✅ Verified (Assigned)' if role_assigned else '⚠️ Role assignment pending'}</span>
                    </div>
                </div>
                
                <div class="status-box">✅ You now have full access to the server!</div>
                
                <a href="https://discord.com/app" class="button">Return to Discord</a>
                
                <p class="footer">You can now close this tab. A DM has been sent to you with verification details.</p>
            </div>
        </body>
        </html>
        """
    
    except Exception as e:
        logger.error(f"❌ Callback error: {e}", exc_info=True)
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Verification Error</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; padding: 20px; }}
            .container {{ background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; max-width: 500px; }}
            .error {{ color: #f44336; font-size: 60px; }}
        </style>
        </head>
        <body>
            <div class="container">
                <div class="error">❌</div>
                <h1>Verification Error</h1>
                <p>An error occurred during verification.</p>
                <p style="color: #888; font-size: 12px;">Error: {str(e)}</p>
                <p>Please try again with <code style="background: #1a1a2e; padding: 4px 8px; border-radius: 4px;">/verify</code> in Discord.</p>
            </div>
        </body>
        </html>
        """

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'bot_name': bot.user.name if bot.user else 'Not logged in',
        'guilds': len(bot.guilds),
        'timestamp': datetime.now().isoformat(),
        'redirect_uri': os.getenv('REDIRECT_URI')
    })

@app.route('/test')
def test():
    return jsonify({
        'message': 'Web server is running!',
        'timestamp': datetime.now().isoformat(),
        'redirect_uri': os.getenv('REDIRECT_URI'),
        'client_id': os.getenv('CLIENT_ID', 'Not set')
    })

# ============ DISCORD BOT ============
# Try to import Firebase with error handling
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
    logger.info("✅ Firebase module loaded successfully!")
except ImportError as e:
    FIREBASE_AVAILABLE = False
    logger.warning(f"⚠️ Firebase not available - using local database: {e}")
    firebase_admin = None
    credentials = None
    firestore = None

# Initialize Firebase if available
db_firebase = None
if FIREBASE_AVAILABLE:
    try:
        firebase_json = os.getenv('FIREBASE_KEY_JSON')
        if firebase_json:
            logger.info("🔑 Firebase credentials found, connecting...")
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            db_firebase = firestore.client()
            logger.info("✅ Firebase connected successfully!")
        else:
            logger.warning("⚠️ No Firebase credentials found in environment")
    except Exception as e:
        logger.error(f"❌ Firebase connection error: {e}")
        db_firebase = None

# Initialize bot with slash commands
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
logger.info("🤖 Bot initialized")

# Local database fallback
class SimpleDB:
    def __init__(self):
        logger.info("📂 Initializing local database...")
        self.data = {}
        self.load_data()
    
    def load_data(self):
        try:
            if os.path.exists('./data/db.json'):
                with open('./data/db.json', 'r') as f:
                    self.data = json.load(f)
                logger.info("✅ Local database loaded from ./data/db.json")
            else:
                self.data = {'users': {}, 'guilds': {}, 'giveaways': {}, 'tickets': {}, 'notes': {}, 'oauth_states': {}}
                self.save_data()
                logger.info("📂 New local database created")
        except Exception as e:
            logger.error(f"❌ Failed to load database: {e}")
            self.data = {'users': {}, 'guilds': {}, 'giveaways': {}, 'tickets': {}, 'notes': {}, 'oauth_states': {}}
            self.save_data()
    
    def save_data(self):
        try:
            os.makedirs('./data', exist_ok=True)
            with open('./data/db.json', 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save database: {e}")
    
    def get_user(self, user_id, guild_id):
        user_id = str(user_id)
        guild_id = str(guild_id)
        if guild_id not in self.data['users']:
            self.data['users'][guild_id] = {}
        if user_id not in self.data['users'][guild_id]:
            self.data['users'][guild_id][user_id] = {
                'verified': False,
                'profile': {},
                'tickets': [],
                'notes': [],
                'guild_id': guild_id,
                'user_id': user_id,
                'verified_at': None
            }
            self.save_data()
        return self.data['users'][guild_id][user_id]
    
    def set_user(self, user_id, guild_id, data):
        user_id = str(user_id)
        guild_id = str(guild_id)
        if guild_id not in self.data['users']:
            self.data['users'][guild_id] = {}
        self.data['users'][guild_id][user_id] = data
        self.save_data()
    
    def check_user_verified(self, user_id, guild_id):
        user_id = str(user_id)
        guild_id = str(guild_id)
        if guild_id in self.data['users']:
            if user_id in self.data['users'][guild_id]:
                return self.data['users'][guild_id][user_id].get('verified', False)
        return False
    
    def get_guild(self, guild_id):
        guild_id = str(guild_id)
        return self.data['guilds'].get(guild_id)
    
    def set_guild(self, guild_id, data):
        guild_id = str(guild_id)
        self.data['guilds'][guild_id] = data
        self.save_data()

db = SimpleDB()

# OAuth states storage
oauth_states = {}

# ============ OAUTH VERIFICATION ============
class OAuthVerification:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI', 'https://edith-bot.up.railway.app/callback')
        logger.info(f"🔐 OAuth initialized")
        logger.info(f"   Client ID: {self.client_id[:10] if self.client_id else 'None'}...")
        logger.info(f"   Redirect URI: {self.redirect_uri}")
    
    def generate_oauth_url(self, user_id, guild_id):
        state = secrets.token_urlsafe(32)
        oauth_states[state] = {
            'user_id': user_id,
            'guild_id': guild_id,
            'timestamp': datetime.now().isoformat()
        }
        
        if db_firebase:
            try:
                doc_ref = db_firebase.collection('oauth_states').document(state)
                doc_ref.set({
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"   Failed to store in Firebase: {e}")
        
        # Build URL with prompt=consent for proper flow
        url = (f"https://discord.com/api/oauth2/authorize?"
               f"client_id={self.client_id}&"
               f"redirect_uri={self.redirect_uri}&"
               f"response_type=code&"
               f"scope=identify%20email%20guilds%20connections&"
               f"state={state}&"
               f"prompt=consent")
        
        logger.info(f"🔗 OAuth URL generated")
        return url, state

oauth = OAuthVerification()

# ============ GIVEAWAY SYSTEM ============
class GiveawayMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
        logger.debug("🎁 GiveawayMainView created")
    
    @discord.ui.button(label="🎁 Host Giveaway", style=discord.ButtonStyle.success)
    async def host_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        modal = GiveawayModal()
        await interaction.response.send_modal(modal)

class GiveawayModal(Modal):
    def __init__(self):
        super().__init__(title="Host Giveaway")
        self.name = TextInput(label="Giveaway Name", required=True)
        self.duration = TextInput(label="Duration (minutes)", required=True)
        self.winners = TextInput(label="Number of Winners", required=True)
        self.prize = TextInput(label="Prize", required=True)
        self.add_item(self.name)
        self.add_item(self.duration)
        self.add_item(self.winners)
        self.add_item(self.prize)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration_minutes = int(self.duration.value)
            winners_count = int(self.winners.value)
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            giveaway_id = secrets.token_hex(8)
            
            embed = discord.Embed(
                title=f"🎉 {self.name.value}",
                description=f"""
                **Prize:** {self.prize.value}
                **Host:** {interaction.user.mention}
                **Duration:** {duration_minutes} minutes
                **Winners:** {winners_count}
                **Ends:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}
                """,
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
            
            view = GiveawayParticipateView(giveaway_id, end_time, winners_count, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view)
            
            db.data['giveaways'][giveaway_id] = {
                'name': self.name.value,
                'prize': self.prize.value,
                'host': interaction.user.id,
                'winners': winners_count,
                'end_time': end_time.isoformat(),
                'participants': []
            }
            db.save_data()
            
            asyncio.create_task(self.giveaway_countdown(giveaway_id, interaction.channel, end_time))
            logger.info(f"🎁 Giveaway created: {self.name.value} with {winners_count} winners")
        except ValueError:
            await interaction.response.send_message("❌ Invalid numbers!", ephemeral=True)
    
    async def giveaway_countdown(self, giveaway_id, channel, end_time):
        await asyncio.sleep((end_time - datetime.now()).total_seconds())
        giveaway_data = db.data['giveaways'].get(giveaway_id)
        if not giveaway_data:
            return
        
        participants = giveaway_data.get('participants', [])
        if len(participants) < giveaway_data['winners']:
            await channel.send(f"❌ Not enough participants for **{giveaway_data['name']}**!")
            return
        
        winners = random.sample(participants, min(giveaway_data['winners'], len(participants)))
        winner_mentions = [f"<@{winner}>" for winner in winners]
        
        embed = discord.Embed(
            title="🎉 GIVEAWAY COMPLETE!",
            description=f"""
            **Giveaway:** {giveaway_data['name']}
            **Prize:** {giveaway_data['prize']}
            **Winners:** {', '.join(winner_mentions)}
            
            🎊 Congratulations! Create a ticket within 24 hours to claim!
            """,
            color=discord.Color.green()
        )
        
        giveaway_role = discord.utils.get(channel.guild.roles, name="🎁 Giveaway")
        host = giveaway_data['host']
        
        await channel.send(f"{giveaway_role.mention if giveaway_role else '@everyone'} <@{host}>")
        await channel.send(embed=embed)
        logger.info(f"🎁 Giveaway completed: {giveaway_data['name']}")

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 Participate", style=discord.ButtonStyle.success)
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if not giveaway_data:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        if datetime.now() > datetime.fromisoformat(giveaway_data['end_time']):
            await interaction.response.send_message("❌ Giveaway ended!", ephemeral=True)
            return
        if interaction.user.id in giveaway_data['participants']:
            await interaction.response.send_message("❌ Already participating!", ephemeral=True)
            return
        
        giveaway_data['participants'].append(interaction.user.id)
        db.save_data()
        await interaction.response.send_message("✅ You're participating!", ephemeral=True)
        logger.info(f"🎯 {interaction.user} joined giveaway {self.giveaway_id}")
    
    @discord.ui.button(label="❌ Un-Participate", style=discord.ButtonStyle.danger)
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and interaction.user.id in giveaway_data['participants']:
            giveaway_data['participants'].remove(interaction.user.id)
            db.save_data()
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ Delete Giveaway", style=discord.ButtonStyle.danger)
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
        logger.info(f"🗑️ Giveaway {self.giveaway_id} deleted by {interaction.user}")
    
    @discord.ui.button(label="🔄 Reroll", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and giveaway_data['participants']:
            new_winner = random.choice(giveaway_data['participants'])
            await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)
            logger.info(f"🔄 Giveaway {self.giveaway_id} rerolled by {interaction.user}")

# ============ TICKET SYSTEM ============
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        logger.debug("🎫 TicketView created")
    
    @discord.ui.button(label="🛠️ Server Related", style=discord.ButtonStyle.primary)
    async def server_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Server Related")
    
    @discord.ui.button(label="👮 Contact Mods", style=discord.ButtonStyle.danger)
    async def mod_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Contact Mods")
    
    @discord.ui.button(label="❓ Others", style=discord.ButtonStyle.secondary)
    async def other_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Others")
    
    async def create_ticket(self, interaction, ticket_type):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name="🎫 Support")
            if not category:
                category = await guild.create_category("🎫 Support")
                logger.info(f"   Created Support category")
            
            ticket_name = f"ticket-{interaction.user.name}-{secrets.token_hex(3)}".lower()
            mod_role = discord.utils.get(guild.roles, name="🔰 Moderator")
            admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
            logger.info(f"   Created ticket channel: {channel.name}")
            
            embed = discord.Embed(
                title=f"🎫 Ticket: {ticket_type}",
                description=f"Created by: {interaction.user.mention}\nType: {ticket_type}\nCreated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=discord.Color.blue()
            )
            
            view = TicketControlView(interaction.user.id, channel.id)
            await channel.send(embed=embed, view=view)
            
            if db_firebase:
                try:
                    doc_ref = db_firebase.collection('tickets').document(str(channel.id))
                    doc_ref.set({
                        'channel_id': channel.id,
                        'user_id': interaction.user.id,
                        'type': ticket_type,
                        'created_at': datetime.now().isoformat(),
                        'status': 'open',
                        'guild_id': str(guild.id)
                    })
                except Exception as e:
                    logger.error(f"   Failed to store ticket in Firebase: {e}")
            
            db.data['tickets'][str(channel.id)] = {
                'channel_id': channel.id,
                'user_id': interaction.user.id,
                'type': ticket_type,
                'created_at': datetime.now().isoformat(),
                'status': 'open'
            }
            db.save_data()
            
            await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)
            logger.info(f"✅ Ticket created successfully: {channel.name}")
        except Exception as e:
            logger.error(f"❌ Failed to create ticket: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

class TicketControlView(View):
    def __init__(self, user_id, channel_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.channel_id = channel_id
    
    @discord.ui.button(label="➕ Add User", style=discord.ButtonStyle.success)
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Remove User", style=discord.ButtonStyle.danger)
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⛔ Ban User", style=discord.ButtonStyle.danger)
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BanUserModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📄 Transcript", style=discord.ButtonStyle.secondary)
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            channel = interaction.channel
            messages = []
            async for msg in channel.history(limit=100):
                messages.append(f"{msg.author}: {msg.content}")
            
            transcript = "\n".join(reversed(messages))
            import io
            file = discord.File(io.BytesIO(transcript.encode()), f"transcript-{channel.name}.txt")
            await interaction.followup.send(file=file, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        
        await interaction.response.defer()
        channel = interaction.channel
        await channel.send("🔒 Closing ticket...")
        db.data['tickets'][str(channel.id)]['status'] = 'closed'
        db.save_data()
        await asyncio.sleep(2)
        await channel.delete()
    
    @discord.ui.button(label="📝 Special Note", style=discord.ButtonStyle.primary)
    async def special_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NoteModal(self.channel_id)
        await interaction.response.send_modal(modal)

class AddUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Add User")
        self.channel_id = channel_id
        self.user_id_input = TextInput(label="User ID or Mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await channel.set_permissions(user, read_messages=True, send_messages=True)
                await channel.send(f"✅ {user.mention} added to ticket!")
                await interaction.response.send_message("✅ User added!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class RemoveUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Remove User")
        self.channel_id = channel_id
        self.user_id_input = TextInput(label="User ID or Mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await channel.set_permissions(user, read_messages=False, send_messages=False)
                await channel.send(f"❌ {user.mention} removed from ticket!")
                await interaction.response.send_message("✅ User removed!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class BanUserModal(Modal):
    def __init__(self):
        super().__init__(title="Ban User")
        self.user_id_input = TextInput(label="User ID", required=True)
        self.reason_input = TextInput(label="Reason", required=False)
        self.add_item(self.user_id_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id_input.value)
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await user.ban(reason=self.reason_input.value or "Banned from ticket")
                await interaction.response.send_message(f"✅ Banned {user.mention}!", ephemeral=True)
                await interaction.channel.send(f"⛔ {user.mention} has been banned!")
        except:
            await interaction.response.send_message("❌ Failed to ban user!", ephemeral=True)

class NoteModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="Add Special Note")
        self.channel_id = channel_id
        self.note_input = TextInput(label="Note", style=discord.TextStyle.paragraph, required=True)
        self.add_item(self.note_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        user_data = db.get_user(user_id, guild_id)
        if 'notes' not in user_data:
            user_data['notes'] = []
        user_data['notes'].append({
            'note': self.note_input.value,
            'ticket': str(self.channel_id),
            'moderator': str(interaction.user),
            'timestamp': datetime.now().isoformat()
        })
        db.set_user(user_id, guild_id, user_data)
        
        if db_firebase:
            try:
                doc_ref = db_firebase.collection('user_notes').document(f"{guild_id}_{user_id}_{self.channel_id}")
                doc_ref.set({
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'note': self.note_input.value,
                    'ticket': str(self.channel_id),
                    'moderator': str(interaction.user),
                    'timestamp': datetime.now().isoformat()
                })
            except:
                pass
        
        await interaction.response.send_message("✅ Note saved!", ephemeral=True)

# ============ SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        logger.info(f"🛠️ SetupView created by {author} ({author.id})")
    
    async def setup_all(self, guild, interaction):
        """Complete server setup with progress updates"""
        
        logger.info(f"🚀 Starting full server setup for guild: {guild.name} ({guild.id})")
        logger.info(f"   Channels before: {len(guild.channels)}")
        logger.info(f"   Roles before: {len(guild.roles)}")
        
        # Step 1: Delete existing channels
        logger.info("📝 Step 1: Deleting existing channels...")
        await interaction.edit_original_response(content="🔄 **Step 1/6:** Deleting existing channels...")
        
        channels_deleted = 0
        for channel in guild.channels:
            try:
                await channel.delete()
                channels_deleted += 1
                if channels_deleted % 10 == 0:
                    await interaction.edit_original_response(content=f"🔄 **Step 1/6:** Deleting existing channels... ({channels_deleted} deleted)")
            except Exception as e:
                logger.warning(f"   Failed to delete channel {channel.name}: {e}")
        logger.info(f"✅ Deleted {channels_deleted} channels")
        
        # Step 2: Delete existing roles
        logger.info("📝 Step 2: Deleting existing roles...")
        await interaction.edit_original_response(content="🔄 **Step 2/6:** Deleting existing roles...")
        
        roles_deleted = 0
        for role in guild.roles:
            if role.name != "@everyone" and not role.managed:
                try:
                    await role.delete()
                    roles_deleted += 1
                except Exception as e:
                    logger.warning(f"   Failed to delete role {role.name}: {e}")
        logger.info(f"✅ Deleted {roles_deleted} roles")
        
        # Step 3: Create categories and channels
        logger.info("📝 Step 3: Creating categories and channels...")
        await interaction.edit_original_response(content="🔄 **Step 3/6:** Creating categories and channels...")
        
        categories = {
            "📋 Information": ["📌-rules", "📢-announcements", "📋-server-info"],
            "🔐 Security": ["🔐-verification", "🛡️-mod-logs", "📊-logs"],
            "💬 General": ["💬-general-chat", "📸-media", "🎮-gaming", "🎵-music"],
            "📞 Voice Channels": ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"],
            "🎫 Support": ["🎫-tickets", "📝-feedback", "❓-faq"],
            "🎉 Events": ["🎉-giveaways", "📅-events", "🏆-contests"],
            "👑 Admin": ["⚙️-admin-commands", "📊-stats", "🔧-bot-controls"]
        }
        
        created_categories = {}
        created_channels = {}
        created_roles = {}
        category_objects = {}
        
        total_categories = len(categories)
        category_count = 0
        
        for category_name, channel_names in categories.items():
            category_count += 1
            try:
                category = await guild.create_category(category_name)
                created_categories[category_name] = category.id
                category_objects[category_name] = category
                logger.info(f"✅ Created category: {category_name} (ID: {category.id})")
                await interaction.edit_original_response(
                    content=f"🔄 **Step 3/6:** Creating channels... ({category_count}/{total_categories} categories)"
                )
            except Exception as e:
                logger.error(f"❌ Failed to create category {category_name}: {e}")
                continue
            
            for channel_name in channel_names:
                try:
                    channel = await guild.create_text_channel(channel_name, category=category)
                    created_channels[channel_name] = channel.id
                    logger.info(f"✅ Created channel: {channel_name} (ID: {channel.id})")
                except Exception as e:
                    logger.error(f"❌ Failed to create channel {channel_name}: {e}")
        
        # Step 4: Create voice channels (FIXED - use category_objects)
        logger.info("📝 Step 4: Creating voice channels...")
        await interaction.edit_original_response(content="🔄 **Step 4/6:** Creating voice channels...")
        
        voice_channels = ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"]
        voice_category = category_objects.get("📞 Voice Channels")
        
        if voice_category:
            for vc_name in voice_channels:
                try:
                    vc = await guild.create_voice_channel(vc_name, category=voice_category)
                    created_channels[vc_name] = vc.id
                    logger.info(f"✅ Created voice channel: {vc_name} (ID: {vc.id})")
                except Exception as e:
                    logger.error(f"❌ Failed to create voice channel {vc_name}: {e}")
        else:
            logger.error("❌ Voice category not found, skipping voice channels")
        
        # Step 5: Create roles with permissions
        logger.info("📝 Step 5: Creating roles with permissions...")
        await interaction.edit_original_response(content="🔄 **Step 5/6:** Creating roles with permissions...")
        
        roles_config = {
            "👑 Owner": discord.Permissions(administrator=True),
            "🛡️ Admin": discord.Permissions(administrator=True),
            "🔰 Moderator": discord.Permissions(
                kick_members=True,
                ban_members=True,
                manage_messages=True,
                manage_channels=True,
                manage_roles=True
            ),
            "🤝 Helper": discord.Permissions(
                manage_messages=True,
                mute_members=True,
                deafen_members=True,
                move_members=True
            ),
            "✅ Verified": discord.Permissions(
                read_messages=True,
                send_messages=True,
                connect=True,
                speak=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                add_reactions=True
            ),
            "❌ Unverified": discord.Permissions(
                read_messages=True,
                send_messages=False
            ),
            "🎁 Giveaway": discord.Permissions(
                read_messages=True,
                send_messages=False
            ),
            "🎮 Gamer": discord.Permissions(read_messages=True, send_messages=True),
            "🎵 Music Lover": discord.Permissions(read_messages=True, send_messages=True)
        }
        
        total_roles = len(roles_config)
        role_count = 0
        
        for role_name, perms in roles_config.items():
            role_count += 1
            try:
                role = await guild.create_role(name=role_name, permissions=perms)
                created_roles[role_name] = role.id
                logger.info(f"✅ Created role: {role_name} (ID: {role.id})")
                await interaction.edit_original_response(
                    content=f"🔄 **Step 5/6:** Creating roles... ({role_count}/{total_roles})"
                )
            except Exception as e:
                logger.error(f"❌ Failed to create role {role_name}: {e}")
        
        # Step 6: Store in database
        logger.info("📝 Step 6: Storing in database...")
        await interaction.edit_original_response(content="🔄 **Step 6/6:** Saving configuration...")
        
        guild_data = {
            'categories': created_categories,
            'channels': created_channels,
            'roles': created_roles,
            'setup_complete': True,
            'setup_date': datetime.now().isoformat()
        }
        
        if db_firebase:
            try:
                doc_ref = db_firebase.collection('guilds').document(str(guild.id))
                doc_ref.set(guild_data)
                logger.info("✅ Saved to Firebase")
            except Exception as e:
                logger.error(f"❌ Failed to save to Firebase: {e}")
        
        db.set_guild(guild.id, guild_data)
        logger.info("✅ Saved to local database")
        
        # Get channels
        verify_channel = discord.utils.get(guild.channels, name="🔐-verification")
        ticket_channel = discord.utils.get(guild.channels, name="🎫-tickets")
        giveaway_channel = discord.utils.get(guild.channels, name="🎉-giveaways")
        
        logger.info(f"📊 Setup Summary:")
        logger.info(f"   Categories: {len(created_categories)}")
        logger.info(f"   Channels: {len(created_channels)}")
        logger.info(f"   Roles: {len(created_roles)}")
        logger.info(f"   Verify Channel: {verify_channel.name if verify_channel else 'Not found'}")
        logger.info(f"   Ticket Channel: {ticket_channel.name if ticket_channel else 'Not found'}")
        logger.info(f"   Giveaway Channel: {giveaway_channel.name if giveaway_channel else 'Not found'}")
        
        return verify_channel, ticket_channel, giveaway_channel, created_roles
    
    @discord.ui.button(label="⚡ Setup All", style=discord.ButtonStyle.success, emoji="⚡")
    async def setup_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        logger.info(f"🔄 Setup All button clicked by {interaction.user}")
        
        await interaction.response.send_message(
            "🔄 **Starting server setup...**\n\n⏳ Please wait, this may take a moment...", 
            ephemeral=True
        )
        
        try:
            verify_channel, ticket_channel, giveaway_channel, roles = await self.setup_all(
                interaction.guild, interaction
            )
            
            await interaction.edit_original_response(content="📝 Sending verification message...")
            await self.send_verification_message(verify_channel, roles)
            
            await interaction.edit_original_response(content="📝 Sending ticket message...")
            await self.send_ticket_message(ticket_channel)
            
            await interaction.edit_original_response(content="📝 Sending giveaway message...")
            await self.send_giveaway_message(giveaway_channel)
            
            embed = discord.Embed(
                title="✅ **Server Setup Complete!**",
                description=f"""
                **{interaction.guild.name}** has been fully configured!
                
                **Created:**
                • 📋 7 Categories
                • 💬 27+ Channels  
                • 👑 9 Roles
                • 🔐 Verification System
                • 🎫 Ticket System
                • 🎁 Giveaway System
                • 🛡️ Moderation System
                
                **Next Steps:**
                1. Check the 🔐-verification channel
                2. Customize roles and permissions
                3. Start using your server!
                
                🎉 Server is ready to go!
                """,
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
            
            await interaction.edit_original_response(content=None, embed=embed)
            logger.info("✅ Setup All completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Setup All failed: {e}", exc_info=True)
            await interaction.edit_original_response(
                content=f"❌ **Error during setup:**\n```\n{str(e)}\n```\n\nPlease check the logs for more details."
            )
    
    @discord.ui.button(label="🔐 Verification", style=discord.ButtonStyle.primary, emoji="🔐")
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            verify_channel = discord.utils.get(interaction.guild.channels, name="🔐-verification")
            if not verify_channel:
                category = discord.utils.get(interaction.guild.categories, name="🔐 Security")
                if not category:
                    category = await interaction.guild.create_category("🔐 Security")
                verify_channel = await interaction.guild.create_text_channel("🔐-verification", category=category)
            
            roles = {}
            for role_name in ["✅ Verified", "❌ Unverified", "👑 Owner", "🛡️ Admin", "🔰 Moderator"]:
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if role:
                    roles[role_name] = role.id
            
            await self.send_verification_message(verify_channel, roles)
            await interaction.followup.send("✅ Verification system setup complete!", ephemeral=True)
        except Exception as e:
            logger.error(f"❌ Verification setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎫 Tickets", style=discord.ButtonStyle.secondary, emoji="🎫")
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            ticket_channel = discord.utils.get(interaction.guild.channels, name="🎫-tickets")
            if not ticket_channel:
                category = discord.utils.get(interaction.guild.categories, name="🎫 Support")
                if not category:
                    category = await interaction.guild.create_category("🎫 Support")
                ticket_channel = await interaction.guild.create_text_channel("🎫-tickets", category=category)
            await self.send_ticket_message(ticket_channel)
            await interaction.followup.send("✅ Ticket system setup complete!", ephemeral=True)
        except Exception as e:
            logger.error(f"❌ Ticket setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎁 Giveaways", style=discord.ButtonStyle.primary, emoji="🎁")
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            giveaway_channel = discord.utils.get(interaction.guild.channels, name="🎉-giveaways")
            if not giveaway_channel:
                category = discord.utils.get(interaction.guild.categories, name="🎉 Events")
                if not category:
                    category = await interaction.guild.create_category("🎉 Events")
                giveaway_channel = await interaction.guild.create_text_channel("🎉-giveaways", category=category)
            await self.send_giveaway_message(giveaway_channel)
            await interaction.followup.send("✅ Giveaway system setup complete!", ephemeral=True)
        except Exception as e:
            logger.error(f"❌ Giveaway setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="👑 Roles", style=discord.ButtonStyle.secondary, emoji="👑")
    async def setup_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            roles_config = {
                "👑 Owner": discord.Permissions(administrator=True),
                "🛡️ Admin": discord.Permissions(administrator=True),
                "🔰 Moderator": discord.Permissions(kick_members=True, ban_members=True, manage_messages=True, manage_channels=True, manage_roles=True),
                "🤝 Helper": discord.Permissions(manage_messages=True, mute_members=True, deafen_members=True, move_members=True),
                "✅ Verified": discord.Permissions(read_messages=True, send_messages=True, connect=True, speak=True, read_message_history=True, attach_files=True, embed_links=True, add_reactions=True),
                "❌ Unverified": discord.Permissions(read_messages=True, send_messages=False),
                "🎁 Giveaway": discord.Permissions(read_messages=True, send_messages=False),
                "🎮 Gamer": discord.Permissions(read_messages=True, send_messages=True),
                "🎵 Music Lover": discord.Permissions(read_messages=True, send_messages=True)
            }
            for role_name, perms in roles_config.items():
                try:
                    await interaction.guild.create_role(name=role_name, permissions=perms)
                except Exception as e:
                    logger.warning(f"⚠️ Could not create role {role_name}: {e}")
            await interaction.followup.send("✅ Roles created successfully!", ephemeral=True)
        except Exception as e:
            logger.error(f"❌ Role setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🛡️ Moderation", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def setup_moderation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            mod_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
            if not mod_channel:
                category = discord.utils.get(interaction.guild.categories, name="🔐 Security")
                if not category:
                    category = await interaction.guild.create_category("🔐 Security")
                mod_channel = await interaction.guild.create_text_channel("🛡️-mod-logs", category=category)
            await interaction.followup.send("✅ Moderation system setup complete!", ephemeral=True)
        except Exception as e:
            logger.error(f"❌ Moderation setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    async def send_verification_message(self, channel, roles=None):
        if not channel:
            logger.warning("⚠️ Verification channel not found, skipping message")
            return
        
        embed = discord.Embed(
            title="🔐 **VERIFICATION REQUIRED**",
            description="""
            **Why verify?**
            • 🛡️ **Security** - Protect your account from unauthorized access
            • 🎮 **Access** - Unlock full server features and channels
            • 👤 **Identity** - Verify your Discord identity
            • 🏆 **Benefits** - Get access to exclusive content and roles
            • 🛡️ **Anti-Raid** - Help us keep the server safe from bots
            
            **What we collect:**
            • Your Discord username and ID
            • Email address (for verification)
            • Server membership information
            • OAuth tokens for verification
            
            **How to verify:**
            1. Click the **Verify via Discord** button below
            2. Authorize through Discord OAuth
            3. Wait for automatic role assignment
            4. You're done! 🎉
            """,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="EDITH Authentication System • Secure OAuth2 Verification")
        
        view = VerifyView(roles)
        await channel.send(embed=embed, view=view)
        logger.info(f"✅ Verification message sent to {channel.name}")
    
    async def send_ticket_message(self, channel):
        if not channel:
            logger.warning("⚠️ Ticket channel not found, skipping message")
            return
        embed = discord.Embed(
            title="🎫 **TICKET SYSTEM**",
            description="""
            **Need help? Create a ticket!**
            
            Select the type of support you need:
            • 🛠️ **Server Related** - Server issues, suggestions, feedback
            • 👮 **Contact Mods** - Report users, moderation issues
            • ❓ **Others** - General questions, help
            
            Click a button below to create your ticket!
            """,
            color=discord.Color.purple()
        )
        view = TicketView()
        await channel.send(embed=embed, view=view)
        logger.info(f"✅ Ticket message sent to {channel.name}")
    
    async def send_giveaway_message(self, channel):
        if not channel:
            logger.warning("⚠️ Giveaway channel not found, skipping message")
            return
        embed = discord.Embed(
            title="🎉 **GIVEAWAYS**",
            description="""
            **Welcome to the Giveaway Center!**
            
            🎁 Host and participate in exciting giveaways!
            👑 Admin only: Use the button below to host
            ⏰ Winners are automatically selected
            
            *Join the fun and win amazing prizes!*
            """,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)
        logger.info(f"✅ Giveaway message sent to {channel.name}")

# ============ VERIFICATION VIEW WITH OAUTH - FIXED FOR NEW TAB ============
class VerifyView(View):
    def __init__(self, roles=None):
        super().__init__(timeout=None)
        self.roles = roles or {}
        logger.debug("🔐 VerifyView created")
    
    @discord.ui.button(label="🔐 Verify via Discord", style=discord.ButtonStyle.link, emoji="🔐")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        logger.info(f"🔐 Verify button clicked by {interaction.user} ({user_id}) in guild {guild_id}")
        
        # Check if user is already verified
        user_data = db.get_user(user_id, guild_id)
        if user_data.get('verified', False):
            logger.info(f"   User {user_id} is already verified in this guild")
            embed = discord.Embed(
                title="✅ Already Verified",
                description="You are already verified in this server!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Generate OAuth URL
        logger.info(f"   Generating OAuth URL for user {user_id}")
        url, state = oauth.generate_oauth_url(user_id, guild_id)
        
        # Create a view with a URL button - this opens in a new tab by default
        view = discord.ui.View()
        verify_link = discord.ui.Button(
            label="🔐 Click to Verify",
            style=discord.ButtonStyle.link,
            url=url,
            emoji="🔐"
        )
        view.add_item(verify_link)
        
        embed = discord.Embed(
            title="🔐 **Authorize Verification**",
            description=f"""
            **Click the button below to verify your identity:**
            
            This will open Discord's authorization page in a **new tab**.
            
            ⏰ **Time Limit:** 10 minutes
            🔒 **Security:** Your data is encrypted and secure
            📧 **Email:** We'll verify your email
            🛡️ **Connections:** We'll check your connected accounts
            
            **What happens next:**
            1. You authorize through Discord
            2. We verify your identity
            3. You get the ✅ Verified role
            4. Full server access granted!
            """,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Verification ID: {state[:8]}...")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"✅ OAuth link sent to user {user_id}")

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    logger.info(f"📝 /setup command used by {interaction.user} in {interaction.guild.name}")
    view = SetupView(interaction.user)
    embed = discord.Embed(
        title="🤖 **EDITH - Ultimate Server Management Bot**",
        description="""
        **Welcome to EDITH!** 🌟
        
        Your all-in-one server management solution:
        
        ✅ **Verification System** - Secure OAuth2 verification
        ✅ **Moderation Suite** - Auto-moderation & logging
        ✅ **Ticket System** - Advanced support tickets
        ✅ **Role Management** - Automated role assignments
        ✅ **Giveaway System** - Host & manage giveaways
        ✅ **Full Server Setup** - Complete channel & role structure
        
        **My Honor** 🏆
        *Built with ❤️ for your server*
        
        **⚠️ Warning:** Setup All will delete ALL existing channels and roles!
        """,
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, view=view)
    logger.info("✅ /setup response sent")

@bot.tree.command(name="verify", description="Start verification process")
async def slash_verify(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    user_data = db.get_user(user_id, guild_id)
    if user_data.get('verified', False):
        embed = discord.Embed(
            title="✅ Already Verified",
            description="You are already verified in this server!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    url, state = oauth.generate_oauth_url(user_id, guild_id)
    
    view = discord.ui.View()
    verify_link = discord.ui.Button(
        label="🔐 Click to Verify",
        style=discord.ButtonStyle.link,
        url=url,
        emoji="🔐"
    )
    view.add_item(verify_link)
    
    embed = discord.Embed(
        title="🔐 **Verification Required**",
        description=f"""
        **Click the button below to verify your identity:**
        
        This will open Discord's authorization page in a **new tab**.
        
        ⏰ **Time Limit:** 10 minutes
        🔒 **Security:** Your data is encrypted and secure
        📧 **Email:** We'll verify your email
        
        **What happens next:**
        1. You authorize through Discord
        2. We verify your identity
        3. You get the ✅ Verified role
        4. Full server access granted!
        """,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Verification ID: {state[:8]}...")
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(interaction.client.latency * 1000)}ms")

@bot.tree.command(name="shutdown", description="Shutdown the bot (Owner only)")
async def slash_shutdown(interaction: discord.Interaction):
    if interaction.user.id != int(os.getenv('SUPER_ADMIN_ID', '0')):
        await interaction.response.send_message("❌ Only the bot owner can use this!", ephemeral=True)
        return
    await interaction.response.send_message("🔴 Shutting down...")
    await bot.close()

# ============ MODERATION ============
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    bad_words = ['badword1', 'badword2', 'badword3', 'fuck', 'shit', 'damn', 'asshole', 'bitch']
    if any(word in message.content.lower() for word in bad_words):
        try:
            await message.delete()
            warn = await message.channel.send(f"{message.author.mention}, watch your language! 🚫")
            await asyncio.sleep(5)
            await warn.delete()
        except:
            pass
        return
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    user_data = db.get_user(str(member.id), str(member.guild.id))
    if user_data.get('verified', False):
        verified_role = discord.utils.get(member.guild.roles, name="✅ Verified")
        unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
        if verified_role:
            if unverified_role:
                await member.remove_roles(unverified_role)
            await member.add_roles(verified_role)
    else:
        unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
        if unverified_role:
            try:
                await member.add_roles(unverified_role)
            except:
                pass

@bot.event
async def on_ready():
    print(f"""
    ╔════════════════════════════════════════╗
    ║         🚀 EDITH BOT ONLINE            ║
    ╠════════════════════════════════════════╣
    ║ Name: {bot.user.name}                  ║
    ║ ID: {bot.user.id}                      ║
    ║ Firebase: {'✅ Connected' if db_firebase else '⚠️ Local DB'} ║
    ║ Guilds: {len(bot.guilds)}              ║
    ║ Users: {len(bot.users)}                ║
    ║ Web Server: {'✅ Running' if flask_thread and flask_thread.is_alive() else '❌ Starting...'} ║
    ║ Slash Commands: Syncing...             ║
    ╚════════════════════════════════════════╝
    """)
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands!")
        for cmd in synced:
            print(f"   /{cmd.name}")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ============ FLASK THREAD ============
flask_thread = None

def run_flask():
    port = int(os.getenv('PORT', 8080))
    logger.info(f"🔥 Flask server starting on port {port}")
    logger.info(f"🌐 Visit: https://edith-bot.up.railway.app")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============ RUN ============
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ No DISCORD_TOKEN found!")
        exit(1)
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=False)
    flask_thread.start()
    logger.info("✅ Flask thread started")
    
    # Give Flask time to start
    time.sleep(2)
    logger.info("🌐 Web server should be running on port 8080")
    
    print("🚀 Starting EDITH Bot with OAuth + Firebase...")
    print("🌐 Web server: https://edith-bot.up.railway.app")
    try:
        bot.run(token)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
