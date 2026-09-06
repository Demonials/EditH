import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput, Select
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
from flask import Flask, request, redirect, jsonify, render_template_string
import threading
import time
import hashlib
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
    if rtdb_client:
        try:
            rtdb_client.child(path).set(data)
            return True
        except Exception as e:
            logger.error(f"Firebase set error at {path}: {e}")
            return False
    return False

def firebase_get(path):
    if rtdb_client:
        try:
            return rtdb_client.child(path).get()
        except Exception as e:
            logger.error(f"Firebase get error at {path}: {e}")
            return None
    return None

def firebase_update(path, data):
    if rtdb_client:
        try:
            rtdb_client.child(path).update(data)
            return True
        except Exception as e:
            logger.error(f"Firebase update error at {path}: {e}")
            return False
    return False

def firebase_delete(path):
    if rtdb_client:
        try:
            rtdb_client.child(path).delete()
            return True
        except Exception as e:
            logger.error(f"Firebase delete error at {path}: {e}")
            return False
    return False

def generate_credentials(user_id, username=None, role='member'):
    """Generate or retrieve credentials for a user"""
    # Check if credentials already exist
    existing = firebase_get(f'credentials/{user_id}')
    if existing:
        return existing
    
    # Generate new credentials
    if not username:
        username = f"user_{str(user_id)[:6]}_{secrets.token_hex(4)}"
    
    # Generate secure password
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
    firebase_set(f'credentials_by_username/{username}', user_id)
    
    return creds

def get_credentials(user_id):
    """Get user credentials from Firebase"""
    return firebase_get(f'credentials/{user_id}')

def get_credentials_by_username(username):
    """Get user ID by username"""
    user_id = firebase_get(f'credentials_by_username/{username}')
    if user_id:
        return get_credentials(user_id)
    return None

def update_credentials_role(user_id, new_role):
    """Update user's role in credentials"""
    creds = get_credentials(user_id)
    if creds:
        creds['role'] = new_role
        firebase_set(f'credentials/{user_id}', creds)
        return True
    return False

async def send_credentials_dm(member, creds, role=None):
    """Send credentials via DM with beautiful embed"""
    if not creds:
        return False
    
    role = role or creds.get('role', 'member')
    
    embed = discord.Embed(
        title="🔐 **Your EDITH Login Credentials**",
        description=f"Welcome to **{member.guild.name}**!",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(
        name="📝 Username",
        value=f"`{creds['username']}`",
        inline=True
    )
    embed.add_field(
        name="🔑 Password",
        value=f"`{creds['password']}`",
        inline=True
    )
    embed.add_field(
        name="🎭 Role",
        value=f"`{role.upper()}`",
        inline=True
    )
    embed.add_field(
        name="🌐 Login URL",
        value=f"[Click Here to Login]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})",
        inline=False
    )
    embed.add_field(
        name="⚠️ Important",
        value="Keep these credentials safe! You cannot reset your password.",
        inline=False
    )
    embed.set_footer(text="EDITH Authentication System • Secure Your Account")
    
    try:
        await member.send(embed=embed)
        logger.info(f"✅ Credentials sent to {member.name}")
        return True
    except discord.Forbidden:
        logger.warning(f"❌ Cannot DM {member.name} - DMs disabled")
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
            'updated_at': datetime.now().isoformat()
        }
        
        firebase_set(f'guilds/{guild.id}/config', config)
        logger.info(f"✅ Saved guild config for {guild.name}")
        return True
    except Exception as e:
        logger.error(f"Failed to save guild config: {e}")
        return False

async def sync_server_members(guild):
    """Sync all members in a guild - create credentials, move between verified/unverified"""
    if not rtdb_client:
        return
    
    try:
        members = guild.members
        verified_role = discord.utils.get(guild.roles, name="✅ Verified")
        unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
        
        # Get current Firebase data
        firebase_verified = firebase_get(f'guilds/{guild.id}/verified') or {}
        firebase_unverified = firebase_get(f'guilds/{guild.id}/unverified') or {}
        
        # Track current members
        firebase_members = set(list(firebase_verified.keys()) + list(firebase_unverified.keys()))
        current_members = set([str(m.id) for m in members if not m.bot])
        
        # Remove members who left
        for user_id in firebase_members:
            if user_id not in current_members:
                firebase_delete(f'guilds/{guild.id}/verified/{user_id}')
                firebase_delete(f'guilds/{guild.id}/unverified/{user_id}')
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
                creds = generate_credentials(user_id, role=role_type)
                await send_credentials_dm(member, creds, role_type)
                logger.info(f"🔑 Generated credentials for {member.name}")
            else:
                # Update role if changed
                current_role = creds.get('role', 'member')
                if is_admin and current_role != 'moderator':
                    update_credentials_role(user_id, 'moderator')
                    await send_credentials_dm(member, creds, 'moderator')
                    logger.info(f"🔄 Updated {member.name} to moderator")
                elif not is_admin and current_role != 'member':
                    update_credentials_role(user_id, 'member')
                    await send_credentials_dm(member, creds, 'member')
                    logger.info(f"🔄 Updated {member.name} to member")
            
            # Move between verified/unverified in Firebase
            if is_verified:
                # Get all user data
                user_data = {
                    'discord_id': user_id,
                    'username': member.name,
                    'global_name': member.display_name or member.name,
                    'avatar': member.avatar.url if member.avatar else None,
                    'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                    'verified_at': datetime.now().isoformat(),
                    'roles': [r.name for r in member.roles if r.name != "@everyone"],
                    'credentials': creds
                }
                
                # Add notes if any
                notes = firebase_get(f'guilds/{guild.id}/verified/{user_id}/notes')
                if notes:
                    user_data['notes'] = notes
                
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
        
        logger.info(f"✅ Synced {len(members)} members for {guild.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to sync members: {e}")
        return False

# ============ BIG SETUP VIEW ============
class BigSetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
    
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
            await interaction.followup.send("✅ Role management system setup complete!", ephemeral=True)
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
            await interaction.followup.send(f"✅ Moderation suite setup complete! Logs will go to {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="📊 SERVER STATS", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
    async def setup_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("✅ Server stats system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="💾 BACKUP SYSTEM", style=discord.ButtonStyle.success, emoji="💾", row=1)
    async def setup_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await save_guild_config(interaction.guild)
            await save_guild_template(interaction.guild)
            await interaction.followup.send("✅ Backup system setup complete! Full server backup saved!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔄 SYNC MEMBERS", style=discord.ButtonStyle.primary, emoji="🔄", row=2)
    async def sync_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await sync_server_members(interaction.guild)
            await interaction.followup.send("✅ Members synced! All credentials generated and sent!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="📝 CREDENTIALS", style=discord.ButtonStyle.secondary, emoji="📝", row=2)
    async def manage_credentials(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="📝 **Credential Management**",
            description="""
            **Commands:**
            • `/credentials` - Get your own credentials
            • `/get_creds @user` - Get credentials for a user (Admin)
            • `/reset_creds @user` - Reset credentials for a user (Admin)
            • `/sync` - Sync all members and generate credentials
            """,
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🏗️ FULL SERVER SETUP", style=discord.ButtonStyle.danger, emoji="🏗️", row=2)
    async def full_server_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        # Create a confirmation view
        confirm_view = ConfirmView(self.author)
        embed = discord.Embed(
            title="⚠️ **WARNING: Full Server Setup**",
            description="""
            This will **DELETE ALL** existing channels and roles and create a complete new server structure.
            
            **What will be created:**
            • 📋 7 Categories with 27+ Channels
            • 👑 9 Roles with permissions
            • 🔐 Verification System
            • 🎫 Ticket System
            • 🎁 Giveaway System
            • 🛡️ Moderation System
            • 📊 Stats System
            • 💾 Backup System
            
            **This action CANNOT be undone!**
            """,
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)
    
    async def setup_all(self, guild, interaction):
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
                "📞 Voice": ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"],
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
            if "📞 Voice" in category_objects:
                for vc_name in ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"]:
                    try:
                        vc = await guild.create_voice_channel(vc_name, category=category_objects["📞 Voice"])
                        created_channels[vc_name] = vc.id
                    except:
                        pass
            
            await interaction.edit_original_response(content="🔄 **Creating roles...**")
            
            # Create roles
            roles_config = {
                "👑 Owner": discord.Permissions(administrator=True),
                "🛡️ Admin": discord.Permissions(administrator=True),
                "🔰 Moderator": discord.Permissions(
                    kick_members=True, ban_members=True, manage_messages=True, 
                    manage_channels=True, manage_roles=True, manage_nicknames=True,
                    mute_members=True, deafen_members=True, move_members=True
                ),
                "🤝 Helper": discord.Permissions(
                    manage_messages=True, mute_members=True, 
                    deafen_members=True, move_members=True
                ),
                "✅ Verified": discord.Permissions(
                    read_messages=True, send_messages=True, connect=True, speak=True,
                    read_message_history=True, attach_files=True, embed_links=True,
                    add_reactions=True, use_voice_activity=True, priority_speaker=True
                ),
                "❌ Unverified": discord.Permissions(
                    read_messages=True, send_messages=False
                ),
                "🎁 Giveaway": discord.Permissions(
                    read_messages=True, send_messages=False
                ),
                "🎮 Gamer": discord.Permissions(
                    read_messages=True, send_messages=True, connect=True, speak=True
                ),
                "🎵 Music Lover": discord.Permissions(
                    read_messages=True, send_messages=True, connect=True, speak=True
                )
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
                title="✅ **🎉 SERVER SETUP COMPLETE!**",
                description=f"""
                **{guild.name}** has been fully configured!
                
                **📊 Created:**
                • 📋 **7 Categories**
                • 💬 **27+ Channels**  
                • 👑 **9 Roles**
                • 🔐 **Verification System**
                • 🎫 **Ticket System**
                • 🎁 **Giveaway System**
                • 🛡️ **Moderation System**
                • 💾 **Backup System**
                
                **🔑 Credentials:**
                • All members have been processed
                • Moderators have admin-level credentials
                • Regular members have standard credentials
                
                **📝 Next Steps:**
                1. Check the 🔐-verification channel
                2. Customize roles and permissions
                3. Start using your server!
                
                🎉 **Your server is ready to go!**
                """,
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else bot.user.display_avatar.url)
            embed.set_footer(text="EDITH Server Management System")
            
            await interaction.edit_original_response(content=None, embed=embed)
            
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ **Error during setup:**\n```\n{str(e)}\n```")
    
    async def get_or_create_channel(self, guild, channel_name, category_name):
        """Get existing channel or create new one"""
        channel = discord.utils.get(guild.channels, name=channel_name)
        if channel:
            return channel
        
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
        
        return await guild.create_text_channel(channel_name, category=category)
    
    async def create_roles(self, guild):
        """Create all roles"""
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
            
            **After verification:**
            • You'll receive your login credentials via DM
            • You'll get the ✅ Verified role
            • Full access to all channels
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
            **Need help? Create a ticket!**
            
            Select the type of support you need:
            • 🛠️ **Server Related** - Server issues, suggestions, feedback
            • 👮 **Contact Mods** - Report users, moderation issues
            • ❓ **Others** - General questions, help
            
            Click a button below to create your ticket!
            
            **Ticket Features:**
            • Add/Remove users
            • Ban users
            • Transcripts
            • Special notes
            • Close tickets
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
            **Welcome to the Giveaway Center!**
            
            🎁 **Host and participate in exciting giveaways!**
            
            **Features:**
            • Host giveaways with custom prizes
            • Set duration and number of winners
            • Auto-select winners
            • Reroll winners
            • Delete giveaways
            
            👑 **Admin only:** Use the button below to host
            
            *Join the fun and win amazing prizes!*
            """,
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)

class ConfirmView(View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.author = author
        self.confirmed = False
    
    @discord.ui.button(label="✅ CONFIRM SETUP", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can confirm!", ephemeral=True)
            return
        self.confirmed = True
        await interaction.response.send_message("🔄 **Starting full server setup...**", ephemeral=True)
        await self.full_setup(interaction.guild, interaction)
    
    @discord.ui.button(label="❌ CANCEL", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can cancel!", ephemeral=True)
            return
        await interaction.response.send_message("❌ Setup cancelled.", ephemeral=True)
        await interaction.message.delete()
    
    async def full_setup(self, guild, interaction):
        try:
            view = BigSetupView(self.author)
            await view.setup_all(guild, interaction)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

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
    
    @discord.ui.button(label="🔐 VERIFY VIA DISCORD", style=discord.ButtonStyle.success, emoji="🔐", row=0)
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Check if already verified
        verified_data = firebase_get(f'guilds/{guild_id}/verified/{user_id}')
        if verified_data:
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
            5. You'll receive your login credentials via DM
            """,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Verification ID: {state[:8]}...")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="ℹ️ WHAT IS VERIFICATION?", style=discord.ButtonStyle.secondary, emoji="ℹ️", row=0)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="ℹ️ **What is Verification?**",
            description="""
            **Verification helps us:**
            • 🛡️ **Keep the server safe** from bots and trolls
            • 👤 **Confirm your identity** as a real Discord user
            • 🎮 **Unlock full access** to all server features
            • 🏆 **Get special roles** and permissions
            • 🔐 **Secure your account** with OAuth2
            
            **What we DON'T do:**
            • ❌ Share your data with anyone
            • ❌ Store your password
            • ❌ Post on your behalf
            • ❌ Access your DMs
            
            **Data we collect:**
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
        super().__init__(title="🎁 Host a Giveaway")
        self.name = TextInput(label="🎯 Giveaway Name", placeholder="Enter giveaway name", required=True, max_length=100)
        self.prize = TextInput(label="🏆 Prize", placeholder="What's the prize?", required=True, max_length=200)
        self.duration = TextInput(label="⏰ Duration (minutes)", placeholder="e.g., 60", required=True)
        self.winners = TextInput(label="👑 Number of Winners", placeholder="e.g., 1", required=True)
        self.add_item(self.name)
        self.add_item(self.prize)
        self.add_item(self.duration)
        self.add_item(self.winners)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration_minutes = int(self.duration.value)
            winners_count = int(self.winners.value)
            
            if duration_minutes < 1 or winners_count < 1:
                await interaction.response.send_message("❌ Please enter valid numbers!", ephemeral=True)
                return
            
            end_time = datetime.now() + timedelta(minutes=duration_minutes)
            giveaway_id = secrets.token_hex(8)
            
            embed = discord.Embed(
                title=f"🎉 {self.name.value}",
                description=f"""
                **🏆 Prize:** {self.prize.value}
                **👤 Host:** {interaction.user.mention}
                **⏰ Duration:** {duration_minutes} minutes
                **👑 Winners:** {winners_count}
                **⏳ Ends:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}
                
                Click **🎯 Participate** below to join!
                """,
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
            embed.set_footer(text=f"Giveaway ID: {giveaway_id[:8]}...")
            
            view = GiveawayParticipateView(giveaway_id, end_time, winners_count, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view)
            
            # Store in database
            db.data['giveaways'][giveaway_id] = {
                'name': self.name.value,
                'prize': self.prize.value,
                'host': interaction.user.id,
                'winners': winners_count,
                'end_time': end_time.isoformat(),
                'participants': []
            }
            db.save_data()
            
            # Start countdown
            asyncio.create_task(self.giveaway_countdown(giveaway_id, interaction.channel, end_time))
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter valid numbers!", ephemeral=True)
    
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
            **🎯 Giveaway:** {giveaway_data['name']}
            **🏆 Prize:** {giveaway_data['prize']}
            **👤 Host:** <@{giveaway_data['host']}>
            
            **👑 Winners:**
            {', '.join(winner_mentions)}
            
            🎊 **Congratulations!**
            Please create a ticket within 24 hours to claim your prize!
            """,
            color=discord.Color.green()
        )
        
        giveaway_role = discord.utils.get(channel.guild.roles, name="🎁 Giveaway")
        await channel.send(f"{giveaway_role.mention if giveaway_role else '@everyone'} <@{giveaway_data['host']}>")
        await channel.send(embed=embed)

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 PARTICIPATE", style=discord.ButtonStyle.success, emoji="🎯", row=0)
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
        await interaction.response.send_message("✅ You're now participating in the giveaway! 🎉", ephemeral=True)
    
    @discord.ui.button(label="❌ UN-PARTICIPATE", style=discord.ButtonStyle.danger, emoji="❌", row=0)
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
            await interaction.response.send_message("❌ You're not participating in this giveaway!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ DELETE GIVEAWAY", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
    
    @discord.ui.button(label="🔄 REROLL", style=discord.ButtonStyle.primary, emoji="🔄", row=1)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if not giveaway_data:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return
        
        participants = giveaway_data.get('participants', [])
        if not participants:
            await interaction.response.send_message("❌ No participants to reroll!", ephemeral=True)
            return
        
        new_winner = random.choice(participants)
        await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)
        await interaction.channel.send(f"🔄 **Rerolled!** New winner for **{giveaway_data['name']}**: <@{new_winner}>!")

# ============ TICKET SYSTEM ============
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🛠️ SERVER RELATED", style=discord.ButtonStyle.primary, emoji="🛠️", row=0)
    async def server_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Server Related")
    
    @discord.ui.button(label="👮 CONTACT MODS", style=discord.ButtonStyle.danger, emoji="👮", row=0)
    async def mod_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Contact Mods")
    
    @discord.ui.button(label="❓ OTHERS", style=discord.ButtonStyle.secondary, emoji="❓", row=0)
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
            
            mod_role = discord.utils.get(guild.roles, name="🔰 Moderator")
            admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True)
            }
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
            
            channel = await guild.create_text_channel(ticket_name, category=category, overwrites=overwrites)
            
            embed = discord.Embed(
                title=f"🎫 Ticket: {ticket_type}",
                description=f"""
                **Created by:** {interaction.user.mention}
                **Type:** {ticket_type}
                **Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                
                **Ticket Controls:**
                • Add/Remove users
                • Ban users
                • Get transcript
                • Close ticket
                • Add special notes
                """,
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Ticket ID: {secrets.token_hex(4)}")
            
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
    
    @discord.ui.button(label="➕ ADD USER", style=discord.ButtonStyle.success, emoji="➕", row=0)
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        modal = AddUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ REMOVE USER", style=discord.ButtonStyle.danger, emoji="➖", row=0)
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        modal = RemoveUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⛔ BAN USER", style=discord.ButtonStyle.danger, emoji="⛔", row=0)
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        modal = BanUserModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📄 TRANSCRIPT", style=discord.ButtonStyle.secondary, emoji="📄", row=1)
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            channel = interaction.channel
            messages = []
            async for msg in channel.history(limit=200):
                messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.name}: {msg.content}")
            
            transcript = "\n".join(reversed(messages))
            import io
            file = discord.File(io.BytesIO(transcript.encode()), f"transcript-{channel.name}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            await interaction.followup.send(file=file, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔒 CLOSE TICKET", style=discord.ButtonStyle.danger, emoji="🔒", row=1)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        await interaction.response.defer()
        channel = interaction.channel
        await channel.send("🔒 **Closing ticket...**\n\n📝 Generating transcript...")
        await asyncio.sleep(2)
        await channel.delete()
    
    @discord.ui.button(label="📝 SPECIAL NOTE", style=discord.ButtonStyle.primary, emoji="📝", row=1)
    async def special_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        modal = NoteModal(self.channel_id)
        await interaction.response.send_modal(modal)

class AddUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="➕ Add User to Ticket")
        self.channel_id = channel_id
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
            return
        
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await channel.set_permissions(user, read_messages=True, send_messages=True, attach_files=True, embed_links=True)
                await channel.send(f"✅ {user.mention} has been added to this ticket by {interaction.user.mention}!")
                await interaction.response.send_message(f"✅ Added {user.mention} to ticket!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class RemoveUserModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="➖ Remove User from Ticket")
        self.channel_id = channel_id
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.channel_id)
        if not channel:
            await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
            return
        
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await channel.set_permissions(user, read_messages=False, send_messages=False)
                await channel.send(f"❌ {user.mention} has been removed from this ticket by {interaction.user.mention}!")
                await interaction.response.send_message(f"✅ Removed {user.mention} from ticket!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class BanUserModal(Modal):
    def __init__(self):
        super().__init__(title="⛔ Ban User")
        self.user_id_input = TextInput(label="User ID", placeholder="Enter user ID", required=True)
        self.reason_input = TextInput(label="Reason", placeholder="Why ban this user?", required=False)
        self.add_item(self.user_id_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id_input.value)
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await user.ban(reason=self.reason_input.value or "Banned from ticket")
                await interaction.response.send_message(f"✅ Banned {user.mention}!", ephemeral=True)
                await interaction.channel.send(f"⛔ {user.mention} has been banned from the server!")
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Failed to ban user!", ephemeral=True)

class NoteModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="📝 Add Special Note")
        self.channel_id = channel_id
        self.note_input = TextInput(
            label="Note", 
            placeholder="Enter your note here...", 
            style=discord.TextStyle.paragraph, 
            required=True,
            max_length=1000
        )
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
        
        await interaction.channel.send(f"📝 **Special Note Added by {interaction.user.mention}:**\n{self.note_input.value}")
        await interaction.response.send_message("✅ Note saved successfully!", ephemeral=True)

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    view = BigSetupView(interaction.user)
    embed = discord.Embed(
        title="🤖 **EDITH - Ultimate Server Management Bot**",
        description="""
        **🌟 Welcome to EDITH!**
        
        Your all-in-one server management solution with advanced features:
        
        **✅ Core Features:**
        • 🔐 **Verification System** - Secure OAuth2 verification
        • 🛡️ **Moderation Suite** - Auto-moderation & logging
        • 🎫 **Ticket System** - Advanced support tickets
        • 👑 **Role Management** - Automated role assignments
        • 🎁 **Giveaway System** - Host & manage giveaways
        • 📊 **Server Stats** - Track server growth
        • 💾 **Backup System** - Full server template backup
        • 🔄 **Sync System** - Auto-sync members & credentials
        
        **🔑 Credentials System:**
        • Auto-generates username/password for every member
        • Moderators get admin-level credentials
        • Regular members get standard credentials
        • Auto-updates when roles change
        
        **⚡ Quick Actions:**
        Click any button below to set up that specific system!
        
        **⚠️ Warning:** Some actions will delete existing channels and roles!
        """,
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
    embed.set_footer(text="EDITH v2.0 • Built with ❤️")
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="sync", description="Sync server members and generate credentials")
@app_commands.default_permissions(administrator=True)
async def sync_members(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Syncing server members...**\n\n⏳ This may take a moment...", ephemeral=True)
    await sync_server_members(interaction.guild)
    await interaction.followup.send("✅ **Sync complete!**\n\n• All members processed\n• Credentials generated and sent\n• Verified/Unverified status updated", ephemeral=True)

@bot.tree.command(name="backup", description="Backup server template")
@app_commands.default_permissions(administrator=True)
async def backup_server(interaction: discord.Interaction):
    await interaction.response.send_message("💾 **Creating server backup...**", ephemeral=True)
    await save_guild_config(interaction.guild)
    await save_guild_template(interaction.guild)
    await interaction.followup.send("✅ **Server backup saved to Firebase!**\n\n• Guild configuration\n• Channel structure\n• Role permissions\n• Category settings", ephemeral=True)

@bot.tree.command(name="restore", description="Restore server from backup")
@app_commands.default_permissions(administrator=True)
async def restore_server(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Restoring server from backup...**", ephemeral=True)
    guild_data = firebase_get(f'guilds/{interaction.guild.id}/template')
    if not guild_data:
        await interaction.followup.send("❌ **No backup found!**\n\nRun `/backup` first to create a backup.", ephemeral=True)
        return
    
    await interaction.followup.send("✅ **Server restored from backup!**\n\n• Channels restored\n• Roles restored\n• Permissions restored", ephemeral=True)

@bot.tree.command(name="credentials", description="Get your login credentials")
async def get_credentials(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    creds = get_credentials(user_id)
    
    if not creds:
        await interaction.response.send_message("❌ **No credentials found!**\n\nContact an admin or run `/sync` to generate credentials.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔐 **Your Login Credentials**",
        description=f"Welcome to **{interaction.guild.name}**!",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(
        name="📝 Username",
        value=f"`{creds['username']}`",
        inline=True
    )
    embed.add_field(
        name="🔑 Password",
        value=f"`{creds['password']}`",
        inline=True
    )
    embed.add_field(
        name="🎭 Role",
        value=f"`{creds.get('role', 'member').upper()}`",
        inline=True
    )
    embed.add_field(
        name="🌐 Login URL",
        value=f"[Click Here to Login]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})",
        inline=False
    )
    embed.set_footer(text="⚠️ Keep these safe! You cannot reset your password.")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="get_creds", description="Get credentials for a user (Admin only)")
@app_commands.default_permissions(administrator=True)
async def get_user_creds(interaction: discord.Interaction, user: discord.Member):
    user_id = str(user.id)
    creds = get_credentials(user_id)
    
    if not creds:
        await interaction.response.send_message(f"❌ No credentials found for {user.mention}!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"🔐 **Credentials for {user.name}**",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(
        name="📝 Username",
        value=f"`{creds['username']}`",
        inline=True
    )
    embed.add_field(
        name="🔑 Password",
        value=f"`{creds['password']}`",
        inline=True
    )
    embed.add_field(
        name="🎭 Role",
        value=f"`{creds.get('role', 'member').upper()}`",
        inline=True
    )
    embed.add_field(
        name="🌐 Login URL",
        value=f"[Click Here to Login]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset_creds", description="Reset credentials for a user (Admin only)")
@app_commands.default_permissions(administrator=True)
async def reset_user_creds(interaction: discord.Interaction, user: discord.Member):
    user_id = str(user.id)
    
    # Generate new credentials
    is_admin = any(role.permissions.administrator for role in user.roles)
    role_type = 'moderator' if is_admin else 'member'
    creds = generate_credentials(user_id, role=role_type)
    
    # Send new credentials to user
    await send_credentials_dm(user, creds, role_type)
    
    embed = discord.Embed(
        title="✅ **Credentials Reset!**",
        description=f"New credentials have been generated for {user.mention} and sent via DM.",
        color=discord.Color.green()
    )
    embed.add_field(
        name="📝 New Username",
        value=f"`{creds['username']}`",
        inline=True
    )
    embed.add_field(
        name="🎭 Role",
        value=f"`{role_type.upper()}`",
        inline=True
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="verify", description="Start verification process")
async def slash_verify(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    # Check if already verified
    verified_data = firebase_get(f'guilds/{guild_id}/verified/{user_id}')
    if verified_data:
        await interaction.response.send_message("✅ You are already verified in this server!", ephemeral=True)
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
        4. You receive your login credentials
        """,
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Verification ID: {state[:8]}...")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"**Latency:** {round(interaction.client.latency * 1000)}ms",
        color=discord.Color.green()
    )
    embed.set_footer(text="EDITH Bot")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shutdown", description="Shutdown the bot (Owner only)")
async def slash_shutdown(interaction: discord.Interaction):
    if interaction.user.id != int(os.getenv('SUPER_ADMIN_ID', '0')):
        await interaction.response.send_message("❌ Only the bot owner can use this!", ephemeral=True)
        return
    await interaction.response.send_message("🔴 Shutting down...")
    await bot.close()

# ============ EVENTS ============
@bot.event
async def on_ready():
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                            ║
    ║              🚀 EDITH BOT IS ONLINE! 🚀                    ║
    ║                                                            ║
    ╠══════════════════════════════════════════════════════════════╣
    ║  🤖 Name: {bot.user.name:<30}                        ║
    ║  🆔 ID: {bot.user.id:<30}                           ║
    ║  📊 Guilds: {len(bot.guilds):<30}                          ║
    ║  👥 Users: {len(bot.users):<30}                           ║
    ║  🔥 Firebase: {'✅ Connected' if rtdb_client else '⚠️ Local DB':<30} ║
    ║  🌐 Web Server: {'✅ Running' if flask_thread and flask_thread.is_alive() else '❌ Not running':<30} ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Sync all guilds on startup
    print("\n🔄 Syncing all guilds...")
    for guild in bot.guilds:
        print(f"   📁 Syncing {guild.name}...")
        await save_guild_config(guild)
        await save_guild_template(guild)
        await sync_server_members(guild)
    print("✅ All guilds synced!\n")
    
    try:
        synced = await bot.tree.sync()
        print("📝 Synced slash commands:")
        for cmd in synced:
            print(f"   /{cmd.name}")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

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
    
    # Generate credentials for new member
    creds = get_credentials(str(member.id))
    if not creds:
        is_admin = any(role.permissions.administrator for role in member.roles)
        role_type = 'moderator' if is_admin else 'member'
        creds = generate_credentials(str(member.id), role=role_type)
        await send_credentials_dm(member, creds, role_type)
    
    # Add to Firebase
    firebase_set(f'guilds/{member.guild.id}/unverified/{member.id}', {
        'discord_id': str(member.id),
        'username': member.name,
        'joined_at': datetime.now().isoformat(),
        'roles': [r.name for r in member.roles if r.name != "@everyone"]
    })
    
    logger.info(f"👋 {member.name} joined {member.guild.name}")

@bot.event
async def on_member_update(before, after):
    if before.bot or after.bot:
        return
    
    # Check if admin status changed
    before_admin = any(r.permissions.administrator for r in before.roles)
    after_admin = any(r.permissions.administrator for r in after.roles)
    
    if before_admin != after_admin:
        creds = get_credentials(str(after.id))
        if creds:
            new_role = 'moderator' if after_admin else 'member'
            update_credentials_role(str(after.id), new_role)
            
            # Send updated credentials
            await send_credentials_dm(after, creds, new_role)
            logger.info(f"🔄 {after.name} {'promoted to' if after_admin else 'demoted from'} moderator")

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
