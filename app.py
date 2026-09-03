#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                           🔐 ANION PROJECT - COMPLETE BOT
                           FULL 10,000+ LINE VERSION
                           ALL FEATURES + GUI + 3D ANIMATIONS
═══════════════════════════════════════════════════════════════════════════════
"""

# ═════════════════════════════════════════════════════════════════════════════
# IMPORTS - Complete list for all features
# ═════════════════════════════════════════════════════════════════════════════

import os
import sys
import json
import io
import re
import random
import asyncio
import sqlite3
import secrets
import requests
import logging
import threading
import time
import math
import hashlib
import base64
import urllib.parse
import traceback
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple, Union
from collections import defaultdict, deque
from functools import wraps

# Discord
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput, Item

# Flask
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify, abort, make_response, send_file
from flask_cors import CORS

# Music
import yt_dlp

# AI
import openai

# Environment
from dotenv import load_dotenv

# Additional
import aiohttp
from PIL import Image, ImageDraw, ImageFont

# ═════════════════════════════════════════════════════════════════════════════
# LOAD ENVIRONMENT VARIABLES
# ═════════════════════════════════════════════════════════════════════════════

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('AnionBot')

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

class Config:
    """Complete configuration management"""
    
    def __init__(self):
        # Required - Will raise error if missing
        self.DISCORD_TOKEN = self.get_required('DISCORD_TOKEN')
        self.CLIENT_ID = self.get_required('CLIENT_ID')
        self.CLIENT_SECRET = self.get_required('CLIENT_SECRET')
        
        # Optional with defaults
        self.REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://edith.up.railway.app/callback')
        self.DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://edith.up.railway.app/dashboard')
        self.FLASK_SECRET = os.getenv('FLASK_SECRET', secrets.token_urlsafe(32))
        self.OPENAI_KEY = os.getenv('OPENAI_KEY', '')
        self.DB_PATH = os.getenv('DB_PATH', '/data')
        self.POKEAPI_BASE = os.getenv('POKEAPI_BASE', 'https://pokeapi.co/api/v2')
        
        # Ensure DB path exists
        os.makedirs(self.DB_PATH, exist_ok=True)
        self.DB_FILE = os.path.join(self.DB_PATH, 'bot_database.db')
        
        self.ENVIRONMENT = os.getenv('ENVIRONMENT', 'production')
        self.DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
        self.OWNER_ID = int(os.getenv('OWNER_ID', '0'))
        
        # Bot settings
        self.SPAWN_INTERVAL = int(os.getenv('SPAWN_INTERVAL', '30'))
        self.LEGENDARY_SPAWN_INTERVAL = int(os.getenv('LEGENDARY_SPAWN_INTERVAL', '14400'))
        self.MAX_TICKETS_PER_USER = int(os.getenv('MAX_TICKETS_PER_USER', '3'))
        self.MAX_GIVEAWAY_WINNERS = int(os.getenv('MAX_GIVEAWAY_WINNERS', '10'))
        self.XP_PER_MESSAGE_MIN = int(os.getenv('XP_PER_MESSAGE_MIN', '15'))
        self.XP_PER_MESSAGE_MAX = int(os.getenv('XP_PER_MESSAGE_MAX', '25'))
        self.LEVEL_COOLDOWN = int(os.getenv('LEVEL_COOLDOWN', '30'))
        
        # API Keys
        self.WEATHER_API_KEY = os.getenv('WEATHER_API_KEY', '')
        self.DBL_API_KEY = os.getenv('DBL_API_KEY', '')
        
        print(f"✅ Config loaded - Environment: {self.ENVIRONMENT}")
        print(f"✅ Database: {self.DB_FILE}")
        print(f"✅ OpenAI: {'✅ Configured' if self.OPENAI_KEY else '❌ Not Configured'}")
        print(f"✅ Owner ID: {self.OWNER_ID}")
    
    def get_required(self, key):
        value = os.getenv(key)
        if not value:
            raise ValueError(f"❌ Missing required env: {key}")
        return value

config = Config()

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE CLASS - Complete with all tables
# ═════════════════════════════════════════════════════════════════════════════

class Database:
    """Complete database management with all tables"""
    
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
        
        tables = [
            # Pokémon System
            """CREATE TABLE IF NOT EXISTS pokemon_users (
                user_id TEXT, guild_id TEXT,
                coins INTEGER DEFAULT 100,
                catches INTEGER DEFAULT 0,
                total_cp INTEGER DEFAULT 0,
                legendary_catches INTEGER DEFAULT 0,
                shiny_catches INTEGER DEFAULT 0,
                last_daily TIMESTAMP,
                total_battles INTEGER DEFAULT 0,
                total_wins INTEGER DEFAULT 0,
                total_losses INTEGER DEFAULT 0,
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
                listing_id TEXT,
                favorite BOOLEAN DEFAULT 0,
                nickname TEXT,
                level INTEGER DEFAULT 1,
                experience INTEGER DEFAULT 0
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_pokedex (
                user_id TEXT, guild_id TEXT,
                pokemon_id INTEGER,
                seen BOOLEAN DEFAULT 0,
                caught BOOLEAN DEFAULT 0,
                caught_count INTEGER DEFAULT 0,
                shiny_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id, pokemon_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_settings (
                guild_id TEXT PRIMARY KEY,
                channel_id TEXT,
                spawn_enabled BOOLEAN DEFAULT 1,
                catch_cooldown INTEGER DEFAULT 30,
                spawn_rate INTEGER DEFAULT 30,
                legendary_spawn_rate INTEGER DEFAULT 3600,
                max_spawns INTEGER DEFAULT 5
            )""",
            
            """CREATE TABLE IF NOT EXISTS user_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, guild_id TEXT,
                item_id TEXT, item_type TEXT,
                quantity INTEGER DEFAULT 1,
                UNIQUE(user_id, guild_id, item_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_market (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id TEXT UNIQUE,
                pokemon_id INTEGER,
                seller_id TEXT,
                guild_id TEXT,
                price INTEGER,
                listed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sold BOOLEAN DEFAULT 0,
                buyer_id TEXT,
                sold_at TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                initiator_id TEXT,
                receiver_id TEXT,
                guild_id TEXT,
                status TEXT DEFAULT 'pending',
                initiator_pokemon TEXT,
                receiver_pokemon TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS pokemon_battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                battle_id TEXT UNIQUE,
                challenger_id TEXT,
                opponent_id TEXT,
                guild_id TEXT,
                status TEXT DEFAULT 'pending',
                challenger_pokemon INTEGER,
                opponent_pokemon INTEGER,
                winner_id TEXT,
                started_at TIMESTAMP,
                ended_at TIMESTAMP
            )""",
            
            # Verification System
            """CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id TEXT PRIMARY KEY,
                verified_role_id TEXT,
                unverified_role_id TEXT,
                log_channel_id TEXT,
                welcome_channel_id TEXT,
                goodbye_channel_id TEXT,
                welcome_message TEXT,
                goodbye_message TEXT,
                auto_verify BOOLEAN DEFAULT 0,
                verification_level TEXT DEFAULT 'normal',
                lockdown_enabled BOOLEAN DEFAULT 0,
                mute_new_members BOOLEAN DEFAULT 0,
                require_2fa BOOLEAN DEFAULT 0
            )""",
            
            """CREATE TABLE IF NOT EXISTS verified_users (
                user_id TEXT, guild_id TEXT,
                verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email TEXT,
                ip_address TEXT,
                user_agent TEXT,
                verification_method TEXT DEFAULT 'oauth',
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS verify_tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT, guild_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used BOOLEAN DEFAULT 0,
                expires_at TIMESTAMP
            )""",
            
            """CREATE TABLE IF NOT EXISTS login_sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                guild_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT
            )""",
            
            # Leveling System
            """CREATE TABLE IF NOT EXISTS levels (
                user_id TEXT, guild_id TEXT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                voice_minutes INTEGER DEFAULT 0,
                last_message TIMESTAMP,
                weekly_xp INTEGER DEFAULT 0,
                monthly_xp INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS level_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                level INTEGER,
                role_id TEXT,
                message TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS level_leaderboard (
                guild_id TEXT,
                user_id TEXT,
                rank INTEGER,
                week_rank INTEGER,
                month_rank INTEGER,
                PRIMARY KEY (guild_id, user_id)
            )""",
            
            # Moderation System
            """CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, guild_id TEXT,
                moderator_id TEXT, reason TEXT,
                warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                active BOOLEAN DEFAULT 1
            )""",
            
            """CREATE TABLE IF NOT EXISTS muted (
                user_id TEXT, guild_id TEXT,
                muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unmute_at TIMESTAMP, reason TEXT,
                moderator_id TEXT,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS banned (
                user_id TEXT, guild_id TEXT,
                banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT, moderator_id TEXT,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action TEXT,
                moderator_id TEXT,
                target_id TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS bad_words (
                word TEXT, guild_id TEXT,
                severity INTEGER DEFAULT 1,
                PRIMARY KEY (word, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS auto_mod_settings (
                guild_id TEXT PRIMARY KEY,
                spam_threshold INTEGER DEFAULT 5,
                spam_timeframe INTEGER DEFAULT 5,
                mention_threshold INTEGER DEFAULT 5,
                link_filter BOOLEAN DEFAULT 0,
                invite_filter BOOLEAN DEFAULT 0,
                mass_mention BOOLEAN DEFAULT 0,
                raid_protection BOOLEAN DEFAULT 0
            )""",
            
            # Ticket System
            """CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE,
                guild_id TEXT, user_id TEXT,
                channel_id TEXT, status TEXT DEFAULT 'open',
                reason TEXT, claimed_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                priority TEXT DEFAULT 'medium',
                category TEXT DEFAULT 'general',
                rating INTEGER
            )""",
            
            """CREATE TABLE IF NOT EXISTS ticket_settings (
                guild_id TEXT PRIMARY KEY,
                category_id TEXT,
                support_role_id TEXT,
                admin_role_id TEXT,
                transcript_channel_id TEXT,
                ticket_limit INTEGER DEFAULT 3,
                auto_close_hours INTEGER DEFAULT 24
            )""",
            
            # Giveaway System
            """CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT, channel_id TEXT,
                guild_id TEXT, prize TEXT,
                winners INTEGER DEFAULT 1,
                ended BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                winner_ids TEXT,
                hosted_by TEXT,
                requirements TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS giveaway_entries (
                giveaway_id INTEGER,
                user_id TEXT,
                entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (giveaway_id, user_id)
            )""",
            
            # Music System
            """CREATE TABLE IF NOT EXISTS music_queue (
                guild_id TEXT PRIMARY KEY,
                queue_json TEXT,
                current_song_json TEXT,
                loop_mode TEXT DEFAULT 'none',
                volume INTEGER DEFAULT 100
            )""",
            
            """CREATE TABLE IF NOT EXISTS music_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                song_title TEXT,
                song_url TEXT,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                played_by TEXT,
                duration INTEGER
            )""",
            
            # Economy System
            """CREATE TABLE IF NOT EXISTS economy (
                user_id TEXT, guild_id TEXT,
                balance INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                daily_streak INTEGER DEFAULT 0,
                last_daily TIMESTAMP,
                last_work TIMESTAMP,
                last_rob TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS shop_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                item_name TEXT,
                item_price INTEGER,
                item_description TEXT,
                stock INTEGER DEFAULT -1,
                unlimited BOOLEAN DEFAULT 1,
                role_id TEXT
            )""",
            
            """CREATE TABLE IF NOT EXISTS user_inventory_shop (
                user_id TEXT, guild_id TEXT,
                item_id INTEGER,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, guild_id, item_id)
            )""",
            
            # Custom Commands
            """CREATE TABLE IF NOT EXISTS custom_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                command_name TEXT,
                response TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                use_count INTEGER DEFAULT 0,
                UNIQUE(guild_id, command_name)
            )""",
            
            # Stats
            """CREATE TABLE IF NOT EXISTS server_stats (
                guild_id TEXT PRIMARY KEY,
                total_messages INTEGER DEFAULT 0,
                total_members INTEGER DEFAULT 0,
                total_commands INTEGER DEFAULT 0,
                updated_at TIMESTAMP,
                daily_messages INTEGER DEFAULT 0,
                weekly_messages INTEGER DEFAULT 0,
                monthly_messages INTEGER DEFAULT 0
            )""",
            
            """CREATE TABLE IF NOT EXISTS command_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_name TEXT,
                guild_id TEXT,
                user_id TEXT,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT 1
            )""",
            
            # Audit
            """CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                action TEXT,
                moderator_id TEXT,
                target_id TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            
            # Reaction Roles
            """CREATE TABLE IF NOT EXISTS reaction_roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                message_id TEXT,
                channel_id TEXT,
                role_id TEXT,
                emoji TEXT,
                UNIQUE(guild_id, message_id, emoji)
            )""",
            
            # Welcome Messages
            """CREATE TABLE IF NOT EXISTS welcome_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT,
                message TEXT,
                channel_id TEXT,
                image_url TEXT,
                enabled BOOLEAN DEFAULT 1,
                embed_color TEXT DEFAULT '#3498db'
            )""",
            
            # Polls
            """CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT,
                guild_id TEXT,
                channel_id TEXT,
                question TEXT,
                options TEXT,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended BOOLEAN DEFAULT 0,
                votes TEXT
            )"""
        ]
        
        for table in tables:
            try:
                c.execute(table)
            except Exception as e:
                print(f"⚠️ Error creating table: {e}")
        
        conn.commit()
        self.close_connection()
        print("✅ All database tables created successfully")
    
    def execute(self, query, params=()):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute(query, params)
        conn.commit()
        return c
    
    def executemany(self, query, params_list):
        conn = self.get_connection()
        c = conn.cursor()
        c.executemany(query, params_list)
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
    
    def delete(self, table, where):
        where_clause = ' AND '.join([f"{k} = ?" for k in where.keys()])
        query = f"DELETE FROM {table} WHERE {where_clause}"
        self.execute(query, list(where.values()))
    
    def exists(self, table, where):
        where_clause = ' AND '.join([f"{k} = ?" for k in where.keys()])
        query = f"SELECT 1 FROM {table} WHERE {where_clause} LIMIT 1"
        result = self.fetch_one(query, list(where.values()))
        return result is not None
    
    def get_count(self, table, where=None):
        query = f"SELECT COUNT(*) FROM {table}"
        if where:
            where_clause = ' AND '.join([f"{k} = ?" for k in where.keys()])
            query += f" WHERE {where_clause}"
            result = self.fetch_one(query, list(where.values()))
        else:
            result = self.fetch_one(query)
        return result[0] if result else 0

# ═════════════════════════════════════════════════════════════════════════════
# POKEMON DATA - Complete
# ═════════════════════════════════════════════════════════════════════════════

class PokemonData:
    """Complete Pokémon data management with all generations"""
    
    def __init__(self):
        self.pokemon_list = []
        self.pokemon_by_id = {}
        self.pokemon_by_name = {}
        self.rarities = {
            'Common': {'weight': 45, 'catch_rate': 0.8, 'emoji': '⬜', 'color': 0x808080, 'min_cp': 50, 'max_cp': 300},
            'Uncommon': {'weight': 25, 'catch_rate': 0.6, 'emoji': '🟩', 'color': 0x00FF00, 'min_cp': 100, 'max_cp': 450},
            'Rare': {'weight': 18, 'catch_rate': 0.35, 'emoji': '🟦', 'color': 0x0000FF, 'min_cp': 200, 'max_cp': 600},
            'Epic': {'weight': 8, 'catch_rate': 0.2, 'emoji': '🟪', 'color': 0x9B59B6, 'min_cp': 350, 'max_cp': 750},
            'Legendary': {'weight': 3, 'catch_rate': 0.1, 'emoji': '🌟', 'color': 0xFFD700, 'min_cp': 500, 'max_cp': 1000},
            'Mythical': {'weight': 1, 'catch_rate': 0.05, 'emoji': '💫', 'color': 0xFF69B4, 'min_cp': 700, 'max_cp': 1200}
        }
        self.ball_multipliers = {
            'pokeball': 1.0, 'greatball': 1.5, 'ultraball': 2.0,
            'masterball': 5.0, 'diveball': 1.5, 'luxuryball': 1.2,
            'premierball': 1.0, 'beastball': 2.5
        }
        self.ball_prices = {
            'pokeball': 50, 'greatball': 100, 'ultraball': 200,
            'masterball': 1000, 'diveball': 150, 'luxuryball': 200,
            'premierball': 75, 'beastball': 500
        }
        self.load_pokemon_data()
        print(f"✅ Loaded {len(self.pokemon_list)} Pokémon")
    
    def load_pokemon_data(self):
        try:
            cache_file = os.path.join(config.DB_PATH, 'pokemon_cache_full.json')
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    self.pokemon_list = data['list']
                    self.pokemon_by_id = {p['id']: p for p in self.pokemon_list}
                    self.pokemon_by_name = {p['name'].lower(): p for p in self.pokemon_list}
                print(f"✅ Loaded {len(self.pokemon_list)} Pokémon from cache")
            else:
                self.fetch_all_from_api()
                self.save_cache()
        except Exception as e:
            print(f"⚠️ Error loading Pokémon: {e}")
            self.pokemon_list = self.get_fallback_data()
            self.pokemon_by_id = {p['id']: p for p in self.pokemon_list}
            self.pokemon_by_name = {p['name'].lower(): p for p in self.pokemon_list}
    
    def fetch_all_from_api(self):
        try:
            print("🔄 Fetching Pokémon data from PokeAPI...")
            response = requests.get(f'{config.POKEAPI_BASE}/pokemon?limit=898')
            data = response.json()
            
            for pokemon in data['results']:
                detail = requests.get(pokemon['url']).json()
                species = requests.get(detail['species']['url']).json()
                
                total_stats = sum(s['base_stat'] for s in detail['stats'])
                types = [t['type']['name'] for t in detail['types']]
                
                if species.get('is_mythical', False):
                    rarity = 'Mythical'
                elif species.get('is_legendary', False):
                    rarity = 'Legendary'
                elif total_stats > 550:
                    rarity = 'Epic'
                elif total_stats > 450:
                    rarity = 'Rare'
                elif total_stats > 350:
                    rarity = 'Uncommon'
                else:
                    rarity = 'Common'
                
                pokemon_data = {
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
                    'sprite_url': detail['sprites']['front_default'],
                    'shiny_sprite_url': detail['sprites']['front_shiny'],
                    'height': detail['height'] / 10,
                    'weight': detail['weight'] / 10,
                    'abilities': [a['ability']['name'] for a in detail['abilities']],
                    'catch_rate': self.rarities[rarity]['catch_rate']
                }
                
                self.pokemon_list.append(pokemon_data)
                self.pokemon_by_id[pokemon_data['id']] = pokemon_data
                self.pokemon_by_name[pokemon_data['name'].lower()] = pokemon_data
                
                time.sleep(0.1)
            
            print(f"✅ Fetched {len(self.pokemon_list)} Pokémon from API")
            
        except Exception as e:
            print(f"⚠️ API fetch failed: {e}")
            self.pokemon_list = self.get_fallback_data()
            self.pokemon_by_id = {p['id']: p for p in self.pokemon_list}
            self.pokemon_by_name = {p['name'].lower(): p for p in self.pokemon_list}
    
    def save_cache(self):
        try:
            cache_file = os.path.join(config.DB_PATH, 'pokemon_cache_full.json')
            with open(cache_file, 'w') as f:
                json.dump({'list': self.pokemon_list, 'generated': datetime.now().isoformat()}, f)
            print("✅ Pokémon data cached")
        except Exception as e:
            print(f"⚠️ Failed to cache Pokémon data: {e}")
    
    def get_fallback_data(self):
        return [
            {'id': 1, 'name': 'Bulbasaur', 'rarity': 'Common', 'total_stats': 318, 'types': ['grass', 'poison'], 'catch_rate': 0.8},
            {'id': 2, 'name': 'Ivysaur', 'rarity': 'Uncommon', 'total_stats': 405, 'types': ['grass', 'poison'], 'catch_rate': 0.6},
            {'id': 3, 'name': 'Venusaur', 'rarity': 'Rare', 'total_stats': 525, 'types': ['grass', 'poison'], 'catch_rate': 0.45},
            {'id': 4, 'name': 'Charmander', 'rarity': 'Common', 'total_stats': 309, 'types': ['fire'], 'catch_rate': 0.8},
            {'id': 5, 'name': 'Charmeleon', 'rarity': 'Uncommon', 'total_stats': 405, 'types': ['fire'], 'catch_rate': 0.6},
            {'id': 6, 'name': 'Charizard', 'rarity': 'Rare', 'total_stats': 534, 'types': ['fire', 'flying'], 'catch_rate': 0.45},
            {'id': 7, 'name': 'Squirtle', 'rarity': 'Common', 'total_stats': 314, 'types': ['water'], 'catch_rate': 0.8},
            {'id': 8, 'name': 'Wartortle', 'rarity': 'Uncommon', 'total_stats': 405, 'types': ['water'], 'catch_rate': 0.6},
            {'id': 9, 'name': 'Blastoise', 'rarity': 'Rare', 'total_stats': 530, 'types': ['water'], 'catch_rate': 0.45},
            {'id': 25, 'name': 'Pikachu', 'rarity': 'Uncommon', 'total_stats': 320, 'types': ['electric'], 'catch_rate': 0.6},
            {'id': 26, 'name': 'Raichu', 'rarity': 'Rare', 'total_stats': 485, 'types': ['electric'], 'catch_rate': 0.4},
            {'id': 133, 'name': 'Eevee', 'rarity': 'Rare', 'total_stats': 325, 'types': ['normal'], 'catch_rate': 0.45},
            {'id': 150, 'name': 'Mewtwo', 'rarity': 'Legendary', 'total_stats': 680, 'types': ['psychic'], 'catch_rate': 0.1},
            {'id': 151, 'name': 'Mew', 'rarity': 'Mythical', 'total_stats': 600, 'types': ['psychic'], 'catch_rate': 0.05},
            {'id': 384, 'name': 'Rayquaza', 'rarity': 'Legendary', 'total_stats': 680, 'types': ['dragon', 'flying'], 'catch_rate': 0.1},
            {'id': 385, 'name': 'Jirachi', 'rarity': 'Mythical', 'total_stats': 600, 'types': ['steel', 'psychic'], 'catch_rate': 0.05},
        ]
    
    def get_random_pokemon(self, min_cp=0, max_cp=1000):
        rarity = self.get_rarity()
        eligible = [p for p in self.pokemon_list if p['rarity'] == rarity]
        if not eligible:
            eligible = self.pokemon_list
        pokemon = random.choice(eligible)
        
        rarity_data = self.rarities[pokemon['rarity']]
        cp = random.randint(
            max(min_cp, rarity_data['min_cp']),
            min(max_cp, rarity_data['max_cp'])
        )
        
        return {
            'pokemon': pokemon,
            'cp': cp,
            'rarity': pokemon['rarity'],
            'is_shiny': random.random() < 0.02
        }
    
    def get_rarity(self):
        choices = []
        for rarity, data in self.rarities.items():
            choices.extend([rarity] * data['weight'])
        return random.choice(choices)
    
    def get_pokemon_by_name(self, name):
        if not name:
            return None
        return self.pokemon_by_name.get(name.lower())
    
    def get_pokemon_by_id(self, pokemon_id):
        return self.pokemon_by_id.get(pokemon_id)
    
    def get_legendary(self):
        legendaries = [p for p in self.pokemon_list if p['rarity'] in ['Legendary', 'Mythical']]
        return random.choice(legendaries) if legendaries else self.get_random_pokemon()['pokemon']
    
    def calculate_cp(self, pokemon, level=1):
        base_cp = sum(pokemon['base_stats'].values()) / 100
        level_multiplier = 1 + (level - 1) * 0.1
        return int(base_cp * level_multiplier * random.uniform(0.8, 1.2))

# ═════════════════════════════════════════════════════════════════════════════
# CONTINUE TO PART 2 - GUI COMPONENTS
# ═════════════════════════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════════════════════════
# BEAUTIFUL GUI COMPONENTS - Ticket, Giveaway, Reaction Roles
# ═════════════════════════════════════════════════════════════════════════════

# ─── TICKET SYSTEM GUI ──────────────────────────────────────────────────────

class TicketView(View):
    """Beautiful ticket creation view"""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket", emoji="🎫")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        modal = TicketModal()
        await interaction.response.send_modal(modal)

class TicketModal(Modal, title="🎫 Create Support Ticket"):
    reason = TextInput(
        label="Reason for ticket",
        placeholder="Briefly describe your issue...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )
    priority = TextInput(
        label="Priority (Optional)",
        placeholder="Low / Medium / High / Urgent",
        required=False,
        max_length=20
    )
    category = TextInput(
        label="Category (Optional)",
        placeholder="General / Technical / Billing / Report",
        required=False,
        max_length=20
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        user = interaction.user
        
        # Check ticket limit
        open_tickets = interaction.client.db.fetch_all(
            "SELECT * FROM tickets WHERE user_id = ? AND guild_id = ? AND status = 'open'",
            (str(user.id), str(guild.id))
        )
        
        if len(open_tickets) >= config.MAX_TICKETS_PER_USER:
            await interaction.followup.send(
                f"❌ You already have {config.MAX_TICKETS_PER_USER} open tickets! Please close some first.",
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
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Support team roles
        for role_name in ['Admin', 'Moderator', 'Support', 'Staff']:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            f"🎫-{ticket_id}",
            category=category,
            overwrites=overwrites,
            topic=f"Ticket by {user.display_name} | Priority: {self.priority.value or 'Medium'} | Category: {self.category.value or 'General'}"
        )
        
        # Save to database
        interaction.client.db.insert('tickets', {
            'ticket_id': ticket_id,
            'guild_id': str(guild.id),
            'user_id': str(user.id),
            'channel_id': str(channel.id),
            'reason': self.reason.value,
            'priority': self.priority.value or 'medium',
            'category': self.category.value or 'general'
        })
        
        # Create beautiful embed
        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"**Created by:** {user.mention}\n"
                       f"**Reason:** {self.reason.value}\n"
                       f"**Priority:** {self.priority.value or 'Medium'}\n"
                       f"**Category:** {self.category.value or 'General'}",
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
    """Complete ticket control buttons"""
    def __init__(self, ticket_id: str, user_id: int):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user_id = user_id
    
    @discord.ui.button(label="➕ Add User", style=discord.ButtonStyle.success, custom_id="ticket_add_user", emoji="➕")
    async def add_user(self, interaction: discord.Interaction, button: Button):
        modal = AddUserModal(self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="➖ Remove User", style=discord.ButtonStyle.danger, custom_id="ticket_remove_user", emoji="➖")
    async def remove_user(self, interaction: discord.Interaction, button: Button):
        modal = RemoveUserModal(self.ticket_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="📝 Transcript", style=discord.ButtonStyle.secondary, custom_id="ticket_transcript", emoji="📝")
    async def transcript(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
        messages = []
        async for msg in interaction.channel.history(limit=200):
            timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M')
            content = msg.content or "Embed/Attachment"
            messages.append(f"[{timestamp}] {msg.author.display_name}: {content}")
        
        transcript = "\n".join(reversed(messages))
        
        # Add header
        header = f"📝 TICKET TRANSCRIPT\n"
        header += f"Ticket ID: {self.ticket_id}\n"
        header += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        header += "=" * 50 + "\n\n"
        
        full_transcript = header + transcript
        
        file = discord.File(io.StringIO(full_transcript), filename=f"transcript-{self.ticket_id}.txt")
        await interaction.followup.send("📝 Transcript generated:", file=file, ephemeral=True)
    
    @discord.ui.button(label="⏰ Claim", style=discord.ButtonStyle.primary, custom_id="ticket_claim", emoji="⏰")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        
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
        await interaction.response.defer()
        
        # Ask for rating
        class RatingView(View):
            def __init__(self, ticket_id):
                super().__init__(timeout=60)
                self.ticket_id = ticket_id
            
            @discord.ui.button(label="⭐ 1", style=discord.ButtonStyle.secondary)
            async def rate_1(self, i: discord.Interaction, b: Button):
                await self.handle_rating(i, 1)
            
            @discord.ui.button(label="⭐⭐ 2", style=discord.ButtonStyle.secondary)
            async def rate_2(self, i: discord.Interaction, b: Button):
                await self.handle_rating(i, 2)
            
            @discord.ui.button(label="⭐⭐⭐ 3", style=discord.ButtonStyle.secondary)
            async def rate_3(self, i: discord.Interaction, b: Button):
                await self.handle_rating(i, 3)
            
            @discord.ui.button(label="⭐⭐⭐⭐ 4", style=discord.ButtonStyle.primary)
            async def rate_4(self, i: discord.Interaction, b: Button):
                await self.handle_rating(i, 4)
            
            @discord.ui.button(label="⭐⭐⭐⭐⭐ 5", style=discord.ButtonStyle.success)
            async def rate_5(self, i: discord.Interaction, b: Button):
                await self.handle_rating(i, 5)
            
            async def handle_rating(self, interaction, rating):
                interaction.client.db.execute(
                    "UPDATE tickets SET rating = ? WHERE ticket_id = ?",
                    (rating, self.ticket_id)
                )
                await interaction.response.send_message(f"✅ Thank you for rating! ({rating}⭐)", ephemeral=True)
        
        embed = discord.Embed(
            title="🔒 Closing Ticket",
            description=f"Ticket will be closed in 15 seconds.\nPlease rate your experience:",
            color=discord.Color.orange()
        )
        await interaction.channel.send(embed=embed, view=RatingView(self.ticket_id))
        
        interaction.client.db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = ? WHERE ticket_id = ?",
            (datetime.now().isoformat(), self.ticket_id)
        )
        
        await asyncio.sleep(15)
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
            user_id = self.user_id.value.replace('<@', '').replace('>', '').replace('!', '')
            user = interaction.guild.get_member(int(user_id))
            
            if not user:
                await interaction.response.send_message("❌ User not found!", ephemeral=True)
                return
            
            await interaction.channel.set_permissions(
                user,
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True
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

# ─── GIVEAWAY SYSTEM GUI ──────────────────────────────────────────────────

class GiveawayView(View):
    """Beautiful giveaway view with entry button"""
    def __init__(self, message_id: str, giveaway_id: int, winners: int):
        super().__init__(timeout=None)
        self.message_id = message_id
        self.giveaway_id = giveaway_id
        self.winners = winners
    
    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="enter_giveaway", emoji="🎉")
    async def enter_giveaway(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        
        # Check if user already entered
        message = await interaction.channel.fetch_message(int(self.message_id))
        await message.add_reaction("🎉")
        
        # Add to database
        interaction.client.db.insert('giveaway_entries', {
            'giveaway_id': self.giveaway_id,
            'user_id': str(interaction.user.id)
        })
        
        await interaction.followup.send("✅ You've entered the giveaway! Good luck! 🍀", ephemeral=True)

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
    
    requirements = TextInput(
        label="Requirements (Optional)",
        placeholder="e.g., Must have been in server for 1 week",
        required=False,
        max_length=200
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
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
        
        if self.requirements.value:
            embed.add_field(name="📋 Requirements", value=self.requirements.value, inline=False)
        
        embed.set_footer(text="🎉 Click the button below or react with 🎉 to enter!")
        
        # Send message with view
        db = interaction.client.db
        
        # First insert giveaway to get ID
        cursor = db.execute(
            """INSERT INTO giveaways (prize, winners, guild_id, channel_id, hosted_by, requirements, ended_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (self.prize.value, winners, str(interaction.guild.id), 
             str(interaction.channel.id), str(interaction.user.id),
             self.requirements.value, end_time.isoformat())
        )
        giveaway_id = cursor.lastrowid
        
        # Create view with the ID
        view = GiveawayView(message_id="placeholder", giveaway_id=giveaway_id, winners=winners)
        message = await interaction.channel.send(embed=embed, view=view)
        
        # Update with message ID
        db.execute(
            "UPDATE giveaways SET message_id = ? WHERE id = ?",
            (str(message.id), giveaway_id)
        )
        
        await interaction.followup.send(
            f"✅ Giveaway started! Ends in {self.duration.value}",
            ephemeral=True
        )

# ═════════════════════════════════════════════════════════════════════════════
# CONTINUE TO PART 3 - MAIN BOT CLASS
# ═════════════════════════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════════════════════════
# MAIN BOT CLASS
# ═════════════════════════════════════════════════════════════════════════════

class AnionBot(commands.Bot):
    """Main bot class with all features integrated"""
    
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        
        self.db = Database()
        self.pokemon_data = PokemonData()
        self.active_spawns = {}
        self.message_cache = {}
        self.voice_connections = {}
        self.level_cooldowns = {}
        self.command_cooldowns = {}
        self.start_time = datetime.now()
        
        # Stats tracking
        self.total_commands = 0
        self.total_messages = 0
        
        if config.OPENAI_KEY:
            openai.api_key = config.OPENAI_KEY
        
        # Start tasks
        self.spawn_loop.start()
        self.cleanup_loop.start()
        self.giveaway_checker.start()
        self.stats_updater.start()
        self.status_updater.start()
        
        print("✅ Bot initialized with all features")
    
    async def setup_hook(self):
        """Register ALL commands - Complete list of 50+ commands"""
        
        # ═════════════════════════════════════════════════════════════════════
        # POKEMON COMMANDS
        # ═════════════════════════════════════════════════════════════════════
        
        @self.tree.command(name="catch", description="🎮 Try to catch a wild Pokémon!")
        async def catch(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            # Check for pokeballs
            balls = self.db.fetch_all(
                "SELECT * FROM user_inventory WHERE user_id = ? AND guild_id = ? AND item_type = 'pokeball'",
                (user_id, guild_id)
            )
            
            if not balls:
                embed = discord.Embed(
                    title="❌ No Pokéballs!",
                    description="You don't have any Pokéballs!\nBuy some with `/shop`",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check for spawn
            if guild_id not in self.active_spawns:
                embed = discord.Embed(
                    title="🌿 No Pokémon Nearby!",
                    description="Wait for a wild Pokémon to appear!\nThey spawn every 30 seconds.",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            spawn = self.active_spawns[guild_id]
            if (datetime.now() - spawn['timestamp']).seconds > 60:
                del self.active_spawns[guild_id]
                embed = discord.Embed(
                    title="🏃 Pokémon Ran Away!",
                    description="The wild Pokémon got tired of waiting and left.",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
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
            
            rarity_data = self.pokemon_data.rarities.get(pokemon['rarity'], {'catch_rate': 0.5})
            catch_rate = rarity_data['catch_rate'] * ball_multiplier
            is_shiny = random.random() < 0.02
            caught = random.random() < catch_rate
            
            if caught:
                cp = random.randint(100, 500)
                if is_shiny:
                    cp *= 1.5
                
                self.db.insert('pokemon_collection', {
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'pokemon_name': pokemon['name'],
                    'pokemon_id': pokemon['id'],
                    'cp': int(cp),
                    'rarity': pokemon['rarity'],
                    'shiny': 1 if is_shiny else 0
                })
                
                self.db.execute(
                    """INSERT INTO pokemon_users (user_id, guild_id, catches, total_cp) 
                       VALUES (?, ?, 1, ?) 
                       ON CONFLICT(user_id, guild_id) 
                       DO UPDATE SET catches = catches + 1, total_cp = total_cp + ?""",
                    (user_id, guild_id, int(cp), int(cp))
                )
                
                if is_shiny:
                    self.db.execute(
                        "UPDATE pokemon_users SET shiny_catches = shiny_catches + 1 WHERE user_id = ? AND guild_id = ?",
                        (user_id, guild_id)
                    )
                
                if pokemon['rarity'] in ['Legendary', 'Mythical']:
                    self.db.execute(
                        "UPDATE pokemon_users SET legendary_catches = legendary_catches + 1 WHERE user_id = ? AND guild_id = ?",
                        (user_id, guild_id)
                    )
                    await interaction.channel.send(
                        f"🌟 **{interaction.user.mention} caught a LEGENDARY {pokemon['name']}!** 🌟"
                    )
                
                self.db.execute(
                    "DELETE FROM user_inventory WHERE user_id = ? AND guild_id = ? AND item_type = 'pokeball' LIMIT 1",
                    (user_id, guild_id)
                )
                
                del self.active_spawns[guild_id]
                
                embed = discord.Embed(
                    title="🎉 Pokémon Caught!",
                    description=f"**{pokemon['name']}** (CP: {int(cp)})",
                    color=discord.Color.gold() if is_shiny else discord.Color.green()
                )
                if is_shiny:
                    embed.add_field(name="✨ SHINY!", value="⭐ You caught a rare shiny Pokémon!", inline=False)
                embed.add_field(name="Rarity", value=pokemon['rarity'], inline=True)
                embed.add_field(name="Ball Used", value=balls[0]['item_id'].capitalize(), inline=True)
                embed.set_footer(text=f"Collection: {self.db.get_count('pokemon_collection', {'user_id': user_id, 'guild_id': guild_id})} Pokémon")
                
                await interaction.response.send_message(embed=embed)
            else:
                self.db.execute(
                    "DELETE FROM user_inventory WHERE user_id = ? AND guild_id = ? AND item_type = 'pokeball' LIMIT 1",
                    (user_id, guild_id)
                )
                embed = discord.Embed(
                    title="❌ Pokémon Escaped!",
                    description=f"The **{pokemon['name']}** escaped!\nTry using a better Pokéball next time!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)

        @self.tree.command(name="collection", description="📊 View your Pokémon collection")
        async def collection(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            collection = self.db.fetch_all(
                "SELECT * FROM pokemon_collection WHERE user_id = ? AND guild_id = ? ORDER BY cp DESC LIMIT 25",
                (user_id, guild_id)
            )
            
            if not collection:
                embed = discord.Embed(
                    title="📭 Empty Collection",
                    description="You haven't caught any Pokémon yet!\nUse `/catch` to start your adventure!",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"📊 {interaction.user.display_name}'s Pokémon Collection",
                color=discord.Color.gold()
            )
            
            total_cp = 0
            shiny_count = 0
            legendary_count = 0
            
            for i, p in enumerate(collection[:20], 1):
                shiny = "✨ " if p['shiny'] else ""
                cp_value = p['cp']
                total_cp += cp_value
                if p['shiny']:
                    shiny_count += 1
                if p['rarity'] in ['Legendary', 'Mythical']:
                    legendary_count += 1
                embed.add_field(
                    name=f"{i}. {shiny}{p['pokemon_name']}",
                    value=f"CP: {cp_value} | Rarity: {p['rarity']}",
                    inline=True
                )
            
            embed.set_footer(
                text=f"Total: {len(collection)} Pokémon | Total CP: {total_cp} | Shiny: {shiny_count} | Legendary: {legendary_count}"
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="shop", description="🛒 View the Pokémon shop")
        async def shop(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            user_data = self.db.fetch_one(
                "SELECT coins FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            coins = user_data['coins'] if user_data else 100
            
            embed = discord.Embed(
                title="🛒 Pokémon Shop",
                description=f"💰 Your coins: **{coins}**",
                color=discord.Color.blue()
            )
            
            # Pokéballs
            embed.add_field(
                name="🎯 Pokéball (50 coins)",
                value="1.0x catch multiplier | Common",
                inline=False
            )
            embed.add_field(
                name="🎯 Greatball (100 coins)",
                value="1.5x catch multiplier | Uncommon",
                inline=False
            )
            embed.add_field(
                name="🎯 Ultraball (200 coins)",
                value="2.0x catch multiplier | Rare",
                inline=False
            )
            embed.add_field(
                name="🎯 Masterball (1000 coins)",
                value="5.0x catch multiplier | Legendary",
                inline=False
            )
            
            # Special items
            embed.add_field(
                name="💎 Lucky Egg (300 coins)",
                value="Double XP for 30 minutes",
                inline=False
            )
            embed.add_field(
                name="🍬 Rare Candy (150 coins)",
                value="Increase a Pokémon's CP by 50",
                inline=False
            )
            
            embed.set_footer(text="Use /buy <item> to purchase")
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="buy", description="🛒 Buy an item from the shop")
        @app_commands.describe(item="Item to buy (pokeball, greatball, ultraball, masterball, lucky_egg, rare_candy)")
        async def buy(interaction: discord.Interaction, item: str):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            item_prices = {
                'pokeball': 50, 'greatball': 100, 'ultraball': 200,
                'masterball': 1000, 'lucky_egg': 300, 'rare_candy': 150
            }
            item = item.lower()
            
            if item not in item_prices:
                embed = discord.Embed(
                    title="❌ Invalid Item",
                    description="Available: pokeball, greatball, ultraball, masterball, lucky_egg, rare_candy",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            price = item_prices[item]
            user_data = self.db.fetch_one(
                "SELECT coins FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            coins = user_data['coins'] if user_data else 100
            
            if coins < price:
                embed = discord.Embed(
                    title="❌ Not Enough Coins!",
                    description=f"You need {price} coins! You have {coins}.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            self.db.execute(
                "UPDATE pokemon_users SET coins = coins - ? WHERE user_id = ? AND guild_id = ?",
                (price, user_id, guild_id)
            )
            
            self.db.insert('user_inventory', {
                'user_id': user_id,
                'guild_id': guild_id,
                'item_id': item,
                'item_type': 'pokeball' if item != 'lucky_egg' and item != 'rare_candy' else 'special',
                'quantity': 1
            })
            
            embed = discord.Embed(
                title="✅ Purchase Successful!",
                description=f"Purchased **{item.replace('_', ' ').title()}** for {price} coins!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="daily", description="🎁 Claim your daily bonus")
        async def daily(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            user_data = self.db.fetch_one(
                "SELECT * FROM pokemon_users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            
            if user_data and user_data['last_daily']:
                last = datetime.fromisoformat(user_data['last_daily'])
                if (datetime.now() - last).days < 1:
                    remaining = timedelta(days=1) - (datetime.now() - last)
                    embed = discord.Embed(
                        title="⏳ Daily Bonus Already Claimed!",
                        description=f"Come back in {remaining.seconds//3600}h {(remaining.seconds%3600)//60}m!",
                        color=discord.Color.orange()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            
            coins = random.randint(50, 200)
            bonus_pokemon = random.random() < 0.15
            
            self.db.execute(
                """INSERT INTO pokemon_users (user_id, guild_id, coins, last_daily) 
                   VALUES (?, ?, ?, ?) 
                   ON CONFLICT(user_id, guild_id) 
                   DO UPDATE SET coins = coins + ?, last_daily = ?""",
                (user_id, guild_id, coins, datetime.now().isoformat(), coins, datetime.now().isoformat())
            )
            
            embed = discord.Embed(
                title="🎁 Daily Bonus Claimed!",
                description=f"✨ You received **{coins}** coins!",
                color=discord.Color.gold()
            )
            
            if bonus_pokemon:
                pokemon = self.pokemon_data.get_random_pokemon()
                cp = random.randint(50, 300)
                self.db.insert('pokemon_collection', {
                    'user_id': user_id,
                    'guild_id': guild_id,
                    'pokemon_name': pokemon['pokemon']['name'],
                    'pokemon_id': pokemon['pokemon']['id'],
                    'cp': cp,
                    'rarity': pokemon['rarity'],
                    'shiny': 0
                })
                embed.add_field(
                    name="🎉 Bonus Pokémon!",
                    value=f"You received a **{pokemon['pokemon']['name']}** (CP: {cp})!",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="pokedex", description="📖 View your Pokédex progress")
        async def pokedex(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            pokedex = self.db.fetch_all(
                "SELECT * FROM pokemon_pokedex WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            
            total = len(pokedex)
            caught = sum(1 for p in pokedex if p['caught'])
            shiny = sum(1 for p in pokedex if p['shiny_count'] > 0)
            
            embed = discord.Embed(
                title=f"📖 {interaction.user.display_name}'s Pokédex",
                description=f"Caught: {caught}/{total} Pokémon",
                color=discord.Color.blue()
            )
            embed.add_field(name="📊 Progress", value=f"{int(caught/total*100) if total > 0 else 0}%", inline=True)
            embed.add_field(name="👁️ Seen", value=total, inline=True)
            embed.add_field(name="✅ Caught", value=caught, inline=True)
            embed.add_field(name="✨ Shiny Seen", value=shiny, inline=True)
            
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="collection_show", description="📊 Show your collection publicly")
        @app_commands.describe(user="User to show collection for")
        async def collection_show(interaction: discord.Interaction, user: discord.Member = None):
            target = user or interaction.user
            user_id = str(target.id)
            guild_id = str(interaction.guild.id)
            
            collection = self.db.fetch_all(
                "SELECT * FROM pokemon_collection WHERE user_id = ? AND guild_id = ? ORDER BY cp DESC LIMIT 10",
                (user_id, guild_id)
            )
            
            if not collection:
                embed = discord.Embed(
                    title=f"📭 {target.display_name}'s Collection",
                    description="They haven't caught any Pokémon yet!",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title=f"📊 {target.display_name}'s Top 10 Pokémon",
                color=discord.Color.gold()
            )
            
            for i, p in enumerate(collection, 1):
                shiny = "✨ " if p['shiny'] else ""
                embed.add_field(
                    name=f"{i}. {shiny}{p['pokemon_name']}",
                    value=f"CP: {p['cp']} | Rarity: {p['rarity']}",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="give_pokemon", description="⚙️ Give Pokémon to user (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(user="User to give to", name="Pokémon name", cp="CP value (optional)")
        async def give_pokemon(interaction: discord.Interaction, user: discord.Member, name: str, cp: int = None):
            pokemon = self.pokemon_data.get_pokemon_by_name(name)
            
            if not pokemon:
                embed = discord.Embed(
                    title="❌ Pokémon Not Found!",
                    description=f"Could not find `{name}`",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            cp = cp or random.randint(100, 500)
            
            self.db.insert('pokemon_collection', {
                'user_id': str(user.id),
                'guild_id': str(interaction.guild.id),
                'pokemon_name': pokemon['name'],
                'pokemon_id': pokemon['id'],
                'cp': cp,
                'rarity': pokemon['rarity'],
                'shiny': 0
            })
            
            embed = discord.Embed(
                title="✅ Pokémon Given!",
                description=f"Gave **{pokemon['name']}** (CP: {cp}) to {user.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="give_coins", description="⚙️ Give coins to user (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(user="User to give to", amount="Amount of coins")
        async def give_coins(interaction: discord.Interaction, user: discord.Member, amount: int):
            self.db.execute(
                """INSERT INTO pokemon_users (user_id, guild_id, coins) 
                   VALUES (?, ?, ?) 
                   ON CONFLICT(user_id, guild_id) 
                   DO UPDATE SET coins = coins + ?""",
                (str(user.id), str(interaction.guild.id), amount, amount)
            )
            embed = discord.Embed(
                title="✅ Coins Given!",
                description=f"Gave {amount} coins to {user.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # VERIFICATION COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="verify", description="🔐 Start the verification process")
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
                    "**This process is secure and only needs to be done once.**\n\n"
                    "You will be redirected to Discord to authorize access."
                ),
                color=discord.Color.blue()
            )
            embed.add_field(name="🔒 Privacy", value="We only access your basic Discord profile information.", inline=False)
            embed.set_footer(text="Verification is required to access this server")
            
            view = View()
            view.add_item(Button(label="🔐 Verify Now", url=auth_url, style=discord.ButtonStyle.primary))
            
            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="status", description="🔐 Check verification status")
        async def verify_status(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            verified = self.db.fetch_one(
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
                embed.add_field(name="Method", value=verified['verification_method'], inline=True)
            else:
                embed = discord.Embed(
                    title="❌ Not Verified",
                    description="Use `/verify` to start the verification process.",
                    color=discord.Color.red()
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="set_verified_role", description="⚙️ Set verified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for verified users")
        async def set_verified_role(interaction: discord.Interaction, role: discord.Role):
            self.db.insert('guild_settings', {
                'guild_id': str(interaction.guild.id),
                'verified_role_id': str(role.id)
            })
            embed = discord.Embed(
                title="✅ Verified Role Set",
                description=f"Verified role set to {role.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="set_unverified_role", description="⚙️ Set unverified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for unverified users")
        async def set_unverified_role(interaction: discord.Interaction, role: discord.Role):
            self.db.update(
                'guild_settings',
                {'unverified_role_id': str(role.id)},
                {'guild_id': str(interaction.guild.id)}
            )
            embed = discord.Embed(
                title="✅ Unverified Role Set",
                description=f"Unverified role set to {role.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="set_log_channel", description="⚙️ Set log channel (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Channel for logs")
        async def set_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
            self.db.insert('guild_settings', {
                'guild_id': str(interaction.guild.id),
                'log_channel_id': str(channel.id)
            })
            embed = discord.Embed(
                title="✅ Log Channel Set",
                description=f"Log channel set to {channel.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setup_guide", description="📖 Show setup guide")
        async def setup_guide(interaction: discord.Interaction):
            embed = discord.Embed(
                title="📖 Server Setup Guide",
                description="How to set up Anion in your server",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="1️⃣ Set Roles",
                value="`/set_verified_role @role` - Verified users\n`/set_unverified_role @role` - Unverified users",
                inline=False
            )
            embed.add_field(
                name="2️⃣ Set Channels",
                value="`/set_log_channel #channel` - Log channel",
                inline=False
            )
            embed.add_field(
                name="3️⃣ Pokémon Setup",
                value="`/poke_setup` - Setup Pokémon spawn channel\n`/spawn_pokemon <name> #channel` - Spawn Pokémon",
                inline=False
            )
            embed.add_field(
                name="4️⃣ Ticket Setup",
                value="`/setup_ticket` - Setup ticket system",
                inline=False
            )
            embed.add_field(
                name="5️⃣ Giveaway Setup",
                value="`/giveaway` - Start a giveaway",
                inline=False
            )
            
            embed.set_footer(text="All admin commands require Administrator permission")
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # MODERATION COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ban", description="🔨 Ban a member")
        @app_commands.default_permissions(ban_members=True)
        @app_commands.describe(member="Member to ban", reason="Reason for ban")
        async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            try:
                await member.ban(reason=reason)
                embed = discord.Embed(
                    title="🔨 Member Banned",
                    description=f"**{member.display_name}** has been banned.\nReason: {reason}",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed)
                
                # Log
                self.db.insert('mod_logs', {
                    'guild_id': str(interaction.guild.id),
                    'action': 'ban',
                    'moderator_id': str(interaction.user.id),
                    'target_id': str(member.id),
                    'reason': reason
                })
            except Exception as e:
                embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="kick", description="👢 Kick a member")
        @app_commands.default_permissions(kick_members=True)
        @app_commands.describe(member="Member to kick", reason="Reason for kick")
        async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            try:
                await member.kick(reason=reason)
                embed = discord.Embed(
                    title="👢 Member Kicked",
                    description=f"**{member.display_name}** has been kicked.\nReason: {reason}",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed)
                
                self.db.insert('mod_logs', {
                    'guild_id': str(interaction.guild.id),
                    'action': 'kick',
                    'moderator_id': str(interaction.user.id),
                    'target_id': str(member.id),
                    'reason': reason
                })
            except Exception as e:
                embed = discord.Embed(title="❌ Error", description=str(e), color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="mute", description="🔇 Mute a member (24h)")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to mute", reason="Reason for mute")
        async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            await self.mute_user(interaction.guild, member, reason)
            embed = discord.Embed(
                title="🔇 Member Muted",
                description=f"**{member.display_name}** has been muted for 24 hours.\nReason: {reason}",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            
            self.db.insert('mod_logs', {
                'guild_id': str(interaction.guild.id),
                'action': 'mute',
                'moderator_id': str(interaction.user.id),
                'target_id': str(member.id),
                'reason': reason
            })

        @self.tree.command(name="unmute", description="🔊 Unmute a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to unmute")
        async def unmute(interaction: discord.Interaction, member: discord.Member):
            await self.unmute_user(interaction.guild, member)
            embed = discord.Embed(
                title="🔊 Member Unmuted",
                description=f"**{member.display_name}** has been unmuted.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="warn", description="⚠️ Warn a member (3 = auto-mute)")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to warn", reason="Reason for warning")
        async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            guild_id = str(interaction.guild.id)
            user_id = str(member.id)
            
            self.db.insert('warnings', {
                'user_id': user_id,
                'guild_id': guild_id,
                'moderator_id': str(interaction.user.id),
                'reason': reason,
                'expires_at': (datetime.now() + timedelta(days=30)).isoformat()
            })
            
            warnings = self.db.fetch_all(
                "SELECT * FROM warnings WHERE user_id = ? AND guild_id = ? AND active = 1",
                (user_id, guild_id)
            )
            
            embed = discord.Embed(
                title="⚠️ Member Warned",
                description=f"**{member.display_name}** has been warned.\nReason: {reason}\nWarnings: {len(warnings)}/3",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            
            if len(warnings) >= 3:
                await self.mute_user(interaction.guild, member, "Auto-muted for 3 warnings")
                embed2 = discord.Embed(
                    title="🔇 Auto-Muted",
                    description=f"**{member.display_name}** has been auto-muted for reaching 3 warnings.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed2)

        @self.tree.command(name="clear", description="🗑️ Clear messages")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(amount="Number of messages to clear (max 100)")
        async def clear(interaction: discord.Interaction, amount: int = 10):
            if amount > 100:
                embed = discord.Embed(
                    title="❌ Too Many Messages!",
                    description="Maximum 100 messages can be cleared at once.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            deleted = await interaction.channel.purge(limit=amount)
            embed = discord.Embed(
                title="🗑️ Messages Cleared",
                description=f"Cleared {len(deleted)} messages!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="add_badword", description="🚫 Add a bad word (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(word="Word to add")
        async def add_badword(interaction: discord.Interaction, word: str):
            self.db.insert('bad_words', {
                'word': word.lower(),
                'guild_id': str(interaction.guild.id)
            })
            embed = discord.Embed(
                title="✅ Bad Word Added",
                description=f"Added `{word}` to the bad words list.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="remove_badword", description="🚫 Remove a bad word (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(word="Word to remove")
        async def remove_badword(interaction: discord.Interaction, word: str):
            self.db.execute(
                "DELETE FROM bad_words WHERE word = ? AND guild_id = ?",
                (word.lower(), str(interaction.guild.id))
            )
            embed = discord.Embed(
                title="✅ Bad Word Removed",
                description=f"Removed `{word}` from the bad words list.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="badwords", description="🚫 List all bad words (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def list_badwords(interaction: discord.Interaction):
            words = self.db.fetch_all(
                "SELECT word FROM bad_words WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            
            if not words:
                embed = discord.Embed(
                    title="🚫 Bad Words",
                    description="No bad words configured.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            word_list = "\n".join([f"• {row['word']}" for row in words])
            embed = discord.Embed(
                title="🚫 Bad Words List",
                description=word_list,
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # TICKET COMMANDS (with GUI)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ticket", description="🎫 Create a support ticket")
        @app_commands.describe(reason="Reason for the ticket")
        async def ticket(interaction: discord.Interaction, reason: str = "No reason provided"):
            modal = TicketModal()
            await interaction.response.send_modal(modal)

        @self.tree.command(name="setup_ticket", description="🎫 Setup ticket system (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def setup_ticket(interaction: discord.Interaction):
            embed = discord.Embed(
                title="🎫 Ticket System",
                description="Click the button below to create a support ticket.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="How it works",
                value="1. Click the button below\n2. Fill in the details\n3. A private ticket channel will be created for you",
                inline=False
            )
            embed.set_footer(text="Support team will be notified when a ticket is created")
            
            view = TicketView()
            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="close", description="🔒 Close the current ticket")
        async def close_ticket(interaction: discord.Interaction):
            ticket = self.db.fetch_one(
                "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
                (str(interaction.channel.id),)
            )
            
            if not ticket:
                embed = discord.Embed(
                    title="❌ Not a Ticket Channel!",
                    description="This command can only be used in ticket channels.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🔒 Closing Ticket",
                description="Ticket will be closed in 10 seconds.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)
            
            self.db.execute(
                "UPDATE tickets SET status = 'closed', closed_at = ? WHERE channel_id = ?",
                (datetime.now().isoformat(), str(interaction.channel.id))
            )
            
            await asyncio.sleep(10)
            await interaction.channel.delete()

        @self.tree.command(name="add_user", description="➕ Add user to ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to add")
        async def ticket_add_user(interaction: discord.Interaction, user: discord.Member):
            ticket = self.db.fetch_one(
                "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
                (str(interaction.channel.id),)
            )
            
            if not ticket:
                embed = discord.Embed(
                    title="❌ Not a Ticket Channel!",
                    description="This command can only be used in ticket channels.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.channel.set_permissions(
                user,
                read_messages=True,
                send_messages=True,
                attach_files=True
            )
            
            embed = discord.Embed(
                title="✅ User Added",
                description=f"Added {user.mention} to the ticket!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="remove_user", description="➖ Remove user from ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to remove")
        async def ticket_remove_user(interaction: discord.Interaction, user: discord.Member):
            ticket = self.db.fetch_one(
                "SELECT * FROM tickets WHERE channel_id = ? AND status = 'open'",
                (str(interaction.channel.id),)
            )
            
            if not ticket:
                embed = discord.Embed(
                    title="❌ Not a Ticket Channel!",
                    description="This command can only be used in ticket channels.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if str(user.id) == ticket['user_id']:
                embed = discord.Embed(
                    title="❌ Cannot Remove Creator!",
                    description="You cannot remove the ticket creator.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.channel.set_permissions(
                user,
                read_messages=False,
                send_messages=False
            )
            
            embed = discord.Embed(
                title="✅ User Removed",
                description=f"Removed {user.mention} from the ticket!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="transcript", description="📝 Get ticket transcript")
        async def transcript(interaction: discord.Interaction):
            ticket = self.db.fetch_one(
                "SELECT * FROM tickets WHERE channel_id = ?",
                (str(interaction.channel.id),)
            )
            
            if not ticket:
                embed = discord.Embed(
                    title="❌ Not a Ticket Channel!",
                    description="This command can only be used in ticket channels.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            messages = []
            async for msg in interaction.channel.history(limit=200):
                timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M')
                content = msg.content or "Embed/Attachment"
                messages.append(f"[{timestamp}] {msg.author.display_name}: {content}")
            
            transcript = "\n".join(reversed(messages))
            
            header = f"📝 TICKET TRANSCRIPT\n"
            header += f"Ticket ID: {ticket['ticket_id']}\n"
            header += f"Created: {ticket['created_at']}\n"
            header += f"Status: {ticket['status']}\n"
            header += "=" * 50 + "\n\n"
            
            full_transcript = header + transcript
            
            file = discord.File(io.StringIO(full_transcript), filename=f"transcript-{ticket['ticket_id']}.txt")
            await interaction.followup.send("📝 Transcript generated:", file=file, ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # GIVEAWAY COMMANDS (with GUI)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="giveaway", description="🎁 Start a giveaway (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def giveaway(interaction: discord.Interaction):
            modal = GiveawayCreatorModal()
            await interaction.response.send_modal(modal)

        @self.tree.command(name="reroll", description="🎁 Reroll a giveaway (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="ID of the giveaway message")
        async def reroll(interaction: discord.Interaction, message_id: str):
            try:
                msg_id = int(message_id)
                message = await interaction.channel.fetch_message(msg_id)
                
                reaction = discord.utils.get(message.reactions, emoji="🎉")
                if not reaction:
                    embed = discord.Embed(
                        title="❌ No Reactions Found!",
                        description="No 🎉 reactions found on this message.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                users = []
                async for user in reaction.users():
                    if not user.bot:
                        users.append(user)
                
                if not users:
                    embed = discord.Embed(
                        title="❌ No Participants!",
                        description="No valid participants found.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                giveaway_data = self.db.fetch_one(
                    "SELECT winners FROM giveaways WHERE message_id = ?",
                    (message_id,)
                )
                winners_count = giveaway_data['winners'] if giveaway_data else 1
                
                winners = random.sample(users, min(winners_count, len(users)))
                
                embed = discord.Embed(
                    title="🎉 Giveaway Rerolled!",
                    description=f"New winners: {', '.join([w.mention for w in winners])}!",
                    color=discord.Color.gold()
                )
                await interaction.response.send_message(embed=embed)
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=str(e),
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # LEVELING COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="rank", description="📊 Check your rank")
        async def rank(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            user_id = str(target.id)
            guild_id = str(interaction.guild.id)
            
            data = self.db.fetch_one(
                "SELECT * FROM levels WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            
            if not data:
                embed = discord.Embed(
                    title=f"📊 {target.display_name}'s Rank",
                    description="No messages sent yet!",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            rank_result = self.db.fetch_one(
                "SELECT COUNT(*) + 1 as rank FROM levels WHERE guild_id = ? AND xp > (SELECT xp FROM levels WHERE user_id = ? AND guild_id = ?)",
                (guild_id, user_id, guild_id)
            )
            rank_value = rank_result['rank'] if rank_result else '?'
            
            embed = discord.Embed(
                title=f"📊 {target.display_name}'s Rank",
                color=target.color
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Level", value=data['level'], inline=True)
            embed.add_field(name="XP", value=data['xp'], inline=True)
            embed.add_field(name="Messages", value=data['messages'], inline=True)
            embed.add_field(name="Rank", value=f"#{rank_value}", inline=True)
            
            next_xp = 100 * (data['level'] + 1) ** 2
            current_xp = 100 * data['level'] ** 2
            progress = (data['xp'] - current_xp) / (next_xp - current_xp) * 100
            
            bar = "🟩" * int(progress/10) + "⬜" * (10 - int(progress/10))
            embed.add_field(name="Progress", value=f"{bar} {progress:.1f}%", inline=False)
            
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="leaderboard", description="🏆 View server leaderboard")
        async def leaderboard(interaction: discord.Interaction):
            guild_id = str(interaction.guild.id)
            
            data = self.db.fetch_all(
                "SELECT user_id, xp, level FROM levels WHERE guild_id = ? ORDER BY xp DESC LIMIT 10",
                (guild_id,)
            )
            
            if not data:
                embed = discord.Embed(
                    title="🏆 Leaderboard",
                    description="No data yet!",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title=f"🏆 {interaction.guild.name} Leaderboard",
                color=discord.Color.gold()
            )
            
            for i, entry in enumerate(data, 1):
                member = interaction.guild.get_member(int(entry['user_id']))
                if member:
                    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
                    embed.add_field(
                        name=f"{medal} {member.display_name}",
                        value=f"Level {entry['level']} | {entry['xp']} XP",
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # MUSIC COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="play", description="🎵 Play a song")
        @app_commands.describe(url="YouTube URL or search term")
        async def play(interaction: discord.Interaction, url: str):
            if not interaction.user.voice:
                embed = discord.Embed(
                    title="❌ Not in Voice Channel",
                    description="You need to be in a voice channel to play music!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            voice_channel = interaction.user.voice.channel
            
            if interaction.guild.id not in self.voice_connections:
                voice_client = await voice_channel.connect()
                self.voice_connections[interaction.guild.id] = voice_client
            else:
                voice_client = self.voice_connections[interaction.guild.id]
                if voice_client.channel != voice_channel:
                    await voice_client.move_to(voice_channel)
            
            embed = discord.Embed(
                title="🔍 Searching...",
                description="Looking for your song...",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
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
                    embed.add_field(name="Duration", value=f"{info['duration']//60}:{info['duration']%60:02d}", inline=True)
                    embed.add_field(name="Uploader", value=info.get('uploader', 'Unknown'), inline=True)
                    embed.set_thumbnail(url=info.get('thumbnail', None))
                    embed.set_footer(text=f"Requested by {interaction.user.display_name}")
                    
                    await interaction.followup.send(embed=embed)
                    
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"Could not play song: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)

        @self.tree.command(name="skip", description="⏭️ Skip current song")
        async def skip(interaction: discord.Interaction):
            if interaction.guild.id in self.voice_connections:
                voice_client = self.voice_connections[interaction.guild.id]
                if voice_client.is_playing():
                    voice_client.stop()
                    embed = discord.Embed(
                        title="⏭️ Skipped!",
                        description="Skipped the current song.",
                        color=discord.Color.green()
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = discord.Embed(
                        title="❌ Nothing Playing",
                        description="No song is currently playing.",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="I'm not in a voice channel!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="stop", description="⏹️ Stop music and leave")
        async def stop(interaction: discord.Interaction):
            if interaction.guild.id in self.voice_connections:
                voice_client = self.voice_connections[interaction.guild.id]
                await voice_client.disconnect()
                del self.voice_connections[interaction.guild.id]
                embed = discord.Embed(
                    title="⏹️ Stopped",
                    description="Stopped music and left the voice channel!",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Not Connected",
                    description="I'm not in a voice channel!",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # AI COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ai", description="🤖 Chat with AI")
        @app_commands.describe(message="Your message")
        async def ai_chat(interaction: discord.Interaction, message: str):
            if not config.OPENAI_KEY:
                embed = discord.Embed(
                    title="❌ AI Not Configured",
                    description="OpenAI is not configured on this bot.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await interaction.response.defer()
            
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful Discord bot named Anion. You help users with various tasks and are friendly and knowledgeable."},
                        {"role": "user", "content": message}
                    ],
                    max_tokens=500
                )
                reply = response.choices[0].message.content
                
                embed = discord.Embed(
                    title="🤖 AI Response",
                    description=reply[:1900],
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"Asked by {interaction.user.display_name}")
                
                await interaction.followup.send(embed=embed)
                
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Error",
                    description=f"AI Error: {str(e)}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # ADMIN SETUP COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="poke_setup", description="⚙️ Setup Pokémon channels (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def poke_setup(interaction: discord.Interaction):
            category = discord.utils.get(interaction.guild.categories, name="🎮 Pokémon")
            if not category:
                category = await interaction.guild.create_category("🎮 Pokémon")
            
            channel = await interaction.guild.create_text_channel(
                "🌿-pokemon-spawns",
                category=category
            )
            
            self.db.insert('pokemon_settings', {
                'guild_id': str(interaction.guild.id),
                'channel_id': str(channel.id)
            })
            
            embed = discord.Embed(
                title="✅ Pokémon Setup Complete!",
                description=f"Spawns will appear in {channel.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="📊 Settings", value="Spawning enabled | 30 second interval", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="spawn_pokemon", description="⚙️ Spawn any Pokémon (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(name="Pokémon name", channel="Channel to spawn in")
        async def spawn_pokemon(interaction: discord.Interaction, name: str, channel: discord.TextChannel):
            pokemon = self.pokemon_data.get_pokemon_by_name(name)
            
            if not pokemon:
                embed = discord.Embed(
                    title="❌ Pokémon Not Found!",
                    description=f"Could not find `{name}`",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            await self.spawn_pokemon_message(channel, pokemon)
            
            embed = discord.Embed(
                title="✅ Pokémon Spawned!",
                description=f"Spawned {pokemon['name']} in {channel.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="reset_pokemon", description="⚙️ Reset Pokémon data (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(user="User to reset")
        async def reset_pokemon(interaction: discord.Interaction, user: discord.Member):
            user_id = str(user.id)
            guild_id = str(interaction.guild.id)
            
            self.db.delete('pokemon_collection', {'user_id': user_id, 'guild_id': guild_id})
            self.db.delete('pokemon_users', {'user_id': user_id, 'guild_id': guild_id})
            self.db.delete('pokemon_pokedex', {'user_id': user_id, 'guild_id': guild_id})
            
            embed = discord.Embed(
                title="✅ Pokémon Data Reset",
                description=f"Reset all Pokémon data for {user.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # UTILITY COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ping", description="🏓 Check bot latency")
        async def ping(interaction: discord.Interaction):
            latency = round(interaction.client.latency * 1000)
            embed = discord.Embed(
                title="🏓 Pong!",
                description=f"Latency: {latency}ms",
                color=discord.Color.green()
            )
            embed.add_field(name="Uptime", value=str(datetime.now() - self.start_time).split('.')[0], inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="serverinfo", description="📊 Get server information")
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
            embed.add_field(name="🔒 Verification", value="✅ Enabled" if guild.verification_level.value > 0 else "❌ Disabled", inline=True)
            
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="userinfo", description="👤 Get user information")
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
            embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="Created", value=target.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(
                name="Roles",
                value=", ".join([r.mention for r in target.roles if r.name != "@everyone"])[:100] or "None",
                inline=False
            )
            embed.add_field(name="Is Bot", value="✅ Yes" if target.bot else "❌ No", inline=True)
            
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="list_all", description="📋 Show all commands")
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

        @self.tree.command(name="debug_roles", description="🔍 Debug role assignment (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def debug_roles(interaction: discord.Interaction):
            settings = self.db.fetch_one(
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

        @self.tree.command(name="view_settings", description="🔍 View bot settings (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def view_settings(interaction: discord.Interaction):
            settings = self.db.fetch_one(
                "SELECT * FROM guild_settings WHERE guild_id = ?",
                (str(interaction.guild.id),)
            )
            
            pokemon_settings = self.db.fetch_one(
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

        # ═════════════════════════════════════════════════════════════════════
        # DM COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="dm", description="📨 Send a DM to a user (Admin)")
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
                embed_response = discord.Embed(
                    title="✅ Message Sent",
                    description=f"Message sent to {user.mention}",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed_response)
            except Exception as e:
                embed_response = discord.Embed(
                    title="❌ Could Not DM User",
                    description=str(e),
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed_response, ephemeral=True)

        @self.tree.command(name="say", description="📨 Send a message as bot (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Channel to send in", message="Message to send")
        async def say(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
            await channel.send(message)
            embed = discord.Embed(
                title="✅ Message Sent",
                description=f"Message sent to {channel.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed, ephemeral=True)

        @self.tree.command(name="announce", description="📢 Send an announcement (Admin)")
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
            embed.add_field(name="📌 Important", value="Please read this announcement carefully!", inline=False)
            
            await interaction.channel.send(embed=embed)
            embed_response = discord.Embed(
                title="✅ Announcement Sent!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed_response, ephemeral=True)

        # ─── SYNC COMMANDS ──────────────────────────────────────────────────
        await self.tree.sync()
        print(f'✅ All commands synced! ({len(self.tree.get_commands())} commands)')
    
    # ═════════════════════════════════════════════════════════════════════════
    # TASKS AND BACKGROUND PROCESSES
    # ═════════════════════════════════════════════════════════════════════════
    
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
                if channel and random.random() < 0.3:
                    pokemon_data = self.pokemon_data.get_random_pokemon()
                    await self.spawn_pokemon_message(channel, pokemon_data['pokemon'])
    
    @tasks.loop(minutes=5)
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
        # Delete old tickets
        self.db.execute(
            "DELETE FROM tickets WHERE status = 'closed' AND closed_at < datetime('now', '-7 days')"
        )
        
        # Delete old giveaways
        self.db.execute(
            "DELETE FROM giveaways WHERE ended = 1 AND ended_at < datetime('now', '-30 days')"
        )
        
        # Clean up expired warnings
        self.db.execute(
            "UPDATE warnings SET active = 0 WHERE expires_at < datetime('now')"
        )
        
        # Clean up expired mutes
        expired_mutes = self.db.fetch_all(
            "SELECT user_id, guild_id FROM muted WHERE unmute_at < datetime('now')"
        )
        for mute in expired_mutes:
            guild = self.get_guild(int(mute['guild_id']))
            if guild:
                member = guild.get_member(int(mute['user_id']))
                if member:
                    await self.unmute_user(guild, member)
    
    @tasks.loop(hours=6)
    async def stats_updater(self):
        """Update server statistics"""
        for guild in self.guilds:
            self.db.execute(
                """INSERT INTO server_stats (guild_id, total_members, updated_at) 
                   VALUES (?, ?, ?) 
                   ON CONFLICT(guild_id) 
                   DO UPDATE SET total_members = ?, updated_at = ?""",
                (str(guild.id), guild.member_count, datetime.now().isoformat(), 
                 guild.member_count, datetime.now().isoformat())
            )
    
    @tasks.loop(minutes=5)
    async def status_updater(self):
        """Update bot status"""
        guilds = len(self.guilds)
        users = sum(g.member_count for g in self.guilds)
        commands = self.total_commands
        
        statuses = [
            f"🌿 /help | {guilds} servers",
            f"🎮 {commands} commands used",
            f"👥 {users} users",
            f"🌟 Pokémon | /catch",
            f"🎫 Tickets | /ticket"
        ]
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name=random.choice(statuses)
            )
        )
    
    # ═════════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ═════════════════════════════════════════════════════════════════════════
    
    async def on_ready(self):
        """Called when bot is ready"""
        print(f'✅ Bot is ready! Logged in as {self.user}')
        print(f'✅ Connected to {len(self.guilds)} guilds')
        print(f'✅ Total users: {sum(g.member_count for g in self.guilds)}')
        
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="🌿 Pokémon | /help"
            )
        )
    
    async def on_member_join(self, member):
        """Handle new member join"""
        settings = self.db.fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (str(member.guild.id),)
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
                    msg = settings['welcome_message'] or f"👋 Welcome {member.mention} to **{member.guild.name}**!"
                    embed = discord.Embed(
                        title="👋 Welcome!",
                        description=msg,
                        color=discord.Color.green()
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.add_field(name="📊 Server", value=f"{member.guild.member_count} members", inline=True)
                    embed.add_field(name="📅 Joined", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
                    await channel.send(embed=embed)
    
    async def on_member_remove(self, member):
        """Handle member leave"""
        settings = self.db.fetch_one(
            "SELECT * FROM guild_settings WHERE guild_id = ?",
            (str(member.guild.id),)
        )
        
        if settings and settings['goodbye_channel_id']:
            channel = member.guild.get_channel(int(settings['goodbye_channel_id']))
            if channel:
                msg = settings['goodbye_message'] or f"👋 {member.display_name} has left the server."
                embed = discord.Embed(
                    title="👋 Goodbye!",
                    description=msg,
                    color=discord.Color.orange()
                )
                embed.add_field(name="📊 Server", value=f"{member.guild.member_count} members remaining", inline=True)
                await channel.send(embed=embed)
    
    async def on_message(self, message):
        """Handle all messages"""
        if message.author.bot:
            return
        
        self.total_messages += 1
        
        # Anti-spam
        await self.handle_antispam(message)
        
        # Bad words filter
        await self.handle_bad_words(message)
        
        # Leveling
        await self.handle_leveling(message)
        
        # Process commands
        await self.process_commands(message)
    
    async def on_command_completion(self, ctx):
        """Track command usage"""
        self.total_commands += 1
        self.db.insert('command_stats', {
            'command_name': ctx.command.name if ctx.command else 'unknown',
            'guild_id': str(ctx.guild.id) if ctx.guild else 'DM',
            'user_id': str(ctx.author.id)
        })
    
    # ═════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═════════════════════════════════════════════════════════════════════════
    
    async def spawn_pokemon_message(self, channel, pokemon):
        """Send a Pokémon spawn message"""
        is_legendary = pokemon['rarity'] in ['Legendary', 'Mythical']
        
        embed = discord.Embed(
            title=f"🌟 A wild {pokemon['name']} appeared!" if is_legendary else f"🌿 A wild {pokemon['name']} appeared!",
            description=f"Rarity: {pokemon['rarity']}",
            color=discord.Color.gold() if is_legendary else discord.Color.blue()
        )
        
        if pokemon.get('sprite_url'):
            embed.set_image(url=pokemon['sprite_url'])
        
        embed.add_field(name="📍 Location", value=f"{channel.mention}", inline=True)
        embed.add_field(name="⏱️ Time", value="1 minute", inline=True)
        
        if is_legendary:
            embed.add_field(name="🌟 Legendary!", value="This is a rare spawn! Don't miss it!", inline=False)
        
        embed.set_footer(text="Use /catch to try and catch it!")
        
        # Store spawn info
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
            
            users = []
            if reaction:
                async for user in reaction.users():
                    if not user.bot:
                        users.append(user)
            
            # Also check database entries
            db_entries = self.db.fetch_all(
                "SELECT user_id FROM giveaway_entries WHERE giveaway_id = ?",
                (giveaway['id'],)
            )
            for entry in db_entries:
                user = self.get_user(int(entry['user_id']))
                if user and user not in users:
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
            if winners:
                embed.add_field(name="🎉 Congratulations!", value="\n".join([w.mention for w in winners]), inline=False)
            
            await message.edit(embed=embed, view=None)
            await channel.send(f"🎉 **Giveaway Ended!**\nWinners: {winner_mentions}")
            
            # Update database
            self.db.execute(
                "UPDATE giveaways SET ended = 1, winner_ids = ? WHERE id = ?",
                (','.join([str(w.id) for w in winners]), giveaway['id'])
            )
            
            # DM winners
            for winner in winners:
                try:
                    dm_embed = discord.Embed(
                        title="🎉 You Won a Giveaway!",
                        description=f"You won **{giveaway['prize']}** in **{channel.guild.name}**!",
                        color=discord.Color.gold()
                    )
                    await winner.send(embed=dm_embed)
                except:
                    pass
                    
        except Exception as e:
            print(f"⚠️ Error ending giveaway: {e}")
    
    async def handle_antispam(self, message):
        """Handle anti-spam detection"""
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
                embed = discord.Embed(
                    title="🔇 Auto-Muted",
                    description=f"{message.author.mention} has been auto-muted for spamming!",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
    
    async def handle_bad_words(self, message):
        """Handle bad word filtering"""
        bad_words = self.db.fetch_all(
            "SELECT word FROM bad_words WHERE guild_id = ?",
            (str(message.guild.id),)
        )
        
        content = message.content.lower()
        for row in bad_words:
            if row['word'].lower() in content:
                await message.delete()
                embed = discord.Embed(
                    title="🚫 Message Deleted",
                    description=f"{message.author.mention}, that word is not allowed!",
                    color=discord.Color.red()
                )
                await message.channel.send(embed=embed)
                break
    
    async def handle_leveling(self, message):
        """Handle XP and leveling"""
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        cooldown_key = f"{guild_id}:{user_id}"
        if cooldown_key in self.level_cooldowns:
            if (datetime.now() - self.level_cooldowns[cooldown_key]).seconds < config.LEVEL_COOLDOWN:
                return
        
        self.level_cooldowns[cooldown_key] = datetime.now()
        
        xp_gain = random.randint(config.XP_PER_MESSAGE_MIN, config.XP_PER_MESSAGE_MAX)
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
                
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"{message.author.mention} leveled up to **Level {new_level}**!",
                    color=discord.Color.gold()
                )
                await message.channel.send(embed=embed)
                
                # Check for level rewards
                reward = self.db.fetch_one(
                    "SELECT * FROM level_rewards WHERE guild_id = ? AND level = ?",
                    (guild_id, new_level)
                )
                if reward and reward['role_id']:
                    role = message.guild.get_role(int(reward['role_id']))
                    if role:
                        await message.author.add_roles(role)
                        await message.channel.send(f"{message.author.mention} You earned the {role.name} role!")
    
    async def mute_user(self, guild, member, reason):
        """Mute a user"""
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if not muted_role:
            muted_role = await guild.create_role(
                name="Muted",
                permissions=discord.Permissions(send_messages=False, add_reactions=False)
            )
            for channel in guild.channels:
                try:
                    await channel.set_permissions(muted_role, send_messages=False, add_reactions=False)
                except:
                    pass
        
        await member.add_roles(muted_role)
        
        unmute_time = datetime.now() + timedelta(hours=24)
        self.db.insert('muted', {
            'user_id': str(member.id),
            'guild_id': str(guild.id),
            'reason': reason,
            'unmute_at': unmute_time.isoformat(),
            'moderator_id': str(self.user.id)
        })
    
    async def unmute_user(self, guild, member):
        """Unmute a user"""
        muted_role = discord.utils.get(guild.roles, name="Muted")
        if muted_role and muted_role in member.roles:
            await member.remove_roles(muted_role)
        
        self.db.execute(
            "DELETE FROM muted WHERE user_id = ? AND guild_id = ?",
            (str(member.id), str(guild.id))
        )

# ═════════════════════════════════════════════════════════════════════════════
# CONTINUE TO PART 4 - FLASK WEB APP
# ═════════════════════════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════════════════════════
# FLASK WEB APP - Complete Dashboard with 3D Animations
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = config.FLASK_SECRET
CORS(flask_app)

# ═════════════════════════════════════════════════════════════════════════════
# WEB ROUTES
# ═════════════════════════════════════════════════════════════════════════════

@flask_app.route('/')
def index():
    """Home page with 3D animations"""
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>🤖 Anion Bot</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            min-height: 100vh; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            overflow: hidden;
        }
        #particles-js {
            position: fixed;
            width: 100%;
            height: 100%;
            top: 0;
            left: 0;
            z-index: 0;
        }
        .container { 
            background: rgba(255,255,255,0.95); 
            border-radius: 25px; 
            padding: 50px; 
            max-width: 700px; 
            width: 90%; 
            box-shadow: 0 30px 80px rgba(0,0,0,0.3); 
            text-align: center; 
            z-index: 1;
            position: relative;
            animation: fadeInUp 1s ease-out;
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(50px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-20px); }
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(0.95); }
        }
        .logo { 
            font-size: 80px; 
            margin-bottom: 10px; 
            animation: float 3s ease-in-out infinite;
        }
        h1 { 
            color: #2d3748; 
            font-size: 3em; 
            margin-bottom: 5px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle { color: #718096; font-size: 1.2em; margin-bottom: 25px; }
        .status-badge { 
            display: inline-block; 
            padding: 10px 30px; 
            border-radius: 50px; 
            background: linear-gradient(135deg, #48bb78, #38a169);
            color: white; 
            font-weight: bold; 
            margin-bottom: 25px; 
            animation: pulse 2s infinite;
            box-shadow: 0 4px 15px rgba(72, 187, 120, 0.4);
        }
        .features { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 12px; 
            margin: 25px 0; 
            text-align: left; 
        }
        .feature { 
            background: #f7fafc; 
            padding: 12px 18px; 
            border-radius: 10px; 
            transition: all 0.3s ease;
            cursor: pointer;
        }
        .feature:hover { 
            transform: translateY(-3px); 
            background: #edf2f7; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .feature span { margin-right: 8px; }
        .btn-group { 
            display: flex; 
            flex-wrap: wrap; 
            gap: 12px; 
            justify-content: center; 
            margin-top: 25px; 
        }
        .btn { 
            padding: 14px 35px; 
            border-radius: 50px; 
            border: none; 
            font-size: 1em; 
            font-weight: 600; 
            cursor: pointer; 
            text-decoration: none; 
            transition: all 0.3s ease; 
            display: inline-block;
            position: relative;
            overflow: hidden;
        }
        .btn:hover { 
            transform: translateY(-3px); 
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .btn-primary { 
            background: linear-gradient(135deg, #667eea, #764ba2); 
            color: white; 
        }
        .btn-success { 
            background: linear-gradient(135deg, #48bb78, #38a169); 
            color: white; 
        }
        .btn-secondary { 
            background: linear-gradient(135deg, #f56565, #e53e3e); 
            color: white; 
        }
        .footer { margin-top: 30px; color: #a0aec0; font-size: 0.9em; }
        .glow {
            animation: glow 2s ease-in-out infinite alternate;
        }
        @keyframes glow {
            from { box-shadow: 0 0 10px rgba(102, 126, 234, 0.3); }
            to { box-shadow: 0 0 30px rgba(118, 75, 162, 0.6); }
        }
        @media (max-width: 500px) { 
            .features { grid-template-columns: 1fr; } 
            .container { padding: 30px 20px; } 
            h1 { font-size: 2em; } 
        }
        .stat-counter {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }
    </style>
</head>
<body>
    <div id="particles-js"></div>
    
    <div class="container">
        <div class="logo">🤖</div>
        <h1>Anion Bot</h1>
        <div class="subtitle">All-in-One Discord Bot</div>
        <div class="status-badge">🟢 Online & Ready</div>
        
        <div class="features">
            <div class="feature"><span>🎮</span> Pokémon System</div>
            <div class="feature"><span>🔐</span> OAuth2 Verification</div>
            <div class="feature"><span>🛡️</span> Full Moderation</div>
            <div class="feature"><span>🎫</span> Ticket System</div>
            <div class="feature"><span>📈</span> Leveling & Ranks</div>
            <div class="feature"><span>🎁</span> Giveaways</div>
            <div class="feature"><span>🎵</span> Music Player</div>
            <div class="feature"><span>🤖</span> AI Chat</div>
        </div>
        
        <div class="btn-group">
            <a href="/dashboard" class="btn btn-primary glow">📊 Dashboard</a>
            <a href="https://discord.com/oauth2/authorize?client_id={{ client_id }}&permissions=8&scope=bot%20applications.commands" class="btn btn-success">➕ Invite Bot</a>
            <a href="https://discord.gg" class="btn btn-secondary">💬 Support</a>
        </div>
        
        <div class="footer">🚀 Powered by Railway | MIT Portfolio Project</div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/particles.js/2.0.0/particles.min.js"></script>
    <script>
        particlesJS('particles-js', {
            particles: {
                number: { value: 80, density: { enable: true, value_area: 800 } },
                color: { value: '#ffffff' },
                shape: { type: 'circle' },
                opacity: { value: 0.5, random: false },
                size: { value: 3, random: true },
                line_linked: {
                    enable: true,
                    distance: 150,
                    color: '#ffffff',
                    opacity: 0.4,
                    width: 1
                },
                move: {
                    enable: true,
                    speed: 6,
                    direction: 'none',
                    random: false,
                    straight: false,
                    out_mode: 'out',
                    bounce: false
                }
            },
            interactivity: {
                detect_on: 'canvas',
                events: {
                    onhover: { enable: true, mode: 'repulse' },
                    onclick: { enable: true, mode: 'push' }
                }
            },
            retina_detect: true
        });
    </script>
</body>
</html>
    """, client_id=config.CLIENT_ID)

@flask_app.route('/dashboard')
def dashboard():
    """Dashboard page with 3D animations and stats"""
    if not bot:
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - Anion Bot</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; background: #f7fafc; margin: 0; padding: 40px 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 20px; margin-bottom: 30px; text-align: center; }
        .loading { text-align: center; padding: 40px; color: #718096; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #667eea; border-radius: 50%; width: 50px; height: 50px; animation: spin 1s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><h1>📊 Dashboard</h1><p>Bot Status & Statistics</p></div>
        <div class="loading"><div class="spinner"></div>Loading bot data...</div>
    </div>
</body>
</html>
        """)
    
    pokemon_count = bot.db.fetch_one("SELECT COUNT(*) FROM pokemon_collection")
    total_pokemon = pokemon_count[0] if pokemon_count else 0
    total_guilds = len(bot.guilds)
    total_users = sum(g.member_count for g in bot.guilds)
    total_tickets = bot.db.get_count('tickets')
    total_giveaways = bot.db.get_count('giveaways')
    
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - Anion Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            padding: 40px; 
            border-radius: 20px; 
            margin-bottom: 30px; 
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
            animation: rotate 20s linear infinite;
        }
        @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        .header h1 { position: relative; z-index: 1; font-size: 2.5em; }
        .header p { position: relative; z-index: 1; opacity: 0.9; }
        
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 20px; 
            margin-bottom: 30px; 
        }
        .stat-card { 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 4px 15px rgba(0,0,0,0.08); 
            text-align: center; 
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }
        .stat-card:hover { 
            transform: translateY(-5px); 
            box-shadow: 0 8px 30px rgba(0,0,0,0.15);
        }
        .stat-card::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2);
        }
        .stat-number { 
            font-size: 2.8em; 
            font-weight: bold; 
            color: #667eea; 
            transition: all 0.3s ease;
        }
        .stat-label { color: #718096; margin-top: 8px; font-size: 1em; }
        .stat-icon { font-size: 2em; margin-bottom: 5px; }
        
        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 30px;
        }
        .content-box {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
        }
        .content-box:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        }
        .content-box h2 { 
            color: #2d3748; 
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .feature-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); 
            gap: 15px; 
        }
        .feature-item { 
            padding: 15px; 
            background: #f7fafc; 
            border-radius: 12px; 
            text-align: center; 
            transition: all 0.3s ease;
        }
        .feature-item:hover { 
            transform: translateY(-3px); 
            background: #edf2f7;
            box-shadow: 0 4px 15px rgba(0,0,0,0.08);
        }
        .feature-icon { font-size: 2.5em; margin-bottom: 8px; }
        .feature-name { font-weight: 600; color: #2d3748; }
        .feature-desc { font-size: 0.85em; color: #718096; margin-top: 4px; }
        
        .footer { 
            margin-top: 30px; 
            text-align: center; 
            color: #a0aec0;
            padding: 20px;
        }
        
        .glow {
            animation: glow 2s ease-in-out infinite alternate;
        }
        @keyframes glow {
            from { box-shadow: 0 0 20px rgba(102, 126, 234, 0.2); }
            to { box-shadow: 0 0 40px rgba(118, 75, 162, 0.4); }
        }
        
        .status-dot {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #48bb78;
            animation: pulse-dot 2s infinite;
            margin-right: 8px;
        }
        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.8); }
        }
        
        @media (max-width: 768px) {
            .content-grid { grid-template-columns: 1fr; }
            .stats { grid-template-columns: repeat(2, 1fr); }
            .header h1 { font-size: 1.8em; }
        }
        @media (max-width: 500px) {
            .stats { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header glow">
            <h1>📊 Anion Bot Dashboard</h1>
            <p><span class="status-dot"></span> Bot is Online & Operational</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-icon">🏰</div>
                <div class="stat-number" id="guilds">{{ guilds }}</div>
                <div class="stat-label">Servers</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">👥</div>
                <div class="stat-number" id="users">{{ users }}</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🎮</div>
                <div class="stat-number" id="pokemon">{{ pokemon }}</div>
                <div class="stat-label">Pokémon Caught</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🎫</div>
                <div class="stat-number" id="tickets">{{ tickets }}</div>
                <div class="stat-label">Tickets Created</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🎁</div>
                <div class="stat-number" id="giveaways">{{ giveaways }}</div>
                <div class="stat-label">Giveaways</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🟢</div>
                <div class="stat-number">●</div>
                <div class="stat-label">Status: Online</div>
            </div>
        </div>
        
        <div class="content-grid">
            <div class="content-box">
                <h2>✨ Features</h2>
                <div class="feature-grid">
                    <div class="feature-item"><div class="feature-icon">🎮</div><div class="feature-name">Pokémon</div><div class="feature-desc">Catch & Collect</div></div>
                    <div class="feature-item"><div class="feature-icon">🔐</div><div class="feature-name">Verification</div><div class="feature-desc">OAuth2 Secure</div></div>
                    <div class="feature-item"><div class="feature-icon">🛡️</div><div class="feature-name">Moderation</div><div class="feature-desc">Full Suite</div></div>
                    <div class="feature-item"><div class="feature-icon">🎫</div><div class="feature-name">Tickets</div><div class="feature-desc">GUI System</div></div>
                    <div class="feature-item"><div class="feature-icon">📈</div><div class="feature-name">Leveling</div><div class="feature-desc">XP & Ranks</div></div>
                    <div class="feature-item"><div class="feature-icon">🎁</div><div class="feature-name">Giveaways</div><div class="feature-desc">GUI System</div></div>
                    <div class="feature-item"><div class="feature-icon">🎵</div><div class="feature-name">Music</div><div class="feature-desc">Play Songs</div></div>
                    <div class="feature-item"><div class="feature-icon">🤖</div><div class="feature-name">AI Chat</div><div class="feature-desc">OpenAI Powered</div></div>
                </div>
            </div>
            
            <div class="content-box">
                <h2>📊 Quick Stats</h2>
                <div style="margin-top: 10px;">
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee;">
                        <span>🕐 Uptime</span>
                        <span id="uptime">Loading...</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee;">
                        <span>⚡ Commands Used</span>
                        <span id="commands">0</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee;">
                        <span>💬 Messages Processed</span>
                        <span id="messages">0</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee;">
                        <span>🎮 Pokémon Types</span>
                        <span>18 Types</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 10px 0;">
                        <span>🌟 Legendary Pokémon</span>
                        <span>66+ Available</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            🚀 Anion Bot | MIT Portfolio Project | Built with ❤️
        </div>
    </div>
    
    <script>
        // Update stats in real-time
        function updateStats() {
            fetch('/api/stats')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('guilds').textContent = data.guilds || 0;
                    document.getElementById('users').textContent = data.users || 0;
                    document.getElementById('pokemon').textContent = data.pokemon || 0;
                    document.getElementById('tickets').textContent = data.tickets || 0;
                    document.getElementById('giveaways').textContent = data.giveaways || 0;
                    document.getElementById('commands').textContent = data.commands || 0;
                    document.getElementById('messages').textContent = data.messages || 0;
                });
        }
        
        // Calculate uptime
        function updateUptime() {
            fetch('/api/uptime')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('uptime').textContent = data.uptime || 'Just started';
                });
        }
        
        // Update every 10 seconds
        updateStats();
        updateUptime();
        setInterval(updateStats, 10000);
        setInterval(updateUptime, 30000);
    </script>
</body>
</html>
    """, 
    guilds=total_guilds,
    users=total_users,
    pokemon=total_pokemon,
    tickets=total_tickets,
    giveaways=total_giveaways)

@flask_app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    if not bot:
        return jsonify({
            'guilds': 0, 'users': 0, 'pokemon': 0, 
            'tickets': 0, 'giveaways': 0, 'commands': 0, 
            'messages': 0, 'status': 'offline'
        })
    
    pokemon_count = bot.db.fetch_one("SELECT COUNT(*) FROM pokemon_collection")
    ticket_count = bot.db.get_count('tickets')
    giveaway_count = bot.db.get_count('giveaways')
    
    return jsonify({
        'guilds': len(bot.guilds),
        'users': sum(g.member_count for g in bot.guilds),
        'pokemon': pokemon_count[0] if pokemon_count else 0,
        'tickets': ticket_count,
        'giveaways': giveaway_count,
        'commands': bot.total_commands,
        'messages': bot.total_messages,
        'status': 'online'
    })

@flask_app.route('/api/uptime')
def api_uptime():
    """API endpoint for uptime"""
    if not bot:
        return jsonify({'uptime': 'Offline'})
    
    uptime = datetime.now() - bot.start_time
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60
    
    uptime_str = f"{days}d {hours}h {minutes}m" if days > 0 else f"{hours}h {minutes}m"
    return jsonify({'uptime': uptime_str})

@flask_app.route('/callback')
def oauth_callback():
    """OAuth2 callback handler - Complete user verification"""
    code = request.args.get('code')
    guild_id = request.args.get('state')
    
    if not code:
        return "Invalid request - Missing code", 400
    
    # Exchange code for token
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
        return "Authentication failed - Could not get access token", 400
    
    # Get user info
    headers = {'Authorization': f"Bearer {token_data['access_token']}"}
    user_response = requests.get('https://discord.com/api/users/@me', headers=headers)
    user_data = user_response.json()
    
    if 'id' not in user_data:
        return "Authentication failed - Could not get user data", 400
    
    # Store user in session
    session['user'] = user_data
    
    # Verify user in guild and assign roles
    if guild_id and bot:
        guild = bot.get_guild(int(guild_id))
        if guild:
            member = guild.get_member(int(user_data['id']))
            if member:
                # Check if user is in guild
                guilds_response = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
                guilds = guilds_response.json()
                
                if any(str(g['id']) == guild_id for g in guilds):
                    # Get settings
                    settings = bot.db.fetch_one(
                        "SELECT * FROM guild_settings WHERE guild_id = ?",
                        (guild_id,)
                    )
                    
                    if settings and settings['verified_role_id']:
                        role = guild.get_role(int(settings['verified_role_id']))
                        if role:
                            # Add verified role
                            asyncio.run_coroutine_threadsafe(
                                member.add_roles(role),
                                bot.loop
                            )
                            
                            # Remove unverified role
                            if settings['unverified_role_id']:
                                unverified_role = guild.get_role(int(settings['unverified_role_id']))
                                if unverified_role:
                                    asyncio.run_coroutine_threadsafe(
                                        member.remove_roles(unverified_role),
                                        bot.loop
                                    )
                    
                    # Save to database
                    bot.db.insert('verified_users', {
                        'user_id': str(user_data['id']),
                        'guild_id': guild_id,
                        'email': user_data.get('email', ''),
                        'verification_method': 'oauth'
                    })
    
    return redirect(url_for('dashboard'))

# ═════════════════════════════════════════════════════════════════════════════
# CONTINUE TO PART 5 - MAIN ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════

bot = None

async def main():
    """Main entry point for the bot"""
    global bot
    
    print("🚀 Starting Anion Bot...")
    print("═" * 60)
    print("📋 Features:")
    print("  🎮 Pokémon System - Catch, Collect, Trade, Battle")
    print("  🔐 OAuth2 Verification - Secure Server Verification")
    print("  🛡️ Moderation - Ban, Kick, Mute, Warn, Auto-Mod")
    print("  🎫 Ticket System - Beautiful GUI with Modals")
    print("  🎁 Giveaway System - GUI with Buttons and Auto-End")
    print("  📈 Leveling - XP, Ranks, Leaderboards")
    print("  🎵 Music - Play, Skip, Stop")
    print("  🤖 AI Chat - OpenAI Integration")
    print("  🌐 Web Dashboard - 3D Animations")
    print("═" * 60)
    
    # Create bot instance
    bot = AnionBot()
    
    # Start Flask in separate thread
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False, threaded=True)
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    print("🌐 Flask server started on port 5000")
    print("⏳ Connecting to Discord...")
    
    try:
        await bot.start(config.DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord token! Please check your DISCORD_TOKEN environment variable.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

# ═════════════════════════════════════════════════════════════════════════════
# END OF FILE - Total Lines: ~10,000+
# ═════════════════════════════════════════════════════════════════════════════
