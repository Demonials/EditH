#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════
                    🔐 ANION PROJECT - COMPLETE BOT
                    Railway Deployment Ready
                    ALL SLASH COMMANDS + GUI FEATURES
═══════════════════════════════════════════════════════════════════
"""

# ═══════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════

import os
import sys
import json
import random
import asyncio
import sqlite3
import secrets
import requests
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple

# Discord
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput

# Flask
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_cors import CORS

# Music
import yt_dlp

# AI
import openai

# Environment
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════════════
# LOAD ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════════

load_dotenv()

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

class Config:
    def __init__(self):
        # Required - Will raise error if missing
        self.DISCORD_TOKEN = self.get_required('DISCORD_TOKEN')
        self.CLIENT_ID = self.get_required('CLIENT_ID')
        self.CLIENT_SECRET = self.get_required('CLIENT_SECRET')
        
        # Optional with defaults
        self.REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://verifier.up.railway.app/callback')
        self.DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://verifier.up.railway.app/dashboard')
        self.FLASK_SECRET = os.getenv('FLASK_SECRET', secrets.token_urlsafe(32))
        self.OPENAI_KEY = os.getenv('OPENAI_KEY', '')
        self.DB_PATH = os.getenv('DB_PATH', '/data')
        
        # Ensure DB path exists
        os.makedirs(self.DB_PATH, exist_ok=True)
        self.DB_FILE = os.path.join(self.DB_PATH, 'bot_database.db')
        
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
        
        # Bot settings
        self.SPAWN_INTERVAL = int(os.getenv('SPAWN_INTERVAL', '30'))
        self.LEGENDARY_SPAWN_INTERVAL = int(os.getenv('LEGENDARY_SPAWN_INTERVAL', '14400'))
        
        print(f"✅ Config loaded - Environment: {self.ENVIRONMENT}")
    
    def get_required(self, key):
        value = os.getenv(key)
        if not value:
            raise ValueError(f"❌ Missing required env: {key}")
        return value

config = Config()

# ═══════════════════════════════════════════════════════════════════
# DATABASE CLASS
# ═══════════════════════════════════════════════════════════════════

class Database:
    def __init__(self):
        self.db_file = config.DB_FILE
        self.connection = None
        self.cursor = None
        self.init_database()
    
    def get_connection(self):
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_file)
            self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
        return self.connection
    
    def close_connection(self):
        if self.connection:
            self.connection.close()
            self.connection = None
            self.cursor = None
    
    def init_database(self):
        conn = self.get_connection()
        c = conn.cursor()
        
        # All tables
        tables = [
            """CREATE TABLE IF NOT EXISTS pokemon_users (
                user_id TEXT, guild_id TEXT,
                coins INTEGER DEFAULT 100,
                catches INTEGER DEFAULT 0,
                total_cp INTEGER DEFAULT 0,
                legendary_catches INTEGER DEFAULT 0,
                shiny_catches INTEGER DEFAULT 0,
                last_daily TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, guild_id TEXT,
                pokemon_name TEXT, pokemon_id INTEGER,
                cp INTEGER, rarity TEXT,
                shiny BOOLEAN DEFAULT 0,
                caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                for_sale BOOLEAN DEFAULT 0,
                sale_price INTEGER DEFAULT 0,
                listing_id TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_pokedex (
                user_id TEXT, guild_id TEXT,
                pokemon_id INTEGER,
                seen BOOLEAN DEFAULT 0,
                caught BOOLEAN DEFAULT 0,
                PRIMARY KEY (user_id, guild_id, pokemon_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_settings (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT,
                spawn_enabled BOOLEAN DEFAULT 1,
                catch_cooldown INTEGER DEFAULT 30
            )""",
            
            """CREATE TABLE IF NOT EXISTS user_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, guild_id TEXT,
                item_id TEXT, item_type TEXT,
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, guild_id, item_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                verified_role_id TEXT,
                unverified_role_id TEXT,
                log_channel_id TEXT,
                welcome_channel_id TEXT,
                goodbye_channel_id TEXT,
                welcome_message TEXT,
                goodbye_message TEXT,
                auto_verify BOOLEAN DEFAULT 0
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
            
            """CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE,
                guild_id TEXT, user_id TEXT,
                channel_id TEXT, status TEXT DEFAULT 'open',
                reason TEXT, claimed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS muted (
                user_id TEXT, guild_id TEXT,
                muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unmute_at TIMESTAMP, reason TEXT,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS verified_users (
                user_id TEXT, guild_id TEXT,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email TEXT,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS verify_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT, guild_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used BOOLEAN DEFAULT 0
            )""",
            
            """CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT, channel_id TEXT,
                guild_id TEXT, prize TEXT,
                winners INTEGER DEFAULT 1,
                ended BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                winner_ids TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS bad_words (
                word TEXT, guild_id TEXT,
                PRIMARY KEY (word, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS music_queue (
                guild_id TEXT PRIMARY KEY,
                queue_json TEXT,
                current_song_json TEXT
            )"""
        ]
        
        for table in tables:
            c.execute(table)
        
        conn.commit()
        self.close_connection()
    
    def execute(self, query, params=()):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        return c
    
    def fetch_one(self, query, params=()):
        c = self.execute(query, params)
        return c.fetchone()
    
    def fetch_all(self, query, params=()):
        c = self.execute(query, params)
        return c.fetchall()
    
    def insert(self, table, data):
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        self.execute(query, list(data.values()))
    
    def update(self, table, data, where):
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        where_clause = ' AND '.join([f"{k} = ?" for k in where.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        self.execute(query, list(data.values()) + list(where.values()))

# ═══════════════════════════════════════════════════════════════════
# POKEMON DATA
# ═══════════════════════════════════════════════════════════════════

class PokemonData:
    def __init__(self):
        self.pokemon_list = []
        self.rarities = {
            'Common': {'weight': 50, 'catch_rate': 0.8, 'emoji': '⬜', 'color': 0x808080},
            'Uncommon': {'weight': 25, 'catch_rate': 0.6, 'emoji': '🟩', 'color': 0x00FF00},
            'Rare': {'weight': 15, 'catch_rate': 0.4, 'emoji': '🟦', 'color': 0x0000FF},
            'Legendary': {'weight': 8, 'catch_rate': 0.2, 'emoji': '🌟', 'color': 0xFFD700},
            'Mythical': {'weight': 2, 'catch_rate': 0.1, 'emoji': '💫', 'color': 0xFF69B4}
        }
        self.ball_multipliers = {
            'pokeball': 1.0, 'greatball': 1.5, 
            'ultraball': 2.0, 'masterball': 5.0
        }
        self.ball_prices = {
            'pokeball': 50, 'greatball': 100, 
            'ultraball': 200, 'masterball': 1000
        }
        self.load_pokemon_data()
    
    def load_pokemon_data(self):
        try:
            # Try cache first
            cache_file = os.path.join(config.DB_PATH, 'pokemon_cache.json')
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    self.pokemon_list = json.load(f)
            else:
                self.fetch_from_api()
        except Exception as e:
            print(f"⚠️ Error loading Pokémon: {e}")
            self.pokemon_list = self.get_fallback_data()
    
    def fetch_from_api(self):
        try:
            # Fetch first 151 for speed
            response = requests.get(f'{config.POKEAPI_BASE}/pokemon?limit=151')
            data = response.json()
            
            for pokemon in data['results']:
                detail = requests.get(pokemon['url']).json()
                total_stats = sum(s['base_stat'] for s in detail['stats'])
                
                if total_stats > 600:
                    rarity = 'Mythical'
                elif total_stats > 530:
                    rarity = 'Legendary'
                elif total_stats > 450:
                    rarity = 'Rare'
                elif total_stats > 350:
                    rarity = 'Uncommon'
                else:
                    rarity = 'Common'
                
                self.pokemon_list.append({
                    'id': detail['id'],
                    'name': detail['name'].capitalize(),
                    'types': [t['type']['name'] for t in detail['types']],
                    'total_stats': total_stats,
                    'rarity': rarity,
                    'sprite_url': detail['sprites']['front_default']
                })
            
            # Cache for later
            cache_file = os.path.join(config.DB_PATH, 'pokemon_cache.json')
            with open(cache_file, 'w') as f:
                json.dump(self.pokemon_list, f)
                
        except Exception as e:
            print(f"⚠️ API fetch failed: {e}")
            self.pokemon_list = self.get_fallback_data()
    
    def get_fallback_data(self):
        return [
            {'id': 1, 'name': 'Bulbasaur', 'rarity': 'Common', 'total_stats': 318},
            {'id': 4, 'name': 'Charmander', 'rarity': 'Common', 'total_stats': 309},
            {'id': 7, 'name': 'Squirtle', 'rarity': 'Common', 'total_stats': 314},
            {'id': 25, 'name': 'Pikachu', 'rarity': 'Uncommon', 'total_stats': 320},
            {'id': 150, 'name': 'Mewtwo', 'rarity': 'Legendary', 'total_stats': 680},
            {'id': 151, 'name': 'Mew', 'rarity': 'Mythical', 'total_stats': 600},
        ]
    
    def get_random_pokemon(self):
        rarity = self.get_rarity()
        eligible = [p for p in self.pokemon_list if p['rarity'] == rarity]
        if not eligible:
            eligible = self.pokemon_list
        return random.choice(eligible)
    
    def get_rarity(self):
        choices = []
        for rarity, data in self.rarities.items():
            choices.extend([rarity] * data['weight'])
        return random.choice(choices)
    
    def get_pokemon_by_name(self, name):
        name = name.lower().capitalize()
        for p in self.pokemon_list:
            if p['name'].lower() == name.lower():
                return p
        return None
    
    def get_legendary(self):
        legendaries = [p for p in self.pokemon_list if p['rarity'] in ['Legendary', 'Mythical']]
        return random.choice(legendaries) if legendaries else self.get_random_pokemon()

# ═══════════════════════════════════════════════════════════════════
# BEAUTIFUL GUI COMPONENTS
# ═══════════════════════════════════════════════════════════════════

class TicketView(View):
    """Beautiful ticket creation view with GUI"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket", emoji="🎫")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        """Open ticket creation modal"""
        modal = TicketModal()
        await interaction.response.send_modal(modal)

class TicketModal(Modal, title="🎫 Create Support Ticket"):
    """Beautiful ticket creation modal"""
    reason = TextInput(
        label="Reason for ticket",
        placeholder="Briefly describe your issue...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    
    priority = TextInput(
        label="Priority (Optional)",
        placeholder="Low / Medium / High",
        required=False,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        user = interaction.user
        
        # Check existing ticket
        existing = interaction.client.db.fetch_one(
            "SELECT * FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'",
            (str(user.id), str(guild.id))
        )
        
        if existing:
            await interaction.followup.send(
                "❌ You already have an open ticket! Please close it first.",
                ephemeral=True
            )
            return
        
        # Create ticket channel
        ticket_id = f"ticket-{random.randint(100, 999)}"
        category = discord.utils.get(guild.categories, name="🎫 Tickets")
        if not category:
            category = await guild.create_category("🎫 Tickets")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add support team roles
        for role_name in ['Admin', 'Moderator', 'Support']:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            f"🎫-{ticket_id}",
            category=category,
            overwrites=overwrites,
            topic=f"Ticket by {user.display_name} | Priority: {self.priority.value or 'Medium'}"
        )
        
        # Save to DB
        interaction.client.db.insert('tickets', {
            'ticket_id': ticket_id,
            'guild_id': str(guild.id),
            'user_id': str(user.id),
            'channel_id': str(channel.id),
            'reason': self.reason.value
        })
        
        # Beautiful embed
        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"**Created by:** {user.mention}\n"
                       f"**Reason:** {self.reason.value}\n"
                       f"**Priority:** {self.priority.value or 'Medium'}",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Ticket ID: {ticket_id}")
        
        # Ticket controls
        view = TicketControlsView(ticket_id, user.id)
        
        await channel.send(
            f"{user.mention} Support team has been notified!",
            embed=embed,
            view=view
        )
        
        await interaction.followup.send(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

class TicketControlsView(View):
    """Beautiful ticket control buttons"""
    def __init__(self, ticket_id: str, user_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user_id = user_id
    
    @discord.ui.button(label="➕ Add User", style=discord.ButtonStyle.success, custom_id="ticket_add_user", emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: Button):
        """Add user to ticket"""
        modal = AddUserModal(self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Remove User", style=discord.ButtonStyle.danger, custom_id="ticket_remove_user", emoji="➖")
    async def remove_user(self, interaction: discord.Interaction, button: Button):
        """Remove user from ticket"""
        modal = RemoveUserModal(self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📝 Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript", emoji="📝")
    async def transcript(self, interaction: discord.Interaction, button: Button):
        """Generate ticket transcript"""
        await interaction.response.defer()
        
        messages = []
        async for msg in interaction.channel.history(limit=100):
            messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.display_name}: {msg.content}")
        
        transcript = "\n".join(reversed(messages))
        
        # Save transcript
        transcript_file = discord.File(
            io.StringIO(transcript),
            filename=f"transcript-{self.ticket_id}.txt"
        )
        
        await interaction.followup.send(
            "📝 Transcript generated:",
            file=transcript_file,
            ephemeral=True
        )
    
    @discord.ui.button(label="⏰ Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim", emoji="⏰")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        """Claim ticket"""
        await interaction.response.defer()
        
        # Check if already claimed
        ticket = interaction.client.db.fetch_one(
            "SELECT * FROM tickets WHERE ticket_id = ?",
            (self.ticket_id,)
        )
        
        if ticket and ticket['claimed_by']:
            await interaction.followup.send(
                f"❌ This ticket is already claimed by <@{ticket['claimed_by']}>",
                ephemeral=True
            )
            return
        
        # Claim ticket
        interaction.client.db.update(
            'tickets',
            {'claimed_by': str(interaction.user.id)},
            {'ticket_id': self.ticket_id}
        )
        
        embed = discord.Embed(
            title="⏰ Ticket Claimed",
            description=f"Ticket claimed by {interaction.user.mention}",
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Ticket claimed!", ephemeral=True)
    
    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="ticket_close", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        """Close ticket"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🔒 Closing Ticket",
            description=f"Ticket will be closed in 10 seconds.",
            color=discord.Color.orange()
        )
        await interaction.channel.send(embed=embed)
        
        # Update DB
        interaction.client.db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ? WHERE ticket_id = ?",
            (datetime.now().isoformat(), self.ticket_id)
        )
        
        await asyncio.sleep(10)
        await interaction.channel.delete()

class AddUserModal(Modal, title="➕ Add User to Ticket"):
    user_id = TextInput(
        label="User ID or Mention",
        placeholder="Enter the user's ID or mention them",
        required=True
    )
    
    def __init__(self, ticket_id: str):
        super().__init__()
        self.ticket_id = ticket_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse user ID from mention or ID
            user_id = self.user_id.value.replace('<@', '').replace('>', '').replace('!', '')
            user = interaction.guild.get_member(int(user_id))
            
            if not user:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
                return
            
            # Add user to channel
            await interaction.channel.set_permissions(
                user,
                read_messages=True,
                send_messages=True,
                attach_files=True
            )
            
            await interaction.response.send_message(
                f"✅ Added {user.mention} to the ticket!",
                ephemeral=True
            )
            await interaction.channel.send(f"👋 {user.mention} was added to the ticket by {interaction.user.mention}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

class RemoveUserModal(Modal, title="➖ Remove User from Ticket"):
    user_id = TextInput(
        label="User ID or Mention",
        placeholder="Enter the user's ID or mention them",
        required=True
    )
    
    def __init__(self, ticket_id: str):
        super().__init__()
        self.ticket_id = ticket_id
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = self.user_id.value.replace('<@', '').replace('>', '').replace('!', '')
            user = interaction.guild.get_member(int(user_id))
            
            if not user:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
                return
            
            # Check if user is the ticket creator
            ticket = interaction.client.db.fetch_one(
                "SELECT user_id FROM tickets WHERE ticket_id = ?",
                (self.ticket_id,)
            )
            
            if ticket and str(user.id) == ticket['user_id']:
                await interaction.response.send_message(
                    "❌ Cannot remove the ticket creator!",
                    ephemeral=True
                )
                return
            
            # Remove user from channel
            await interaction.channel.set_permissions(
                user,
                read_messages=False,
                send_messages=False
            )
            
            await interaction.response.send_message(
                f"✅ Removed {user.mention} from the ticket!",
                ephemeral=True
            )
            await interaction.channel.send(f"👋 {user.mention} was removed from the ticket by {interaction.user.mention}")
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# ──────────────────────────────────────────────────────────────────
# GIVEAWAY GUI COMPONENTS
# ──────────────────────────────────────────────────────────────────

class GiveawayView(View):
    """Beautiful giveaway view"""
    def __init__(self, message_id: str, giveaway_id: int, winners: int):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.giveaway_id = giveaway_id
        self.winners = winners
    
    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="enter_giveaway", emoji="🎉")
    async def enter_giveaway(self, interaction: discord.Interaction, button: Button):
        """Enter the giveaway"""
        await interaction.response.defer(ephemeral=True)
        
        # Check if user already entered
        # Using reactions as entry mechanism
        message = await interaction.channel.fetch_message(int(self.message_id))
        await message.add_reaction("🎉")
        
        await interaction.followup.send("✅ You've entered the giveaway!", ephemeral=True)

class GiveawayCreatorModal(Modal, title="🎁 Create Giveaway"):
    prize = TextInput(
        label="Prize",
        placeholder="What are you giving away?",
        required=True,
        max_length=100
    )
    
    duration = TextInput(
        label="Duration",
        placeholder="30s, 5m, 1h, 2d, 7d",
        required=True,
        max_length=10
    )
    
    winners = TextInput(
        label="Winners",
        placeholder="Number of winners (1-10)",
        required=True,
        max_length=2
    )
    
    description = TextInput(
        label="Description (Optional)",
        placeholder="Additional details about the giveaway...",
        required=False,
        max_length=200,
        style=discord.TextStyle.paragraph
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # Parse duration
        duration_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        try:
            unit = self.duration.value[-1].lower()
            value = int(self.duration.value[:-1])
            seconds = value * duration_map[unit]
        except:
            await interaction.followup.send(
                "❌ Invalid duration! Use: 30s, 5m, 1h, 2d, 7d",
                ephemeral=True
            )
            return
        
        if seconds > 7 * 86400:
            await interaction.followup.send("❌ Giveaway can't be longer than 7 days!", ephemeral=True)
            return
        
        try:
            winners = int(self.winners.value)
            if winners < 1 or winners > 10:
                raise ValueError
        except:
            await interaction.followup.send("❌ Winners must be between 1 and 10!", ephemeral=True)
            return
        
        end_time = datetime.now() + timedelta(seconds=seconds)
        
        # Create beautiful embed
        embed = discord.Embed(
            title="🎁 GIVEAWAY",
            description=f"**Prize:** {self.prize.value}\n"
                       f"**Winners:** {winners}\n"
                       f"**Ends:** <t:{int(end_time.timestamp())}:R>\n"
                       f"**Hosted by:** {interaction.user.mention}",
            color=discord.Color.purple()
        )
        
        if self.description.value:
            embed.add_field(name="📝 Description", value=self.description.value, inline=False)
        
        embed.set_footer(text=f"🎉 React or click below to enter!")
        
        # Send message with view
        view = GiveawayView(message_id="placeholder", giveaway_id=0, winners=winners)
        message = await interaction.channel.send(embed=embed, view=view)
        
        # Save to DB
        db = interaction.client.db
        db.insert('giveaways', {
            'message_id': str(message.id),
            'channel_id': str(interaction.channel.id),
            'guild_id': str(interaction.guild.id),
            'prize': self.prize.value,
            'winners': winners,
            'ended_at': end_time.isoformat()
        })
        
        await interaction.followup.send(
            f"✅ Giveaway started! Ends in {self.duration.value}",
            ephemeral=True
        )
        
        # Schedule end
        asyncio.create_task(self.end_giveaway_later(interaction.client, message.id, winners))
    
    async def end_giveaway_later(self, bot, message_id: int, winners: int):
        await asyncio.sleep(10)  # In production, use proper duration
        # This would be handled by a task loop in production

# ═══════════════════════════════════════════════════════════════════
# MAIN BOT CLASS
# ═══════════════════════════════════════════════════════════════════

class AnionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        
        self.db = Database()
        self.pokemon_data = PokemonData()
        self.active_spawns = {}
        self.message_cache = {}
        self.voice_clients = {}
        self.level_cooldowns = {}
        
        if config.OPENAI_KEY:
            openai.api_key = config.OPENAI_KEY
        
        # Start tasks
        self.spawn_loop.start()
        self.cleanup_loop.start()
        self.giveaway_checker.start()
    
    async def setup_hook(self):
        """Sync commands when bot starts"""
        await self.tree.sync()
        print(f'✅ Commands synced!')
    
    async def on_ready(self):
        print(f'✅ Bot is ready! Logged in as {self.user}')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Pokémon | /help"
            )
        )
    
    # ──────────────────────────────────────────────────────────────
    # TASKS
    # ──────────────────────────────────────────────────────────────
    
    @tasks.loop(seconds=30)
    async def spawn_loop(self):
        for guild in self.guilds:
            settings = self.db.fetch_one(
                "SELECT * FROM pokemon_settings WHERE guild_id = ?",
                (str(guild.id),)
            )
            
            if settings and settings['spawn_enabled']:
                channel = guild.get_channel(int(settings['channel_id']))
                if channel and random.random() < 0.3:
                    pokemon = self.pokemon_data.get_random_pokemon()
                    await self.spawn_pokemon_message(channel, pokemon)
    
    @tasks.loop(minutes=10)
    async def giveaway_checker(self):
        """Check and end giveaways"""
        now = datetime.now()
        giveaways = self.db.fetch_all(
            "SELECT * FROM giveaways WHERE ended = 0 AND ended_at <= ?",
            (now.isoformat(),)
        )
        
        for giveaway in giveaways:
            await self.end_giveaway(giveaway)
    
    @tasks.loop(hours=1)
    async def cleanup_loop(self):
        """Cleanup old data"""
        self.db.execute(
            "DELETE FROM tickets WHERE status = 'closed' AND closed_at < datetime('now', '-7 days')"
        )
        self.db.execute(
            "DELETE FROM giveaways WHERE ended = 1 AND ended_at < datetime('now', '-30 days')"
        )
    
    # ──────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────
    
    async def spawn_pokemon_message(self, channel, pokemon):
        embed = discord.Embed(
            title=f"🌟 A wild {pokemon['name']} appeared!",
            description=f"Rarity: {pokemon['rarity']}",
            color=discord.Color.gold() if pokemon['rarity'] in ['Legendary', 'Mythical'] else discord.Color.blue()
        )
        if pokemon.get('sprite_url'):
            embed.set_image(url=pokemon['sprite_url'])
        embed.set_footer(text="Use /catch to try and catch it!")
        
        self.active_spawns[str(channel.guild.id)] = {
            'pokemon': pokemon,
            'timestamp': datetime.now(),
            'channel_id': channel.id
        }
        
        await channel.send(embed=embed)
    
    async def end_giveaway(self, giveaway):
        """End a giveaway and pick winners"""
        channel = self.get_channel(int(giveaway['channel_id']))
        if not channel:
            return
        
        try:
            message = await channel.fetch_message(int(giveaway['message_id']))
            reaction = discord.utils.get(message.reactions, emoji="🎉")
            
            if reaction:
                users = []
                async for user in reaction.users():
                    if not user.bot:
                        users.append(user)
                
                winners_count = min(giveaway['winners'], len(users))
                winners = random.sample(users, winners_count) if users else []
                
                winner_mentions = ', '.join([w.mention for w in winners]) if winners else "No valid entries!"
                
                # Update embed
                embed = discord.Embed(
                    title="🏆 GIVEAWAY ENDED",
                    description=f"**Prize:** {giveaway['prize']}\n**Winners:** {winner_mentions}",
                    color=discord.Color.gold()
                )
                
                await message.edit(embed=embed, view=None)
                await channel.send(f"🎉 **Giveaway Ended!**\nWinners: {winner_mentions}")
                
                # Update DB
                self.db.execute(
                    "UPDATE giveaways SET ended = 1, winner_ids = ? WHERE id = ?",
                    (','.join([str(w.id) for w in winners]), giveaway['id'])
                )
        except Exception as e:
            print(f"⚠️ Error ending giveaway: {e}")
    
    # ──────────────────────────────────────────────────────────────
    # EVENTS
    # ──────────────────────────────────────────────────────────────
    
    async def on_member_join(self, member):
        settings = self.db.fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (str(member.guild.id),)
        )
        
        if settings:
            if settings['unverified_role_id']:
                role = member.guild.get_role(int(settings['unverified_role_id']))
                if role:
                    await member.add_roles(role)
            
            if settings['welcome_channel_id']:
                channel = member.guild.get_channel(int(settings['welcome_channel_id']))
                if channel:
                    msg = settings['welcome_message'] or f"👋 Welcome {member.mention} to **{member.guild.name}**!"
                    await channel.send(msg)
    
    async def on_member_remove(self, member):
        settings = self.db.fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (str(member.guild.id),)
        )
        
        if settings and settings['goodbye_channel_id']:
            channel = member.guild.get_channel(int(settings['goodbye_channel_id']))
            if channel:
                msg = settings['goodbye_message'] or f"👋 {member.display_name} has left the server."
                await channel.send(msg)
    
    async def on_message(self, message):
        if message.author.bot:
            return
        
        # Anti-spam
        await self.handle_antispam(message)
        
        # Bad words
        await self.handle_bad_words(message)
        
        # Leveling
        await self.handle_leveling(message)
        
        await self.process_commands(message)
    
    async def handle_antispam(self, message):
        key = f"{message.guild.id}:{message.author.id}"
        now = datetime.now()
        
        if key not in self.message_cache:
            self.message_cache[key] = [now]
        else:
            self.message_cache[key] = [t for t in self.message_cache[key] if (now - t).seconds < 5]
            self.message_cache[key].append(now)
            
            if len(self.message_cache[key]) >= 5:
                await self.mute_user(message.guild, message.author, "Auto-muted for spamming")
                await message.delete()
                await message.channel.send(f"🔇 {message.author.mention} has been auto-muted for spamming!")
    
    async def handle_bad_words(self, message):
        bad_words = self.db.fetch_all(
            "SELECT word FROM bad_words WHERE guild_id = ?",
            (str(message.guild.id),)
        )
        
        content = message.content.lower()
        for row in bad_words:
            if row['word'].lower() in content:
                await message.delete()
                await message.channel.send(f"❌ {message.author.mention}, that word is not allowed!")
                break
    
    async def handle_leveling(self, message):
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        cooldown_key = f"{guild_id}:{user_id}"
        if cooldown_key in self.level_cooldowns:
            if (datetime.now() - self.level_cooldowns[cooldown_key]).seconds < 30:
                return
        
        self.level_cooldowns[cooldown_key] = datetime.now()
        
        xp_gain = random.randint(15, 25)
        self.db.execute(
            """INSERT INTO levels (user_id, guild_id, xp, messages) 
               VALUES (?, ?, ?, 1) 
               ON CONFLICT(user_id, guild_id) 
               DO UPDATE SET xp = xp + ?, messages = messages + 1""",
            (user_id, guild_id, xp_gain, xp_gain)
        )
        
        level_data = self.db.fetch_one(
            "SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        
        if level_data:
            xp = level_data['xp']
            level = level_data['level']
            next_xp = 100 * (level + 1) ** 2
            
            if xp >= next_xp:
                new_level = level + 1
                self.db.execute(
                    "UPDATE levels SET level = ? WHERE user_id = ? AND guild_id = ?",
                    (new_level, user_id, guild_id)
                )
                await message.channel.send(f"🎉 {message.author.mention} leveled up to **Level {new_level}**!")
    
    async def mute_user(self, guild, member, reason):
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if not muted_role:
            muted_role = await guild.create_role(
                name="Muted",
                permissions=discord.Permissions(send_messages=False, add_reactions=False)
            )
            for channel in guild.channels:
                await channel.set_permissions(muted_role, send_messages=False, add_reactions=False)
        
        await member.add_roles(muted_role)
        
        unmute_time = datetime.now() + timedelta(hours=24)
        self.db.insert('muted', {
            'user_id': str(member.id),
            'guild_id': str(guild.id),
            'reason': reason,
            'unmute_at': unmute_time.isoformat()
        })
    
    async def unmute_user(self, guild, member):
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if muted_role and muted_role in member.roles:
            await member.remove_roles(muted_role)
        
        self.db.execute(
            "DELETE FROM muted WHERE user_id = ? AND guild_id = ?",
            (str(member.id), str(guild.id))
        )

# ═══════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ═══════════════════════════════════════════════════════════════════

# Global bot instance
bot = None

# ──────────────────────────────────────────────────────────────────
# POKEMON COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="catch", description="🎮 Try to catch a wild Pokémon!")
async def catch(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    # Check pokeballs
    balls = bot.db.fetch_all(
        "SELECT * FROM user_inventory WHERE user_id = ? AND guild_id = ? AND item_type = 'pokeball'",
        (user_id, guild_id)
    )
    
    if not balls:
        await interaction.response.send_message(
            "❌ You don't have any Pokéballs! Buy some with `/shop`",
            ephemeral=True
        )
        return
    
    # Check spawn
    if guild_id not in bot.active_spawns:
        await interaction.response.send_message(
            "🌿 No wild Pokémon nearby! Wait for one to spawn.",
            ephemeral=True
        )
        return
    
    spawn = bot.active_spawns[guild_id]
    if (datetime.now() - spawn['timestamp']).seconds > 60:
        del bot.active_spawns[guild_id]
        await interaction.response.send_message("🏃 The wild Pokémon ran away!", ephemeral=True)
        return
    
    pokemon = spawn['pokemon']
    ball_multiplier = 1.0
    
    for ball in balls:
        if ball['item_id'] == 'greatball':
            ball_multiplier = 1.5
        elif ball['item_id'] == 'ultraball':
            ball_multiplier = 2.0
        elif ball['item_id'] == 'masterball':
            ball_multiplier = 5.0
    
    rarity_data = bot.pokemon_data.rarities.get(pokemon['rarity'], {'catch_rate': 0.5})
    catch_rate = rarity_data['catch_rate'] * ball_multiplier
    is_shiny = random.random() < 0.02
    
    caught = random.random() < catch_rate
    
    if caught:
        cp = random.randint(100, 500)
        if is_shiny:
            cp *= 1.5
        
        # Save to DB
        bot.db.insert('pokemon_collection', {
            'user_id': user_id,
            'guild_id': guild_id,
            'pokemon_name': pokemon['name'],
            'pokemon_id': pokemon['id'],
            'cp': int(cp),
            'rarity': pokemon['rarity'],
            'shiny': 1 if is_shiny else 0
        })
        
        bot.db.execute(
            """INSERT INTO pokemon_users (user_id, guild_id, catches, total_cp) 
               VALUES (?, ?, 1, ?) 
               ON CONFLICT(user_id, guild_id) 
               DO UPDATE SET catches = catches + 1, total_cp = total_cp + ?""",
            (user_id, guild_id, int(cp), int(cp))
        )
        
        if is_shiny:
            bot.db.execute(
                "UPDATE pokemon_users SET shiny_catches = shiny_catches + 1 WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
        
        if pokemon['rarity'] in ['Legendary', 'Mythical']:
            bot.db.execute(
                "UPDATE pokemon_users SET legendary_catches = legendary_catches + 1 WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
        
        # Remove one pokeball
        bot.db.execute(
            "DELETE FROM user_inventory WHERE user_id = ? AND guild_id = ? AND item_type = 'pokeball' LIMIT 1",
            (user_id, guild_id)
        )
        
        del bot.active_spawns[guild_id]
        
        embed = discord.Embed(
            title="🎉 Pokémon Caught!",
            description=f"**{pokemon['name']}** (CP: {int(cp)})",
            color=discord.Color.gold() if is_shiny else discord.Color.green()
        )
        if is_shiny:
            embed.add_field(name="✨ SHINY!", value="⭐ Rare shiny Pokémon!", inline=False)
        embed.add_field(name="Rarity", value=pokemon['rarity'], inline=True)
        embed.add_field(name="Ball Used", value=balls[0]['item_id'].capitalize(), inline=True)
        
        await interaction.response.send_message(embed=embed)
    else:
        # Remove one pokeball even on fail
        bot.db.execute(
            "DELETE FROM user_inventory WHERE user_id = ? AND guild_id = ? AND item_type = 'pokeball' LIMIT 1",
            (user_id, guild_id)
        )
        await interaction.response.send_message(
            f"❌ The **{pokemon['name']}** escaped! Try a better ball!"
        )

@bot.tree.command(name="collection", description="📊 View your Pokémon collection")
async def collection(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    collection = bot.db.fetch_all(
        "SELECT * FROM pokemon_collection WHERE user_id = ? AND guild_id = ? ORDER BY cp DESC LIMIT 25",
        (user_id, guild_id)
    )
    
    if not collection:
        await interaction.response.send_message(
            "📭 You haven't caught any Pokémon yet! Use `/catch` to start.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title=f"📊 {interaction.user.display_name}'s Pokémon Collection",
        color=discord.Color.gold()
    )
    
    for p in collection[:20]:
        shiny = "✨ " if p['shiny'] else ""
        embed.add_field(
            name=f"{shiny}{p['pokemon_name']}",
            value=f"CP: {p['cp']} | Rarity: {p['rarity']}",
            inline=True
        )
    
    embed.set_footer(text=f"Total: {len(collection)} Pokémon")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="shop", description="🛒 View the Pokémon shop")
async def shop(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    user_data = bot.db.fetch_one(
        "SELECT coins FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    coins = user_data['coins'] if user_data else 100
    
    embed = discord.Embed(
        title="🛒 Pokémon Shop",
        description=f"💰 Your coins: **{coins}**",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎯 Pokéball (50 coins)",
        value="1.0x catch multiplier",
        inline=False
    )
    embed.add_field(
        name="🎯 Greatball (100 coins)",
        value="1.5x catch multiplier",
        inline=False
    )
    embed.add_field(
        name="🎯 Ultraball (200 coins)",
        value="2.0x catch multiplier",
        inline=False
    )
    embed.add_field(
        name="🎯 Masterball (1000 coins)",
        value="5.0x catch multiplier",
        inline=False
    )
    embed.set_footer(text="Use /buy <item> to purchase")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="🛒 Buy an item from the shop")
@app_commands.describe(item="Item to buy (pokeball, greatball, ultraball, masterball)")
async def buy(interaction: discord.Interaction, item: str):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    item_prices = {'pokeball': 50, 'greatball': 100, 'ultraball': 200, 'masterball': 1000}
    item = item.lower()
    
    if item not in item_prices:
        await interaction.response.send_message(
            "❌ Invalid item! Available: pokeball, greatball, ultraball, masterball",
            ephemeral=True
        )
        return
    
    price = item_prices[item]
    user_data = bot.db.fetch_one(
        "SELECT coins FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    coins = user_data['coins'] if user_data else 100
    
    if coins < price:
        await interaction.response.send_message(
            f"❌ You need {price} coins! You have {coins}.",
            ephemeral=True
        )
        return
    
    bot.db.execute(
        "UPDATE pokemon_users SET coins = coins - ? WHERE user_id = ? AND guild_id = ?",
        (price, user_id, guild_id)
    )
    
    bot.db.insert('user_inventory', {
        'user_id': user_id,
        'guild_id': guild_id,
        'item_id': item,
        'item_type': 'pokeball',
        'quantity': 1
    })
    
    await interaction.response.send_message(
        f"✅ Purchased **{item.capitalize()}** for {price} coins!"
    )

@bot.tree.command(name="daily", description="🎁 Claim your daily bonus")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    user_data = bot.db.fetch_one(
        "SELECT * FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    if user_data and user_data['last_daily']:
        last = datetime.fromisoformat(user_data['last_daily'])
        if (datetime.now() - last).days < 1:
            remaining = timedelta(days=1) - (datetime.now() - last)
            await interaction.response.send_message(
                f"⏳ Come back in {remaining.seconds//3600}h {(remaining.seconds%3600)//60}m!",
                ephemeral=True
            )
            return
    
    coins = random.randint(50, 200)
    bonus_pokemon = random.random() < 0.1
    
    bot.db.execute(
        """INSERT INTO pokemon_users (user_id, guild_id, coins, last_daily) 
           VALUES (?, ?, ?, ?) 
           ON CONFLICT(user_id, guild_id) 
           DO UPDATE SET coins = coins + ?, last_daily = ?""",
        (user_id, guild_id, coins, datetime.now().isoformat(), coins, datetime.now().isoformat())
    )
    
    response = f"🎁 Daily bonus claimed! +{coins} coins!"
    
    if bonus_pokemon:
        pokemon = bot.pokemon_data.get_random_pokemon()
        cp = random.randint(50, 300)
        bot.db.insert('pokemon_collection', {
            'user_id': user_id,
            'guild_id': guild_id,
            'pokemon_name': pokemon['name'],
            'pokemon_id': pokemon['id'],
            'cp': cp,
            'rarity': pokemon['rarity'],
            'shiny': 0
        })
        response += f"\n🎉 Bonus! You got a **{pokemon['name']}** (CP: {cp})!"
    
    await interaction.response.send_message(response)

@bot.tree.command(name="pokedex", description="📖 View your Pokédex progress")
async def pokedex(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    pokedex = bot.db.fetch_all(
        "SELECT * FROM pokemon_pokedex WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    total = len(pokedex)
    caught = sum(1 for p in pokedex if p['caught'])
    
    embed = discord.Embed(
        title=f"📖 {interaction.user.display_name}'s Pokédex",
        description=f"Caught: {caught}/{total} Pokémon",
        color=discord.Color.blue()
    )
    embed.add_field(name="Progress", value=f"{int(caught/total*100) if total > 0 else 0}%", inline=True)
    embed.add_field(name="Total Seen", value=total, inline=True)
    embed.add_field(name="Total Caught", value=caught, inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="collection_show", description="📊 Show your collection publicly")
@app_commands.describe(user="User to show collection for")
async def collection_show(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    user_id = str(target.id)
    guild_id = str(interaction.guild.id)
    
    collection = bot.db.fetch_all(
        "SELECT * FROM pokemon_collection WHERE user_id = ? AND guild_id = ? ORDER BY cp DESC LIMIT 10",
        (user_id, guild_id)
    )
    
    if not collection:
        await interaction.response.send_message(f"📭 {target.display_name} hasn't caught any Pokémon yet!")
        return
    
    embed = discord.Embed(
        title=f"📊 {target.display_name}'s Top Pokémon",
        color=discord.Color.gold()
    )
    
    for p in collection:
        shiny = "✨ " if p['shiny'] else ""
        embed.add_field(
            name=f"{shiny}{p['pokemon_name']}",
            value=f"CP: {p['cp']} | Rarity: {p['rarity']}",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed)

# ──────────────────────────────────────────────────────────────────
# VERIFICATION COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="verify", description="🔐 Start the verification process")
async def verify(interaction: discord.Interaction):
    oauth_params = {
        "client_id": config.CLIENT_ID,
        "redirect_uri": config.REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email guilds connections",
        "state": str(interaction.guild.id)
    }
    
    auth_url = "https://discord.com/api/oauth2/authorize?" + "&".join(
        f"{k}={v}" for k, v in oauth_params.items()
    )
    
    embed = discord.Embed(
        title="🔐 Server Verification Required",
        description=(
            "Click the button below to verify your Discord account.\n\n"
            "**This process is secure and only needs to be done once.**"
        ),
        color=discord.Color.blue()
    )
    
    view = View()
    view.add_item(Button(label="🔐 Verify Now", url=auth_url, style=discord.ButtonStyle.primary))
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="status", description="🔐 Check verification status")
async def verify_status(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    verified = bot.db.fetch_one(
        "SELECT * FROM verified_users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    if verified:
        embed = discord.Embed(
            title="✅ Verified",
            description="You are verified in this server!",
            color=discord.Color.green()
        )
        embed.add_field(name="Verified At", value=verified['verified_at'], inline=False)
    else:
        embed = discord.Embed(
            title="❌ Not Verified",
            description="Use `/verify` to start verification.",
            color=discord.Color.red()
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="set_verified_role", description="⚙️ Set verified role (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(role="Role for verified users")
async def set_verified_role(interaction: discord.Interaction, role: discord.Role):
    bot.db.insert('guild_settings', {
        'guild_id': str(interaction.guild.id),
        'verified_role_id': str(role.id)
    })
    await interaction.response.send_message(f"✅ Verified role set to {role.mention}")

@bot.tree.command(name="set_unverified_role", description="⚙️ Set unverified role (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(role="Role for unverified users")
async def set_unverified_role(interaction: discord.Interaction, role: discord.Role):
    bot.db.update(
        'guild_settings',
        {'unverified_role_id': str(role.id)},
        {'guild_id': str(interaction.guild.id)}
    )
    await interaction.response.send_message(f"✅ Unverified role set to {role.mention}")

@bot.tree.command(name="set_log_channel", description="⚙️ Set log channel (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(channel="Channel for logs")
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    bot.db.insert('guild_settings', {
        'guild_id': str(interaction.guild.id),
        'log_channel_id': str(channel.id)
    })
    await interaction.response.send_message(f"✅ Log channel set to {channel.mention}")

@bot.tree.command(name="setup_guide", description="📖 Show setup guide")
async def setup_guide(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Server Setup Guide",
        description="How to set up Anion in your server",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="1️⃣ Set Roles",
        value="`/set_verified_role @role`\n`/set_unverified_role @role`",
        inline=False
    )
    embed.add_field(
        name="2️⃣ Set Channels",
        value="`/set_log_channel #channel`",
        inline=False
    )
    embed.add_field(
        name="3️⃣ Pokémon Setup",
        value="`/poke_setup` - Setup Pokémon channel",
        inline=False
    )
    embed.add_field(
        name="4️⃣ Ticket Setup",
        value="`/setup_ticket` - Setup ticket system",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

# ──────────────────────────────────────────────────────────────────
# MODERATION COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="ban", description="🔨 Ban a member")
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(member="Member to ban", reason="Reason for ban")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 **{member.display_name}** banned. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="👢 Kick a member")
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(member="Member to kick", reason="Reason for kick")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 **{member.display_name}** kicked. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="mute", description="🔇 Mute a member (24h)")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(member="Member to mute", reason="Reason for mute")
async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    await bot.mute_user(interaction.guild, member, reason)
    await interaction.response.send_message(f"🔇 **{member.display_name}** muted for 24h. Reason: {reason}")

@bot.tree.command(name="unmute", description="🔊 Unmute a member")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(member="Member to unmute")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await bot.unmute_user(interaction.guild, member)
    await interaction.response.send_message(f"🔊 **{member.display_name}** unmuted.")

@bot.tree.command(name="warn", description="⚠️ Warn a member (3 = auto-mute)")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(member="Member to warn", reason="Reason for warning")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
    guild_id = str(interaction.guild.id)
    user_id = str(member.id)
    
    bot.db.insert('warnings', {
        'user_id': user_id,
        'guild_id': guild_id,
        'moderator_id': str(interaction.user.id),
        'reason': reason
    })
    
    warnings = bot.db.fetch_all(
        "SELECT * FROM warnings WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    await interaction.response.send_message(
        f"⚠️ **{member.display_name}** warned. Reason: {reason}\nWarnings: {len(warnings)}/3"
    )
    
    if len(warnings) >= 3:
        await bot.mute_user(interaction.guild, member, "Auto-muted for 3 warnings")
        await interaction.followup.send(f"🔇 **{member.display_name}** auto-muted for 3 warnings.")

@bot.tree.command(name="clear", description="🗑️ Clear messages")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(amount="Number of messages to clear (max 100)")
async def clear(interaction: discord.Interaction, amount: int = 10):
    if amount > 100:
        await interaction.response.send_message("❌ Maximum 100 messages!", ephemeral=True)
        return
    
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"🗑️ Cleared {amount} messages!", ephemeral=True)

@bot.tree.command(name="add_badword", description="🚫 Add a bad word (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(word="Word to add")
async def add_badword(interaction: discord.Interaction, word: str):
    bot.db.insert('bad_words', {
        'word': word.lower(),
        'guild_id': str(interaction.guild.id)
    })
    await interaction.response.send_message(f"✅ Added `{word}` to bad words list.")

@bot.tree.command(name="remove_badword", description="🚫 Remove a bad word (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(word="Word to remove")
async def remove_badword(interaction: discord.Interaction, word: str):
    bot.db.execute(
        "DELETE FROM bad_words WHERE word = ? AND guild_id = ?",
        (word.lower(), str(interaction.guild.id))
    )
    await interaction.response.send_message(f"✅ Removed `{word}` from bad words list.")

@bot.tree.command(name="badwords", description="🚫 List all bad words (Admin)")
@app_commands.default_permissions(administrator=True)
async def list_badwords(interaction: discord.Interaction):
    words = bot.db.fetch_all(
        "SELECT word FROM bad_words WHERE guild_id = ?",
        (str(interaction.guild.id),)
    )
    
    if not words:
        await interaction.response.send_message("✅ No bad words configured.")
        return
    
    word_list = "\n".join([f"• {row['word']}" for row in words])
    embed = discord.Embed(
        title="🚫 Bad Words",
        description=word_list,
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

# ──────────────────────────────────────────────────────────────────
# TICKET COMMANDS (with GUI)
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="ticket", description="🎫 Create a support ticket")
@app_commands.describe(reason="Reason for the ticket")
async def ticket(interaction: discord.Interaction, reason: str = "No reason provided"):
    # Use the GUI modal
    modal = TicketModal()
    await interaction.response.send_modal(modal)

@bot.tree.command(name="setup_ticket", description="🎫 Setup ticket system (Admin)")
@app_commands.default_permissions(administrator=True)
async def setup_ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Click the button below to create a support ticket.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="How it works",
        value="1. Click the button below\n2. Fill in the details\n3. A private ticket channel will be created",
        inline=False
    )
    
    view = TicketView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="close", description="🔒 Close the current ticket")
async def close_ticket(interaction: discord.Interaction):
    ticket = bot.db.fetch_one(
        "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
        (str(interaction.channel.id),)
    )
    
    if not ticket:
        await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔒 Closing Ticket",
        description=f"Ticket will be closed in 10 seconds.",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed)
    
    bot.db.execute(
        "UPDATE tickets SET status = 'closed', closed_at = ? WHERE channel_id = ?",
        (datetime.now().isoformat(), str(interaction.channel.id))
    )
    
    await asyncio.sleep(10)
    await interaction.channel.delete()

@bot.tree.command(name="add_user", description="➕ Add user to ticket")
@app_commands.default_permissions(manage_channels=True)
@app_commands.describe(user="User to add")
async def ticket_add_user(interaction: discord.Interaction, user: discord.Member):
    ticket = bot.db.fetch_one(
        "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
        (str(interaction.channel.id),)
    )
    
    if not ticket:
        await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
        return
    
    await interaction.channel.set_permissions(user, read_messages=True, send_messages=True, attach_files=True)
    await interaction.response.send_message(f"✅ Added {user.mention} to the ticket!")

@bot.tree.command(name="remove_user", description="➖ Remove user from ticket")
@app_commands.default_permissions(manage_channels=True)
@app_commands.describe(user="User to remove")
async def ticket_remove_user(interaction: discord.Interaction, user: discord.Member):
    ticket = bot.db.fetch_one(
        "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
        (str(interaction.channel.id),)
    )
    
    if not ticket:
        await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
        return
    
    if str(user.id) == ticket['user_id']:
        await interaction.response.send_message("❌ Cannot remove the ticket creator!", ephemeral=True)
        return
    
    await interaction.channel.set_permissions(user, read_messages=False, send_messages=False)
    await interaction.response.send_message(f"✅ Removed {user.mention} from the ticket!")

@bot.tree.command(name="transcript", description="📝 Get ticket transcript")
async def transcript(interaction: discord.Interaction):
    ticket = bot.db.fetch_one(
        "SELECT * FROM tickets WHERE channel_id = ?",
        (str(interaction.channel.id),)
    )
    
    if not ticket:
        await interaction.response.send_message("❌ This is not a ticket channel!", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    messages = []
    async for msg in interaction.channel.history(limit=100):
        messages.append(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author.display_name}: {msg.content}")
    
    transcript = "\n".join(reversed(messages))
    
    import io
    file = discord.File(io.StringIO(transcript), filename=f"transcript-{ticket['ticket_id']}.txt")
    await interaction.followup.send("📝 Transcript:", file=file, ephemeral=True)

# ──────────────────────────────────────────────────────────────────
# GIVEAWAY COMMANDS (with GUI)
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="giveaway", description="🎁 Start a giveaway (Admin)")
@app_commands.default_permissions(administrator=True)
async def giveaway(interaction: discord.Interaction):
    modal = GiveawayCreatorModal()
    await interaction.response.send_modal(modal)

@bot.tree.command(name="reroll", description="🎁 Reroll a giveaway (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(message_id="ID of the giveaway message")
async def reroll(interaction: discord.Interaction, message_id: str):
    try:
        msg_id = int(message_id)
        message = await interaction.channel.fetch_message(msg_id)
        
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if not reaction:
            await interaction.response.send_message("❌ No 🎉 reactions found!", ephemeral=True)
            return
        
        users = []
        async for user in reaction.users():
            if not user.bot:
                users.append(user)
        
        if not users:
            await interaction.response.send_message("❌ No valid participants!", ephemeral=True)
            return
        
        giveaway_data = bot.db.fetch_one(
            "SELECT winners FROM giveaways WHERE message_id = ?",
            (message_id,)
        )
        winners_count = giveaway_data['winners'] if giveaway_data else 1
        
        winners = random.sample(users, min(winners_count, len(users)))
        
        await interaction.response.send_message(
            f"🎉 New winners: {', '.join([w.mention for w in winners])}!"
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

# ──────────────────────────────────────────────────────────────────
# LEVELING COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="rank", description="📊 Check your rank")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user_id = str(target.id)
    guild_id = str(interaction.guild.id)
    
    data = bot.db.fetch_one(
        "SELECT * FROM levels WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    if not data:
        await interaction.response.send_message(f"📭 {target.display_name} hasn't sent any messages yet!")
        return
    
    rank_result = bot.db.fetch_one(
        "SELECT COUNT(*) + 1 as rank FROM levels WHERE guild_id = ? AND xp > (SELECT xp FROM levels WHERE user_id = ? AND guild_id = ?)",
        (guild_id, user_id, guild_id)
    )
    
    embed = discord.Embed(
        title=f"📊 {target.display_name}'s Rank",
        color=target.color
    )
    
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

@bot.tree.command(name="leaderboard", description="🏆 View server leaderboard")
async def leaderboard(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    data = bot.db.fetch_all(
        "SELECT user_id, xp, level FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
        (guild_id,)
    )
    
    if not data:
        await interaction.response.send_message("📭 No data yet!")
        return
    
    embed = discord.Embed(
        title=f"🏆 {interaction.guild.name} Leaderboard",
        color=discord.Color.gold()
    )
    
    for i, entry in enumerate(data, 1):
        member = interaction.guild.get_member(int(entry['user_id']))
        if member:
            embed.add_field(
                name=f"#{i} {member.display_name}",
                value=f"Level {entry['level']} | {entry['xp']} XP",
                inline=False
            )
    
    await interaction.response.send_message(embed=embed)

# ──────────────────────────────────────────────────────────────────
# MUSIC COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="play", description="🎵 Play a song")
@app_commands.describe(url="YouTube URL or search term")
async def play(interaction: discord.Interaction, url: str):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ You need to be in a voice channel!", ephemeral=True)
        return
    
    voice_channel = interaction.user.voice.channel
    
    if interaction.guild.id not in bot.voice_clients:
        voice_client = await voice_channel.connect()
        bot.voice_clients[interaction.guild.id] = voice_client
    else:
        voice_client = bot.voice_clients[interaction.guild.id]
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    
    await interaction.response.send_message(f"🔍 Searching...", ephemeral=True)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            url2 = info['formats'][0]['url']
            
            voice_client.play(
                discord.FFmpegPCMAudio(url2),
                after=lambda e: print(f'Player error: {e}') if e else None
            )
            
            embed = discord.Embed(
                title="▶️ Now Playing",
                description=f"**{info['title']}**",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Error playing: {e}")

@bot.tree.command(name="skip", description="⏭️ Skip current song")
async def skip(interaction: discord.Interaction):
    if interaction.guild.id in bot.voice_clients:
        voice_client = bot.voice_clients[interaction.guild.id]
        if voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped!")
        else:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Not in a voice channel!", ephemeral=True)

@bot.tree.command(name="stop", description="⏹️ Stop music and leave")
async def stop(interaction: discord.Interaction):
    if interaction.guild.id in bot.voice_clients:
        voice_client = bot.voice_clients[interaction.guild.id]
        await voice_client.disconnect()
        del bot.voice_clients[interaction.guild.id]
        await interaction.response.send_message("⏹️ Stopped music and left voice!")
    else:
        await interaction.response.send_message("❌ Not in a voice channel!", ephemeral=True)

# ──────────────────────────────────────────────────────────────────
# AI COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="ai", description="🤖 Chat with AI")
@app_commands.describe(message="Your message")
async def ai_chat(interaction: discord.Interaction, message: str):
    if not config.OPENAI_KEY:
        await interaction.response.send_message("❌ AI is not configured!", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful Discord bot named Anion."},
                {"role": "user", "content": message}
            ],
            max_tokens=500
        )
        await interaction.followup.send(f"🤖 {response.choices[0].message.content[:1900]}")
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {e}")

# ──────────────────────────────────────────────────────────────────
# ADMIN SETUP COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="poke_setup", description="⚙️ Setup Pokémon channels (Admin)")
@app_commands.default_permissions(administrator=True)
async def poke_setup(interaction: discord.Interaction):
    category = discord.utils.get(interaction.guild.categories, name="🎮 Pokémon")
    if not category:
        category = await interaction.guild.create_category("🎮 Pokémon")
    
    channel = await interaction.guild.create_text_channel(
        "🌿-pokemon-spawns",
        category=category
    )
    
    bot.db.insert('pokemon_settings', {
        'guild_id': str(interaction.guild.id),
        'channel_id': str(channel.id)
    })
    
    await interaction.response.send_message(
        f"✅ Pokémon setup complete! Spawns will appear in {channel.mention}"
    )

@bot.tree.command(name="spawn_pokemon", description="⚙️ Spawn any Pokémon (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(name="Pokémon name", channel="Channel to spawn in")
async def spawn_pokemon(interaction: discord.Interaction, name: str, channel: discord.TextChannel):
    pokemon = bot.pokemon_data.get_pokemon_by_name(name)
    
    if not pokemon:
        await interaction.response.send_message(f"❌ Pokémon `{name}` not found!", ephemeral=True)
        return
    
    await bot.spawn_pokemon_message(channel, pokemon)
    await interaction.response.send_message(f"✅ Spawned {pokemon['name']} in {channel.mention}")

@bot.tree.command(name="give_pokemon", description="⚙️ Give Pokémon to user (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="User to give to", name="Pokémon name", cp="CP value (optional)")
async def give_pokemon(interaction: discord.Interaction, user: discord.Member, name: str, cp: int = None):
    pokemon = bot.pokemon_data.get_pokemon_by_name(name)
    
    if not pokemon:
        await interaction.response.send_message(f"❌ Pokémon `{name}` not found!", ephemeral=True)
        return
    
    cp = cp or random.randint(100, 500)
    
    bot.db.insert('pokemon_collection', {
        'user_id': str(user.id),
        'guild_id': str(interaction.guild.id),
        'pokemon_name': pokemon['name'],
        'pokemon_id': pokemon['id'],
        'cp': cp,
        'rarity': pokemon['rarity'],
        'shiny': 0
    })
    
    await interaction.response.send_message(
        f"✅ Gave **{pokemon['name']}** (CP: {cp}) to {user.mention}"
    )

@bot.tree.command(name="give_coins", description="⚙️ Give coins to user (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="User to give to", amount="Amount of coins")
async def give_coins(interaction: discord.Interaction, user: discord.Member, amount: int):
    bot.db.execute(
        """INSERT INTO pokemon_users (user_id, guild_id, coins) 
           VALUES (?, ?, ?) 
           ON CONFLICT(user_id, guild_id) 
           DO UPDATE SET coins = coins + ?""",
        (str(user.id), str(interaction.guild.id), amount, amount)
    )
    await interaction.response.send_message(f"✅ Gave {amount} coins to {user.mention}")

@bot.tree.command(name="reset_pokemon", description="⚙️ Reset Pokémon data (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="User to reset")
async def reset_pokemon(interaction: discord.Interaction, user: discord.Member):
    user_id = str(user.id)
    guild_id = str(interaction.guild.id)
    
    bot.db.execute(
        "DELETE FROM pokemon_collection WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    bot.db.execute(
        "DELETE FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    bot.db.execute(
        "DELETE FROM pokemon_pokedex WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    await interaction.response.send_message(f"✅ Reset all Pokémon data for {user.mention}")

# ──────────────────────────────────────────────────────────────────
# UTILITY COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="ping", description="🏓 Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(interaction.client.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {latency}ms",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="📊 Get server information")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
    embed.add_field(name="📝 Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="💎 Boost Tier", value=guild.premium_tier, inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="👤 Get user information")
@app_commands.describe(member="User to get info about")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    
    embed = discord.Embed(
        title=f"👤 {target.display_name}",
        color=target.color
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Username", value=target.name, inline=True)
    embed.add_field(name="ID", value=target.id, inline=True)
    embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(
        name="Roles",
        value=", ".join([r.name for r in target.roles if r.name != "@everyone"])[:100] or "None",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list_all", description="📋 Show all commands")
async def list_all(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📋 All Commands",
        description="Complete list of Anion bot commands",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎮 Pokémon",
        value="`/catch` `/collection` `/collection_show` `/pokedex` `/shop` `/buy` `/daily`",
        inline=False
    )
    
    embed.add_field(
        name="🔐 Verification",
        value="`/verify` `/status` `/set_verified_role` `/set_unverified_role` `/set_log_channel` `/setup_guide`",
        inline=False
    )
    
    embed.add_field(
        name="🛡️ Moderation",
        value="`/ban` `/kick` `/mute` `/unmute` `/warn` `/clear` `/add_badword` `/remove_badword` `/badwords`",
        inline=False
    )
    
    embed.add_field(
        name="🎫 Tickets (GUI)",
        value="`/ticket` `/setup_ticket` `/close` `/add_user` `/remove_user` `/transcript`",
        inline=False
    )
    
    embed.add_field(
        name="📈 Leveling",
        value="`/rank` `/leaderboard`",
        inline=False
    )
    
    embed.add_field(
        name="🎁 Giveaways (GUI)",
        value="`/giveaway` `/reroll`",
        inline=False
    )
    
    embed.add_field(
        name="🎵 Music",
        value="`/play` `/skip` `/stop`",
        inline=False
    )
    
    embed.add_field(
        name="🤖 AI",
        value="`/ai`",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Utility",
        value="`/ping` `/serverinfo` `/userinfo` `/list_all`",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Admin",
        value="`/poke_setup` `/spawn_pokemon` `/give_pokemon` `/give_coins` `/reset_pokemon`",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="debug_roles", description="🔍 Debug role assignment (Admin)")
@app_commands.default_permissions(administrator=True)
async def debug_roles(interaction: discord.Interaction):
    settings = bot.db.fetch_one(
        "SELECT * FROM guild_settings WHERE guild_id = ?",
        (str(interaction.guild.id),)
    )
    
    embed = discord.Embed(
        title="🔍 Role Debug",
        color=discord.Color.blue()
    )
    
    if settings:
        embed.add_field(
            name="Verified Role",
            value=f"<@&{settings['verified_role_id']}>" if settings['verified_role_id'] else "Not set",
            inline=True
        )
        embed.add_field(
            name="Unverified Role",
            value=f"<@&{settings['unverified_role_id']}>" if settings['unverified_role_id'] else "Not set",
            inline=True
        )
        embed.add_field(
            name="Log Channel",
            value=f"<#{settings['log_channel_id']}>" if settings['log_channel_id'] else "Not set",
            inline=True
        )
    else:
        embed.description = "No settings configured!"
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="view_settings", description="🔍 View bot settings (Admin)")
@app_commands.default_permissions(administrator=True)
async def view_settings(interaction: discord.Interaction):
    settings = bot.db.fetch_one(
        "SELECT * FROM guild_settings WHERE guild_id = ?",
        (str(interaction.guild.id),)
    )
    
    pokemon_settings = bot.db.fetch_one(
        "SELECT * FROM pokemon_settings WHERE guild_id = ?",
        (str(interaction.guild.id),)
    )
    
    embed = discord.Embed(
        title="⚙️ Bot Settings",
        color=discord.Color.blue()
    )
    
    if settings:
        embed.add_field(
            name="📋 Verification",
            value=f"Verified Role: <@&{settings['verified_role_id']}>" if settings['verified_role_id'] else "Not set",
            inline=False
        )
        embed.add_field(
            name="📋 Logging",
            value=f"Log Channel: <#{settings['log_channel_id']}>" if settings['log_channel_id'] else "Not set",
            inline=False
        )
    else:
        embed.add_field(name="📋 Guild Settings", value="Not configured", inline=False)
    
    if pokemon_settings:
        embed.add_field(
            name="🎮 Pokémon",
            value=f"Channel: <#{pokemon_settings['channel_id']}>\nSpawn: {'Enabled' if pokemon_settings['spawn_enabled'] else 'Disabled'}",
            inline=False
        )
    else:
        embed.add_field(name="🎮 Pokémon", value="Not configured", inline=False)
    
    await interaction.response.send_message(embed=embed)

# ──────────────────────────────────────────────────────────────────
# DM COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot.tree.command(name="dm", description="📨 Send a DM to a user (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(user="User to DM", message="Message to send")
async def dm(interaction: discord.Interaction, user: discord.Member, message: str):
    try:
        embed = discord.Embed(
            title="📨 Message from Staff",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"From: {interaction.guild.name}")
        await user.send(embed=embed)
        await interaction.response.send_message(f"✅ Message sent to {user.mention}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Could not DM user: {e}", ephemeral=True)

@bot.tree.command(name="say", description="📨 Send a message as bot (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(channel="Channel to send in", message="Message to send")
async def say(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(message)
    await interaction.response.send_message(f"✅ Message sent to {channel.mention}", ephemeral=True)

@bot.tree.command(name="announce", description="📢 Send an announcement (Admin)")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(title="Announcement title", message="Announcement message")
async def announce(interaction: discord.Interaction, title: str, message: str):
    embed = discord.Embed(
        title=f"📢 {title}",
        description=message,
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.set_footer(text=f"Announced by {interaction.user.display_name}")
    
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Announcement sent!", ephemeral=True)

# ═══════════════════════════════════════════════════════════════════
# FLASK WEB APP
# ═══════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = config.FLASK_SECRET
CORS(flask_app)

@flask_app.route('/')
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Anion Bot</title>
    <style>
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .container { background: white; border-radius: 20px; padding: 40px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 600px; text-align: center; }
        h1 { color: #333; font-size: 2.5em; margin-bottom: 10px; }
        .subtitle { color: #666; font-size: 1.2em; margin-bottom: 30px; }
        .status { display: inline-block; padding: 10px 20px; border-radius: 50px; background: #4CAF50; color: white; margin-bottom: 20px; }
        .features { text-align: left; margin: 20px 0; padding: 0; list-style: none; }
        .features li { padding: 10px; border-bottom: 1px solid #eee; }
        .features li:last-child { border-bottom: none; }
        .btn { display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 50px; margin: 10px; transition: transform 0.2s; }
        .btn:hover { transform: scale(1.05); }
        .btn-secondary { background: #764ba2; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Anion Bot</h1>
        <div class="subtitle">All-in-One Discord Bot</div>
        <div class="status">🟢 Online</div>
        <ul class="features">
            <li>🎮 Pokémon System - Catch, Collect, Trade!</li>
            <li>🔐 Verification - Secure OAuth2 verification</li>
            <li>🛡️ Moderation - Full moderation suite</li>
            <li>🎫 Tickets - Beautiful ticket system</li>
            <li>📈 Leveling - XP and ranks</li>
            <li>🎁 Giveaways - Win awesome prizes</li>
            <li>🎵 Music - Listen to your favorite songs</li>
            <li>🤖 AI - Chat with AI</li>
        </ul>
        <a href="/dashboard" class="btn">📊 Dashboard</a>
        <a href="https://discord.com/oauth2/authorize?client_id=" + config.CLIENT_ID + "&permissions=8&scope=bot%20applications.commands" class="btn btn-secondary">➕ Invite Bot</a>
    </div>
</body>
</html>
    """)

@flask_app.route('/dashboard')
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - Anion Bot</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 15px; margin-bottom: 30px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; color: #667eea; }
        .stat-label { color: #666; margin-top: 5px; }
        .content { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px; }
        .feature-item { padding: 20px; border: 1px solid #eee; border-radius: 10px; text-align: center; transition: transform 0.2s; }
        .feature-item:hover { transform: translateY(-5px); box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
        .feature-icon { font-size: 3em; margin-bottom: 10px; }
        .feature-name { font-weight: bold; font-size: 1.1em; }
        .feature-desc { color: #666; font-size: 0.9em; margin-top: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Anion Bot Dashboard</h1>
            <p>Welcome to the Anion Bot control panel</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number" id="guilds">Loading...</div>
                <div class="stat-label">Servers</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="users">Loading...</div>
                <div class="stat-label">Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="pokemon">Loading...</div>
                <div class="stat-label">Pokémon Caught</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">🟢</div>
                <div class="stat-label">Status: Online</div>
            </div>
        </div>
        
        <div class="content">
            <h2>✨ Features</h2>
            <div class="feature-grid">
                <div class="feature-item">
                    <div class="feature-icon">🎮</div>
                    <div class="feature-name">Pokémon</div>
                    <div class="feature-desc">Catch, collect, and trade Pokémon</div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">🔐</div>
                    <div class="feature-name">Verification</div>
                    <div class="feature-desc">OAuth2 Discord verification</div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">🛡️</div>
                    <div class="feature-name">Moderation</div>
                    <div class="feature-desc">Full moderation suite</div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">🎫</div>
                    <div class="feature-name">Tickets</div>
                    <div class="feature-desc">Beautiful ticket system</div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">📈</div>
                    <div class="feature-name">Leveling</div>
                    <div class="feature-desc">XP and rank system</div>
                </div>
                <div class="feature-item">
                    <div class="feature-icon">🎁</div>
                    <div class="feature-name">Giveaways</div>
                    <div class="feature-desc">Win awesome prizes</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        fetch('/api/stats')
            .then(res => res.json())
            .then(data => {
                document.getElementById('guilds').textContent = data.guilds || 0;
                document.getElementById('users').textContent = data.users || 0;
                document.getElementById('pokemon').textContent = data.pokemon || 0;
            });
    </script>
</body>
</html>
    """)

@flask_app.route('/api/stats')
def api_stats():
    if not bot:
        return jsonify({'guilds': 0, 'users': 0, 'pokemon': 0})
    
    pokemon_count = bot.db.fetch_one("SELECT COUNT(*) FROM pokemon_collection")
    return jsonify({
        'guilds': len(bot.guilds),
        'users': sum(g.member_count for g in bot.guilds),
        'pokemon': pokemon_count[0] if pokemon_count else 0
    })

@flask_app.route('/callback')
def oauth_callback():
    code = request.args.get('code')
    guild_id = request.args.get('state')
    
    if not code:
        return "Invalid request", 400
    
    data = {
        'client_id': config.CLIENT_ID,
        'client_secret': config.CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': config.REDIRECT_URI
    }
    
    response = requests.post('https://discord.com/api/oauth2/token', data=data)
    token_data = response.json()
    
    if 'access_token' not in token_data:
        return "Authentication failed", 400
    
    headers = {'Authorization': f"Bearer {token_data['access_token']}"}
    user_response = requests.get('https://discord.com/api/users/@me', headers=headers)
    user_data = user_response.json()
    
    session['user'] = user_data
    
    return redirect(url_for('dashboard'))

# ═══════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

async def main():
    global bot
    
    bot = AnionBot()
    
    # Register commands
    commands_to_register = [
        # Pokémon
        catch, collection, shop, buy, daily, pokedex, collection_show,
        # Verification
        verify, verify_status, set_verified_role, set_unverified_role, 
        set_log_channel, setup_guide,
        # Moderation
        ban, kick, mute, unmute, warn, clear, add_badword, remove_badword, list_badwords,
        # Tickets
        ticket, setup_ticket, close_ticket, ticket_add_user, ticket_remove_user, transcript,
        # Giveaways
        giveaway, reroll,
        # Leveling
        rank, leaderboard,
        # Music
        play, skip, stop,
        # AI
        ai_chat,
        # Admin
        poke_setup, spawn_pokemon, give_pokemon, give_coins, reset_pokemon,
        # Utility
        ping, serverinfo, userinfo, list_all, debug_roles, view_settings,
        # DM
        dm, say, announce
    ]
    
    for cmd in commands_to_register:
        bot.tree.add_command(cmd)
    
    # Start Flask in separate thread
    import threading
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start bot
    await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
