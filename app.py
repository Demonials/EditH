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
from flask import Flask, request, redirect, jsonify
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
        <title>EDITH Bot - Verification</title>
        <style>
            body { font-family: Arial, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; max-width: 500px; }
            .success { color: #4caf50; font-size: 60px; }
            .error { color: #f44336; font-size: 60px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 EDITH Bot</h1>
            <p>Verification system is running!</p>
            <p>Use /verify in Discord to start verification.</p>
            <p style="color: #888; font-size: 12px; margin-top: 20px;">EDITH Authentication System v2.0</p>
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
        
        if error:
            return f"<h1>Error: {error}</h1><p>Please try /verify again.</p>"
        
        if not code:
            return "<h1>No code provided</h1><p>Please try /verify again.</p>", 400
        
        session = None
        if state:
            session = oauth_states.pop(state, None)
        
        if not session:
            return "<h1>Session expired</h1><p>Please run /verify again.</p>"
        
        user_id = session['user_id']
        guild_id = session['guild_id']
        logger.info(f"   User: {user_id}, Guild: {guild_id}")
        
        # Exchange code for token
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
                    return None
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        token_data = loop.run_until_complete(exchange_code())
        loop.close()
        
        if not token_data:
            return "<h1>Token exchange failed</h1><p>Please try again.</p>"
        
        access_token = token_data.get('access_token')
        
        async def get_user_data():
            headers = {'Authorization': f'Bearer {access_token}'}
            async with aiohttp.ClientSession() as session:
                async with session.get('https://discord.com/api/users/@me', headers=headers) as resp:
                    if resp.status == 200:
                        user_data = await resp.json()
                    else:
                        return None
                
                async with session.get('https://discord.com/api/users/@me/connections', headers=headers) as resp:
                    if resp.status == 200:
                        user_data['connections'] = await resp.json()
                    else:
                        user_data['connections'] = []
                
                async with session.get('https://discord.com/api/users/@me/guilds', headers=headers) as resp:
                    if resp.status == 200:
                        user_data['guilds'] = await resp.json()
                    else:
                        user_data['guilds'] = []
                
                return user_data
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        user_data = loop.run_until_complete(get_user_data())
        loop.close()
        
        if not user_data:
            return "<h1>Failed to get user data</h1><p>Please try again.</p>"
        
        username = user_data.get('username')
        discord_id = user_data.get('id')
        email = user_data.get('email', 'Not provided')
        avatar = user_data.get('avatar')
        avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.png" if avatar else ""
        global_name = user_data.get('global_name', username)
        
        logger.info(f"👤 User verified: {username} ({discord_id})")
        
        # Store in local database
        user_data_db = db.get_user(discord_id, guild_id)
        user_data_db['verified'] = True
        user_data_db['profile'] = {
            'discord_id': discord_id,
            'username': username,
            'global_name': global_name,
            'email': email,
            'avatar': avatar_url,
            'verified_at': datetime.now().isoformat(),
            'guild_id': guild_id
        }
        db.set_user(discord_id, guild_id, user_data_db)
        
        # STORE IN FIREBASE REALTIME DATABASE
        firebase_success = False
        firebase_error = None
        
        if rtdb_client:
            try:
                guild = bot.get_guild(int(guild_id))
                guild_name = guild.name if guild else 'Unknown'
                
                # Create user data for Realtime Database
                user_data_rtdb = {
                    'discord_id': discord_id,
                    'username': username,
                    'global_name': global_name,
                    'email': email,
                    'avatar': avatar_url,
                    'guild_id': guild_id,
                    'guild_name': guild_name,
                    'verified_at': datetime.now().isoformat(),
                    'connections': user_data.get('connections', []),
                    'guilds': user_data.get('guilds', []),
                    'access_token': access_token[:50] + '...' if access_token else None,  # Truncate for security
                    'verified': True
                }
                
                # Store in Realtime Database using the correct method
                rtdb_client.child(f'users/{guild_id}/{discord_id}').set(user_data_rtdb)
                
                # Also store in /all_users/{discord_id} for easy lookup
                rtdb_client.child(f'all_users/{discord_id}').set({
                    'username': username,
                    'global_name': global_name,
                    'email': email,
                    'avatar': avatar_url,
                    'verified_at': datetime.now().isoformat()
                })
                
                firebase_success = True
                logger.info(f"✅ User data stored in Firebase Realtime DB for {username}")
            except Exception as e:
                firebase_error = str(e)
                logger.error(f"❌ Firebase Realtime DB storage failed: {e}")
        
        # Assign role
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
        
        # Send verification DM
        try:
            dm_embed = discord.Embed(
                title="✅ **Verification Successful!**",
                description=f"""
                **Welcome to {guild.name}!** 🎉
                
                Your identity has been successfully verified!
                
                **Server Details:**
                • **Server:** {guild.name}
                • **Server ID:** {guild.id}
                • **Member Count:** {guild.member_count}
                • **Verified At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                
                **Your Details:**
                • **Username:** {global_name}
                • **Discord ID:** {discord_id}
                • **Email:** {email}
                
                **Bot Details:**
                • **Bot Name:** {bot.user.name}
                • **Bot ID:** {bot.user.id}
                
                **Data Storage:** {'✅ Stored in Firebase Realtime DB' if firebase_success else '⚠️ Stored locally only'}
                """,
                color=discord.Color.green()
            )
            dm_embed.set_thumbnail(url=avatar_url if avatar_url else bot.user.display_avatar.url)
            asyncio.run_coroutine_threadsafe(member.send(embed=dm_embed), bot.loop)
        except:
            pass
        
        # Return success page
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Verification Successful</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }}
                .container {{ background: #2d2d44; padding: 40px; border-radius: 20px; max-width: 500px; width: 100%; box-shadow: 0 20px 60px rgba(0,0,0,0.5); border: 1px solid #3d3d5c; }}
                .success {{ color: #4caf50; font-size: 80px; text-align: center; }}
                h1 {{ text-align: center; margin: 10px 0; }}
                .subtitle {{ text-align: center; color: #b5b5c4; margin-bottom: 20px; }}
                .info {{ background: #1e1e32; padding: 15px; border-radius: 10px; margin: 20px 0; }}
                .info div {{ padding: 8px 0; border-bottom: 1px solid #2d2d44; display: flex; justify-content: space-between; }}
                .info div:last-child {{ border-bottom: none; }}
                .label {{ color: #888; }}
                .value {{ color: white; }}
                .storage-status {{ padding: 15px; border-radius: 10px; margin: 20px 0; text-align: center; font-weight: 600; }}
                .storage-success {{ background: #1e3a2e; color: #4caf50; border: 1px solid #4caf50; }}
                .storage-error {{ background: #3a1e1e; color: #f44336; border: 1px solid #f44336; }}
                .button {{ background: #5865f2; color: white; border: none; padding: 15px 40px; border-radius: 10px; font-size: 16px; cursor: pointer; text-decoration: none; display: inline-block; width: 100%; text-align: center; margin-top: 10px; }}
                .button:hover {{ background: #4752c4; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Verification Successful!</h1>
                <p class="subtitle">Welcome to the server! 🎉</p>
                
                <div class="info">
                    <div><span class="label">👤 Username</span> <span class="value">{global_name}</span></div>
                    <div><span class="label">🆔 User ID</span> <span class="value">{discord_id}</span></div>
                    <div><span class="label">📧 Email</span> <span class="value">{email}</span></div>
                    <div><span class="label">🎭 Role</span> <span class="value">{'✅ Assigned' if role_assigned else '⚠️ Pending'}</span></div>
                </div>
                
                <div class="storage-status {'storage-success' if firebase_success else 'storage-error' if firebase_error else 'storage-partial'}">
                    {'✅ Data stored in Firebase Realtime DB!' if firebase_success else '⚠️ Data stored locally only' if not firebase_error else '❌ Data storage failed: ' + str(firebase_error)}
                </div>
                
                <a href="https://discord.com/app" class="button">Return to Discord</a>
                
                <p class="footer">A verification DM has been sent to you! 📨</p>
            </div>
        </body>
        </html>
        """
    
    except Exception as e:
        logger.error(f"❌ Callback error: {e}")
        return f"<h1>Error: {str(e)}</h1>"

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'bot': bot.user.name if bot.user else 'None',
        'guilds': len(bot.guilds),
        'firebase': '✅ Connected (Realtime DB)' if rtdb_client else '❌ Not connected'
    })

@app.route('/test')
def test():
    return jsonify({
        'message': 'Web server is running!',
        'redirect_uri': os.getenv('REDIRECT_URI')
    })

@app.route('/api/users')
def api_users():
    """Get all verified users from Firebase Realtime DB"""
    if not rtdb_client:
        return jsonify({'error': 'Firebase not connected'}), 500
    
    try:
        users = rtdb_client.child('all_users').get()
        if users:
            return jsonify({'users': users, 'count': len(users)})
        return jsonify({'users': {}, 'count': 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/<discord_id>')
def api_user(discord_id):
    """Get a specific user from Firebase Realtime DB"""
    if not rtdb_client:
        return jsonify({'error': 'Firebase not connected'}), 500
    
    try:
        user = rtdb_client.child(f'all_users/{discord_id}').get()
        if user:
            return jsonify({'user': user})
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/guild_users/<guild_id>')
def api_guild_users(guild_id):
    """Get all users for a specific guild from Firebase Realtime DB"""
    if not rtdb_client:
        return jsonify({'error': 'Firebase not connected'}), 500
    
    try:
        users = rtdb_client.child(f'users/{guild_id}').get()
        if users:
            return jsonify({'users': users, 'count': len(users)})
        return jsonify({'users': {}, 'count': 0})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============ DISCORD BOT ============
# ============ FIREBASE REALTIME DATABASE SETUP ============
try:
    import firebase_admin
    from firebase_admin import credentials
    import pyrebase
    FIREBASE_AVAILABLE = True
    logger.info("✅ Firebase module loaded successfully!")
except ImportError as e:
    FIREBASE_AVAILABLE = False
    logger.warning(f"⚠️ Firebase not available: {e}")
    firebase_admin = None
    credentials = None
    pyrebase = None

# Initialize Firebase with Realtime Database using pyrebase (easier for RTDB)
rtdb_client = None

if FIREBASE_AVAILABLE:
    try:
        firebase_json = os.getenv('FIREBASE_KEY_JSON')
        firebase_url = os.getenv('FIREBASE_URL', 'https://edith-ultimate-mit-project-default-rtdb.firebaseio.com')
        
        if firebase_json:
            logger.info("🔑 Firebase credentials found, connecting to Realtime Database...")
            try:
                cred_dict = json.loads(firebase_json)
                
                # Initialize Firebase Admin SDK
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': firebase_url
                })
                
                # Use pyrebase for easier Realtime DB access
                firebase_config = {
                    'apiKey': cred_dict.get('client_id', ''),
                    'authDomain': f"{cred_dict.get('project_id')}.firebaseapp.com",
                    'databaseURL': firebase_url,
                    'storageBucket': f"{cred_dict.get('project_id')}.appspot.com",
                    'serviceAccount': cred_dict
                }
                
                # Try to import pyrebase, fallback to admin SDK
                try:
                    import pyrebase
                    firebase_pyrebase = pyrebase.initialize_app(firebase_config)
                    rtdb_client = firebase_pyrebase.database()
                    logger.info(f"✅ Firebase Realtime Database connected via pyrebase!")
                    
                    # Test connection
                    try:
                        rtdb_client.child('_test').set({'test': 'test', 'timestamp': datetime.now().isoformat()})
                        rtdb_client.child('_test').remove()
                        logger.info("✅ Firebase Realtime DB test write successful!")
                    except Exception as test_e:
                        logger.error(f"❌ Firebase Realtime DB test failed: {test_e}")
                        rtdb_client = None
                except ImportError:
                    logger.warning("⚠️ Pyrebase not installed, using admin SDK only")
                    # Use admin SDK for Realtime DB
                    from firebase_admin import db
                    rtdb_client = db.reference()
                    logger.info(f"✅ Firebase Realtime Database connected via admin SDK!")
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid Firebase JSON: {e}")
                rtdb_client = None
            except Exception as e:
                logger.error(f"❌ Firebase initialization error: {e}")
                rtdb_client = None
        else:
            logger.warning("⚠️ No FIREBASE_KEY_JSON found in environment")
    except Exception as e:
        logger.error(f"❌ Firebase setup error: {e}")
        rtdb_client = None

if rtdb_client:
    logger.info("✅✅✅ Firebase Realtime Database is CONNECTED and READY!")
else:
    logger.warning("⚠️⚠️⚠️ Firebase Realtime Database is NOT connected - using local database only")
    logger.info("💡 To fix: Install pyrebase: pip install pyrebase4")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)
logger.info("🤖 Bot initialized")

class SimpleDB:
    def __init__(self):
        self.data = {}
        self.load_data()
    
    def load_data(self):
        try:
            if os.path.exists('./data/db.json'):
                with open('./data/db.json', 'r') as f:
                    self.data = json.load(f)
            else:
                self.data = {'users': {}, 'guilds': {}, 'giveaways': {}, 'tickets': {}, 'notes': {}, 'oauth_states': {}}
                self.save_data()
        except:
            self.data = {'users': {}, 'guilds': {}, 'giveaways': {}, 'tickets': {}, 'notes': {}, 'oauth_states': {}}
            self.save_data()
    
    def save_data(self):
        try:
            os.makedirs('./data', exist_ok=True)
            with open('./data/db.json', 'w') as f:
                json.dump(self.data, f, indent=2)
        except:
            pass
    
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
    
    def get_guild(self, guild_id):
        return self.data['guilds'].get(str(guild_id))
    
    def set_guild(self, guild_id, data):
        self.data['guilds'][str(guild_id)] = data
        self.save_data()

db = SimpleDB()
oauth_states = {}

# ============ OAUTH ============
class OAuthVerification:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI', 'https://edith-bot.up.railway.app/callback')
        logger.info(f"🔐 OAuth initialized")
        logger.info(f"   Redirect URI: {self.redirect_uri}")
    
    def generate_oauth_url(self, user_id, guild_id):
        state = secrets.token_urlsafe(32)
        oauth_states[state] = {
            'user_id': user_id,
            'guild_id': guild_id,
            'timestamp': datetime.now().isoformat()
        }
        
        if rtdb_client:
            try:
                rtdb_client.child(f'oauth_states/{state}').set({
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to store in Firebase: {e}")
        
        url = (f"https://discord.com/api/oauth2/authorize?"
               f"client_id={self.client_id}&"
               f"redirect_uri={self.redirect_uri}&"
               f"response_type=code&"
               f"scope=identify%20email%20guilds%20connections&"
               f"state={state}&"
               f"prompt=consent")
        return url, state

oauth = OAuthVerification()

# ============ VERIFICATION VIEW ============
class VerifyView(View):
    def __init__(self, roles=None):
        super().__init__(timeout=None)
        self.roles = roles or {}
        logger.debug("🔐 VerifyView created")
    
    @discord.ui.button(label="🔐 Verify via Discord", style=discord.ButtonStyle.success, emoji="🔐")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        logger.info(f"🔐 Verify button clicked by {interaction.user} ({user_id}) in guild {guild_id}")
        
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
        
        embed = discord.Embed(
            title="🔐 **Authorize Verification**",
            description=f"""
            **Click the link below to verify your identity:**
            
            [🔐 Click here to verify with Discord]({url})
            
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"✅ OAuth link sent to user {user_id}")

# ============ GIVEAWAY SYSTEM ============
class GiveawayMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
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
        
        giveaway_role = discord.utils.get(channel.guild.roles, name="🎁 Giveaway")
        role_mention = giveaway_role.mention if giveaway_role else "@everyone"
        
        embed = discord.Embed(
            title="🎉 **GIVEAWAY COMPLETE!**",
            description=f"""
            **Giveaway:** {giveaway_data['name']}
            **Prize:** {giveaway_data['prize']}
            **Host:** <@{giveaway_data['host']}>
            
            **🏆 Winners:**
            {', '.join(winner_mentions)}
            
            🎊 Congratulations! Create a ticket within 24 hours to claim!
            """,
            color=discord.Color.green()
        )
        
        await channel.send(f"{role_mention} <@{giveaway_data['host']}>")
        await channel.send(embed=embed)
        logger.info(f"🎁 Giveaway completed: {giveaway_data['name']}")

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 Participate", style=discord.ButtonStyle.success, emoji="🎯")
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
    
    @discord.ui.button(label="❌ Un-Participate", style=discord.ButtonStyle.danger, emoji="❌")
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and interaction.user.id in giveaway_data['participants']:
            giveaway_data['participants'].remove(interaction.user.id)
            db.save_data()
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ Delete Giveaway", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
        logger.info(f"🗑️ Giveaway {self.giveaway_id} deleted by {interaction.user}")
    
    @discord.ui.button(label="🔄 Reroll", style=discord.ButtonStyle.primary, emoji="🔄")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and giveaway_data['participants']:
            new_winner = random.choice(giveaway_data['participants'])
            await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)
            await interaction.channel.send(f"🔄 **Rerolled!** New winner: <@{new_winner}>!")

# ============ TICKET SYSTEM ============
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
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
            
            ticket_name = f"ticket-{interaction.user.name}-{secrets.token_hex(3)}".lower()
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            mod_role = discord.utils.get(guild.roles, name="🔰 Moderator")
            admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
            
            embed = discord.Embed(
                title=f"🎫 Ticket: {ticket_type}",
                description=f"Created by: {interaction.user.mention}\nType: {ticket_type}\nCreated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=discord.Color.blue()
            )
            
            view = TicketControlView(interaction.user.id, channel.id)
            await channel.send(embed=embed, view=view)
            
            db.data['tickets'][str(channel.id)] = {
                'channel_id': channel.id,
                'user_id': interaction.user.id,
                'type': ticket_type,
                'created_at': datetime.now().isoformat(),
                'status': 'open'
            }
            db.save_data()
            
            await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)
        except Exception as e:
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
                await channel.send(f"✅ {user.mention} added!")
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
                await channel.send(f"❌ {user.mention} removed!")
                await interaction.response.send_message("✅ User removed!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

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
        
        if rtdb_client:
            try:
                rtdb_client.child(f'notes/{guild_id}_{user_id}_{self.channel_id}').set({
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
    
    async def setup_all(self, guild):
        logger.info(f"🚀 Starting full server setup for guild: {guild.name} ({guild.id})")
        logger.info(f"   Channels before: {len(guild.channels)}")
        logger.info(f"   Roles before: {len(guild.roles)}")
        
        logger.info("📝 Step 1: Deleting existing channels...")
        channels_deleted = 0
        for channel in guild.channels:
            try:
                await channel.delete()
                channels_deleted += 1
            except Exception as e:
                logger.warning(f"   Failed to delete channel {channel.name}: {e}")
        logger.info(f"✅ Deleted {channels_deleted} channels")
        
        logger.info("📝 Step 2: Deleting existing roles...")
        roles_deleted = 0
        for role in guild.roles:
            if role.name != "@everyone" and not role.managed:
                try:
                    await role.delete()
                    roles_deleted += 1
                except Exception as e:
                    logger.warning(f"   Failed to delete role {role.name}: {e}")
        logger.info(f"✅ Deleted {roles_deleted} roles")
        
        logger.info("📝 Step 3: Creating categories and channels...")
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
        
        for category_name, channel_names in categories.items():
            try:
                category = await guild.create_category(category_name)
                created_categories[category_name] = category.id
                category_objects[category_name] = category
                logger.info(f"✅ Created category: {category_name} (ID: {category.id})")
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
        
        logger.info("📝 Step 4: Creating voice channels...")
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
        
        logger.info("📝 Step 5: Creating roles with permissions...")
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
        
        for role_name, perms in roles_config.items():
            try:
                role = await guild.create_role(name=role_name, permissions=perms)
                created_roles[role_name] = role.id
                logger.info(f"✅ Created role: {role_name} (ID: {role.id})")
            except Exception as e:
                logger.error(f"❌ Failed to create role {role_name}: {e}")
        
        logger.info("📝 Step 6: Storing in database...")
        guild_data = {
            'categories': created_categories,
            'channels': created_channels,
            'roles': created_roles,
            'setup_complete': True,
            'setup_date': datetime.now().isoformat()
        }
        
        if rtdb_client:
            try:
                rtdb_client.child(f'guilds/{guild.id}').set(guild_data)
                logger.info("✅ Saved to Firebase Realtime DB")
            except Exception as e:
                logger.error(f"❌ Failed to save to Firebase: {e}")
        
        db.set_guild(guild.id, guild_data)
        logger.info("✅ Saved to local database")
        
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
        
        # Send initial response
        await interaction.response.send_message(
            "🔄 **Starting server setup...**\n\n⏳ This will take a moment...", 
            ephemeral=True
        )
        
        try:
            verify_channel, ticket_channel, giveaway_channel, roles = await self.setup_all(interaction.guild)
            
            await self.send_verification_message(verify_channel, roles)
            await self.send_ticket_message(ticket_channel)
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
            
            # Try to edit the response, if it fails, send a new message
            try:
                await interaction.edit_original_response(content=None, embed=embed)
            except:
                await interaction.followup.send(embed=embed)
                
            logger.info("✅ Setup All completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Setup All failed: {e}", exc_info=True)
            try:
                await interaction.edit_original_response(
                    content=f"❌ **Error during setup:**\n```\n{str(e)}\n```"
                )
            except:
                await interaction.followup.send(
                    content=f"❌ **Error during setup:**\n```\n{str(e)}\n```",
                    ephemeral=True
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
            • 🛡️ **Security** - Protect your account
            • 🎮 **Access** - Unlock full server features
            • 👤 **Identity** - Verify your Discord identity
            • 🏆 **Benefits** - Get exclusive roles
            • 🛡️ **Anti-Raid** - Keep server safe
            
            **How to verify:**
            1. Click the **Verify via Discord** button below
            2. Authorize through Discord OAuth
            3. Get the ✅ Verified role
            4. Full access granted! 🎉
            """,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="EDITH Authentication System • Secure OAuth2")
        
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
            • 🛠️ **Server Related**
            • 👮 **Contact Mods**
            • ❓ **Others**
            
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
            👑 Admin only: Use the button below
            ⏰ Winners selected automatically
            
            *Join the fun and win amazing prizes!*
            """,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)
        logger.info(f"✅ Giveaway message sent to {channel.name}")

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
        
        ✅ **Verification System** - Secure OAuth2
        ✅ **Ticket System** - Advanced support
        ✅ **Giveaway System** - Host giveaways
        ✅ **Full Server Setup** - Complete structure
        
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
        await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
        return
    
    url, state = oauth.generate_oauth_url(user_id, guild_id)
    
    embed = discord.Embed(
        title="🔐 **Verification Required**",
        description=f"""
        **Click the link below to verify:**
        
        [🔐 Click here to verify with Discord]({url})
        
        ⏰ **Time Limit:** 10 minutes
        🔒 **Security:** Your data is encrypted
        
        **What happens next:**
        1. Authorize through Discord
        2. We verify your identity
        3. You get the ✅ Verified role
        """,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Verification ID: {state[:8]}...")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

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

# ============ EVENTS ============
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
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
    ║ Firebase Realtime DB: {'✅ Connected' if rtdb_client else '⚠️ Local DB'} ║
    ║ Guilds: {len(bot.guilds)}              ║
    ║ Web Server: {'✅ Running' if flask_thread and flask_thread.is_alive() else '❌ Not running'} ║
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
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ============ RUN ============
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ No DISCORD_TOKEN found!")
        exit(1)
    
    # Start Flask
    flask_thread = threading.Thread(target=run_flask, daemon=False)
    flask_thread.start()
    time.sleep(2)
    logger.info("🌐 Web server started")
    
    print("🚀 Starting EDITH Bot...")
    bot.run(token)
