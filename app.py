#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION BOT - SIMPLE WORKING VERSION
                    RAILWAY DEPLOYMENT READY
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import io
import random
import asyncio
import sqlite3
import secrets
import requests
import logging
import threading
import time
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput

from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_cors import CORS

from dotenv import load_dotenv
load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG - SIMPLE
# ═════════════════════════════════════════════════════════════════════════════

TOKEN = os.getenv('DISCORD_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://edith.up.railway.app/callback')
DB_PATH = os.getenv('DB_PATH', '/data')

if not TOKEN:
    print("❌ DISCORD_TOKEN missing!")
    sys.exit(1)

# IMPORTANT: Database path on Railway
os.makedirs(DB_PATH, exist_ok=True)
DB_FILE = os.path.join(DB_PATH, 'bot_database.db')

print(f"✅ Token: {TOKEN[:15]}...{TOKEN[-10:]}")
print(f"✅ Database: {DB_FILE}")

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE - SIMPLE WORKING
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
        
        # All tables - simple and working
        tables = [
            """CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                verified_role_id TEXT,
                unverified_role_id TEXT,
                log_channel_id TEXT,
                giveaway_ping_role_id TEXT,
                giveaway_thumbnail_url TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS verified_users (
                user_id TEXT, guild_id TEXT,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email TEXT,
                username TEXT,
                guilds_json TEXT,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
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
            
            """CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE,
                guild_id TEXT, user_id TEXT,
                channel_id TEXT, status TEXT DEFAULT 'open',
                reason TEXT, claimed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS bad_words (
                word TEXT, guild_id TEXT,
                PRIMARY KEY (word, guild_id)
            )"""
        ]
        
        for table in tables:
            c.execute(table)
        
        self.get_conn().commit()
        print("✅ Database ready")

db = Database()

# ═════════════════════════════════════════════════════════════════════════════
# POKEMON DATA - SIMPLE
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
# GUI COMPONENTS - TICKETS
# ═════════════════════════════════════════════════════════════════════════════

class TicketModal(Modal, title="🎫 Create Ticket"):
    reason = TextInput(label="Reason", placeholder="Describe your issue", style=discord.TextStyle.paragraph, required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild, user = interaction.guild, interaction.user
        
        ticket_id = f"ticket-{random.randint(100, 999)}"
        category = discord.utils.get(guild.categories, name="🎫 Tickets")
        if not category:
            category = await guild.create_category("🎫 Tickets")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await guild.create_text_channel(f"🎫-{ticket_id}", category=category, overwrites=overwrites)
        
        db.insert('tickets', {
            'ticket_id': ticket_id,
            'guild_id': str(guild.id),
            'user_id': str(user.id),
            'channel_id': str(channel.id),
            'reason': self.reason.value
        })
        
        embed = discord.Embed(title="🎫 Ticket", description=f"Created by {user.mention}\nReason: {self.reason.value}", color=discord.Color.blue())
        await channel.send(embed=embed)
        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TicketModal())

# ═════════════════════════════════════════════════════════════════════════════
# GUI COMPONENTS - GIVEAWAYS
# ═════════════════════════════════════════════════════════════════════════════

class GiveawayModal(Modal, title="🎁 Create Giveaway"):
    prize = TextInput(label="Prize", placeholder="What are you giving away?", required=True)
    duration = TextInput(label="Duration", placeholder="30s, 5m, 1h, 2d", required=True)
    winners = TextInput(label="Winners", placeholder="1-10", required=True)
    ping_role = TextInput(label="Ping Role ID", placeholder="Optional - Role ID to ping", required=False)
    thumbnail = TextInput(label="Thumbnail URL", placeholder="Optional - Image URL", required=False)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        duration_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        try:
            unit = self.duration.value[-1].lower()
            value = int(self.duration.value[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.followup.send("❌ Invalid duration!", ephemeral=True)
            return
        
        try:
            winners = int(self.winners.value)
            if winners < 1 or winners > 10:
                raise ValueError
        except:
            await interaction.followup.send("❌ Winners must be 1-10!", ephemeral=True)
            return
        
        end_time = datetime.now() + timedelta(seconds=seconds)
        
        embed = discord.Embed(
            title="🎁 GIVEAWAY",
            description=f"**Prize:** {self.prize.value}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
            color=discord.Color.purple()
        )
        
        if self.thumbnail.value:
            embed.set_thumbnail(url=self.thumbnail.value)
        
        message = await interaction.channel.send(embed=embed)
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

# ═════════════════════════════════════════════════════════════════════════════
# MAIN BOT
# ═════════════════════════════════════════════════════════════════════════════

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
        # ─── VERIFICATION ───
        @self.tree.command(name="verify", description="🔐 Verify with Discord")
        async def verify(interaction: discord.Interaction):
            oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds&state={interaction.guild.id}"
            embed = discord.Embed(title="🔐 Verification", description="Click the button to verify.", color=discord.Color.blue())
            view = View()
            view.add_item(Button(label="Verify", url=oauth_url, style=discord.ButtonStyle.success))
            await interaction.response.send_message(embed=embed, view=view)
        
        @self.tree.command(name="setverified", description="Set verified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for verified users")
        async def setverified(interaction: discord.Interaction, role: discord.Role):
            db.execute("INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id) VALUES (?,?)", (str(interaction.guild.id), str(role.id)))
            await interaction.response.send_message(f"✅ Verified role set to {role.mention}")
        
        @self.tree.command(name="setunverified", description="Set unverified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for unverified users")
        async def setunverified(interaction: discord.Interaction, role: discord.Role):
            db.execute("INSERT OR REPLACE INTO guild_settings (guild_id, unverified_role_id) VALUES (?,?)", (str(interaction.guild.id), str(role.id)))
            await interaction.response.send_message(f"✅ Unverified role set to {role.mention}")
        
        # ─── GIVEAWAYS ───
        @self.tree.command(name="giveaway", description="🎁 Start giveaway (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def giveaway(interaction: discord.Interaction):
            await interaction.response.send_modal(GiveawayModal())
        
        # ─── TICKETS ───
        @self.tree.command(name="ticket", description="🎫 Create ticket")
        async def ticket(interaction: discord.Interaction):
            await interaction.response.send_modal(TicketModal())
        
        @self.tree.command(name="setupticket", description="Setup ticket system (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def setupticket(interaction: discord.Interaction):
            embed = discord.Embed(title="🎫 Ticket System", description="Click below to create a ticket.", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed, view=TicketView())
        
        @self.tree.command(name="closeticket", description="🔒 Close ticket")
        async def closeticket(interaction: discord.Interaction):
            ticket = db.fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel!", ephemeral=True)
                return
            await interaction.response.send_message("🔒 Closing in 10 seconds...")
            db.execute("UPDATE tickets SET status='closed', closed_at=? WHERE channel_id=?", (datetime.now().isoformat(), str(interaction.channel.id)))
            await asyncio.sleep(10)
            await interaction.channel.delete()
        
        # ─── POKEMON ───
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
                
                embed = discord.Embed(title="🎉 Caught!", description=f"**{p['name']}** (CP: {cp})", color=discord.Color.gold() if data['is_shiny'] else discord.Color.green())
                await interaction.response.send_message(embed=embed)
            else:
                db.execute("DELETE FROM user_inventory WHERE user_id=? AND guild_id=? AND item_type='pokeball' LIMIT 1", (user_id, guild_id))
                await interaction.response.send_message(f"❌ The {p['name']} escaped!")
        
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
        
        @self.tree.command(name="shop", description="🛒 Shop")
        async def shop(interaction: discord.Interaction):
            user_id, guild_id = str(interaction.user.id), str(interaction.guild.id)
            data = db.fetch_one("SELECT coins FROM pokemon_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            coins = data['coins'] if data else 100
            embed = discord.Embed(title="🛒 Shop", description=f"💰 Coins: {coins}", color=discord.Color.blue())
            embed.add_field(name="🎯 Pokéball (50)", value="1.0x", inline=False)
            embed.add_field(name="🎯 Greatball (100)", value="1.5x", inline=False)
            embed.add_field(name="🎯 Ultraball (200)", value="2.0x", inline=False)
            embed.add_field(name="🎯 Masterball (1000)", value="5.0x", inline=False)
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
            await interaction.response.send_message(f"✅ Setup complete! Spawns in {channel.mention}")
        
        # ─── MODERATION ───
        @self.tree.command(name="ban", description="🔨 Ban member")
        @app_commands.default_permissions(ban_members=True)
        @app_commands.describe(member="Member to ban", reason="Reason")
        async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            try:
                await member.ban(reason=reason)
                await interaction.response.send_message(f"🔨 Banned {member.mention}\nReason: {reason}")
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        @self.tree.command(name="kick", description="👢 Kick member")
        @app_commands.default_permissions(kick_members=True)
        @app_commands.describe(member="Member to kick", reason="Reason")
        async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            try:
                await member.kick(reason=reason)
                await interaction.response.send_message(f"👢 Kicked {member.mention}\nReason: {reason}")
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
                await interaction.response.send_message(f"🔇 Muted {member.mention} for 24h\nReason: {reason}")
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        @self.tree.command(name="unmute", description="🔊 Unmute member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to unmute")
        async def unmute(interaction: discord.Interaction, member: discord.Member):
            try:
                muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
                if muted_role:
                    await member.remove_roles(muted_role)
                db.execute("DELETE FROM muted WHERE user_id=? AND guild_id=?", (str(member.id), str(interaction.guild.id)))
                await interaction.response.send_message(f"🔊 Unmuted {member.mention}")
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        
        @self.tree.command(name="warn", description="⚠️ Warn member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to warn", reason="Reason")
        async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            db.insert('warnings', {'user_id': str(member.id), 'guild_id': str(interaction.guild.id), 'moderator_id': str(interaction.user.id), 'reason': reason})
            warnings = db.count('warnings', {'user_id': str(member.id), 'guild_id': str(interaction.guild.id)})
            await interaction.response.send_message(f"⚠️ Warned {member.mention}\nReason: {reason}\nWarnings: {warnings}/3")
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
            await interaction.response.send_message(f"🗑️ Cleared {len(deleted)} messages!", ephemeral=True)
        
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
        
        # ─── UTILITY ───
        @self.tree.command(name="ping", description="🏓 Check latency")
        async def ping(interaction: discord.Interaction):
            latency = round(self.latency * 1000)
            await interaction.response.send_message(f"🏓 Pong! {latency}ms")
        
        @self.tree.command(name="serverinfo", description="📊 Server info")
        async def serverinfo(interaction: discord.Interaction):
            guild = interaction.guild
            embed = discord.Embed(title=f"📊 {guild.name}", color=discord.Color.blue())
            embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
            embed.add_field(name="📝 Channels", value=len(guild.channels), inline=True)
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
            await interaction.response.send_message(embed=embed)
        
        @self.tree.command(name="list_all", description="📋 All commands")
        async def list_all(interaction: discord.Interaction):
            embed = discord.Embed(title="📋 All Commands", color=discord.Color.blue())
            embed.add_field(name="🎮 Pokémon", value="/catch /collection /shop /buy /daily /poke_setup", inline=False)
            embed.add_field(name="🔐 Verification", value="/verify /setverified /setunverified", inline=False)
            embed.add_field(name="🎁 Giveaways", value="/giveaway", inline=False)
            embed.add_field(name="🎫 Tickets", value="/ticket /setupticket /closeticket", inline=False)
            embed.add_field(name="🛡️ Moderation", value="/ban /kick /mute /unmute /warn /clear /addbadword /removebadword", inline=False)
            embed.add_field(name="🔧 Utility", value="/ping /serverinfo /userinfo /list_all", inline=False)
            await interaction.response.send_message(embed=embed)
    
    # ─── TASKS ───
    @tasks.loop(seconds=30)
    async def spawn_loop(self):
        for guild in self.guilds:
            settings = db.fetch_one("SELECT * FROM pokemon_settings WHERE guild_id=?", (str(guild.id),))
            if settings and settings['spawn_enabled']:
                channel = guild.get_channel(int(settings['channel_id']))
                if channel and random.random() < 0.3:
                    data = get_random_pokemon()
                    p = data['pokemon']
                    embed = discord.Embed(title=f"🌟 Wild {p['name']} appeared!", description=f"Rarity: {data['rarity']}", color=discord.Color.blue())
                    self.active_spawns[str(guild.id)] = {'data': data, 'timestamp': datetime.now(), 'channel_id': channel.id}
                    await channel.send(embed=embed)
    
    @tasks.loop(minutes=1)
    async def giveaway_checker(self):
        now = datetime.now()
        giveaways = db.fetch_all("SELECT * FROM giveaways WHERE ended=0 AND ended_at <= ?", (now.isoformat(),))
        for giveaway in giveaways:
            await self.end_giveaway(giveaway)
    
    async def end_giveaway(self, giveaway):
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
            
            embed = discord.Embed(title="🏆 Giveaway Ended", description=f"**Prize:** {giveaway['prize']}\n**Winners:** {winner_mentions}", color=discord.Color.gold())
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
    
    # ─── EVENTS ───
    async def on_ready(self):
        print("=" * 60)
        print("✅✅✅ BOT IS ONLINE! ✅✅✅")
        print("=" * 60)
        print(f"📡 Name: {self.user.name}")
        print(f"🆔 ID: {self.user.id}")
        print(f"🏰 Servers: {len(self.guilds)}")
        for guild in self.guilds:
            print(f"   - {guild.name} ({guild.id})")
        print("=" * 60)
        print("🎯 Bot is ready!")
    
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
# FLASK APP - FOR OAUTH CALLBACK
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = secrets.token_urlsafe(32)
CORS(flask_app)

@flask_app.route('/')
def index():
    return "🤖 Anion Bot is Online!"

@flask_app.route('/callback')
def oauth_callback():
    code = request.args.get('code')
    guild_id = request.args.get('state')
    
    if not code:
        return "Invalid request", 400
    
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
    
    headers = {'Authorization': f"Bearer {token_data['access_token']}"}
    user_response = requests.get('https://discord.com/api/users/@me', headers=headers)
    user_data = user_response.json()
    
    guilds_response = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
    guilds_data = guilds_response.json()
    
    # Save to database
    if guild_id and user_data.get('id'):
        db.execute(
            "INSERT OR REPLACE INTO verified_users (user_id, guild_id, email, username, guilds_json) VALUES (?, ?, ?, ?, ?)",
            (
                str(user_data['id']),
                guild_id,
                user_data.get('email', ''),
                user_data.get('username', ''),
                json.dumps(guilds_data)
            )
        )
        
        # Assign verified role
        if bot:
            guild = bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_data['id']))
                if member:
                    settings = db.fetch_one("SELECT verified_role_id FROM guild_settings WHERE guild_id=?", (guild_id,))
                    if settings and settings['verified_role_id']:
                        role = guild.get_role(int(settings['verified_role_id']))
                        if role:
                            asyncio.run_coroutine_threadsafe(member.add_roles(role), bot.loop)
    
    return f"""
    <html><body style="text-align:center;padding:50px;font-family:Arial;">
    <h1>✅ Verification Complete!</h1>
    <p>Welcome {user_data.get('username', 'User')}!</p>
    <p>You have been verified. You can close this window.</p>
    </body></html>
    """

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

bot = None

def run_flask():
    flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)

async def main():
    global bot
    print("🚀 Starting Anion Bot...")
    
    # Start Flask
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("🌐 Flask started")
    
    # Start bot
    bot = AnionBot()
    await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
