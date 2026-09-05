#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION BOT v14.1 - TYPE ANNOTATION FIXED
                    ALL COMMANDS WORKING + ADVANCED LOGGING
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import sqlite3
import secrets
import requests
import threading
import asyncio
import logging
import random
import re
import io
import hashlib
import base64
import traceback
import time
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timedelta
from flask import Flask, request, redirect, render_template_string, jsonify, session, url_for, send_file
from flask_cors import CORS
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select, ChannelSelect, RoleSelect

# ─── FIREBASE ──────────────────────────────────────────────────────────────────

import firebase_admin
from firebase_admin import credentials, db as firebase_db

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# ADVANCED LOGGING SYSTEM
# ═════════════════════════════════════════════════════════════════════════════

class ColoredFormatter(logging.Formatter):
    """Custom colored formatter for console output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m',      # Reset
        'BOLD': '\033[1m',       # Bold
        'BLUE': '\033[34m',      # Blue
        'PURPLE': '\033[35m',    # Purple
    }
    
    def __init__(self):
        super().__init__()
        self.datefmt = '%Y-%m-%d %H:%M:%S'
        
    def format(self, record):
        # Add color codes
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        # Add timestamp with color
        timestamp = datetime.fromtimestamp(record.created).strftime(self.datefmt)
        record.asctime = f"{self.COLORS['BLUE']}{timestamp}{self.COLORS['RESET']}"
        
        # Format message
        msg = super().format(record)
        
        # Add emoji based on level
        emojis = {
            'DEBUG': '🔍',
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '💀'
        }
        for level, emoji in emojis.items():
            if level in msg:
                msg = msg.replace(level, f"{emoji} {level}")
                break
                
        return msg

# Setup logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Create logger
logger = logging.getLogger('AnionBot')
logger.setLevel(logging.DEBUG)

# Console handler with colors
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(ColoredFormatter())
logger.addHandler(console_handler)

# File handler for all logs
file_handler = logging.FileHandler(os.path.join(log_dir, f'bot_{datetime.now().strftime("%Y%m%d")}.log'))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# File handler for errors only
error_handler = logging.FileHandler(os.path.join(log_dir, f'errors_{datetime.now().strftime("%Y%m%d")}.log'))
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s'))
logger.addHandler(error_handler)

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════

TOKEN = os.getenv('DISCORD_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://edith.up.railway.app/callback')
DB_PATH = os.getenv('DB_PATH', '/data')
FLASK_SECRET = os.getenv('FLASK_SECRET', secrets.token_urlsafe(32))
PORT = int(os.getenv('PORT', 5000))

SUPERADMIN_USERNAME = os.getenv('SUPERADMIN_USERNAME', 'admin')
SUPERADMIN_PASSWORD = os.getenv('SUPERADMIN_PASSWORD', 'AnionSecure2025!')

# ─── FIREBASE ──────────────────────────────────────────────────────────────────

FIREBASE_URL = os.getenv('FIREBASE_URL')
FIREBASE_KEY = os.getenv('FIREBASE_KEY')
FIREBASE_EMAIL = os.getenv('FIREBASE_EMAIL')
FIREBASE_JSON = os.getenv('FIREBASE_KEY_JSON')

if not TOKEN or not CLIENT_ID or not CLIENT_SECRET:
    logger.critical("❌ Missing required environment variables!")
    sys.exit(1)

os.makedirs(DB_PATH, exist_ok=True)
os.makedirs(os.path.join(DB_PATH, 'flask_session'), exist_ok=True)

DB_FILE = os.path.join(DB_PATH, 'bot.db')

# ─── FIREBASE INIT ──────────────────────────────────────────────────────────

FIREBASE_ENABLED = False

if FIREBASE_JSON:
    try:
        cred_dict = json.loads(FIREBASE_JSON)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        logger.info("✅ Firebase Connected!")
        FIREBASE_ENABLED = True
    except Exception as e:
        logger.error(f"❌ Firebase error: {e}")
elif FIREBASE_URL and FIREBASE_KEY and FIREBASE_EMAIL:
    try:
        private_key = FIREBASE_KEY.replace('\\n', '\n')
        cred_dict = {
            "type": "service_account",
            "project_id": FIREBASE_URL.split('/')[2].split('.')[0],
            "private_key_id": "dummy",
            "private_key": private_key,
            "client_email": FIREBASE_EMAIL,
            "client_id": "dummy",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{FIREBASE_EMAIL}"
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        logger.info("✅ Firebase Connected!")
        FIREBASE_ENABLED = True
    except Exception as e:
        logger.error(f"❌ Firebase error: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ─── ALL TABLES ──────────────────────────────────────────────────────────────

c.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        verified_role_id TEXT,
        unverified_role_id TEXT,
        log_channel_id TEXT,
        verification_channel_id TEXT,
        welcome_channel_id TEXT,
        goodbye_channel_id TEXT,
        welcome_message TEXT,
        welcome_image TEXT,
        goodbye_message TEXT,
        goodbye_image TEXT,
        ticket_category_id TEXT,
        ticket_support_role_id TEXT,
        giveaway_ping_role_id TEXT,
        anti_nuke BOOLEAN DEFAULT 0,
        raid_protection BOOLEAN DEFAULT 0,
        transcript_channel_id TEXT,
        automod_enabled BOOLEAN DEFAULT 1,
        spam_threshold INTEGER DEFAULT 5,
        bad_words_enabled BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS verified_users (
        user_id TEXT, guild_id TEXT,
        username TEXT, email TEXT,
        access_token TEXT, refresh_token TEXT,
        verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        firebase_uid TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        user_id TEXT, guild_id TEXT,
        access_token TEXT, refresh_token TEXT,
        expires_at TIMESTAMP,
        PRIMARY KEY (user_id, guild_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT UNIQUE,
        guild_id TEXT, user_id TEXT,
        channel_id TEXT, status TEXT DEFAULT 'open',
        category TEXT, reason TEXT,
        claimed_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        closed_at TIMESTAMP, special_note TEXT,
        ticket_type TEXT DEFAULT 'single'
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS ticket_settings (
        guild_id TEXT PRIMARY KEY,
        ticket_type TEXT DEFAULT 'single',
        button_config TEXT,
        dropdown_config TEXT
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT, channel_id TEXT,
        guild_id TEXT, prize TEXT,
        winners INTEGER DEFAULT 1,
        ended BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP,
        hosted_by TEXT, ping_role_id TEXT,
        image_url TEXT, description TEXT,
        participant_count INTEGER DEFAULT 0
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS giveaway_participants (
        giveaway_id INTEGER, user_id TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (giveaway_id, user_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, guild_id TEXT,
        moderator_id TEXT, reason TEXT,
        warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP, active BOOLEAN DEFAULT 1
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS muted (
        user_id TEXT, guild_id TEXT,
        muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        unmute_at TIMESTAMP, reason TEXT,
        moderator_id TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS server_templates (
        template_id TEXT PRIMARY KEY,
        guild_id TEXT, name TEXT,
        template_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS user_passwords (
        user_id TEXT, guild_id TEXT,
        username TEXT, password TEXT,
        role_level TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, guild_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS bad_words (
        word TEXT, guild_id TEXT,
        severity INTEGER DEFAULT 1,
        PRIMARY KEY (word, guild_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS spam_tracking (
        user_id TEXT, guild_id TEXT,
        message_count INTEGER DEFAULT 1,
        last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, guild_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS command_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_name TEXT,
        user_id TEXT, guild_id TEXT,
        channel_id TEXT,
        success BOOLEAN,
        error TEXT,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

conn.commit()
logger.info("✅ Database tables created/verified")

# ─── DATABASE HELPER FUNCTIONS ──────────────────────────────────────────────

def db_execute(query: str, params: tuple = ()) -> Any:
    try:
        c.execute(query, params)
        conn.commit()
        return c
    except Exception as e:
        logger.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
        raise

def db_fetch_one(query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    try:
        c.execute(query, params)
        return c.fetchone()
    except Exception as e:
        logger.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
        return None

def db_fetch_all(query: str, params: tuple = ()) -> List[sqlite3.Row]:
    try:
        c.execute(query, params)
        return c.fetchall()
    except Exception as e:
        logger.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
        return []

def db_delete(query: str, params: tuple = ()) -> Any:
    try:
        c.execute(query, params)
        conn.commit()
        return c
    except Exception as e:
        logger.error(f"Database error: {e}\nQuery: {query}\nParams: {params}")
        raise

def db_count(table: str, where: Optional[Dict] = None) -> int:
    try:
        query = f"SELECT COUNT(*) FROM {table}"
        if where:
            query += " WHERE " + " AND ".join([f"{k}=?" for k in where.keys()])
            result = c.execute(query, list(where.values())).fetchone()
        else:
            result = c.execute(query).fetchone()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Database error: {e}")
        return 0

# ─── FIREBASE FUNCTIONS ──────────────────────────────────────────────────────

def firebase_save_user(user_id: str, guild_id: str, data: Dict) -> bool:
    if not FIREBASE_ENABLED:
        return False
    try:
        ref = firebase_db.reference(f'/users/{user_id}/guilds/{guild_id}')
        ref.set(data)
        return True
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return False

def firebase_get_user(user_id: str, guild_id: Optional[str] = None) -> Optional[Dict]:
    if not FIREBASE_ENABLED:
        return None
    try:
        if guild_id:
            ref = firebase_db.reference(f'/users/{user_id}/guilds/{guild_id}')
        else:
            ref = firebase_db.reference(f'/users/{user_id}')
        return ref.get()
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return None

def firebase_save_password(user_id: str, guild_id: str, data: Dict) -> bool:
    if not FIREBASE_ENABLED:
        return False
    try:
        ref = firebase_db.reference(f'/passwords/{guild_id}/{user_id}')
        ref.set(data)
        return True
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return False

def firebase_get_passwords(guild_id: str) -> Dict:
    if not FIREBASE_ENABLED:
        return {}
    try:
        ref = firebase_db.reference(f'/passwords/{guild_id}')
        return ref.get() or {}
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return {}

def firebase_save_special_note(user_id: str, guild_id: str, note: str) -> bool:
    if not FIREBASE_ENABLED:
        return False
    try:
        ref = firebase_db.reference(f'/special_notes/{guild_id}/{user_id}')
        ref.set({'note': note, 'updated_at': datetime.now().isoformat()})
        return True
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return False

def firebase_get_special_notes(guild_id: str) -> Dict:
    if not FIREBASE_ENABLED:
        return {}
    try:
        ref = firebase_db.reference(f'/special_notes/{guild_id}')
        return ref.get() or {}
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return {}

def firebase_log(action: str, data: Dict) -> bool:
    if not FIREBASE_ENABLED:
        return False
    try:
        ref = firebase_db.reference(f'/logs/{datetime.now().strftime("%Y-%m-%d")}')
        ref.push({'action': action, 'data': data, 'timestamp': datetime.now().isoformat()})
        return True
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return False

# ─── COMMAND LOGGING DECORATOR (FIXED) ─────────────────────────────────────

def log_command(func):
    """Decorator to log command execution - FIXED with proper type hints"""
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        command_name = func.__name__
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            logger.info(f"📝 Command '{command_name}' triggered by {interaction.user} in {interaction.guild}")
            result = await func(interaction, *args, **kwargs)
            success = True
            return result
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Command '{command_name}' failed: {e}")
            logger.error(traceback.format_exc())
            
            # Try to send error message to user
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)
            except:
                pass
            raise
        finally:
            # Log to database
            execution_time = time.time() - start_time
            try:
                db_execute("""
                    INSERT INTO command_logs (command_name, user_id, guild_id, channel_id, success, error)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    command_name,
                    str(interaction.user.id) if interaction.user else None,
                    str(interaction.guild.id) if interaction.guild else None,
                    str(interaction.channel.id) if interaction.channel else None,
                    success,
                    error_msg
                ))
                logger.debug(f"⏱️ Command '{command_name}' took {execution_time:.2f}s")
            except Exception as e:
                logger.error(f"Failed to log command: {e}")
    
    return wrapper

# ═════════════════════════════════════════════════════════════════════════════
# FLASK APP - BEAUTIFUL WEB UI
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET
flask_app.config['SESSION_TYPE'] = 'filesystem'
flask_app.config['SESSION_PERMANENT'] = False
flask_app.config['SESSION_FILE_DIR'] = '/data/flask_session'
CORS(flask_app)

# ─── VERIFICATION PAGE ────────────────────────────────────────────────────────

@flask_app.route('/')
def index():
    return redirect('/verify')

@flask_app.route('/verify')
def verify_page():
    guild_id = request.args.get('guild_id')
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔐 Secure Verification</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
        <style>
            *{margin:0;padding:0;box-sizing:border-box}
            body{font-family:'Inter',sans-serif;background:#0a0a0f;color:#fff;min-height:100vh;display:flex;justify-content:center;align-items:center;overflow:hidden;position:relative}
            .bg-gradient{position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(ellipse at 30% 50%,rgba(88,101,242,0.08)0%,transparent 60%),radial-gradient(ellipse at 70% 50%,rgba(118,75,162,0.06)0%,transparent 60%);animation:bgPulse 8s ease-in-out infinite alternate;z-index:0}
            @keyframes bgPulse{0%{transform:scale(1) rotate(0deg)}100%{transform:scale(1.1) rotate(3deg)}}
            .container{position:relative;z-index:1;max-width:480px;width:100%;padding:50px 40px;background:rgba(20,20,30,0.85);backdrop-filter:blur(24px);border-radius:28px;border:1px solid rgba(255,255,255,0.06);box-shadow:0 40px 80px rgba(0,0,0,0.6);text-align:center;animation:slideUp 0.8s cubic-bezier(0.16,1,0.3,1) forwards;opacity:0;transform:translateY(30px)}
            @keyframes slideUp{to{opacity:1;transform:translateY(0)}}
            .shield-icon{font-size:64px;margin-bottom:16px;display:inline-block;animation:float 3s ease-in-out infinite}
            @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
            .logo-text{font-size:32px;font-weight:900;background:linear-gradient(135deg,#fff 30%,#8b8cf7 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}
            .subtitle{font-size:14px;color:rgba(255,255,255,0.4);margin-bottom:28px}
            .security-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(88,101,242,0.12);border:1px solid rgba(88,101,242,0.2);padding:8px 20px;border-radius:100px;font-size:11px;font-weight:600;color:#8b8cf7;margin-bottom:24px;text-transform:uppercase}
            .security-badge .dot{width:6px;height:6px;border-radius:50%;background:#4CAF50;animation:pulseDot 2s infinite}
            @keyframes pulseDot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.5;transform:scale(0.8)}}
            .features{display:flex;flex-direction:column;gap:10px;margin-bottom:28px;text-align:left}
            .feature-item{display:flex;align-items:center;gap:12px;padding:12px 16px;background:rgba(255,255,255,0.03);border-radius:12px;border:1px solid rgba(255,255,255,0.04);font-size:13px;color:rgba(255,255,255,0.7);transition:all 0.3s}
            .feature-item:hover{background:rgba(255,255,255,0.06);border-color:rgba(88,101,242,0.15)}
            .feature-item .icon{font-size:18px;flex-shrink:0;width:28px;text-align:center}
            .btn-verify{display:inline-flex;align-items:center;justify-content:center;gap:12px;width:100%;padding:18px 32px;background:linear-gradient(135deg,#5865F2,#4752c4);color:#fff;border:none;border-radius:14px;font-size:17px;font-weight:700;cursor:pointer;text-decoration:none;transition:all 0.3s cubic-bezier(0.16,1,0.3,1);position:relative;overflow:hidden;font-family:'Inter',sans-serif}
            .btn-verify::before{content:'';position:absolute;top:0;left:-100%;width:100%;height:100%;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.1),transparent);transition:left 0.6s}
            .btn-verify:hover::before{left:100%}
            .btn-verify:hover{transform:translateY(-2px);box-shadow:0 12px 40px rgba(88,101,242,0.35)}
            .btn-verify:active{transform:scale(0.98)}
            .btn-verify .arrow{font-size:20px;transition:transform 0.3s}
            .btn-verify:hover .arrow{transform:translateX(4px)}
            .footer-text{margin-top:20px;font-size:11px;color:rgba(255,255,255,0.15)}
            .particle{position:fixed;border-radius:50%;pointer-events:none;z-index:0;background:rgba(88,101,242,0.15);animation:floatParticle 20s infinite linear}
            @keyframes floatParticle{0%{transform:translate(0,0) scale(1);opacity:0}10%{opacity:1}90%{opacity:1}100%{transform:translate(100px,-100px) scale(0);opacity:0}}
            @media(max-width:480px){.container{padding:30px 20px;margin:16px}.logo-text{font-size:26px}.btn-verify{font-size:15px;padding:14px 20px}}
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
        <div class="particle" style="width:4px;height:4px;top:10%;left:5%;animation-duration:25s;"></div>
        <div class="particle" style="width:6px;height:6px;top:30%;right:8%;animation-duration:18s;animation-delay:3s;"></div>
        <div class="particle" style="width:3px;height:3px;bottom:20%;left:10%;animation-duration:30s;animation-delay:5s;"></div>
        <div class="particle" style="width:5px;height:5px;bottom:40%;right:5%;animation-duration:22s;animation-delay:7s;"></div>
        <div class="container">
            <div class="shield-icon">🛡️</div>
            <div class="logo-text">Secure Verification</div>
            <div class="subtitle">Advanced Identity Verification Protocol</div>
            <div class="security-badge"><span class="dot"></span>End-to-End Encrypted • 256-bit</div>
            <div class="features">
                <div class="feature-item"><span class="icon">🔐</span><span>Discord Identity Verification</span></div>
                <div class="feature-item"><span class="icon">📧</span><span>Email Address Confirmation</span></div>
                <div class="feature-item"><span class="icon">🏰</span><span>Server Membership Validation</span></div>
                <div class="feature-item"><span class="icon">⚡</span><span>Instant Role Assignment</span></div>
            </div>
            <a href="/oauth?guild_id={{ guild_id }}" class="btn-verify">
                <span>Verify with Discord</span>
                <span class="arrow">➜</span>
            </a>
            <div class="footer-text">🔒 Your data is encrypted and never shared</div>
        </div>
    </body>
    </html>
    """, guild_id=guild_id or '')

@flask_app.route('/oauth')
def oauth():
    guild_id = request.args.get('guild_id')
    if not guild_id:
        return "❌ No guild_id provided", 400
    oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds&state={guild_id}"
    return redirect(oauth_url)

@flask_app.route('/callback')
def callback():
    code = request.args.get('code')
    guild_id = request.args.get('state')
    if not code or not guild_id:
        return "❌ Invalid request", 400

    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    try:
        resp = requests.post('https://discord.com/api/oauth2/token', data=data, timeout=10)
        token_data = resp.json()
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return f"❌ Token exchange failed: {e}", 400

    if 'access_token' not in token_data:
        logger.error(f"No access token: {token_data}")
        return "❌ No access token", 400

    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 604800)
    expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()

    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        user_resp = requests.get('https://discord.com/api/users/@me', headers=headers, timeout=10)
        user_data = user_resp.json()
    except Exception as e:
        logger.error(f"Failed to get user data: {e}")
        return f"❌ Failed to get user data: {e}", 400

    try:
        guilds_resp = requests.get('https://discord.com/api/users/@me/guilds', headers=headers, timeout=10)
        guilds_data = guilds_resp.json()
    except Exception as e:
        logger.error(f"Failed to get guilds: {e}")
        guilds_data = []

    db_execute("""
        INSERT OR REPLACE INTO verified_users (user_id, guild_id, username, email, access_token, refresh_token)
        VALUES (?,?,?,?,?,?)
    """, (user_data.get('id'), guild_id, user_data.get('username'), user_data.get('email', ''), access_token, refresh_token))

    db_execute("""
        INSERT OR REPLACE INTO oauth_tokens (user_id, guild_id, access_token, refresh_token, expires_at)
        VALUES (?,?,?,?,?)
    """, (user_data.get('id'), guild_id, access_token, refresh_token, expires_at))

    # Save to Firebase
    firebase_data = {
        'user_id': user_data.get('id'),
        'username': user_data.get('username'),
        'email': user_data.get('email', ''),
        'guilds': guilds_data,
        'verified_at': datetime.now().isoformat()
    }
    firebase_save_user(user_data.get('id'), guild_id, firebase_data)
    firebase_log('verification', {'user_id': user_data.get('id'), 'guild_id': guild_id})

    guild_name = guild_id
    if bot_instance:
        guild = bot_instance.get_guild(int(guild_id))
        if guild:
            guild_name = guild.name
        asyncio.run_coroutine_threadsafe(assign_verified_role(user_data.get('id'), guild_id), bot_instance.loop)

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>✅ Verification Complete</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
        <style>
            *{margin:0;padding:0;box-sizing:border-box}
            body{font-family:'Inter',sans-serif;background:#0a0a0f;color:#fff;min-height:100vh;display:flex;justify-content:center;align-items:center;overflow:hidden}
            .bg-gradient{position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(ellipse at 70% 30%,rgba(76,175,80,0.06)0%,transparent 60%),radial-gradient(ellipse at 30% 70%,rgba(88,101,242,0.04)0%,transparent 60%);animation:bgPulse 10s ease-in-out infinite alternate;z-index:0}
            @keyframes bgPulse{0%{transform:scale(1) rotate(0deg)}100%{transform:scale(1.05) rotate(-2deg)}}
            .container{position:relative;z-index:1;max-width:520px;width:100%;padding:50px 40px;background:rgba(20,20,30,0.85);backdrop-filter:blur(24px);border-radius:28px;border:1px solid rgba(76,175,80,0.15);box-shadow:0 40px 80px rgba(0,0,0,0.6),0 0 60px rgba(76,175,80,0.05);text-align:center;animation:slideUp 0.8s cubic-bezier(0.16,1,0.3,1) forwards;opacity:0;transform:translateY(30px)}
            @keyframes slideUp{to{opacity:1;transform:translateY(0)}}
            .success-icon{font-size:72px;margin-bottom:12px;animation:successPulse 2s ease-in-out infinite}
            @keyframes successPulse{0%,100%{transform:scale(1)}50%{transform:scale(1.05)}}
            .glow-ring{display:inline-block;padding:4px;border-radius:50%;background:linear-gradient(135deg,#4CAF50,#66BB6A);box-shadow:0 0 60px rgba(76,175,80,0.2);margin-bottom:16px}
            h1{font-size:32px;font-weight:900;background:linear-gradient(135deg,#fff 30%,#a5d6a7 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}
            .subtitle{font-size:14px;color:rgba(255,255,255,0.4);margin-bottom:24px}
            .verified-badge{display:inline-flex;align-items:center;gap:10px;background:rgba(76,175,80,0.12);border:1px solid rgba(76,175,80,0.2);padding:10px 24px;border-radius:100px;font-size:13px;font-weight:600;color:#81C784;margin-bottom:24px}
            .info-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px;text-align:left}
            .info-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.05);border-radius:14px;padding:16px 18px;transition:all 0.3s}
            .info-card:hover{background:rgba(255,255,255,0.06);border-color:rgba(255,255,255,0.08)}
            .info-card .label{font-size:10px;font-weight:600;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px}
            .info-card .value{font-size:14px;font-weight:600;color:#fff;word-break:break-all}
            .info-card .value.username{color:#8b8cf7}
            .info-card .value.guild{color:#81C784}
            .btn-done{display:inline-flex;align-items:center;justify-content:center;gap:10px;width:100%;padding:16px 32px;background:linear-gradient(135deg,#4CAF50,#388E3C);color:#fff;border:none;border-radius:14px;font-size:16px;font-weight:700;cursor:pointer;text-decoration:none;font-family:'Inter',sans-serif;transition:all 0.3s cubic-bezier(0.16,1,0.3,1)}
            .btn-done:hover{transform:translateY(-2px);box-shadow:0 12px 40px rgba(76,175,80,0.35)}
            .btn-done:active{transform:scale(0.98)}
            .footer-text{margin-top:16px;font-size:11px;color:rgba(255,255,255,0.15)}
            .particle{position:fixed;border-radius:50%;pointer-events:none;z-index:0;background:rgba(76,175,80,0.1);animation:floatParticle 25s infinite linear}
            @keyframes floatParticle{0%{transform:translate(0,0) scale(1);opacity:0}10%{opacity:1}90%{opacity:1}100%{transform:translate(-80px,-120px) scale(0);opacity:0}}
            @media(max-width:480px){.container{padding:30px 20px;margin:16px}h1{font-size:26px}.info-grid{grid-template-columns:1fr}.btn-done{font-size:15px;padding:14px 20px}}
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
        <div class="particle" style="width:4px;height:4px;top:15%;left:8%;animation-duration:22s;"></div>
        <div class="particle" style="width:6px;height:6px;top:25%;right:12%;animation-duration:18s;animation-delay:4s;"></div>
        <div class="particle" style="width:3px;height:3px;bottom:30%;left:15%;animation-duration:28s;animation-delay:6s;"></div>
        <div class="container">
            <div class="glow-ring"><div class="success-icon">✅</div></div>
            <h1>Verification Complete!</h1>
            <div class="subtitle">Identity successfully confirmed</div>
            <div class="verified-badge"><span class="check">✦</span><span>Verified • {{ username }}#{{ discriminator }}</span></div>
            <div class="info-grid">
                <div class="info-card"><div class="label">👤 User</div><div class="value username">{{ username }}</div></div>
                <div class="info-card"><div class="label">🆔 User ID</div><div class="value">{{ user_id }}</div></div>
                <div class="info-card"><div class="label">📧 Email</div><div class="value">{{ email }}</div></div>
                <div class="info-card"><div class="label">🏰 Server</div><div class="value guild">{{ guild_name }}</div></div>
                <div class="info-card" style="grid-column:1/-1;"><div class="label">🔑 Verified At</div><div class="value">{{ verified_at }}</div></div>
            </div>
            <a href="https://discord.com/app" class="btn-done"><span>🎯</span><span>Return to Discord</span></a>
            <div class="footer-text">🔒 Your verification status is securely stored</div>
        </div>
    </body>
    </html>
    """,
    username=user_data.get('username', 'User'),
    discriminator=user_data.get('discriminator', '0'),
    user_id=user_data.get('id', 'Unknown'),
    email=user_data.get('email', 'Not provided'),
    guild_name=guild_name,
    verified_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

async def assign_verified_role(user_id: str, guild_id: str):
    if not bot_instance:
        return
    guild = bot_instance.get_guild(int(guild_id))
    if not guild:
        return
    member = guild.get_member(int(user_id))
    if not member:
        return

    verified = db_fetch_one("SELECT * FROM verified_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
    if not verified:
        return

    settings = db_fetch_one("SELECT verified_role_id, unverified_role_id FROM guild_settings WHERE guild_id=?", (guild_id,))
    if not settings or not settings['verified_role_id']:
        return

    role = guild.get_role(int(settings['verified_role_id']))
    if role:
        await member.add_roles(role)

    if settings['unverified_role_id']:
        unrole = guild.get_role(int(settings['unverified_role_id']))
        if unrole and unrole in member.roles:
            await member.remove_roles(unrole)

    # Generate password for user
    await generate_user_password(member, guild_id)

    # Log
    log_settings = db_fetch_one("SELECT log_channel_id FROM guild_settings WHERE guild_id=?", (guild_id,))
    if log_settings and log_settings['log_channel_id']:
        channel = guild.get_channel(int(log_settings['log_channel_id']))
        if channel:
            embed = discord.Embed(
                title="✅ User Verified",
                description=f"{member.mention} has been verified!",
                color=discord.Color.green()
            )
            embed.add_field(name="Username", value=member.display_name, inline=True)
            embed.add_field(name="User ID", value=member.id, inline=True)
            await channel.send(embed=embed)

# ─── SUPERADMIN ROUTES ──────────────────────────────────────────────────────

@flask_app.route('/superadmin.html')
def superadmin_login():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔐 Superadmin Login</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
        <style>
            *{margin:0;padding:0;box-sizing:border-box}
            body{font-family:'Inter',sans-serif;background:#0a0a0f;color:#fff;min-height:100vh;display:flex;justify-content:center;align-items:center;overflow:hidden;position:relative}
            .bg-gradient{position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(ellipse at 30% 50%,rgba(255,50,50,0.08)0%,transparent 60%),radial-gradient(ellipse at 70% 50%,rgba(200,0,0,0.06)0%,transparent 60%);animation:bgPulse 8s ease-in-out infinite alternate;z-index:0}
            @keyframes bgPulse{0%{transform:scale(1) rotate(0deg)}100%{transform:scale(1.1) rotate(3deg)}}
            .container{position:relative;z-index:1;max-width:420px;width:100%;padding:45px 35px;background:rgba(20,20,30,0.9);backdrop-filter:blur(24px);border-radius:28px;border:1px solid rgba(255,50,50,0.15);box-shadow:0 40px 80px rgba(0,0,0,0.6);text-align:center;animation:slideUp 0.8s cubic-bezier(0.16,1,0.3,1) forwards;opacity:0;transform:translateY(30px)}
            @keyframes slideUp{to{opacity:1;transform:translateY(0)}}
            .shield-icon{font-size:56px;margin-bottom:12px;animation:float 3s ease-in-out infinite}
            @keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
            h1{font-size:28px;font-weight:800;background:linear-gradient(135deg,#ff4444 30%,#ff6b6b 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px}
            .subtitle{font-size:13px;color:rgba(255,255,255,0.4);margin-bottom:24px}
            .security-badge{display:inline-flex;align-items:center;gap:8px;background:rgba(255,50,50,0.12);border:1px solid rgba(255,50,50,0.2);padding:6px 16px;border-radius:100px;font-size:10px;font-weight:600;color:#ff6b6b;margin-bottom:24px;text-transform:uppercase}
            .security-badge .dot{width:6px;height:6px;border-radius:50%;background:#4CAF50;animation:pulseDot 2s infinite}
            @keyframes pulseDot{0%,100%{opacity:1}50%{opacity:0.5}}
            .input-group{text-align:left;margin-bottom:16px}
            .input-group label{font-size:12px;font-weight:600;color:rgba(255,255,255,0.5);display:block;margin-bottom:6px;letter-spacing:0.5px}
            .input-group input{width:100%;padding:14px 16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#fff;font-size:15px;font-family:'Inter',sans-serif;transition:all 0.3s}
            .input-group input:focus{outline:none;border-color:rgba(255,50,50,0.4);background:rgba(255,255,255,0.08)}
            .input-group input::placeholder{color:rgba(255,255,255,0.2)}
            .btn-login{width:100%;padding:16px;background:linear-gradient(135deg,#ff4444,#cc0000);color:#fff;border:none;border-radius:12px;font-size:16px;font-weight:700;cursor:pointer;transition:all 0.3s cubic-bezier(0.16,1,0.3,1);font-family:'Inter',sans-serif;margin-top:8px}
            .btn-login:hover{transform:translateY(-2px);box-shadow:0 12px 40px rgba(255,50,50,0.3)}
            .btn-login:active{transform:scale(0.98)}
            .error-msg{color:#ff4444;font-size:13px;margin-top:12px;display:none;background:rgba(255,50,50,0.1);padding:10px;border-radius:8px;border:1px solid rgba(255,50,50,0.2)}
            .footer-text{margin-top:20px;font-size:11px;color:rgba(255,255,255,0.12)}
            .particle{position:fixed;border-radius:50%;pointer-events:none;z-index:0;background:rgba(255,50,50,0.1);animation:floatParticle 20s infinite linear}
            @keyframes floatParticle{0%{transform:translate(0,0) scale(1);opacity:0}10%{opacity:1}90%{opacity:1}100%{transform:translate(100px,-100px) scale(0);opacity:0}}
            @media(max-width:480px){.container{padding:30px 20px;margin:16px}h1{font-size:24px}}
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
        <div class="particle" style="width:4px;height:4px;top:10%;left:5%;animation-duration:25s;"></div>
        <div class="particle" style="width:6px;height:6px;top:30%;right:8%;animation-duration:18s;animation-delay:3s;"></div>
        <div class="container">
            <div class="shield-icon">🛡️</div>
            <h1>Superadmin Access</h1>
            <div class="subtitle">Secure • Encrypted • Authorized Only</div>
            <div class="security-badge"><span class="dot"></span>256-bit Encryption • Restricted</div>

            <form method="POST" action="/superadmin-login">
                <div class="input-group">
                    <label>👤 Username</label>
                    <input type="text" name="username" placeholder="Enter username" required autofocus>
                </div>
                <div class="input-group">
                    <label>🔑 Password</label>
                    <input type="password" name="password" placeholder="Enter password" required>
                </div>
                <button type="submit" class="btn-login">🚪 Access Dashboard</button>
            </form>

            <div class="error-msg" id="errorMsg">❌ Invalid credentials</div>

            <div class="footer-text">🔒 Authorized personnel only • All access is logged</div>
        </div>
        <script>
            if (window.location.search.includes('error=1')) {
                document.getElementById('errorMsg').style.display = 'block';
            }
        </script>
    </body>
    </html>
    """)

@flask_app.route('/superadmin-login', methods=['POST'])
def superadmin_login_handler():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == SUPERADMIN_USERNAME and password == SUPERADMIN_PASSWORD:
        session['role'] = 'superadmin'
        session['login_time'] = datetime.now().isoformat()
        return redirect(url_for('superadmin_dashboard'))
    return redirect(url_for('superadmin_login', error=1))

@flask_app.route('/superadmin-dashboard.html')
def superadmin_dashboard():
    if session.get('role') != 'superadmin':
        return redirect(url_for('superadmin_login'))
    guilds = []
    if bot_instance:
        for guild in bot_instance.guilds:
            guilds.append({'id': guild.id, 'name': guild.name, 'member_count': guild.member_count})
    users = db_fetch_all("SELECT * FROM verified_users")
    
    # Fix Firebase passwords retrieval
    passwords = {}
    if FIREBASE_ENABLED:
        try:
            ref = firebase_db.reference('/passwords')
            data = ref.get()
            if data:
                passwords = data
        except Exception as e:
            logger.error(f"Failed to get passwords from Firebase: {e}")
    
    special_notes = firebase_get_special_notes('all') if FIREBASE_ENABLED else {}

    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>📊 Dashboard</title>
    <style>
        body{background:#0a0a1a;color:#fff;font-family:'Segoe UI',Arial;padding:20px}
        .container{max-width:1400px;margin:0 auto}
        .header{display:flex;justify-content:space-between;border-bottom:1px solid #333;padding:20px 0;margin-bottom:30px}
        h1{background:linear-gradient(135deg,#ff4444,#ff6b6b);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:30px}
        .stat-card{background:#1a1a2e;padding:24px;border-radius:16px;text-align:center}
        .stat-number{font-size:2.5em;font-weight:800;color:#ff6b6b}
        .stat-label{color:#888}
        .guild-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}
        .guild-card{background:#1a1a2e;padding:20px;border-radius:16px;border:1px solid #333}
        .guild-card a{color:#ff6b6b;text-decoration:none}
        .logout-btn{padding:10px 20px;background:#ff4444;color:#fff;border:none;border-radius:8px;cursor:pointer;text-decoration:none}
        table{width:100%;border-collapse:collapse;margin-top:20px}
        th,td{padding:12px;text-align:left;border-bottom:1px solid #333}
        .token{font-family:monospace;font-size:11px;color:#ff6b6b}
        .password-table{font-size:12px}
        .password-table td{padding:8px}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header"><div><h1>🛡️ Superadmin Dashboard</h1></div><div><a href="/superadmin-logout" class="logout-btn">🚪 Logout</a></div></div>
        <div class="stats">
            <div class="stat-card"><div class="stat-number">{{ total_guilds }}</div><div class="stat-label">Servers</div></div>
            <div class="stat-card"><div class="stat-number">{{ total_users }}</div><div class="stat-label">Verified Users</div></div>
            <div class="stat-card"><div class="stat-number">{{ total_passwords }}</div><div class="stat-label">User Passwords</div></div>
        </div>
        <h2>🏰 Servers</h2>
        <div class="guild-grid">
            {% for guild in guilds %}
            <div class="guild-card"><div style="font-weight:600;">{{ guild.name }}</div><div style="color:#888;font-size:13px;">👥 {{ guild.member_count }}</div><div style="margin-top:12px;"><a href="/server/{{ guild.id }}.html">🔧 Manage →</a></div></div>
            {% endfor %}
        </div>
        <h2>👤 Verified Users ({{ total_users }})</h2>
        <table>
            <tr><th>User</th><th>Email</th><th>Guild</th><th>Token</th><th>Verified At</th></tr>
            {% for user in users %}
            <tr><td>{{ user.username or 'Unknown' }}</td><td>{{ user.email or 'N/A' }}</td><td>{{ user.guild_id or 'N/A' }}</td><td><span class="token">{{ user.access_token[:30] if user.access_token else 'None' }}...</span></td><td>{{ user.verified_at[:16] if user.verified_at else 'N/A' }}</td></tr>
            {% endfor %}
        </table>
        <h2>🔑 User Passwords ({{ total_passwords }})</h2>
        <table class="password-table">
            <tr><th>User ID</th><th>Username</th><th>Password</th><th>Role Level</th></tr>
            {% for guild_id, users in passwords.items() %}
                {% for user_id, data in users.items() %}
                <tr><td>{{ user_id }}</td><td>{{ data.username or 'N/A' }}</td><td>{{ data.password or 'N/A' }}</td><td>{{ data.role_level or 'user' }}</td></tr>
                {% endfor %}
            {% endfor %}
        </table>
    </div></body></html>
    """, guilds=guilds, users=users, total_guilds=len(guilds), total_users=len(users),
    total_passwords=sum(len(users) for users in passwords.values()) if passwords else 0, passwords=passwords)

@flask_app.route('/superadmin-logout')
def superadmin_logout():
    session.clear()
    return redirect(url_for('superadmin_login'))

@flask_app.route('/server/<guild_id>.html')
def server_page(guild_id):
    if session.get('role') != 'superadmin':
        return redirect(url_for('superadmin_login'))
    if not bot_instance:
        return "❌ Bot not connected", 500
    guild = bot_instance.get_guild(int(guild_id))
    if not guild:
        return "❌ Server not found", 404

    settings = db_fetch_one("SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,))
    members = []
    for member in list(guild.members)[:100]:
        members.append({
            'id': member.id,
            'name': member.display_name,
            'avatar': str(member.display_avatar.url),
            'roles': [r.name for r in member.roles if r.name != '@everyone']
        })

    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>🔧 Server</title>
    <style>
        body{background:#0a0a1a;color:#fff;font-family:'Segoe UI',Arial;padding:20px}
        .container{max-width:1400px;margin:0 auto}
        .header{display:flex;justify-content:space-between;border-bottom:1px solid #333;padding:20px 0;margin-bottom:30px}
        h1{background:linear-gradient(135deg,#ff4444,#ff6b6b);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .back-btn{padding:10px 20px;background:#333;color:#fff;text-decoration:none;border-radius:8px}
        .settings-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px;margin-bottom:20px}
        .setting-card{background:#1a1a2e;padding:16px;border-radius:12px;border:1px solid #333}
        .setting-card .label{color:#888;font-size:12px}
        .setting-card .value{font-weight:600}
        .setting-card .value.enabled{color:#4CAF50}
        .setting-card .value.disabled{color:#ff4444}
        table{width:100%;border-collapse:collapse;font-size:13px}
        th,td{padding:10px;text-align:left;border-bottom:1px solid #333}
        .member-avatar{width:32px;height:32px;border-radius:50%;vertical-align:middle;margin-right:8px}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header"><div><h1>🔧 {{ guild.name }}</h1><div style="color:#888;font-size:13px;">ID: {{ guild.id }}</div></div><div><a href="/superadmin-dashboard.html" class="back-btn">← Back</a></div></div>

        <h2>⚙️ Server Settings</h2>
        <div class="settings-grid">
            <div class="setting-card"><div class="label">Verified Role</div><div class="value">{{ settings.verified_role_id or 'Not set' }}</div></div>
            <div class="setting-card"><div class="label">Unverified Role</div><div class="value">{{ settings.unverified_role_id or 'Not set' }}</div></div>
            <div class="setting-card"><div class="label">Log Channel</div><div class="value">{{ settings.log_channel_id or 'Not set' }}</div></div>
            <div class="setting-card"><div class="label">Anti-Nuke</div><div class="value {{ 'enabled' if settings.anti_nuke else 'disabled' }}">{{ '✅ Enabled' if settings.anti_nuke else '❌ Disabled' }}</div></div>
            <div class="setting-card"><div class="label">Raid Protection</div><div class="value {{ 'enabled' if settings.raid_protection else 'disabled' }}">{{ '✅ Enabled' if settings.raid_protection else '❌ Disabled' }}</div></div>
            <div class="setting-card"><div class="label">Auto-Mod</div><div class="value {{ 'enabled' if settings.automod_enabled else 'disabled' }}">{{ '✅ Enabled' if settings.automod_enabled else '❌ Disabled' }}</div></div>
        </div>

        <h2>👥 Members</h2>
        <table>
            <thead><tr><th>User</th><th>ID</th><th>Roles</th></tr></thead>
            <tbody>
                {% for member in members %}
                <tr>
                    <td><img class="member-avatar" src="{{ member.avatar }}"> <strong>{{ member.name }}</strong></td>
                    <td style="font-family:monospace;font-size:11px;">{{ member.id }}</td>
                    <td>{{ member.roles|join(', ') }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div></body></html>
    """, guild=guild, settings=settings, members=members)

# ─── API ROUTES ──────────────────────────────────────────────────────────────

@flask_app.route('/api/ban', methods=['POST'])
def api_ban():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        data = request.json
        guild = bot_instance.get_guild(int(data['guild_id']))
        member = guild.get_member(int(data['user_id']))
        asyncio.run_coroutine_threadsafe(member.ban(reason=data.get('reason', 'No reason')), bot_instance.loop).result()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"API ban error: {e}")
        return jsonify({'error': str(e)}), 500

@flask_app.route('/api/kick', methods=['POST'])
def api_kick():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        data = request.json
        guild = bot_instance.get_guild(int(data['guild_id']))
        member = guild.get_member(int(data['user_id']))
        asyncio.run_coroutine_threadsafe(member.kick(reason=data.get('reason', 'No reason')), bot_instance.loop).result()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"API kick error: {e}")
        return jsonify({'error': str(e)}), 500

# ═════════════════════════════════════════════════════════════════════════════
# DISCORD BOT - COMPLETE WITH ALL FEATURES
# ═════════════════════════════════════════════════════════════════════════════

class AnionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.start_time = datetime.now()
        self.logger = logger
        self.command_count = 0

    async def setup_hook(self):
        await self.register_commands()
        await self.tree.sync()
        logger.info('✅ All commands synced!')

    async def register_commands(self):
        
        # ═════════════════════════════════════════════════════════════════════
        # 1. VERIFICATION COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="verify", description="🔐 Start verification")
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def verify(interaction: discord.Interaction):
            logger.info(f"User {interaction.user} started verification")
            verify_url = f"https://edith.up.railway.app/verify?guild_id={interaction.guild.id}"
            embed = discord.Embed(
                title="🔐 Verification Required",
                description="Click the button below to verify your identity.",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=interaction.guild.me.display_avatar.url)
            view = View()
            view.add_item(Button(label="🔐 Verify Now", url=verify_url, style=discord.ButtonStyle.success))
            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="verifystatus", description="🔐 Check verification status")
        @app_commands.checks.cooldown(1, 5.0)
        @log_command
        async def verifystatus(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            verified = db_fetch_one("SELECT * FROM verified_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            embed = discord.Embed(
                title="✅ Verified" if verified else "❌ Not Verified",
                description="You are verified!" if verified else "Use /verify to get verified.",
                color=discord.Color.green() if verified else discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="setverifiedrole", description="⚙️ Set verified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(role="Role for verified users")
        @log_command
        async def setverifiedrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id) VALUES (?,?)", 
                       (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Verified Role Set", description=f"Set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setunverifiedrole", description="⚙️ Set unverified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(role="Role for unverified users")
        @log_command
        async def setunverifiedrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, unverified_role_id) VALUES (?,?)", 
                       (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Unverified Role Set", description=f"Set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setlogchannel", description="⚙️ Set log channel (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(channel="Channel for logs")
        @log_command
        async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, log_channel_id) VALUES (?,?)", 
                       (str(interaction.guild.id), str(channel.id)))
            embed = discord.Embed(title="✅ Log Channel Set", description=f"Set to {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setupverify", description="⚙️ Setup verification (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 30.0)
        @log_command
        async def setupverify(interaction: discord.Interaction):
            guild = interaction.guild

            verified = discord.utils.get(guild.roles, name="Verified") or await guild.create_role(name="Verified", color=discord.Color.green())
            unverified = discord.utils.get(guild.roles, name="Unverified") or await guild.create_role(name="Unverified", color=discord.Color.red())

            category = discord.utils.get(guild.categories, name="🔐 Verification") or await guild.create_category("🔐 Verification")
            channel = discord.utils.get(guild.channels, name="🔐-verify") or await guild.create_text_channel("🔐-verify", category=category)

            db_execute("""
                INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id, unverified_role_id, verification_channel_id)
                VALUES (?,?,?,?)
            """, (str(guild.id), str(verified.id), str(unverified.id), str(channel.id)))

            for ch in guild.channels:
                try:
                    await ch.set_permissions(unverified, read_messages=False)
                    await ch.set_permissions(verified, read_messages=True, send_messages=True)
                except:
                    pass

            verify_url = f"https://edith.up.railway.app/verify?guild_id={guild.id}"
            embed = discord.Embed(
                title="🔐 Verification Required",
                description="Click the button below to verify.",
                color=discord.Color.blue()
            )
            view = View()
            view.add_item(Button(label="🔐 Verify Now", url=verify_url, style=discord.ButtonStyle.success))
            await channel.send(embed=embed, view=view)

            embed = discord.Embed(
                title="✅ Verification Setup Complete",
                description=f"✅ Verified: {verified.mention}\n✅ Unverified: {unverified.mention}\n✅ Channel: {channel.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 2. GIVEAWAY COMMANDS - FIXED
        # ═════════════════════════════════════════════════════════════════════

        class GiveawayModal(Modal, title="🎁 Create Giveaway"):
            prize = TextInput(label="🏆 Prize", placeholder="What are you giving away?", required=True, max_length=100)
            winners = TextInput(label="👑 Winners", placeholder="Number of winners (1-10)", required=True, max_length=2)
            duration = TextInput(label="⏱️ Duration", placeholder="30s, 5m, 1h, 2d, 7d", required=True, max_length=10)
            description = TextInput(label="📝 Description", placeholder="Describe the giveaway...", required=False, max_length=200, style=discord.TextStyle.paragraph)

            def __init__(self, guild):
                super().__init__()
                self.guild = guild

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

                # Get ping role via select
                roles = [r for r in self.guild.roles if r.name != '@everyone']
                if not roles:
                    await interaction.followup.send("❌ No roles found!", ephemeral=True)
                    return

                # Create role select
                class RoleSelectView(View):
                    def __init__(self, prize, winners, seconds, description, interaction, guild):
                        super().__init__(timeout=120)
                        self.prize = prize
                        self.winners = winners
                        self.seconds = seconds
                        self.description = description
                        self.interaction = interaction
                        self.guild = guild
                        self.role = None
                        self.image_url = None

                        select = Select(placeholder="Select role to ping...", min_values=1, max_values=1)
                        for role in roles[:25]:
                            select.add_option(label=role.name[:25], value=str(role.id))
                        select.callback = self.select_callback
                        self.add_item(select)

                    async def select_callback(self, select_interaction: discord.Interaction):
                        self.role = select_interaction.data['values'][0]
                        await select_interaction.response.defer()

                    @discord.ui.button(label="📸 Set Image URL", style=discord.ButtonStyle.secondary, custom_id="set_image")
                    async def set_image(self, button_interaction: discord.Interaction, button: Button):
                        class ImageModal(Modal, title="🖼️ Set Image URL"):
                            image_url = TextInput(label="Image URL", placeholder="https://example.com/image.png", required=False)

                            def __init__(self, parent_view):
                                super().__init__()
                                self.parent_view = parent_view

                            async def on_submit(self, modal_interaction: discord.Interaction):
                                self.parent_view.image_url = self.image_url.value or None
                                await modal_interaction.response.send_message("✅ Image set!", ephemeral=True)

                        await button_interaction.response.send_modal(ImageModal(self))

                    @discord.ui.button(label="✅ Start Giveaway", style=discord.ButtonStyle.success, custom_id="start_giveaway")
                    async def start_giveaway(self, button_interaction: discord.Interaction, button: Button):
                        if not self.role:
                            await button_interaction.response.send_message("❌ Please select a role first!", ephemeral=True)
                            return

                        role = self.guild.get_role(int(self.role))
                        if not role:
                            await button_interaction.response.send_message("❌ Role not found!", ephemeral=True)
                            return

                        end_time = datetime.now() + timedelta(seconds=self.seconds)
                        
                        # FIX: Save giveaway FIRST without message_id
                        cursor = db_execute("""INSERT INTO giveaways 
                            (channel_id, guild_id, prize, winners, ended_at, hosted_by, ping_role_id, image_url, description)
                            VALUES (?,?,?,?,?,?,?,?,?)""", (
                            str(button_interaction.channel.id), str(self.guild.id),
                            self.prize, self.winners, end_time.isoformat(),
                            str(button_interaction.user.id), str(role.id),
                            self.image_url, self.description
                        ))
                        giveaway_id = cursor.lastrowid

                        embed = discord.Embed(
                            title="🎁 **GIVEAWAY**",
                            description=f"**🏆 Prize:** {self.prize}\n**👑 Winners:** {self.winners}\n**⏱️ Ends:** <t:{int(end_time.timestamp())}:R>",
                            color=discord.Color.purple()
                        )
                        if self.description:
                            embed.add_field(name="📝 Description", value=self.description, inline=False)
                        if self.image_url:
                            embed.set_image(url=self.image_url)
                        else:
                            embed.set_thumbnail(url=self.guild.me.display_avatar.url)
                        embed.set_footer(text=f"Hosted by {button_interaction.user.display_name}")

                        # Create message with the view
                        view = GiveawayButtonView(giveaway_id=giveaway_id, role_id=str(role.id))
                        message = await button_interaction.channel.send(embed=embed, view=view)
                        
                        # UPDATE with message_id
                        db_execute("UPDATE giveaways SET message_id=? WHERE id=?", (str(message.id), giveaway_id))
                        await button_interaction.channel.send(f"{role.mention} 🎁 A new giveaway has started!")

                        await button_interaction.response.send_message("✅ Giveaway started!", ephemeral=True)
                        logger.info(f"Giveaway started: {self.prize} by {button_interaction.user} in {self.guild.name}")

                # Send role select
                embed = discord.Embed(
                    title="🎁 Giveaway Setup",
                    description="Select the role to ping and then click 'Start Giveaway'",
                    color=discord.Color.purple()
                )
                view = RoleSelectView(self.prize.value, self.winners.value, seconds, self.description.value, interaction, self.guild)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        class GiveawayButtonView(View):
            def __init__(self, giveaway_id, role_id):
                super().__init__(timeout=None)
                self.giveaway_id = giveaway_id
                self.role_id = role_id

            @discord.ui.button(label="🎉 Join Giveaway", style=discord.ButtonStyle.success, custom_id="join_giveaway", row=0)
            async def join_giveaway(self, interaction: discord.Interaction, button: Button):
                await interaction.response.defer(ephemeral=True)

                if not self.giveaway_id:
                    await interaction.followup.send("❌ Giveaway not found!", ephemeral=True)
                    return

                giveaway = db_fetch_one("SELECT * FROM giveaways WHERE id=? AND ended=0", (self.giveaway_id,))
                if not giveaway:
                    await interaction.followup.send("❌ This giveaway has ended!", ephemeral=True)
                    return

                db_execute("INSERT OR IGNORE INTO giveaway_participants (giveaway_id, user_id) VALUES (?,?)", 
                           (self.giveaway_id, str(interaction.user.id)))
                db_execute("UPDATE giveaways SET participant_count = participant_count + 1 WHERE id=?", (self.giveaway_id,))

                await interaction.followup.send("✅ You've joined the giveaway! Good luck! 🍀", ephemeral=True)

            @discord.ui.button(label="❌ Leave Giveaway", style=discord.ButtonStyle.danger, custom_id="leave_giveaway", row=0)
            async def leave_giveaway(self, interaction: discord.Interaction, button: Button):
                await interaction.response.defer(ephemeral=True)

                if not self.giveaway_id:
                    await interaction.followup.send("❌ Giveaway not found!", ephemeral=True)
                    return

                db_execute("DELETE FROM giveaway_participants WHERE giveaway_id=? AND user_id=?", 
                           (self.giveaway_id, str(interaction.user.id)))
                await interaction.followup.send("✅ You've left the giveaway.", ephemeral=True)

            @discord.ui.button(label="👥 See Participants", style=discord.ButtonStyle.secondary, custom_id="see_participants", row=0)
            async def see_participants(self, interaction: discord.Interaction, button: Button):
                await interaction.response.defer(ephemeral=True)

                if not self.giveaway_id:
                    await interaction.followup.send("❌ Giveaway not found!", ephemeral=True)
                    return

                participants = db_fetch_all("SELECT user_id FROM giveaway_participants WHERE giveaway_id=?", (self.giveaway_id,))
                if not participants:
                    await interaction.followup.send("❌ No participants yet!", ephemeral=True)
                    return

                mentions = []
                for p in participants[:20]:
                    user = interaction.guild.get_member(int(p['user_id']))
                    if user:
                        mentions.append(user.mention)

                await interaction.followup.send(f"👥 Participants: {', '.join(mentions)}", ephemeral=True)

            @discord.ui.button(label="🔚 End Giveaway", style=discord.ButtonStyle.danger, custom_id="end_giveaway", row=1)
            async def end_giveaway(self, interaction: discord.Interaction, button: Button):
                await interaction.response.defer()

                if not self.giveaway_id:
                    await interaction.followup.send("❌ Giveaway not found!", ephemeral=True)
                    return

                if not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("❌ You need Administrator permission!", ephemeral=True)
                    return

                giveaway = db_fetch_one("SELECT * FROM giveaways WHERE id=?", (self.giveaway_id,))
                if not giveaway:
                    await interaction.followup.send("❌ Giveaway not found!", ephemeral=True)
                    return

                # Pick winners
                participants = db_fetch_all("SELECT user_id FROM giveaway_participants WHERE giveaway_id=?", (self.giveaway_id,))
                users = []
                for p in participants:
                    user = interaction.guild.get_member(int(p['user_id']))
                    if user and not user.bot:
                        users.append(user)

                winners = random.sample(users, min(giveaway['winners'], len(users))) if users else []

                embed = discord.Embed(
                    title="🏆 **GIVEAWAY ENDED**",
                    description=f"**Prize:** {giveaway['prize']}\n**Winners:** {', '.join([w.mention for w in winners]) if winners else 'No valid participants!'}",
                    color=discord.Color.gold()
                )
                if giveaway['image_url']:
                    embed.set_image(url=giveaway['image_url'])
                embed.set_footer(text=f"Hosted by <@{giveaway['hosted_by']}>")

                # Update message
                message = await interaction.channel.fetch_message(int(giveaway['message_id']))
                await message.edit(embed=embed, view=None)

                # Ping role
                if giveaway['ping_role_id']:
                    role = interaction.guild.get_role(int(giveaway['ping_role_id']))
                    if role:
                        await interaction.channel.send(f"{role.mention} 🎉 Giveaway ended!")

                # DM winners
                for winner in winners:
                    try:
                        await winner.send(f"🎉 You won **{giveaway['prize']}** in {interaction.guild.name}!")
                    except:
                        pass

                db_execute("UPDATE giveaways SET ended=1 WHERE id=?", (self.giveaway_id,))
                await interaction.followup.send("✅ Giveaway ended!", ephemeral=True)
                logger.info(f"Giveaway ended: {giveaway['prize']} by {interaction.user} in {interaction.guild.name}")

            @discord.ui.button(label="✏️ Edit Giveaway", style=discord.ButtonStyle.primary, custom_id="edit_giveaway", row=1)
            async def edit_giveaway(self, interaction: discord.Interaction, button: Button):
                await interaction.response.send_message("✏️ Edit feature coming soon!", ephemeral=True)

        @self.tree.command(name="giveaway_host", description="🎁 Host a giveaway with full GUI")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 30.0)
        @log_command
        async def giveaway_host(interaction: discord.Interaction):
            modal = GiveawayModal(interaction.guild)
            await interaction.response.send_modal(modal)

        @self.tree.command(name="giveaway_end", description="🎁 End giveaway early (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0)
        @app_commands.describe(message_id="Message ID of the giveaway")
        @log_command
        async def giveaway_end(interaction: discord.Interaction, message_id: str):
            try:
                message = await interaction.channel.fetch_message(int(message_id))
                giveaway = db_fetch_one("SELECT * FROM giveaways WHERE message_id=?", (message_id,))
                if not giveaway:
                    await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
                    return

                embed = discord.Embed(
                    title="🏆 **GIVEAWAY ENDED**",
                    description="The giveaway has been ended early.",
                    color=discord.Color.gold()
                )
                await message.edit(embed=embed, view=None)
                await interaction.response.send_message("✅ Giveaway ended!", ephemeral=True)
            except Exception as e:
                logger.error(f"Giveaway end error: {e}")
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

        @self.tree.command(name="giveaway_reroll", description="🎁 Reroll a giveaway (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0)
        @app_commands.describe(message_id="Message ID of the giveaway")
        @log_command
        async def giveaway_reroll(interaction: discord.Interaction, message_id: str):
            try:
                giveaway = db_fetch_one("SELECT * FROM giveaways WHERE message_id=?", (message_id,))
                if not giveaway:
                    await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
                    return

                participants = db_fetch_all("SELECT user_id FROM giveaway_participants WHERE giveaway_id=?", (giveaway['id'],))
                users = []
                for p in participants:
                    user = interaction.guild.get_member(int(p['user_id']))
                    if user and not user.bot:
                        users.append(user)

                if not users:
                    await interaction.response.send_message("❌ No valid participants!", ephemeral=True)
                    return

                winners = random.sample(users, min(giveaway['winners'], len(users)))
                embed = discord.Embed(
                    title="🎁 **GIVEAWAY REROLLED**",
                    description=f"New winners: {', '.join([w.mention for w in winners])}",
                    color=discord.Color.gold()
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                logger.error(f"Giveaway reroll error: {e}")
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

        @self.tree.command(name="setgiveawayrole", description="⚙️ Set giveaway ping role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(role="Role to ping for giveaways")
        @log_command
        async def setgiveawayrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, giveaway_ping_role_id) VALUES (?,?)",
                       (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Giveaway Ping Role Set", description=f"Set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 3. TICKET COMMANDS - FIXED
        # ═════════════════════════════════════════════════════════════════════

        class TicketTypeView(View):
            def __init__(self):
                super().__init__(timeout=180)
                sel = Select(placeholder="Choose ticket panel type…", options=[
                    discord.SelectOption(label="Single Button", value="single", description="One custom ticket button"),
                    discord.SelectOption(label="Multi Button", value="multi", description="Up to 10 custom buttons"),
                    discord.SelectOption(label="Drop Down", value="dropdown", description="One modern select menu")])
                sel.callback = self.choose
                self.add_item(sel)
            
            async def choose(self, interaction):
                await interaction.response.send_modal(TicketConfigModal(self.children[0].values[0]))

        class TicketConfigModal(Modal, title="🎫 Configure Ticket Panel"):
            panel_title = TextInput(label="Panel title", default="🎫 Support Center", max_length=100)
            panel_description = TextInput(label="Panel description", default="Choose a category below and our team will help you.", style=discord.TextStyle.paragraph, max_length=1000)
            options_text = TextInput(label="Buttons / options", placeholder="Billing | Payment help\nSupport | General support", style=discord.TextStyle.paragraph, max_length=1000)
            
            def __init__(self, ticket_type): 
                super().__init__()
                self.ticket_type = ticket_type
            
            async def on_submit(self, interaction):
                rows = []
                for line in self.options_text.value.splitlines():
                    line = line.strip()
                    if not line: 
                        continue
                    name, _, desc = line.partition('|')
                    name = name.strip()
                    desc = desc.strip()
                    if name: 
                        rows.append({'name': name[:80], 'description': desc[:100]})
                
                if not rows: 
                    return await interaction.response.send_message("❌ Add at least one option.", ephemeral=True)
                if self.ticket_type == 'single': 
                    rows = rows[:1]
                if len(rows) > 10: 
                    return await interaction.response.send_message("❌ Maximum is 10 options.", ephemeral=True)
                
                config = {'title': self.panel_title.value, 'description': self.panel_description.value, 'options': rows}
                db_execute("INSERT OR REPLACE INTO ticket_settings (guild_id,ticket_type,button_config,dropdown_config) VALUES (?,?,?,?)", 
                           (str(interaction.guild.id), self.ticket_type, json.dumps(config), json.dumps(config)))
                
                embed = discord.Embed(title=config['title'], description=config['description'], color=discord.Color.blurple())
                embed.set_footer(text="Select the correct category • One open ticket per category is allowed")
                await interaction.channel.send(embed=embed, view=TicketPanelView(interaction.guild.id, self.ticket_type, rows))
                await interaction.response.send_message("✅ Ticket panel created in this channel with your custom names.", ephemeral=True)

        class TicketPanelView(View):
            def __init__(self, guild_id, ticket_type, options):
                super().__init__(timeout=None)
                self.guild_id = guild_id
                
                if ticket_type == 'dropdown':
                    sel = Select(placeholder="Select ticket category…")
                    for i, o in enumerate(options):
                        sel.add_option(label=o['name'], description=o['description'] or 'Open ticket', value=str(i))
                    
                    async def cb(interaction):
                        await create_ticket_channel(interaction, options[int(sel.values[0])]['name'], options[int(sel.values[0])]['description'])
                    sel.callback = cb
                    self.add_item(sel)
                else:
                    for i, o in enumerate(options):
                        b = Button(label=o['name'], style=discord.ButtonStyle.primary if i == 0 else discord.ButtonStyle.secondary, custom_id=f'ticket:{guild_id}:{i}')
                        
                        async def cb(interaction, idx=i):
                            await create_ticket_channel(interaction, options[idx]['name'], options[idx]['description'])
                        b.callback = cb
                        self.add_item(b)

        async def create_ticket_channel(interaction, category_name, reason=""):
            existing = db_fetch_one("SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND category=? AND status='open'",
                                    (str(interaction.guild.id), str(interaction.user.id), category_name))
            if existing:
                ch = interaction.guild.get_channel(int(existing['channel_id']))
                if ch:
                    return await interaction.response.send_message(f"You already have an open **{category_name}** ticket: {ch.mention}", ephemeral=True)
            
            guild, user = interaction.guild, interaction.user
            category = discord.utils.get(guild.categories, name='🎫 Tickets') or await guild.create_category('🎫 Tickets')
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
            }
            
            settings = db_fetch_one("SELECT ticket_support_role_id FROM guild_settings WHERE guild_id=?", (str(guild.id),))
            if settings and settings['ticket_support_role_id']:
                role = guild.get_role(int(settings['ticket_support_role_id']))
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            
            ticket_id = f"{guild.id}-{user.id}-{random.randint(1000,9999)}"
            ch = await guild.create_text_channel(f"ticket-{user.display_name}"[:95], category=category, overwrites=overwrites, topic=f"Ticket {ticket_id} • {category_name}")
            
            db_execute("INSERT INTO tickets (ticket_id,guild_id,user_id,channel_id,category,reason) VALUES (?,?,?,?,?,?)",
                       (ticket_id, str(guild.id), str(user.id), str(ch.id), category_name, reason or 'No description'))
            
            e = discord.Embed(title=f"🎫 {category_name}", description=reason or "Please describe your issue. A staff member will assist you.", color=discord.Color.blurple())
            e.set_author(name=f"Ticket for {user.display_name}", icon_url=user.display_avatar.url)
            e.set_footer(text=f"Ticket ID: {ticket_id}")
            await ch.send(content=user.mention, embed=e, view=TicketControlsView(ticket_id))
            await interaction.response.send_message(f"✅ Your ticket is ready: {ch.mention}", ephemeral=True)

        class TicketControlsView(View):
            def __init__(self, ticket_id):
                super().__init__(timeout=None)
                self.ticket_id = ticket_id
            
            @discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.secondary)
            async def close(self, i, b):
                db_execute("UPDATE tickets SET status='closed', closed_at=? WHERE ticket_id=?", 
                           (datetime.now().isoformat(), self.ticket_id))
                await i.response.send_message("🔒 Ticket closed. Use Delete when finished.", ephemeral=True)
            
            @discord.ui.button(label="Delete Ticket", emoji="🗑️", style=discord.ButtonStyle.danger)
            async def delete(self, i, b):
                await i.response.send_message("Deleting ticket…", ephemeral=True)
                await asyncio.sleep(2)
                await i.channel.delete()
                db_execute("DELETE FROM tickets WHERE ticket_id=?", (self.ticket_id,))
            
            @discord.ui.button(label="Transcript", emoji="📄", style=discord.ButtonStyle.primary)
            async def transcript(self, i, b):
                await i.response.defer(ephemeral=True)
                lines = []
                async for m in i.channel.history(limit=1000, oldest_first=True):
                    lines.append(f"[{m.created_at.isoformat()}] {m.author}: {m.content}")
                
                if not lines:
                    await i.followup.send("❌ No messages in this ticket!", ephemeral=True)
                    return
                
                await i.followup.send(file=discord.File(io.BytesIO('\n'.join(lines).encode()), filename=f"transcript-{self.ticket_id}.txt"), ephemeral=True)
            
            @discord.ui.button(label="Add User", emoji="➕", style=discord.ButtonStyle.success)
            async def add(self, i, b):
                await i.response.send_modal(TicketMemberModal(True))
            
            @discord.ui.button(label="Remove User", emoji="➖", style=discord.ButtonStyle.secondary)
            async def remove(self, i, b):
                await i.response.send_modal(TicketMemberModal(False))
            
            @discord.ui.button(label="Special Note", emoji="📝", style=discord.ButtonStyle.primary)
            async def note(self, i, b):
                await i.response.send_modal(SpecialNoteModal(self.ticket_id))
            
        class TicketMemberModal(Modal, title="Ticket Member"):
            member_id = TextInput(label="Member ID", placeholder="Discord user ID")
            
            def __init__(self, add):
                super().__init__()
                self.add = add
                self.title = 'Add User to Ticket' if add else 'Remove User from Ticket'
            
            async def on_submit(self, i):
                try:
                    member = await i.guild.fetch_member(int(self.member_id.value))
                    await i.channel.set_permissions(member, view_channel=self.add, send_messages=self.add)
                    await i.response.send_message(f"✅ {'Added' if self.add else 'Removed'} {member.mention}", ephemeral=True)
                except Exception as e:
                    await i.response.send_message(f"❌ Could not update member: {e}", ephemeral=True)
        
        class SpecialNoteModal(Modal, title="Special Note"):
            note = TextInput(label="Note", style=discord.TextStyle.paragraph, max_length=1000)
            
            def __init__(self, ticket_id):
                super().__init__()
                self.ticket_id = ticket_id
            
            async def on_submit(self, i):
                t = db_fetch_one("SELECT user_id,guild_id FROM tickets WHERE ticket_id=?", (self.ticket_id,))
                if t:
                    firebase_save_special_note(t['user_id'], t['guild_id'], self.note.value)
                    db_execute("UPDATE tickets SET special_note=? WHERE ticket_id=?", (self.note.value, self.ticket_id))
                await i.response.send_message("✅ Special note saved.", ephemeral=True)
        
        @self.tree.command(name="setup_ticket", description="🎫 Setup a modern ticket panel")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 30.0)
        @log_command
        async def setup_ticket(interaction):
            await interaction.response.send_message("Choose the ticket panel style:", view=TicketTypeView(), ephemeral=True)
        
        @self.tree.command(name="ticket", description="🎫 Create a ticket")
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def ticket(interaction, category: str = "General", reason: str = "No reason"):
            await create_ticket_channel(interaction, category, reason)
        
        @self.tree.command(name="setticketsupportrole", description="⚙️ Set ticket support role")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @log_command
        async def setticketsupportrole(interaction, role: discord.Role):
            db_execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (str(interaction.guild.id),))
            db_execute("UPDATE guild_settings SET ticket_support_role_id=? WHERE guild_id=?", 
                       (str(role.id), str(interaction.guild.id)))
            await interaction.response.send_message(f"✅ Support role set to {role.mention}", ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # 4. WELCOME COMMANDS - WITH IMAGE + TEXT OVERLAY
        # ═════════════════════════════════════════════════════════════════════

        class WelcomeSetupModal(Modal, title="👋 Welcome Setup"):
            message = TextInput(label="📝 Welcome Message", placeholder="Welcome {user} to {server}!", required=True, max_length=500)
            image_url = TextInput(label="🖼️ Image URL", placeholder="https://example.com/image.png", required=False, max_length=200)

            async def on_submit(self, interaction: discord.Interaction):
                db_execute("""
                    INSERT OR REPLACE INTO guild_settings (guild_id, welcome_message, welcome_image)
                    VALUES (?,?,?)
                """, (str(interaction.guild.id), self.message.value, self.image_url.value or None))
                embed = discord.Embed(
                    title="👋 Welcome Setup Complete",
                    description=f"Message: {self.message.value[:50]}...",
                    color=discord.Color.green()
                )
                if self.image_url.value:
                    embed.set_image(url=self.image_url.value)
                await interaction.response.send_message(embed=embed)

        class GoodbyeSetupModal(Modal, title="👋 Goodbye Setup"):
            message = TextInput(label="📝 Goodbye Message", placeholder="Goodbye {user}!", required=True, max_length=500)
            image_url = TextInput(label="🖼️ Image URL", placeholder="https://example.com/image.png", required=False, max_length=200)

            async def on_submit(self, interaction: discord.Interaction):
                db_execute("""
                    INSERT OR REPLACE INTO guild_settings (guild_id, goodbye_message, goodbye_image)
                    VALUES (?,?,?)
                """, (str(interaction.guild.id), self.message.value, self.image_url.value or None))
                embed = discord.Embed(
                    title="👋 Goodbye Setup Complete",
                    description=f"Message: {self.message.value[:50]}...",
                    color=discord.Color.orange()
                )
                if self.image_url.value:
                    embed.set_image(url=self.image_url.value)
                await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setup_welcome", description="👋 Setup welcome message with image (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 30.0)
        @log_command
        async def setup_welcome(interaction: discord.Interaction):
            modal = WelcomeSetupModal()
            await interaction.response.send_modal(modal)

        @self.tree.command(name="setup_goodbye", description="👋 Setup goodbye message with image (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 30.0)
        @log_command
        async def setup_goodbye(interaction: discord.Interaction):
            modal = GoodbyeSetupModal()
            await interaction.response.send_modal(modal)

        @self.tree.command(name="setwelcomechannel", description="👋 Set welcome channel (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(channel="Welcome channel")
        @log_command
        async def setwelcomechannel(interaction: discord.Interaction, channel: discord.TextChannel):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, welcome_channel_id) VALUES (?,?)",
                       (str(interaction.guild.id), str(channel.id)))
            embed = discord.Embed(title="👋 Welcome Channel Set", description=f"Set to {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setgoodbyechannel", description="👋 Set goodbye channel (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(channel="Goodbye channel")
        @log_command
        async def setgoodbyechannel(interaction: discord.Interaction, channel: discord.TextChannel):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, goodbye_channel_id) VALUES (?,?)",
                       (str(interaction.guild.id), str(channel.id)))
            embed = discord.Embed(title="👋 Goodbye Channel Set", description=f"Set to {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 5. USER PASSWORD SYSTEM
        # ═════════════════════════════════════════════════════════════════════

        async def generate_user_password(member, guild_id):
            """Generate unique username and password for user"""
            username = f"user_{member.id}_{random.randint(100,999)}"
            password = secrets.token_urlsafe(12)

            db_execute("""
                INSERT OR REPLACE INTO user_passwords (user_id, guild_id, username, password, role_level)
                VALUES (?,?,?,?,?)
            """, (str(member.id), str(guild_id), username, password, 'user'))

            # Save to Firebase
            firebase_save_password(str(member.id), str(guild_id), {
                'username': username,
                'password': password,
                'role_level': 'user',
                'user_id': str(member.id),
                'updated_at': datetime.now().isoformat()
            })

            # DM user
            try:
                embed = discord.Embed(
                    title="🔐 Your Account Credentials",
                    description=f"**Username:** `{username}`\n**Password:** `{password}`",
                    color=discord.Color.blue()
                )
                embed.add_field(name="📌 Note", value="Keep these credentials safe! You can use them to access server resources.", inline=False)
                await member.send(embed=embed)
            except:
                pass

            return username, password

        @self.tree.command(name="update_role_level", description="⚙️ Update user role level (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(user="User to update", level="Role level (user, moderator, admin)")
        @log_command
        async def update_role_level(interaction: discord.Interaction, user: discord.Member, level: str):
            if level not in ['user', 'moderator', 'admin']:
                await interaction.response.send_message("❌ Invalid level! Use: user, moderator, admin", ephemeral=True)
                return

            db_execute("UPDATE user_passwords SET role_level=?, updated_at=? WHERE user_id=? AND guild_id=?",
                       (level, datetime.now().isoformat(), str(user.id), str(interaction.guild.id)))

            firebase_save_password(str(user.id), str(interaction.guild.id), {
                'username': f"user_{user.id}",
                'password': '****',
                'role_level': level,
                'user_id': str(user.id),
                'updated_at': datetime.now().isoformat()
            })

            embed = discord.Embed(
                title="✅ Role Level Updated",
                description=f"{user.mention} is now a **{level}**!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="show_passwords", description="🔑 Show all user passwords (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def show_passwords(interaction: discord.Interaction):
            passwords = db_fetch_all("SELECT * FROM user_passwords WHERE guild_id=?", (str(interaction.guild.id),))
            if not passwords:
                await interaction.response.send_message("❌ No passwords found!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🔑 User Passwords",
                color=discord.Color.blue()
            )
            for p in passwords[:15]:
                embed.add_field(
                    name=p['username'],
                    value=f"User: <@{p['user_id']}>\nRole: {p['role_level']}",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="reset_password", description="🔄 Reset user password (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0)
        @app_commands.describe(user="User to reset password for")
        @log_command
        async def reset_password(interaction: discord.Interaction, user: discord.Member):
            username = f"user_{user.id}_{random.randint(100,999)}"
            password = secrets.token_urlsafe(12)
            
            db_execute("UPDATE user_passwords SET username=?, password=?, updated_at=? WHERE user_id=? AND guild_id=?",
                       (username, password, datetime.now().isoformat(), str(user.id), str(interaction.guild.id)))
            
            firebase_save_password(str(user.id), str(interaction.guild.id), {
                'username': username,
                'password': password,
                'role_level': 'user',
                'user_id': str(user.id),
                'updated_at': datetime.now().isoformat()
            })
            
            try:
                embed = discord.Embed(
                    title="🔄 Password Reset",
                    description=f"**Username:** `{username}`\n**Password:** `{password}`",
                    color=discord.Color.blue()
                )
                await user.send(embed=embed)
            except:
                pass
            
            embed = discord.Embed(
                title="✅ Password Reset",
                description=f"New credentials sent to {user.mention}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 6. SETUP SERVER - FULL GUI
        # ═════════════════════════════════════════════════════════════════════

        class SetupServerView(View):
            def __init__(self):
                super().__init__(timeout=300)
                self.values = {}
                self.add_item(ChannelSelect(channel_types=[discord.ChannelType.text], placeholder="Select log channel", custom_id="setup_log"))
                self.add_item(ChannelSelect(channel_types=[discord.ChannelType.text], placeholder="Select transcript channel", custom_id="setup_transcript"))
                self.add_item(RoleSelect(placeholder="Select verified role", custom_id="setup_verified"))
                self.add_item(RoleSelect(placeholder="Select unverified role", custom_id="setup_unverified"))
                
                for child in self.children:
                    async def cb(interaction, c=child):
                        self.values[c.custom_id] = c.values[0].id if c.values else None
                        await interaction.response.defer()
                    child.callback = cb
            
            @discord.ui.button(label="Save Configuration", style=discord.ButtonStyle.success)
            async def save(self, i, b):
                db_execute("INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (str(i.guild.id),))
                mapping = {
                    'setup_log': 'log_channel_id',
                    'setup_transcript': 'transcript_channel_id',
                    'setup_verified': 'verified_role_id',
                    'setup_unverified': 'unverified_role_id'
                }
                for k, col in mapping.items():
                    if k in self.values and self.values[k]:
                        db_execute(f"UPDATE guild_settings SET {col}=? WHERE guild_id=?", (str(self.values[k]), str(i.guild.id)))
                
                await i.response.send_message("✅ Server configuration saved. You can run `/server_status` to review it.", ephemeral=True)

        @self.tree.command(name="setup_server", description="⚙️ Configure your server")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 60.0)
        @log_command
        async def setup_server(interaction):
            await interaction.response.send_message("Configure channels and roles, then press **Save Configuration**.", view=SetupServerView(), ephemeral=True)
        
        @self.tree.command(name="server_status", description="📊 View server configuration status")
        @app_commands.checks.cooldown(1, 5.0)
        @log_command
        async def server_status(interaction):
            settings = db_fetch_one("SELECT * FROM guild_settings WHERE guild_id=?", (str(interaction.guild.id),))
            e = discord.Embed(title=f"📊 {interaction.guild.name} • Configuration", color=discord.Color.blurple())
            
            if not settings:
                e.description = "No settings configured yet. Run `/setup_server`."
                return await interaction.response.send_message(embed=e, ephemeral=True)
            
            fields = [
                ('Verified Role', 'verified_role_id'),
                ('Unverified Role', 'unverified_role_id'),
                ('Log Channel', 'log_channel_id'),
                ('Transcript Channel', 'transcript_channel_id'),
                ('Welcome Channel', 'welcome_channel_id'),
                ('Goodbye Channel', 'goodbye_channel_id')
            ]
            
            for label, key in fields:
                v = settings[key]
                if v:
                    if 'Role' in label:
                        e.add_field(name=label, value=f"✅ <@&{v}>", inline=True)
                    else:
                        e.add_field(name=label, value=f"✅ <#{v}>", inline=True)
                else:
                    e.add_field(name=label, value='❌ Not configured', inline=True)
            
            e.add_field(name='Anti-Nuke', value='🟢 Enabled' if settings['anti_nuke'] else '⚪ Disabled')
            e.add_field(name='Raid Protection', value='🟢 Enabled' if settings['raid_protection'] else '⚪ Disabled')
            e.add_field(name='Auto-Mod', value='🟢 Enabled' if settings['automod_enabled'] else '⚪ Disabled')
            
            await interaction.response.send_message(embed=e, ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # 7. MODERATION - FULL GUI WITH MEMBER SELECT
        # ═════════════════════════════════════════════════════════════════════

        class ModReasonModal(Modal, title="Moderation Reason"):
            reason = TextInput(label="📝 Reason", placeholder="Why is this action being taken?", required=False, max_length=300)
            
            def __init__(self, action, member_id):
                super().__init__()
                self.action = action
                self.member_id = member_id
                self.title = f"{action.title()} • Reason"
            
            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                
                try:
                    if self.action in ['lock', 'unlock']:
                        await interaction.channel.set_permissions(
                            interaction.guild.default_role, 
                            send_messages=(self.action == 'unlock')
                        )
                        await interaction.followup.send(f"✅ Channel {self.action}ed.", ephemeral=True)
                        return
                    
                    member = await interaction.guild.fetch_member(int(self.member_id))
                    reason = self.reason.value or 'No reason provided'
                    
                    if self.action == 'kick':
                        await member.kick(reason=reason)
                    elif self.action == 'ban':
                        await member.ban(reason=reason)
                    elif self.action == 'mute':
                        muted = discord.utils.get(interaction.guild.roles, name="Muted")
                        if not muted:
                            muted = await interaction.guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False))
                            for ch in interaction.guild.channels:
                                try:
                                    await ch.set_permissions(muted, send_messages=False)
                                except:
                                    pass
                        await member.add_roles(muted)
                        db_execute("INSERT OR REPLACE INTO muted (user_id, guild_id, reason, unmute_at) VALUES (?,?,?,?)",
                                   (str(member.id), str(interaction.guild.id), reason, (datetime.now() + timedelta(hours=24)).isoformat()))
                    elif self.action == 'unmute':
                        muted = discord.utils.get(interaction.guild.roles, name="Muted")
                        if muted:
                            await member.remove_roles(muted)
                        db_execute("DELETE FROM muted WHERE user_id=? AND guild_id=?", 
                                   (str(member.id), str(interaction.guild.id)))
                    elif self.action == 'warn':
                        db_execute("INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?,?,?,?)",
                                   (str(member.id), str(interaction.guild.id), str(interaction.user.id), reason))
                    elif self.action == 'timeout':
                        await member.timeout(timedelta(minutes=10), reason=reason)
                    elif self.action == 'deafen':
                        if member.voice:
                            await member.edit(deafen=True)
                    
                    await interaction.followup.send(f"✅ {self.action.title()} completed for {member.mention}.", ephemeral=True)
                    
                    # Log to channel
                    settings = db_fetch_one("SELECT log_channel_id FROM guild_settings WHERE guild_id=?", (str(interaction.guild.id),))
                    if settings and settings['log_channel_id']:
                        channel = interaction.guild.get_channel(int(settings['log_channel_id']))
                        if channel:
                            embed = discord.Embed(
                                title=f"🛡️ {self.action.title()}",
                                description=f"**Member:** {member.mention}\n**Moderator:** {interaction.user.mention}\n**Reason:** {reason}",
                                color=discord.Color.orange()
                            )
                            await channel.send(embed=embed)
                            
                except Exception as e:
                    logger.error(f"Moderation error: {e}")
                    await interaction.followup.send(f"❌ Moderation failed: {e}", ephemeral=True)

        class ModActionSelect(View):
            def __init__(self, guild):
                super().__init__(timeout=120)
                self.guild = guild
                self.selected_action = None
                self.selected_member = None
                
                # Action select
                action_select = Select(placeholder="Select moderation action...", min_values=1, max_values=1)
                actions = [
                    ("ban", "🔨 Ban"),
                    ("kick", "👢 Kick"),
                    ("mute", "🔇 Mute"),
                    ("unmute", "🔊 Unmute"),
                    ("warn", "⚠️ Warn"),
                    ("timeout", "⏰ Timeout"),
                    ("deafen", "🔇 Deafen"),
                    ("lock", "🔒 Lock"),
                    ("unlock", "🔓 Unlock"),
                ]
                for value, label in actions:
                    action_select.add_option(label=label, value=value)
                action_select.callback = self.action_callback
                self.add_item(action_select)
            
            async def action_callback(self, interaction: discord.Interaction):
                self.selected_action = interaction.data['values'][0]
                
                if self.selected_action in ['lock', 'unlock']:
                    # No member needed for channel actions
                    await interaction.response.send_modal(ModReasonModal(self.selected_action, None))
                    return
                
                # Create member select
                member_select = Select(placeholder="Select member...", min_values=1, max_values=1)
                members = [m for m in self.guild.members if not m.bot][:25]
                for member in members:
                    member_select.add_option(
                        label=member.display_name[:25],
                        value=str(member.id)
                    )
                member_select.callback = self.member_callback
                
                # Replace the action select with member select
                self.clear_items()
                self.add_item(member_select)
                await interaction.response.edit_message(view=self)
            
            async def member_callback(self, interaction: discord.Interaction):
                self.selected_member = interaction.data['values'][0]
                await interaction.response.send_modal(ModReasonModal(self.selected_action, self.selected_member))

        @self.tree.command(name="mod", description="🛡️ Open moderation panel (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def mod(interaction: discord.Interaction):
            view = ModActionSelect(interaction.guild)
            embed = discord.Embed(
                title="🛡️ Moderation Panel",
                description="Select an action from the dropdown below, then select a member.",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Admin-only moderation tools")
            await interaction.response.send_message(embed=embed, view=view)

        # ─── MODERATION COMMANDS ──────────────────────────────────────────────

        @self.tree.command(name="ban", description="🔨 Ban a member")
        @app_commands.default_permissions(ban_members=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(member="Member to ban", reason="Reason")
        @log_command
        async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            await member.ban(reason=reason)
            embed = discord.Embed(
                title="🔨 Member Banned",
                description=f"{member.mention} has been banned.",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="unban", description="🔓 Unban a user")
        @app_commands.default_permissions(ban_members=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(user_id="User ID to unban")
        @log_command
        async def unban(interaction: discord.Interaction, user_id: str):
            try:
                user = await interaction.guild.fetch_user(int(user_id))
                await interaction.guild.unban(user)
                embed = discord.Embed(
                    title="🔓 User Unbanned",
                    description=f"{user.mention} has been unbanned.",
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                await interaction.response.send_message(f"❌ User not found in bans: {e}", ephemeral=True)

        @self.tree.command(name="kick", description="👢 Kick a member")
        @app_commands.default_permissions(kick_members=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(member="Member to kick", reason="Reason")
        @log_command
        async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            await member.kick(reason=reason)
            embed = discord.Embed(
                title="👢 Member Kicked",
                description=f"{member.mention} has been kicked.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="mute", description="🔇 Mute a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(member="Member to mute", reason="Reason")
        @log_command
        async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            muted = discord.utils.get(interaction.guild.roles, name="Muted")
            if not muted:
                muted = await interaction.guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False))
                for ch in interaction.guild.channels:
                    try:
                        await ch.set_permissions(muted, send_messages=False)
                    except:
                        pass
            await member.add_roles(muted)
            unmute_time = datetime.now() + timedelta(hours=24)
            db_execute("INSERT OR REPLACE INTO muted (user_id, guild_id, reason, unmute_at) VALUES (?,?,?,?)",
                       (str(member.id), str(interaction.guild.id), reason, unmute_time.isoformat()))
            embed = discord.Embed(
                title="🔇 Member Muted",
                description=f"{member.mention} muted for 24 hours.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="unmute", description="🔊 Unmute a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(member="Member to unmute")
        @log_command
        async def unmute(interaction: discord.Interaction, member: discord.Member):
            muted = discord.utils.get(interaction.guild.roles, name="Muted")
            if muted:
                await member.remove_roles(muted)
            db_execute("DELETE FROM muted WHERE user_id=? AND guild_id=?", (str(member.id), str(interaction.guild.id)))
            embed = discord.Embed(title="🔊 Member Unmuted", description=f"{member.mention} unmuted.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="warn", description="⚠️ Warn a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(member="Member to warn", reason="Reason")
        @log_command
        async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            db_execute("INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?,?,?,?)",
                       (str(member.id), str(interaction.guild.id), str(interaction.user.id), reason))
            warnings = db_fetch_all("SELECT * FROM warnings WHERE user_id=? AND guild_id=?", (str(member.id), str(interaction.guild.id)))
            embed = discord.Embed(
                title="⚠️ Member Warned",
                description=f"{member.mention} has been warned.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Warnings", value=f"{len(warnings)}/3", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="unwarn", description="✅ Remove a warning")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(warning_id="ID of warning to remove")
        @log_command
        async def unwarn(interaction: discord.Interaction, warning_id: int):
            db_delete("DELETE FROM warnings WHERE id=?", (warning_id,))
            embed = discord.Embed(title="✅ Warning Removed", description=f"Removed warning #{warning_id}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="timeout", description="⏰ Timeout a member")
        @app_commands.default_permissions(moderate_members=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(member="Member to timeout", duration="Duration (1m, 1h, 1d)", reason="Reason")
        @log_command
        async def timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
            duration_map = {'m': 60, 'h': 3600, 'd': 86400}
            unit = duration[-1].lower()
            seconds = int(duration[:-1]) * duration_map[unit]
            await member.timeout(discord.utils.utcnow() + timedelta(seconds=seconds), reason=reason)
            embed = discord.Embed(
                title="⏰ Member Timed Out",
                description=f"{member.mention} timed out for {duration}.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="deafen", description="🔇 Deafen a member")
        @app_commands.default_permissions(mute_members=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(member="Member to deafen")
        @log_command
        async def deafen(interaction: discord.Interaction, member: discord.Member):
            if member.voice:
                await member.edit(deafen=True)
                embed = discord.Embed(title="🔇 Member Deafened", description=f"{member.mention} has been deafened.", color=discord.Color.orange())
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("❌ User is not in voice channel!", ephemeral=True)

        @self.tree.command(name="lock", description="🔒 Lock channel")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(channel="Channel to lock")
        @log_command
        async def lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
            channel = channel or interaction.channel
            await channel.set_permissions(interaction.guild.default_role, send_messages=False)
            embed = discord.Embed(title="🔒 Channel Locked", description=f"{channel.mention} has been locked.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="unlock", description="🔓 Unlock channel")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(channel="Channel to unlock")
        @log_command
        async def unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
            channel = channel or interaction.channel
            await channel.set_permissions(interaction.guild.default_role, send_messages=None)
            embed = discord.Embed(title="🔓 Channel Unlocked", description=f"{channel.mention} has been unlocked.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="clear", description="🗑️ Clear messages")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.checks.cooldown(1, 10.0)
        @app_commands.describe(amount="Number of messages (max 100)")
        @log_command
        async def clear(interaction: discord.Interaction, amount: int = 10):
            if amount > 100:
                await interaction.response.send_message("❌ Max 100", ephemeral=True)
                return
            deleted = await interaction.channel.purge(limit=amount)
            embed = discord.Embed(title="🗑️ Cleared", description=f"Cleared {len(deleted)} messages", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # 8. OPFUN - DM ALL, EMBED, ANNOUNCEMENT
        # ═════════════════════════════════════════════════════════════════════

        class DmAllModal(Modal, title="📨 DM All Members"):
            message = TextInput(label="📝 Message", placeholder="Enter message to send to all members", required=True, max_length=500, style=discord.TextStyle.paragraph)

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer(ephemeral=True)
                members = [m for m in interaction.guild.members if not m.bot]
                total = len(members)
                sent = 0
                failed = 0
                
                # Send in batches of 10 with delays
                for i in range(0, total, 10):
                    batch = members[i:i+10]
                    for member in batch:
                        try:
                            await member.send(self.message.value)
                            sent += 1
                            await asyncio.sleep(0.5)
                        except:
                            failed += 1
                    await asyncio.sleep(1)  # Delay between batches
                
                await interaction.followup.send(
                    f"✅ DM Results:\n• Sent: {sent}\n• Failed: {failed}\n• Total: {total}",
                    ephemeral=True
                )

        class EmbedModal(Modal, title="📊 Create Embed"):
            title = TextInput(label="📌 Title", placeholder="Embed title", required=True, max_length=100)
            description = TextInput(label="📝 Description", placeholder="Embed description", required=True, max_length=500, style=discord.TextStyle.paragraph)
            color = TextInput(label="🎨 Color", placeholder="#5865F2", required=False, max_length=7)

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    color = int(self.color.value.replace('#', ''), 16) if self.color.value else 0x5865F2
                except:
                    color = 0x5865F2
                
                embed = discord.Embed(
                    title=self.title.value,
                    description=self.description.value,
                    color=color
                )
                embed.set_footer(text=f"Sent by {interaction.user.display_name}")
                await interaction.channel.send(embed=embed)
                await interaction.response.send_message("✅ Embed sent!", ephemeral=True)

        class AnnouncementModal(Modal, title="📢 Send Announcement"):
            title = TextInput(label="📌 Title", placeholder="Announcement title", required=True, max_length=100)
            message = TextInput(label="📝 Message", placeholder="Announcement message", required=True, max_length=500, style=discord.TextStyle.paragraph)
            ping_role = TextInput(label="📢 Ping Role ID", placeholder="Role ID to ping (optional)", required=False, max_length=30)

            async def on_submit(self, interaction: discord.Interaction):
                embed = discord.Embed(
                    title=f"📢 {self.title.value}",
                    description=self.message.value,
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"Announced by {interaction.user.display_name}")

                ping = ""
                if self.ping_role.value:
                    try:
                        role = interaction.guild.get_role(int(self.ping_role.value))
                        if role:
                            ping = f"{role.mention} "
                    except:
                        pass

                await interaction.channel.send(ping, embed=embed)
                await interaction.response.send_message("✅ Announcement sent!", ephemeral=True)

        class DmUserModal(Modal, title="📨 DM User"):
            user_id = TextInput(label="👤 User ID", placeholder="Enter user ID", required=True)
            message = TextInput(label="📝 Message", placeholder="Enter message", required=True, max_length=500)

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    user = await interaction.guild.fetch_member(int(self.user_id.value))
                    if user:
                        await user.send(self.message.value)
                        await interaction.response.send_message(f"✅ DM sent to {user.mention}!", ephemeral=True)
                    else:
                        await interaction.response.send_message("❌ User not found!", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"❌ Could not send DM: {e}", ephemeral=True)

        class OPFunView(View):
            def __init__(self):
                super().__init__(timeout=180)
            
            @discord.ui.button(label="DM All", emoji="📨", style=discord.ButtonStyle.primary)
            async def all_dm(self, i, b):
                if not i.user.guild_permissions.administrator:
                    return await i.response.send_message('Admins only.', ephemeral=True)
                await i.response.send_modal(DmAllModal())
            
            @discord.ui.button(label="Create Embed", emoji="📊", style=discord.ButtonStyle.success)
            async def emb(self, i, b):
                await i.response.send_modal(EmbedModal())
            
            @discord.ui.button(label="Announcement", emoji="📢", style=discord.ButtonStyle.danger)
            async def ann(self, i, b):
                await i.response.send_modal(AnnouncementModal())
            
            @discord.ui.button(label="DM User", emoji="👤", style=discord.ButtonStyle.secondary)
            async def dm(self, i, b):
                await i.response.send_modal(DmUserModal())

        @self.tree.command(name="opfun", description="🎯 Open OP Fun Panel")
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def opfun(interaction: discord.Interaction):
            embed = discord.Embed(
                title="🎯 OP Fun Panel",
                description="Select an option from the buttons below.",
                color=discord.Color.blue()
            )
            embed.add_field(name="📋 Available Actions", value="• DM All Members\n• Create Embed\n• Send Announcement\n• DM Individual User", inline=False)
            view = OPFunView()
            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="dm_all", description="📨 DM all members")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 60.0)
        @log_command
        async def dm_all(interaction: discord.Interaction):
            modal = DmAllModal()
            await interaction.response.send_modal(modal)

        @self.tree.command(name="send_embed", description="📊 Send an embed")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def send_embed(interaction: discord.Interaction):
            modal = EmbedModal()
            await interaction.response.send_modal(modal)

        @self.tree.command(name="announce", description="📢 Send an announcement")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def announce(interaction: discord.Interaction):
            modal = AnnouncementModal()
            await interaction.response.send_modal(modal)

        @self.tree.command(name="dm_user", description="📨 DM a specific user")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def dm_user(interaction: discord.Interaction):
            modal = DmUserModal()
            await interaction.response.send_modal(modal)

        # ═════════════════════════════════════════════════════════════════════
        # 9. AUTO-MOD - BAD WORDS + SPAM (FIXED)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="add_badword", description="🚫 Add a bad word (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(word="Word to add")
        @log_command
        async def add_badword(interaction: discord.Interaction, word: str):
            db_execute("INSERT OR REPLACE INTO bad_words (word, guild_id) VALUES (?,?)",
                       (word.lower(), str(interaction.guild.id)))
            embed = discord.Embed(title="✅ Bad Word Added", description=f"Added `{word}`", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="remove_badword", description="🚫 Remove a bad word (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(word="Word to remove")
        @log_command
        async def remove_badword(interaction: discord.Interaction, word: str):
            db_delete("DELETE FROM bad_words WHERE word=? AND guild_id=?", (word.lower(), str(interaction.guild.id)))
            embed = discord.Embed(title="✅ Bad Word Removed", description=f"Removed `{word}`", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="list_badwords", description="🚫 List all bad words (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 5.0)
        @log_command
        async def list_badwords(interaction: discord.Interaction):
            words = db_fetch_all("SELECT word FROM bad_words WHERE guild_id=?", (str(interaction.guild.id),))
            if not words:
                await interaction.response.send_message("✅ No bad words configured!", ephemeral=True)
                return
            word_list = "\n".join([f"• {w['word']}" for w in words])
            embed = discord.Embed(title="🚫 Bad Words", description=word_list, color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)

        # ─── EVENT HANDLERS WITH SPAM DETECTION ─────────────────────────────

        async def on_message(self, message):
            if message.author.bot:
                return
            
            if message.guild:
                settings = db_fetch_one("SELECT automod_enabled, spam_threshold, bad_words_enabled FROM guild_settings WHERE guild_id=?", 
                                        (str(message.guild.id),))
                
                if settings and settings['automod_enabled']:
                    # Spam detection
                    threshold = settings['spam_threshold'] or 5
                    spam_data = db_fetch_one(
                        "SELECT message_count, last_message_at FROM spam_tracking WHERE user_id=? AND guild_id=?",
                        (str(message.author.id), str(message.guild.id))
                    )
                    
                    now = datetime.now()
                    if spam_data:
                        try:
                            last_time = datetime.fromisoformat(spam_data['last_message_at'])
                        except:
                            last_time = now - timedelta(minutes=5)
                        
                        if (now - last_time).seconds < 5:
                            count = spam_data['message_count'] + 1
                            if count > threshold:
                                await message.delete()
                                await message.channel.send(f"⚠️ {message.author.mention} slow down! Please wait before sending more messages.")
                                try:
                                    await message.author.timeout(timedelta(minutes=5), reason="Spamming")
                                except:
                                    pass
                                return
                            db_execute(
                                "UPDATE spam_tracking SET message_count=?, last_message_at=? WHERE user_id=? AND guild_id=?",
                                (count, now.isoformat(), str(message.author.id), str(message.guild.id))
                            )
                        else:
                            db_execute(
                                "UPDATE spam_tracking SET message_count=1, last_message_at=? WHERE user_id=? AND guild_id=?",
                                (now.isoformat(), str(message.author.id), str(message.guild.id))
                            )
                    else:
                        db_execute(
                            "INSERT INTO spam_tracking (user_id, guild_id, message_count, last_message_at) VALUES (?,?,?,?)",
                            (str(message.author.id), str(message.guild.id), 1, now.isoformat())
                        )
                    
                    # Bad words filter
                    if settings.get('bad_words_enabled', True):
                        bad_words = db_fetch_all("SELECT word FROM bad_words WHERE guild_id=?", (str(message.guild.id),))
                        content = message.content.lower()
                        for row in bad_words:
                            if row['word'] in content:
                                await message.delete()
                                await message.channel.send(f"❌ {message.author.mention}, that word is not allowed!")
                                db_execute("INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?,?,?,?)",
                                           (str(message.author.id), str(message.guild.id), str(message.guild.me.id), f"Used banned word: {row['word']}"))
                                return
            
            await self.process_commands(message)

        # ═════════════════════════════════════════════════════════════════════
        # 10. TEMPLATE COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="savetemplate", description="💾 Save server template (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 30.0)
        @app_commands.describe(name="Template name")
        @log_command
        async def savetemplate(interaction: discord.Interaction, name: str):
            guild = interaction.guild
            template = {'name': guild.name, 'roles': [], 'channels': [], 'permissions': []}

            for role in guild.roles:
                if role.name != '@everyone':
                    template['roles'].append({
                        'name': role.name, 'color': role.color.value,
                        'permissions': role.permissions.value,
                        'hoist': role.hoist, 'mentionable': role.mentionable,
                        'position': role.position
                    })

            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.VoiceChannel):
                    channel_data = {
                        'name': channel.name,
                        'type': str(channel.type).split('.')[-1],
                        'position': channel.position,
                        'category': channel.category.name if channel.category else None
                    }
                    if isinstance(channel, discord.TextChannel):
                        channel_data['topic'] = channel.topic
                        channel_data['nsfw'] = channel.nsfw
                        channel_data['slowmode'] = channel.slowmode_delay
                    if isinstance(channel, discord.VoiceChannel):
                        channel_data['bitrate'] = channel.bitrate
                        channel_data['user_limit'] = channel.user_limit
                    template['channels'].append(channel_data)

            template_id = secrets.token_urlsafe(8)
            db_execute("INSERT OR REPLACE INTO server_templates (template_id, guild_id, name, template_json) VALUES (?,?,?,?)",
                       (template_id, str(guild.id), name, json.dumps(template)))

            embed = discord.Embed(
                title="✅ Template Saved",
                description=f"Template: {name}\nID: {template_id}\nRoles: {len(template['roles'])}\nChannels: {len(template['channels'])}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="applytemplate", description="📥 Apply saved template (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 60.0)
        @app_commands.describe(template_id="Template ID")
        @log_command
        async def applytemplate(interaction: discord.Interaction, template_id: str):
            template_data = db_fetch_one("SELECT * FROM server_templates WHERE template_id=?", (template_id,))
            if not template_data:
                await interaction.response.send_message("❌ Template not found!", ephemeral=True)
                return

            guild = interaction.guild
            template = json.loads(template_data['template_json'])

            for role in template['roles']:
                await guild.create_role(
                    name=role['name'],
                    color=discord.Color(role['color']),
                    permissions=discord.Permissions(role['permissions']),
                    hoist=role['hoist'],
                    mentionable=role['mentionable']
                )

            for channel in template['channels']:
                if channel['type'] == 'text':
                    await guild.create_text_channel(
                        channel['name'],
                        topic=channel.get('topic'),
                        nsfw=channel.get('nsfw', False),
                        slowmode_delay=channel.get('slowmode', 0)
                    )
                elif channel['type'] == 'voice':
                    await guild.create_voice_channel(
                        channel['name'],
                        bitrate=channel.get('bitrate', 64000),
                        user_limit=channel.get('user_limit', 0)
                    )

            embed = discord.Embed(
                title="✅ Template Applied",
                description=f"Applied template to **{guild.name}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Roles", value=len(template['roles']), inline=True)
            embed.add_field(name="Channels", value=len(template['channels']), inline=True)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 11. UTILITY COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="serverinfo", description="📊 Server information")
        @app_commands.checks.cooldown(1, 5.0)
        @log_command
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
            embed.add_field(name="💎 Boost Level", value=guild.premium_tier, inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="userinfo", description="👤 User information")
        @app_commands.checks.cooldown(1, 5.0)
        @app_commands.describe(member="User to get info about")
        @log_command
        async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            embed = discord.Embed(
                title=f"👤 {target.display_name}",
                color=target.color
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Username", value=target.name, inline=True)
            embed.add_field(name="ID", value=target.id, inline=True)
            embed.add_field(name="Created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
            embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "Unknown", inline=True)
            embed.add_field(name="Is Bot", value="✅ Yes" if target.bot else "❌ No", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="ping", description="🏓 Check latency")
        @app_commands.checks.cooldown(1, 3.0)
        @log_command
        async def ping(interaction: discord.Interaction):
            latency = round(interaction.client.latency * 1000)
            embed = discord.Embed(
                title="🏓 Pong!",
                description=f"Latency: {latency}ms",
                color=discord.Color.green()
            )
            embed.add_field(name="Uptime", value=str(datetime.now() - bot_instance.start_time).split('.')[0], inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="list_all", description="📋 Show all commands")
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def list_all(interaction: discord.Interaction):
            embed = discord.Embed(
                title="📋 All Commands",
                description="Complete list of Anion bot commands",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=interaction.guild.me.display_avatar.url)
            embed.add_field(name="🔐 Verification", value="/verify /verifystatus /setverifiedrole /setunverifiedrole /setlogchannel /setupverify", inline=False)
            embed.add_field(name="🎁 Giveaways", value="/giveaway_host /giveaway_end /giveaway_reroll /setgiveawayrole", inline=False)
            embed.add_field(name="🎫 Tickets", value="/setup_ticket /ticket /setticketsupportrole", inline=False)
            embed.add_field(name="👋 Welcome", value="/setup_welcome /setup_goodbye /setwelcomechannel /setgoodbyechannel", inline=False)
            embed.add_field(name="⚙️ Setup", value="/setup_server /server_status", inline=False)
            embed.add_field(name="🛡️ Moderation", value="/mod /ban /unban /kick /mute /unmute /warn /unwarn /timeout /deafen /lock /unlock /clear", inline=False)
            embed.add_field(name="🎯 OP Fun", value="/opfun /dm_all /send_embed /announce /dm_user", inline=False)
            embed.add_field(name="🔑 Passwords", value="/update_role_level /show_passwords /reset_password", inline=False)
            embed.add_field(name="🚫 Auto-Mod", value="/add_badword /remove_badword /list_badwords", inline=False)
            embed.add_field(name="📁 Templates", value="/savetemplate /applytemplate", inline=False)
            embed.add_field(name="🔧 Utility", value="/serverinfo /userinfo /ping", inline=False)
            await interaction.response.send_message(embed=embed)

    async def on_ready(self):
        logger.info("╔══════════════════════════════════════════════════════════════════╗")
        logger.info("║              ✅✅✅ BOT IS ONLINE! ✅✅✅                           ║")
        logger.info("╚══════════════════════════════════════════════════════════════════╝")
        logger.info(f"📡 Name: {self.user.name}")
        logger.info(f"🆔 ID: {self.user.id}")
        logger.info(f"🏰 Servers: {len(self.guilds)}")
        for guild in self.guilds:
            logger.info(f"   - {guild.name} ({guild.id})")
        logger.info("═" * 70)
        logger.info("📋 ALL FEATURES LOADED!")
        logger.info("═" * 70)

    async def on_member_join(self, member):
        settings = db_fetch_one("SELECT welcome_channel_id, welcome_message, welcome_image FROM guild_settings WHERE guild_id=?", 
                                (str(member.guild.id),))
        if settings and settings['welcome_channel_id']:
            channel = member.guild.get_channel(int(settings['welcome_channel_id']))
            if channel:
                msg = settings['welcome_message'] or "👋 Welcome {mention} to **{server}**!"
                msg = msg.replace("{mention}", member.mention).replace("{user}", member.display_name).replace("{server}", member.guild.name)

                embed = discord.Embed(
                    title="👋 Welcome to the Server!",
                    description=msg,
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="📊 Server Stats", value=f"{member.guild.member_count} members", inline=True)
                embed.add_field(name="📅 Joined", value=datetime.now().strftime("%Y-%m-%d"), inline=True)
                if settings['welcome_image']:
                    embed.set_image(url=settings['welcome_image'])
                embed.set_footer(text="We're glad to have you!")

                await channel.send(embed=embed)

        # Generate password
        await generate_user_password(member, str(member.guild.id))

        # Assign unverified role
        settings2 = db_fetch_one("SELECT unverified_role_id FROM guild_settings WHERE guild_id=?", (str(member.guild.id),))
        if settings2 and settings2['unverified_role_id']:
            role = member.guild.get_role(int(settings2['unverified_role_id']))
            if role:
                await member.add_roles(role)

    async def on_member_remove(self, member):
        settings = db_fetch_one("SELECT goodbye_channel_id, goodbye_message, goodbye_image FROM guild_settings WHERE guild_id=?", 
                                (str(member.guild.id),))
        if settings and settings['goodbye_channel_id']:
            channel = member.guild.get_channel(int(settings['goodbye_channel_id']))
            if channel:
                msg = settings['goodbye_message'] or "👋 {user} has left the server."
                msg = msg.replace("{user}", member.display_name)

                embed = discord.Embed(
                    title="👋 Goodbye!",
                    description=msg,
                    color=discord.Color.orange()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="📊 Server Stats", value=f"{member.guild.member_count} members remaining", inline=True)
                if settings['goodbye_image']:
                    embed.set_image(url=settings['goodbye_image'])
                await channel.send(embed=embed)

    async def on_error(self, event, *args, **kwargs):
        logger.error(f"Error in event {event}:")
        logger.error(traceback.format_exc())

bot_instance = None

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

async def main():
    global bot_instance
    logger.info("🚀 Starting Anion Bot v14.1...")
    logger.info("═" * 70)

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info(f"🌐 Flask started on port {PORT}")

    bot_instance = AnionBot()
    await bot_instance.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
