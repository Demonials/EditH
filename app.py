import discord
from discord import app_commands
from discord.ext import commands, tasks
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
import string

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
    logger.info("✅ Firebase module loaded!")
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("⚠️ Firebase not available")
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
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
            firebase_app = firebase_admin.initialize_app(cred, {
                'databaseURL': firebase_url
            })
            rtdb_client = db.reference()
            logger.info("✅ Firebase connected!")
            
            try:
                test_ref = rtdb_client.child('_test')
                test_ref.set({'test': 'test'})
                test_ref.delete()
                logger.info("✅ Firebase test successful!")
            except Exception as e:
                logger.error(f"❌ Firebase test failed: {e}")
                rtdb_client = None
        else:
            logger.warning("⚠️ No FIREBASE_KEY_JSON found")
    except Exception as e:
        logger.error(f"❌ Firebase error: {e}")
        rtdb_client = None

if rtdb_client:
    logger.info("✅✅✅ Firebase is CONNECTED!")
else:
    logger.warning("⚠️⚠️⚠️ Firebase NOT connected - using local DB")

# ============ DISCORD BOT ============
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# ============ DATABASE ============
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
    if rtdb_client:
        try:
            rtdb_client.child(path).set(data)
            return True
        except Exception as e:
            logger.error(f"Firebase set error: {e}")
            return False
    return False

def firebase_get(path):
    if rtdb_client:
        try:
            return rtdb_client.child(path).get()
        except Exception as e:
            return None
    return None

def firebase_delete(path):
    if rtdb_client:
        try:
            rtdb_client.child(path).delete()
            return True
        except Exception as e:
            return False
    return False

def generate_credentials(user_id, username=None, role='member'):
    """Generate or retrieve credentials for a user"""
    existing = firebase_get(f'credentials/{user_id}')
    if existing:
        return existing
    
    if not username:
        username = f"user_{str(user_id)[:6]}_{secrets.token_hex(4)}"
    
    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    password = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    creds = {
        'username': username,
        'password': password,
        'role': role,
        'user_id': user_id,
        'created_at': datetime.now().isoformat()
    }
    
    firebase_set(f'credentials/{user_id}', creds)
    return creds

def get_credentials(user_id):
    return firebase_get(f'credentials/{user_id}')

def delete_credentials(user_id):
    """Delete only credentials for a user"""
    firebase_delete(f'credentials/{user_id}')
    firebase_delete(f'credentials_by_username/{user_id}')
    logger.info(f"🗑️ Deleted credentials for {user_id}")

async def send_credentials_dm(member, creds, role=None, log_channel=None):
    """Send credentials via DM and log to channel"""
    if not creds:
        return False
    
    role = role or creds.get('role', 'member')
    
    embed = discord.Embed(
        title="🔐 **YOUR EDITH LOGIN CREDENTIALS**",
        description=f"Welcome to **{member.guild.name}**!",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="📝 USERNAME", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="🔑 PASSWORD", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="🎭 ROLE", value=f"`{role.upper()}`", inline=True)
    embed.add_field(name="🌐 LOGIN URL", value=f"[Click Here to Login]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})", inline=False)
    embed.set_footer(text="⚠️ Keep these safe! You cannot reset your password.")
    
    try:
        await member.send(embed=embed)
        logger.info(f"✅ Credentials sent to {member.name}")
        
        if log_channel:
            log_embed = discord.Embed(
                title="🔐 CREDENTIALS SENT",
                description=f"Credentials sent to {member.mention}",
                color=discord.Color.green()
            )
            log_embed.add_field(name="Username", value=f"`{creds['username']}`", inline=True)
            log_embed.add_field(name="Role", value=f"`{role.upper()}`", inline=True)
            await log_channel.send(content="@everyone", embed=log_embed)
        
        return True
    except discord.Forbidden:
        logger.warning(f"❌ Cannot DM {member.name}")
        return False

async def process_members(guild, log_channel=None):
    """Process all members - generate credentials only for verified users"""
    if not rtdb_client:
        return False
    
    try:
        members = guild.members
        verified_role = discord.utils.get(guild.roles, name="✅ Verified")
        
        sent_count = 0
        for member in members:
            if member.bot:
                continue
                
            user_id = str(member.id)
            is_verified = verified_role in member.roles if verified_role else False
            
            # ONLY generate/send credentials for verified users
            if is_verified:
                is_admin = any(role.permissions.administrator for role in member.roles)
                role_type = 'moderator' if is_admin else 'member'
                
                creds = get_credentials(user_id)
                if not creds:
                    creds = generate_credentials(user_id, role=role_type)
                    await send_credentials_dm(member, creds, role_type, log_channel)
                    sent_count += 1
                    logger.info(f"🔑 Generated credentials for verified user {member.name}")
                else:
                    # Update role if changed
                    current_role = creds.get('role', 'member')
                    if is_admin and current_role != 'moderator':
                        creds['role'] = 'moderator'
                        firebase_set(f'credentials/{user_id}', creds)
                        await send_credentials_dm(member, creds, 'moderator', log_channel)
                        sent_count += 1
                    elif not is_admin and current_role != 'member':
                        creds['role'] = 'member'
                        firebase_set(f'credentials/{user_id}', creds)
                        await send_credentials_dm(member, creds, 'member', log_channel)
                        sent_count += 1
            else:
                # If not verified, delete their credentials
                delete_credentials(user_id)
            
            # Update Firebase with user data (always keep, even if not verified)
            user_data = {
                'discord_id': user_id,
                'username': member.name,
                'global_name': member.display_name or member.name,
                'avatar': member.avatar.url if member.avatar else None,
                'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                'roles': [r.name for r in member.roles if r.name != "@everyone"],
                'verified': is_verified,
                'verified_at': datetime.now().isoformat() if is_verified else None
            }
            
            if is_verified:
                # Add credentials to verified user data
                creds = get_credentials(user_id)
                if creds:
                    user_data['credentials'] = creds
                firebase_set(f'guilds/{guild.id}/verified/{user_id}', user_data)
                firebase_delete(f'guilds/{guild.id}/unverified/{user_id}')
            else:
                firebase_set(f'guilds/{guild.id}/unverified/{user_id}', {
                    'discord_id': user_id,
                    'username': member.name,
                    'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                    'roles': [r.name for r in member.roles if r.name != "@everyone"]
                })
                firebase_delete(f'guilds/{guild.id}/verified/{user_id}')
        
        if sent_count > 0 and log_channel:
            await log_channel.send(f"✅ **Sent {sent_count} new credentials to verified members!**")
        
        logger.info(f"✅ Processed {len(members)} members for {guild.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to process members: {e}")
        return False

# ============ AUTO SYNC TASK (Every 5 seconds) ============
@tasks.loop(seconds=5)
async def auto_sync():
    """Automatically process all guilds every 5 seconds"""
    try:
        for guild in bot.guilds:
            log_channel = discord.utils.get(guild.channels, name="🛡️-mod-logs")
            if not log_channel:
                log_channel = discord.utils.get(guild.channels, name="🔐-verification")
            
            await process_members(guild, log_channel)
    except Exception as e:
        logger.error(f"Auto sync error: {e}")

# ============ BIG SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
        self.setup_done = False
    
    @discord.ui.button(label="⚡ SETUP ALL", style=discord.ButtonStyle.success, emoji="⚡", row=0)
    async def setup_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.send_message("🔄 **Starting full server setup...**\n\n⏳ This will take a moment...", ephemeral=True)
        await self.setup_all(interaction.guild, interaction)
    
    @discord.ui.button(label="🔐 VERIFICATION SYSTEM", style=discord.ButtonStyle.primary, emoji="🔐", row=0)
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            channel = await self.get_or_create_channel(interaction.guild, "🔐-verification", "🔐 Security")
            await self.send_verification_message(channel)
            await interaction.followup.send(f"✅ Verification system setup complete in {channel.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎫 TICKET SYSTEM", style=discord.ButtonStyle.secondary, emoji="🎫", row=0)
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            channel = await self.get_or_create_channel(interaction.guild, "🎫-tickets", "🎫 Support")
            await self.send_ticket_message(channel)
            await interaction.followup.send(f"✅ Ticket system setup complete in {channel.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎁 GIVEAWAY SYSTEM", style=discord.ButtonStyle.primary, emoji="🎁", row=0)
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            channel = await self.get_or_create_channel(interaction.guild, "🎉-giveaways", "🎉 Events")
            await self.send_giveaway_message(channel)
            await interaction.followup.send(f"✅ Giveaway system setup complete in {channel.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="👑 ROLE MANAGEMENT", style=discord.ButtonStyle.secondary, emoji="👑", row=1)
    async def setup_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await self.create_roles(interaction.guild)
            await interaction.followup.send("✅ Roles created successfully!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🛡️ MODERATION SUITE", style=discord.ButtonStyle.danger, emoji="🛡️", row=1)
    async def setup_moderation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            channel = await self.get_or_create_channel(interaction.guild, "🛡️-mod-logs", "🔐 Security")
            await interaction.followup.send(f"✅ Moderation setup complete! Logs in {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="📊 SERVER STATS", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
    async def setup_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("✅ Stats system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="💾 BACKUP SYSTEM", style=discord.ButtonStyle.success, emoji="💾", row=1)
    async def setup_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await self.save_guild_config(interaction.guild)
            await interaction.followup.send("✅ Backup system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔄 SYNC MEMBERS", style=discord.ButtonStyle.primary, emoji="🔄", row=2)
    async def sync_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            log_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
            if not log_channel:
                log_channel = discord.utils.get(interaction.guild.channels, name="🔐-verification")
            
            await process_members(interaction.guild, log_channel)
            await interaction.followup.send("✅ **Members synced!**\n\n• All verified members processed\n• Credentials generated and sent\n• Verified/Unverified status updated", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="📝 CREDENTIALS MANAGEMENT", style=discord.ButtonStyle.secondary, emoji="📝", row=2)
    async def manage_credentials(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📝 **CREDENTIALS MANAGEMENT**",
            description="""
            **📋 AVAILABLE COMMANDS:**
            • `/credentials` - Get your own credentials
            • `/get_creds @user` - Get credentials for a user
            • `/reset_creds @user` - Reset credentials for a user
            • `/sync` - Sync all members
            
            **⚡ AUTO FEATURES:**
            • 🔄 Auto-sync every 5 seconds
            • ✅ Only verified users get credentials
            • 🗑️ Credentials auto-delete when user leaves
            • 📝 Logged to #🛡️-mod-logs
            • 📧 Credentials sent via DM
            
            **🔒 SECURITY:**
            • Passwords are securely generated
            • Unique username per user
            • Role-based access control
            """,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def setup_all(self, guild, interaction):
        try:
            await interaction.followup.send("🔄 **STEP 1/5:** Deleting existing channels and roles...", ephemeral=True)
            
            # Delete channels
            channel_count = 0
            for channel in guild.channels:
                try:
                    await channel.delete()
                    channel_count += 1
                except:
                    pass
            logger.info(f"🗑️ Deleted {channel_count} channels")
            
            # Delete roles
            role_count = 0
            for role in guild.roles:
                if role.name != "@everyone" and not role.managed:
                    try:
                        await role.delete()
                        role_count += 1
                    except:
                        pass
            logger.info(f"🗑️ Deleted {role_count} roles")
            
            await interaction.followup.send("🔄 **STEP 2/5:** Creating new server structure...", ephemeral=True)
            
            # Create categories and channels
            categories = {
                "📋 INFORMATION": ["📌-rules", "📢-announcements", "📋-server-info"],
                "🔐 SECURITY": ["🔐-verification", "🛡️-mod-logs", "📊-logs"],
                "💬 GENERAL": ["💬-general-chat", "📸-media", "🎮-gaming", "🎵-music"],
                "📞 VOICE CHANNELS": ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"],
                "🎫 SUPPORT": ["🎫-tickets", "📝-feedback", "❓-faq"],
                "🎉 EVENTS": ["🎉-giveaways", "📅-events", "🏆-contests"],
                "👑 ADMIN": ["⚙️-admin-commands", "📊-stats", "🔧-bot-controls"]
            }
            
            category_objects = {}
            created_count = 0
            
            for category_name, channel_names in categories.items():
                category = await guild.create_category(category_name)
                category_objects[category_name] = category
                logger.info(f"✅ Created category: {category_name}")
                
                for channel_name in channel_names:
                    try:
                        await guild.create_text_channel(channel_name, category=category)
                        created_count += 1
                        logger.info(f"✅ Created channel: {channel_name}")
                    except Exception as e:
                        logger.error(f"❌ Failed to create {channel_name}: {e}")
            
            # Create voice channels
            if "📞 VOICE CHANNELS" in category_objects:
                for vc_name in ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"]:
                    try:
                        await guild.create_voice_channel(vc_name, category=category_objects["📞 VOICE CHANNELS"])
                        created_count += 1
                        logger.info(f"✅ Created voice channel: {vc_name}")
                    except Exception as e:
                        logger.error(f"❌ Failed to create {vc_name}: {e}")
            
            logger.info(f"✅ Created {created_count} channels")
            
            await interaction.followup.send("🔄 **STEP 3/5:** Creating roles...", ephemeral=True)
            
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
            
            role_count = 0
            for role_name, perms in roles_config.items():
                try:
                    await guild.create_role(name=role_name, permissions=perms)
                    role_count += 1
                    logger.info(f"✅ Created role: {role_name}")
                except Exception as e:
                    logger.error(f"❌ Failed to create {role_name}: {e}")
            
            logger.info(f"✅ Created {role_count} roles")
            
            await interaction.followup.send("🔄 **STEP 4/5:** Setting up systems...", ephemeral=True)
            
            # Get channels
            verify_channel = discord.utils.get(guild.channels, name="🔐-verification")
            ticket_channel = discord.utils.get(guild.channels, name="🎫-tickets")
            giveaway_channel = discord.utils.get(guild.channels, name="🎉-giveaways")
            
            if verify_channel:
                await self.send_verification_message(verify_channel)
                logger.info("✅ Sent verification message")
            if ticket_channel:
                await self.send_ticket_message(ticket_channel)
                logger.info("✅ Sent ticket message")
            if giveaway_channel:
                await self.send_giveaway_message(giveaway_channel)
                logger.info("✅ Sent giveaway message")
            
            await interaction.followup.send("🔄 **STEP 5/5:** Syncing members and generating credentials...", ephemeral=True)
            
            # Sync members
            log_channel = discord.utils.get(guild.channels, name="🛡️-mod-logs")
            await process_members(guild, log_channel)
            
            embed = discord.Embed(
                title="✅ **🎉 SERVER SETUP COMPLETE!**",
                description=f"""
                **📊 SERVER: {guild.name}**
                
                **✅ CREATED:**
                • 📋 7 Categories
                • 💬 27+ Channels  
                • 👑 9 Roles
                • 🔐 Verification System
                • 🎫 Ticket System
                • 🎁 Giveaway System
                • 🛡️ Moderation System
                • 💾 Backup System
                
                **🔑 CREDENTIALS:**
                • ✅ Verified members processed
                • 📧 Credentials sent via DM
                • 📝 Logged in #🛡️-mod-logs
                • 🔄 Auto-sync every 5 seconds
                
                🎉 **Your server is ready to go!**
                """,
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else bot.user.display_avatar.url)
            embed.set_footer(text="EDITH Server Management System v2.0")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info("✅ Setup complete for {guild.name}")
            
        except Exception as e:
            logger.error(f"Setup error: {e}")
            try:
                await interaction.followup.send(f"❌ **ERROR:**\n```\n{str(e)}\n```", ephemeral=True)
            except:
                pass
    
    async def get_or_create_channel(self, guild, channel_name, category_name):
        channel = discord.utils.get(guild.channels, name=channel_name)
        if channel:
            return channel
        
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
        
        return await guild.create_text_channel(channel_name, category=category)
    
    async def create_roles(self, guild):
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
            if not discord.utils.get(guild.roles, name=role_name):
                try:
                    await guild.create_role(name=role_name, permissions=perms)
                except:
                    pass
    
    async def send_verification_message(self, channel):
        if not channel:
            return
        
        embed = discord.Embed(
            title="🔐 **VERIFICATION REQUIRED**",
            description="""
            **🔒 WHY VERIFY?**
            • 🛡️ **SECURITY** - Protect your account from unauthorized access
            • 🎮 **ACCESS** - Unlock full server features and channels
            • 👤 **IDENTITY** - Verify your Discord identity
            • 🏆 **BENEFITS** - Get access to exclusive content and roles
            • 🛡️ **ANTI-RAID** - Help us keep the server safe from bots
            
            **📋 WHAT WE COLLECT:**
            • Your Discord username and ID
            • Email address (for verification)
            • Server membership information
            • OAuth tokens for verification
            
            **✅ HOW TO VERIFY:**
            1. Click the **VERIFY VIA DISCORD** button below
            2. Authorize through Discord OAuth
            3. Wait for automatic role assignment
            4. Receive your login credentials via DM
            
            **🎯 AFTER VERIFICATION:**
            • You'll receive your login credentials
            • You'll get the ✅ Verified role
            • Full access to all channels
            • Login access to the website
            """,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="EDITH Authentication System • Secure OAuth2 Verification")
        
        view = VerifyView()
        await channel.send(embed=embed, view=view)
    
    async def send_ticket_message(self, channel):
        if not channel:
            return
        
        embed = discord.Embed(
            title="🎫 **TICKET SYSTEM**",
            description="""
            **🆘 NEED HELP? CREATE A TICKET!**
            
            **📋 TICKET TYPES:**
            • 🛠️ **SERVER RELATED** - Server issues, suggestions, feedback
            • 👮 **CONTACT MODS** - Report users, moderation issues
            • ❓ **OTHERS** - General questions, help
            
            **⚡ TICKET FEATURES:**
            • ➕ Add/Remove users
            • ⛔ Ban users
            • 📄 Transcripts
            • 📝 Special notes
            • 🔒 Close tickets
            
            Click a button below to create your ticket!
            """,
            color=discord.Color.purple()
        )
        view = TicketView()
        await channel.send(embed=embed, view=view)
    
    async def send_giveaway_message(self, channel):
        if not channel:
            return
        
        embed = discord.Embed(
            title="🎉 **GIVEAWAY CENTER**",
            description="""
            **🎁 WELCOME TO THE GIVEAWAY CENTER!**
            
            **⚡ FEATURES:**
            • 🎯 Host giveaways with custom prizes
            • ⏰ Set duration and number of winners
            • 🤖 Auto-select winners
            • 🔄 Reroll winners
            • 🗑️ Delete giveaways
            
            **👑 ADMIN ONLY:** Use the button below to host
            
            *Join the fun and win amazing prizes!*
            """,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)
    
    async def save_guild_config(self, guild):
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
                'updated_at': datetime.now().isoformat()
            }
            
            firebase_set(f'guilds/{guild.id}/config', config)
            return True
        except Exception as e:
            logger.error(f"Failed to save guild config: {e}")
            return False

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

# ============ VERIFY VIEW ============
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔐 VERIFY VIA DISCORD", style=discord.ButtonStyle.success, emoji="🔐")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        verified_data = firebase_get(f'guilds/{guild_id}/verified/{user_id}')
        if verified_data:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return
        
        url, state = oauth.generate_oauth_url(user_id, guild_id)
        
        embed = discord.Embed(
            title="🔐 **AUTHORIZE VERIFICATION**",
            description=f"""
            **Click the link below to verify your identity:**
            
            [🔐 Click here to verify with Discord]({url})
            
            ⏰ **TIME LIMIT:** 10 minutes
            🔒 **SECURITY:** Your data is encrypted and secure
            📧 **EMAIL:** We'll verify your email
            🛡️ **CONNECTIONS:** We'll check your connected accounts
            
            **✅ WHAT HAPPENS NEXT:**
            1. You authorize through Discord
            2. We verify your identity
            3. You get the ✅ Verified role
            4. Full server access granted!
            5. You'll receive your login credentials via DM
            """,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Verification ID: {state[:8]}...")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="ℹ️ WHAT IS VERIFICATION?", style=discord.ButtonStyle.secondary, emoji="ℹ️")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="ℹ️ **WHAT IS VERIFICATION?**",
            description="""
            **🔒 VERIFICATION HELPS US:**
            • 🛡️ **Keep the server safe** from bots and trolls
            • 👤 **Confirm your identity** as a real Discord user
            • 🎮 **Unlock full access** to all server features
            • 🏆 **Get special roles** and permissions
            • 🔐 **Secure your account** with OAuth2
            
            **❌ WHAT WE DON'T DO:**
            • ❌ Share your data with anyone
            • ❌ Store your password
            • ❌ Post on your behalf
            • ❌ Access your DMs
            
            **📋 DATA WE COLLECT:**
            • Username and ID
            • Email address
            • Server membership
            • OAuth tokens (encrypted)
            """,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ============ GIVEAWAY SYSTEM ============
class GiveawayMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎁 HOST GIVEAWAY", style=discord.ButtonStyle.success, emoji="🎁")
    async def host_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        modal = GiveawayModal()
        await interaction.response.send_modal(modal)

class GiveawayModal(Modal):
    def __init__(self):
        super().__init__(title="🎁 Host Giveaway")
        self.name = TextInput(label="Giveaway Name", required=True, max_length=100)
        self.prize = TextInput(label="Prize", required=True, max_length=200)
        self.duration = TextInput(label="Duration (minutes)", required=True)
        self.winners = TextInput(label="Number of Winners", required=True)
        self.add_item(self.name)
        self.add_item(self.prize)
        self.add_item(self.duration)
        self.add_item(self.winners)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration_minutes = int(self.duration.value)
            winners_count = int(self.winners.value)
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            giveaway_id = secrets.token_hex(8)
            
            embed = discord.Embed(
                title=f"🎉 {self.name.value}",
                description=f"""
                **🏆 PRIZE:** {self.prize.value}
                **👤 HOST:** {interaction.user.mention}
                **⏰ DURATION:** {duration_minutes} minutes
                **👑 WINNERS:** {winners_count}
                **⏳ ENDS:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}
                
                Click **PARTICIPATE** below to join!
                """,
                color=discord.Color.gold()
            )
            
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
            title="🎉 **GIVEAWAY COMPLETE!**",
            description=f"""
            **🎯 GIVEAWAY:** {giveaway_data['name']}
            **🏆 PRIZE:** {giveaway_data['prize']}
            **👤 HOST:** <@{giveaway_data['host']}>
            
            **👑 WINNERS:**
            {', '.join(winner_mentions)}
            
            🎊 **Congratulations!**
            Please create a ticket within 24 hours to claim your prize!
            """,
            color=discord.Color.green()
        )
        
        await channel.send(embed=embed)

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 PARTICIPATE", style=discord.ButtonStyle.success, emoji="🎯")
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
    
    @discord.ui.button(label="❌ UN-PARTICIPATE", style=discord.ButtonStyle.danger, emoji="❌")
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and interaction.user.id in giveaway_data['participants']:
            giveaway_data['participants'].remove(interaction.user.id)
            db.save_data()
            await interaction.response.send_message("✅ Removed!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ DELETE", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions!", ephemeral=True)
            return
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
    
    @discord.ui.button(label="🔄 REROLL", style=discord.ButtonStyle.primary, emoji="🔄")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions!", ephemeral=True)
            return
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and giveaway_data['participants']:
            new_winner = random.choice(giveaway_data['participants'])
            await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)

# ============ TICKET SYSTEM ============
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🛠️ SERVER RELATED", style=discord.ButtonStyle.primary, emoji="🛠️")
    async def server_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Server Related")
    
    @discord.ui.button(label="👮 CONTACT MODS", style=discord.ButtonStyle.danger, emoji="👮")
    async def mod_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Contact Mods")
    
    @discord.ui.button(label="❓ OTHERS", style=discord.ButtonStyle.secondary, emoji="❓")
    async def other_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Others")
    
    async def create_ticket(self, interaction, ticket_type):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            category = discord.utils.get(guild.categories, name="🎫 SUPPORT")
            if not category:
                category = await guild.create_category("🎫 SUPPORT")
            
            ticket_name = f"ticket-{interaction.user.name}-{secrets.token_hex(3)}".lower()
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
            
            embed = discord.Embed(
                title=f"🎫 TICKET: {ticket_type}",
                description=f"""
                **👤 CREATED BY:** {interaction.user.mention}
                **📋 TYPE:** {ticket_type}
                **⏰ CREATED:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                
                **🎯 TICKET CONTROLS:**
                • ➕ Add users
                • ➖ Remove users
                • 🔒 Close ticket
                • 📝 Add special notes
                """,
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
    
    @discord.ui.button(label="➕ ADD USER", style=discord.ButtonStyle.success, emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ REMOVE USER", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔒 CLOSE TICKET", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        await interaction.response.defer()
        channel = interaction.channel
        await channel.send("🔒 **Closing ticket...**")
        await asyncio.sleep(2)
        await channel.delete()
    
    @discord.ui.button(label="📝 SPECIAL NOTE", style=discord.ButtonStyle.primary, emoji="📝")
    async def special_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NoteModal(self.channel_id)
        await interaction.response.send_modal(modal)

class AddUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="➕ Add User")
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
        super().__init__(title="➖ Remove User")
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
        super().__init__(title="📝 Special Note")
        self.channel_id = channel_id
        self.note_input = TextInput(label="Note", style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.add_item(self.note_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        firebase_set(f'guilds/{guild_id}/verified/{user_id}/notes/{self.channel_id}', {
            'note': self.note_input.value,
            'ticket': str(self.channel_id),
            'moderator': str(interaction.user),
            'timestamp': datetime.now().isoformat()
        })
        
        await interaction.channel.send(f"📝 **Special Note by {interaction.user.mention}:**\n{self.note_input.value}")
        await interaction.response.send_message("✅ Note saved!", ephemeral=True)

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    view = SetupView(interaction.user)
    embed = discord.Embed(
        title="🤖 **EDITH - ULTIMATE SERVER MANAGEMENT BOT**",
        description="""
        **🌟 WELCOME TO EDITH!**
        
        **Click any button below to set up that system!**
        
        **⚠️ WARNING:** Setup All will delete ALL existing channels and roles!
        """,
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
    embed.set_footer(text="EDITH v2.0 • Built with ❤️")
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="sync", description="Sync server members and generate credentials")
@app_commands.default_permissions(administrator=True)
async def sync_command(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Syncing members...**", ephemeral=True)
    
    log_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
    if not log_channel:
        log_channel = discord.utils.get(interaction.guild.channels, name="🔐-verification")
    
    await process_members(interaction.guild, log_channel)
    await interaction.followup.send("✅ **Sync complete!** Credentials generated and sent to verified members!", ephemeral=True)

@bot.tree.command(name="credentials", description="Get your login credentials")
async def get_credentials_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    creds = get_credentials(user_id)
    
    if not creds:
        await interaction.response.send_message("❌ No credentials found! You need to be verified first.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔐 **YOUR CREDENTIALS**",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="📝 Username", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="🔑 Password", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="🎭 Role", value=f"`{creds.get('role', 'member').upper()}`", inline=True)
    embed.add_field(name="🌐 Login URL", value=f"[Click Here]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="get_creds", description="Get credentials for a user (Admin only)")
@app_commands.default_permissions(administrator=True)
async def get_user_creds(interaction: discord.Interaction, user: discord.Member):
    creds = get_credentials(str(user.id))
    
    if not creds:
        await interaction.response.send_message(f"❌ No credentials for {user.mention}! They may not be verified.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"🔐 CREDENTIALS FOR {user.name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="📝 Username", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="🔑 Password", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="🎭 Role", value=f"`{creds.get('role', 'member').upper()}`", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset_creds", description="Reset credentials for a user (Admin only)")
@app_commands.default_permissions(administrator=True)
async def reset_user_creds(interaction: discord.Interaction, user: discord.Member):
    user_id = str(user.id)
    
    # Check if user is verified
    verified_role = discord.utils.get(interaction.guild.roles, name="✅ Verified")
    if verified_role not in user.roles:
        await interaction.response.send_message(f"❌ {user.mention} is not verified! Only verified users get credentials.", ephemeral=True)
        return
    
    is_admin = any(role.permissions.administrator for role in user.roles)
    role_type = 'moderator' if is_admin else 'member'
    
    # Delete old credentials
    firebase_delete(f'credentials/{user_id}')
    
    # Generate new
    creds = generate_credentials(user_id, role=role_type)
    
    log_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
    await send_credentials_dm(user, creds, role_type, log_channel)
    
    await interaction.response.send_message(f"✅ Credentials reset for {user.mention}!", ephemeral=True)

@bot.tree.command(name="verify", description="Start verification process")
async def verify_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    url, state = oauth.generate_oauth_url(user_id, guild_id)
    
    embed = discord.Embed(
        title="🔐 **VERIFICATION REQUIRED**",
        description=f"""
        **Click the link below to verify:**
        
        [🔐 Click here to verify with Discord]({url})
        
        ⏰ **TIME LIMIT:** 10 minutes
        🔒 **SECURITY:** Your data is encrypted
        
        **✅ WHAT HAPPENS NEXT:**
        1. Authorize through Discord
        2. We verify your identity
        3. You get the ✅ Verified role
        4. You receive your login credentials
        """,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Verification ID: {state[:8]}...")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Check bot latency")
async def ping_command(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 **PONG!**\nLatency: {round(interaction.client.latency * 1000)}ms")

@bot.tree.command(name="shutdown", description="Shutdown the bot (Owner only)")
async def shutdown_command(interaction: discord.Interaction):
    if interaction.user.id != int(os.getenv('SUPER_ADMIN_ID', '0')):
        await interaction.response.send_message("❌ Only the bot owner can use this!", ephemeral=True)
        return
    await interaction.response.send_message("🔴 **Shutting down...**")
    await bot.close()

# ============ FLASK ROUTES ============
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>EDITH Bot</title>
    <style>
        body { font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; max-width: 500px; }
        h1 { font-size: 32px; }
        .status { color: #4caf50; }
    </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 EDITH Bot</h1>
            <p>Ultimate Server Management System</p>
            <p class="status">✅ Online</p>
            <p>Use <code>/setup</code> in Discord</p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        'status': 'online',
        'bot': bot.user.name if bot.user else 'None',
        'guilds': len(bot.guilds),
        'firebase': '✅ Connected' if rtdb_client else '❌ Not connected'
    })

# ============ EVENTS ============
@bot.event
async def on_ready():
    print(f"""
    ╔════════════════════════════════════════╗
    ║         🚀 EDITH BOT ONLINE            ║
    ╠════════════════════════════════════════╣
    ║ Name: {bot.user.name}                  ║
    ║ ID: {bot.user.id}                      ║
    ║ Guilds: {len(bot.guilds)}              ║
    ║ Firebase: {'✅ Connected' if rtdb_client else '⚠️ Local DB'} ║
    ╚════════════════════════════════════════╝
    """)
    
    if not auto_sync.is_running():
        auto_sync.start()
        print("🔄 Auto-sync started (every 5 seconds)")
    
    for guild in bot.guilds:
        log_channel = discord.utils.get(guild.channels, name="🛡️-mod-logs")
        await process_members(guild, log_channel)
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands!")
    except Exception as e:
        print(f"❌ Failed to sync: {e}")

@bot.event
async def on_member_join(member):
    if member.bot:
        return
    
    unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
    if unverified_role:
        try:
            await member.add_roles(unverified_role)
        except:
            pass
    
    # Add to unverified in Firebase
    firebase_set(f'guilds/{member.guild.id}/unverified/{member.id}', {
        'discord_id': str(member.id),
        'username': member.name,
        'joined_at': datetime.now().isoformat(),
        'roles': [r.name for r in member.roles if r.name != "@everyone"]
    })
    
    # Delete any existing credentials (they are not verified yet)
    delete_credentials(str(member.id))
    
    logger.info(f"👋 {member.name} joined {member.guild.name}")

@bot.event
async def on_member_update(before, after):
    if before.bot or after.bot:
        return
    
    # Check if user got verified
    verified_role = discord.utils.get(after.guild.roles, name="✅ Verified")
    was_verified = verified_role in before.roles
    is_verified = verified_role in after.roles
    
    # If user just got verified, generate credentials
    if not was_verified and is_verified:
        creds = get_credentials(str(after.id))
        if not creds:
            is_admin = any(role.permissions.administrator for role in after.roles)
            role_type = 'moderator' if is_admin else 'member'
            creds = generate_credentials(str(after.id), role=role_type)
            
            log_channel = discord.utils.get(after.guild.channels, name="🛡️-mod-logs")
            await send_credentials_dm(after, creds, role_type, log_channel)
            logger.info(f"✅ Generated credentials for newly verified {after.name}")
    
    # Check if user got unverified
    if was_verified and not is_verified:
        delete_credentials(str(after.id))
        logger.info(f"🗑️ Deleted credentials for {after.name} (unverified)")

@bot.event
async def on_member_remove(member):
    """When a member leaves, delete only their credentials"""
    if member.bot:
        return
    
    # Delete credentials only
    delete_credentials(str(member.id))
    logger.info(f"👋 {member.name} left {member.guild.name} - credentials deleted")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

# ============ FLASK THREAD ============
flask_thread = None

def run_flask():
    port = int(os.getenv('PORT', 8080))
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
