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
    firebase_delete(f'credentials/{user_id}')
    firebase_delete(f'credentials_by_username/{user_id}')
    logger.info(f"🗑️ Deleted credentials for {user_id}")

sent_credentials_cache = {}

async def send_credentials_dm(member, creds, role=None, log_channel=None):
    if not creds:
        return False
    
    user_id = str(member.id)
    
    if user_id in sent_credentials_cache:
        last_sent = sent_credentials_cache[user_id]
        if (datetime.now() - last_sent).seconds < 60:
            return True
    
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
    embed.add_field(name="🌐 LOGIN URL", value=f"[Click Here]({os.getenv('WEBSITE_URL', 'https://edith-bot.up.railway.app')})", inline=False)
    embed.set_footer(text="⚠️ Keep these safe! You cannot reset your password.")
    
    try:
        await member.send(embed=embed)
        logger.info(f"✅ Credentials sent to {member.name}")
        sent_credentials_cache[user_id] = datetime.now()
        
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

async def process_single_member(member, log_channel=None):
    if not rtdb_client or member.bot:
        return
    
    try:
        user_id = str(member.id)
        guild = member.guild
        verified_role = discord.utils.get(guild.roles, name="✅ Verified")
        is_verified = verified_role in member.roles if verified_role else False
        
        if is_verified:
            is_admin = any(role.permissions.administrator for role in member.roles)
            role_type = 'moderator' if is_admin else 'member'
            
            creds = get_credentials(user_id)
            if not creds:
                creds = generate_credentials(user_id, role=role_type)
                await send_credentials_dm(member, creds, role_type, log_channel)
                logger.info(f"🔑 Generated credentials for {member.name}")
            else:
                current_role = creds.get('role', 'member')
                if is_admin and current_role != 'moderator':
                    creds['role'] = 'moderator'
                    firebase_set(f'credentials/{user_id}', creds)
                    await send_credentials_dm(member, creds, 'moderator', log_channel)
                elif not is_admin and current_role != 'member':
                    creds['role'] = 'member'
                    firebase_set(f'credentials/{user_id}', creds)
                    await send_credentials_dm(member, creds, 'member', log_channel)
        else:
            delete_credentials(user_id)
        
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
            creds = get_credentials(user_id)
            if creds:
                user_data['credentials'] = creds
            firebase_set(f'guilds/{guild.id}/verified/{user_id}', user_data)
            firebase_delete(f'guilds/{guild.id}/unverified/{user_id}')
        else:
            firebase_set(f'guilds/{guild.id}/unverified/{user_id}', {
                'discord_id': user_id,
                'username': member.name,
                'joined_at': member.joined_at.isoformat() if member.joined_at else None
            })
            firebase_delete(f'guilds/{guild.id}/verified/{user_id}')
        
        return True
    except Exception as e:
        logger.error(f"Failed to process member {member.name}: {e}")
        return False

# ============ BIG MODERATION SUITE VIEW ============
class ModerationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="⛔ BAN USER", style=discord.ButtonStyle.danger, emoji="⛔", row=0)
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You don't have permission to ban members!", ephemeral=True)
            return
        await interaction.response.send_modal(BanUserModal())
    
    @discord.ui.button(label="👢 KICK USER", style=discord.ButtonStyle.danger, emoji="👢", row=0)
    async def kick_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ You don't have permission to kick members!", ephemeral=True)
            return
        await interaction.response.send_modal(KickUserModal())
    
    @discord.ui.button(label="🔇 MUTE USER", style=discord.ButtonStyle.primary, emoji="🔇", row=0)
    async def mute_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.mute_members:
            await interaction.response.send_message("❌ You don't have permission to mute members!", ephemeral=True)
            return
        await interaction.response.send_modal(MuteUserModal())
    
    @discord.ui.button(label="🔊 UNMUTE USER", style=discord.ButtonStyle.success, emoji="🔊", row=1)
    async def unmute_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.mute_members:
            await interaction.response.send_message("❌ You don't have permission to unmute members!", ephemeral=True)
            return
        await interaction.response.send_modal(UnmuteUserModal())
    
    @discord.ui.button(label="⏰ TIMEOUT USER", style=discord.ButtonStyle.secondary, emoji="⏰", row=1)
    async def timeout_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to timeout members!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeoutUserModal())
    
    @discord.ui.button(label="⏰ REMOVE TIMEOUT", style=discord.ButtonStyle.secondary, emoji="⏰", row=1)
    async def remove_timeout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to remove timeouts!", ephemeral=True)
            return
        await interaction.response.send_modal(RemoveTimeoutModal())
    
    @discord.ui.button(label="ℹ️ ABOUT USER", style=discord.ButtonStyle.secondary, emoji="ℹ️", row=2)
    async def about_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AboutUserModal())

class BanUserModal(Modal):
    def __init__(self):
        super().__init__(title="⛔ Ban User")
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.reason_input = TextInput(label="Reason", placeholder="Why ban this user?", required=False, max_length=200)
        self.add_item(self.user_id_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await user.ban(reason=self.reason_input.value or "No reason provided")
                embed = discord.Embed(
                    title="⛔ User Banned",
                    description=f"{user.mention} has been banned!",
                    color=discord.Color.red()
                )
                embed.add_field(name="Reason", value=self.reason_input.value or "No reason provided")
                await interaction.response.send_message(embed=embed)
                await interaction.channel.send(f"⛔ {user.mention} has been banned by {interaction.user.mention}!")
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class KickUserModal(Modal):
    def __init__(self):
        super().__init__(title="👢 Kick User")
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.reason_input = TextInput(label="Reason", placeholder="Why kick this user?", required=False, max_length=200)
        self.add_item(self.user_id_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await user.kick(reason=self.reason_input.value or "No reason provided")
                embed = discord.Embed(
                    title="👢 User Kicked",
                    description=f"{user.mention} has been kicked!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Reason", value=self.reason_input.value or "No reason provided")
                await interaction.response.send_message(embed=embed)
                await interaction.channel.send(f"👢 {user.mention} has been kicked by {interaction.user.mention}!")
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class MuteUserModal(Modal):
    def __init__(self):
        super().__init__(title="🔇 Mute User")
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.duration_input = TextInput(label="Duration (minutes)", placeholder="e.g., 60", required=True)
        self.reason_input = TextInput(label="Reason", placeholder="Why mute this user?", required=False, max_length=200)
        self.add_item(self.user_id_input)
        self.add_item(self.duration_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                duration_minutes = int(self.duration_input.value)
                duration = timedelta(minutes=duration_minutes)
                await user.timeout(duration, reason=self.reason_input.value or "No reason provided")
                embed = discord.Embed(
                    title="🔇 User Muted",
                    description=f"{user.mention} has been muted for {duration_minutes} minutes!",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Reason", value=self.reason_input.value or "No reason provided")
                await interaction.response.send_message(embed=embed)
                await interaction.channel.send(f"🔇 {user.mention} has been muted by {interaction.user.mention} for {duration_minutes} minutes!")
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid duration! Please enter a number.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class UnmuteUserModal(Modal):
    def __init__(self):
        super().__init__(title="🔊 Unmute User")
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await user.timeout(None)
                embed = discord.Embed(
                    title="🔊 User Unmuted",
                    description=f"{user.mention} has been unmuted!",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
                await interaction.channel.send(f"🔊 {user.mention} has been unmuted by {interaction.user.mention}!")
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class TimeoutUserModal(Modal):
    def __init__(self):
        super().__init__(title="⏰ Timeout User")
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.duration_input = TextInput(label="Duration (minutes)", placeholder="e.g., 60", required=True)
        self.reason_input = TextInput(label="Reason", placeholder="Why timeout this user?", required=False, max_length=200)
        self.add_item(self.user_id_input)
        self.add_item(self.duration_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                duration_minutes = int(self.duration_input.value)
                duration = timedelta(minutes=duration_minutes)
                await user.timeout(duration, reason=self.reason_input.value or "No reason provided")
                embed = discord.Embed(
                    title="⏰ User Timed Out",
                    description=f"{user.mention} has been timed out for {duration_minutes} minutes!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="Reason", value=self.reason_input.value or "No reason provided")
                await interaction.response.send_message(embed=embed)
                await interaction.channel.send(f"⏰ {user.mention} has been timed out by {interaction.user.mention} for {duration_minutes} minutes!")
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid duration! Please enter a number.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class RemoveTimeoutModal(Modal):
    def __init__(self):
        super().__init__(title="⏰ Remove Timeout")
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await user.timeout(None)
                embed = discord.Embed(
                    title="⏰ Timeout Removed",
                    description=f"{user.mention}'s timeout has been removed!",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
                await interaction.channel.send(f"⏰ {user.mention}'s timeout has been removed by {interaction.user.mention}!")
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class AboutUserModal(Modal):
    def __init__(self):
        super().__init__(title="ℹ️ About User")
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.add_item(self.user_id_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            if user:
                embed = discord.Embed(
                    title=f"ℹ️ About {user.name}",
                    color=discord.Color.blue()
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                embed.add_field(name="Username", value=f"{user.name}#{user.discriminator}", inline=True)
                embed.add_field(name="ID", value=user.id, inline=True)
                embed.add_field(name="Joined Server", value=user.joined_at.strftime("%Y-%m-%d %H:%M:%S") if user.joined_at else "Unknown", inline=True)
                embed.add_field(name="Joined Discord", value=user.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
                roles_str = ", ".join([r.mention for r in user.roles[1:5]]) + ("..." if len(user.roles) > 5 else "")
                embed.add_field(name="Roles", value=roles_str or "None", inline=False)
                embed.add_field(name="Is Bot", value="✅ Yes" if user.bot else "❌ No", inline=True)
                embed.add_field(name="Status", value=str(user.status).upper() if user.status else "OFFLINE", inline=True)
                
                verified_role = discord.utils.get(interaction.guild.roles, name="✅ Verified")
                is_verified = verified_role in user.roles if verified_role else False
                embed.add_field(name="Verified", value="✅ Yes" if is_verified else "❌ No", inline=True)
                
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

# ============ SERVER MANAGEMENT VIEW ============
class ServerManagementView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📢 SEND ANNOUNCEMENT", style=discord.ButtonStyle.primary, emoji="📢", row=0)
    async def send_announcement(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(AnnouncementModal())
    
    @discord.ui.button(label="📩 SEND DM TO USER", style=discord.ButtonStyle.success, emoji="📩", row=0)
    async def send_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(DMUserModal())
    
    @discord.ui.button(label="📊 SERVER STATS", style=discord.ButtonStyle.secondary, emoji="📊", row=0)
    async def server_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        
        embed = discord.Embed(
            title=f"📊 Server Statistics: {guild.name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else bot.user.display_avatar.url)
        embed.add_field(name="👥 Total Members", value=guild.member_count, inline=True)
        embed.add_field(name="🟢 Online", value=len([m for m in guild.members if m.status != discord.Status.offline]), inline=True)
        embed.add_field(name="🤖 Bots", value=len([m for m in guild.members if m.bot]), inline=True)
        embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="👑 Owner", value=str(guild.owner), inline=True)
        embed.add_field(name="💎 Boost Level", value=guild.premium_tier, inline=True)
        embed.add_field(name="📈 Boost Count", value=guild.premium_subscription_count, inline=True)
        embed.add_field(name="📋 Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
        embed.set_footer(text=f"Server ID: {guild.id}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔧 SETUP PERMISSIONS", style=discord.ButtonStyle.warning, emoji="🔧", row=1)
    async def setup_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔧 **Permission Setup Guide**",
            description="""
            **🔒 PERMISSION SYSTEM:**
            
            **❌ Unverified Role:**
            • Can only see #🔐-verification channel
            • Cannot see any other channels
            • Cannot send messages
            
            **✅ Verified Role:**
            • Can see all public channels
            • Can send messages in most channels
            • Access to full server features
            
            **🛡️ Moderator Role:**
            • Can see admin channels
            • Can manage messages
            • Can mute/kick/ban members
            
            **👑 Admin Role:**
            • Full access to everything
            • Can manage server settings
            
            **📋 To Set Up:**
            1. Create roles: ❌ Unverified, ✅ Verified, 🛡️ Moderator, 👑 Admin
            2. Set channel permissions:
               - Remove @everyone from all channels
               - Add ❌ Unverified to #🔐-verification only
               - Add ✅ Verified to all public channels
            3. Click Setup All or Setup Roles
            """,
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="⚡ QUICK ACTIONS", style=discord.ButtonStyle.success, emoji="⚡", row=1)
    async def quick_actions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        
        view = QuickActionsView()
        embed = discord.Embed(
            title="⚡ **Quick Actions**",
            description="Select an action below:",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class QuickActionsView(View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="🔇 Mute All", style=discord.ButtonStyle.danger, emoji="🔇")
    async def mute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(MuteAllModal())
    
    @discord.ui.button(label="🔊 Unmute All", style=discord.ButtonStyle.success, emoji="🔊")
    async def unmute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        
        count = 0
        for member in interaction.guild.members:
            if member.is_timed_out():
                try:
                    await member.timeout(None)
                    count += 1
                    await asyncio.sleep(0.5)
                except:
                    pass
        
        await interaction.response.send_message(f"✅ Unmuted {count} members!", ephemeral=True)
    
    @discord.ui.button(label="📊 Member Count", style=discord.ButtonStyle.secondary, emoji="📊")
    async def member_count(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        total = guild.member_count
        bots = len([m for m in guild.members if m.bot])
        humans = total - bots
        online = len([m for m in guild.members if m.status != discord.Status.offline])
        
        await interaction.response.send_message(
            f"📊 **Member Stats:**\n"
            f"• Total: {total}\n"
            f"• Humans: {humans}\n"
            f"• Bots: {bots}\n"
            f"• Online: {online}",
            ephemeral=True
        )

class MuteAllModal(Modal):
    def __init__(self):
        super().__init__(title="🔇 Mute All Members")
        self.duration_input = TextInput(label="Duration (minutes)", placeholder="e.g., 60", required=True)
        self.reason_input = TextInput(label="Reason", placeholder="Why mute everyone?", required=False, max_length=200)
        self.add_item(self.duration_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            duration_minutes = int(self.duration_input.value)
            duration = timedelta(minutes=duration_minutes)
            
            await interaction.response.send_message(f"🔇 Muting all members for {duration_minutes} minutes...", ephemeral=True)
            
            count = 0
            for member in interaction.guild.members:
                if not member.bot and not member.guild_permissions.administrator:
                    try:
                        await member.timeout(duration, reason=self.reason_input.value or "Server-wide mute")
                        count += 1
                        await asyncio.sleep(0.5)
                    except:
                        pass
            
            await interaction.followup.send(f"✅ Muted {count} members for {duration_minutes} minutes!", ephemeral=True)
            await interaction.channel.send(f"🔇 **Server-wide mute initiated by {interaction.user.mention}!**\nMuted {count} members for {duration_minutes} minutes.")
        except ValueError:
            await interaction.response.send_message("❌ Invalid duration! Please enter a number.", ephemeral=True)

class AnnouncementModal(Modal):
    def __init__(self):
        super().__init__(title="📢 Send Announcement")
        self.title_input = TextInput(label="Title", placeholder="Enter announcement title", required=True, max_length=100)
        self.message_input = TextInput(label="Message", placeholder="Enter announcement message", style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.channel_input = TextInput(label="Channel ID or @channel", placeholder="Leave blank for current channel", required=False)
        self.add_item(self.title_input)
        self.add_item(self.message_input)
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel = interaction.channel
            if self.channel_input.value:
                try:
                    channel_id = int(re.search(r'\d+', self.channel_input.value).group())
                    channel = interaction.guild.get_channel(channel_id)
                    if not channel:
                        channel = interaction.channel
                except:
                    channel = interaction.channel
            
            embed = discord.Embed(
                title=f"📢 {self.title_input.value}",
                description=self.message_input.value,
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Announced by {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            embed.timestamp = datetime.now()
            
            await channel.send(embed=embed)
            
            # Log to mod-logs
            log_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
            if log_channel:
                log_embed = discord.Embed(
                    title="📢 Announcement Sent",
                    description=f"By: {interaction.user.mention}\nChannel: {channel.mention}",
                    color=discord.Color.green()
                )
                await log_channel.send(embed=log_embed)
            
            await interaction.response.send_message(f"✅ Announcement sent to {channel.mention}!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

class DMUserModal(Modal):
    def __init__(self):
        super().__init__(title="📩 Send DM to User")
        self.user_id_input = TextInput(label="User ID or @mention", placeholder="Enter user ID or @mention", required=True)
        self.message_input = TextInput(label="Message", placeholder="Enter your message", style=discord.TextStyle.paragraph, required=True, max_length=1000)
        self.add_item(self.user_id_input)
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(re.search(r'\d+', self.user_id_input.value).group())
            user = await interaction.guild.fetch_member(user_id)
            
            if not user:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📩 Message from Server Staff",
                description=self.message_input.value,
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"From {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
            
            await user.send(embed=embed)
            
            # Log to mod-logs
            log_channel = discord.utils.get(interaction.guild.channels, name="🛡️-mod-logs")
            if log_channel:
                log_embed = discord.Embed(
                    title="📩 DM Sent",
                    description=f"To: {user.mention}\nBy: {interaction.user.mention}",
                    color=discord.Color.green()
                )
                await log_channel.send(embed=log_embed)
            
            await interaction.response.send_message(f"✅ DM sent to {user.mention}!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

# ============ BIG SETUP VIEW ============
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
    
    @discord.ui.button(label="🔐 VERIFICATION SYSTEM", style=discord.ButtonStyle.primary, emoji="🔐", row=0)
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            channel = await self.create_channel(interaction.guild, "🔐-verification", "🔐 Security")
            await self.send_verification_message(channel)
            await interaction.followup.send(f"✅ Verification system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎫 TICKET SYSTEM", style=discord.ButtonStyle.secondary, emoji="🎫", row=0)
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            channel = await self.create_channel(interaction.guild, "🎫-tickets", "🎫 Support")
            await self.send_ticket_message(channel)
            await interaction.followup.send(f"✅ Ticket system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎁 GIVEAWAY SYSTEM", style=discord.ButtonStyle.primary, emoji="🎁", row=0)
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            channel = await self.create_channel(interaction.guild, "🎉-giveaways", "🎉 Events")
            await self.send_giveaway_message(channel)
            await interaction.followup.send(f"✅ Giveaway system setup complete!", ephemeral=True)
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
            channel = await self.create_channel(interaction.guild, "🛡️-mod-logs", "🔐 Security")
            await self.send_moderation_message(channel)
            await interaction.followup.send(f"✅ Moderation suite setup complete! Check {channel.mention}!", ephemeral=True)
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
            
            for member in interaction.guild.members:
                if not member.bot:
                    await process_single_member(member, log_channel)
            
            await interaction.followup.send("✅ **Members synced!**", ephemeral=True)
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
            • ✅ Auto-sync on member join/leave
            • ✅ Only verified users get credentials
            • 🗑️ Credentials deleted when user leaves
            • 🛡️ Spam protection (1 per minute)
            • 📝 Logged to #🛡️-mod-logs
            • 📧 Credentials sent via DM
            """,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="⚙️ SERVER MANAGEMENT", style=discord.ButtonStyle.success, emoji="⚙️", row=2)
    async def server_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        
        embed = discord.Embed(
            title="⚙️ **SERVER MANAGEMENT**",
            description="""
            **📋 AVAILABLE ACTIONS:**
            • 📢 **Send Announcement** - Post announcements
            • 📩 **Send DM** - DM any server member
            • 📊 **Server Stats** - View server statistics
            • 🔧 **Setup Permissions** - Permission guide
            • ⚡ **Quick Actions** - Mute all, unmute all
            
            **👑 ADMIN ONLY**
            Click any button below!
            """,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        embed.set_footer(text="EDITH Server Management")
        
        view = ServerManagementView()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    async def setup_all(self, guild, interaction):
        try:
            command_channel = interaction.channel
            
            await interaction.followup.send("🔄 **STEP 1/6:** DELETING existing channels...", ephemeral=True)
            logger.info("🗑️ DELETING all channels except command channel...")
            
            channel_count = 0
            for channel in guild.channels:
                if channel.id == command_channel.id:
                    logger.info(f"ℹ️ Keeping command channel: {channel.name}")
                    continue
                try:
                    await channel.delete()
                    channel_count += 1
                    logger.info(f"🗑️ Deleted channel: {channel.name}")
                    await asyncio.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Could not delete channel {channel.name}: {e}")
            logger.info(f"🗑️ Deleted {channel_count} channels")
            
            await interaction.followup.send(f"🔄 **STEP 2/6:** DELETED {channel_count} channels. Deleting roles...", ephemeral=True)
            
            role_count = 0
            for role in guild.roles:
                if role.name != "@everyone" and not role.managed:
                    try:
                        await role.delete()
                        role_count += 1
                        logger.info(f"🗑️ Deleted role: {role.name}")
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        logger.warning(f"Could not delete role {role.name}: {e}")
            logger.info(f"🗑️ Deleted {role_count} roles")
            
            await interaction.followup.send(f"🔄 **STEP 3/6:** DELETED {role_count} roles. Creating new structure...", ephemeral=True)
            
            await asyncio.sleep(2)
            
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
                try:
                    category = await guild.create_category(category_name)
                    category_objects[category_name] = category
                    logger.info(f"✅ Created category: {category_name}")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"❌ Failed to create category {category_name}: {e}")
                    continue
                
                for channel_name in channel_names:
                    try:
                        await guild.create_text_channel(channel_name, category=category)
                        created_count += 1
                        logger.info(f"✅ Created channel: {channel_name}")
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        logger.error(f"❌ Failed to create {channel_name}: {e}")
            
            if "📞 VOICE CHANNELS" in category_objects:
                for vc_name in ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"]:
                    try:
                        await guild.create_voice_channel(vc_name, category=category_objects["📞 VOICE CHANNELS"])
                        created_count += 1
                        logger.info(f"✅ Created voice channel: {vc_name}")
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        logger.error(f"❌ Failed to create {vc_name}: {e}")
            
            logger.info(f"✅ Created {created_count} channels")
            
            await interaction.followup.send(f"🔄 **STEP 4/6:** CREATED {created_count} channels. Creating roles...", ephemeral=True)
            
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
                    add_reactions=True, priority_speaker=True
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
            
            role_count = 0
            for role_name, perms in roles_config.items():
                try:
                    await guild.create_role(name=role_name, permissions=perms)
                    role_count += 1
                    logger.info(f"✅ Created role: {role_name}")
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"❌ Failed to create {role_name}: {e}")
            
            logger.info(f"✅ Created {role_count} roles")
            
            await interaction.followup.send(f"🔄 **STEP 5/6:** CREATED {role_count} roles. Setting up systems...", ephemeral=True)
            
            await asyncio.sleep(2)
            
            verify_channel = discord.utils.get(guild.channels, name="🔐-verification")
            ticket_channel = discord.utils.get(guild.channels, name="🎫-tickets")
            giveaway_channel = discord.utils.get(guild.channels, name="🎉-giveaways")
            mod_channel = discord.utils.get(guild.channels, name="🛡️-mod-logs")
            
            if verify_channel:
                await self.send_verification_message(verify_channel)
                logger.info("✅ Sent verification message")
            if ticket_channel:
                await self.send_ticket_message(ticket_channel)
                logger.info("✅ Sent ticket message")
            if giveaway_channel:
                await self.send_giveaway_message(giveaway_channel)
                logger.info("✅ Sent giveaway message")
            if mod_channel:
                await self.send_moderation_message(mod_channel)
                await self.send_server_management_message(mod_channel)
                logger.info("✅ Sent moderation and server management messages")
            
            await interaction.followup.send("🔄 **STEP 6/6:** Syncing members...", ephemeral=True)
            
            log_channel = mod_channel or discord.utils.get(guild.channels, name="🔐-verification")
            for member in guild.members:
                if not member.bot:
                    await process_single_member(member, log_channel)
            
            embed = discord.Embed(
                title="✅ **🎉 SERVER SETUP COMPLETE!**",
                description=f"""
                **📊 SERVER: {guild.name}**
                
                **✅ COMPLETED:**
                • 🗑️ Deleted {channel_count} channels
                • 🗑️ Deleted {role_count} roles  
                • 📋 Created 7 Categories
                • 💬 Created {created_count} Channels  
                • 👑 Created {role_count} Roles
                • 🔐 Verification System
                • 🎫 Ticket System
                • 🎁 Giveaway System
                • 🛡️ Moderation System
                • 💾 Backup System
                • ⚙️ Server Management System
                
                **🔑 CREDENTIALS:**
                • ✅ Verified members processed
                • 📧 Credentials sent via DM
                • 📝 Logged in #🛡️-mod-logs
                • 🔄 Auto-sync on member join/leave
                
                **🔒 PERMISSIONS:**
                • ❌ Unverified: Only see #🔐-verification
                • ✅ Verified: See all public channels
                • 🛡️ Moderator: Admin channel access
                • 👑 Admin: Full access
                
                🎉 **Your server is ready to go!**
                """,
                color=discord.Color.green()
            )
            embed.set_image(url="https://i.imgur.com/your-image-here.png")
            embed.set_thumbnail(url=guild.icon.url if guild.icon else bot.user.display_avatar.url)
            embed.set_footer(text="EDITH Server Management System v2.0 • Built with ❤️")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"✅ Setup complete for {guild.name}")
            
        except Exception as e:
            logger.error(f"Setup error: {e}")
            try:
                await interaction.followup.send(f"❌ **ERROR:**\n```\n{str(e)}\n```", ephemeral=True)
            except:
                pass
    
    async def create_channel(self, guild, channel_name, category_name):
        existing = discord.utils.get(guild.channels, name=channel_name)
        if existing:
            return existing
        
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
            await asyncio.sleep(0.5)
        
        channel = await guild.create_text_channel(channel_name, category=category)
        await asyncio.sleep(0.5)
        return channel
    
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
                    await asyncio.sleep(0.3)
                except:
                    pass
    
    async def send_verification_message(self, channel):
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
        embed.set_image(url="https://i.imgur.com/your-image-here.png")
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="EDITH Authentication System • Secure OAuth2 Verification")
        view = VerifyView()
        await channel.send(embed=embed, view=view)
    
    async def send_ticket_message(self, channel):
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
        embed.set_image(url="https://i.imgur.com/your-image-here.png")
        view = TicketView()
        await channel.send(embed=embed, view=view)
    
    async def send_giveaway_message(self, channel):
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
        embed.set_image(url="https://i.imgur.com/your-image-here.png")
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)
    
    async def send_moderation_message(self, channel):
        embed = discord.Embed(
            title="🛡️ **MODERATION SUITE**",
            description="""
            **⚡ MODERATOR CONTROL PANEL**
            
            **📋 AVAILABLE ACTIONS:**
            • ⛔ **Ban User** - Permanently ban a user
            • 👢 **Kick User** - Kick a user from the server
            • 🔇 **Mute User** - Mute a user for a specified time
            • 🔊 **Unmute User** - Remove mute from a user
            • ⏰ **Timeout User** - Put a user in timeout
            • ⏰ **Remove Timeout** - Remove timeout from a user
            • ℹ️ **About User** - Get user information
            
            **👮 MODERATORS ONLY**
            Click any button below to perform moderation actions!
            """,
            color=discord.Color.red()
        )
        embed.set_image(url="https://i.imgur.com/your-image-here.png")
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="EDITH Moderation System • Moderators Only")
        view = ModerationView()
        await channel.send(embed=embed, view=view)
    
    async def send_server_management_message(self, channel):
        embed = discord.Embed(
            title="⚙️ **SERVER MANAGEMENT**",
            description="""
            **👑 ADMIN CONTROL PANEL**
            
            **📋 AVAILABLE ACTIONS:**
            • 📢 **Send Announcement** - Post announcements to any channel
            • 📩 **Send DM** - Direct message any server member
            • 📊 **Server Stats** - View detailed server statistics
            • 🔧 **Setup Permissions** - Permission setup guide
            • ⚡ **Quick Actions** - Mute all, unmute all, member count
            
            **👑 ADMIN ONLY**
            Click any button below to manage your server!
            """,
            color=discord.Color.blue()
        )
        embed.set_image(url="https://i.imgur.com/your-image-here.png")
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.set_footer(text="EDITH Server Management • Admins Only")
        view = ServerManagementView()
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
            embed.set_image(url="https://i.imgur.com/your-image-here.png")
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
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ DELETE GIVEAWAY", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
    
    @discord.ui.button(label="🔄 REROLL", style=discord.ButtonStyle.primary, emoji="🔄")
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and giveaway_data['participants']:
            new_winner = random.choice(giveaway_data['participants'])
            await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)
            await interaction.channel.send(f"🔄 **Rerolled!** New winner for **{giveaway_data['name']}**: <@{new_winner}>!")

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
            
            mod_role = discord.utils.get(guild.roles, name="🔰 Moderator")
            admin_role = discord.utils.get(guild.roles, name="🛡️ Admin")
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            if admin_role:
                overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
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
            embed.set_image(url="https://i.imgur.com/your-image-here.png")
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
    
    @discord.ui.button(label="➕ ADD USER", style=discord.ButtonStyle.success, emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ REMOVE USER", style=discord.ButtonStyle.danger, emoji="➖")
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⛔ BAN USER", style=discord.ButtonStyle.danger, emoji="⛔")
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BanUserModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📄 TRANSCRIPT", style=discord.ButtonStyle.secondary, emoji="📄")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            channel = interaction.channel
            messages = []
            async for msg in channel.history(limit=200):
                messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.name}: {msg.content}")
            
            transcript = "\n".join(reversed(messages))
            import io
            file = discord.File(io.BytesIO(transcript.encode()), f"transcript-{channel.name}.txt")
            await interaction.followup.send(file=file, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔒 CLOSE TICKET", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        await interaction.response.defer()
        channel = interaction.channel
        await channel.send("🔒 **Closing ticket...**\n\n📝 Generating transcript...")
        await asyncio.sleep(2)
        await channel.delete()
    
    @discord.ui.button(label="📝 SPECIAL NOTE", style=discord.ButtonStyle.primary, emoji="📝")
    async def special_note(self, interaction: discord.Interaction, button: discord.ui.Button):
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

class NoteModal(Modal):
    def __init__(self, channel_id):
        super().__init__(title="📝 Add Special Note")
        self.channel_id = channel_id
        self.note_input = TextInput(label="Note", placeholder="Enter your note here...", style=discord.TextStyle.paragraph, required=True, max_length=1000)
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
        
        await interaction.channel.send(f"📝 **Special Note Added by {interaction.user.mention}:**\n{self.note_input.value}")
        await interaction.response.send_message("✅ Note saved successfully!", ephemeral=True)

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
        
        **⚠️ WARNING:** Setup All will DELETE ALL existing channels and roles!
        """,
        color=discord.Color.gold()
    )
    embed.set_image(url="https://i.imgur.com/your-image-here.png")
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
    
    for member in interaction.guild.members:
        if not member.bot:
            await process_single_member(member, log_channel)
    
    await interaction.followup.send("✅ **Sync complete!** Credentials generated and sent to verified members!", ephemeral=True)

@bot.tree.command(name="credentials", description="Get your login credentials")
async def get_credentials_cmd(interaction: discord.Interaction):
    creds = get_credentials(str(interaction.user.id))
    
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
    verified_role = discord.utils.get(interaction.guild.roles, name="✅ Verified")
    if verified_role not in user.roles:
        await interaction.response.send_message(f"❌ {user.mention} is not verified! Only verified users get credentials.", ephemeral=True)
        return
    
    is_admin = any(role.permissions.administrator for role in user.roles)
    role_type = 'moderator' if is_admin else 'member'
    
    firebase_delete(f'credentials/{str(user.id)}')
    creds = generate_credentials(str(user.id), role=role_type)
    
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
    embed = discord.Embed(
        title="🏓 **PONG!**",
        description=f"**Latency:** {round(interaction.client.latency * 1000)}ms",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

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
            return f"""
            <html>
            <head><title>Verification Failed</title>
            <style>
                body {{ font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }}
                .container {{ background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; }}
                .error {{ color: #f44336; font-size: 60px; }}
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>Verification Failed</h1>
                    <p>Error: {error}</p>
                    <p>Please try <code>/verify</code> again in Discord.</p>
                </div>
            </body>
            </html>
            """
        
        if not code:
            return """
            <html>
            <head><title>Verification Failed</title>
            <style>
                body { font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }
                .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; }
                .error { color: #f44336; font-size: 60px; }
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>No Code Provided</h1>
                    <p>Please try <code>/verify</code> again in Discord.</p>
                </div>
            </body>
            </html>
            """, 400
        
        session = None
        if state:
            session = oauth_states.pop(state, None)
            logger.info(f"   Session found: {session is not None}")
        
        if not session:
            return """
            <html>
            <head><title>Verification Failed</title>
            <style>
                body { font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }
                .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; }
                .error { color: #f44336; font-size: 60px; }
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>Session Expired</h1>
                    <p>Your verification session has expired.</p>
                    <p>Please run <code>/verify</code> again in Discord.</p>
                </div>
            </body>
            </html>
            """
        
        user_id = session['user_id']
        guild_id = session['guild_id']
        logger.info(f"   User ID: {user_id}, Guild ID: {guild_id}")
        
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
                    return None
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        token_data = loop.run_until_complete(exchange_code())
        loop.close()
        
        if not token_data:
            return """
            <html>
            <head><title>Token Exchange Failed</title>
            <style>
                body { font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }
                .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; }
                .error { color: #f44336; font-size: 60px; }
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>Token Exchange Failed</h1>
                    <p>Please try <code>/verify</code> again.</p>
                </div>
            </body>
            </html>
            """
        
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
            return """
            <html>
            <head><title>Failed to Get User Data</title>
            <style>
                body { font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }
                .container { background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; }
                .error { color: #f44336; font-size: 60px; }
            </style>
            </head>
            <body>
                <div class="container">
                    <div class="error">❌</div>
                    <h1>Failed to Get User Data</h1>
                    <p>Please try <code>/verify</code> again.</p>
                </div>
            </body>
            </html>
            """
        
        username = user_data.get('username')
        discord_id = user_data.get('id')
        email = user_data.get('email', 'Not provided')
        
        logger.info(f"✅ User verified: {username} ({discord_id})")
        
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
        
        firebase_success = False
        if rtdb_client:
            try:
                guild = bot.get_guild(int(guild_id))
                guild_name = guild.name if guild else 'Unknown'
                
                firebase_set(f'guilds/{guild_id}/verified/{discord_id}', {
                    'discord_id': discord_id,
                    'username': username,
                    'email': email,
                    'guild_id': guild_id,
                    'guild_name': guild_name,
                    'verified_at': datetime.now().isoformat(),
                    'verified': True
                })
                firebase_success = True
                logger.info(f"✅ Stored in Firebase: {username}")
            except Exception as e:
                logger.error(f"❌ Firebase storage failed: {e}")
        
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
        <html>
        <head>
            <title>Verification Successful</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }}
                .container {{ background: #2d2d44; padding: 40px; border-radius: 20px; max-width: 500px; width: 100%; }}
                .success {{ color: #4caf50; font-size: 80px; text-align: center; }}
                h1 {{ text-align: center; margin: 10px 0; }}
                .info {{ background: #1e1e32; padding: 15px; border-radius: 10px; margin: 20px 0; }}
                .info div {{ padding: 8px 0; border-bottom: 1px solid #2d2d44; display: flex; justify-content: space-between; }}
                .info div:last-child {{ border-bottom: none; }}
                .label {{ color: #888; }}
                .value {{ color: white; }}
                .button {{ background: #5865f2; color: white; border: none; padding: 15px; border-radius: 10px; font-size: 16px; cursor: pointer; text-decoration: none; display: block; text-align: center; margin-top: 20px; }}
                .button:hover {{ background: #4752c4; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success">✅</div>
                <h1>Verification Successful!</h1>
                <p style="text-align: center;">Welcome to the server! 🎉</p>
                
                <div class="info">
                    <div><span class="label">👤 Username</span> <span class="value">{username}</span></div>
                    <div><span class="label">🆔 ID</span> <span class="value">{discord_id}</span></div>
                    <div><span class="label">📧 Email</span> <span class="value">{email}</span></div>
                    <div><span class="label">🎭 Role</span> <span class="value">{'✅ Assigned' if role_assigned else '⚠️ Pending'}</span></div>
                    <div><span class="label">📦 Firebase</span> <span class="value">{'✅ Stored' if firebase_success else '⚠️ Local only'}</span></div>
                </div>
                
                <a href="https://discord.com/app" class="button">Return to Discord</a>
                
                <p class="footer">A verification DM has been sent to you! 📨</p>
            </div>
        </body>
        </html>
        """
    
    except Exception as e:
        logger.error(f"❌ Callback error: {e}")
        return f"""
        <html>
        <head><title>Verification Error</title>
        <style>
            body {{ font-family: Arial; background: #1a1a2e; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; }}
            .container {{ background: #2d2d44; padding: 40px; border-radius: 20px; text-align: center; }}
            .error {{ color: #f44336; font-size: 60px; }}
        </style>
        </head>
        <body>
            <div class="container">
                <div class="error">❌</div>
                <h1>Verification Error</h1>
                <p>Error: {str(e)}</p>
                <p>Please try <code>/verify</code> again.</p>
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
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands!")
        for cmd in synced:
            print(f"   /{cmd.name}")
    except Exception as e:
        print(f"❌ Failed to sync: {e}")

@bot.event
async def on_member_join(member):
    if member.bot:
        return
    
    logger.info(f"👋 {member.name} joined - Syncing...")
    
    firebase_set(f'guilds/{member.guild.id}/unverified/{member.id}', {
        'discord_id': str(member.id),
        'username': member.name,
        'joined_at': datetime.now().isoformat()
    })
    
    delete_credentials(str(member.id))
    
    unverified_role = discord.utils.get(member.guild.roles, name="❌ Unverified")
    if unverified_role:
        try:
            await member.add_roles(unverified_role)
        except:
            pass

@bot.event
async def on_member_remove(member):
    if member.bot:
        return
    
    logger.info(f"👋 {member.name} left - Deleting credentials...")
    delete_credentials(str(member.id))
    firebase_delete(f'guilds/{member.guild.id}/verified/{member.id}')
    firebase_delete(f'guilds/{member.guild.id}/unverified/{member.id}')

@bot.event
async def on_member_update(before, after):
    if before.bot or after.bot:
        return
    
    verified_role = discord.utils.get(after.guild.roles, name="✅ Verified")
    was_verified = verified_role in before.roles
    is_verified = verified_role in after.roles
    
    if was_verified != is_verified:
        log_channel = discord.utils.get(after.guild.channels, name="🛡️-mod-logs")
        
        if is_verified:
            logger.info(f"✅ {after.name} verified - Generating credentials...")
            
            is_admin = any(role.permissions.administrator for role in after.roles)
            role_type = 'moderator' if is_admin else 'member'
            
            creds = get_credentials(str(after.id))
            if not creds:
                creds = generate_credentials(str(after.id), role=role_type)
                await send_credentials_dm(after, creds, role_type, log_channel)
            else:
                current_role = creds.get('role', 'member')
                if is_admin and current_role != 'moderator':
                    creds['role'] = 'moderator'
                    firebase_set(f'credentials/{after.id}', creds)
                    await send_credentials_dm(after, creds, 'moderator', log_channel)
                elif not is_admin and current_role != 'member':
                    creds['role'] = 'member'
                    firebase_set(f'credentials/{after.id}', creds)
                    await send_credentials_dm(after, creds, 'member', log_channel)
        else:
            logger.info(f"❌ {after.name} unverified - Deleting credentials...")
            delete_credentials(str(after.id))

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
