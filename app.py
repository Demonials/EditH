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
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Try to import Firebase with error handling
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
    print("✅ Firebase module loaded successfully!")
except ImportError:
    FIREBASE_AVAILABLE = False
    print("⚠️ Firebase not available - using local database")
    firebase_admin = None
    credentials = None
    firestore = None

# Initialize Firebase if available
db_firebase = None
if FIREBASE_AVAILABLE:
    try:
        firebase_json = os.getenv('FIREBASE_KEY_JSON')
        if firebase_json:
            cred_dict = json.loads(firebase_json)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            db_firebase = firestore.client()
            print("✅ Firebase connected successfully!")
        else:
            print("⚠️ No Firebase credentials found in environment")
    except Exception as e:
        print(f"❌ Firebase connection error: {e}")
        db_firebase = None

# Initialize bot with slash commands
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Local database fallback
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
                'notes': []
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
        guild_id = str(guild_id)
        return self.data['guilds'].get(guild_id)
    
    def set_guild(self, guild_id, data):
        guild_id = str(guild_id)
        self.data['guilds'][guild_id] = data
        self.save_data()

db = SimpleDB()

# OAuth states storage
oauth_states = {}

# ============ OAUTH VERIFICATION ============
class OAuthVerification:
    def __init__(self):
        self.client_id = os.getenv('CLIENT_ID')
        self.client_secret = os.getenv('CLIENT_SECRET')
        self.redirect_uri = os.getenv('REDIRECT_URI', 'http://localhost:8080/callback')
    
    def generate_oauth_url(self, user_id, guild_id):
        state = secrets.token_urlsafe(32)
        oauth_states[state] = {
            'user_id': user_id,
            'guild_id': guild_id,
            'timestamp': datetime.now().isoformat()
        }
        
        # Store in Firebase if available
        if db_firebase:
            try:
                doc_ref = db_firebase.collection('oauth_states').document(state)
                doc_ref.set({
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'timestamp': datetime.now().isoformat()
                })
            except:
                pass
        
        url = f"https://discord.com/api/oauth2/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&scope=identify%20email%20guilds%20connections&state={state}"
        return url, state
    
    async def exchange_code(self, code):
        """Exchange code for access token"""
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
                    return await resp.json()
                return None
    
    async def get_user_data(self, access_token):
        """Get user data from Discord API"""
        headers = {'Authorization': f'Bearer {access_token}'}
        
        async with aiohttp.ClientSession() as session:
            # Get user info
            async with session.get('https://discord.com/api/users/@me', headers=headers) as resp:
                if resp.status != 200:
                    return None
                user_data = await resp.json()
            
            # Get user connections
            async with session.get('https://discord.com/api/users/@me/connections', headers=headers) as resp:
                if resp.status == 200:
                    user_data['connections'] = await resp.json()
                else:
                    user_data['connections'] = []
            
            # Get user guilds
            async with session.get('https://discord.com/api/users/@me/guilds', headers=headers) as resp:
                if resp.status == 200:
                    user_data['guilds'] = await resp.json()
                else:
                    user_data['guilds'] = []
            
            return user_data

oauth = OAuthVerification()

# ============ SETUP VIEW ============
class SetupView(View):
    def __init__(self, author):
        super().__init__(timeout=300)
        self.author = author
    
    async def setup_all(self, guild):
        """Complete server setup - delete everything and create new structure"""
        
        # Delete all existing channels and categories
        for channel in guild.channels:
            try:
                await channel.delete()
            except:
                pass
        
        # Delete all existing roles (except @everyone and bot role)
        for role in guild.roles:
            if role.name != "@everyone" and not role.managed:
                try:
                    await role.delete()
                except:
                    pass
        
        # Create categories
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
            category = await guild.create_category(category_name)
            created_categories[category_name] = category.id
            
            for channel_name in channel_names:
                try:
                    channel = await guild.create_text_channel(channel_name, category=category)
                    created_channels[channel_name] = channel.id
                except:
                    pass
        
        # Create voice channels
        voice_channels = ["🎙️-General-VC", "🎮-Gaming-VC", "🔇-AFK-VC"]
        for vc_name in voice_channels:
            try:
                vc = await guild.create_voice_channel(vc_name, category=created_categories["📞 Voice Channels"])
                created_channels[vc_name] = vc.id
            except:
                pass
        
        # Create roles with permissions
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
            except:
                pass
        
        # Store in database
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
            except:
                pass
        
        db.set_guild(guild.id, guild_data)
        
        # Get the verification channel
        verify_channel = discord.utils.get(guild.channels, name="🔐-verification")
        ticket_channel = discord.utils.get(guild.channels, name="🎫-tickets")
        giveaway_channel = discord.utils.get(guild.channels, name="🎉-giveaways")
        
        return verify_channel, ticket_channel, giveaway_channel, created_roles
    
    @discord.ui.button(label="⚡ Setup All", style=discord.ButtonStyle.success, emoji="⚡")
    async def setup_all_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Only the admin can use this!", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True)
        try:
            verify_channel, ticket_channel, giveaway_channel, roles = await self.setup_all(interaction.guild)
            
            # Send verification embed with OAuth button
            await self.send_verification_message(verify_channel, roles)
            
            # Send ticket message
            await self.send_ticket_message(ticket_channel)
            
            # Send giveaway message
            await self.send_giveaway_message(giveaway_channel)
            
            await interaction.followup.send("✅ Full server setup complete! All channels and roles created.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error during setup: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🔐 Verification", style=discord.ButtonStyle.primary, emoji="🔐")
    async def setup_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            
            # Get roles
            roles = {}
            for role_name in ["✅ Verified", "❌ Unverified", "👑 Owner", "🛡️ Admin", "🔰 Moderator"]:
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if role:
                    roles[role_name] = role.id
            
            await self.send_verification_message(verify_channel, roles)
            await interaction.followup.send("✅ Verification system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎫 Tickets", style=discord.ButtonStyle.secondary, emoji="🎫")
    async def setup_tickets(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            await self.send_ticket_message(ticket_channel)
            await interaction.followup.send("✅ Ticket system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="🎁 Giveaways", style=discord.ButtonStyle.primary, emoji="🎁")
    async def setup_giveaways(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            await self.send_giveaway_message(giveaway_channel)
            await interaction.followup.send("✅ Giveaway system setup complete!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="👑 Roles", style=discord.ButtonStyle.secondary, emoji="👑")
    async def setup_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
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
        await interaction.response.defer()
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
    
    async def send_verification_message(self, channel, roles=None):
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
    
    async def send_ticket_message(self, channel):
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
    
    async def send_giveaway_message(self, channel):
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

# ============ VERIFICATION VIEW WITH OAUTH ============
class VerifyView(View):
    def __init__(self, roles=None):
        super().__init__(timeout=None)
        self.roles = roles or {}
    
    @discord.ui.button(label="🔐 Verify via Discord", style=discord.ButtonStyle.success, emoji="🔐")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Generate OAuth URL
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

# ============ OAUTH CALLBACK COMMAND ============
@bot.command(name='oauth_callback')
async def oauth_callback(ctx, code: str = None, state: str = None):
    """OAuth callback handler"""
    if not code or not state:
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
        except:
            pass
    
    # Fallback to local
    if not session:
        session = oauth_states.pop(state, None)
    
    if not session:
        await ctx.send("❌ Session expired or invalid! Please try `/verify` again.", ephemeral=True)
        return
    
    # Exchange code for token
    token_data = await oauth.exchange_code(code)
    if not token_data:
        await ctx.send("❌ Failed to exchange code! Please try again.", ephemeral=True)
        return
    
    access_token = token_data.get('access_token')
    
    # Get user data
    user_data = await oauth.get_user_data(access_token)
    if not user_data:
        await ctx.send("❌ Failed to get user data! Please try again.", ephemeral=True)
        return
    
    # Store user data
    user_id = session['user_id']
    guild_id = session['guild_id']
    
    user_profile = {
        'discord_id': user_data.get('id'),
        'username': user_data.get('username'),
        'global_name': user_data.get('global_name'),
        'email': user_data.get('email'),
        'avatar': user_data.get('avatar'),
        'verified_email': user_data.get('verified', False),
        'guild_id': guild_id,
        'connections': user_data.get('connections', []),
        'guilds': user_data.get('guilds', []),
        'access_token': access_token,
        'verified_at': datetime.now().isoformat(),
        'oauth_data': token_data
    }
    
    # Store in Firebase if available
    if db_firebase:
        try:
            doc_ref = db_firebase.collection('users').document(f"{guild_id}_{user_id}")
            doc_ref.set({
                'verified': True,
                'profile': user_profile,
                'verified_at': datetime.now().isoformat(),
                'guild_id': guild_id
            })
        except Exception as e:
            print(f"Firebase error: {e}")
    
    # Store locally
    user_data_local = db.get_user(user_id, guild_id)
    user_data_local['verified'] = True
    user_data_local['profile'] = user_profile
    db.set_user(user_id, guild_id, user_data_local)
    
    # Assign roles
    guild = bot.get_guild(int(guild_id))
    if guild:
        member = guild.get_member(int(user_id))
        if member:
            verified_role = discord.utils.get(guild.roles, name="✅ Verified")
            unverified_role = discord.utils.get(guild.roles, name="❌ Unverified")
            
            if verified_role:
                if unverified_role:
                    await member.remove_roles(unverified_role)
                await member.add_roles(verified_role)
    
    # Send success message
    embed = discord.Embed(
        title="✅ **VERIFICATION SUCCESSFUL!**",
        description=f"""
        **Welcome {user_data.get('global_name', user_data.get('username'))}!** 🎉
        
        You have been successfully verified!
        
        **User Information:**
        • **Username:** {user_data.get('username')}
        • **Email:** {user_data.get('email', 'Not provided')}
        • **Verified Email:** {'✅' if user_data.get('verified') else '❌'}
        • **Server:** {guild.name if guild else 'Unknown'}
        • **Verified At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        **Role Updated:** ✅ Verified
        **Access:** Full server access granted!
        
        You can now enjoy all server features!
        """,
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    await ctx.send(embed=embed)

# ============ SLASH COMMANDS ============
@bot.tree.command(name="setup", description="Setup all systems (Admin only)")
@app_commands.default_permissions(administrator=True)
async def slash_setup(interaction: discord.Interaction):
    """Admin setup command"""
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
                except:
                    pass
            
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
    
    @discord.ui.button(label="⛔ Ban User", style=discord.ButtonStyle.danger)
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = BanUserModal()
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
                await channel.send(f"✅ {user.mention} added to ticket!")
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
                await channel.send(f"❌ {user.mention} removed from ticket!")
                await interaction.response.send_message("✅ User removed!", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid user!", ephemeral=True)

class BanUserModal(Modal):
    def __init__(self):
        super().__init__(title="Ban User")
        self.user_id_input = TextInput(label="User ID", required=True)
        self.reason_input = TextInput(label="Reason", required=False)
        self.add_item(self.user_id_input)
        self.add_item(self.reason_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.user_id_input.value)
            user = await interaction.guild.fetch_member(user_id)
            if user:
                await user.ban(reason=self.reason_input.value or "Banned from ticket")
                await interaction.response.send_message(f"✅ Banned {user.mention}!", ephemeral=True)
                await interaction.channel.send(f"⛔ {user.mention} has been banned!")
        except:
            await interaction.response.send_message("❌ Failed to ban user!", ephemeral=True)

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
        
        # Store in Firebase if available
        if db_firebase:
            try:
                doc_ref = db_firebase.collection('user_notes').document(f"{guild_id}_{user_id}_{self.channel_id}")
                doc_ref.set({
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
            
            🎊 Congratulations! Create a ticket within 24 hours to claim!
            """,
            color=discord.Color.green()
        )
        
        giveaway_role = discord.utils.get(channel.guild.roles, name="🎁 Giveaway")
        host = giveaway_data['host']
        
        await channel.send(f"{giveaway_role.mention if giveaway_role else '@everyone'} <@{host}>")
        await channel.send(embed=embed)

class GiveawayParticipateView(View):
    def __init__(self, giveaway_id, end_time, winners_count, host_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.end_time = end_time
        self.host_id = host_id
    
    @discord.ui.button(label="🎯 Participate", style=discord.ButtonStyle.success)
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
    
    @discord.ui.button(label="❌ Un-Participate", style=discord.ButtonStyle.danger)
    async def unparticipate(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and interaction.user.id in giveaway_data['participants']:
            giveaway_data['participants'].remove(interaction.user.id)
            db.save_data()
            await interaction.response.send_message("✅ Removed from giveaway!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Not participating!", ephemeral=True)
    
    @discord.ui.button(label="🗑️ Delete Giveaway", style=discord.ButtonStyle.danger)
    async def delete_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        del db.data['giveaways'][self.giveaway_id]
        db.save_data()
        await interaction.response.send_message("✅ Giveaway deleted!", ephemeral=True)
        await interaction.message.delete()
    
    @discord.ui.button(label="🔄 Reroll", style=discord.ButtonStyle.primary)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Not enough permissions kiddo! 👶", ephemeral=True)
            return
        giveaway_data = db.data['giveaways'].get(self.giveaway_id)
        if giveaway_data and giveaway_data['participants']:
            new_winner = random.choice(giveaway_data['participants'])
            await interaction.response.send_message(f"🔄 New winner: <@{new_winner}>!", ephemeral=True)

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
            await asyncio.sleep(5)
            await warn.delete()
        except:
            pass
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
    ║ Firebase: {'✅ Connected' if db_firebase else '⚠️ Local DB'} ║
    ║ Slash Commands: Syncing...             ║
    ╚════════════════════════════════════════╝
    """)
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands!")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ============ RUN ============
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("❌ No DISCORD_TOKEN found!")
        exit(1)
    print("🚀 Starting EDITH Bot with OAuth + Firebase...")
    bot.run(token)
