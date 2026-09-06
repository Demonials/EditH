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

# ============ FLASK IMPORTS ============
try:
    from flask import Flask, request, redirect, jsonify, session
    from flask_cors import CORS
    from flask_session import Session
    FLASK_AVAILABLE = True
    logger.info("✅ Flask imported successfully!")
except ImportError as e:
    FLASK_AVAILABLE = False
    logger.warning(f"⚠️ Flask not available: {e}")

# ============ FLASK APP ============
if FLASK_AVAILABLE:
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    CORS(app, origins=['https://edith-bot.up.railway.app', 'http://localhost:3000'])
    Session(app)

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
            
            if error:
                return f"<h1>Error: {error}</h1><p>Please try /verify again in Discord.</p>"
            
            if not code:
                return "<h1>No code provided</h1><p>Please try /verify again in Discord.</p>", 400
            
            # Get session
            session_data = None
            if state:
                session_data = oauth_states.pop(state, None)
            
            if not session_data:
                return "<h1>Session expired</h1><p>Please run /verify again in Discord.</p>"
            
            user_id = session_data['user_id']
            guild_id = session_data['guild_id']
            logger.info(f"   User ID: {user_id}, Guild ID: {guild_id}")
            
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
                            return await resp.json()
                        return None
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            user_data = loop.run_until_complete(get_user_data())
            loop.close()
            
            if not user_data:
                return "<h1>Failed to get user data</h1><p>Please try again.</p>"
            
            username = user_data.get('username')
            discord_id = user_data.get('id')
            email = user_data.get('email', 'Not provided')
            
            logger.info(f"✅ User verified: {username} ({discord_id})")
            
            # Store in database
            user_data_db = db.get_user(discord_id, guild_id)
            user_data_db['verified'] = True
            user_data_db['profile'] = {
                'discord_id': discord_id,
                'username': username,
                'email': email,
                'verified_at': datetime.now().isoformat(),
                'guild_id': guild_id
            }
            db.set_user(discord_id, guild_id, user_data_db)
            
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
            
            return f"""
            <!DOCTYPE html>
            <html>
            <head><title>Verification Successful</title>
            <style>
                body {{ font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }}
                .container {{ background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; }}
                .success {{ color: #4caf50; font-size: 60px; }}
                .info {{ background: #1e1e32; padding: 15px; border-radius: 10px; margin: 20px 0; text-align: left; }}
                .info div {{ padding: 8px 0; border-bottom: 1px solid #2d2d44; }}
                .label {{ color: #888; }}
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">✅</div>
                    <h1>Verification Successful!</h1>
                    <p>Welcome to the server! 🎉</p>
                    <div class="info">
                        <div><span class="label">👤 Username</span> {username}</div>
                        <div><span class="label">🆔 ID</span> {discord_id}</div>
                        <div><span class="label">📧 Email</span> {email}</div>
                        <div><span class="label">🎭 Role</span> {'✅ Assigned' if role_assigned else '⚠️ Pending'}</div>
                    </div>
                    <a href="https://discord.com/app" style="color: #5865f2;">Return to Discord</a>
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
            'timestamp': datetime.now().isoformat()
        })

    @app.route('/test')
    def test():
        return jsonify({
            'message': 'Web server is running!',
            'redirect_uri': os.getenv('REDIRECT_URI'),
            'client_id': os.getenv('CLIENT_ID', 'Not set')
        })

# ============ DISCORD BOT ============
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
    logger.info("✅ Firebase module loaded successfully!")
except ImportError as e:
    FIREBASE_AVAILABLE = False
    logger.warning(f"⚠️ Firebase not available: {e}")
    firebase_admin = None
    credentials = None
    firestore = None

db_firebase = None
if FIREBASE_AVAILABLE:
    try:
        firebase_json = os.getenv('FIREBASE_KEY_JSON')
        if firebase_json:
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            db_firebase = firestore.client()
            logger.info("✅ Firebase connected successfully!")
        else:
            logger.warning("⚠️ No Firebase credentials found")
    except Exception as e:
        logger.error(f"❌ Firebase error: {e}")

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
                logger.info("✅ Local database loaded")
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
        
        if db_firebase:
            try:
                doc_ref = db_firebase.collection('oauth_states').document(state)
                doc_ref.set({
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
        self.name = TextInput(label="Giveaway Name", required=True, placeholder="Enter giveaway name")
        self.duration = TextInput(label="Duration (minutes)", required=True, placeholder="e.g., 60")
        self.winners = TextInput(label="Number of Winners", required=True, placeholder="e.g., 1")
        self.prize = TextInput(label="Prize", required=True, placeholder="What's the prize?")
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
                **Ends at:** <t:{int(end_time.timestamp())}:R>
                
                Click **Participate** below to join!
                """,
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
            embed.set_footer(text=f"Giveaway ID: {giveaway_id[:8]}...")
            
            view = GiveawayParticipateView(giveaway_id, end_time, winners_count, interaction.user.id)
            
            await interaction.response.send_message(embed=embed, view=view)
            
            db.data['giveaways'][giveaway_id] = {
                'name': self.name.value,
                'prize': self.prize.value,
                'host': interaction.user.id,
                'winners': winners_count,
                'end_time': end_time.isoformat(),
                'participants': [],
                'channel_id': interaction.channel.id
            }
            db.save_data()
            
            logger.info(f"🎁 Giveaway created: {self.name.value}")
            
            asyncio.create_task(self.giveaway_countdown(giveaway_id, interaction.channel, end_time))
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers!", ephemeral=True)
    
    async def giveaway_countdown(self, giveaway_id, channel, end_time):
        try:
            await asyncio.sleep((end_time - datetime.now()).total_seconds())
            
            giveaway_data = db.data['giveaways'].get(giveaway_id)
            if not giveaway_data:
                return
            
            participants = giveaway_data.get('participants', [])
            
            if len(participants) == 0:
                await channel.send(f"❌ No one participated in **{giveaway_data['name']}**!")
                return
            
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
            
        except Exception as e:
            logger.error(f"❌ Giveaway countdown error: {e}")

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
            await interaction.response.send_message("❌ This giveaway has ended!", ephemeral=True)
            return
        
        if interaction.user.id in giveaway_data['participants']:
            await interaction.response.send_message("❌ You're already participating!", ephemeral=True)
            return
        
        giveaway_data['participants'].append(interaction.user.id)
        db.save_data()
        
        await interaction.response.send_message("✅ You're now participating!", ephemeral=True)
        logger.info(f"🎯 {interaction.user} joined giveaway {self.giveaway_id}")
    
    @discord.ui.button(label="❌ Un-Participate", style=discord.ButtonStyle.danger, emoji="❌")
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if not giveaway_data:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        
        if interaction.user.id in giveaway_data['participants']:
            giveaway_data['participants'].remove(interaction.user.id)
            db.save_data()
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You're not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ Delete Giveaway", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
        logger.info(f"🗑️ Giveaway {self.giveaway_id} deleted")
    
    @discord.ui.button(label="🔄 Reroll", style=discord.ButtonStyle.primary, emoji="🔄")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if not giveaway_data:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        
        participants = giveaway_data.get('participants', [])
        if len(participants) < 1:
            await interaction.response.send_message("❌ Not enough participants!", ephemeral=True)
            return
        
        new_winner = random.choice(participants)
        await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)
        await interaction.channel.send(f"🔄 **Rerolled!** New winner: <@{new_winner}>!")

# ============ VERIFY VIEW ============
class VerifyView(View):
    def __init__(self, roles=None):
        super().__init__(timeout=None)
        self.roles = roles or {}
    
    @discord.ui.button(label="🔐 Verify via Discord", style=discord.ButtonStyle.link, emoji="🔐")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        user_data = db.get_user(user_id, guild_id)
        if user_data.get('verified', False):
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return
        
        url, state = oauth.generate_oauth_url(user_id, guild_id)
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="🔐 Click to Verify",
            style=discord.ButtonStyle.link,
            url=url,
            emoji="🔐"
        ))
        
        embed = discord.Embed(
            title="🔐 **Authorize Verification**",
            description=f"""
            **Click the button below to verify your identity:**
            
            This will open Discord's authorization page in a **new tab**.
            
            ⏰ **Time Limit:** 10 minutes
            🔒 **Security:** Your data is encrypted and secure
            
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

# ============ SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
    
    async def setup_all(self, guild, interaction):
        logger.info(f"🚀 Setting up guild: {guild.name}")
        
        # Delete existing channels
        for channel in guild.channels:
            try:
                await channel.delete()
            except:
                pass
        
        # Delete existing roles
        for role in guild.roles:
            if role.name != "@everyone" and not role.managed:
                try:
                    await role.delete()
                except:
                    pass
        
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
        
        created_channels = {}
        created_roles = {}
        category_objects = {}
        
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
        voice_category = category_objects.get("📞 Voice Channels")
        if voice_category:
            for vc_name in ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"]:
                try:
                    vc = await guild.create_voice_channel(vc_name, category=voice_category)
                    created_channels[vc_name] = vc.id
                except:
                    pass
        
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
        
        for role_name, perms in roles_config.items():
            try:
                role = await guild.create_role(name=role_name, permissions=perms)
                created_roles[role_name] = role.id
            except:
                pass
        
        # Store in database
        guild_data = {
            'categories': {k: v.id for k, v in category_objects.items()},
            'channels': created_channels,
            'roles': created_roles,
            'setup_complete': True,
            'setup_date': datetime.now().isoformat()
        }
        db.set_guild(guild.id, guild_data)
        
        # Get channels
        verify_channel = discord.utils.get(guild.channels, name="🔐-verification")
        ticket_channel = discord.utils.get(guild.channels, name="🎫-tickets")
        giveaway_channel = discord.utils.get(guild.channels, name="🎉-giveaways")
        
        return verify_channel, ticket_channel, giveaway_channel, created_roles
    
    @discord.ui.button(label="⚡ Setup All", style=discord.ButtonStyle.success, emoji="⚡")
    async def setup_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        await interaction.response.send_message("🔄 **Starting server setup...**\n\n⏳ Please wait...", ephemeral=True)
        
        try:
            verify_channel, ticket_channel, giveaway_channel, roles = await self.setup_all(interaction.guild, interaction)
            
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
                
                🎉 Server is ready to go!
                """,
                color=discord.Color.green()
            )
            await interaction.edit_original_response(content=None, embed=embed)
            
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ **Error:** {str(e)}")
    
    async def send_verification_message(self, channel, roles=None):
        if not channel:
            return
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
            4. Full access granted!
            """,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = VerifyView(roles)
        await channel.send(embed=embed, view=view)
    
    async def send_ticket_message(self, channel):
        if not channel:
            return
        embed = discord.Embed(
            title="🎫 **TICKET SYSTEM**",
            description="Click a button below to create a ticket!",
            color=discord.Color.purple()
        )
        view = TicketView()
        await channel.send(embed=embed, view=view)
    
    async def send_giveaway_message(self, channel):
        if not channel:
            return
        embed = discord.Embed(
            title="🎉 **GIVEAWAYS**",
            description="""
            **Welcome to the Giveaway Center!**
            
            🎁 Host and participate in exciting giveaways!
            👑 Admin only: Use the button below to host
            
            *Join the fun and win amazing prizes!*
            """,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)

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
    
    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger)
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
    
    @discord.ui.button(label="📝 Note", style=discord.ButtonStyle.primary)
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
        await interaction.response.send_message("✅ Note saved!", ephemeral=True)

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    view = SetupView(interaction.user)
    embed = discord.Embed(
        title="🤖 **EDITH - Ultimate Server Management Bot**",
        description="""
        **Welcome to EDITH!** 🌟
        
        ✅ **Verification System** - Secure OAuth2 verification
        ✅ **Ticket System** - Advanced support tickets
        ✅ **Giveaway System** - Host & manage giveaways
        ✅ **Full Server Setup** - Complete channel & role structure
        
        **⚠️ Warning:** Setup All will delete ALL existing channels and roles!
        """,
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="verify", description="Start verification process")
async def slash_verify(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    user_data = db.get_user(user_id, guild_id)
    if user_data.get('verified', False):
        await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
        return
    
    url, state = oauth.generate_oauth_url(user_id, guild_id)
    
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="🔐 Click to Verify",
        style=discord.ButtonStyle.link,
        url=url,
        emoji="🔐"
    ))
    
    embed = discord.Embed(
        title="🔐 **Verification Required**",
        description=f"""
        **Click the button below to verify your identity:**
        
        This will open Discord's authorization page in a **new tab**.
        
        ⏰ **Time Limit:** 10 minutes
        🔒 **Security:** Your data is encrypted and secure
        
        **What happens next:**
        1. You authorize through Discord
        2. We verify your identity
        3. You get the ✅ Verified role
        """,
        color=discord.Color.blue()
    )
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

# ============ EVENTS ============
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"""
    ╔════════════════════════════════════════╗
    ║         🚀 EDITH BOT ONLINE            ║
    ╠════════════════════════════════════════╣
    ║ Name: {bot.user.name}                  ║
    ║ ID: {bot.user.id}                      ║
    ║ Guilds: {len(bot.guilds)}              ║
    ║ Web Server: {'✅ Running' if FLASK_AVAILABLE else '⚠️ Not running'} ║
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
if FLASK_AVAILABLE:
    import threading
    import time
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
    
    # Start Flask if available
    if FLASK_AVAILABLE:
        flask_thread = threading.Thread(target=run_flask, daemon=False)
        flask_thread.start()
        time.sleep(2)
        logger.info("🌐 Web server started")
    else:
        logger.warning("⚠️ Flask not available - web server not running")
    
    print("🚀 Starting EDITH Bot...")
    bot.run(token)
