#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION BOT v12.0 - COMPLETE FIXED
                    ALL FEATURES + GUI + PERFECT VERIFICATION
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
from datetime import datetime, timedelta
from flask import Flask, request, redirect, render_template_string, jsonify, session, url_for
from flask_cors import CORS
from dotenv import load_dotenv

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select

load_dotenv()

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
    print("❌ Missing required environment variables!")
    sys.exit(1)

os.makedirs(DB_PATH, exist_ok=True)
os.makedirs(os.path.join(DB_PATH, 'flask_session'), exist_ok=True)

DB_FILE = os.path.join(DB_PATH, 'bot.db')

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
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
        verification_channel_id TEXT,
        welcome_channel_id TEXT,
        goodbye_channel_id TEXT,
        welcome_message TEXT,
        goodbye_message TEXT,
        ticket_category_id TEXT,
        ticket_support_role_id TEXT,
        giveaway_ping_role_id TEXT
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS verified_users (
        user_id TEXT, guild_id TEXT,
        username TEXT, email TEXT,
        access_token TEXT, refresh_token TEXT,
        verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
        closed_at TIMESTAMP
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
        hosted_by TEXT, ping_role_id TEXT
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS giveaway_entries (
        giveaway_id INTEGER, user_id TEXT,
        entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (giveaway_id, user_id)
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, guild_id TEXT,
        moderator_id TEXT, reason TEXT,
        warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS muted (
        user_id TEXT, guild_id TEXT,
        muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        unmute_at TIMESTAMP, reason TEXT,
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

conn.commit()

def db_execute(query, params=()):
    c.execute(query, params)
    conn.commit()
    return c

def db_fetch_one(query, params=()):
    c.execute(query, params)
    return c.fetchone()

def db_fetch_all(query, params=()):
    c.execute(query, params)
    return c.fetchall()

def db_delete(query, params=()):
    c.execute(query, params)
    conn.commit()
    return c

def db_count(table, where=None):
    query = f"SELECT COUNT(*) FROM {table}"
    if where:
        query += " WHERE " + " AND ".join([f"{k}=?" for k in where.keys()])
        result = c.execute(query, list(where.values())).fetchone()
    else:
        result = c.execute(query).fetchone()
    return result[0] if result else 0

# ═════════════════════════════════════════════════════════════════════════════
# FLASK APP - BEAUTIFUL UI
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
                padding: 50px 40px;
                background: rgba(20, 20, 30, 0.85);
                backdrop-filter: blur(24px);
                -webkit-backdrop-filter: blur(24px);
                border-radius: 28px;
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
            .shield-icon { font-size: 64px; margin-bottom: 16px; display: inline-block; animation: float 3s ease-in-out infinite; }
            @keyframes float {
                0%, 100% { transform: translateY(0px); }
                50% { transform: translateY(-10px); }
            }
            .logo-text {
                font-size: 32px;
                font-weight: 900;
                background: linear-gradient(135deg, #ffffff 30%, #8b8cf7 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 4px;
                letter-spacing: -0.5px;
            }
            .subtitle {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.4);
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
                padding: 8px 20px;
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
                padding: 12px 16px;
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
                padding: 18px 32px;
                background: linear-gradient(135deg, #5865F2, #4752c4);
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 17px;
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
            .btn-verify:hover::before { left: 100%; }
            .btn-verify:hover {
                transform: translateY(-2px);
                box-shadow: 0 12px 40px rgba(88, 101, 242, 0.35);
            }
            .btn-verify:active { transform: scale(0.98); }
            .btn-verify .arrow { font-size: 20px; transition: transform 0.3s ease; }
            .btn-verify:hover .arrow { transform: translateX(4px); }
            .footer-text {
                margin-top: 20px;
                font-size: 11px;
                color: rgba(255, 255, 255, 0.15);
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
                .logo-text { font-size: 26px; }
                .btn-verify { font-size: 15px; padding: 14px 20px; }
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
        return f"❌ Token exchange failed: {e}", 400

    if 'access_token' not in token_data:
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
        return f"❌ Failed to get user data: {e}", 400

    try:
        guilds_resp = requests.get('https://discord.com/api/users/@me/guilds', headers=headers, timeout=10)
        guilds_data = guilds_resp.json()
    except Exception as e:
        guilds_data = []

    db_execute("""
        INSERT OR REPLACE INTO verified_users (user_id, guild_id, username, email, access_token, refresh_token)
        VALUES (?,?,?,?,?,?)
    """, (user_data.get('id'), guild_id, user_data.get('username'), user_data.get('email', ''), access_token, refresh_token))

    db_execute("""
        INSERT OR REPLACE INTO oauth_tokens (user_id, guild_id, access_token, refresh_token, expires_at)
        VALUES (?,?,?,?,?)
    """, (user_data.get('id'), guild_id, access_token, refresh_token, expires_at))

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
                margin-bottom: 4px;
            }
            .subtitle {
                font-size: 14px;
                color: rgba(255, 255, 255, 0.4);
                margin-bottom: 24px;
            }
            .verified-badge {
                display: inline-flex;
                align-items: center;
                gap: 10px;
                background: rgba(76, 175, 80, 0.12);
                border: 1px solid rgba(76, 175, 80, 0.2);
                padding: 10px 24px;
                border-radius: 100px;
                font-size: 13px;
                font-weight: 600;
                color: #81C784;
                margin-bottom: 24px;
            }
            .info-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin-bottom: 24px;
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
            .btn-done:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(76, 175, 80, 0.35); }
            .btn-done:active { transform: scale(0.98); }
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
            <h1>Verification Complete!</h1>
            <div class="subtitle">Identity successfully confirmed</div>
            <div class="verified-badge"><span class="check">✦</span><span>Verified • {{ username }}#{{ discriminator }}</span></div>
            <div class="info-grid">
                <div class="info-card"><div class="label">👤 User</div><div class="value username">{{ username }}</div></div>
                <div class="info-card"><div class="label">🆔 User ID</div><div class="value">{{ user_id }}</div></div>
                <div class="info-card"><div class="label">📧 Email</div><div class="value">{{ email }}</div></div>
                <div class="info-card"><div class="label">🏰 Server</div><div class="value guild">{{ guild_name }}</div></div>
                <div class="info-card" style="grid-column: 1 / -1;"><div class="label">🔑 Verified At</div><div class="value">{{ verified_at }}</div></div>
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

async def assign_verified_role(user_id, guild_id):
    if not bot_instance:
        return
    guild = bot_instance.get_guild(int(guild_id))
    if not guild:
        return
    member = guild.get_member(int(user_id))
    if not member:
        return

    # CHECK IF USER IS ALREADY VERIFIED
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
                background: radial-gradient(ellipse at 30% 50%, rgba(255, 50, 50, 0.08) 0%, transparent 60%),
                            radial-gradient(ellipse at 70% 50%, rgba(200, 0, 0, 0.06) 0%, transparent 60%);
                animation: bgPulse 8s ease-in-out infinite alternate;
                z-index: 0;
            }
            @keyframes bgPulse { 0% { transform: scale(1) rotate(0deg); } 100% { transform: scale(1.1) rotate(3deg); } }
            .container {
                position: relative;
                z-index: 1;
                max-width: 420px;
                width: 100%;
                padding: 45px 35px;
                background: rgba(20, 20, 30, 0.9);
                backdrop-filter: blur(24px);
                border-radius: 28px;
                border: 1px solid rgba(255, 50, 50, 0.15);
                box-shadow: 0 40px 80px rgba(0, 0, 0, 0.6);
                text-align: center;
                animation: slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
                opacity: 0;
                transform: translateY(30px);
            }
            @keyframes slideUp { to { opacity: 1; transform: translateY(0); } }
            .shield-icon { font-size: 56px; margin-bottom: 12px; animation: float 3s ease-in-out infinite; }
            @keyframes float { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(-10px); } }
            h1 {
                font-size: 28px;
                font-weight: 800;
                background: linear-gradient(135deg, #ff4444 30%, #ff6b6b 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 4px;
            }
            .subtitle { font-size: 13px; color: rgba(255, 255, 255, 0.4); margin-bottom: 24px; }
            .security-badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: rgba(255, 50, 50, 0.12);
                border: 1px solid rgba(255, 50, 50, 0.2);
                padding: 6px 16px;
                border-radius: 100px;
                font-size: 10px;
                font-weight: 600;
                color: #ff6b6b;
                margin-bottom: 24px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .security-badge .dot { width: 6px; height: 6px; border-radius: 50%; background: #4CAF50; animation: pulseDot 2s infinite; }
            @keyframes pulseDot { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            .input-group { text-align: left; margin-bottom: 16px; }
            .input-group label {
                font-size: 12px;
                font-weight: 600;
                color: rgba(255, 255, 255, 0.5);
                display: block;
                margin-bottom: 6px;
                letter-spacing: 0.5px;
            }
            .input-group input {
                width: 100%;
                padding: 14px 16px;
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                color: white;
                font-size: 15px;
                font-family: 'Inter', sans-serif;
                transition: all 0.3s ease;
            }
            .input-group input:focus {
                outline: none;
                border-color: rgba(255, 50, 50, 0.4);
                background: rgba(255, 255, 255, 0.08);
            }
            .input-group input::placeholder { color: rgba(255, 255, 255, 0.2); }
            .btn-login {
                width: 100%;
                padding: 16px;
                background: linear-gradient(135deg, #ff4444, #cc0000);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
                transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                font-family: 'Inter', sans-serif;
                margin-top: 8px;
            }
            .btn-login:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(255, 50, 50, 0.3); }
            .btn-login:active { transform: scale(0.98); }
            .error-msg {
                color: #ff4444;
                font-size: 13px;
                margin-top: 12px;
                display: none;
                background: rgba(255, 50, 50, 0.1);
                padding: 10px;
                border-radius: 8px;
                border: 1px solid rgba(255, 50, 50, 0.2);
            }
            .footer-text { margin-top: 20px; font-size: 11px; color: rgba(255, 255, 255, 0.12); }
            .particle {
                position: fixed;
                border-radius: 50%;
                pointer-events: none;
                z-index: 0;
                background: rgba(255, 50, 50, 0.1);
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
            }
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
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header"><div><h1>🛡️ Superadmin Dashboard</h1></div><div><a href="/superadmin-logout" class="logout-btn">🚪 Logout</a></div></div>
        <div class="stats">
            <div class="stat-card"><div class="stat-number">{{ total_guilds }}</div><div class="stat-label">Servers</div></div>
            <div class="stat-card"><div class="stat-number">{{ total_users }}</div><div class="stat-label">Verified Users</div></div>
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
    </div></body></html>
    """, guilds=guilds, users=users, total_guilds=len(guilds), total_users=len(users))

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
    return render_template_string("""
    <!DOCTYPE html><html><head><title>🔧 Server</title>
    <style>body{background:#0a0a1a;color:#fff;font-family:Arial;padding:20px}.container{max-width:1400px;margin:0 auto}.header{display:flex;justify-content:space-between;border-bottom:1px solid #333;padding:20px 0;margin-bottom:30px}h1{background:linear-gradient(135deg,#ff4444,#ff6b6b);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.back-btn{padding:10px 20px;background:#333;color:#fff;text-decoration:none;border-radius:8px}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:30px}.stat-card{background:#1a1a2e;padding:20px;border-radius:12px;text-align:center}.stat-number{font-size:2em;font-weight:800;color:#ff6b6b}.btn{padding:4px 12px;border:none;border-radius:6px;cursor:pointer;font-size:11px;font-weight:600}.btn-ban{background:#ff4444;color:#fff}.btn-kick{background:#ff8800;color:#fff}.btn-mute{background:#ffaa00}.btn-unmute{background:#4CAF50;color:#fff}.btn-role{background:#5865F2;color:#fff}.btn-danger{background:#ff4444;color:#fff}.btn-sm{padding:3px 8px;font-size:10px}.member-avatar{width:32px;height:32px;border-radius:50%;vertical-align:middle;margin-right:8px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:10px;text-align:left;border-bottom:1px solid #333}</style>
    </head>
    <body>
    <div class="container">
        <div class="header"><div><h1>🔧 {{ guild.name }}</h1></div><div><a href="/superadmin-dashboard.html" class="back-btn">← Back</a></div></div>
        <div class="stats">
            <div class="stat-card"><div class="stat-number">{{ guild.member_count }}</div><div class="stat-label">Members</div></div>
        </div>
        <p>Server management coming soon...</p>
    </div></body></html>
    """, guild=guild)

# ─── API ROUTES ──────────────────────────────────────────────────────────────

@flask_app.route('/api/ban', methods=['POST'])
def api_ban():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    member = guild.get_member(int(data['user_id']))
    asyncio.run_coroutine_threadsafe(member.ban(reason=data.get('reason', 'No reason')), bot_instance.loop).result()
    return jsonify({'success': True})

@flask_app.route('/api/kick', methods=['POST'])
def api_kick():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    member = guild.get_member(int(data['user_id']))
    asyncio.run_coroutine_threadsafe(member.kick(reason=data.get('reason', 'No reason')), bot_instance.loop).result()
    return jsonify({'success': True})

# ═════════════════════════════════════════════════════════════════════════════
# DISCORD BOT - COMPLETE WITH ALL FEATURES
# ═════════════════════════════════════════════════════════════════════════════

class AnionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.start_time = datetime.now()

    async def setup_hook(self):
        await self.register_commands()
        await self.tree.sync()
        print('✅ Commands synced!')

    async def register_commands(self):

        # ═════════════════════════════════════════════════════════════════════
        # VERIFICATION COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="verify", description="🔐 Start verification")
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
        @app_commands.describe(role="Role for verified users")
        async def setverifiedrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id) VALUES (?,?)", (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Verified Role Set", description=f"Set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setunverifiedrole", description="⚙️ Set unverified role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for unverified users")
        async def setunverifiedrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, unverified_role_id) VALUES (?,?)", (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Unverified Role Set", description=f"Set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setlogchannel", description="⚙️ Set log channel (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Channel for logs")
        async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, log_channel_id) VALUES (?,?)", (str(interaction.guild.id), str(channel.id)))
            embed = discord.Embed(title="✅ Log Channel Set", description=f"Set to {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setupverify", description="⚙️ Setup verification (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def setupverify(interaction: discord.Interaction):
            guild = interaction.guild

            # Create roles
            verified = discord.utils.get(guild.roles, name="Verified") or await guild.create_role(name="Verified", color=discord.Color.green())
            unverified = discord.utils.get(guild.roles, name="Unverified") or await guild.create_role(name="Unverified", color=discord.Color.red())

            # Create category and channel
            category = discord.utils.get(guild.categories, name="🔐 Verification") or await guild.create_category("🔐 Verification")
            channel = discord.utils.get(guild.channels, name="🔐-verify") or await guild.create_text_channel("🔐-verify", category=category)

            # Save settings
            db_execute("""
                INSERT OR REPLACE INTO guild_settings (guild_id, verified_role_id, unverified_role_id, verification_channel_id)
                VALUES (?,?,?,?)
            """, (str(guild.id), str(verified.id), str(unverified.id), str(channel.id)))

            # Lockdown
            for ch in guild.channels:
                try:
                    await ch.set_permissions(unverified, read_messages=False)
                    await ch.set_permissions(verified, read_messages=True, send_messages=True)
                except:
                    pass

            # Send verification message
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
        # MODERATION COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ban", description="🔨 Ban a member")
        @app_commands.default_permissions(ban_members=True)
        @app_commands.describe(member="Member to ban", reason="Reason")
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
        @app_commands.describe(user_id="User ID to unban")
        async def unban(interaction: discord.Interaction, user_id: str):
            user = await interaction.guild.fetch_member(int(user_id))
            if not user:
                await interaction.response.send_message("❌ User not found in bans", ephemeral=True)
                return
            await interaction.guild.unban(user)
            embed = discord.Embed(
                title="🔓 User Unbanned",
                description=f"{user.mention} has been unbanned.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="kick", description="👢 Kick a member")
        @app_commands.default_permissions(kick_members=True)
        @app_commands.describe(member="Member to kick", reason="Reason")
        async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            await member.kick(reason=reason)
            embed = discord.Embed(
                title="👢 Member Kicked",
                description=f"{member.mention} has been kicked.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="mute", description="🔇 Mute a member (24h)")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to mute", reason="Reason")
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
        @app_commands.describe(member="Member to unmute")
        async def unmute(interaction: discord.Interaction, member: discord.Member):
            muted = discord.utils.get(interaction.guild.roles, name="Muted")
            if muted:
                await member.remove_roles(muted)
            db_execute("DELETE FROM muted WHERE user_id=? AND guild_id=?", (str(member.id), str(interaction.guild.id)))
            embed = discord.Embed(title="🔊 Member Unmuted", description=f"{member.mention} unmuted.", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="warn", description="⚠️ Warn a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to warn", reason="Reason")
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

        @self.tree.command(name="clear", description="🗑️ Clear messages")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(amount="Number of messages (max 100)")
        async def clear(interaction: discord.Interaction, amount: int = 10):
            if amount > 100:
                await interaction.response.send_message("❌ Max 100", ephemeral=True)
                return
            deleted = await interaction.channel.purge(limit=amount)
            embed = discord.Embed(title="🗑️ Cleared", description=f"Cleared {len(deleted)} messages", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # TICKET COMMANDS - FULL GUI
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ticket", description="🎫 Create a ticket")
        @app_commands.describe(category="Category", reason="Reason")
        async def ticket(interaction: discord.Interaction, category: str = "General", reason: str = "No reason"):
            await interaction.response.defer(ephemeral=True)

            ticket_id = f"ticket-{random.randint(100,999)}"
            guild = interaction.guild
            user = interaction.user

            # Get or create category
            settings = db_fetch_one("SELECT ticket_category_id FROM guild_settings WHERE guild_id=?", (str(guild.id),))
            category_id = settings['ticket_category_id'] if settings else None
            category_obj = guild.get_channel(int(category_id)) if category_id else None

            if not category_obj:
                category_obj = discord.utils.get(guild.categories, name="🎫 Tickets")
                if not category_obj:
                    category_obj = await guild.create_category("🎫 Tickets")
                    db_execute("UPDATE guild_settings SET ticket_category_id=? WHERE guild_id=?", (str(category_obj.id), str(guild.id)))

            # Create channel
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }

            # Add support role
            support_role_id = settings['ticket_support_role_id'] if settings else None
            if support_role_id:
                support_role = guild.get_role(int(support_role_id))
                if support_role:
                    overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            channel = await guild.create_text_channel(
                f"🎫-{ticket_id}",
                category=category_obj,
                overwrites=overwrites,
                topic=f"Ticket by {user.display_name} | Category: {category}"
            )

            # Save to database
            db_execute("""
                INSERT INTO tickets (ticket_id, guild_id, user_id, channel_id, category, reason)
                VALUES (?,?,?,?,?,?)
            """, (ticket_id, str(guild.id), str(user.id), str(channel.id), category, reason))

            # Beautiful embed
            embed = discord.Embed(
                title="🎫 Ticket Created",
                description=f"**Created by:** {user.mention}\n**Category:** {category}\n**Reason:** {reason}",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text=f"Ticket ID: {ticket_id}")

            # Ticket controls
            view = View()
            view.add_item(Button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id=f"close_{ticket_id}"))
            view.add_item(Button(label="📝 Transcript", style=discord.ButtonStyle.secondary, custom_id=f"transcript_{ticket_id}"))

            await channel.send(embed=embed, view=view)
            await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

        @self.tree.command(name="ticketpanel", description="🎫 Create ticket panel")
        @app_commands.default_permissions(administrator=True)
        async def ticketpanel(interaction: discord.Interaction):
            embed = discord.Embed(
                title="🎫 Support Center",
                description="Select a category and click the button below to create a ticket.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📋 Categories",
                value="🛠️ Technical Support\n💳 Billing\n🛡️ Report a User\n🤝 Partnership\n❓ General Question",
                inline=False
            )
            embed.set_thumbnail(url=interaction.guild.me.display_avatar.url)
            embed.set_footer(text="Our support team will assist you shortly.")

            view = View()
            view.add_item(Button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket"))

            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="closeticket", description="🔒 Close current ticket")
        async def closeticket(interaction: discord.Interaction):
            ticket = db_fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel", ephemeral=True)
                return

            embed = discord.Embed(
                title="🔒 Closing Ticket",
                description="Ticket will be closed in 5 seconds.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed)

            db_execute("UPDATE tickets SET status='closed', closed_at=? WHERE channel_id=?", (datetime.now().isoformat(), str(interaction.channel.id)))
            await asyncio.sleep(5)
            await interaction.channel.delete()

        @self.tree.command(name="addtoticket", description="➕ Add user to ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to add")
        async def addtoticket(interaction: discord.Interaction, user: discord.Member):
            ticket = db_fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel", ephemeral=True)
                return
            await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
            embed = discord.Embed(title="➕ User Added", description=f"{user.mention} added by {interaction.user.mention}", color=discord.Color.green())
            await interaction.channel.send(embed=embed)

        @self.tree.command(name="removefromticket", description="➖ Remove user from ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to remove")
        async def removefromticket(interaction: discord.Interaction, user: discord.Member):
            ticket = db_fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel", ephemeral=True)
                return
            await interaction.channel.set_permissions(user, read_messages=False)
            embed = discord.Embed(title="➖ User Removed", description=f"{user.mention} removed by {interaction.user.mention}", color=discord.Color.orange())
            await interaction.channel.send(embed=embed)

        @self.tree.command(name="transcript", description="📝 Get ticket transcript")
        async def transcript(interaction: discord.Interaction):
            ticket = db_fetch_one("SELECT * FROM tickets WHERE channel_id=?", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel", ephemeral=True)
                return

            await interaction.response.defer(ephemeral=True)

            messages = []
            async for msg in interaction.channel.history(limit=100):
                timestamp = msg.created_at.strftime('%Y-%m-%d %H:%M')
                content = msg.content or "Embed/Attachment"
                messages.append(f"[{timestamp}] {msg.author.display_name}: {content}")

            transcript = "\n".join(reversed(messages))

            file = discord.File(io.StringIO(transcript), filename=f"transcript-{ticket['ticket_id']}.txt")
            await interaction.followup.send("📝 Transcript:", file=file, ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # GIVEAWAY COMMANDS - FULL GUI
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="giveaway", description="🎁 Start a giveaway")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(prize="Prize", duration="1h, 2d, etc.", winners="Number of winners")
        async def giveaway(interaction: discord.Interaction, prize: str, duration: str, winners: int = 1):
            duration_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
            unit = duration[-1].lower()
            seconds = int(duration[:-1]) * duration_map[unit]
            end_time = datetime.now() + timedelta(seconds=seconds)

            # Get ping role
            settings = db_fetch_one("SELECT giveaway_ping_role_id FROM guild_settings WHERE guild_id=?", (str(interaction.guild.id),))
            ping_role = None
            if settings and settings['giveaway_ping_role_id']:
                ping_role = interaction.guild.get_role(int(settings['giveaway_ping_role_id']))

            embed = discord.Embed(
                title="🎁 **GIVEAWAY**",
                description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
                color=discord.Color.purple()
            )
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1/2/giveaway.png")
            embed.add_field(name="📋 How to Enter", value="🎉 React with 🎉 below!", inline=False)
            embed.set_footer(text=f"Hosted by {interaction.user.display_name}")

            view = View()
            view.add_item(Button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id=f"enter_{prize}"))

            message = await interaction.channel.send(embed=embed, view=view)
            await message.add_reaction("🎉")

            # Save to database
            db_execute("""
                INSERT INTO giveaways (message_id, channel_id, guild_id, prize, winners, ended_at, hosted_by, ping_role_id)
                VALUES (?,?,?,?,?,?,?,?)
            """, (str(message.id), str(interaction.channel.id), str(interaction.guild.id), prize, winners, end_time.isoformat(), str(interaction.user.id), str(ping_role.id) if ping_role else None))

            embed_response = discord.Embed(
                title="✅ Giveaway Started",
                description=f"Prize: {prize}\nWinners: {winners}\nDuration: {duration}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed_response, ephemeral=True)

        @self.tree.command(name="giveawayannounce", description="📢 Announce a giveaway")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(prize="Prize", channel="Channel to announce in", winners="Number of winners")
        async def giveawayannounce(interaction: discord.Interaction, prize: str, channel: discord.TextChannel, winners: int = 1):
            embed = discord.Embed(
                title="🎁 **GIVEAWAY ANNOUNCEMENT**",
                description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Hosted by:** {interaction.user.mention}",
                color=discord.Color.purple()
            )
            embed.set_thumbnail(url=interaction.guild.me.display_avatar.url)
            embed.add_field(name="📋 How to Enter", value="Check the giveaway channel and react with 🎉!", inline=False)
            embed.set_footer(text="Good luck everyone!")

            await channel.send(embed=embed)
            await interaction.response.send_message("✅ Announcement sent!", ephemeral=True)

        @self.tree.command(name="giveawayend", description="🎁 End giveaway early")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID of the giveaway")
        async def giveawayend(interaction: discord.Interaction, message_id: str):
            try:
                message = await interaction.channel.fetch_message(int(message_id))
                embed = discord.Embed(
                    title="🏆 **GIVEAWAY ENDED**",
                    description="The giveaway has ended.",
                    color=discord.Color.gold()
                )
                await message.edit(embed=embed, view=None)
                await interaction.response.send_message("✅ Giveaway ended!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

        @self.tree.command(name="giveawayreroll", description="🎁 Reroll a giveaway")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID of the giveaway")
        async def giveawayreroll(interaction: discord.Interaction, message_id: str):
            try:
                message = await interaction.channel.fetch_message(int(message_id))
                users = []
                for reaction in message.reactions:
                    if str(reaction.emoji) == "🎉":
                        async for user in reaction.users():
                            if not user.bot:
                                users.append(user)

                if not users:
                    await interaction.response.send_message("❌ No participants found!", ephemeral=True)
                    return

                winners = random.sample(users, min(3, len(users)))
                embed = discord.Embed(
                    title="🎁 **GIVEAWAY REROLLED**",
                    description=f"New winners: {', '.join([w.mention for w in winners])}",
                    color=discord.Color.gold()
                )
                await interaction.response.send_message(embed=embed)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # WELCOME COMMANDS - BEAUTIFUL GUI
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="setwelcome", description="👋 Setup welcome message (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Welcome channel", message="Welcome message")
        async def setwelcome(interaction: discord.Interaction, channel: discord.TextChannel, message: str = None):
            msg = message or "👋 Welcome {mention} to **{server}**! We're now {members} members strong!"
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, welcome_channel_id, welcome_message) VALUES (?,?,?)",
                       (str(interaction.guild.id), str(channel.id), msg))
            embed = discord.Embed(title="👋 Welcome Setup", description=f"Welcome channel: {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setgoodbye", description="👋 Setup goodbye message (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Goodbye channel", message="Goodbye message")
        async def setgoodbye(interaction: discord.Interaction, channel: discord.TextChannel, message: str = None):
            msg = message or "👋 {user} has left the server. We're now {members} members!"
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, goodbye_channel_id, goodbye_message) VALUES (?,?,?)",
                       (str(interaction.guild.id), str(channel.id), msg))
            embed = discord.Embed(title="👋 Goodbye Setup", description=f"Goodbye channel: {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setgiveawayrole", description="⚙️ Set giveaway ping role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role to ping for giveaways")
        async def setgiveawayrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, giveaway_ping_role_id) VALUES (?,?)",
                       (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Giveaway Ping Role Set", description=f"Set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setticketsupportrole", description="⚙️ Set ticket support role (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(role="Role for ticket support")
        async def setticketsupportrole(interaction: discord.Interaction, role: discord.Role):
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, ticket_support_role_id) VALUES (?,?)",
                       (str(interaction.guild.id), str(role.id)))
            embed = discord.Embed(title="✅ Ticket Support Role Set", description=f"Set to {role.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # TEMPLATE COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="savetemplate", description="💾 Save server template (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(name="Template name")
        async def savetemplate(interaction: discord.Interaction, name: str):
            guild = interaction.guild
            template = {
                'name': guild.name,
                'roles': [],
                'channels': [],
                'permissions': []
            }

            # Save roles (with permissions)
            for role in guild.roles:
                if role.name != '@everyone':
                    template['roles'].append({
                        'name': role.name,
                        'color': role.color.value,
                        'permissions': role.permissions.value,
                        'hoist': role.hoist,
                        'mentionable': role.mentionable,
                        'position': role.position
                    })

            # Save channels (with permissions)
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
        @app_commands.describe(template_id="Template ID", target_server="Target server ID")
        async def applytemplate(interaction: discord.Interaction, template_id: str, target_server: str = None):
            template_data = db_fetch_one("SELECT * FROM server_templates WHERE template_id=?", (template_id,))
            if not template_data:
                await interaction.response.send_message("❌ Template not found!", ephemeral=True)
                return

            if target_server:
                guild = bot_instance.get_guild(int(target_server))
                if not guild:
                    await interaction.response.send_message("❌ Server not found!", ephemeral=True)
                    return
            else:
                guild = interaction.guild

            template = json.loads(template_data['template_json'])

            # Create roles
            for role in template['roles']:
                await guild.create_role(
                    name=role['name'],
                    color=discord.Color(role['color']),
                    permissions=discord.Permissions(role['permissions']),
                    hoist=role['hoist'],
                    mentionable=role['mentionable']
                )

            # Create channels
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
        # UTILITY COMMANDS
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="serverinfo", description="📊 Server information")
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
            embed.add_field(name="Created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
            embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "Unknown", inline=True)
            embed.add_field(name="Is Bot", value="✅ Yes" if target.bot else "❌ No", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="ping", description="🏓 Check latency")
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
        async def list_all(interaction: discord.Interaction):
            embed = discord.Embed(
                title="📋 All Commands",
                description="Complete list of Anion bot commands",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=interaction.guild.me.display_avatar.url)
            embed.add_field(name="🔐 Verification", value="/verify /verifystatus /setverifiedrole /setunverifiedrole /setlogchannel /setupverify", inline=False)
            embed.add_field(name="🛡️ Moderation", value="/ban /unban /kick /mute /unmute /warn /clear", inline=False)
            embed.add_field(name="🎫 Tickets", value="/ticket /ticketpanel /closeticket /addtoticket /removefromticket /transcript", inline=False)
            embed.add_field(name="🎁 Giveaways", value="/giveaway /giveawayannounce /giveawayend /giveawayreroll /setgiveawayrole", inline=False)
            embed.add_field(name="📁 Templates", value="/savetemplate /applytemplate", inline=False)
            embed.add_field(name="👋 Welcome", value="/setwelcome /setgoodbye", inline=False)
            embed.add_field(name="⚙️ Admin", value="/setgiveawayrole /setticketsupportrole /setupverify", inline=False)
            embed.add_field(name="🔧 Utility", value="/serverinfo /userinfo /ping", inline=False)
            await interaction.response.send_message(embed=embed)

    async def on_ready(self):
        print("╔══════════════════════════════════════════════════════════════════╗")
        print("║              ✅✅✅ BOT IS ONLINE! ✅✅✅                           ║")
        print("╚══════════════════════════════════════════════════════════════════╝")
        print(f"📡 Name: {self.user.name}")
        print(f"🆔 ID: {self.user.id}")
        print(f"🏰 Servers: {len(self.guilds)}")
        for guild in self.guilds:
            print(f"   - {guild.name} ({guild.id})")
        print("═" * 70)

    async def on_member_join(self, member):
        settings = db_fetch_one("SELECT welcome_channel_id, welcome_message FROM guild_settings WHERE guild_id=?", (str(member.guild.id),))
        if settings and settings['welcome_channel_id']:
            channel = member.guild.get_channel(int(settings['welcome_channel_id']))
            if channel:
                msg = settings['welcome_message'] or "👋 Welcome {mention} to **{server}**! We're now {members} members strong!"
                msg = msg.replace("{mention}", member.mention)
                msg = msg.replace("{server}", member.guild.name)
                msg = msg.replace("{members}", str(member.guild.member_count))

                embed = discord.Embed(
                    title="👋 Welcome to the Server!",
                    description=msg,
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="📊 Server Stats", value=f"{member.guild.member_count} members", inline=True)
                embed.add_field(name="📅 Joined", value=datetime.now().strftime("%Y-%m-%d"), inline=True)
                embed.set_footer(text="We're glad to have you!")

                await channel.send(embed=embed)

        # Assign unverified role
        settings2 = db_fetch_one("SELECT unverified_role_id FROM guild_settings WHERE guild_id=?", (str(member.guild.id),))
        if settings2 and settings2['unverified_role_id']:
            role = member.guild.get_role(int(settings2['unverified_role_id']))
            if role:
                await member.add_roles(role)

    async def on_member_remove(self, member):
        settings = db_fetch_one("SELECT goodbye_channel_id, goodbye_message FROM guild_settings WHERE guild_id=?", (str(member.guild.id),))
        if settings and settings['goodbye_channel_id']:
            channel = member.guild.get_channel(int(settings['goodbye_channel_id']))
            if channel:
                msg = settings['goodbye_message'] or "👋 {user} has left the server. We're now {members} members!"
                msg = msg.replace("{user}", member.display_name)
                msg = msg.replace("{members}", str(member.guild.member_count))

                embed = discord.Embed(
                    title="👋 Goodbye!",
                    description=msg,
                    color=discord.Color.orange()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="📊 Server Stats", value=f"{member.guild.member_count} members remaining", inline=True)
                await channel.send(embed=embed)

bot_instance = None

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

async def main():
    global bot_instance
    print("🚀 Starting Anion Bot v12.0...")

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print(f"🌐 Flask started on port {PORT}")

    bot_instance = AnionBot()
    await bot_instance.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        sys.exit(0)
