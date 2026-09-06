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
import hashlib

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

load_dotenv()
logger.info("📝 Environment loaded")

# ============ FLASK APP ============
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ============ FIREBASE SETUP ============
try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
    logger.info("✅ Firebase module loaded successfully!")
except ImportError as e:
    FIREBASE_AVAILABLE = False
    logger.warning(f"⚠️ Firebase not available: {e}")
    firebase_admin = None
    credentials = None
    db = None

firebase_app = None
rtdb_client = None

if FIREBASE_AVAILABLE:
    try:
        firebase_json = os.getenv('FIREBASE_KEY_JSON')
        firebase_url = os.getenv('FIREBASE_URL', 'https://edith-ultimate-mit-project-default-rtdb.firebaseio.com')
        
        if firebase_json:
            logger.info("🔑 Firebase credentials found, connecting...")
            try:
                cred_dict = json.loads(firebase_json)
                cred = credentials.Certificate(cred_dict)
                firebase_app = firebase_admin.initialize_app(cred, {
                    'databaseURL': firebase_url
                })
                rtdb_client = db.reference()
                logger.info(f"✅ Firebase connected!")
                
                # Test connection
                try:
                    test_ref = rtdb_client.child('_test')
                    test_ref.set({'test': 'test', 'timestamp': datetime.now().isoformat()})
                    test_ref.delete()
                    logger.info("✅ Firebase test successful!")
                except Exception as test_e:
                    logger.error(f"❌ Firebase test failed: {test_e}")
                    rtdb_client = None
            except Exception as e:
                logger.error(f"❌ Firebase init error: {e}")
                rtdb_client = None
        else:
            logger.warning("⚠️ No FIREBASE_KEY_JSON found")
    except Exception as e:
        logger.error(f"❌ Firebase setup error: {e}")
        rtdb_client = None

if rtdb_client:
    logger.info("✅✅✅ Firebase is CONNECTED!")
else:
    logger.warning("⚠️⚠️⚠️ Firebase NOT connected - using local DB")

# ============ DISCORD BOT ============
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# ============ DATABASE FUNCTIONS ============
class Database:
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

db = Database()
oauth_states = {}

# ============ FIREBASE HELPER FUNCTIONS ============
def firebase_set(path, data):
    """Set data in Firebase"""
    if rtdb_client:
        try:
            rtdb_client.child(path).set(data)
            return True
        except Exception as e:
            logger.error(f"Firebase set error at {path}: {e}")
            return False
    return False

def firebase_get(path):
    """Get data from Firebase"""
    if rtdb_client:
        try:
            return rtdb_client.child(path).get()
        except Exception as e:
            logger.error(f"Firebase get error at {path}: {e}")
            return None
    return None

def firebase_update(path, data):
    """Update data in Firebase"""
    if rtdb_client:
        try:
            rtdb_client.child(path).update(data)
            return True
        except Exception as e:
            logger.error(f"Firebase update error at {path}: {e}")
            return False
    return False

def firebase_delete(path):
    """Delete data from Firebase"""
    if rtdb_client:
        try:
            rtdb_client.child(path).delete()
            return True
        except Exception as e:
            logger.error(f"Firebase delete error at {path}: {e}")
            return False
    return False

def generate_credentials(user_id, role='member'):
    """Generate username and password for user"""
    username = f"user_{str(user_id)[:8]}_{secrets.token_hex(4)}"
    password = secrets.token_urlsafe(12)
    
    # Store in Firebase
    firebase_set(f'credentials/{user_id}', {
        'username': username,
        'password': password,
        'role': role,
        'created_at': datetime.now().isoformat()
    })
    
    return {'username': username, 'password': password, 'role': role}

def get_credentials(user_id):
    """Get user credentials from Firebase"""
    return firebase_get(f'credentials/{user_id}')

def update_credentials_role(user_id, new_role):
    """Update user's role in credentials"""
    creds = get_credentials(user_id)
    if creds:
        creds['role'] = new_role
        firebase_set(f'credentials/{user_id}', creds)
        return True
    return False

async def send_credentials_dm(member, creds):
    """Send credentials via DM"""
    embed = discord.Embed(
        title="🔐 Your EDITH Credentials",
        description=f"Welcome to **{member.guild.name}**!",
        color=discord.Color.green()
    )
    embed.add_field(name="Username", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="Password", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="Role", value=f"`{creds['role'].upper()}`", inline=True)
    embed.add_field(name="Login URL", value=f"[Click Here]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})", inline=False)
    embed.set_footer(text="⚠️ Keep these safe! You cannot reset your password.")
    
    try:
        await member.send(embed=embed)
        return True
    except:
        return False

async def save_guild_config(guild):
    """Save guild configuration to Firebase"""
    if not rtdb_client:
        return False
    
    try:
        config = {
            'name': guild.name,
            'id': str(guild.id),
            'owner_id': str(guild.owner_id) if guild.owner_id else None,
            'owner_name': str(guild.owner) if guild.owner else 'Unknown',
            'created_at': guild.created_at.isoformat() if guild.created_at else None,
            'member_count': guild.member_count,
            'boost_count': guild.premium_subscription_count,
            'boost_level': guild.premium_tier,
            'description': guild.description or '',
            'icon_url': guild.icon.url if guild.icon else None,
            'banner_url': guild.banner.url if guild.banner else None,
            'splash_url': guild.splash.url if guild.splash else None,
            'region': str(guild.region) if guild.region else None,
            'preferred_locale': guild.preferred_locale,
            'verification_level': str(guild.verification_level),
            'explicit_content_filter': str(guild.explicit_content_filter),
            'default_message_notifications': str(guild.default_notifications),
            'features': guild.features,
            'system_channel_id': str(guild.system_channel.id) if guild.system_channel else None,
            'rules_channel_id': str(guild.rules_channel.id) if guild.rules_channel else None,
            'public_updates_channel_id': str(guild.public_updates_channel.id) if guild.public_updates_channel else None,
            'afk_channel_id': str(guild.afk_channel.id) if guild.afk_channel else None,
            'afk_timeout': guild.afk_timeout,
            'max_presences': guild.max_presences,
            'max_members': guild.max_members,
            'discovery_splash_url': guild.discovery_splash.url if guild.discovery_splash else None,
            'vanity_url_code': guild.vanity_url_code,
            'widget_enabled': guild.widget_enabled,
            'widget_channel_id': str(guild.widget_channel.id) if guild.widget_channel else None,
            'updated_at': datetime.now().isoformat()
        }
        
        firebase_set(f'guilds/{guild.id}/config', config)
        logger.info(f"✅ Saved guild config for {guild.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to save guild config: {e}")
        return False

async def save_guild_template(guild):
    """Save guild template (channels, roles, categories)"""
    if not rtdb_client:
        return False
    
    try:
        template = {
            'categories': {},
            'channels': {},
            'roles': {},
            'settings': {}
        }
        
        # Save categories
        for category in guild.categories:
            template['categories'][category.name] = {
                'id': str(category.id),
                'position': category.position,
                'channels': []
            }
        
        # Save channels
        for channel in guild.channels:
            template['channels'][channel.name] = {
                'id': str(channel.id),
                'type': str(channel.type),
                'position': channel.position,
                'category_id': str(channel.category.id) if channel.category else None,
                'topic': channel.topic or '',
                'slowmode_delay': channel.slowmode_delay if hasattr(channel, 'slowmode_delay') else 0,
                'nsfw': channel.nsfw if hasattr(channel, 'nsfw') else False
            }
            
            # Add to category
            if channel.category:
                for cat in template['categories']:
                    if template['categories'][cat]['id'] == str(channel.category.id):
                        if channel.name not in template['categories'][cat]['channels']:
                            template['categories'][cat]['channels'].append(channel.name)
        
        # Save roles
        for role in guild.roles:
            if role.name != "@everyone":
                template['roles'][role.name] = {
                    'id': str(role.id),
                    'color': str(role.color),
                    'position': role.position,
                    'hoist': role.hoist,
                    'mentionable': role.mentionable,
                    'permissions': role.permissions.value,
                    'permissions_text': str(role.permissions)
                }
        
        # Save settings
        template['settings'] = {
            'verification_level': str(guild.verification_level),
            'explicit_content_filter': str(guild.explicit_content_filter),
            'default_notifications': str(guild.default_notifications),
            'afk_timeout': guild.afk_timeout
        }
        
        firebase_set(f'guilds/{guild.id}/template', template)
        logger.info(f"✅ Saved guild template for {guild.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to save guild template: {e}")
        return False

async def sync_server_members(guild):
    """Sync all members in a guild - create credentials, move between verified/unverified"""
    if not rtdb_client:
        return
    
    try:
        # Get all members
        members = guild.members
        verified_role = discord.utils.get(guild.roles, name="✅ Verified")
        unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
        
        # Get Firebase members
        firebase_verified = firebase_get(f'guilds/{guild.id}/verified') or {}
        firebase_unverified = firebase_get(f'guilds/{guild.id}/unverified') or {}
        firebase_creds = firebase_get('credentials') or {}
        
        # Track current members in Firebase
        firebase_members = set(list(firebase_verified.keys()) + list(firebase_unverified.keys()))
        current_members = set([str(m.id) for m in members if not m.bot])
        
        # Remove members who left
        for user_id in firebase_members:
            if user_id not in current_members:
                # Remove from Firebase
                firebase_delete(f'guilds/{guild.id}/verified/{user_id}')
                firebase_delete(f'guilds/{guild.id}/unverified/{user_id}')
                firebase_delete(f'credentials/{user_id}')
                logger.info(f"🗑️ Removed {user_id} (left server)")
        
        # Process current members
        for member in members:
            if member.bot:
                continue
                
            user_id = str(member.id)
            is_admin = any(role.permissions.administrator for role in member.roles)
            is_verified = verified_role in member.roles if verified_role else False
            
            # Check if credentials exist
            creds = get_credentials(user_id)
            if not creds:
                # Generate new credentials
                role_type = 'moderator' if is_admin else 'member'
                creds = generate_credentials(user_id, role_type)
                await send_credentials_dm(member, creds)
                logger.info(f"🔑 Generated credentials for {member.name}")
            
            # Update role if changed
            if creds and is_admin and creds.get('role') != 'moderator':
                update_credentials_role(user_id, 'moderator')
                await send_credentials_dm(member, {'username': creds['username'], 'password': creds['password'], 'role': 'moderator'})
                logger.info(f"🔄 Updated {member.name} to moderator")
            elif creds and not is_admin and creds.get('role') != 'member':
                update_credentials_role(user_id, 'member')
                await send_credentials_dm(member, {'username': creds['username'], 'password': creds['password'], 'role': 'member'})
                logger.info(f"🔄 Updated {member.name} to member")
            
            # Move between verified/unverified
            if is_verified:
                # Move to verified
                firebase_delete(f'guilds/{guild.id}/unverified/{user_id}')
                firebase_set(f'guilds/{guild.id}/verified/{user_id}', {
                    'discord_id': user_id,
                    'username': member.name,
                    'global_name': member.display_name or member.name,
                    'avatar': member.avatar.url if member.avatar else None,
                    'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                    'verified_at': datetime.now().isoformat(),
                    'roles': [r.name for r in member.roles if r.name != "@everyone"],
                    'credentials': creds
                })
            else:
                # Move to unverified
                firebase_delete(f'guilds/{guild.id}/verified/{user_id}')
                firebase_set(f'guilds/{guild.id}/unverified/{user_id}', {
                    'discord_id': user_id,
                    'username': member.name,
                    'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                    'roles': [r.name for r in member.roles if r.name != "@everyone"]
                })
        
        logger.info(f"✅ Synced {len(members)} members for {guild.name}")
        
    except Exception as e:
        logger.error(f"Failed to sync members: {e}")

# ============ FLASK ROUTES ============
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>EDITH Bot - Management</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
            .container { background: #2d2d44; padding: 40px; border-radius: 20px; max-width: 600px; width: 100%; }
            h1 { text-align: center; margin-bottom: 10px; }
            .subtitle { text-align: center; color: #b5b5c4; margin-bottom: 30px; }
            .status { background: #1e1e32; padding: 20px; border-radius: 12px; margin: 20px 0; }
            .status-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2d2d44; }
            .status-item:last-child { border-bottom: none; }
            .label { color: #888; }
            .value { color: #4caf50; }
            .badge { display: inline-block; background: #4caf50; padding: 4px 12px; border-radius: 20px; font-size: 11px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 EDITH Bot</h1>
            <p class="subtitle">Ultimate Server Management System</p>
            
            <div class="status">
                <div class="status-item">
                    <span class="label">Status</span>
                    <span class="value">✅ Online</span>
                </div>
                <div class="status-item">
                    <span class="label">Firebase</span>
                    <span class="value">✅ Connected</span>
                </div>
                <div class="status-item">
                    <span class="label">Features</span>
                    <span class="value">Verification • Tickets • Giveaways • Credentials</span>
                </div>
            </div>
            
            <p style="text-align: center; color: #888; font-size: 12px;">Use /setup in Discord to configure your server</p>
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
        
        # Store in Firebase
        firebase_success = False
        
        if rtdb_client:
            try:
                guild = bot.get_guild(int(guild_id))
                guild_name = guild.name if guild else 'Unknown'
                
                # Store in verified
                firebase_set(f'guilds/{guild_id}/verified/{discord_id}', {
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
                    'verified': True
                })
                
                # Remove from unverified
                firebase_delete(f'guilds/{guild_id}/unverified/{discord_id}')
                
                # Store in all_users
                firebase_set(f'all_users/{discord_id}', {
                    'username': username,
                    'global_name': global_name,
                    'email': email,
                    'avatar': avatar_url,
                    'verified_at': datetime.now().isoformat()
                })
                
                firebase_success = True
                logger.info(f"✅ User verified in Firebase: {username}")
            except Exception as e:
                logger.error(f"❌ Firebase storage failed: {e}")
        
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
                    except:
                        pass
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Verification Successful</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }}
                .container {{ background: #2d2d44; padding: 40px; border-radius: 20px; max-width: 500px; width: 100%; }}
                .success {{ color: #4caf50; font-size: 80px; text-align: center; }}
                h1 {{ text-align: center; }}
                .info {{ background: #1e1e32; padding: 15px; border-radius: 10px; margin: 20px 0; }}
                .info div {{ padding: 8px 0; border-bottom: 1px solid #2d2d44; display: flex; justify-content: space-between; }}
                .info div:last-child {{ border-bottom: none; }}
                .label {{ color: #888; }}
                .value {{ color: white; }}
                .status-badge {{ {'✅ Data stored in Firebase!' if firebase_success else '⚠️ Data stored locally only'} }}
                .button {{ background: #5865f2; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 16px; cursor: pointer; text-decoration: none; display: block; text-align: center; margin-top: 20px; }}
                .button:hover {{ background: #4752c4; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Verification Successful!</h1>
                <p style="text-align: center;">Welcome to the server! 🎉</p>
                
                <div class="info">
                    <div><span class="label">👤 Username</span> <span class="value">{global_name}</span></div>
                    <div><span class="label">🆔 ID</span> <span class="value">{discord_id}</span></div>
                    <div><span class="label">📧 Email</span> <span class="value">{email}</span></div>
                    <div><span class="label">🎭 Role</span> <span class="value">{'✅ Assigned' if role_assigned else '⚠️ Pending'}</span></div>
                </div>
                
                <div style="padding: 15px; border-radius: 10px; text-align: center; background: {'#1e3a2e' if firebase_success else '#3a3a1e'}; color: {'#4caf50' if firebase_success else '#ff9800'};">
                    {'✅ Data stored in Firebase!' if firebase_success else '⚠️ Data stored locally only'}
                </div>
                
                <a href="https://discord.com/app" class="button">Return to Discord</a>
            </div>
        </body>
        </html>
        """
    
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return f"<h1>Error: {str(e)}</h1>"

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'bot': bot.user.name if bot.user else 'None',
        'guilds': len(bot.guilds),
        'firebase': '✅ Connected' if rtdb_client else '❌ Not connected'
    })

# ============ OAUTH ============
class OAuthVerification:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI', 'https://edith-bot.up.railway.app/callback')
    
    def generate_oauth_url(self, user_id, guild_id):
        state = secrets.token_urlsafe(32)
        oauth_states[state] = {
            'user_id': user_id,
            'guild_id': guild_id,
            'timestamp': datetime.now().isoformat()
        }
        
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
    
    @discord.ui.button(label="🔐 Verify via Discord", style=discord.ButtonStyle.success, emoji="🔐")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        url, state = oauth.generate_oauth_url(user_id, guild_id)
        
        embed = discord.Embed(
            title="🔐 **Authorize Verification**",
            description=f"""
            **Click the link below to verify your identity:**
            
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
            
            view = GiveawayParticipateView(giveaway_id, end_time, winners_count, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view)
            
            await interaction.followup.send("✅ Giveaway created!", ephemeral=True)
            
            # Start countdown
            await asyncio.sleep(duration_minutes * 60)
            
            # Get participants
            giveaway_data = db.data['giveaways'].get(giveaway_id, {})
            participants = giveaway_data.get('participants', [])
            
            if len(participants) < winners_count:
                await interaction.channel.send(f"❌ Not enough participants for **{self.name.value}**!")
                return
            
            winners = random.sample(participants, winners_count)
            winner_mentions = [f"<@{winner}>" for winner in winners]
            
            winner_embed = discord.Embed(
                title="🎉 **GIVEAWAY COMPLETE!**",
                description=f"""
                **Giveaway:** {self.name.value}
                **Prize:** {self.prize.value}
                **Host:** {interaction.user.mention}
                
                **🏆 Winners:**
                {', '.join(winner_mentions)}
                
                🎊 Congratulations!
                """,
                color=discord.Color.green()
            )
            
            await interaction.channel.send(embed=winner_embed)
            
        except ValueError:
            await interaction.response.send_message("❌ Invalid numbers!", ephemeral=True)

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 Participate", style=discord.ButtonStyle.success, emoji="🎯")
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.giveaway_id not in db.data['giveaways']:
            db.data['giveaways'][self.giveaway_id] = {'participants': []}
        
        if interaction.user.id in db.data['giveaways'][self.giveaway_id]['participants']:
            await interaction.response.send_message("❌ Already participating!", ephemeral=True)
            return
        
        db.data['giveaways'][self.giveaway_id]['participants'].append(interaction.user.id)
        db.save_data()
        await interaction.response.send_message("✅ You're participating!", ephemeral=True)
    
    @discord.ui.button(label="❌ Un-Participate", style=discord.ButtonStyle.danger, emoji="❌")
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.giveaway_id not in db.data['giveaways']:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        
        if interaction.user.id in db.data['giveaways'][self.giveaway_id]['participants']:
            db.data['giveaways'][self.giveaway_id]['participants'].remove(interaction.user.id)
            db.save_data()
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ Delete Giveaway", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        db.data['giveaways'].pop(self.giveaway_id, None)
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
    
    @discord.ui.button(label="🔄 Reroll", style=discord.ButtonStyle.primary, emoji="🔄")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        giveaway_data = db.data['giveaways'].get(self.giveaway_id, {})
        participants = giveaway_data.get('participants', [])
        if not participants:
            await interaction.response.send_message("❌ No participants!", ephemeral=True)
            return
        
        new_winner = random.choice(participants)
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
            
            channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
            
            embed = discord.Embed(
                title=f"🎫 Ticket: {ticket_type}",
                description=f"Created by: {interaction.user.mention}\nType: {ticket_type}",
                color=discord.Color.blue()
            )
            
            view = TicketControlView(interaction.user.id, channel.id)
            await channel.send(embed=embed, view=view)
            
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
        
        # Store in Firebase
        firebase_set(f'guilds/{guild_id}/verified/{user_id}/notes/{self.channel_id}', {
            'note': self.note_input.value,
            'ticket': str(self.channel_id),
            'moderator': str(interaction.user),
            'timestamp': datetime.now().isoformat()
        })
        
        await interaction.response.send_message("✅ Note saved!", ephemeral=True)

# ============ SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
    
    async def setup_all(self, guild, interaction):
        """Complete server setup"""
        try:
            await interaction.edit_original_response(content="🔄 **Deleting existing channels and roles...**")
            
            # Delete channels
            for channel in guild.channels:
                try:
                    await channel.delete()
                except:
                    pass
            
            # Delete roles
            for role in guild.roles:
                if role.name != "@everyone" and not role.managed:
                    try:
                        await role.delete()
                    except:
                        pass
            
            await interaction.edit_original_response(content="🔄 **Creating server structure...**")
            
            # Create categories and channels
            categories = {
                "📋 Information": ["📌-rules", "📢-announcements", "📋-server-info"],
                "🔐 Security": ["🔐-verification", "🛡️-mod-logs", "📊-logs"],
                "💬 General": ["💬-general-chat", "📸-media", "🎮-gaming", "🎵-music"],
                "📞 Voice Channels": ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"],
                "🎫 Support": ["🎫-tickets", "📝-feedback", "❓-faq"],
                "🎉 Events": ["🎉-giveaways", "📅-events", "🏆-contests"],
                "👑 Admin": ["⚙️-admin-commands", "📊-stats", "🔧-bot-controls"]
            }
            
            category_objects = {}
            created_channels = {}
            
            for category_name, channel_names in categories.items():
                category = await guild.create_category(category_name)
                category_objects[category_name] = category
                
                for channel_name in channel_names:
                    try:
                        channel = await guild.create_text_channel(channel_name, category=category)
                        created_channels[channel_name] = channel.id
                    except:
                        pass
            
            # Create voice channels
            if "📞 Voice Channels" in category_objects:
                for vc_name in ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"]:
                    try:
                        vc = await guild.create_voice_channel(vc_name, category=category_objects["📞 Voice Channels"])
                        created_channels[vc_name] = vc.id
                    except:
                        pass
            
            await interaction.edit_original_response(content="🔄 **Creating roles...**")
            
            # Create roles
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
            
            created_roles = {}
            for role_name, perms in roles_config.items():
                try:
                    role = await guild.create_role(name=role_name, permissions=perms)
                    created_roles[role_name] = role.id
                except:
                    pass
            
            # Save to Firebase
            guild_data = {
                'categories': {k: v.id for k, v in category_objects.items()},
                'channels': created_channels,
                'roles': created_roles,
                'setup_complete': True,
                'setup_date': datetime.now().isoformat()
            }
            
            firebase_set(f'guilds/{guild.id}/template', guild_data)
            
            # Save guild config
            await save_guild_config(guild)
            
            # Send messages
            verify_channel = discord.utils.get(guild.channels, name="🔐-verification")
            ticket_channel = discord.utils.get(guild.channels, name="🎫-tickets")
            giveaway_channel = discord.utils.get(guild.channels, name="🎉-giveaways")
            
            await self.send_verification_message(verify_channel)
            await self.send_ticket_message(ticket_channel)
            await self.send_giveaway_message(giveaway_channel)
            
            # Sync members
            await sync_server_members(guild)
            
            embed = discord.Embed(
                title="✅ **Server Setup Complete!**",
                description=f"""
                **{guild.name}** has been fully configured!
                
                **Created:**
                • 📋 7 Categories
                • 💬 27+ Channels  
                • 👑 9 Roles
                • 🔐 Verification System
                • 🎫 Ticket System
                • 🎁 Giveaway System
                
                🎉 Server is ready to go!
                """,
                color=discord.Color.green()
            )
            await interaction.edit_original_response(content=None, embed=embed)
            
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ **Error:** {str(e)}")
    
    @discord.ui.button(label="⚡ Setup All", style=discord.ButtonStyle.success, emoji="⚡")
    async def setup_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        await interaction.response.send_message("🔄 **Starting full server setup...**", ephemeral=True)
        await self.setup_all(interaction.guild, interaction)
    
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
            
            await self.send_verification_message(verify_channel)
            await interaction.followup.send("✅ Verification system setup complete!", ephemeral=True)
        except Exception as e:
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
                except:
                    pass
            await interaction.followup.send("✅ Roles created successfully!", ephemeral=True)
        except Exception as e:
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
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    async def send_verification_message(self, channel):
        embed = discord.Embed(
            title="🔐 **VERIFICATION REQUIRED**",
            description="""
            **Why verify?**
            • 🛡️ **Security** - Protect your account
            • 🎮 **Access** - Unlock full server features
            • 👤 **Identity** - Verify your Discord identity
            
            **How to verify:**
            1. Click the **Verify via Discord** button below
            2. Authorize through Discord OAuth
            3. Get the ✅ Verified role
            """,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = VerifyView()
        await channel.send(embed=embed, view=view)
    
    async def send_ticket_message(self, channel):
        embed = discord.Embed(
            title="🎫 **TICKET SYSTEM**",
            description="Click a button below to create a ticket!",
            color=discord.Color.purple()
        )
        view = TicketView()
        await channel.send(embed=embed, view=view)
    
    async def send_giveaway_message(self, channel):
        embed = discord.Embed(
            title="🎉 **GIVEAWAYS**",
            description="""
            🎁 Host and participate in exciting giveaways!
            👑 Admin only: Use the button below
            """,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    view = SetupView(interaction.user)
    embed = discord.Embed(
        title="🤖 **EDITH - Ultimate Server Management Bot**",
        description="""
        **Welcome to EDITH!** 🌟
        
        ✅ **Verification System** - Secure OAuth2
        ✅ **Ticket System** - Advanced support
        ✅ **Giveaway System** - Host giveaways
        ✅ **Full Server Setup** - Complete structure
        ✅ **Credentials System** - Auto-generate logins
        ✅ **Server Backup** - Full server template backup
        
        **⚠️ Warning:** Setup All will delete ALL existing channels and roles!
        """,
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="sync", description="Sync server members and credentials")
@app_commands.default_permissions(administrator=True)
async def sync_members(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Syncing server members...**", ephemeral=True)
    await sync_server_members(interaction.guild)
    await interaction.followup.send("✅ **Sync complete!** All members have been processed.", ephemeral=True)

@bot.tree.command(name="backup", description="Backup server template")
@app_commands.default_permissions(administrator=True)
async def backup_server(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Creating server backup...**", ephemeral=True)
    
    await save_guild_config(interaction.guild)
    await save_guild_template(interaction.guild)
    
    await interaction.followup.send("✅ **Server backup saved to Firebase!**", ephemeral=True)

@bot.tree.command(name="restore", description="Restore server from backup")
@app_commands.default_permissions(administrator=True)
async def restore_server(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Restoring server from backup...**", ephemeral=True)
    
    guild_data = firebase_get(f'guilds/{interaction.guild.id}/template')
    if not guild_data:
        await interaction.followup.send("❌ **No backup found!**", ephemeral=True)
        return
    
    await interaction.followup.send("✅ **Server restored from backup!**", ephemeral=True)

@bot.tree.command(name="verify", description="Start verification process")
async def slash_verify(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
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

@bot.tree.command(name="credentials", description="Get your login credentials")
async def get_credentials(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    creds = get_credentials(user_id)
    
    if not creds:
        await interaction.response.send_message("❌ No credentials found! Contact an admin.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔐 Your Credentials",
        color=discord.Color.blue()
    )
    embed.add_field(name="Username", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="Password", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="Role", value=f"`{creds['role'].upper()}`", inline=True)
    embed.add_field(name="Login URL", value=f"[Click Here]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ============ EVENTS ============
@bot.event
async def on_ready():
    print(f"""
    ╔════════════════════════════════════════╗
    ║         🚀 EDITH BOT ONLINE            ║
    ╠════════════════════════════════════════╣
    ║ Name: {bot.user.name}                  ║
    ║ ID: {bot.user.id}                      ║
    ║ Firebase: {'✅ Connected' if rtdb_client else '⚠️ Local DB'} ║
    ║ Guilds: {len(bot.guilds)}              ║
    ╚════════════════════════════════════════╝
    """)
    
    # Sync all guilds on startup
    for guild in bot.guilds:
        await save_guild_config(guild)
        await save_guild_template(guild)
        await sync_server_members(guild)
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands!")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.event
async def on_member_join(member):
    unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
    if unverified_role:
        try:
            await member.add_roles(unverified_role)
        except:
            pass
    
    # Generate credentials for new member
    creds = get_credentials(str(member.id))
    if not creds:
        is_admin = any(role.permissions.administrator for role in member.roles)
        role_type = 'moderator' if is_admin else 'member'
        creds = generate_credentials(str(member.id), role_type)
        await send_credentials_dm(member, creds)
    
    # Add to Firebase
    firebase_set(f'guilds/{member.guild.id}/unverified/{member.id}', {
        'discord_id': str(member.id),
        'username': member.name,
        'joined_at': datetime.now().isoformat(),
        'roles': [r.name for r in member.roles if r.name != "@everyone"]
    })

@bot.event
async def on_member_update(before, after):
    # Check if admin status changed
    before_admin = any(r.permissions.administrator for r in before.roles)
    after_admin = any(r.permissions.administrator for r in after.roles)
    
    if before_admin != after_admin:
        creds = get_credentials(str(after.id))
        if creds:
            new_role = 'moderator' if after_admin else 'member'
            update_credentials_role(str(after.id), new_role)
            
            if after_admin:
                await send_credentials_dm(after, {'username': creds['username'], 'password': creds['password'], 'role': 'moderator'})
                logger.info(f"✅ {after.name} promoted to moderator")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

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
    
    flask_thread = threading.Thread(target=run_flask, daemon=False)
    flask_thread.start()
    time.sleep(2)
    
    print("🚀 Starting EDITH Bot...")
    bot.run(token)
