#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════
                    🔐 ANION PROJECT - COMPLETE BOT
                    Single File Implementation
═══════════════════════════════════════════════════════════════════

MIT Portfolio Project - Full Stack Discord Bot
Features: Pokémon System, Verification, Moderation, Music, AI, Giveaways
"""

# ═══════════════════════════════════════════════════════════════════
# IMPORTS
# ═══════════════════════════════════════════════════════════════════

import os
import json
import random
import asyncio
import sqlite3
import hashlib
import secrets
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple

# Discord
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Select

# Web
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_cors import CORS

# Music
import yt_dlp
import asyncio
from collections import deque

# AI
import openai

# Configuration
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

TOKEN = os.getenv('DISCORD_TOKEN', 'MTUzNDMwOTIzNDcwNjIyMzI1Ng.GQSM5C.ZcyRZfnz2y9D1iCNB9OroL0ZyXYAjap7PThQaQ')
CLIENT_ID = os.getenv('CLIENT_ID', '1534309234706223256')
CLIENT_SECRET = os.getenv('CLIENT_SECRET', '2l-Tv7WysMP87tjIfaLWK5y438_S-7Gm')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://verifier.up.railway.app/callback')
OPENAI_KEY = os.getenv('OPENAI_KEY', '')
DB_PATH = os.getenv('DB_PATH', '/data')  # Railway persistence

# Database setup with persistence
if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH, exist_ok=True)

DB_FILE = os.path.join(DB_PATH, 'bot_database.db')

# ═══════════════════════════════════════════════════════════════════
# DATABASE CLASS
# ═══════════════════════════════════════════════════════════════════

class Database:
    """Handles all database operations with proper connection management"""
    
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.connection = None
        self.cursor = None
        self.init_database()
    
    def get_connection(self):
        """Get or create database connection"""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_file)
            self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
        return self.connection
    
    def close_connection(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.cursor = None
    
    def init_database(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Pokémon Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_users (
                user_id TEXT,
                guild_id TEXT,
                coins INTEGER DEFAULT 100,
                catches INTEGER DEFAULT 0,
                total_cp INTEGER DEFAULT 0,
                legendary_catches INTEGER DEFAULT 0,
                shiny_catches INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        # Pokémon Collection Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_collection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                guild_id TEXT,
                pokemon_name TEXT,
                pokemon_id INTEGER,
                cp INTEGER,
                rarity TEXT,
                shiny BOOLEAN DEFAULT 0,
                caught_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOR SALE BOOLEAN DEFAULT 0,
                sale_price INTEGER DEFAULT 0
            )
        ''')
        
        # Pokédex Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_pokedex (
                user_id TEXT,
                guild_id TEXT,
                pokemon_id INTEGER,
                seen BOOLEAN DEFAULT 0,
                caught BOOLEAN DEFAULT 0,
                PRIMARY KEY (user_id, guild_id, pokemon_id)
            )
        ''')
        
        # Pokémon Settings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_settings (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT,
                spawn_enabled BOOLEAN DEFAULT 1,
                catch_cooldown INTEGER DEFAULT 30
            )
        ''')
        
        # Pokémon Market Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pokemon_market (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT UNIQUE,
                pokemon_id INTEGER,
                seller_id TEXT,
                guild_id TEXT,
                price INTEGER,
                listed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sold BOOLEAN DEFAULT 0
            )
        ''')
        
        # Guild Settings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                verified_role_id TEXT,
                unverified_role_id TEXT,
                log_channel_id TEXT,
                welcome_channel_id TEXT,
                goodbye_channel_id TEXT,
                welcome_message TEXT,
                goodbye_message TEXT,
                auto_verify BOOLEAN DEFAULT 0
            )
        ''')
        
        # Leveling System Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS levels (
                user_id TEXT,
                guild_id TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        # Warnings Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                guild_id TEXT,
                moderator_id TEXT,
                reason TEXT,
                warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tickets Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE,
                guild_id TEXT,
                user_id TEXT,
                channel_id TEXT,
                status TEXT DEFAULT 'open',
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            )
        ''')
        
        # Muted Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS muted (
                user_id TEXT,
                guild_id TEXT,
                muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unmute_at TIMESTAMP,
                reason TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        # Verified Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verified_users (
                user_id TEXT,
                guild_id TEXT,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        ''')
        
        # Verify Tokens Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verify_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT,
                guild_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used BOOLEAN DEFAULT 0
            )
        ''')
        
        # Giveaways Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                channel_id TEXT,
                guild_id TEXT,
                prize TEXT,
                winners INTEGER DEFAULT 1,
                ended BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP
            )
        ''')
        
        # Bad Words Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bad_words (
                word TEXT PRIMARY KEY,
                guild_id TEXT
            )
        ''')
        
        # Music Queue Table (for persistence)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS music_queue (
                guild_id TEXT PRIMARY KEY,
                queue_json TEXT,
                current_song_json TEXT
            )
        ''')
        
        conn.commit()
        self.close_connection()
    
    def execute(self, query, params=()):
        """Execute a query and return cursor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor
    
    def fetch_one(self, query, params=()):
        """Fetch one row"""
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def fetch_all(self, query, params=()):
        """Fetch all rows"""
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    def insert(self, table, data):
        """Insert data into table"""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})"
        self.execute(query, list(data.values()))
    
    def update(self, table, data, where):
        """Update data in table"""
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        where_clause = ' AND '.join([f"{k} = ?" for k in where.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        self.execute(query, list(data.values()) + list(where.values()))

# ═══════════════════════════════════════════════════════════════════
# POKEMON DATA
# ═══════════════════════════════════════════════════════════════════

class PokemonData:
    """Pokémon data management with API integration"""
    
    def __init__(self):
        self.pokemon_list = []
        self.rarities = {
            'Common': {'weight': 50, 'catch_rate': 0.8, 'emoji': '⬜'},
            'Uncommon': {'weight': 25, 'catch_rate': 0.6, 'emoji': '🟩'},
            'Rare': {'weight': 15, 'catch_rate': 0.4, 'emoji': '🟦'},
            'Legendary': {'weight': 8, 'catch_rate': 0.2, 'emoji': '🌟'},
            'Mythical': {'weight': 2, 'catch_rate': 0.1, 'emoji': '💫'}
        }
        self.ball_multipliers = {
            'pokeball': 1.0,
            'greatball': 1.5,
            'ultraball': 2.0,
            'masterball': 5.0
        }
        self.ball_prices = {
            'pokeball': 50,
            'greatball': 100,
            'ultraball': 200,
            'masterball': 1000
        }
        self.load_pokemon_data()
    
    def load_pokemon_data(self):
        """Load Pokémon data from API or cache"""
        try:
            # Try to load from cache first
            with open('pokemon_cache.json', 'r') as f:
                self.pokemon_list = json.load(f)
        except FileNotFoundError:
            # Fetch from PokeAPI
            self.fetch_from_api()
            # Save cache
            with open('pokemon_cache.json', 'w') as f:
                json.dump(self.pokemon_list, f)
    
    def fetch_from_api(self):
        """Fetch Pokémon data from PokeAPI"""
        try:
            response = requests.get('https://pokeapi.co/api/v2/pokemon?limit=898')
            data = response.json()
            
            for pokemon in data['results']:
                # Get detailed info
                detail_response = requests.get(pokemon['url'])
                detail = detail_response.json()
                
                # Determine rarity based on types and stats
                total_stats = sum(stat['base_stat'] for stat in detail['stats'])
                types = [t['type']['name'] for t in detail['types']]
                
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
                    'types': types,
                    'base_stats': {
                        'hp': detail['stats'][0]['base_stat'],
                        'attack': detail['stats'][1]['base_stat'],
                        'defense': detail['stats'][2]['base_stat'],
                        'special_attack': detail['stats'][3]['base_stat'],
                        'special_defense': detail['stats'][4]['base_stat'],
                        'speed': detail['stats'][5]['base_stat']
                    },
                    'total_stats': total_stats,
                    'rarity': rarity,
                    'sprite_url': detail['sprites']['front_default']
                })
        except Exception as e:
            print(f"Error fetching Pokémon data: {e}")
            # Fallback data
            self.pokemon_list = self.get_fallback_data()
    
    def get_fallback_data(self):
        """Fallback Pokémon data if API fails"""
        return [
            {'id': 1, 'name': 'Bulbasaur', 'rarity': 'Common', 'total_stats': 318},
            {'id': 4, 'name': 'Charmander', 'rarity': 'Common', 'total_stats': 309},
            {'id': 7, 'name': 'Squirtle', 'rarity': 'Common', 'total_stats': 314},
            {'id': 25, 'name': 'Pikachu', 'rarity': 'Uncommon', 'total_stats': 320},
            {'id': 150, 'name': 'Mewtwo', 'rarity': 'Legendary', 'total_stats': 680},
            {'id': 151, 'name': 'Mew', 'rarity': 'Mythical', 'total_stats': 600},
            {'id': 384, 'name': 'Rayquaza', 'rarity': 'Legendary', 'total_stats': 680},
            {'id': 385, 'name': 'Jirachi', 'rarity': 'Mythical', 'total_stats': 600},
        ]
    
    def get_random_pokemon(self):
        """Get a random Pokémon based on rarity weights"""
        rarity = self.get_rarity()
        eligible = [p for p in self.pokemon_list if p['rarity'] == rarity]
        if not eligible:
            eligible = self.pokemon_list
        return random.choice(eligible)
    
    def get_rarity(self):
        """Get a random rarity based on weights"""
        choices = []
        for rarity, data in self.rarities.items():
            choices.extend([rarity] * data['weight'])
        return random.choice(choices)
    
    def get_pokemon_by_name(self, name):
        """Find Pokémon by name"""
        name = name.lower().capitalize()
        for pokemon in self.pokemon_list:
            if pokemon['name'].lower() == name.lower():
                return pokemon
        return None

# ═══════════════════════════════════════════════════════════════════
# DISCORD BOT CLASS
# ═══════════════════════════════════════════════════════════════════

class AnionBot(commands.Bot):
    """Main bot class with all features integrated"""
    
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        
        # Initialize components
        self.db = Database()
        self.pokemon_data = PokemonData()
        
        # Active spawns
        self.active_spawns = {}
        self.legendary_spawns = {}
        
        # Music queues
        self.music_queues = {}
        self.voice_clients = {}
        
        # Message cache for spam detection
        self.message_cache = {}
        
        # Remove default help command
        self.remove_command('help')
        
        # Load cogs
        self.load_extensions()
        
        # Setup tasks
        self.spawn_loop.start()
        self.cleanup_loop.start()
    
    def load_extensions(self):
        """Load all extensions"""
        # We'll use direct method registration since it's a single file
        pass
    
    async def setup_hook(self):
        """Setup hook for bot initialization"""
        await self.tree.sync()
        print(f'✅ Bot is ready! Logged in as {self.user}')
    
    # ═══════════════════════════════════════════════════════════════
    # EVENTS
    # ═══════════════════════════════════════════════════════════════
    
    async def on_ready(self):
        """Called when bot is ready"""
        print(f'✅ Logged in as {self.user} (ID: {self.user.id})')
        print(f'✅ Connected to {len(self.guilds)} guilds')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Pokémon | /help"
            )
        )
    
    async def on_member_join(self, member):
        """Handle new member join"""
        guild_id = str(member.guild.id)
        settings = self.db.fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        )
        
        if settings:
            # Assign unverified role
            if settings['unverified_role_id']:
                role = member.guild.get_role(int(settings['unverified_role_id']))
                if role:
                    await member.add_roles(role)
            
            # Send welcome message
            if settings['welcome_channel_id']:
                channel = member.guild.get_channel(int(settings['welcome_channel_id']))
                if channel:
                    message = settings['welcome_message'] or f"Welcome {member.mention}!"
                    await channel.send(message)
    
    async def on_member_remove(self, member):
        """Handle member leave"""
        guild_id = str(member.guild.id)
        settings = self.db.fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        )
        
        if settings and settings['goodbye_channel_id']:
            channel = member.guild.get_channel(int(settings['goodbye_channel_id']))
            if channel:
                message = settings['goodbye_message'] or f"{member.display_name} has left the server."
                await channel.send(message)
    
    async def on_message(self, message):
        """Handle message events"""
        if message.author.bot:
            return
        
        # Anti-spam
        await self.handle_antispam(message)
        
        # Bad word filter
        await self.handle_bad_words(message)
        
        # Leveling
        await self.handle_leveling(message)
        
        # Process commands
        await self.process_commands(message)
    
    # ═══════════════════════════════════════════════════════════════
    # TASKS
    # ═══════════════════════════════════════════════════════════════
    
    @tasks.loop(seconds=30)
    async def spawn_loop(self):
        """Spawn Pokémon in configured channels"""
        for guild in self.guilds:
            settings = self.db.fetch_one(
                "SELECT * FROM pokemon_settings WHERE guild_id = ?",
                (str(guild.id),)
            )
            
            if settings and settings['spawn_enabled']:
                channel = guild.get_channel(int(settings['channel_id']))
                if channel:
                    # Random spawn
                    if random.random() < 0.3:  # 30% chance every 30 seconds
                        pokemon = self.pokemon_data.get_random_pokemon()
                        await self.spawn_pokemon_message(channel, pokemon)
                    
                    # Legendary spawn (every 4 hours)
                    if random.random() < 0.01:  # 1% chance
                        legendary = self.get_legendary_pokemon()
                        await self.spawn_pokemon_message(channel, legendary, legendary=True)
    
    @tasks.loop(hours=1)
    async def cleanup_loop(self):
        """Cleanup expired data"""
        # Clean old tickets
        self.db.execute(
            "DELETE FROM tickets WHERE status = 'closed' AND closed_at < datetime('now', '-7 days')"
        )
        
        # Clean old giveaways
        self.db.execute(
            "DELETE FROM giveaways WHERE ended = 1 AND ended_at < datetime('now', '-30 days')"
        )
    
    # ═══════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def spawn_pokemon_message(self, channel, pokemon, legendary=False):
        """Send a spawn message"""
        embed = discord.Embed(
            title=f"🌟 A wild {pokemon['name']} appeared!",
            description=f"Rarity: {pokemon['rarity']}",
            color=discord.Color.gold() if legendary else discord.Color.blue()
        )
        
        if pokemon.get('sprite_url'):
            embed.set_image(url=pokemon['sprite_url'])
        
        embed.set_footer(text="Use /catch to try and catch it!")
        
        # Store spawn info
        self.active_spawns[channel.guild.id] = {
            'pokemon': pokemon,
            'timestamp': datetime.now(),
            'channel_id': channel.id
        }
        
        await channel.send(embed=embed)
    
    def get_legendary_pokemon(self):
        """Get a legendary or mythical Pokémon"""
        legendaries = [p for p in self.pokemon_data.pokemon_list 
                      if p['rarity'] in ['Legendary', 'Mythical']]
        return random.choice(legendaries) if legendaries else self.pokemon_data.get_random_pokemon()
    
    async def handle_antispam(self, message):
        """Handle spam detection"""
        key = f"{message.guild.id}:{message.author.id}"
        current_time = datetime.now()
        
        if key not in self.message_cache:
            self.message_cache[key] = [current_time]
        else:
            # Clean old messages
            self.message_cache[key] = [
                t for t in self.message_cache[key] 
                if (current_time - t).seconds < 5
            ]
            self.message_cache[key].append(current_time)
            
            # Check spam threshold
            if len(self.message_cache[key]) >= 5:
                await self.mute_user(
                    message.guild, 
                    message.author, 
                    "Auto-muted for spamming (5 messages in 5 seconds)"
                )
                await message.delete()
                await message.channel.send(
                    f"🔇 {message.author.mention} has been auto-muted for spamming!"
                )
    
    async def handle_bad_words(self, message):
        """Handle bad word filter"""
        bad_words = self.db.fetch_all(
            "SELECT word FROM bad_words WHERE guild_id = ?",
            (str(message.guild.id),)
        )
        
        bad_word_list = [row['word'].lower() for row in bad_words]
        content = message.content.lower()
        
        for word in bad_word_list:
            if word in content:
                await message.delete()
                await message.channel.send(
                    f"❌ {message.author.mention}, that word is not allowed!"
                )
                break
    
    async def handle_leveling(self, message):
        """Handle XP and leveling"""
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        # Check cooldown (30 seconds between XP)
        cooldown_key = f"{guild_id}:{user_id}"
        if cooldown_key in self.level_cooldown:
            if (datetime.now() - self.level_cooldown[cooldown_key]).seconds < 30:
                return
        
        self.level_cooldown[cooldown_key] = datetime.now()
        
        # Add XP
        xp_gain = random.randint(15, 25)
        self.db.execute(
            """INSERT INTO levels (user_id, guild_id, xp, messages) 
               VALUES (?, ?, ?, 1) 
               ON CONFLICT(user_id, guild_id) 
               DO UPDATE SET 
               xp = xp + ?, 
               messages = messages + 1""",
            (user_id, guild_id, xp_gain, xp_gain)
        )
        
        # Check level up
        level_data = self.db.fetch_one(
            "SELECT xp, level FROM levels WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )
        
        if level_data:
            xp = level_data['xp']
            level = level_data['level']
            next_level_xp = 100 * (level + 1) ** 2
            
            if xp >= next_level_xp:
                # Level up!
                new_level = level + 1
                self.db.execute(
                    "UPDATE levels SET level = ? WHERE user_id = ? AND guild_id = ?",
                    (new_level, user_id, guild_id)
                )
                
                await message.channel.send(
                    f"🎉 {message.author.mention} leveled up to **Level {new_level}**!"
                )
    
    async def mute_user(self, guild, member, reason):
        """Mute a user for 24 hours"""
        # Get or create muted role
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if not muted_role:
            muted_role = await guild.create_role(
                name="Muted",
                permissions=discord.Permissions(send_messages=False, add_reactions=False)
            )
            # Apply to all channels
            for channel in guild.channels:
                await channel.set_permissions(muted_role, send_messages=False, add_reactions=False)
        
        await member.add_roles(muted_role)
        
        # Store in database
        unmute_time = datetime.now() + timedelta(hours=24)
        self.db.insert('muted', {
            'user_id': str(member.id),
            'guild_id': str(guild.id),
            'reason': reason,
            'unmute_at': unmute_time.isoformat()
        })
        
        # DM user
        try:
            await member.send(f"🔇 You have been muted in {guild.name} for: {reason}")
        except:
            pass
    
    async def unmute_user(self, guild, member):
        """Unmute a user"""
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if muted_role and muted_role in member.roles:
            await member.remove_roles(muted_role)
        
        self.db.execute(
            "DELETE FROM muted WHERE user_id = ? AND guild_id = ?",
            (str(member.id), str(guild.id))
        )
    
    def level_cooldown(self):
        """Initialize level cooldown dict"""
        if not hasattr(self, '_level_cooldown'):
            self._level_cooldown = {}
        return self._level_cooldown

# ═══════════════════════════════════════════════════════════════════
# FLASK WEB DASHBOARD
# ═══════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET', secrets.token_hex(32))
CORS(app)

# Global bot instance (will be set later)
bot_instance = None

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard page"""
    if not session.get('user'):
        return redirect(url_for('auth'))
    return render_template('dashboard.html', user=session['user'])

@app.route('/auth')
def auth():
    """Authentication page"""
    return render_template('auth.html')

@app.route('/callback')
def oauth_callback():
    """OAuth2 callback handler"""
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
    
    # Get user info
    headers = {'Authorization': f"Bearer {token_data['access_token']}"}
    user_response = requests.get('https://discord.com/api/users/@me', headers=headers)
    user_data = user_response.json()
    
    # Store user in session
    session['user'] = user_data
    
    # Verify user is in guild
    guilds_response = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
    guilds = guilds_response.json()
    
    if any(str(g['id']) == guild_id for g in guilds):
        # Add verified role to user
        if bot_instance:
            guild = bot_instance.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_data['id']))
                if member:
                    settings = bot_instance.db.fetch_one(
                        "SELECT * FROM guild_settings WHERE guild_id = ?",
                        (guild_id,)
                    )
                    if settings and settings['verified_role_id']:
                        role = guild.get_role(int(settings['verified_role_id']))
                        if role:
                            asyncio.run_coroutine_threadsafe(
                                member.add_roles(role),
                                bot_instance.loop
                            )
                            # Remove unverified role
                            if settings['unverified_role_id']:
                                unverified_role = guild.get_role(int(settings['unverified_role_id']))
                                if unverified_role:
                                    asyncio.run_coroutine_threadsafe(
                                        member.remove_roles(unverified_role),
                                        bot_instance.loop
                                    )
    
    return redirect(url_for('dashboard'))

@app.route('/api/stats')
def api_stats():
    """Get bot statistics"""
    if not bot_instance:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    return jsonify({
        'guilds': len(bot_instance.guilds),
        'users': sum(guild.member_count for guild in bot_instance.guilds),
        'uptime': 'Online',
        'pokemon_caught': bot_instance.db.fetch_one("SELECT COUNT(*) FROM pokemon_collection")[0] or 0
    })

@app.route('/api/pokemon/<user_id>')
def api_user_pokemon(user_id):
    """Get user's Pokémon collection"""
    if not bot_instance:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    collection = bot_instance.db.fetch_all(
        "SELECT * FROM pokemon_collection WHERE user_id = ?",
        (user_id,)
    )
    
    return jsonify([dict(row) for row in collection])

# ═══════════════════════════════════════════════════════════════════
# DISCORD COMMANDS (All in one place)
# ═══════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────
# POKEMON COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="catch", description="Try to catch a wild Pokémon!")
async def catch(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    # Check if user has a pokeball
    balls = db.fetch_all(
        "SELECT * FROM user_inventory WHERE user_id = ? AND guild_id = ? AND item_type = 'pokeball'",
        (user_id, guild_id)
    )
    
    if not balls:
        await interaction.response.send_message(
            "You don't have any Pokéballs! Buy some from the shop with `/shop`",
            ephemeral=True
        )
        return
    
    # Check if there's a spawned Pokémon
    if guild_id not in active_spawns:
        await interaction.response.send_message(
            "No wild Pokémon nearby! Wait for one to spawn.",
            ephemeral=True
        )
        return
    
    spawn = active_spawns[guild_id]
    if (datetime.now() - spawn['timestamp']).seconds > 60:
        del active_spawns[guild_id]
        await interaction.response.send_message(
            "The wild Pokémon ran away!",
            ephemeral=True
        )
        return
    
    pokemon = spawn['pokemon']
    
    # Calculate catch chance
    ball_multiplier = 1.0  # Default pokeball
    for ball in balls:
        if ball['item_id'] == 'pokeball':
            ball_multiplier = 1.0
        elif ball['item_id'] == 'greatball':
            ball_multiplier = 1.5
        elif ball['item_id'] == 'ultraball':
            ball_multiplier = 2.0
        elif ball['item_id'] == 'masterball':
            ball_multiplier = 5.0
    
    rarity_data = pokemon_data.rarities.get(pokemon['rarity'], {'catch_rate': 0.5})
    catch_rate = rarity_data['catch_rate'] * ball_multiplier
    is_shiny = random.random() < 0.02  # 2% shiny chance
    
    caught = random.random() < catch_rate
    
    if caught:
        cp = random.randint(100, 500)
        if is_shiny:
            cp *= 1.5
            shiny_emoji = "✨"
        else:
            shiny_emoji = ""
        
        # Save to database
        db.insert('pokemon_collection', {
            'user_id': user_id,
            'guild_id': guild_id,
            'pokemon_name': pokemon['name'],
            'pokemon_id': pokemon['id'],
            'cp': cp,
            'rarity': pokemon['rarity'],
            'shiny': 1 if is_shiny else 0
        })
        
        # Update user stats
        db.execute(
            """INSERT INTO pokemon_users (user_id, guild_id, catches, total_cp) 
               VALUES (?, ?, 1, ?) 
               ON CONFLICT(user_id, guild_id) 
               DO UPDATE SET 
               catches = catches + 1,
               total_cp = total_cp + ?""",
            (user_id, guild_id, cp, cp)
        )
        
        if is_shiny:
            db.execute(
                "UPDATE pokemon_users SET shiny_catches = shiny_catches + 1 WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
        
        if pokemon['rarity'] in ['Legendary', 'Mythical']:
            db.execute(
                "UPDATE pokemon_users SET legendary_catches = legendary_catches + 1 WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
        
        # Remove spawn
        del active_spawns[guild_id]
        
        await interaction.response.send_message(
            f"🎉 **CAUGHT!** {shiny_emoji} **{pokemon['name']}** (CP: {cp}) {shiny_emoji}\n"
            f"Rarity: {pokemon['rarity']} | Shiny: {'Yes' if is_shiny else 'No'}"
        )
    else:
        await interaction.response.send_message(
            f"❌ The **{pokemon['name']}** escaped! Try using a better ball!"
        )

@bot_instance.tree.command(name="collection", description="View your Pokémon collection")
async def collection(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    collection = db.fetch_all(
        "SELECT * FROM pokemon_collection WHERE user_id = ? AND guild_id = ? ORDER BY cp DESC LIMIT 20",
        (user_id, guild_id)
    )
    
    if not collection:
        await interaction.response.send_message(
            "You haven't caught any Pokémon yet! Use `/catch` to start your journey.",
            ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s Pokémon Collection",
        color=discord.Color.gold()
    )
    
    for pokemon in collection:
        shiny = "✨ " if pokemon['shiny'] else ""
        embed.add_field(
            name=f"{shiny}{pokemon['pokemon_name']}",
            value=f"CP: {pokemon['cp']} | Rarity: {pokemon['rarity']}",
            inline=False
        )
    
    embed.set_footer(text=f"Total: {len(collection)} Pokémon")
    await interaction.response.send_message(embed=embed)

@bot_instance.tree.command(name="shop", description="View the Pokémon shop")
async def shop(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🛒 Pokémon Shop",
        description="Buy items to help you catch Pokémon!",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="Pokéball (50 coins)",
        value="1.0x catch multiplier",
        inline=False
    )
    embed.add_field(
        name="Greatball (100 coins)",
        value="1.5x catch multiplier",
        inline=False
    )
    embed.add_field(
        name="Ultraball (200 coins)",
        value="2.0x catch multiplier",
        inline=False
    )
    embed.add_field(
        name="Masterball (1000 coins)",
        value="5.0x catch multiplier",
        inline=False
    )
    
    embed.set_footer(text="Use /buy <item> to purchase")
    await interaction.response.send_message(embed=embed)

@bot_instance.tree.command(name="buy", description="Buy an item from the shop")
@app_commands.describe(item="The item to buy (pokeball, greatball, ultraball, masterball)")
async def buy(interaction: discord.Interaction, item: str):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    item_prices = {
        'pokeball': 50,
        'greatball': 100,
        'ultraball': 200,
        'masterball': 1000
    }
    
    item = item.lower()
    if item not in item_prices:
        await interaction.response.send_message(
            "Invalid item! Available: pokeball, greatball, ultraball, masterball",
            ephemeral=True
        )
        return
    
    price = item_prices[item]
    
    # Get user coins
    user_data = db.fetch_one(
        "SELECT coins FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    coins = user_data['coins'] if user_data else 0
    
    if coins < price:
        await interaction.response.send_message(
            f"You don't have enough coins! You have {coins} coins, need {price}.",
            ephemeral=True
        )
        return
    
    # Deduct coins
    db.execute(
        "UPDATE pokemon_users SET coins = coins - ? WHERE user_id = ? AND guild_id = ?",
        (price, user_id, guild_id)
    )
    
    # Add item to inventory
    db.insert('user_inventory', {
        'user_id': user_id,
        'guild_id': guild_id,
        'item_id': item,
        'item_type': 'pokeball',
        'quantity': 1
    })
    
    await interaction.response.send_message(
        f"✅ You bought a **{item.capitalize()}** for {price} coins!"
    )

@bot_instance.tree.command(name="daily", description="Claim your daily bonus")
async def daily(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    # Check last daily claim
    last_claim = db.fetch_one(
        "SELECT last_daily FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    if last_claim and last_claim['last_daily']:
        last_time = datetime.fromisoformat(last_claim['last_daily'])
        if (datetime.now() - last_time).days < 1:
            time_left = timedelta(days=1) - (datetime.now() - last_time)
            hours = time_left.seconds // 3600
            minutes = (time_left.seconds % 3600) // 60
            await interaction.response.send_message(
                f"You already claimed your daily bonus! Come back in {hours}h {minutes}m.",
                ephemeral=True
            )
            return
    
    # Give bonus
    coins = random.randint(50, 200)
    bonus_pokemon = random.random() < 0.1  # 10% chance for bonus Pokémon
    
    db.execute(
        """INSERT INTO pokemon_users (user_id, guild_id, coins, last_daily) 
           VALUES (?, ?, ?, ?) 
           ON CONFLICT(user_id, guild_id) 
           DO UPDATE SET 
           coins = coins + ?,
           last_daily = ?""",
        (user_id, guild_id, coins, datetime.now().isoformat(), coins, datetime.now().isoformat())
    )
    
    response = f"🎁 You claimed your daily bonus and received **{coins}** coins!"
    
    if bonus_pokemon:
        # Give random free Pokémon
        pokemon = pokemon_data.get_random_pokemon()
        cp = random.randint(50, 300)
        db.insert('pokemon_collection', {
            'user_id': user_id,
            'guild_id': guild_id,
            'pokemon_name': pokemon['name'],
            'pokemon_id': pokemon['id'],
            'cp': cp,
            'rarity': pokemon['rarity'],
            'shiny': 0
        })
        response += f"\n🎉 Bonus! You also got a **{pokemon['name']}** (CP: {cp})!"
    
    await interaction.response.send_message(response)

# ──────────────────────────────────────────────────────────────────
# VERIFICATION COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="verify", description="Start the verification process")
async def verify(interaction: discord.Interaction):
    oauth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
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
            "To access this server, you need to verify your Discord account.\n\n"
            "Click the button below to start verification. You'll be redirected "
            "to Discord to authorize access.\n\n"
            "**This process is secure and only needs to be done once.**"
        ),
        color=discord.Color.blue()
    )
    
    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="🔐 Verify Now",
            url=auth_url,
            style=discord.ButtonStyle.primary
        )
    )
    
    await interaction.response.send_message(embed=embed, view=view)

@bot_instance.tree.command(name="status", description="Check your verification status")
async def verify_status(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)
    
    verified = db.fetch_one(
        "SELECT * FROM verified_users WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    if verified:
        embed = discord.Embed(
            title="✅ Verification Status",
            description="You are **verified** in this server!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Verified At",
            value=verified['verified_at'],
            inline=False
        )
    else:
        embed = discord.Embed(
            title="❌ Verification Status",
            description="You are **not verified** in this server. Use `/verify` to start.",
            color=discord.Color.red()
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot_instance.tree.command(name="setup_guide", description="Show setup guide")
async def setup_guide(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📖 Server Setup Guide",
        description="How to set up the Anion bot in your server",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="1️⃣ Set Roles",
        value=(
            "`/set_verified_role @role` - Set the verified role\n"
            "`/set_unverified_role @role` - Set the unverified role"
        ),
        inline=False
    )
    
    embed.add_field(
        name="2️⃣ Set Channels",
        value=(
            "`/set_log_channel #channel` - Set log channel\n"
            "`/set_welcome_channel #channel` - Set welcome channel\n"
            "`/set_goodbye_channel #channel` - Set goodbye channel"
        ),
        inline=False
    )
    
    embed.add_field(
        name="3️⃣ Pokémon Setup",
        value=(
            "`/poke_setup` - Setup Pokémon channels\n"
            "`/spawn_pokemon <name> #channel` - Spawn Pokémon"
        ),
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

@bot_instance.tree.command(name="ban", description="Ban a member")
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(member="The member to ban", reason="Reason for the ban")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(
            f"🔨 **{member.display_name}** has been banned. Reason: {reason}"
        )
        
        # Log to channel
        await log_action(interaction.guild, "Ban", member, interaction.user, reason)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

@bot_instance.tree.command(name="kick", description="Kick a member")
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(member="The member to kick", reason="Reason for the kick")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(
            f"👢 **{member.display_name}** has been kicked. Reason: {reason}"
        )
        await log_action(interaction.guild, "Kick", member, interaction.user, reason)
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

@bot_instance.tree.command(name="mute", description="Mute a member for 24 hours")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(member="The member to mute", reason="Reason for the mute")
async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await bot_instance.mute_user(interaction.guild, member, reason)
    await interaction.response.send_message(
        f"🔇 **{member.display_name}** has been muted for 24 hours. Reason: {reason}"
    )
    await log_action(interaction.guild, "Mute", member, interaction.user, reason)

@bot_instance.tree.command(name="unmute", description="Unmute a member")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(member="The member to unmute")
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await bot_instance.unmute_user(interaction.guild, member)
    await interaction.response.send_message(
        f"🔊 **{member.display_name}** has been unmuted."
    )

@bot_instance.tree.command(name="warn", description="Warn a member (3 warns = auto-mute)")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(member="The member to warn", reason="Reason for the warning")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    guild_id = str(interaction.guild.id)
    user_id = str(member.id)
    
    # Add warning
    db.insert('warnings', {
        'user_id': user_id,
        'guild_id': guild_id,
        'moderator_id': str(interaction.user.id),
        'reason': reason
    })
    
    # Check warning count
    warnings = db.fetch_all(
        "SELECT * FROM warnings WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    await interaction.response.send_message(
        f"⚠️ **{member.display_name}** has been warned. Reason: {reason}\n"
        f"Warnings: {len(warnings)}/3"
    )
    
    # Auto-mute at 3 warnings
    if len(warnings) >= 3:
        await bot_instance.mute_user(interaction.guild, member, "Auto-muted for 3 warnings")
        await interaction.followup.send(
            f"🔇 **{member.display_name}** has been auto-muted for reaching 3 warnings."
        )

@bot_instance.tree.command(name="clear", description="Clear messages")
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(amount="Number of messages to clear")
async def clear(interaction: discord.Interaction, amount: int = 10):
    if amount > 100:
        await interaction.response.send_message("Maximum 100 messages!", ephemeral=True)
        return
    
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"🗑️ Cleared {amount} messages!", ephemeral=True)

@bot_instance.tree.command(name="add_badword", description="Add a bad word to the filter")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(word="The word to add")
async def add_badword(interaction: discord.Interaction, word: str):
    guild_id = str(interaction.guild.id)
    
    db.insert('bad_words', {
        'word': word.lower(),
        'guild_id': guild_id
    })
    
    await interaction.response.send_message(
        f"✅ Added `{word}` to the bad words list."
    )

@bot_instance.tree.command(name="remove_badword", description="Remove a bad word from the filter")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(word="The word to remove")
async def remove_badword(interaction: discord.Interaction, word: str):
    guild_id = str(interaction.guild.id)
    
    db.execute(
        "DELETE FROM bad_words WHERE word = ? AND guild_id = ?",
        (word.lower(), guild_id)
    )
    
    await interaction.response.send_message(
        f"✅ Removed `{word}` from the bad words list."
    )

@bot_instance.tree.command(name="badwords", description="List all bad words")
@app_commands.default_permissions(administrator=True)
async def list_badwords(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    words = db.fetch_all(
        "SELECT word FROM bad_words WHERE guild_id = ?",
        (guild_id,)
    )
    
    if not words:
        await interaction.response.send_message("No bad words configured.")
        return
    
    word_list = "\n".join([f"• {row['word']}" for row in words])
    embed = discord.Embed(
        title="🚫 Bad Words List",
        description=word_list,
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)

# ──────────────────────────────────────────────────────────────────
# TICKET COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="ticket", description="Create a support ticket")
@app_commands.describe(reason="Reason for the ticket")
async def ticket(interaction: discord.Interaction, reason: str = "No reason provided"):
    guild = interaction.guild
    user = interaction.user
    
    # Check if user already has an open ticket
    existing = db.fetch_one(
        "SELECT * FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'",
        (str(user.id), str(guild.id))
    )
    
    if existing:
        await interaction.response.send_message(
            f"You already have an open ticket! Please close it first.",
            ephemeral=True
        )
        return
    
    # Create ticket channel
    ticket_id = f"ticket-{random.randint(100, 999)}"
    category = discord.utils.get(guild.categories, name="Tickets")
    
    if not category:
        category = await guild.create_category("Tickets")
    
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    # Add admin role if exists
    admin_role = discord.utils.get(guild.roles, name="Admin")
    if admin_role:
        overwrites[admin_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    
    # Create channel
    channel = await guild.create_text_channel(
        f"🎫-{ticket_id}",
        category=category,
        overwrites=overwrites,
        topic=f"Ticket created by {user.display_name} | Reason: {reason}"
    )
    
    # Save to database
    db.insert('tickets', {
        'ticket_id': ticket_id,
        'guild_id': str(guild.id),
        'user_id': str(user.id),
        'channel_id': str(channel.id),
        'reason': reason
    })
    
    # Send initial message
    embed = discord.Embed(
        title="🎫 Support Ticket",
        description=f"Ticket created by {user.mention}\n**Reason:** {reason}",
        color=discord.Color.blue()
    )
    
    # Create ticket controls
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="➕ Add User", style=discord.ButtonStyle.success, custom_id="ticket_add"))
    view.add_item(discord.ui.Button(label="➖ Remove User", style=discord.ButtonStyle.danger, custom_id="ticket_remove"))
    view.add_item(discord.ui.Button(label="📝 Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript"))
    view.add_item(discord.ui.Button(label="🔒 Close", style=discord.ButtonStyle.primary, custom_id="ticket_close"))
    
    await channel.send(embed=embed, view=view)
    
    await interaction.response.send_message(
        f"✅ Ticket created: {channel.mention}",
        ephemeral=True
    )

@bot_instance.tree.command(name="setup_ticket", description="Setup ticket system")
@app_commands.default_permissions(administrator=True)
async def setup_ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Ticket System",
        description="Click the button below to create a ticket.",
        color=discord.Color.blue()
    )
    
    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="🎫 Create Ticket",
            style=discord.ButtonStyle.primary,
            custom_id="create_ticket"
        )
    )
    
    await interaction.response.send_message(embed=embed, view=view)
    await interaction.followup.send("✅ Ticket system setup complete!")

@bot_instance.tree.command(name="close", description="Close the current ticket")
async def close_ticket(interaction: discord.Interaction):
    # Check if channel is a ticket
    ticket = db.fetch_one(
        "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
        (str(interaction.channel.id),)
    )
    
    if not ticket:
        await interaction.response.send_message(
            "This is not a ticket channel!",
            ephemeral=True
        )
        return
    
    # Close ticket
    db.execute(
        "UPDATE tickets SET status = 'closed', closed_at = ? WHERE channel_id = ?",
        (datetime.now().isoformat(), str(interaction.channel.id))
    )
    
    await interaction.response.send_message("🔒 Ticket closed!")
    
    # Clean up channel after delay
    await asyncio.sleep(10)
    await interaction.channel.delete()

# ──────────────────────────────────────────────────────────────────
# LEVELING COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="rank", description="Check your rank")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    user_id = str(target.id)
    guild_id = str(interaction.guild.id)
    
    data = db.fetch_one(
        "SELECT * FROM levels WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id)
    )
    
    if not data:
        await interaction.response.send_message(
            f"{target.display_name} hasn't sent any messages yet!"
        )
        return
    
    # Get rank
    rank_result = db.fetch_one(
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
    embed.add_field(name="Rank", value=f"#{rank_result['rank']}", inline=True)
    
    # XP progress
    next_level_xp = 100 * (data['level'] + 1) ** 2
    current_level_xp = 100 * data['level'] ** 2
    progress = (data['xp'] - current_level_xp) / (next_level_xp - current_level_xp) * 100
    
    embed.add_field(
        name="Progress",
        value=f"🟩{'🟩' * int(progress/10)}{'⬜' * (10 - int(progress/10))} {progress:.1f}%",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@bot_instance.tree.command(name="leaderboard", description="View server leaderboard")
async def leaderboard(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    leaderboard_data = db.fetch_all(
        "SELECT user_id, xp, level FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
        (guild_id,)
    )
    
    if not leaderboard_data:
        await interaction.response.send_message("No data yet!")
        return
    
    embed = discord.Embed(
        title=f"🏆 {interaction.guild.name} Leaderboard",
        color=discord.Color.gold()
    )
    
    for i, entry in enumerate(leaderboard_data, 1):
        member = interaction.guild.get_member(int(entry['user_id']))
        if member:
            embed.add_field(
                name=f"#{i} {member.display_name}",
                value=f"Level {entry['level']} | {entry['xp']} XP",
                inline=False
            )
    
    await interaction.response.send_message(embed=embed)

# ──────────────────────────────────────────────────────────────────
# GIVEAWAY COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="giveaway", description="Start a giveaway")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    prize="The prize to give away",
    duration="Duration (1h, 1d, 30m, etc.)",
    winners="Number of winners"
)
async def giveaway(interaction: discord.Interaction, prize: str, duration: str, winners: int = 1):
    # Parse duration
    duration_map = {
        's': 1, 'm': 60, 'h': 3600, 'd': 86400
    }
    
    try:
        unit = duration[-1].lower()
        value = int(duration[:-1])
        seconds = value * duration_map[unit]
    except:
        await interaction.response.send_message(
            "Invalid duration format! Use: 30s, 5m, 1h, 2d",
            ephemeral=True
        )
        return
    
    if seconds > 7 * 86400:  # 7 days max
        await interaction.response.send_message("Giveaway can't be longer than 7 days!", ephemeral=True)
        return
    
    if winners > 10:
        await interaction.response.send_message("Maximum 10 winners!", ephemeral=True)
        return
    
    end_time = datetime.now() + timedelta(seconds=seconds)
    
    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.purple()
    )
    
    embed.set_footer(text="React with 🎉 to enter!")
    
    message = await interaction.channel.send(embed=embed)
    await message.add_reaction("🎉")
    
    # Save to database
    db.insert('giveaways', {
        'message_id': str(message.id),
        'channel_id': str(interaction.channel.id),
        'guild_id': str(interaction.guild.id),
        'prize': prize,
        'winners': winners,
        'ended_at': end_time.isoformat()
    })
    
    await interaction.response.send_message(
        f"✅ Giveaway started! Ends in {duration}",
        ephemeral=True
    )

@bot_instance.tree.command(name="reroll", description="Reroll a giveaway")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(message_id="The ID of the giveaway message")
async def reroll(interaction: discord.Interaction, message_id: str):
    try:
        message_id_int = int(message_id)
        message = await interaction.channel.fetch_message(message_id_int)
        
        # Get reactions
        reaction = discord.utils.get(message.reactions, emoji="🎉")
        if not reaction:
            await interaction.response.send_message("No 🎉 reactions found!", ephemeral=True)
            return
        
        users = []
        async for user in reaction.users():
            if not user.bot:
                users.append(user)
        
        if not users:
            await interaction.response.send_message("No valid participants!", ephemeral=True)
            return
        
        # Pick winners
        winners_count = 1
        giveaway_data = db.fetch_one(
            "SELECT winners FROM giveaways WHERE message_id = ?",
            (message_id,)
        )
        if giveaway_data:
            winners_count = giveaway_data['winners']
        
        winners = random.sample(users, min(winners_count, len(users)))
        
        await interaction.response.send_message(
            f"🎉 New winners: {', '.join([w.mention for w in winners])}!"
        )
    except Exception as e:
        await interaction.response.send_message(f"Error: {e}", ephemeral=True)

# ──────────────────────────────────────────────────────────────────
# MUSIC COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="play", description="Play a song")
@app_commands.describe(url="URL of the song to play")
async def play(interaction: discord.Interaction, url: str):
    if not interaction.user.voice:
        await interaction.response.send_message(
            "You need to be in a voice channel!",
            ephemeral=True
        )
        return
    
    voice_channel = interaction.user.voice.channel
    
    # Check if already in voice
    if interaction.guild.id not in bot_instance.voice_clients:
        voice_client = await voice_channel.connect()
        bot_instance.voice_clients[interaction.guild.id] = voice_client
    else:
        voice_client = bot_instance.voice_clients[interaction.guild.id]
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    
    await interaction.response.send_message(
        f"🎵 Searching for: {url}...",
        ephemeral=True
    )
    
    # Download audio
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
            
            # Play audio
            voice_client.play(
                discord.FFmpegPCMAudio(url2),
                after=lambda e: print(f'Player error: {e}') if e else None
            )
            
            await interaction.followup.send(f"▶️ Now playing: **{info['title']}**")
    except Exception as e:
        await interaction.followup.send(f"Error playing: {e}")

@bot_instance.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    if interaction.guild.id in bot_instance.voice_clients:
        voice_client = bot_instance.voice_clients[interaction.guild.id]
        if voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped the current song!")
        else:
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
    else:
        await interaction.response.send_message("Not in a voice channel!", ephemeral=True)

@bot_instance.tree.command(name="stop", description="Stop music and leave voice")
async def stop(interaction: discord.Interaction):
    if interaction.guild.id in bot_instance.voice_clients:
        voice_client = bot_instance.voice_clients[interaction.guild.id]
        await voice_client.disconnect()
        del bot_instance.voice_clients[interaction.guild.id]
        await interaction.response.send_message("⏹️ Stopped music and left voice!")
    else:
        await interaction.response.send_message("Not in a voice channel!", ephemeral=True)

# ──────────────────────────────────────────────────────────────────
# AI COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="ai", description="Chat with AI")
@app_commands.describe(message="Your message to the AI")
async def ai_chat(interaction: discord.Interaction, message: str):
    if not OPENAI_KEY:
        await interaction.response.send_message(
            "AI is not configured! Please set OPENAI_KEY.",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        openai.api_key = OPENAI_KEY
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful Discord bot named Anion."},
                {"role": "user", "content": message}
            ]
        )
        await interaction.followup.send(f"🤖 {response.choices[0].message.content}")
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# ──────────────────────────────────────────────────────────────────
# UTILITY COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    latency = round(interaction.client.latency * 1000)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {latency}ms",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

@bot_instance.tree.command(name="serverinfo", description="Get server information")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    
    embed = discord.Embed(
        title=f"📊 {guild.name}",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot_instance.tree.command(name="userinfo", description="Get user information")
@app_commands.describe(member="The member to get info about")
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
    embed.add_field(name="Roles", value=", ".join([r.name for r in target.roles if r.name != "@everyone"])[:100] or "None", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot_instance.tree.command(name="list_all", description="Show all commands")
async def list_all(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📋 All Commands",
        description="Complete list of Anion bot commands",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="🎮 Pokémon",
        value=(
            "`/catch` - Catch a Pokémon\n"
            "`/collection` - View collection\n"
            "`/shop` - View shop\n"
            "`/buy` - Buy items\n"
            "`/daily` - Daily bonus\n"
            "`/pokedex` - Pokédex progress"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔐 Verification",
        value=(
            "`/verify` - Start verification\n"
            "`/status` - Check status"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🛡️ Moderation",
        value=(
            "`/ban` - Ban member\n"
            "`/kick` - Kick member\n"
            "`/mute` - Mute member\n"
            "`/warn` - Warn member\n"
            "`/clear` - Clear messages"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎫 Tickets",
        value=(
            "`/ticket` - Create ticket\n"
            "`/close` - Close ticket"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📈 Leveling",
        value=(
            "`/rank` - Check rank\n"
            "`/leaderboard` - View leaderboard"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎁 Giveaways",
        value=(
            "`/giveaway` - Start giveaway\n"
            "`/reroll` - Reroll giveaway"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎵 Music",
        value=(
            "`/play` - Play music\n"
            "`/skip` - Skip song\n"
            "`/stop` - Stop music"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🤖 AI",
        value="`/ai` - Chat with AI",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Utility",
        value=(
            "`/ping` - Check latency\n"
            "`/serverinfo` - Server info\n"
            "`/userinfo` - User info"
        ),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

# ──────────────────────────────────────────────────────────────────
# ADMIN COMMANDS
# ──────────────────────────────────────────────────────────────────

@bot_instance.tree.command(name="set_verified_role", description="Set the verified role")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(role="The role to assign to verified users")
async def set_verified_role(interaction: discord.Interaction, role: discord.Role):
    guild_id = str(interaction.guild.id)
    
    db.insert('guild_settings', {
        'guild_id': guild_id,
        'verified_role_id': str(role.id)
    })
    
    await interaction.response.send_message(
        f"✅ Verified role set to {role.mention}"
    )

@bot_instance.tree.command(name="set_unverified_role", description="Set the unverified role")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(role="The role for unverified users")
async def set_unverified_role(interaction: discord.Interaction, role: discord.Role):
    guild_id = str(interaction.guild.id)
    
    db.update('guild_settings', 
              {'unverified_role_id': str(role.id)},
              {'guild_id': guild_id})
    
    await interaction.response.send_message(
        f"✅ Unverified role set to {role.mention}"
    )

@bot_instance.tree.command(name="set_log_channel", description="Set the log channel")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(channel="The channel for logs")
async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = str(interaction.guild.id)
    
    db.insert('guild_settings', {
        'guild_id': guild_id,
        'log_channel_id': str(channel.id)
    })
    
    await interaction.response.send_message(
        f"✅ Log channel set to {channel.mention}"
    )

@bot_instance.tree.command(name="poke_setup", description="Setup Pokémon channels")
@app_commands.default_permissions(administrator=True)
async def poke_setup(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    
    # Create Pokémon channel
    category = discord.utils.get(interaction.guild.categories, name="Pokémon")
    if not category:
        category = await interaction.guild.create_category("Pokémon")
    
    channel = await interaction.guild.create_text_channel(
        "pokémon-spawns",
        category=category
    )
    
    db.insert('pokemon_settings', {
        'guild_id': guild_id,
        'channel_id': str(channel.id)
    })
    
    await interaction.response.send_message(
        f"✅ Pokémon setup complete! Spawns will appear in {channel.mention}"
    )

@bot_instance.tree.command(name="spawn_pokemon", description="Spawn any Pokémon")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(name="Name of the Pokémon to spawn", channel="Channel to spawn in")
async def spawn_pokemon(interaction: discord.Interaction, name: str, channel: discord.TextChannel):
    pokemon = bot_instance.pokemon_data.get_pokemon_by_name(name)
    
    if not pokemon:
        await interaction.response.send_message(
            f"Pokémon `{name}` not found!",
            ephemeral=True
        )
        return
    
    await bot_instance.spawn_pokemon_message(channel, pokemon)
    
    await interaction.response.send_message(
        f"✅ Spawned {pokemon['name']} in {channel.mention}"
    )

# ═══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

async def log_action(guild, action, target, moderator, reason):
    """Log moderation actions"""
    settings = bot_instance.db.fetch_one(
        "SELECT log_channel_id FROM guild_settings WHERE guild_id = ?",
        (str(guild.id),)
    )
    
    if settings and settings['log_channel_id']:
        channel = guild.get_channel(int(settings['log_channel_id']))
        if channel:
            embed = discord.Embed(
                title=f"📋 {action}",
                description=f"**Target:** {target.mention}\n**Moderator:** {moderator.mention}\n**Reason:** {reason}",
                color=discord.Color.red() if action in ['Ban', 'Kick'] else discord.Color.orange()
            )
            await channel.send(embed=embed)

# ═══════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════

async def main():
    """Main entry point"""
    global bot_instance
    
    # Create bot instance
    bot_instance = AnionBot()
    
    # Start Flask in a separate thread
    import threading
    flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 5000})
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start the bot
    await bot_instance.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
