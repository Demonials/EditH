#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION VERIFICATION SYSTEM v4.0
                    FIREBASE + DISCORD OAUTH
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import secrets
import requests
import threading
import asyncio
import logging
from datetime import datetime, timedelta
from flask import Flask, request, redirect, render_template_string, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

# ─── FIREBASE ──────────────────────────────────────────────────────────────────

import firebase_admin
from firebase_admin import credentials, db as firebase_db

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# ENSURE DATA DIRECTORY EXISTS
# ═════════════════════════════════════════════════════════════════════════════

DATA_DIR = '/data'
os.makedirs(DATA_DIR, exist_ok=True)

# ═════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═════════════════════════════════════════════════════════════════════════════

LOG_FILE = os.path.join(DATA_DIR, 'bot.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)
logger = logging.getLogger('AnionBot')

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════

TOKEN = os.getenv('DISCORD_TOKEN')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://edith.up.railway.app/callback')
DB_PATH = os.getenv('DB_PATH', DATA_DIR)
FLASK_SECRET = os.getenv('FLASK_SECRET', secrets.token_urlsafe(32))
PORT = int(os.getenv('PORT', 5000))

# Firebase
FIREBASE_URL = os.getenv('FIREBASE_URL')
FIREBASE_KEY = os.getenv('FIREBASE_KEY')
FIREBASE_EMAIL = os.getenv('FIREBASE_EMAIL')

if not TOKEN or not CLIENT_ID or not CLIENT_SECRET:
    logger.error("❌ Missing required environment variables!")
    sys.exit(1)

if not FIREBASE_URL or not FIREBASE_KEY or not FIREBASE_EMAIL:
    logger.warning("⚠️ Firebase not configured! Data will be stored locally only.")
    FIREBASE_ENABLED = False
else:
    FIREBASE_ENABLED = True
    try:
        cred_dict = {
            "type": "service_account",
            "project_id": FIREBASE_URL.split('/')[2].split('.')[0],
            "private_key_id": "dummy",
            "private_key": FIREBASE_KEY,
            "client_email": FIREBASE_EMAIL,
            "client_id": "dummy",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{FIREBASE_EMAIL}"
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
        ref = firebase_db.reference('/')
        ref.update({'status': 'online', 'timestamp': datetime.now().isoformat()})
        logger.info("✅ Firebase Connected!")
    except Exception as e:
        logger.error(f"❌ Firebase connection failed: {e}")
        FIREBASE_ENABLED = False

DB_FILE = os.path.join(DB_PATH, 'verification.db')
logger.info(f"✅ Token: {TOKEN[:15]}...")
logger.info(f"✅ Firebase: {'Enabled' if FIREBASE_ENABLED else 'Disabled (local only)'}")
logger.info(f"✅ Database: {DB_FILE}")

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE (Local SQLite)
# ═════════════════════════════════════════════════════════════════════════════

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        verified_role_id TEXT,
        unverified_role_id TEXT,
        log_channel_id TEXT,
        verification_channel_id TEXT
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS verified_users (
        user_id TEXT,
        guild_id TEXT,
        username TEXT,
        email TEXT,
        access_token TEXT,
        refresh_token TEXT,
        verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, guild_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        user_id TEXT,
        guild_id TEXT,
        access_token TEXT,
        refresh_token TEXT,
        expires_at TIMESTAMP,
        PRIMARY KEY (user_id, guild_id)
    )
""")

conn.commit()
logger.info("✅ Local Database ready")

def db_execute(query, params=()):
    try:
        c.execute(query, params)
        conn.commit()
        return c
    except Exception as e:
        logger.error(f"❌ DB Error: {e}")
        return None

def db_fetch_one(query, params=()):
    try:
        c.execute(query, params)
        return c.fetchone()
    except Exception as e:
        logger.error(f"❌ DB Error: {e}")
        return None

def db_fetch_all(query, params=()):
    try:
        c.execute(query, params)
        return c.fetchall()
    except Exception as e:
        logger.error(f"❌ DB Error: {e}")
        return []

def db_delete(query, params=()):
    try:
        c.execute(query, params)
        conn.commit()
        return c
    except Exception as e:
        logger.error(f"❌ DB Error: {e}")
        return None

# ═════════════════════════════════════════════════════════════════════════════
# FIREBASE FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def firebase_save_user(user_id, guild_id, data):
    """Save user data to Firebase"""
    if not FIREBASE_ENABLED:
        return False
    try:
        ref = firebase_db.reference(f'/users/{user_id}/guilds/{guild_id}')
        ref.set(data)
        return True
    except Exception as e:
        logger.error(f"❌ Firebase save error: {e}")
        return False

def firebase_get_user(user_id, guild_id=None):
    """Get user data from Firebase"""
    if not FIREBASE_ENABLED:
        return None
    try:
        if guild_id:
            ref = firebase_db.reference(f'/users/{user_id}/guilds/{guild_id}')
        else:
            ref = firebase_db.reference(f'/users/{user_id}')
        return ref.get()
    except Exception as e:
        logger.error(f"❌ Firebase get error: {e}")
        return None

def firebase_get_all_users():
    """Get all users from Firebase"""
    if not FIREBASE_ENABLED:
        return {}
    try:
        ref = firebase_db.reference('/users')
        data = ref.get()
        return data if data else {}
    except Exception as e:
        logger.error(f"❌ Firebase get all error: {e}")
        return {}

def firebase_delete_user(user_id, guild_id):
    """Delete user from Firebase"""
    if not FIREBASE_ENABLED:
        return False
    try:
        ref = firebase_db.reference(f'/users/{user_id}/guilds/{guild_id}')
        ref.delete()
        return True
    except Exception as e:
        logger.error(f"❌ Firebase delete error: {e}")
        return False

def firebase_log(action, data):
    """Log to Firebase"""
    if not FIREBASE_ENABLED:
        return False
    try:
        ref = firebase_db.reference(f'/logs/{datetime.now().strftime("%Y-%m-%d")}')
        ref.push({
            'action': action,
            'data': data,
            'timestamp': datetime.now().isoformat()
        })
        return True
    except Exception as e:
        logger.error(f"❌ Firebase log error: {e}")
        return False

# ═════════════════════════════════════════════════════════════════════════════
# FLASK APP - OAUTH + SUCCESS PAGE
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET
CORS(flask_app)

@flask_app.route('/')
def index():
    return redirect('/verify')

@flask_app.route('/verify')
def verify_page():
    guild_id = request.args.get('guild_id')
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔐 Secure Verification</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Inter', sans-serif;
                background: #0a0a0f;
                color: #ffffff;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                overflow: hidden;
                position: relative;
            }
            .bg-gradient {
                position: fixed;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(ellipse at 30% 50%, rgba(88, 101, 242, 0.08) 0%, transparent 60%),
                            radial-gradient(ellipse at 70% 50%, rgba(118, 75, 162, 0.06) 0%, transparent 60%);
                animation: bgPulse 8s ease-in-out infinite alternate;
                z-index: 0;
            }
            @keyframes bgPulse {
                0% { transform: scale(1) rotate(0deg); }
                100% { transform: scale(1.1) rotate(3deg); }
            }
            .container {
                position: relative;
                z-index: 1;
                max-width: 480px;
                width: 100%;
                padding: 40px 30px;
                background: rgba(20, 20, 30, 0.85);
                backdrop-filter: blur(24px);
                border-radius: 24px;
                border: 1px solid rgba(255, 255, 255, 0.06);
                box-shadow: 0 40px 80px rgba(0, 0, 0, 0.6);
                text-align: center;
                animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                opacity: 0;
                transform: translateY(30px);
            }
            @keyframes slideUp {
                to { opacity: 1; transform: translateY(0); }
            }
            .shield-icon { font-size: 56px; margin-bottom: 16px; animation: float 3s ease-in-out infinite; }
            @keyframes float { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-10px); } }
            h1 {
                font-size: 28px;
                font-weight: 800;
                background: linear-gradient(135deg, #ffffff 30%, #8b8cf7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 8px;
            }
            .subtitle { font-size: 14px; color: rgba(255, 255, 255, 0.5); margin-bottom: 28px; }
            .security-badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: rgba(88, 101, 242, 0.12);
                border: 1px solid rgba(88, 101, 242, 0.2);
                padding: 8px 16px;
                border-radius: 100px;
                font-size: 11px;
                font-weight: 600;
                color: #8b8cf7;
                margin-bottom: 24px;
            }
            .security-badge .dot {
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: #4CAF50;
                animation: pulseDot 2s infinite;
            }
            @keyframes pulseDot { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            .features {
                display: flex;
                flex-direction: column;
                gap: 10px;
                margin-bottom: 28px;
                text-align: left;
            }
            .feature-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 14px;
                background: rgba(255, 255, 255, 0.03);
                border-radius: 12px;
                border: 1px solid rgba(255, 255, 255, 0.04);
                font-size: 13px;
                color: rgba(255, 255, 255, 0.7);
                transition: all 0.3s ease;
            }
            .feature-item:hover {
                background: rgba(255, 255, 255, 0.06);
                border-color: rgba(88, 101, 242, 0.15);
            }
            .feature-item .icon { font-size: 18px; flex-shrink: 0; width: 28px; text-align: center; }
            .btn-verify {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 12px;
                width: 100%;
                padding: 16px 32px;
                background: linear-gradient(135deg, #5865F2, #4752c4);
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
                text-decoration: none;
                transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                font-family: 'Inter', sans-serif;
            }
            .btn-verify:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 40px rgba(88, 101, 242, 0.35);
            }
            .btn-verify .arrow { font-size: 20px; transition: transform 0.3s ease; }
            .btn-verify:hover .arrow { transform: translateX(4px); }
            .footer-text { margin-top: 20px; font-size: 11px; color: rgba(255, 255, 255, 0.2); }
            .particle {
                position: fixed;
                border-radius: 50%;
                pointer-events: none;
                z-index: 0;
                background: rgba(88, 101, 242, 0.15);
                animation: floatParticle 20s infinite linear;
            }
            @keyframes floatParticle {
                0% { transform: translate(0, 0) scale(1); opacity: 0; }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { transform: translate(100px, -100px) scale(0); opacity: 0; }
            }
            @media (max-width: 480px) {
                .container { padding: 30px 20px; margin: 16px; }
                h1 { font-size: 24px; }
                .btn-verify { font-size: 15px; padding: 14px 24px; }
            }
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
            <h1>Secure Verification</h1>
            <p class="subtitle">Advanced Identity Verification Protocol</p>
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
    oauth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email%20guilds"
        f"&state={guild_id}"
    )
    return redirect(oauth_url)

@flask_app.route('/callback')
def callback():
    code = request.args.get('code')
    guild_id = request.args.get('state')
    
    logger.info(f"📥 Callback received - Code: {code[:20] if code else 'None'}..., Guild: {guild_id}")
    
    if not code:
        return "❌ No code provided", 400
    if not guild_id:
        return "❌ No guild_id provided", 400
    
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
        logger.info("✅ Token exchange successful")
    except Exception as e:
        logger.error(f"❌ Token exchange failed: {e}")
        return f"❌ Token exchange failed: {e}", 400
    
    if 'access_token' not in token_data:
        logger.error(f"❌ No access token: {token_data}")
        return f"❌ No access token: {token_data}", 400
    
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 604800)
    expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        user_resp = requests.get('https://discord.com/api/users/@me', headers=headers, timeout=10)
        user_data = user_resp.json()
        logger.info(f"👤 User: {user_data.get('username')}")
    except Exception as e:
        logger.error(f"❌ Failed to get user data: {e}")
        return f"❌ Failed to get user data: {e}", 400
    
    try:
        guilds_resp = requests.get('https://discord.com/api/users/@me/guilds', headers=headers, timeout=10)
        guilds_data = guilds_resp.json()
    except Exception as e:
        logger.error(f"❌ Failed to get guilds: {e}")
        guilds_data = []
    
    # ─── SAVE TO LOCAL DB ──────────────────────────────────────────────────
    
    db_execute("""
        INSERT OR REPLACE INTO verified_users 
        (user_id, guild_id, username, email, access_token, refresh_token)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_data.get('id'),
        guild_id,
        user_data.get('username'),
        user_data.get('email', ''),
        access_token,
        refresh_token
    ))
    
    db_execute("""
        INSERT OR REPLACE INTO oauth_tokens
        (user_id, guild_id, access_token, refresh_token, expires_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_data.get('id'),
        guild_id,
        access_token,
        refresh_token,
        expires_at
    ))
    
    # ─── SAVE TO FIREBASE ──────────────────────────────────────────────────
    
    firebase_data = {
        'user_id': user_data.get('id'),
        'username': user_data.get('username'),
        'discriminator': user_data.get('discriminator', '0'),
        'email': user_data.get('email', ''),
        'avatar': user_data.get('avatar'),
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': expires_at,
        'guilds': guilds_data,
        'verified_at': datetime.now().isoformat(),
        'guild_id': guild_id
    }
    
    firebase_save_user(user_data.get('id'), guild_id, firebase_data)
    firebase_log('verification', {
        'user_id': user_data.get('id'),
        'username': user_data.get('username'),
        'guild_id': guild_id,
        'email': user_data.get('email', '')
    })
    
    logger.info("=" * 70)
    logger.info("✅ USER VERIFIED & SAVED TO FIREBASE!")
    logger.info("=" * 70)
    logger.info(f"  👤 User: {user_data.get('username')}")
    logger.info(f"  🆔 ID: {user_data.get('id')}")
    logger.info(f"  📧 Email: {user_data.get('email', 'N/A')}")
    logger.info(f"  🏰 Guild: {guild_id}")
    logger.info("=" * 70)
    
    # ─── ASSIGN ROLE ──────────────────────────────────────────────────────
    
    if bot_instance:
        asyncio.run_coroutine_threadsafe(
            assign_verified_role(user_data.get('id'), guild_id, user_data.get('username')),
            bot_instance.loop
        )
    
    guild_name = guild_id
    if bot_instance:
        guild = bot_instance.get_guild(int(guild_id))
        if guild:
            guild_name = guild.name
    
    # ─── SUCCESS PAGE ──────────────────────────────────────────────────────
    
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>✅ Verification Complete</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap');
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Inter', sans-serif;
                background: #0a0a0f;
                color: #ffffff;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                overflow: hidden;
            }
            .bg-gradient {
                position: fixed;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(ellipse at 70% 30%, rgba(76, 175, 80, 0.06) 0%, transparent 60%),
                            radial-gradient(ellipse at 30% 70%, rgba(88, 101, 242, 0.04) 0%, transparent 60%);
                animation: bgPulse 10s ease-in-out infinite alternate;
                z-index: 0;
            }
            @keyframes bgPulse { 0% { transform: scale(1) rotate(0deg); } 100% { transform: scale(1.05) rotate(-2deg); } }
            .container {
                position: relative;
                z-index: 1;
                max-width: 520px;
                width: 100%;
                padding: 50px 40px;
                background: rgba(20, 20, 30, 0.85);
                backdrop-filter: blur(24px);
                border-radius: 28px;
                border: 1px solid rgba(76, 175, 80, 0.15);
                box-shadow: 0 40px 80px rgba(0, 0, 0, 0.6), 0 0 60px rgba(76, 175, 80, 0.05);
                text-align: center;
                animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                opacity: 0;
                transform: translateY(30px);
            }
            @keyframes slideUp { to { opacity: 1; transform: translateY(0); } }
            .success-icon { font-size: 72px; margin-bottom: 12px; animation: successPulse 2s ease-in-out infinite; }
            @keyframes successPulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.05); } }
            .glow-ring {
                display: inline-block;
                padding: 4px;
                border-radius: 50%;
                background: linear-gradient(135deg, #4CAF50, #66BB6A);
                box-shadow: 0 0 60px rgba(76, 175, 80, 0.2);
                margin-bottom: 16px;
            }
            h1 {
                font-size: 32px;
                font-weight: 900;
                background: linear-gradient(135deg, #ffffff 30%, #a5d6a7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 8px;
            }
            .subtitle { font-size: 14px; color: rgba(255, 255, 255, 0.4); margin-bottom: 28px; }
            .verified-badge {
                display: inline-flex;
                align-items: center;
                gap: 10px;
                background: rgba(76, 175, 80, 0.12);
                border: 1px solid rgba(76, 175, 80, 0.2);
                padding: 10px 20px;
                border-radius: 100px;
                font-size: 13px;
                font-weight: 600;
                color: #81C784;
                margin-bottom: 28px;
            }
            .verified-badge .check { font-size: 18px; }
            .info-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin-bottom: 28px;
                text-align: left;
            }
            .info-card {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 14px;
                padding: 16px 18px;
                transition: all 0.3s ease;
            }
            .info-card:hover {
                background: rgba(255, 255, 255, 0.06);
                border-color: rgba(255, 255, 255, 0.08);
            }
            .info-card .label {
                font-size: 10px;
                font-weight: 600;
                color: rgba(255, 255, 255, 0.3);
                text-transform: uppercase;
                letter-spacing: 0.8px;
                margin-bottom: 4px;
            }
            .info-card .value {
                font-size: 14px;
                font-weight: 600;
                color: #ffffff;
                word-break: break-all;
            }
            .info-card .value.username { color: #8b8cf7; }
            .info-card .value.guild { color: #81C784; }
            .btn-done {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                width: 100%;
                padding: 16px 32px;
                background: linear-gradient(135deg, #4CAF50, #388E3C);
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
                text-decoration: none;
                font-family: 'Inter', sans-serif;
                transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            }
            .btn-done:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 40px rgba(76, 175, 80, 0.35);
            }
            .footer-text { margin-top: 16px; font-size: 11px; color: rgba(255, 255, 255, 0.15); }
            .particle {
                position: fixed;
                border-radius: 50%;
                pointer-events: none;
                z-index: 0;
                background: rgba(76, 175, 80, 0.1);
                animation: floatParticle 25s infinite linear;
            }
            @keyframes floatParticle {
                0% { transform: translate(0, 0) scale(1); opacity: 0; }
                10% { opacity: 1; }
                90% { opacity: 1; }
                100% { transform: translate(-80px, -120px) scale(0); opacity: 0; }
            }
            @media (max-width: 480px) {
                .container { padding: 30px 20px; margin: 16px; }
                h1 { font-size: 26px; }
                .info-grid { grid-template-columns: 1fr; }
                .btn-done { font-size: 15px; padding: 14px 20px; }
            }
        </style>
    </head>
    <body>
        <div class="bg-gradient"></div>
        <div class="particle" style="width:4px;height:4px;top:15%;left:8%;animation-duration:22s;"></div>
        <div class="particle" style="width:6px;height:6px;top:25%;right:12%;animation-duration:18s;animation-delay:4s;"></div>
        <div class="particle" style="width:3px;height:3px;bottom:30%;left:15%;animation-duration:28s;animation-delay:6s;"></div>
        <div class="container">
            <div class="glow-ring"><div class="success-icon">✅</div></div>
            <h1>Verification Complete</h1>
            <p class="subtitle">Identity successfully confirmed</p>
            <div class="verified-badge"><span class="check">✦</span><span>Verified • {{ username }}#{{ discriminator }}</span></div>
            <div class="info-grid">
                <div class="info-card"><div class="label">👤 User</div><div class="value username">{{ username }}</div></div>
                <div class="info-card"><div class="label">🆔 User ID</div><div class="value">{{ user_id }}</div></div>
                <div class="info-card"><div class="label">📧 Email</
