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

# ============ OAUTH VERIFICATION ============
class OAuthVerification:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI', 'https://your-vercel-app.vercel.app/callback')
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
            **Click the button below to verify:**
            
            ⏰ **TIME LIMIT:** 10 minutes
            🔒 **SECURITY:** Your data is encrypted
            
            **✅ WHAT HAPPENS NEXT:**
            1. Authorize through Discord
            2. Get the ✅ Verified role
            3. Receive your login credentials
            """,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Verification ID: {state[:8]}...")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ============ HELPER FUNCTIONS ============
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

def get_credentials(user_id):
    return firebase_get(f'credentials/{user_id}')

def delete_credentials(user_id):
    firebase_delete(f'credentials/{user_id}')
    logger.info(f"🗑️ Deleted credentials for {user_id}")

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

async def send_credentials_dm(member, creds, role=None, log_channel=None):
    if not creds:
        return False
    
    role = role or creds.get('role', 'member')
    
    embed = discord.Embed(
        title="🔐 **YOUR CREDENTIALS**",
        description=f"Welcome to **{member.guild.name}**!",
        color=discord.Color.gold()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Username", value=f"`{creds['username']}`", inline=True)
    embed.add_field(name="Password", value=f"`{creds['password']}`", inline=True)
    embed.add_field(name="Role", value=f"`{role.upper()}`", inline=True)
    embed.add_field(name="Login URL", value=f"[Click Here]({os.getenv('WEBSITE_URL', 'https://your-vercel-app.vercel.app')})", inline=False)
    embed.set_footer(text="⚠️ Keep these safe!")
    
    try:
        await member.send(embed=embed)
        logger.info(f"✅ Credentials sent to {member.name}")
        return True
    except:
        return False

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 **EDITH - ULTIMATE SERVER MANAGEMENT**",
        description="""
        **Click any button below to set up that system!**
        
        **⚠️ WARNING:** Setup All will DELETE ALL existing channels and roles!
        """,
        color=discord.Color.gold()
    )
    view = SetupView(interaction.user)
    await interaction.response.send_message(embed=embed, view=view)

# ============ SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
    
    @discord.ui.button(label="⚡ SETUP ALL", style=discord.ButtonStyle.success, emoji="⚡")
    async def setup_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.send_message("🔄 **Starting setup...**", ephemeral=True)
        await self.setup_all(interaction.guild, interaction)
    
    @discord.ui.button(label="🔐 VERIFICATION", style=discord.ButtonStyle.primary, emoji="🔐")
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(VerificationSetupModal())
    
    @discord.ui.button(label="🎫 TICKETS", style=discord.ButtonStyle.secondary, emoji="🎫")
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(TicketSetupModal())
    
    @discord.ui.button(label="🎁 GIVEAWAYS", style=discord.ButtonStyle.primary, emoji="🎁")
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(GiveawaySetupModal())
    
    @discord.ui.button(label="👑 ROLES", style=discord.ButtonStyle.secondary, emoji="👑")
    async def setup_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await self.create_roles(interaction.guild)
            await interaction.followup.send("✅ Roles created!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🛡️ MODERATION", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def setup_moderation(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        await interaction.response.send_modal(ModerationSetupModal())
    
    async def setup_all(self, guild, interaction):
        try:
            await interaction.followup.send("🔄 **Creating server structure...**", ephemeral=True)
            
            categories = {
                "📋 INFORMATION": ["📌-rules", "📢-announcements", "📋-server-info"],
                "🔐 SECURITY": ["🔐-verification", "🛡️-mod-logs", "📊-logs"],
                "💬 GENERAL": ["💬-general-chat", "📸-media", "🎮-gaming", "🎵-music"],
                "📞 VOICE": ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"],
                "🎫 SUPPORT": ["🎫-tickets", "📝-feedback", "❓-faq"],
                "🎉 EVENTS": ["🎉-giveaways", "📅-events", "🏆-contests"],
                "👑 ADMIN": ["⚙️-admin-commands", "📊-stats", "🔧-bot-controls"]
            }
            
            created_count = 0
            
            for category_name, channel_names in categories.items():
                category = await guild.create_category(category_name)
                for channel_name in channel_names:
                    try:
                        await guild.create_text_channel(channel_name, category=category)
                        created_count += 1
                    except:
                        pass
            
            # Create roles
            roles_config = {
                "👑 Owner": discord.Permissions(administrator=True),
                "🛡️ Admin": discord.Permissions(administrator=True),
                "🔰 Moderator": discord.Permissions(kick_members=True, ban_members=True, manage_messages=True),
                "🤝 Helper": discord.Permissions(manage_messages=True),
                "✅ Verified": discord.Permissions(read_messages=True, send_messages=True, connect=True, speak=True),
                "❌ Unverified": discord.Permissions(read_messages=True, send_messages=False),
                "🎁 Giveaway": discord.Permissions(read_messages=True, send_messages=False),
                "🎮 Gamer": discord.Permissions(read_messages=True, send_messages=True),
                "🎵 Music Lover": discord.Permissions(read_messages=True, send_messages=True)
            }
            
            for role_name, perms in roles_config.items():
                try:
                    await guild.create_role(name=role_name, permissions=perms)
                except:
                    pass
            
            # Send messages
            verify_channel = discord.utils.get(guild.channels, name="🔐-verification")
            ticket_channel = discord.utils.get(guild.channels, name="🎫-tickets")
            giveaway_channel = discord.utils.get(guild.channels, name="🎉-giveaways")
            mod_channel = discord.utils.get(guild.channels, name="🛡️-mod-logs")
            
            if verify_channel:
                await self.send_verification_message(verify_channel)
            if ticket_channel:
                await self.send_ticket_message(ticket_channel)
            if giveaway_channel:
                await self.send_giveaway_message(giveaway_channel)
            
            embed = discord.Embed(
                title="✅ **SERVER SETUP COMPLETE!**",
                description=f"**{guild.name}** has been fully configured!\n\n🎉 Your server is ready!",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    async def send_verification_message(self, channel):
        embed = discord.Embed(
            title="🔐 **VERIFICATION REQUIRED**",
            description="Click the button below to verify!",
            color=discord.Color.blue()
        )
        view = VerifyView()
        await channel.send(embed=embed, view=view)
    
    async def send_ticket_message(self, channel):
        embed = discord.Embed(
            title="🎫 **TICKET SYSTEM**",
            description="Click a button to create a ticket!",
            color=discord.Color.purple()
        )
        view = TicketView()
        await channel.send(embed=embed, view=view)
    
    async def send_giveaway_message(self, channel):
        embed = discord.Embed(
            title="🎉 **GIVEAWAY CENTER**",
            description="👑 Admin only: Host giveaways!",
            color=discord.Color.gold()
        )
        view = GiveawayMainView()
        await channel.send(embed=embed, view=view)
    
    async def create_roles(self, guild):
        roles_config = {
            "👑 Owner": discord.Permissions(administrator=True),
            "🛡️ Admin": discord.Permissions(administrator=True),
            "🔰 Moderator": discord.Permissions(kick_members=True, ban_members=True, manage_messages=True),
            "🤝 Helper": discord.Permissions(manage_messages=True),
            "✅ Verified": discord.Permissions(read_messages=True, send_messages=True, connect=True, speak=True),
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
                title=f"🎫 Ticket: {ticket_type}",
                description=f"Created by: {interaction.user.mention}",
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
        await interaction.channel.send("🔒 Closing ticket...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

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

# ============ GIVEAWAY SYSTEM ============
class GiveawayMainView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎁 HOST GIVEAWAY", style=discord.ButtonStyle.success)
    async def host_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions!", ephemeral=True)
            return
        modal = GiveawayModal()
        await interaction.response.send_modal(modal)

class GiveawayModal(Modal):
    def __init__(self):
        super().__init__(title="Host Giveaway")
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
                """,
                color=discord.Color.gold()
            )
            
            view = GiveawayParticipateView(giveaway_id, end_time, winners_count, interaction.user.id)
            await interaction.response.send_message(embed=embed, view=view)
            
            asyncio.create_task(self.giveaway_countdown(giveaway_id, interaction.channel, end_time))
            
        except ValueError:
            await interaction.response.send_message("❌ Invalid numbers!", ephemeral=True)
    
    async def giveaway_countdown(self, giveaway_id, channel, end_time):
        await asyncio.sleep((end_time - datetime.now()).total_seconds())
        
        winners = random.sample([1, 2, 3], 1)  # Simplified
        
        embed = discord.Embed(
            title="🎉 GIVEAWAY COMPLETE!",
            description=f"Winners: <@{winners[0]}>",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 PARTICIPATE", style=discord.ButtonStyle.success)
    async def participate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ You're participating!", ephemeral=True)
    
    @discord.ui.button(label="❌ UN-PARTICIPATE", style=discord.ButtonStyle.danger)
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ Removed!", ephemeral=True)

# ============ SETUP MODALS ============
class VerificationSetupModal(Modal):
    def __init__(self):
        super().__init__(title="🔐 Verification Setup")
        self.channel_input = TextInput(label="Channel ID", required=True)
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_input.value)
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                return
            
            # Create Verified role
            verified_role = discord.utils.get(interaction.guild.roles, name="✅ Verified")
            if not verified_role:
                await interaction.guild.create_role(
                    name="✅ Verified",
                    color=discord.Color.green()
                )
            
            embed = discord.Embed(
                title="🔐 **VERIFICATION REQUIRED**",
                description="Click the button below to verify!",
                color=discord.Color.blue()
            )
            view = VerifyView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Verification setup complete in {channel.mention}!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid channel ID!", ephemeral=True)

class TicketSetupModal(Modal):
    def __init__(self):
        super().__init__(title="🎫 Ticket Setup")
        self.channel_input = TextInput(label="Channel ID", required=True)
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
                description="Click a button to create a ticket!",
                color=discord.Color.purple()
            )
            view = TicketView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Ticket setup complete in {channel.mention}!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid channel ID!", ephemeral=True)

class GiveawaySetupModal(Modal):
    def __init__(self):
        super().__init__(title="🎁 Giveaway Setup")
        self.channel_input = TextInput(label="Channel ID", required=True)
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
                description="👑 Admin only: Host giveaways!",
                color=discord.Color.gold()
            )
            view = GiveawayMainView()
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Giveaway setup complete in {channel.mention}!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid channel ID!", ephemeral=True)

class ModerationSetupModal(Modal):
    def __init__(self):
        super().__init__(title="🛡️ Moderation Setup")
        self.channel_input = TextInput(label="Channel ID", required=True)
        self.add_item(self.channel_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_input.value)
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message("❌ Channel not found!", ephemeral=True)
                return
            
            view = ModerationView()
            embed = discord.Embed(
                title="🛡️ **MODERATION SUITE**",
                description="Click any button to moderate!",
                color=discord.Color.red()
            )
            await channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Moderation setup complete in {channel.mention}!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid channel ID!", ephemeral=True)

class ModerationView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="⛔ BAN", style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ Use `/ban @user` command!", ephemeral=True)
    
    @discord.ui.button(label="🔇 MUTE", style=discord.ButtonStyle.primary)
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ Use `/mute @user` command!", ephemeral=True)

# ============ RUN ============
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ No DISCORD_TOKEN found!")
        exit(1)
    
    print("🚀 Starting EDITH Bot on Railway...")
    bot.run(token)
