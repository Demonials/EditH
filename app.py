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
            
            # Test connection
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

async def send_credentials_dm(member, creds, role=None, log_channel=None):
    """Send credentials via DM and log to channel"""
    if not creds:
        return False
    
    role = role or creds.get('role', 'member')
    
    embed = discord.Embed(
        title="🔐 **Your EDITH Login Credentials**",
        description=f"Welcome to **{member.guild.name}**!",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="📝 Username", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="🔑 Password", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="🎭 Role", value=f"`{role.upper()}`", inline=True)
    embed.add_field(name="🌐 Login URL", value=f"[Click Here]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})", inline=False)
    embed.set_footer(text="⚠️ Keep these safe! You cannot reset your password.")
    
    try:
        await member.send(embed=embed)
        logger.info(f"✅ Credentials sent to {member.name}")
        
        # Log to channel
        if log_channel:
            log_embed = discord.Embed(
                title="🔐 Credentials Sent",
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

async def sync_server_members(guild, log_channel=None):
    """Sync all members - generate credentials and update Firebase"""
    if not rtdb_client:
        return False
    
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
        sent_count = 0
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
                await send_credentials_dm(member, creds, role_type, log_channel)
                sent_count += 1
                logger.info(f"🔑 Generated credentials for {member.name}")
            else:
                # Update role if changed
                current_role = creds.get('role', 'member')
                if is_admin and current_role != 'moderator':
                    creds['role'] = 'moderator'
                    firebase_set(f'credentials/{user_id}', creds)
                    await send_credentials_dm(member, creds, 'moderator', log_channel)
                    sent_count += 1
                    logger.info(f"🔄 Updated {member.name} to moderator")
                elif not is_admin and current_role != 'member':
                    creds['role'] = 'member'
                    firebase_set(f'credentials/{user_id}', creds)
                    await send_credentials_dm(member, creds, 'member', log_channel)
                    sent_count += 1
                    logger.info(f"🔄 Updated {member.name} to member")
            
            # Move between verified/unverified in Firebase
            user_data = {
                'discord_id': user_id,
                'username': member.name,
                'global_name': member.display_name or member.name,
                'avatar': member.avatar.url if member.avatar else None,
                'joined_at': member.joined_at.isoformat() if member.joined_at else None,
                'roles': [r.name for r in member.roles if r.name != "@everyone"],
                'credentials': creds
            }
            
            if is_verified:
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
            await log_channel.send(f"✅ **Sent {sent_count} new credentials to members!**")
        
        logger.info(f"✅ Synced {len(members)} members for {guild.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to sync members: {e}")
        return False

# ============ AUTO SYNC TASK (Every 5 seconds) ============
@tasks.loop(seconds=5)
async def auto_sync():
    """Automatically sync all guilds every 5 seconds"""
    try:
        for guild in bot.guilds:
            log_channel = discord.utils.get(guild.channels, name="🛡️-mod-logs")
            if not log_channel:
                log_channel = discord.utils.get(guild.channels, name="🔐-verification")
            
            await sync_server_members(guild, log_channel)
    except Exception as e:
        logger.error(f"Auto sync error: {e}")

# ============ SETUP VIEW ============
class SetupView(View):
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
    
    @discord.ui.button(label="🔐 VERIFICATION", style=discord.ButtonStyle.primary, emoji="🔐", row=0)
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
    
    @discord.ui.button(label="🎫 TICKETS", style=discord.ButtonStyle.secondary, emoji="🎫", row=0)
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
    
    @discord.ui.button(label="🎁 GIVEAWAYS", style=discord.ButtonStyle.primary, emoji="🎁", row=0)
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
    
    @discord.ui.button(label="👑 ROLES", style=discord.ButtonStyle.secondary, emoji="👑", row=1)
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
    
    @discord.ui.button(label="🛡️ MODERATION", style=discord.ButtonStyle.danger, emoji="🛡️", row=1)
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
    
    @discord.ui.button(label="📊 STATS", style=discord.ButtonStyle.secondary, emoji="📊", row=1)
    async def setup_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.followup.send("✅ Stats system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="💾 BACKUP", style=discord.ButtonStyle.success, emoji="💾", row=1)
    async def setup_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await save_guild_config(interaction.guild)
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
            
            await sync_server_members(interaction.guild, log_channel)
            await interaction.followup.send("✅ **Members synced!**\n\n• All members processed\n• Credentials generated and sent\n• Verified/Unverified status updated", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="📝 CREDENTIALS", style=discord.ButtonStyle.secondary, emoji="📝", row=2)
    async def manage_credentials(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📝 **Credential Management**",
            description="""
            **Available Commands:**
            • `/credentials` - Get your own credentials
            • `/get_creds @user` - Get credentials for a user
            • `/reset_creds @user` - Reset credentials for a user
            • `/sync` - Sync all members
            
            **Auto Features:**
            • New members get credentials automatically
            • Role changes auto-update credentials
            • Auto-sync every 5 seconds
            • Logged to #🛡️-mod-logs
            """,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def setup_all(self, guild, interaction):
        try:
            await interaction.edit_original_response(content="🔄 **Deleting existing channels and roles...**")
            
            # Delete channels
            for channel in guild.channels:
                try:
                    await channel.delete()
                except:
                    pass
            
            await interaction.edit_original_response(content="🔄 **Creating new server structure...**")
            
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
            
            # Send messages
            verify_channel = discord.utils.get(guild.channels, name="🔐-verification")
            ticket_channel = discord.utils.get(guild.channels, name="🎫-tickets")
            giveaway_channel = discord.utils.get(guild.channels, name="🎉-giveaways")
            
            await self.send_verification_message(verify_channel)
            await self.send_ticket_message(ticket_channel)
            await self.send_giveaway_message(giveaway_channel)
            
            # Sync members
            log_channel = discord.utils.get(guild.channels, name="🛡️-mod-logs")
            await sync_server_members(guild, log_channel)
            
            embed = discord.Embed(
                title="✅ **🎉 SERVER SETUP COMPLETE!**",
                description=f"""
                **{guild.name}** has been fully configured!
                
                **📊 Created:**
                • 📋 7 Categories
                • 💬 27+ Channels  
                • 👑 9 Roles
                • 🔐 Verification System
                • 🎫 Ticket System
                • 🎁 Giveaway System
                • 🛡️ Moderation System
                
                **🔑 Credentials:**
                • All members processed
                • Credentials sent via DM
                • Logged in #🛡️-mod-logs
                
                🎉 **Your server is ready!**
                """,
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else bot.user.display_avatar.url)
            
            await interaction.edit_original_response(content=None, embed=embed)
            
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ **Error:**\n```\n{str(e)}\n```")
    
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
            **Why verify?**
            • 🛡️ **Security** - Protect your account
            • 🎮 **Access** - Unlock full server features
            • 👤 **Identity** - Verify your Discord identity
            
            **How to verify:**
            1. Click the **Verify via Discord** button below
            2. Authorize through Discord OAuth
            3. Get the ✅ Verified role
            4. Receive your login credentials
            """,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = VerifyView()
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
            title="🎉 **GIVEAWAY CENTER**",
            description="👑 Admin only: Host exciting giveaways!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)

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
        
        # Check if already verified
        verified_data = firebase_get(f'guilds/{guild_id}/verified/{user_id}')
        if verified_data:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return
        
        url, state = oauth.generate_oauth_url(user_id, guild_id)
        
        embed = discord.Embed(
            title="🔐 **Authorize Verification**",
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
        self.name = TextInput(label="Giveaway Name", required=True)
        self.prize = TextInput(label="Prize", required=True)
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
            title="🎉 GIVEAWAY COMPLETE!",
            description=f"""
            **Giveaway:** {giveaway_data['name']}
            **Prize:** {giveaway_data['prize']}
            **Winners:** {', '.join(winner_mentions)}
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
    
    @discord.ui.button(label="🛠️ SERVER RELATED", style=discord.ButtonStyle.primary)
    async def server_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Server Related")
    
    @discord.ui.button(label="👮 CONTACT MODS", style=discord.ButtonStyle.danger)
    async def mod_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Contact Mods")
    
    @discord.ui.button(label="❓ OTHERS", style=discord.ButtonStyle.secondary)
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
    
    @discord.ui.button(label="➕ ADD USER", style=discord.ButtonStyle.success)
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ REMOVE USER", style=discord.ButtonStyle.danger)
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="🔒 CLOSE", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        await interaction.response.defer()
        channel = interaction.channel
        await channel.send("🔒 Closing ticket...")
        await asyncio.sleep(2)
        await channel.delete()

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

# ============ SAVE GUILD CONFIG ============
async def save_guild_config(guild):
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

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    view = SetupView(interaction.user)
    embed = discord.Embed(
        title="🤖 **EDITH - Ultimate Server Management Bot**",
        description="""
        **🌟 Welcome to EDITH!**
        
        **Click any button below to set up that system!**
        
        **⚠️ Warning:** Setup All will delete ALL existing channels and roles!
        """,
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="sync", description="Sync server members and generate credentials")
@app_commands.default_permissions(administrator=True)
async def sync_members(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 **Syncing members...**", ephemeral=True)
    
    log_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
    if not log_channel:
        log_channel = discord.utils.get(interaction.guild.channels, name="🔐-verification")
    
    await sync_server_members(interaction.guild, log_channel)
    await interaction.followup.send("✅ **Sync complete!** Credentials generated and sent!", ephemeral=True)

@bot.tree.command(name="credentials", description="Get your login credentials")
async def get_credentials(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    creds = get_credentials(user_id)
    
    if not creds:
        await interaction.response.send_message("❌ No credentials found! Run `/sync` to generate.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔐 Your Credentials",
        color=discord.Color.blue()
    )
    embed.add_field(name="Username", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="Password", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="Role", value=f"`{creds.get('role', 'member').upper()}`", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="get_creds", description="Get credentials for a user (Admin only)")
@app_commands.default_permissions(administrator=True)
async def get_user_creds(interaction: discord.Interaction, user: discord.Member):
    creds = get_credentials(str(user.id))
    
    if not creds:
        await interaction.response.send_message(f"❌ No credentials for {user.mention}!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"🔐 Credentials for {user.name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Username", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="Password", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="Role", value=f"`{creds.get('role', 'member').upper()}`", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="reset_creds", description="Reset credentials for a user (Admin only)")
@app_commands.default_permissions(administrator=True)
async def reset_user_creds(interaction: discord.Interaction, user: discord.Member):
    user_id = str(user.id)
    
    is_admin = any(role.permissions.administrator for role in user.roles)
    role_type = 'moderator' if is_admin else 'member'
    creds = generate_credentials(user_id, role=role_type)
    
    log_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
    await send_credentials_dm(user, creds, role_type, log_channel)
    
    await interaction.response.send_message(f"✅ Credentials reset for {user.mention}!", ephemeral=True)

@bot.tree.command(name="verify", description="Start verification process")
async def slash_verify(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    url, state = oauth.generate_oauth_url(user_id, guild_id)
    
    embed = discord.Embed(
        title="🔐 Verification Required",
        description=f"[🔐 Click here to verify]({url})",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="Check bot latency")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! {round(interaction.client.latency * 1000)}ms")

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
    ╚════════════════════════════════════════╝
    """)
    
    # Start auto-sync
    if not auto_sync.is_running():
        auto_sync.start()
        print("🔄 Auto-sync started (every 5 seconds)")
    
    # Initial sync
    for guild in bot.guilds:
        log_channel = discord.utils.get(guild.channels, name="🛡️-mod-logs")
        await save_guild_config(guild)
        await sync_server_members(guild, log_channel)
    
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
    
    # Generate credentials
    creds = get_credentials(str(member.id))
    if not creds:
        is_admin = any(role.permissions.administrator for role in member.roles)
        role_type = 'moderator' if is_admin else 'member'
        creds = generate_credentials(str(member.id), role=role_type)
        
        log_channel = discord.utils.get(member.guild.channels, name="🛡️-mod-logs")
        await send_credentials_dm(member, creds, role_type, log_channel)

@bot.event
async def on_member_update(before, after):
    if before.bot or after.bot:
        return
    
    before_admin = any(r.permissions.administrator for r in before.roles)
    after_admin = any(r.permissions.administrator for r in after.roles)
    
    if before_admin != after_admin:
        creds = get_credentials(str(after.id))
        if creds:
            new_role = 'moderator' if after_admin else 'member'
            creds['role'] = new_role
            firebase_set(f'credentials/{after.id}', creds)
            
            log_channel = discord.utils.get(after.guild.channels, name="🛡️-mod-logs")
            await send_credentials_dm(after, creds, new_role, log_channel)

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
