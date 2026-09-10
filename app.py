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
from aiohttp import web
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import string
import time
from urllib.parse import urlencode

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


# ============ DATABASE (FIREBASE-BACKED) ============
class Database:
    """Persistent application database. Firebase is the source of truth.

    A tiny in-memory copy is kept only as a runtime cache so existing code can
    continue using db.data without changing the whole bot. Persistent writes
    are mirrored to Firebase under application_data.
    """
    DEFAULTS = {'users': {}, 'guilds': {}, 'giveaways': {}, 'tickets': {}, 'notes': {}, 'oauth_states': {}}

    def __init__(self):
        self.data = {}
        self.load_data()

    def load_data(self):
        firebase_data = firebase_get('application_data')
        if isinstance(firebase_data, dict):
            self.data = firebase_data
            for key, value in self.DEFAULTS.items():
                self.data.setdefault(key, value.copy() if isinstance(value, dict) else value)
            logger.info('☁️ Application database loaded from Firebase')
            return

        # One-time migration for any old Railway local db.json.
        try:
            if os.path.exists('./data/db.json'):
                with open('./data/db.json', 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                logger.info('📦 Migrating existing local database to Firebase...')
            else:
                self.data = json.loads(json.dumps(self.DEFAULTS))
        except Exception:
            self.data = json.loads(json.dumps(self.DEFAULTS))

        self.save_data()

    def save_data(self):
        # Firebase is the persistent source of truth. No application data is
        # required to survive on Railway's ephemeral filesystem.
        if rtdb_client:
            try:
                rtdb_client.child('application_data').set(self.data)
                logger.debug('☁️ Application database saved to Firebase')
                return True
            except Exception as e:
                logger.error(f'❌ Firebase database save failed: {e}')
                return False
        logger.error('❌ Firebase unavailable: application data was NOT persisted')
        return False

    def get_user(self, user_id, guild_id):
        user_id = str(user_id)
        guild_id = str(guild_id)
        if guild_id not in self.data['users']:
            self.data['users'][guild_id] = {}
        if user_id not in self.data['users'][guild_id]:
            self.data['users'][guild_id][user_id] = {
                'verified': False, 'profile': {}, 'tickets': [], 'notes': [],
                'guild_id': guild_id, 'user_id': user_id, 'verified_at': None
            }
            self.save_data()
        return self.data['users'][guild_id][user_id]

    def set_user(self, user_id, guild_id, data):
        user_id = str(user_id); guild_id = str(guild_id)
        self.data.setdefault('users', {}).setdefault(guild_id, {})[user_id] = data
        self.save_data()

    def get_guild(self, guild_id):
        return self.data.get('guilds', {}).get(str(guild_id))

    def set_guild(self, guild_id, data):
        self.data.setdefault('guilds', {})[str(guild_id)] = data
        self.save_data()

db = Database()

def generate_credentials(user_id, username=None, role='member'):
    user_id = str(user_id)
    existing = firebase_get(f'credentials/{user_id}')
    if existing:
        # Repair the reverse index for legacy records.
        if existing.get('username'):
            firebase_set(f"credentials_by_username/{existing['username']}", {'user_id': user_id, 'updated_at': datetime.now().isoformat()})
        return existing

    # Always generate a unique username, even if Firebase has stale/duplicate data.
    for _ in range(12):
        candidate = username or f"user_{user_id[:8]}_{secrets.token_hex(4)}"
        if not firebase_get(f'credentials_by_username/{candidate}'):
            username = candidate
            break
        username = f"user_{user_id[:8]}_{secrets.token_hex(6)}"

    alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
    password = ''.join(secrets.choice(alphabet) for _ in range(20))
    now = datetime.now().isoformat()
    creds = {
        'username': username, 'password': password, 'role': role, 'user_id': user_id,
        'created_at': now, 'updated_at': now, 'credential_version': 2
    }
    firebase_set(f'credentials/{user_id}', creds)
    firebase_set(f'credentials_by_username/{username}', {'user_id': user_id, 'created_at': now})
    return creds

def get_credentials(user_id):
    return firebase_get(f'credentials/{user_id}')

def delete_credentials(user_id):
    old = firebase_get(f'credentials/{user_id}')
    firebase_delete(f'credentials/{user_id}')
    if old and old.get('username'):
        firebase_delete(f"credentials_by_username/{old['username']}")
    logger.info(f"🗑️ Deleted credentials for {user_id}")

def update_web_stats():
    """Write only the two public counters used by the Vercel landing page."""
    try:
        total_servers = len(bot.guilds)
        # Discord's cached guild member_count is cheap to read. This intentionally
        # counts total memberships (not deduplicated global users), which is the
        # standard public bot metric and avoids an expensive full-member scan.
        total_users = sum(int(g.member_count or 0) for g in bot.guilds)
        firebase_set('for_web', {
            'total_user': total_users,
            'total_server': total_servers,
            'updated_at': datetime.now().isoformat()
        })
    except Exception as exc:
        logger.warning(f'Could not update for_web stats: {exc}')

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
    embed.add_field(name="🌐 LOGIN URL", value=f"[Click Here]({os.getenv('WEBSITE_URL', 'https://edith-bot-api.vercel.app')})", inline=False)
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
            # Credentials belong to the Discord account, not one guild. Never delete them merely
            # because the same user is unverified in a different server.
            verified_elsewhere = any(
                g.id != guild.id and (g.get_member(member.id) and (discord.utils.get(g.roles, name='✅ Verified') in g.get_member(member.id).roles if discord.utils.get(g.roles, name='✅ Verified') else False))
                for g in bot.guilds
            )
            if not verified_elsewhere:
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

        # Keep a reverse index so the website can find every server the user shares with EDITH.
        firebase_set(f'user_guilds/{user_id}/{guild.id}', {
            'guild_id': str(guild.id),
            'guild_name': guild.name,
            'guild_icon': guild.icon.url if guild.icon else None,
            'is_owner': guild.owner_id == member.id,
            'is_admin': member.guild_permissions.administrator,
            'permissions': member.guild_permissions.value,
            'updated_at': datetime.now().isoformat()
        })
        firebase_set(f'profiles/{user_id}', {
            'discord_id': user_id, 'username': member.name,
            'global_name': member.display_name or member.name,
            'avatar': member.display_avatar.url,
            'updated_at': datetime.now().isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"Failed to process member {member.name}: {e}")
        return False

# ============ BIG MODERATION SUITE VIEW ============
class ModerationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="⛔ BAN USER", style=discord.ButtonStyle.danger, emoji="⛔", row=0, custom_id="edith:moderation:ban")
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You don't have permission to ban members!", ephemeral=True)
            return
        await interaction.response.send_modal(BanUserModal())
    
    @discord.ui.button(label="👢 KICK USER", style=discord.ButtonStyle.danger, emoji="👢", row=0, custom_id="edith:moderation:kick")
    async def kick_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ You don't have permission to kick members!", ephemeral=True)
            return
        await interaction.response.send_modal(KickUserModal())
    
    @discord.ui.button(label="🔇 MUTE USER", style=discord.ButtonStyle.primary, emoji="🔇", row=0, custom_id="edith:moderation:mute")
    async def mute_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.mute_members:
            await interaction.response.send_message("❌ You don't have permission to mute members!", ephemeral=True)
            return
        await interaction.response.send_modal(MuteUserModal())
    
    @discord.ui.button(label="🔊 UNMUTE USER", style=discord.ButtonStyle.success, emoji="🔊", row=1, custom_id="edith:moderation:unmute")
    async def unmute_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.mute_members:
            await interaction.response.send_message("❌ You don't have permission to unmute members!", ephemeral=True)
            return
        await interaction.response.send_modal(UnmuteUserModal())
    
    @discord.ui.button(label="⏰ TIMEOUT USER", style=discord.ButtonStyle.secondary, emoji="⏰", row=1, custom_id="edith:moderation:timeout")
    async def timeout_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to timeout members!", ephemeral=True)
            return
        await interaction.response.send_modal(TimeoutUserModal())
    
    @discord.ui.button(label="⏰ REMOVE TIMEOUT", style=discord.ButtonStyle.secondary, emoji="⏰", row=1, custom_id="edith:moderation:untimeout")
    async def remove_timeout(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to remove timeouts!", ephemeral=True)
            return
        await interaction.response.send_modal(RemoveTimeoutModal())
    
    @discord.ui.button(label="ℹ️ ABOUT USER", style=discord.ButtonStyle.secondary, emoji="ℹ️", row=2, custom_id="edith:moderation:about")
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
        if not interaction.user.guild_permissions.ban_members and not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ You don't have permission to ban members!", ephemeral=True)
            return
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
        if not interaction.user.guild_permissions.kick_members and not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ You don't have permission to kick members!", ephemeral=True)
            return
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
    
    @discord.ui.button(label="📢 SEND ANNOUNCEMENT", style=discord.ButtonStyle.primary, emoji="📢", row=0, custom_id="edith:server:announcement")
    async def send_announcement(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(AnnouncementModal())
    
    @discord.ui.button(label="📩 SEND DM TO USER", style=discord.ButtonStyle.success, emoji="📩", row=0, custom_id="edith:server:dm")
    async def send_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(DMUserModal())
    
    @discord.ui.button(label="📊 SERVER STATS", style=discord.ButtonStyle.secondary, emoji="📊", row=0, custom_id="edith:server:stats")
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
    
    @discord.ui.button(label="🔧 SETUP PERMISSIONS", style=discord.ButtonStyle.secondary, emoji="🔧", row=1, custom_id="edith:server:permissions")
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
    
    @discord.ui.button(label="⚡ QUICK ACTIONS", style=discord.ButtonStyle.success, emoji="⚡", row=1, custom_id="edith:server:quick_actions")
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
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔇 Mute All", style=discord.ButtonStyle.danger, emoji="🔇", custom_id="edith:quick:muteall")
    async def mute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only admins can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(MuteAllModal())
    
    @discord.ui.button(label="🔊 Unmute All", style=discord.ButtonStyle.success, emoji="🔊", custom_id="edith:quick:unmuteall")
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
    
    @discord.ui.button(label="📊 Member Count", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="edith:quick:members")
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
        await interaction.response.send_modal(VerificationSetupModal())
    
    @discord.ui.button(label="🎫 TICKET SYSTEM", style=discord.ButtonStyle.secondary, emoji="🎫", row=0)
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(TicketSetupModal())
    
    @discord.ui.button(label="🎁 GIVEAWAY SYSTEM", style=discord.ButtonStyle.primary, emoji="🎁", row=0)
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(GiveawaySetupModal())
    
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
        await interaction.response.send_modal(ModerationSetupModal())
    
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

# ============ SETUP MODALS (Ask for Channel ID) ============
class VerificationSetupModal(Modal):
    def __init__(self):
        super().__init__(title="🔐 Verification System Setup")
        self.channel_input = TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID for verification",
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_input.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found! Please enter a valid channel ID.", ephemeral=True)
                return
            
            # Create Verified role if it doesn't exist
            verified_role = discord.utils.get(interaction.guild.roles, name="✅ Verified")
            if not verified_role:
                verified_role = await interaction.guild.create_role(
                    name="✅ Verified",
                    color=discord.Color.green(),
                    permissions=discord.Permissions(
                        read_messages=True, send_messages=True, connect=True, speak=True,
                        read_message_history=True, attach_files=True, embed_links=True, add_reactions=True
                    )
                )
            
            embed = discord.Embed(
                title="🔐 **VERIFICATION REQUIRED**",
                description="""
                **🔒 WHY VERIFY?**
                • 🛡️ **SECURITY** - Protect your account
                • 🎮 **ACCESS** - Unlock full server features
                • 👤 **IDENTITY** - Verify your Discord identity
                
                **✅ HOW TO VERIFY:**
                1. Click the **VERIFY VIA DISCORD** button below
                2. Authorize through Discord OAuth
                3. Get the ✅ Verified role
                4. Receive your login credentials
                """,
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            view = VerifyView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Verification system setup complete in {channel.mention}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid channel ID! Please enter a valid number.", ephemeral=True)

class TicketSetupModal(Modal):
    def __init__(self):
        super().__init__(title="🎫 Ticket System Setup")
        self.channel_input = TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID for tickets",
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_input.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎫 **TICKET SYSTEM**",
                description="Click a button below to create a ticket!",
                color=discord.Color.purple()
            )
            view = TicketView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Ticket system setup complete in {channel.mention}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid channel ID!", ephemeral=True)

class GiveawaySetupModal(Modal):
    def __init__(self):
        super().__init__(title="🎁 Giveaway System Setup")
        self.channel_input = TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID for giveaways",
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_input.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎉 **GIVEAWAY CENTER**",
                description="👑 Admin only: Host exciting giveaways!",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=bot.user.display_avatar.url)
            view = GiveawayMainView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Giveaway system setup complete in {channel.mention}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid channel ID!", ephemeral=True)

class ModerationSetupModal(Modal):
    def __init__(self):
        super().__init__(title="🛡️ Moderation Suite Setup")
        self.channel_input = TextInput(
            label="Channel ID",
            placeholder="Enter the channel ID for moderation logs",
            required=True
        )
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_input.value)
            channel = interaction.guild.get_channel(channel_id)
            
            if not channel:
                await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🛡️ **MODERATION SUITE**",
                description="""
                **⚡ MODERATOR CONTROL PANEL**
                
                **📋 AVAILABLE ACTIONS:**
                • ⛔ **Ban User** - Permanently ban
                • 👢 **Kick User** - Kick from server
                • 🔇 **Mute User** - Mute for duration
                • 🔊 **Unmute User** - Remove mute
                • ⏰ **Timeout User** - Timeout for duration
                • ⏰ **Remove Timeout** - Remove timeout
                • ℹ️ **About User** - Full user info
                
                **👮 MODERATORS ONLY**
                Click any button below!
                """,
                color=discord.Color.red()
            )
            view = ModerationView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Moderation suite setup complete in {channel.mention}!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid channel ID!", ephemeral=True)

# ============ OAUTH ============
class OAuthVerification:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = (os.getenv('REDIRECT_URI') or (os.getenv('WEBSITE_URL','').rstrip('/') + '/callback')).rstrip('/')
        logger.info(f"🔐 OAuth initialized")
        logger.info(f"   Redirect URI: {self.redirect_uri}")
    
    def generate_oauth_url(self, user_id, guild_id):
        state = secrets.token_urlsafe(32)
        if rtdb_client:
            try:
                rtdb_client.child(f'oauth_states/{state}').set({
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Failed to store in Firebase: {e}")
        
        url = "https://discord.com/api/oauth2/authorize?" + urlencode({
            'client_id': self.client_id or '',
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'identify email guilds',
            'state': state,
            'prompt': 'consent'
        })
        return url, state

oauth = OAuthVerification()

# ============ VERIFY VIEW ============
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔐 VERIFY VIA DISCORD", style=discord.ButtonStyle.success, emoji="🔐", custom_id="edith:verify")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        verified_data = firebase_get(f'guilds/{guild_id}/verified/{user_id}')
        if verified_data:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return

        # Preflight the role: if the server does not have a Verified role,
        # create it now. The role is still only assigned after OAuth succeeds.
        try:
            role = await ensure_verified_role(interaction.guild)
            if interaction.guild.me is None or role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    "❌ I cannot manage the ✅ Verified role. Move my bot role above it and try again.",
                    ephemeral=True
                )
                return
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I need Manage Roles permission to create/use the ✅ Verified role.",
                ephemeral=True
            )
            return

        url, state = oauth.generate_oauth_url(user_id, guild_id)
        
        view = View()
        link_button = Button(
            label="🔐 Click to Verify",
            style=discord.ButtonStyle.link,
            url=url,
            emoji="🔐"
        )
        view.add_item(link_button)
        
        embed = discord.Embed(
            title="🔐 **AUTHORIZE VERIFICATION**",
            description=f"""
            **Click the button below to verify your identity:**
            
            ⏰ **TIME LIMIT:** 10 minutes
            🔒 **SECURITY:** Your data is encrypted and secure
            
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
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ============ GIVEAWAY SYSTEM ============
class GiveawayMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎁 HOST GIVEAWAY", style=discord.ButtonStyle.success, emoji="🎁", custom_id="edith:giveaway:host")
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
            message = await interaction.original_response()
            
            db.data['giveaways'][giveaway_id] = {
                'name': self.name.value,
                'prize': self.prize.value,
                'host': interaction.user.id,
                'winners': winners_count,
                'end_time': end_time.isoformat(),
                'participants': [],
                'guild_id': str(interaction.guild.id),
                'channel_id': str(interaction.channel.id),
                'message_id': str(message.id),
                'status': 'active',
                'created_at': datetime.now().isoformat()
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
        self.giveaway_id = str(giveaway_id)
        self.end_time = end_time
        self.host_id = int(host_id)
        # Persistent buttons need stable, message-specific custom IDs.
        for child in self.children:
            suffix = getattr(child, "custom_id", "").split(":")[-1]
            child.custom_id = f"edith:giveaway:{self.giveaway_id}:{suffix}"
    
    @discord.ui.button(label="🎯 PARTICIPATE", style=discord.ButtonStyle.success, emoji="🎯", custom_id="participate")
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
    
    @discord.ui.button(label="❌ UN-PARTICIPATE", style=discord.ButtonStyle.danger, emoji="❌", custom_id="unparticipate")
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and interaction.user.id in giveaway_data['participants']:
            giveaway_data['participants'].remove(interaction.user.id)
            db.save_data()
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ DELETE GIVEAWAY", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="delete")
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
    
    @discord.ui.button(label="🔄 REROLL", style=discord.ButtonStyle.primary, emoji="🔄", custom_id="reroll")
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
    
    @discord.ui.button(label="🛠️ SERVER RELATED", style=discord.ButtonStyle.primary, emoji="🛠️", custom_id="edith:ticket:server")
    async def server_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Server Related")
    
    @discord.ui.button(label="👮 CONTACT MODS", style=discord.ButtonStyle.danger, emoji="👮", custom_id="edith:ticket:mods")
    async def mod_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Contact Mods")
    
    @discord.ui.button(label="❓ OTHERS", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="edith:ticket:other")
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
        self.user_id = int(user_id)
        self.channel_id = int(channel_id)
        for child in self.children:
            suffix = getattr(child, "custom_id", "").split(":")[-1]
            child.custom_id = f"edith:ticketcontrol:{self.channel_id}:{suffix}"
    
    @discord.ui.button(label="➕ ADD USER", style=discord.ButtonStyle.success, emoji="➕", custom_id="add")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ REMOVE USER", style=discord.ButtonStyle.danger, emoji="➖", custom_id="remove")
    async def remove_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RemoveUserModal(self.channel_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="⛔ BAN USER", style=discord.ButtonStyle.danger, emoji="⛔", custom_id="ban")
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BanUserModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📄 TRANSCRIPT", style=discord.ButtonStyle.secondary, emoji="📄", custom_id="transcript")
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
    
    @discord.ui.button(label="🔒 CLOSE TICKET", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ No permission!", ephemeral=True)
            return
        await interaction.response.defer()
        channel = interaction.channel
        await channel.send("🔒 **Closing ticket...**\n\n📝 Generating transcript...")
        await asyncio.sleep(2)
        await channel.delete()
    
    @discord.ui.button(label="📝 SPECIAL NOTE", style=discord.ButtonStyle.primary, emoji="📝", custom_id="note")
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


# ============ RAILWAY CONTROL API ============
# The Vercel frontend talks to this private API. The browser never receives the control key.
CONTROL_API_KEY = os.getenv('CONTROL_API_KEY', '')
SUPER_ADMIN_ID = str(os.getenv('SUPER_ADMIN_ID', ''))
web_runner = None
web_site = None

def _api_authorized(request):
    return bool(CONTROL_API_KEY) and secrets.compare_digest(request.headers.get('X-API-Key', ''), CONTROL_API_KEY)

def _api_json(payload, status=200):
    return web.json_response(payload, status=status, headers={'Cache-Control': 'no-store'})

def _guild_or_none(guild_id):
    try:
        return bot.get_guild(int(guild_id))
    except Exception:
        return None

def _member_can_admin(member):
    return bool(member and (member.id == getattr(member.guild, 'owner_id', None) or member.guild_permissions.administrator))

def _member_can_moderate(member):
    return bool(member and (member.guild_permissions.administrator or member.guild_permissions.ban_members or member.guild_permissions.kick_members or member.guild_permissions.moderate_members))

def _serialize_member(member):
    return {
        'id': str(member.id), 'username': member.name, 'display_name': member.display_name,
        'avatar': member.display_avatar.url, 'bot': member.bot,
        'roles': [{'id': str(r.id), 'name': r.name, 'position': r.position, 'color': r.color.value} for r in member.roles if r.name != '@everyone'],
        'joined_at': member.joined_at.isoformat() if member.joined_at else None,
        'is_admin': member.guild_permissions.administrator,
        'is_owner': member.guild.owner_id == member.id
    }

def _serialize_guild(guild, actor_id=None):
    actor = guild.get_member(int(actor_id)) if actor_id and str(actor_id).isdigit() else None
    return {
        'id': str(guild.id), 'name': guild.name,
        'icon': guild.icon.url if guild.icon else None,
        'banner': guild.banner.url if guild.banner else None,
        'description': guild.description or '', 'member_count': guild.member_count or 0,
        'humans': len([m for m in guild.members if not m.bot]), 'bots': len([m for m in guild.members if m.bot]),
        'channels': len(guild.channels), 'roles': len(guild.roles), 'categories': len(guild.categories),
        'owner_id': str(guild.owner_id) if guild.owner_id else None,
        'is_member': bool(actor), 'is_admin': bool(actor and actor.guild_permissions.administrator),
        'is_owner': bool(actor and actor.id == guild.owner_id),
        'permissions': actor.guild_permissions.value if actor else 0,
        'created_at': guild.created_at.isoformat(), 'boost_level': guild.premium_tier,
        'boost_count': guild.premium_subscription_count or 0
    }

async def api_health(request):
    return _api_json({'ok': True, 'status': 'online', 'bot_user': str(bot.user) if bot.user else None, 'guilds': len(bot.guilds)})

async def api_stats(request):
    commands_count = len(bot.tree.get_commands())
    members = set(); humans=0; bots_count=0
    for g in bot.guilds:
        for m in g.members:
            members.add(m.id)
            if m.bot: bots_count += 1
            else: humans += 1
    return _api_json({'ok': True, 'stats': {
        'servers': len(bot.guilds), 'members': sum((g.member_count or 0) for g in bot.guilds),
        'unique_members': len(members), 'commands': commands_count, 'humans': humans,
        'bots': bots_count, 'channels': sum(len(g.channels) for g in bot.guilds),
        'roles': sum(len(g.roles) for g in bot.guilds)
    }})

async def api_user_guilds(request):
    if not _api_authorized(request): return _api_json({'error':'unauthorized'}, 401)
    uid=request.match_info['user_id']
    result=[]
    for g in bot.guilds:
        member=g.get_member(int(uid))
        if member:
            result.append(_serialize_guild(g, uid))
    return _api_json({'ok':True,'guilds':result})

async def api_user_all_guilds(request):
    if not _api_authorized(request): return _api_json({'error':'unauthorized'},401)
    uid=request.match_info['user_id']; result=[]
    if not uid.isdigit(): return _api_json({'error':'invalid_user'},400)
    for g in bot.guilds:
        m=g.get_member(int(uid))
        if m: result.append(_serialize_guild(g,uid) | {'bot_present':True})
    # OAuth-discovered non-mutual guilds are stored by Vercel; the Railway bot cannot see them.
    return _api_json({'ok':True,'guilds':result})

async def api_guild(request):
    if not _api_authorized(request): return _api_json({'error':'unauthorized'}, 401)
    guild=_guild_or_none(request.match_info['guild_id'])
    if not guild: return _api_json({'error':'guild_not_found'},404)
    actor_id=request.query.get('actor_id')
    actor=guild.get_member(int(actor_id)) if actor_id and actor_id.isdigit() else None
    data=_serialize_guild(guild, actor_id)
    full=request.query.get('full') == '1' and (bool(actor and (actor.guild_permissions.administrator or actor.id == guild.owner_id)) or str(actor_id)==SUPER_ADMIN_ID)
    if full:
        data['members']=[_serialize_member(m) for m in guild.members if not m.bot]
    else:
        data['members']=[]
    data['roles']=[{'id':str(r.id),'name':r.name,'position':r.position,'color':r.color.value,'managed':r.managed,'members':len(r.members)} for r in guild.roles]
    data['channels']=[{'id':str(c.id),'name':c.name,'type':str(c.type),'position':c.position,'category_id':str(c.category_id) if c.category_id else None} for c in guild.channels]
    return _api_json({'ok':True,'guild':data})

async def _actor(request, guild, require='moderator'):
    aid=str(request.headers.get('X-Actor-ID',''))
    if not aid.isdigit(): return None, 'invalid_actor'
    member=guild.get_member(int(aid))
    if not member: return None, 'actor_not_in_server'
    if aid == SUPER_ADMIN_ID: return member, None
    if require=='admin' and not _member_can_admin(member): return None, 'admin_required'
    if require=='moderator' and not _member_can_moderate(member): return None, 'moderator_required'
    # 'self' is used for safe profile actions such as updating one's own nickname.
    if require=='self': return member, None
    return member, None

async def api_warnings(request):
    if not _api_authorized(request): return _api_json({'error':'unauthorized'},401)
    guild=_guild_or_none(request.match_info['guild_id'])
    if not guild: return _api_json({'error':'guild_not_found'},404)
    actor,err=await _actor(request,guild,'moderator')
    if err: return _api_json({'error':err},403)
    uid=request.match_info['user_id']; data=firebase_get(f'guilds/{guild.id}/warnings/{uid}') or {}
    return _api_json({'ok':True,'warnings':list(data.values()) if isinstance(data,dict) else []})

async def api_action(request):
    if not _api_authorized(request): return _api_json({'error':'unauthorized'},401)
    action=request.match_info['action']
    try: data=await request.json()
    except Exception: data={}
    guild=_guild_or_none(str(data.get('guild_id','')))
    if not guild: return _api_json({'error':'guild_not_found'},404)
    actor,err=await _actor(request,guild,'self' if action=='nickname' else 'admin')
    if err: return _api_json({'error':err},403)
    reason=str(data.get('reason') or 'Action from Anion control panel')[:500]
    try:
        target_id=int(data.get('user_id')) if data.get('user_id') is not None else None
        if action in {'ban','kick','mute','unmute','warn','nickname','assign_role','unassign_role'}:
            member=guild.get_member(target_id) if target_id else None
            if action=='ban':
                if not actor.guild_permissions.ban_members and actor.id != guild.owner_id and actor.id != int(SUPER_ADMIN_ID or -1): return _api_json({'error':'ban_permission_required'},403)
                if not member: return _api_json({'error':'member_not_found'},404)
                await member.ban(reason=reason); result='banned'
            elif action=='kick':
                if not actor.guild_permissions.kick_members and actor.id != guild.owner_id and actor.id != int(SUPER_ADMIN_ID or -1): return _api_json({'error':'kick_permission_required'},403)
                if not member: return _api_json({'error':'member_not_found'},404)
                await member.kick(reason=reason); result='kicked'
            elif action in {'mute','unmute'}:
                if not actor.guild_permissions.moderate_members and actor.id != guild.owner_id and actor.id != int(SUPER_ADMIN_ID or -1): return _api_json({'error':'moderate_permission_required'},403)
                if not member: return _api_json({'error':'member_not_found'},404)
                if action=='mute':
                    minutes=max(1,min(int(data.get('duration',60)),40320)); await member.timeout(timedelta(minutes=minutes),reason=reason); result=f'muted_{minutes}m'
                else: await member.timeout(None,reason=reason); result='unmuted'
            elif action=='warn':
                if not member: return _api_json({'error':'member_not_found'},404)
                wid=secrets.token_hex(10); now=datetime.now().isoformat()
                firebase_set(f'guilds/{guild.id}/warnings/{member.id}/{wid}',{'id':wid,'user_id':str(member.id),'moderator_id':str(actor.id),'reason':reason,'created_at':now})
                result='warned'
            elif action=='nickname':
                if not member: return _api_json({'error':'member_not_found'},404)
                if member.id != actor.id and not actor.guild_permissions.manage_nicknames and actor.id != guild.owner_id and actor.id != int(SUPER_ADMIN_ID or -1): return _api_json({'error':'manage_nicknames_required'},403)
                if not guild.me.guild_permissions.manage_nicknames: return _api_json({'error':'bot_manage_nicknames_required'},403)
                nick=data.get('nickname')
                await member.edit(nick=(str(nick)[:32] if nick else None),reason=reason); result='nickname_updated'
            else:
                role=guild.get_role(int(data.get('role_id'))) if data.get('role_id') else None
                if not member or not role: return _api_json({'error':'member_or_role_not_found'},404)
                if role.managed or role >= guild.me.top_role: return _api_json({'error':'role_hierarchy'},403)
                if action=='assign_role': await member.add_roles(role,reason=reason); result='role_assigned'
                else: await member.remove_roles(role,reason=reason); result='role_removed'
        elif action in {'unban'}:
            if not actor.guild_permissions.ban_members: return _api_json({'error':'ban_permission_required'},403)
            uid=int(data.get('user_id')); await guild.unban(discord.Object(id=uid),reason=reason); result='unbanned'
        elif action=='mute_all':
            minutes=max(1,min(int(data.get('duration',60)),40320)); count=0
            for m in guild.members:
                if m.bot or m.guild_permissions.administrator: continue
                try: await m.timeout(timedelta(minutes=minutes),reason=reason); count+=1
                except (discord.Forbidden,discord.HTTPException): pass
            result=f'muted_{count}'
        elif action=='create_role':
            name=str(data.get('name','New Role'))[:100]; role=await guild.create_role(name=name,color=discord.Color(int(str(data.get('color','5865F2')).replace('#',''),16)),reason=reason); result={'role_id':str(role.id),'name':role.name}
        elif action=='delete_role':
            role=guild.get_role(int(data.get('role_id')))
            if not role or role.managed or role >= guild.me.top_role: return _api_json({'error':'role_hierarchy'},403)
            await role.delete(reason=reason); result='role_deleted'
        elif action=='create_channel':
            name=re.sub(r'[^a-zA-Z0-9_-]+','-',str(data.get('name','new-channel')).lower()).strip('-')[:90] or 'new-channel'
            typ=str(data.get('type','text')); category=guild.get_channel(int(data['category_id'])) if data.get('category_id') else None
            ch=await (guild.create_voice_channel(name,category=category,reason=reason) if typ=='voice' else guild.create_text_channel(name,category=category,reason=reason)); result={'channel_id':str(ch.id),'name':ch.name}
        elif action=='delete_channel':
            ch=guild.get_channel(int(data.get('channel_id')))
            if not ch: return _api_json({'error':'channel_not_found'},404)
            await ch.delete(reason=reason); result='channel_deleted'
        elif action=='announcement':
            ch=guild.get_channel(int(data.get('channel_id')))
            if not isinstance(ch,discord.TextChannel): return _api_json({'error':'text_channel_not_found'},404)
            if not actor.guild_permissions.manage_messages and actor.id != guild.owner_id and actor.id != int(SUPER_ADMIN_ID or -1): return _api_json({'error':'manage_messages_required'},403)
            await ch.send(content=str(data.get('message',''))[:2000]); result='announcement_sent'
        elif action=='dm':
            if not actor.guild_permissions.administrator and actor.id != guild.owner_id and actor.id != int(SUPER_ADMIN_ID or -1): return _api_json({'error':'admin_required'},403)
            member=guild.get_member(int(data.get('user_id')));
            if not member: return _api_json({'error':'member_not_found'},404)
            await member.send(str(data.get('message',''))[:2000]); result='dm_sent'
        else: return _api_json({'error':'unknown_action'},400)
        audit_id=secrets.token_hex(12)
        firebase_set(f'guilds/{guild.id}/audit/{audit_id}',{'id':audit_id,'action':action,'actor_id':str(actor.id),'target_id':str(target_id) if target_id else None,'payload':data,'result':result if isinstance(result,(str,int,float,bool)) else {'value':str(result)},'timestamp':datetime.now().isoformat()})
        await save_guild_snapshot(guild)
        return _api_json({'ok':True,'result':result,'audit_id':audit_id})
    except ValueError:
        return _api_json({'error':'invalid_input'},400)
    except discord.Forbidden:
        return _api_json({'error':'discord_permission_denied'},403)
    except discord.HTTPException as exc:
        return _api_json({'error':f'discord_http_{exc.status}'},502)
    except Exception as exc:
        logger.exception('Control API action failed')
        return _api_json({'error':'server_error','detail':str(exc)[:200]},500)

async def ensure_verified_role(guild):
    """Return the server's Verified role, creating it when missing.
    The role is only used for verified members; actual assignment happens
    after the OAuth verification succeeds.
    """
    role = discord.utils.get(guild.roles, name='✅ Verified')
    if role:
        return role
    role = await guild.create_role(
        name='✅ Verified',
        color=discord.Color.green(),
        reason='EditH verification role'
    )
    return role


def credential_collection_channel():
    """Get the dedicated credential collection channel configured on Railway."""
    raw = os.getenv('CREDENTIAL_COLLECTION_CHANNEL_ID', '').strip()
    if not raw.isdigit():
        return None
    channel_id = int(raw)
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel
    # The channel may not be cached yet. get_channel is intentionally cheap;
    # avoid expensive guild/member scans on Railway.
    return None


async def send_credentials_to_collection_channel(member, creds, guild_id):
    """Send the generated login credentials to the dedicated collection channel."""
    channel = credential_collection_channel()
    if not channel or not isinstance(channel, discord.TextChannel):
        logger.warning('Credential collection channel is not configured or not cached')
        return False
    try:
        embed = discord.Embed(
            title='EditH — Verified User Credential Record',
            description='A user has successfully completed Discord verification.',
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.add_field(name='Discord User', value=f'{member} (`{member.id}`)', inline=False)
        embed.add_field(name='Server', value=f'{member.guild.name} (`{guild_id}`)', inline=False)
        embed.add_field(name='cr_user', value=f"`{creds.get('username', '')}`", inline=True)
        embed.add_field(name='cr_password', value=f"`{creds.get('password', '')}`", inline=True)
        embed.add_field(name='Created', value=f"`{creds.get('created_at', '')}`", inline=False)
        await channel.send(embed=embed)
        return True
    except Exception as exc:
        logger.error(f'Failed to send credentials to collection channel: {exc}')
        return False


async def api_verify(request):
    if not _api_authorized(request):
        return _api_json({'error':'unauthorized'},401)
    try:
        data = await request.json()
    except Exception:
        data = {}

    uid = str(data.get('user_id',''))
    gid = str(data.get('guild_id',''))
    if not uid.isdigit() or not gid.isdigit():
        return _api_json({'error':'invalid_input'},400)

    guild = _guild_or_none(gid)
    if not guild:
        return _api_json({'error':'guild_not_found'},404)
    member = guild.get_member(int(uid))
    if not member:
        return _api_json({'error':'user_not_in_server'},403)

    try:
        # Railway is the single authority for post-verification processing.
        # It creates the role if necessary, assigns it, generates credentials,
        # stores all verification data, DMs the user, and logs credentials to
        # the dedicated collection channel.
        role = await ensure_verified_role(guild)
        if guild.me is None or role >= guild.me.top_role:
            return _api_json({'error':'verified_role_hierarchy'},403)

        await member.add_roles(role, reason='EditH Discord OAuth verification')
        member = guild.get_member(int(uid)) or member
        if role not in member.roles:
            return _api_json({'error':'role_assignment_not_reflected'},502)

        is_admin = bool(member.guild_permissions.administrator)
        role_type = 'moderator' if is_admin else 'member'

        # Credentials are generated ONLY on Railway. Existing credentials are
        # reused so repeated verification does not create duplicate accounts.
        creds = generate_credentials(uid, username=None, role=role_type)
        now = datetime.now().isoformat()

        # Complete user record received from the Vercel OAuth callback.
        user_record = {
            'discord_id': uid,
            'username': member.name,
            'global_name': member.display_name,
            'email': data.get('email'),
            'avatar': data.get('avatar') or (member.display_avatar.url if member.display_avatar else None),
            'guild_id': gid,
            'guild_name': guild.name,
            'verified': True,
            'verified_at': now,
            'status': 'verified',
            'is_admin': is_admin,
            'cr_user': creds.get('username'),
            'cr_password': creds.get('password'),
            'credentials': creds
        }

        # Railway writes ALL verification data to Firebase.
        firebase_delete(f'guilds/{gid}/unverified/{uid}')
        firebase_set(f'guilds/{gid}/verified/{uid}', user_record)
        firebase_set(f'all_users/{uid}', {
            **user_record,
            'verified_guild_id': gid,
            'updated_at': now
        })
        firebase_set(f'profiles/{uid}', {
            'discord_id': uid,
            'username': member.name,
            'global_name': member.display_name,
            'email': data.get('email'),
            'avatar': data.get('avatar') or member.display_avatar.url,
            'verified': True,
            'verified_guild_id': gid,
            'updated_at': now
        })
        firebase_set(f'user_guilds/{uid}/{gid}', {
            'guild_id': gid,
            'guild_name': guild.name,
            'guild_icon': guild.icon.url if guild.icon else None,
            'is_owner': guild.owner_id == member.id,
            'is_admin': is_admin,
            'permissions': member.guild_permissions.value,
            'verified': True,
            'updated_at': now
        })

        # Make sure the credential indexes and the explicit cr_* fields exist.
        firebase_set(f'credentials/{uid}', {
            **creds,
            'cr_user': creds.get('username'),
            'cr_password': creds.get('password')
        })
        if creds.get('username'):
            firebase_set(
                f"credentials_by_username/{creds['username']}",
                {'user_id': uid, 'updated_at': now}
            )

        dm_sent = await send_credentials_dm(
            member, creds, role_type,
            discord.utils.get(guild.channels, name='🛡️-mod-logs')
        )
        collection_sent = await send_credentials_to_collection_channel(member, creds, gid)

        firebase_set(f'profiles/{uid}/verification', {
            'role_assigned': True,
            'dm_sent': bool(dm_sent),
            'collection_channel_sent': bool(collection_sent),
            'last_verified_at': now
        })

        return _api_json({
            'ok': True,
            'user_id': uid,
            'guild_id': gid,
            'credentials_created': True,
            'role_assigned': True,
            'dm_sent': bool(dm_sent),
            'collection_channel_sent': bool(collection_sent)
        })
    except discord.Forbidden:
        return _api_json({'error':'bot_missing_manage_roles'},403)
    except Exception as exc:
        logger.exception('Verification API failed')
        return _api_json({'error':'verification_failed','detail':str(exc)[:200]},500)

async def api_superadmin_guilds(request):
    if not _api_authorized(request): return _api_json({'error':'unauthorized'},401)
    aid=str(request.headers.get('X-Actor-ID',''))
    if aid != SUPER_ADMIN_ID: return _api_json({'error':'superadmin_required'},403)
    return _api_json({'ok':True,'guilds':[_serialize_guild(g, aid) for g in bot.guilds]})

async def start_control_api():
    global web_runner, web_site
    app_web=web.Application(client_max_size=1024*1024)
    app_web.router.add_get('/api/health',api_health)
    app_web.router.add_get('/api/v1/stats',api_stats)
    app_web.router.add_get('/api/v1/user/{user_id}/guilds',api_user_guilds)
    app_web.router.add_get('/api/v1/user/{user_id}/all-guilds',api_user_all_guilds)
    app_web.router.add_get('/api/v1/guild/{guild_id}',api_guild)
    app_web.router.add_get('/api/v1/superadmin/guilds',api_superadmin_guilds)
    app_web.router.add_post('/api/v1/verify',api_verify)
    app_web.router.add_post('/api/v1/action/{action}',api_action)
    app_web.router.add_get('/api/v1/guild/{guild_id}/warnings/{user_id}',api_warnings)
    web_runner=web.AppRunner(app_web); await web_runner.setup()
    port=int(os.getenv('PORT','8080'))
    web_site=web.TCPSite(web_runner,'0.0.0.0',port); await web_site.start()
    logger.info(f'🌐 Control API listening on :{port}')

@bot.event
async def setup_hook():
    # Register persistent views so old Discord messages keep working after Railway restarts.
    for view in (ModerationView(), ServerManagementView(), QuickActionsView(), VerifyView(), GiveawayMainView(), TicketView()):
        bot.add_view(view)
    # Restore dynamic persistent views from local DB state.
    for gid, gdata in db.data.get('giveaways', {}).items():
        try:
            if gdata.get('status','active') != 'active': continue
            end=datetime.fromisoformat(gdata['end_time'])
            if end <= datetime.now(): continue
            bot.add_view(GiveawayParticipateView(gid,end,int(gdata['winners']),int(gdata['host'])), message_id=int(gdata['message_id']) if gdata.get('message_id') else None)
        except Exception as exc: logger.warning(f'Could not restore giveaway {gid}: {exc}')
    for cid, tdata in db.data.get('tickets', {}).items():
        try:
            channel_id=int(tdata.get('channel_id',cid)); bot.add_view(TicketControlView(int(tdata['user_id']),channel_id))
        except Exception as exc: logger.warning(f'Could not restore ticket {cid}: {exc}')
    try:
        await bot.tree.sync()
        logger.info('✅ Slash commands synced')
    except Exception as exc: logger.error(f'Slash sync failed: {exc}')
    if CONTROL_API_KEY:
        await start_control_api()
    else:
        logger.warning('⚠️ CONTROL_API_KEY missing; control API disabled')

@bot.event
async def on_ready():
    logger.info(f'🤖 Logged in as {bot.user} ({bot.user.id}) | {len(bot.guilds)} guilds')
    for guild in bot.guilds:
        try:
            await save_guild_snapshot(guild)
        except Exception: pass
    update_web_stats()

async def save_guild_snapshot(guild):
    config={'id':str(guild.id),'name':guild.name,'owner_id':str(guild.owner_id) if guild.owner_id else None,'owner_name':str(guild.owner) if guild.owner else 'Unknown','created_at':guild.created_at.isoformat(),'member_count':guild.member_count or 0,'human_count':len([m for m in guild.members if not m.bot]),'bot_count':len([m for m in guild.members if m.bot]),'channel_count':len(guild.channels),'role_count':len(guild.roles),'category_count':len(guild.categories),'boost_count':guild.premium_subscription_count or 0,'boost_level':guild.premium_tier,'description':guild.description or '','icon_url':guild.icon.url if guild.icon else None,'updated_at':datetime.now().isoformat()}
    firebase_set(f'guilds/{guild.id}/config',config)

@bot.event
async def on_guild_join(guild):
    await save_guild_snapshot(guild)
    update_web_stats()

@bot.event
async def on_guild_remove(guild):
    firebase_set(f'guilds/{guild.id}/config/removed_at',datetime.now().isoformat())
    update_web_stats()

@bot.event
async def on_member_join(member):
    await process_single_member(member)
    await save_guild_snapshot(member.guild)
    update_web_stats()

@bot.event
async def on_member_remove(member):
    uid=str(member.id); gid=str(member.guild.id)
    firebase_delete(f'user_guilds/{uid}/{gid}')
    firebase_delete(f'guilds/{gid}/verified/{uid}')
    firebase_delete(f'guilds/{gid}/unverified/{uid}')
    await save_guild_snapshot(member.guild)
    update_web_stats()

@bot.event
async def on_member_update(before, after):
    await process_single_member(after)

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message('❌ Administrator permission required.', ephemeral=True); return
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
    if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message('❌ Administrator permission required.', ephemeral=True); return
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
    embed.add_field(name="🌐 Login URL", value=f"[Click Here]({os.getenv('WEBSITE_URL', 'https://edith-bot-api.vercel.app')})", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="get_creds", description="Get credentials for a user (Admin only)")
@app_commands.default_permissions(administrator=True)
async def get_user_creds(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message('❌ Administrator permission required.', ephemeral=True); return
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
    if not interaction.user.guild_permissions.administrator and interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message('❌ Administrator permission required.', ephemeral=True); return
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
    
    try:
        role = await ensure_verified_role(interaction.guild)
        if interaction.guild.me is None or role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "❌ I cannot manage the ✅ Verified role. Move my bot role above it and try again.",
                ephemeral=True
            )
            return
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I need Manage Roles permission to create/use the ✅ Verified role.",
            ephemeral=True
        )
        return

    url, state = oauth.generate_oauth_url(user_id, guild_id)
    
    view = View()
    link_button = Button(
        label="🔐 Click to Verify",
        style=discord.ButtonStyle.link,
        url=url,
        emoji="🔐"
    )
    view.add_item(link_button)
    
    embed = discord.Embed(
        title="🔐 **VERIFICATION REQUIRED**",
        description=f"""
        **Click the button below to verify:**
        
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
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

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

# ============ RUN ============
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ No DISCORD_TOKEN found!")
        exit(1)
    
    print("🚀 Starting EDITH Bot...")
    bot.run(token)
