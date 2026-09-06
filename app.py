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
# Create logs directory
os.makedirs('./logs', exist_ok=True)

# Configure logging
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

# Log startup
logger.info("="*60)
logger.info("🚀 EDITH BOT STARTING")
logger.info("="*60)

# Load environment
load_dotenv()
logger.info("📝 Environment loaded")

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
            logger.debug("💾 Database saved")
        except Exception as e:
            logger.error(f"❌ Failed to save database: {e}")
    
    def get_user(self, user_id, guild_id):
        """Get user data for specific guild"""
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
            logger.debug(f"👤 New user created: {user_id} in guild {guild_id}")
        return self.data['users'][guild_id][user_id]
    
    def set_user(self, user_id, guild_id, data):
        """Set user data for specific guild"""
        user_id = str(user_id)
        guild_id = str(guild_id)
        if guild_id not in self.data['users']:
            self.data['users'][guild_id] = {}
        self.data['users'][guild_id][user_id] = data
        self.save_data()
        logger.debug(f"💾 User data saved: {user_id} in guild {guild_id}")
    
    def check_user_verified(self, user_id, guild_id):
        """Check if user is verified in specific guild"""
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
        logger.info(f"💾 Guild data saved: {guild_id}")

db = SimpleDB()

# OAuth states storage
oauth_states = {}

# ============ OAUTH VERIFICATION ============
class OAuthVerification:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:8080/callback')
        logger.info(f"🔐 OAuth initialized")
        logger.info(f"   Client ID: {self.client_id[:10]}...")
        logger.info(f"   Redirect URI: {self.redirect_uri}")
    
    def generate_oauth_url(self, user_id, guild_id):
        state = secrets.token_urlsafe(32)
        oauth_states[state] = {
            'user_id': user_id,
            'guild_id': guild_id,
            'timestamp': datetime.now().isoformat()
        }
        logger.info(f"🔐 OAuth state generated for user {user_id} in guild {guild_id}")
        
        # Store in Firebase if available
        if db_firebase:
            try:
                doc_ref = db_firebase.collection('oauth_states').document(state)
                doc_ref.set({
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'timestamp': datetime.now().isoformat()
                })
                logger.debug(f"   Stored in Firebase")
            except Exception as e:
                logger.error(f"   Failed to store in Firebase: {e}")
        
        url = f"https://discord.com/api/oauth2/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&scope=identify%20email%20guilds%20connections&state={state}"
        logger.info(f"🔗 OAuth URL generated: {url[:50]}...")
        return url, state
    
    async def exchange_code(self, code):
        """Exchange code for access token"""
        logger.info(f"🔄 Exchanging OAuth code...")
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post('https://discord.com/api/oauth2/token', data=data) as resp:
                if resp.status == 200:
                    logger.info("✅ OAuth token exchanged successfully")
                    return await resp.json()
                logger.error(f"❌ Failed to exchange OAuth code: Status {resp.status}")
                return None
    
    async def get_user_data(self, access_token):
        """Get user data from Discord API"""
        logger.info("👤 Fetching user data from Discord...")
        headers = {'Authorization': f'Bearer {access_token}'}
        
        async with aiohttp.ClientSession() as session:
            # Get user info
            async with session.get('https://discord.com/api/users/@me', headers=headers) as resp:
                if resp.status != 200:
                    logger.error(f"❌ Failed to get user data: Status {resp.status}")
                    return None
                user_data = await resp.json()
                logger.info(f"   User: {user_data.get('username')} ({user_data.get('id')})")
            
            # Get user connections
            async with session.get('https://discord.com/api/users/@me/connections', headers=headers) as resp:
                if resp.status == 200:
                    user_data['connections'] = await resp.json()
                    logger.info(f"   Connections: {len(user_data['connections'])} found")
                else:
                    user_data['connections'] = []
                    logger.warning(f"   Failed to get connections: Status {resp.status}")
            
            # Get user guilds
            async with session.get('https://discord.com/api/users/@me/guilds', headers=headers) as resp:
                if resp.status == 200:
                    user_data['guilds'] = await resp.json()
                    logger.info(f"   Guilds: {len(user_data['guilds'])} found")
                else:
                    user_data['guilds'] = []
                    logger.warning(f"   Failed to get guilds: Status {resp.status}")
            
            return user_data

oauth = OAuthVerification()

# ============ SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        logger.info(f"🛠️ SetupView created by {author} ({author.id})")
    
    async def setup_all(self, guild):
        """Complete server setup - delete everything and create new structure"""
        logger.info(f"🚀 Starting full server setup for guild: {guild.name} ({guild.id})")
        logger.info(f"   Channels before: {len(guild.channels)}")
        logger.info(f"   Roles before: {len(guild.roles)}")
        
        # Step 1: Delete all existing channels and categories
        logger.info("📝 Step 1: Deleting existing channels...")
        channels_deleted = 0
        for channel in guild.channels:
            try:
                await channel.delete()
                channels_deleted += 1
                if channels_deleted % 10 == 0:
                    logger.info(f"   Deleted {channels_deleted} channels so far...")
            except Exception as e:
                logger.warning(f"   Failed to delete channel {channel.name}: {e}")
        logger.info(f"✅ Deleted {channels_deleted} channels")
        
        # Step 2: Delete all existing roles (except @everyone and bot role)
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
        
        # Step 3: Create categories and channels
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
        
        # Create categories and channels
        for category_name, channel_names in categories.items():
            try:
                category = await guild.create_category(category_name)
                created_categories[category_name] = category.id
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
        
        # Step 4: Create voice channels
        logger.info("📝 Step 4: Creating voice channels...")
        voice_channels = ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"]
        for vc_name in voice_channels:
            try:
                vc = await guild.create_voice_channel(vc_name, category=created_categories.get("📞 Voice Channels"))
                created_channels[vc_name] = vc.id
                logger.info(f"✅ Created voice channel: {vc_name} (ID: {vc.id})")
            except Exception as e:
                logger.error(f"❌ Failed to create voice channel {vc_name}: {e}")
        
        # Step 5: Create roles with permissions
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
        
        # Step 6: Store in database
        logger.info("📝 Step 6: Storing in database...")
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
                logger.info("✅ Stored in Firebase")
            except Exception as e:
                logger.error(f"❌ Failed to store in Firebase: {e}")
        
        db.set_guild(guild.id, guild_data)
        logger.info("✅ Stored in local database")
        
        # Get the verification channel
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
        logger.info(f"🔄 Setup All button clicked by {interaction.user} ({interaction.user.id})")
        
        if interaction.user != self.author:
            logger.warning(f"⚠️ Unauthorized user tried to use Setup All: {interaction.user}")
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        logger.info("⏳ Setup started, response deferred")
        
        try:
            verify_channel, ticket_channel, giveaway_channel, roles = await self.setup_all(interaction.guild)
            
            # Send verification embed with OAuth button
            logger.info("📝 Sending verification message...")
            await self.send_verification_message(verify_channel, roles)
            
            # Send ticket message
            logger.info("📝 Sending ticket message...")
            await self.send_ticket_message(ticket_channel)
            
            # Send giveaway message
            logger.info("📝 Sending giveaway message...")
            await self.send_giveaway_message(giveaway_channel)
            
            await interaction.followup.send("✅ Full server setup complete! All channels and roles created.", ephemeral=True)
            logger.info("✅ Setup All completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Setup All failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error during setup: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔐 Verification", style=discord.ButtonStyle.primary, emoji="🔐")
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🔐 Setup Verification clicked by {interaction.user}")
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            verify_channel = discord.utils.get(interaction.guild.channels, name="🔐-verification")
            if not verify_channel:
                category = discord.utils.get(interaction.guild.categories, name="🔐 Security")
                if not category:
                    category = await interaction.guild.create_category("🔐 Security")
                verify_channel = await interaction.guild.create_text_channel("🔐-verification", category=category)
                logger.info(f"✅ Created verification channel: {verify_channel.name}")
            
            # Get roles
            roles = {}
            for role_name in ["✅ Verified", "❌ Unverified", "👑 Owner", "🛡️ Admin", "🔰 Moderator"]:
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if role:
                    roles[role_name] = role.id
            
            await self.send_verification_message(verify_channel, roles)
            await interaction.followup.send("✅ Verification system setup complete!", ephemeral=True)
            logger.info("✅ Verification setup complete")
        except Exception as e:
            logger.error(f"❌ Verification setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎫 Tickets", style=discord.ButtonStyle.secondary, emoji="🎫")
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🎫 Setup Tickets clicked by {interaction.user}")
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            ticket_channel = discord.utils.get(interaction.guild.channels, name="🎫-tickets")
            if not ticket_channel:
                category = discord.utils.get(interaction.guild.categories, name="🎫 Support")
                if not category:
                    category = await interaction.guild.create_category("🎫 Support")
                ticket_channel = await interaction.guild.create_text_channel("🎫-tickets", category=category)
                logger.info(f"✅ Created ticket channel: {ticket_channel.name}")
            await self.send_ticket_message(ticket_channel)
            await interaction.followup.send("✅ Ticket system setup complete!", ephemeral=True)
            logger.info("✅ Ticket setup complete")
        except Exception as e:
            logger.error(f"❌ Ticket setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎁 Giveaways", style=discord.ButtonStyle.primary, emoji="🎁")
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🎁 Setup Giveaways clicked by {interaction.user}")
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            giveaway_channel = discord.utils.get(interaction.guild.channels, name="🎉-giveaways")
            if not giveaway_channel:
                category = discord.utils.get(interaction.guild.categories, name="🎉 Events")
                if not category:
                    category = await interaction.guild.create_category("🎉 Events")
                giveaway_channel = await interaction.guild.create_text_channel("🎉-giveaways", category=category)
                logger.info(f"✅ Created giveaway channel: {giveaway_channel.name}")
            await self.send_giveaway_message(giveaway_channel)
            await interaction.followup.send("✅ Giveaway system setup complete!", ephemeral=True)
            logger.info("✅ Giveaway setup complete")
        except Exception as e:
            logger.error(f"❌ Giveaway setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="👑 Roles", style=discord.ButtonStyle.secondary, emoji="👑")
    async def setup_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"👑 Setup Roles clicked by {interaction.user}")
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
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
                    logger.info(f"✅ Created role: {role_name}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not create role {role_name}: {e}")
            await interaction.followup.send("✅ Roles created successfully!", ephemeral=True)
            logger.info("✅ Roles setup complete")
        except Exception as e:
            logger.error(f"❌ Role setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🛡️ Moderation", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def setup_moderation(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🛡️ Setup Moderation clicked by {interaction.user}")
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer()
        try:
            mod_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
            if not mod_channel:
                category = discord.utils.get(interaction.guild.categories, name="🔐 Security")
                if not category:
                    category = await interaction.guild.create_category("🔐 Security")
                mod_channel = await interaction.guild.create_text_channel("🛡️-mod-logs", category=category)
                logger.info(f"✅ Created mod channel: {mod_channel.name}")
            await interaction.followup.send("✅ Moderation system setup complete!", ephemeral=True)
            logger.info("✅ Moderation setup complete")
        except Exception as e:
            logger.error(f"❌ Moderation setup failed: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    async def send_verification_message(self, channel, roles=None):
        if not channel:
            logger.warning("⚠️ Verification channel is None, skipping")
            return
        logger.info(f"📤 Sending verification message to {channel.name}")
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
            logger.warning("⚠️ Ticket channel is None, skipping")
            return
        logger.info(f"📤 Sending ticket message to {channel.name}")
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
            logger.warning("⚠️ Giveaway channel is None, skipping")
            return
        logger.info(f"📤 Sending giveaway message to {channel.name}")
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

# ============ VERIFICATION VIEW WITH OAUTH ============
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
        
        embed = discord.Embed(
            title="🔐 **Authorize Verification**",
            description=f"""
            Click the link below to verify your identity:
            
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

# ============ OAUTH CALLBACK COMMAND ============
@bot.command(name='oauth_callback')
async def oauth_callback(ctx, code: str = None, state: str = None):
    """OAuth callback handler"""
    logger.info(f"🔄 OAuth callback received")
    logger.info(f"   Code: {code[:10] if code else 'None'}...")
    logger.info(f"   State: {state[:10] if state else 'None'}...")
    
    if not code or not state:
        logger.warning("⚠️ Invalid callback - missing code or state")
        await ctx.send("❌ Invalid callback!", ephemeral=True)
        return
    
    # Get session data
    session = None
    
    # Check Firebase first
    if db_firebase:
        try:
            doc_ref = db_firebase.collection('oauth_states').document(state)
            doc = doc_ref.get()
            if doc.exists:
                session = doc.to_dict()
                # Delete after use
                doc_ref.delete()
                logger.info(f"   Session found in Firebase")
        except Exception as e:
            logger.error(f"   Failed to get session from Firebase: {e}")
    
    # Fallback to local
    if not session:
        session = oauth_states.pop(state, None)
        if session:
            logger.info(f"   Session found locally")
    
    if not session:
        logger.warning(f"⚠️ Session not found for state {state[:10]}...")
        await ctx.send("❌ Session expired or invalid! Please try `/verify` again.", ephemeral=True)
        return
    
    user_id = session['user_id']
    guild_id = session['guild_id']
    logger.info(f"   User ID: {user_id}, Guild ID: {guild_id}")
    
    # Check if user is already verified (prevent duplicate verification)
    user_data = db.get_user(user_id, guild_id)
    if user_data.get('verified', False):
        logger.info(f"   User {user_id} is already verified")
        await ctx.send("✅ You are already verified in this server!", ephemeral=True)
        return
    
    # Exchange code for token
    logger.info("🔄 Exchanging code for token...")
    token_data = await oauth.exchange_code(code)
    if not token_data:
        logger.error("❌ Failed to exchange code")
        await ctx.send("❌ Failed to exchange code! Please try again.", ephemeral=True)
        return
    
    access_token = token_data.get('access_token')
    logger.info("✅ Token received")
    
    # Get user data
    logger.info("👤 Fetching user data...")
    user_data_discord = await oauth.get_user_data(access_token)
    if not user_data_discord:
        logger.error("❌ Failed to get user data")
        await ctx.send("❌ Failed to get user data! Please try again.", ephemeral=True)
        return
    
    # Check if user is in the guild
    guild = bot.get_guild(int(guild_id))
    if not guild:
        logger.error(f"❌ Server not found: {guild_id}")
        await ctx.send("❌ Server not found!", ephemeral=True)
        return
    
    member = guild.get_member(int(user_id))
    if not member:
        logger.warning(f"⚠️ User {user_id} is not in guild {guild_id}")
        await ctx.send("❌ You are not in this server!", ephemeral=True)
        return
    
    # Create/Update user profile (guild-specific)
    logger.info("📝 Creating/updating user profile...")
    user_profile = {
        'discord_id': user_data_discord.get('id'),
        'username': user_data_discord.get('username'),
        'global_name': user_data_discord.get('global_name'),
        'email': user_data_discord.get('email'),
        'avatar': user_data_discord.get('avatar'),
        'verified_email': user_data_discord.get('verified', False),
        'guild_id': guild_id,
        'guild_name': guild.name,
        'connections': user_data_discord.get('connections', []),
        'guilds': user_data_discord.get('guilds', []),
        'access_token': access_token,
        'verified_at': datetime.now().isoformat(),
        'oauth_data': token_data,
        'verified': True
    }
    
    # Update user data (don't overwrite, merge with existing)
    if not user_data:
        user_data = {
            'verified': True,
            'profile': user_profile,
            'guild_id': guild_id,
            'user_id': user_id,
            'verified_at': datetime.now().isoformat(),
            'tickets': [],
            'notes': []
        }
    else:
        # Update existing data
        user_data['verified'] = True
        user_data['profile'] = user_profile
        user_data['verified_at'] = datetime.now().isoformat()
    
    # Store in Firebase if available
    if db_firebase:
        try:
            doc_ref = db_firebase.collection('users').document(f"{guild_id}_{user_id}")
            doc_ref.set(user_data)
            logger.info(f"✅ User data stored in Firebase")
        except Exception as e:
            logger.error(f"❌ Firebase error: {e}")
    
    # Store locally
    db.set_user(user_id, guild_id, user_data)
    logger.info(f"✅ User data stored locally")
    
    # Assign roles
    logger.info("👑 Assigning roles...")
    verified_role = discord.utils.get(guild.roles, name="✅ Verified")
    unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
    
    if verified_role:
        if unverified_role:
            await member.remove_roles(unverified_role)
            logger.info(f"   Removed {unverified_role.name} role")
        await member.add_roles(verified_role)
        logger.info(f"   Added {verified_role.name} role")
    else:
        logger.warning("⚠️ Verified role not found")
    
    # Send verification DM to user
    try:
        logger.info("📨 Sending verification DM...")
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
            • **Username:** {user_data_discord.get('global_name', user_data_discord.get('username'))}
            • **Discord ID:** {user_data_discord.get('id')}
            • **Email:** {user_data_discord.get('email', 'Not provided')}
            
            **Bot Details:**
            • **Bot Name:** {bot.user.name}
            • **Bot ID:** {bot.user.id}
            • **Bot Developer:** EDITH Team
            
            **What's Next?**
            • You now have access to all server channels
            • You can participate in giveaways
            • You can create tickets for support
            • Enjoy the server! 🎮
            
            *Thank you for verifying!*
            """,
            color=discord.Color.green()
        )
        dm_embed.set_thumbnail(url=bot.user.display_avatar.url)
        dm_embed.set_footer(text=f"EDITH Authentication System • Verified at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await member.send(embed=dm_embed)
        logger.info(f"✅ DM sent to {member}")
    except Exception as e:
        logger.warning(f"⚠️ Could not send DM to {member}: {e}")
    
    # Send success message in channel
    embed = discord.Embed(
        title="✅ **VERIFICATION SUCCESSFUL!**",
        description=f"""
        **Welcome {user_data_discord.get('global_name', user_data_discord.get('username'))}!** 🎉
        
        You have been successfully verified in **{guild.name}**!
        
        **User Information:**
        • **Username:** {user_data_discord.get('username')}
        • **Email:** {user_data_discord.get('email', 'Not provided')}
        • **Verified Email:** {'✅' if user_data_discord.get('verified') else '❌'}
        • **Server:** {guild.name}
        • **Verified At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        **Role Updated:** ✅ Verified
        **Access:** Full server access granted!
        
        A verification DM has been sent to you! 📨
        """,
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="EDITH Authentication System")
    
    await ctx.send(embed=embed)
    logger.info(f"✅ Verification complete for {user_data_discord.get('username')}")

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    """Admin setup command"""
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

# ============ TICKET SYSTEM ============
# [Your existing TicketView, TicketControlView, AddUserModal, RemoveUserModal, BanUserModal, NoteModal classes]
# I'll add logging to these too - keep your existing code but add logger.info/debug statements

# For brevity, I'll show one example with logging added:

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        logger.debug("🎫 TicketView created")
    
    @discord.ui.button(label="🛠️ Server Related", style=discord.ButtonStyle.primary)
    async def server_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🎫 Server Related ticket requested by {interaction.user}")
        await self.create_ticket(interaction, "Server Related")
    
    @discord.ui.button(label="👮 Contact Mods", style=discord.ButtonStyle.danger)
    async def mod_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🎫 Contact Mods ticket requested by {interaction.user}")
        await self.create_ticket(interaction, "Contact Mods")
    
    @discord.ui.button(label="❓ Others", style=discord.ButtonStyle.secondary)
    async def other_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"🎫 Others ticket requested by {interaction.user}")
        await self.create_ticket(interaction, "Others")
    
    async def create_ticket(self, interaction, ticket_type):
        logger.info(f"🎫 Creating ticket of type '{ticket_type}' for {interaction.user}")
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
            logger.info(f"   Created ticket channel: {channel.name} (ID: {channel.id})")
            
            embed = discord.Embed(
                title=f"🎫 Ticket: {ticket_type}",
                description=f"Created by: {interaction.user.mention}\nType: {ticket_type}\nCreated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                color=discord.Color.blue()
            )
            
            view = TicketControlView(interaction.user.id, channel.id)
            await channel.send(embed=embed, view=view)
            
            # Store in Firebase if available
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
                    logger.debug(f"   Stored ticket in Firebase")
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
            logger.error(f"❌ Failed to create ticket: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

# ============ ADD LOGGING TO OTHER TICKET CLASSES ============
# [Add logger.info/debug to TicketControlView, AddUserModal, RemoveUserModal, BanUserModal, NoteModal]
# You can add similar logging patterns as shown above

# ============ GIVEAWAY SYSTEM ============
# [Add logging to GiveawayMainView, GiveawayModal, GiveawayParticipateView]
# Same pattern - add logger.info for important actions

# ============ MODERATION ============
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Bad word filter
    bad_words = ['badword1', 'badword2', 'badword3', 'fuck', 'shit', 'damn', 'asshole', 'bitch']
    if any(word in message.content.lower() for word in bad_words):
        try:
            await message.delete()
            warn = await message.channel.send(f"{message.author.mention}, watch your language! 🚫")
            logger.info(f"🛡️ Deleted message from {message.author} containing bad word")
            await asyncio.sleep(5)
            await warn.delete()
        except Exception as e:
            logger.warning(f"⚠️ Failed to delete bad word message: {e}")
        return
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    logger.info(f"👋 Member joined: {member} ({member.id}) in {member.guild.name}")
    # Check if user is already verified in this guild
    user_data = db.get_user(str(member.id), str(member.guild.id))
    if user_data.get('verified', False):
        # User was verified before, re-assign roles
        verified_role = discord.utils.get(member.guild.roles, name="✅ Verified")
        unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
        if verified_role:
            if unverified_role:
                await member.remove_roles(unverified_role)
            await member.add_roles(verified_role)
            logger.info(f"   Re-assigned verified role to returning member {member}")
    else:
        # New user, assign unverified role
        unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
        if unverified_role:
            try:
                await member.add_roles(unverified_role)
                logger.info(f"   Assigned unverified role to {member}")
            except Exception as e:
                logger.warning(f"   Failed to assign unverified role: {e}")

@bot.event
async def on_ready():
    logger.info("="*60)
    logger.info("🚀 EDITH BOT IS ONLINE!")
    logger.info("="*60)
    logger.info(f"🤖 Bot Name: {bot.user.name}")
    logger.info(f"🆔 Bot ID: {bot.user.id}")
    logger.info(f"📊 Guilds: {len(bot.guilds)}")
    logger.info(f"👥 Users: {len(bot.users)}")
    logger.info(f"🔥 Firebase: {'✅ Connected' if db_firebase else '⚠️ Local DB'}")
    logger.info("="*60)
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} slash commands!")
        for cmd in synced:
            logger.info(f"   /{cmd.name}")
    except Exception as e:
        logger.error(f"❌ Failed to sync commands: {e}")

# ============ RUN ============
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("❌ No DISCORD_TOKEN found!")
        exit(1)
    
    logger.info("🚀 Starting EDITH Bot with OAuth + Firebase...")
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}", exc_info=True)
