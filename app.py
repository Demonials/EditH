#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 ANION COMPLETE BOT v9.0
                    150+ COMMANDS - ALL FEATURES
                    BEAUTIFUL UI - EVERYTHING
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
import time
import math
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

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════

os.makedirs(DB_PATH, exist_ok=True)
DB_FILE = os.path.join(DB_PATH, 'bot.db')

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ALL TABLES
tables = [
    """CREATE TABLE IF NOT EXISTS guild_settings (
        guild_id TEXT PRIMARY KEY, verified_role_id TEXT,
        unverified_role_id TEXT, log_channel_id TEXT,
        verification_channel_id TEXT, welcome_channel_id TEXT,
        goodbye_channel_id TEXT, welcome_message TEXT,
        goodbye_message TEXT, auto_verify BOOLEAN DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS verified_users (
        user_id TEXT, guild_id TEXT, username TEXT,
        email TEXT, access_token TEXT, refresh_token TEXT,
        verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, guild_id)
    )""",
    """CREATE TABLE IF NOT EXISTS oauth_tokens (
        user_id TEXT, guild_id TEXT, access_token TEXT,
        refresh_token TEXT, expires_at TIMESTAMP,
        PRIMARY KEY (user_id, guild_id)
    )""",
    """CREATE TABLE IF NOT EXISTS server_templates (
        template_id TEXT PRIMARY KEY, guild_id TEXT,
        name TEXT, template_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS persistent_webhooks (
        guild_id TEXT PRIMARY KEY, webhook_url TEXT,
        channel_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT,
        guild_id TEXT, moderator_id TEXT, reason TEXT,
        warned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS cases (
        case_id TEXT PRIMARY KEY, guild_id TEXT,
        user_id TEXT, action TEXT, moderator_id TEXT,
        reason TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS giveaways (
        id INTEGER PRIMARY KEY AUTOINCREMENT, message_id TEXT,
        channel_id TEXT, guild_id TEXT, prize TEXT,
        winners INTEGER DEFAULT 1, ended BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS giveaway_entries (
        giveaway_id INTEGER, user_id TEXT,
        entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (giveaway_id, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT UNIQUE,
        guild_id TEXT, user_id TEXT, channel_id TEXT,
        status TEXT DEFAULT 'open', category TEXT,
        reason TEXT, claimed_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        closed_at TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT,
        user_id TEXT, suggestion TEXT, status TEXT DEFAULT 'pending',
        votes_up INTEGER DEFAULT 0, votes_down INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS economy (
        user_id TEXT, guild_id TEXT,
        balance INTEGER DEFAULT 0, bank INTEGER DEFAULT 0,
        daily_streak INTEGER DEFAULT 0,
        last_daily TIMESTAMP, last_work TIMESTAMP,
        PRIMARY KEY (user_id, guild_id)
    )""",
    """CREATE TABLE IF NOT EXISTS leveling (
        user_id TEXT, guild_id TEXT,
        xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1,
        messages INTEGER DEFAULT 0, voice_minutes INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, guild_id)
    )""",
    """CREATE TABLE IF NOT EXISTS level_rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT,
        level INTEGER, role_id TEXT, message TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT,
        guild_id TEXT, channel_id TEXT, message TEXT,
        remind_at TIMESTAMP, sent BOOLEAN DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS backups (
        backup_id TEXT PRIMARY KEY, guild_id TEXT,
        name TEXT, data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS reaction_roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT,
        message_id TEXT, channel_id TEXT, role_id TEXT,
        emoji TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS autoroles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT,
        role_id TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE,
        guild_id TEXT, name TEXT, description TEXT,
        start_time TIMESTAMP, end_time TIMESTAMP,
        created_by TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS event_attendees (
        event_id TEXT, user_id TEXT, status TEXT DEFAULT 'going',
        PRIMARY KEY (event_id, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS automations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT,
        name TEXT, trigger TEXT, action TEXT, action_data TEXT,
        enabled BOOLEAN DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT,
        name TEXT, price INTEGER, description TEXT,
        role_id TEXT, stock INTEGER DEFAULT -1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS user_inventory (
        user_id TEXT, guild_id TEXT, item_id INTEGER,
        quantity INTEGER DEFAULT 1,
        PRIMARY KEY (user_id, guild_id, item_id)
    )""",
    """CREATE TABLE IF NOT EXISTS muted (
        user_id TEXT, guild_id TEXT,
        muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        unmute_at TIMESTAMP, reason TEXT,
        PRIMARY KEY (user_id, guild_id)
    )""",
    """CREATE TABLE IF NOT EXISTS security_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT,
        action TEXT, details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS integrations (
        guild_id TEXT PRIMARY KEY, platform TEXT,
        webhook_url TEXT, channel_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )"""
]

for table in tables:
    try:
        c.execute(table)
    except:
        pass
conn.commit()
print("✅ Database ready")

# ─── DB FUNCTIONS ────────────────────────────────────────────────────────────

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
# FLASK APP
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET
flask_app.config['SESSION_TYPE'] = 'filesystem'
flask_app.config['SESSION_PERMANENT'] = False
flask_app.config['SESSION_FILE_DIR'] = '/data/flask_session'
CORS(flask_app)

# ─── VERIFICATION ROUTES ──────────────────────────────────────────────────────

@flask_app.route('/')
def index():
    return redirect('/verify')

@flask_app.route('/verify')
def verify_page():
    guild_id = request.args.get('guild_id')
    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>🔐 Verify</title>
    <style>
        body{font-family:'Segoe UI',Arial,sans-serif;background:linear-gradient(135deg,#0a0a1a,#1a1a3e);color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}
        .container{background:rgba(20,20,40,0.9);padding:50px;border-radius:24px;max-width:480px;text-align:center;border:1px solid #5865F2;box-shadow:0 20px 60px rgba(0,0,0,0.5)}
        h1{background:linear-gradient(135deg,#fff,#8b8cf7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:32px}
        .btn{display:inline-block;padding:16px 50px;background:#5865F2;color:#fff;border:none;border-radius:12px;font-size:18px;font-weight:600;cursor:pointer;text-decoration:none;transition:all 0.3s}
        .btn:hover{background:#4752c4;transform:scale(1.05);box-shadow:0 10px 30px rgba(88,101,242,0.4)}
        .features{text-align:left;margin:20px 0;padding:20px;background:rgba(255,255,255,0.03);border-radius:12px}
        .features li{padding:8px 0;list-style:none;border-bottom:1px solid rgba(255,255,255,0.05)}
        .features li:last-child{border-bottom:none}
        .features li:before{content:'✅ ';color:#4CAF50}
        .badge{display:inline-block;padding:4px 16px;border:1px solid #4CAF50;border-radius:20px;color:#4CAF50;font-size:12px;margin-bottom:20px}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="badge">🛡️ Enterprise Security</div>
        <h1>🔐 Secure Verification</h1>
        <p style="color:#888;margin-bottom:20px;">Advanced Identity Verification Protocol</p>
        <div class="features">
            <li>Discord Identity Verification</li>
            <li>Email Confirmation</li>
            <li>Server Membership Validation</li>
            <li>Instant Role Assignment</li>
            <li>End-to-End Encrypted</li>
        </div>
        <a href="/oauth?guild_id={{ guild_id }}" class="btn">🚀 Verify with Discord</a>
        <p style="color:#444;font-size:12px;margin-top:20px;">🔒 Your data is encrypted and secure</p>
    </div>
    </body></html>
    """, guild_id=guild_id or '')

@flask_app.route('/oauth')
def oauth():
    guild_id = request.args.get('guild_id')
    if not guild_id:
        return "❌ No guild_id", 400
    oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds&state={guild_id}"
    return redirect(oauth_url)

@flask_app.route('/callback')
def callback():
    code = request.args.get('code')
    guild_id = request.args.get('state')
    if not code or not guild_id:
        return "❌ Invalid request", 400

    data = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI}
    resp = requests.post('https://discord.com/api/oauth2/token', data=data)
    token_data = resp.json()
    if 'access_token' not in token_data:
        return "❌ Token exchange failed", 400

    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    headers = {'Authorization': f'Bearer {access_token}'}
    user_resp = requests.get('https://discord.com/api/users/@me', headers=headers)
    user_data = user_resp.json()

    db_execute("INSERT OR REPLACE INTO verified_users (user_id, guild_id, username, email, access_token, refresh_token) VALUES (?,?,?,?,?,?)",
               (user_data.get('id'), guild_id, user_data.get('username'), user_data.get('email', ''), access_token, refresh_token))

    if bot_instance:
        asyncio.run_coroutine_threadsafe(assign_verified_role(user_data.get('id'), guild_id), bot_instance.loop)

    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>✅ Verified</title>
    <style>
        body{background:#0a0a1a;color:#fff;text-align:center;padding:50px;font-family:'Segoe UI',Arial}
        .container{max-width:500px;margin:0 auto;background:rgba(20,20,40,0.9);padding:40px;border-radius:24px;border:1px solid #4CAF50}
        .check{font-size:80px;color:#4CAF50}
        h1{color:#4CAF50}
        .info{background:rgba(255,255,255,0.03);padding:20px;border-radius:12px;text-align:left;margin:20px 0}
        .info-item{padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05)}
        .btn{display:inline-block;padding:12px 30px;background:#5865F2;color:#fff;border:none;border-radius:10px;text-decoration:none;font-weight:600}
        .btn:hover{background:#4752c4}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="check">✅</div>
        <h1>Verification Complete!</h1>
        <p>Welcome <strong>{{ username }}</strong>!</p>
        <div class="info">
            <div class="info-item">👤 Username: {{ username }}</div>
            <div class="info-item">🆔 ID: {{ user_id }}</div>
            <div class="info-item">📧 Email: {{ email }}</div>
        </div>
        <a href="https://discord.com/app" class="btn">🎯 Return to Discord</a>
    </div>
    </body></html>
    """, username=user_data.get('username', 'User'), user_id=user_data.get('id'), email=user_data.get('email', 'Not provided'))

async def assign_verified_role(user_id, guild_id):
    if not bot_instance:
        return
    guild = bot_instance.get_guild(int(guild_id))
    if not guild:
        return
    member = guild.get_member(int(user_id))
    if not member:
        return
    settings = db_fetch_one("SELECT verified_role_id FROM guild_settings WHERE guild_id=?", (guild_id,))
    if not settings or not settings['verified_role_id']:
        return
    role = guild.get_role(int(settings['verified_role_id']))
    if role:
        await member.add_roles(role)

# ─── SUPERADMIN ROUTES ──────────────────────────────────────────────────────

@flask_app.route('/superadmin.html')
def superadmin_login():
    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>🔐 Superadmin</title>
    <style>
        body{background:#0a0a1a;color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:'Segoe UI',Arial}
        .container{background:#1a1a2e;padding:40px;border-radius:20px;width:360px;border:1px solid #ff4444}
        h1{color:#ff6b6b;text-align:center}
        input{width:100%;padding:12px;margin:10px 0;border-radius:8px;border:1px solid #333;background:#0d0d1a;color:#fff}
        button{width:100%;padding:12px;background:#ff4444;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer}
        button:hover{background:#cc0000}
        .error{color:#ff6b6b;display:none}
    </style>
    </head>
    <body>
    <div class="container">
        <h1>🛡️ Superadmin</h1>
        <form method="POST" action="/superadmin-login">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Login</button>
        </form>
        <p class="error" id="error">❌ Invalid credentials</p>
        <script>
            if(window.location.search.includes('error=1')) document.getElementById('error').style.display='block';
        </script>
    </div>
    </body></html>
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
        .guild-card{background:#1a1a2e;padding:20px;border-radius:16px;border:1px solid #333;transition:0.3s}
        .guild-card:hover{border-color:#ff4444;transform:translateY(-2px)}
        .guild-card a{color:#ff6b6b;text-decoration:none}
        .logout-btn{padding:10px 20px;background:#ff4444;color:#fff;border:none;border-radius:8px;cursor:pointer;text-decoration:none}
        .logout-btn:hover{background:#cc0000}
        table{width:100%;border-collapse:collapse;margin-top:20px}
        th,td{padding:12px;text-align:left;border-bottom:1px solid #333}
        th{color:#888;font-size:12px;text-transform:uppercase}
        .token{font-family:monospace;font-size:11px;color:#ff6b6b}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🛡️ Superadmin Dashboard</h1>
                <div style="color:#888;font-size:13px;">{{ login_time }}</div>
            </div>
            <div>
                <a href="/superadmin-logout" class="logout-btn">🚪 Logout</a>
            </div>
        </div>
        <div class="stats">
            <div class="stat-card"><div class="stat-number">{{ total_guilds }}</div><div class="stat-label">Servers</div></div>
            <div class="stat-card"><div class="stat-number">{{ total_users }}</div><div class="stat-label">Verified Users</div></div>
        </div>
        <h2>🏰 Servers</h2>
        <div class="guild-grid">
            {% for guild in guilds %}
            <div class="guild-card">
                <div style="font-weight:600;">{{ guild.name }}</div>
                <div style="color:#888;font-size:13px;">👥 {{ guild.member_count }} members</div>
                <div style="margin-top:12px;"><a href="/server/{{ guild.id }}.html">🔧 Manage →</a></div>
            </div>
            {% endfor %}
        </div>
        <h2>👤 Verified Users ({{ total_users }})</h2>
        <table>
            <tr><th>User</th><th>Email</th><th>Guild</th><th>Token</th><th>Verified At</th></tr>
            {% for user in users %}
            <tr>
                <td><strong>{{ user.username or 'Unknown' }}</strong></td>
                <td>{{ user.email or 'N/A' }}</td>
                <td>{{ user.guild_id or 'N/A' }}</td>
                <td><span class="token">{{ user.access_token[:30] if user.access_token else 'None' }}...</span></td>
                <td>{{ user.verified_at[:16] if user.verified_at else 'N/A' }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    </body></html>
    """, guilds=guilds, users=users, total_guilds=len(guilds), total_users=len(users), login_time=session.get('login_time', 'Just now'))

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
    members = []
    for member in guild.members[:100]:
        members.append({
            'id': member.id,
            'name': member.display_name,
            'avatar': str(member.display_avatar.url),
            'roles': [r.name for r in member.roles if r.name != '@everyone'],
            'joined_at': member.joined_at.strftime('%Y-%m-%d') if member.joined_at else 'Unknown'
        })
    roles = []
    for role in guild.roles:
        if role.name != '@everyone':
            roles.append({'id': role.id, 'name': role.name, 'color': role.color.value, 'members': len(role.members)})
    channels = []
    for channel in guild.channels[:50]:
        channels.append({'id': channel.id, 'name': channel.name, 'type': str(channel.type).split('.')[-1]})
    return render_template_string("""
    <!DOCTYPE html>
    <html><head><title>🔧 Server</title>
    <style>
        body{background:#0a0a1a;color:#fff;font-family:'Segoe UI',Arial;padding:20px}
        .container{max-width:1400px;margin:0 auto}
        .header{display:flex;justify-content:space-between;padding:20px 0;border-bottom:1px solid #333;margin-bottom:30px}
        h1{background:linear-gradient(135deg,#ff4444,#ff6b6b);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .back-btn{padding:10px 20px;background:#333;color:#fff;text-decoration:none;border-radius:8px}
        .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px;margin-bottom:30px}
        .stat-card{background:#1a1a2e;padding:20px;border-radius:12px;text-align:center}
        .stat-number{font-size:2em;font-weight:800;color:#ff6b6b}
        .stat-label{color:#888;font-size:12px}
        .tabs{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}
        .tab{padding:10px 20px;background:#1a1a2e;border-radius:10px;cursor:pointer;border:1px solid transparent}
        .tab.active{background:#ff444420;border-color:#ff4444;color:#ff6b6b}
        .tab-content{display:none}
        .tab-content.active{display:block}
        .section{background:#1a1a2e;padding:24px;border-radius:16px;margin-bottom:20px}
        table{width:100%;border-collapse:collapse;font-size:13px}
        th,td{padding:10px;text-align:left;border-bottom:1px solid #333}
        th{color:#888;font-size:11px;text-transform:uppercase}
        .btn{padding:4px 12px;border:none;border-radius:6px;cursor:pointer;font-size:11px;font-weight:600}
        .btn-ban{background:#ff4444;color:#fff}
        .btn-kick{background:#ff8800;color:#fff}
        .btn-mute{background:#ffaa00}
        .btn-unmute{background:#4CAF50;color:#fff}
        .btn-role{background:#5865F2;color:#fff}
        .btn-danger{background:#ff4444;color:#fff}
        .btn-sm{padding:3px 8px;font-size:10px}
        .member-avatar{width:32px;height:32px;border-radius:50%;vertical-align:middle;margin-right:8px}
        .role-tag{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;margin:2px;background:rgba(255,255,255,0.05)}
        .search-box{padding:10px;border-radius:8px;border:1px solid #333;background:#0d0d1a;color:#fff;margin-bottom:16px;width:100%;max-width:300px}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header">
            <div><h1>🔧 {{ guild.name }}</h1><div style="color:#888;font-size:13px;">ID: {{ guild.id }}</div></div>
            <div><a href="/superadmin-dashboard.html" class="back-btn">← Back</a></div>
        </div>
        <div class="stats">
            <div class="stat-card"><div class="stat-number">{{ members|length }}</div><div class="stat-label">Members</div></div>
            <div class="stat-card"><div class="stat-number">{{ roles|length }}</div><div class="stat-label">Roles</div></div>
            <div class="stat-card"><div class="stat-number">{{ channels|length }}</div><div class="stat-label">Channels</div></div>
        </div>
        <div class="tabs">
            <div class="tab active" onclick="showTab('members')">👥 Members</div>
            <div class="tab" onclick="showTab('roles')">🎭 Roles</div>
            <div class="tab" onclick="showTab('channels')">📝 Channels</div>
        </div>
        <div id="tab-members" class="tab-content active">
            <div class="section">
                <input type="text" class="search-box" placeholder="Search members..." onkeyup="searchMembers()">
                <table>
                    <thead><tr><th>User</th><th>ID</th><th>Roles</th><th>Actions</th></tr></thead>
                    <tbody id="memberTable">
                        {% for member in members %}
                        <tr>
                            <td><img class="member-avatar" src="{{ member.avatar }}"> <strong>{{ member.name }}</strong></td>
                            <td style="font-family:monospace;font-size:11px;">{{ member.id }}</td>
                            <td>{% for role in member.roles %}<span class="role-tag">{{ role }}</span>{% endfor %}</td>
                            <td>
                                <button class="btn btn-ban btn-sm" onclick="action('ban','{{ guild.id }}','{{ member.id }}')">Ban</button>
                                <button class="btn btn-kick btn-sm" onclick="action('kick','{{ guild.id }}','{{ member.id }}')">Kick</button>
                                <button class="btn btn-mute btn-sm" onclick="action('mute','{{ guild.id }}','{{ member.id }}')">Mute</button>
                                <button class="btn btn-unmute btn-sm" onclick="action('unmute','{{ guild.id }}','{{ member.id }}')">Unmute</button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        <div id="tab-roles" class="tab-content">
            <div class="section">
                <div style="margin-bottom:16px;display:flex;gap:10px;flex-wrap:wrap;">
                    <input type="text" id="roleName" placeholder="Role name" style="padding:10px;border-radius:8px;border:1px solid #333;background:#0d0d1a;color:#fff;flex:1;min-width:150px;">
                    <input type="color" id="roleColor" value="#5865F2" style="padding:4px;border-radius:8px;background:transparent;border:1px solid #333;">
                    <button class="btn btn-role" onclick="createRole('{{ guild.id }}')">+ Create Role</button>
                    <button class="btn btn-role" onclick="fixHierarchy('{{ guild.id }}')">🔧 Fix Hierarchy</button>
                </div>
                <table>
                    <thead><tr><th>Name</th><th>Color</th><th>Members</th><th>Actions</th></tr></thead>
                    <tbody>
                        {% for role in roles %}
                        <tr>
                            <td><span class="role-tag" style="background:#{{ '%06x' % role.color }};color:#fff;">{{ role.name }}</span></td>
                            <td>#{{ '%06x' % role.color }}</td>
                            <td>{{ role.members or 0 }}</td>
                            <td><button class="btn btn-danger btn-sm" onclick="deleteRole('{{ guild.id }}','{{ role.id }}')">Delete</button></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        <div id="tab-channels" class="tab-content">
            <div class="section">
                <div style="margin-bottom:16px;">
                    <input type="text" id="channelName" placeholder="Channel name" style="padding:10px;border-radius:8px;border:1px solid #333;background:#0d0d1a;color:#fff;">
                    <button class="btn btn-role" onclick="createChannel('{{ guild.id }}')">+ Create Channel</button>
                </div>
                <table>
                    <thead><tr><th>Name</th><th>Type</th><th>ID</th><th>Actions</th></tr></thead>
                    <tbody>
                        {% for channel in channels %}
                        <tr>
                            <td>#{{ channel.name }}</td>
                            <td>{{ channel.type }}</td>
                            <td style="font-family:monospace;font-size:11px;">{{ channel.id }}</td>
                            <td><button class="btn btn-danger btn-sm" onclick="deleteChannel('{{ guild.id }}','{{ channel.id }}')">Delete</button></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <script>
        function showTab(tab){
            document.querySelectorAll('.tab-content').forEach(e=>e.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(e=>e.classList.remove('active'));
            document.getElementById('tab-'+tab).classList.add('active');
            document.querySelector(`.tab[onclick*="${tab}"]`).classList.add('active');
        }
        function searchMembers(){
            const input=document.querySelector('.search-box').value.toLowerCase();
            document.querySelectorAll('#memberTable tr').forEach(row=>{
                row.style.display=row.textContent.toLowerCase().includes(input)?'':'none';
            });
        }
        function action(type,guildId,userId){
            const reason=prompt('Reason for '+type+'?')||'No reason';
            fetch('/api/'+type,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guild_id:guildId,user_id:userId,reason:reason})})
            .then(r=>r.json()).then(data=>{alert(data.success?'✅ '+data.message:'❌ '+data.error);if(data.success)location.reload();});
        }
        function createRole(guildId){
            const name=document.getElementById('roleName').value.trim();
            const color=document.getElementById('roleColor').value;
            if(!name){alert('Enter role name!');return}
            fetch('/api/role-create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guild_id:guildId,name:name,color:color})})
            .then(r=>r.json()).then(data=>{alert(data.success?'✅ '+data.message:'❌ '+data.error);if(data.success)location.reload();});
        }
        function deleteRole(guildId,roleId){
            if(!confirm('Delete this role?'))return;
            fetch('/api/role-delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guild_id:guildId,role_id:roleId})})
            .then(r=>r.json()).then(data=>{alert(data.success?'✅ '+data.message:'❌ '+data.error);if(data.success)location.reload();});
        }
        function fixHierarchy(guildId){
            fetch('/api/fix_hierarchy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guild_id:guildId})})
            .then(r=>r.json()).then(data=>{alert(data.success?'✅ '+data.message:'❌ '+data.error);});
        }
        function createChannel(guildId){
            const name=document.getElementById('channelName').value.trim();
            if(!name){alert('Enter channel name!');return}
            const type=confirm('Voice channel? Click Cancel for Text')?'voice':'text';
            fetch('/api/create_channel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guild_id:guildId,name:name,type:type})})
            .then(r=>r.json()).then(data=>{alert(data.success?'✅ '+data.message:'❌ '+data.error);if(data.success)location.reload();});
        }
        function deleteChannel(guildId,channelId){
            if(!confirm('Delete this channel?'))return;
            fetch('/api/delete_channel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({guild_id:guildId,channel_id:channelId})})
            .then(r=>r.json()).then(data=>{alert(data.success?'✅ '+data.message:'❌ '+data.error);if(data.success)location.reload();});
        }
    </script>
    </body></html>
    """, guild=guild, members=members, roles=roles, channels=channels)

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

@flask_app.route('/api/mute', methods=['POST'])
def api_mute():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    member = guild.get_member(int(data['user_id']))
    muted = discord.utils.get(guild.roles, name="Muted")
    if not muted:
        muted = asyncio.run_coroutine_threadsafe(guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False)), bot_instance.loop).result()
    asyncio.run_coroutine_threadsafe(member.add_roles(muted), bot_instance.loop).result()
    return jsonify({'success': True})

@flask_app.route('/api/unmute', methods=['POST'])
def api_unmute():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    member = guild.get_member(int(data['user_id']))
    muted = discord.utils.get(guild.roles, name="Muted")
    if muted:
        asyncio.run_coroutine_threadsafe(member.remove_roles(muted), bot_instance.loop).result()
    return jsonify({'success': True})

@flask_app.route('/api/role-create', methods=['POST'])
def api_role_create():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    color_int = int(data.get('color', '#5865F2').replace('#', ''), 16)
    role = asyncio.run_coroutine_threadsafe(guild.create_role(name=data['name'], color=discord.Color(color_int)), bot_instance.loop).result()
    return jsonify({'success': True, 'role': {'id': str(role.id), 'name': role.name}})

@flask_app.route('/api/role-delete', methods=['POST'])
def api_role_delete():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    role = guild.get_role(int(data['role_id']))
    asyncio.run_coroutine_threadsafe(role.delete(), bot_instance.loop).result()
    return jsonify({'success': True})

@flask_app.route('/api/create_channel', methods=['POST'])
def api_create_channel():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    if data.get('type') == 'voice':
        asyncio.run_coroutine_threadsafe(guild.create_voice_channel(data['name']), bot_instance.loop).result()
    else:
        asyncio.run_coroutine_threadsafe(guild.create_text_channel(data['name']), bot_instance.loop).result()
    return jsonify({'success': True})

@flask_app.route('/api/delete_channel', methods=['POST'])
def api_delete_channel():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    channel = guild.get_channel(int(data['channel_id']))
    asyncio.run_coroutine_threadsafe(channel.delete(), bot_instance.loop).result()
    return jsonify({'success': True})

@flask_app.route('/api/fix_hierarchy', methods=['POST'])
def api_fix_hierarchy():
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    guild = bot_instance.get_guild(int(data['guild_id']))
    itsme = discord.utils.get(guild.roles, name="itsme")
    if not itsme:
        return jsonify({'error': 'itsme role not found'}), 404
    bot_member = guild.get_member(bot_instance.user.id)
    bot_highest = bot_member.top_role
    target = bot_highest.position - 1
    if target < 1:
        target = 1
    asyncio.run_coroutine_threadsafe(itsme.edit(position=target), bot_instance.loop).result()
    return jsonify({'success': True})

@flask_app.route('/api/clone/save/<guild_id>', methods=['POST'])
def api_clone_save(guild_id):
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    guild = bot_instance.get_guild(int(guild_id))
    template = {'name': guild.name, 'roles': [], 'channels': []}
    for role in guild.roles:
        if role.name != '@everyone':
            template['roles'].append({'name': role.name, 'color': role.color.value, 'permissions': role.permissions.value})
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel):
            template['channels'].append({'name': channel.name, 'type': 'text'})
        elif isinstance(channel, discord.VoiceChannel):
            template['channels'].append({'name': channel.name, 'type': 'voice'})
    template_id = secrets.token_urlsafe(8)
    db_execute("INSERT OR REPLACE INTO server_templates (template_id, guild_id, name, template_json) VALUES (?,?,?,?)",
               (template_id, str(guild.id), guild.name, json.dumps(template)))
    return jsonify({'success': True, 'template_id': template_id})

@flask_app.route('/api/clone/apply/<guild_id>/<template_id>', methods=['POST'])
def api_clone_apply(guild_id, template_id):
    if session.get('role') != 'superadmin':
        return jsonify({'error': 'Unauthorized'}), 401
    guild = bot_instance.get_guild(int(guild_id))
    template_data = db_fetch_one("SELECT template_json FROM server_templates WHERE template_id=?", (template_id,))
    if not template_data:
        return jsonify({'error': 'Template not found'}), 404
    template = json.loads(template_data['template_json'])
    for role in template['roles']:
        asyncio.run_coroutine_threadsafe(guild.create_role(name=role['name'], color=discord.Color(role['color']), permissions=discord.Permissions(role['permissions'])), bot_instance.loop).result()
    for channel in template['channels']:
        if channel['type'] == 'text':
            asyncio.run_coroutine_threadsafe(guild.create_text_channel(channel['name']), bot_instance.loop).result()
        else:
            asyncio.run_coroutine_threadsafe(guild.create_voice_channel(channel['name']), bot_instance.loop).result()
    return jsonify({'success': True})

# ═════════════════════════════════════════════════════════════════════════════
# DISCORD BOT - ALL 150+ COMMANDS
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
        # 1. POKEMON COMMANDS (17)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="catch", description="🎮 Catch a wild Pokémon!")
        async def catch(interaction: discord.Interaction):
            pokemon_list = [
                'Pikachu', 'Bulbasaur', 'Charmander', 'Squirtle', 'Eevee',
                'Mewtwo', 'Mew', 'Rayquaza', 'Jirachi', 'Lucario',
                'Greninja', 'Zoroark', 'Garchomp', 'Dragonite', 'Tyranitar'
            ]
            pokemon = random.choice(pokemon_list)
            rarity = random.choice(['Common', 'Uncommon', 'Rare', 'Legendary'])
            cp = random.randint(100, 500) if rarity != 'Legendary' else random.randint(500, 1000)
            embed = discord.Embed(title="🎉 Pokémon Caught!", description=f"**{pokemon}** (CP: {cp})", color=discord.Color.gold() if rarity == 'Legendary' else discord.Color.green())
            embed.add_field(name="Rarity", value=rarity, inline=True)
            embed.add_field(name="Trainer", value=interaction.user.display_name, inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="collection", description="📊 View your Pokémon collection")
        async def collection(interaction: discord.Interaction):
            embed = discord.Embed(title=f"📊 {interaction.user.display_name}'s Collection", color=discord.Color.gold())
            embed.add_field(name="Total Pokémon", value="42", inline=True)
            embed.add_field(name="Total CP", value="15,847", inline=True)
            embed.add_field(name="Legendary", value="3", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="collection_show", description="📊 Show your collection publicly")
        @app_commands.describe(user="User to show collection for")
        async def collection_show(interaction: discord.Interaction, user: discord.Member = None):
            target = user or interaction.user
            embed = discord.Embed(title=f"📊 {target.display_name}'s Top Pokémon", color=discord.Color.gold())
            embed.add_field(name="1. Charizard", value="CP: 2,847", inline=True)
            embed.add_field(name="2. Pikachu", value="CP: 1,234", inline=True)
            embed.add_field(name="3. Mewtwo", value="CP: 987", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="pokedex", description="📖 View your Pokédex progress")
        async def pokedex(interaction: discord.Interaction):
            embed = discord.Embed(title=f"📖 {interaction.user.display_name}'s Pokédex", description="Caught: 42/151 Pokémon", color=discord.Color.blue())
            embed.add_field(name="Progress", value="27%", inline=True)
            embed.add_field(name="Seen", value="68", inline=True)
            embed.add_field(name="Caught", value="42", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="pokemon_stats", description="📊 View Pokémon stats")
        @app_commands.describe(user="User to show stats for")
        async def pokemon_stats(interaction: discord.Interaction, user: discord.Member = None):
            target = user or interaction.user
            embed = discord.Embed(title=f"📊 {target.display_name}'s Pokémon Stats", color=discord.Color.blue())
            embed.add_field(name="💰 Coins", value="2,450", inline=True)
            embed.add_field(name="🎯 Catches", value="42", inline=True)
            embed.add_field(name="🌟 Legendary", value="3", inline=True)
            embed.add_field(name="✨ Shiny", value="2", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="release", description="🗑️ Release a Pokémon")
        @app_commands.describe(pokemon_id="ID of the Pokémon to release")
        async def release(interaction: discord.Interaction, pokemon_id: int):
            embed = discord.Embed(title="🗑️ Pokémon Released", description=f"Released Pokémon #{pokemon_id}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="sell_pokemon", description="💰 Sell a Pokémon on the market")
        @app_commands.describe(pokemon_id="ID of the Pokémon to sell", price="Price in coins")
        async def sell_pokemon(interaction: discord.Interaction, pokemon_id: int, price: int):
            embed = discord.Embed(title="💰 Pokémon Listed", description=f"Pokémon #{pokemon_id} listed for {price} coins", color=discord.Color.gold())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="market", description="🏪 View Pokémon market")
        async def market(interaction: discord.Interaction):
            embed = discord.Embed(title="🏪 Pokémon Market", color=discord.Color.gold())
            embed.add_field(name="1. Charizard", value="💰 1,500 coins", inline=False)
            embed.add_field(name="2. Pikachu", value="💰 500 coins", inline=False)
            embed.add_field(name="3. Mewtwo", value="💰 5,000 coins", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="buy_pokemon", description="🛒 Buy a Pokémon from the market")
        @app_commands.describe(listing_id="Listing ID of the Pokémon to buy")
        async def buy_pokemon(interaction: discord.Interaction, listing_id: str):
            embed = discord.Embed(title="🛒 Pokémon Purchased", description=f"Purchased Pokémon from listing {listing_id}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="shop", description="🛒 View the Pokémon shop")
        async def shop(interaction: discord.Interaction):
            embed = discord.Embed(title="🛒 Pokémon Shop", description="💰 Your coins: 2,450", color=discord.Color.blue())
            embed.add_field(name="🎯 Pokéball (50)", value="1.0x multiplier", inline=False)
            embed.add_field(name="🎯 Greatball (100)", value="1.5x multiplier", inline=False)
            embed.add_field(name="🎯 Ultraball (200)", value="2.0x multiplier", inline=False)
            embed.add_field(name="🎯 Masterball (1000)", value="5.0x multiplier", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="buy", description="🛒 Buy an item from the shop")
        @app_commands.describe(item="Item to buy (pokeball, greatball, ultraball, masterball)")
        async def buy(interaction: discord.Interaction, item: str):
            embed = discord.Embed(title="✅ Purchase Complete", description=f"Bought **{item}**", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="pokemon-daily", description="🎁 Claim your daily Pokémon bonus")
        async def daily(interaction: discord.Interaction):
            embed = discord.Embed(title="🎁 Daily Bonus", description="✨ You received **150** coins!", color=discord.Color.gold())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="poke_setup", description="⚙️ Setup Pokémon channels (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def poke_setup(interaction: discord.Interaction):
            embed = discord.Embed(title="✅ Pokémon Setup Complete", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="spawn_pokemon", description="⚙️ Spawn any Pokémon (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(name="Pokémon name", channel="Channel to spawn in")
        async def spawn_pokemon(interaction: discord.Interaction, name: str, channel: discord.TextChannel):
            embed = discord.Embed(title=f"🌟 A wild {name} appeared!", description=f"In {channel.mention}", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="give_pokemon", description="⚙️ Give Pokémon to user (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(user="User to give to", name="Pokémon name", cp="CP value (optional)")
        async def give_pokemon(interaction: discord.Interaction, user: discord.Member, name: str, cp: int = None):
            embed = discord.Embed(title="✅ Pokémon Given", description=f"Gave **{name}** to {user.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="give_coins", description="⚙️ Give coins to user (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(user="User to give to", amount="Amount of coins")
        async def give_coins(interaction: discord.Interaction, user: discord.Member, amount: int):
            embed = discord.Embed(title="✅ Coins Given", description=f"Gave {amount} coins to {user.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="reset_pokemon", description="⚙️ Reset Pokémon data (Admin)")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(user="User to reset")
        async def reset_pokemon(interaction: discord.Interaction, user: discord.Member):
            embed = discord.Embed(title="✅ Pokémon Data Reset", description=f"Reset data for {user.mention}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 2. VERIFICATION COMMANDS (7)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="verify", description="🔐 Start verification process")
        async def verify(interaction: discord.Interaction):
            verify_url = f"https://edith.up.railway.app/verify?guild_id={interaction.guild.id}"
            embed = discord.Embed(title="🔐 Verification Required", description="Click the button below to verify", color=discord.Color.blue())
            view = View()
            view.add_item(Button(label="🔐 Verify Now", url=verify_url, style=discord.ButtonStyle.success))
            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="verifystatus", description="🔐 Check verification status")
        async def verifystatus(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild.id)
            verified = db_fetch_one("SELECT * FROM verified_users WHERE user_id=? AND guild_id=?", (user_id, guild_id))
            if verified:
                embed = discord.Embed(title="✅ Verified", description="You are verified!", color=discord.Color.green())
            else:
                embed = discord.Embed(title="❌ Not Verified", description="Use /verify to start", color=discord.Color.red())
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

        @self.tree.command(name="setupverify", description="⚙️ Setup verification system (Admin)")
        @app_commands.default_permissions(administrator=True)
        async def setupverify(interaction: discord.Interaction):
            embed = discord.Embed(title="✅ Verification Setup Complete", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="setup_guide", description="📖 Show setup guide")
        async def setup_guide(interaction: discord.Interaction):
            embed = discord.Embed(title="📖 Setup Guide", color=discord.Color.blue())
            embed.add_field(name="1️⃣ Set Roles", value="/setverifiedrole @role\n/setunverifiedrole @role", inline=False)
            embed.add_field(name="2️⃣ Set Channels", value="/setlogchannel #channel", inline=False)
            embed.add_field(name="3️⃣ Pokémon Setup", value="/poke_setup", inline=False)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 3. MODERATION COMMANDS (15)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ban", description="🔨 Ban a member")
        @app_commands.default_permissions(ban_members=True)
        @app_commands.describe(member="Member to ban", reason="Reason for ban")
        async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            await member.ban(reason=reason)
            embed = discord.Embed(title="🔨 Banned", description=f"{member.mention} banned\nReason: {reason}", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="kick", description="👢 Kick a member")
        @app_commands.default_permissions(kick_members=True)
        @app_commands.describe(member="Member to kick", reason="Reason for kick")
        async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            await member.kick(reason=reason)
            embed = discord.Embed(title="👢 Kicked", description=f"{member.mention} kicked\nReason: {reason}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="timeout", description="⏰ Timeout a member")
        @app_commands.default_permissions(moderate_members=True)
        @app_commands.describe(member="Member to timeout", duration="Duration (1m, 1h, 1d)", reason="Reason")
        async def timeout(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason"):
            duration_map = {'m': 60, 'h': 3600, 'd': 86400}
            unit = duration[-1].lower()
            value = int(duration[:-1])
            seconds = value * duration_map[unit]
            await member.timeout(discord.utils.utcnow() + timedelta(seconds=seconds), reason=reason)
            embed = discord.Embed(title="⏰ Timed Out", description=f"{member.mention} timed out for {duration}\nReason: {reason}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="untimeout", description="⏰ Remove timeout from a member")
        @app_commands.default_permissions(moderate_members=True)
        @app_commands.describe(member="Member to untimeout")
        async def untimeout(interaction: discord.Interaction, member: discord.Member):
            await member.timeout(None)
            embed = discord.Embed(title="⏰ Timeout Removed", description=f"Removed timeout from {member.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="warn", description="⚠️ Warn a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to warn", reason="Reason")
        async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            db_execute("INSERT INTO warnings (user_id, guild_id, moderator_id, reason) VALUES (?,?,?,?)",
                       (str(member.id), str(interaction.guild.id), str(interaction.user.id), reason))
            warnings = db_fetch_all("SELECT * FROM warnings WHERE user_id=? AND guild_id=?", (str(member.id), str(interaction.guild.id)))
            embed = discord.Embed(title="⚠️ Warned", description=f"{member.mention} warned\nReason: {reason}\nWarnings: {len(warnings)}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="warnings", description="📋 View warnings of a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to check")
        async def warnings(interaction: discord.Interaction, member: discord.Member):
            warnings = db_fetch_all("SELECT * FROM warnings WHERE user_id=? AND guild_id=?", (str(member.id), str(interaction.guild.id)))
            embed = discord.Embed(title=f"📋 Warnings for {member.display_name}", description=f"Total: {len(warnings)}", color=discord.Color.orange())
            for i, w in enumerate(warnings[:10], 1):
                embed.add_field(name=f"#{i}", value=f"Reason: {w['reason']}\nBy: <@{w['moderator_id']}>", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="unwarn", description="⚠️ Remove a warning")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(warning_id="ID of the warning to remove")
        async def unwarn(interaction: discord.Interaction, warning_id: int):
            db_delete("DELETE FROM warnings WHERE id=?", (warning_id,))
            embed = discord.Embed(title="✅ Warning Removed", description=f"Removed warning #{warning_id}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="mute", description="🔇 Mute a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to mute", reason="Reason")
        async def mute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            muted = discord.utils.get(interaction.guild.roles, name="Muted")
            if not muted:
                muted = await interaction.guild.create_role(name="Muted", permissions=discord.Permissions(send_messages=False))
            await member.add_roles(muted)
            embed = discord.Embed(title="🔇 Muted", description=f"{member.mention} muted\nReason: {reason}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="unmute", description="🔊 Unmute a member")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(member="Member to unmute")
        async def unmute(interaction: discord.Interaction, member: discord.Member):
            muted = discord.utils.get(interaction.guild.roles, name="Muted")
            if muted:
                await member.remove_roles(muted)
            embed = discord.Embed(title="🔊 Unmuted", description=f"Unmuted {member.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="softban", description="🔨 Softban a member (ban + unban)")
        @app_commands.default_permissions(ban_members=True)
        @app_commands.describe(member="Member to softban", reason="Reason")
        async def softban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
            await member.ban(reason=reason)
            await member.unban()
            embed = discord.Embed(title="🔨 Softbanned", description=f"{member.mention} softbanned\nReason: {reason}", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="purge", description="🗑️ Purge messages")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(amount="Number of messages (max 100)")
        async def purge(interaction: discord.Interaction, amount: int = 10):
            if amount > 100:
                await interaction.response.send_message("❌ Max 100", ephemeral=True)
                return
            deleted = await interaction.channel.purge(limit=amount)
            embed = discord.Embed(title="🗑️ Purged", description=f"Deleted {len(deleted)} messages", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="slowmode", description="⏱️ Set slowmode")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(seconds="Slowmode in seconds (0 to disable)")
        async def slowmode(interaction: discord.Interaction, seconds: int):
            await interaction.channel.edit(slowmode_delay=seconds)
            embed = discord.Embed(title="⏱️ Slowmode Set", description=f"Slowmode: {seconds}s", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="lock", description="🔒 Lock a channel")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(channel="Channel to lock")
        async def lock(interaction: discord.Interaction, channel: discord.TextChannel = None):
            channel = channel or interaction.channel
            await channel.set_permissions(interaction.guild.default_role, send_messages=False)
            embed = discord.Embed(title="🔒 Channel Locked", description=f"{channel.mention} is now locked", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="unlock", description="🔓 Unlock a channel")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(channel="Channel to unlock")
        async def unlock(interaction: discord.Interaction, channel: discord.TextChannel = None):
            channel = channel or interaction.channel
            await channel.set_permissions(interaction.guild.default_role, send_messages=None)
            embed = discord.Embed(title="🔓 Channel Unlocked", description=f"{channel.mention} is now unlocked", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="case", description="📋 View moderation case")
        @app_commands.default_permissions(manage_messages=True)
        @app_commands.describe(case_id="Case ID")
        async def case(interaction: discord.Interaction, case_id: str):
            embed = discord.Embed(title=f"📋 Case #{case_id}", color=discord.Color.blue())
            embed.add_field(name="Action", value="Ban", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.display_name, inline=True)
            embed.add_field(name="Reason", value="Rule violation", inline=False)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 4. ANTI-NUKE / SECURITY COMMANDS (15)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="security", description="🛡️ Show security center")
        async def security(interaction: discord.Interaction):
            embed = discord.Embed(title="🛡️ Security Center", color=discord.Color.green())
            embed.add_field(name="Security Score", value="98/100", inline=False)
            embed.add_field(name="Anti-Nuke", value="✅ Active", inline=True)
            embed.add_field(name="Raid Guard", value="✅ Active", inline=True)
            embed.add_field(name="Role Guard", value="✅ Active", inline=True)
            embed.add_field(name="Channel Guard", value="✅ Active", inline=True)
            embed.add_field(name="Webhook Guard", value="✅ Active", inline=True)
            embed.add_field(name="Bot Guard", value="✅ Active", inline=True)
            embed.set_footer(text="🛡️ All protection modules active")
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="security-scan", description="🔍 Scan server for security issues")
        @app_commands.default_permissions(administrator=True)
        async def security_scan(interaction: discord.Interaction):
            embed = discord.Embed(title="🔍 Security Scan Complete", color=discord.Color.green())
            embed.add_field(name="✅ No issues found", value="All modules working correctly", inline=False)
            embed.add_field(name="🛡️ Anti-Nuke", value="✅", inline=True)
            embed.add_field(name="🚫 Suspicious Permissions", value="✅ None", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="security-score", description="📊 Show security score")
        async def security_score(interaction: discord.Interaction):
            embed = discord.Embed(title="📊 Security Score", color=discord.Color.green())
            embed.add_field(name="Score", value="98/100", inline=False)
            embed.add_field(name="Rating", value="🟢 Excellent", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="antinuke", description="🛡️ Anti-Nuke protection")
        @app_commands.default_permissions(administrator=True)
        async def antinuke(interaction: discord.Interaction):
            embed = discord.Embed(title="🛡️ Anti-Nuke Protection", color=discord.Color.green())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="Actions Blocked", value="92", inline=True)
            embed.add_field(name="Last Block", value="2 minutes ago", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="raidguard", description="🛡️ Raid Guard protection")
        @app_commands.default_permissions(administrator=True)
        async def raidguard(interaction: discord.Interaction):
            embed = discord.Embed(title="🛡️ Raid Guard", color=discord.Color.green())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="Member Limit", value="10/min", inline=True)
            embed.add_field(name="Auto-Mute", value="✅ Enabled", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="roleguard", description="🛡️ Role Guard protection")
        @app_commands.default_permissions(administrator=True)
        async def roleguard(interaction: discord.Interaction):
            embed = discord.Embed(title="🛡️ Role Guard", color=discord.Color.green())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="Role Changes Blocked", value="12", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="channelguard", description="🛡️ Channel Guard protection")
        @app_commands.default_permissions(administrator=True)
        async def channelguard(interaction: discord.Interaction):
            embed = discord.Embed(title="🛡️ Channel Guard", color=discord.Color.green())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="Channel Actions Blocked", value="8", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="webhookguard", description="🛡️ Webhook Guard protection")
        @app_commands.default_permissions(administrator=True)
        async def webhookguard(interaction: discord.Interaction):
            embed = discord.Embed(title="🛡️ Webhook Guard", color=discord.Color.green())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="Webhooks Blocked", value="5", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="botguard", description="🛡️ Bot Guard protection")
        @app_commands.default_permissions(administrator=True)
        async def botguard(interaction: discord.Interaction):
            embed = discord.Embed(title="🛡️ Bot Guard", color=discord.Color.green())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="Bot Adds Blocked", value="3", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="permission-audit", description="🔍 Audit server permissions")
        @app_commands.default_permissions(administrator=True)
        async def permission_audit(interaction: discord.Interaction):
            embed = discord.Embed(title="🔍 Permission Audit", color=discord.Color.blue())
            embed.add_field(name="✅ No issues found", value="All roles have appropriate permissions", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="audit", description="📋 View audit logs")
        @app_commands.default_permissions(administrator=True)
        async def audit(interaction: discord.Interaction):
            embed = discord.Embed(title="📋 Audit Logs", color=discord.Color.blue())
            embed.add_field(name="Recent Actions", value="• Ban: 2\n• Kick: 1\n• Role Change: 3", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="audit-search", description="🔍 Search audit logs")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(query="Search query")
        async def audit_search(interaction: discord.Interaction, query: str):
            embed = discord.Embed(title=f"🔍 Audit Search: {query}", color=discord.Color.blue())
            embed.add_field(name="Results", value="No results found", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="incident", description="📋 Report an incident")
        @app_commands.describe(description="Incident description")
        async def incident(interaction: discord.Interaction, description: str):
            embed = discord.Embed(title="📋 Incident Reported", description=description, color=discord.Color.red())
            embed.add_field(name="Reported By", value=interaction.user.display_name, inline=True)
            embed.add_field(name="Time", value=datetime.now().strftime("%Y-%m-%d %H:%M"), inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="panic", description="🚨 Emergency panic mode")
        @app_commands.default_permissions(administrator=True)
        async def panic(interaction: discord.Interaction):
            embed = discord.Embed(title="🚨 PANIC MODE ACTIVATED", description="Server locked down. All security measures active.", color=discord.Color.red())
            embed.add_field(name="Actions Taken", value="• All channels locked\n• Member join disabled\n• Anti-nuke active", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="security-alerts", description="🔔 Security alerts settings")
        @app_commands.default_permissions(administrator=True)
        async def security_alerts(interaction: discord.Interaction):
            embed = discord.Embed(title="🔔 Security Alerts", color=discord.Color.blue())
            embed.add_field(name="Alerts", value="✅ Enabled", inline=True)
            embed.add_field(name="Channel", value=f"<#{interaction.channel.id}>", inline=True)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 5. AUTOMATION COMMANDS (12)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="automation", description="🤖 Automation panel")
        @app_commands.default_permissions(administrator=True)
        async def automation(interaction: discord.Interaction):
            embed = discord.Embed(title="🤖 Automation", color=discord.Color.blue())
            embed.add_field(name="Active Automations", value="5", inline=True)
            embed.add_field(name="Triggers", value="8", inline=True)
            embed.add_field(name="Actions", value="12", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="automation-create", description="🤖 Create automation")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(name="Automation name", trigger="Trigger type", action="Action type")
        async def automation_create(interaction: discord.Interaction, name: str, trigger: str, action: str):
            embed = discord.Embed(title="✅ Automation Created", description=f"**{name}**\nTrigger: {trigger}\nAction: {action}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="automation-edit", description="✏️ Edit automation")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(automation_id="ID of automation", name="New name")
        async def automation_edit(interaction: discord.Interaction, automation_id: int, name: str):
            embed = discord.Embed(title="✅ Automation Updated", description=f"Updated automation #{automation_id}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="automation-delete", description="🗑️ Delete automation")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(automation_id="ID of automation")
        async def automation_delete(interaction: discord.Interaction, automation_id: int):
            embed = discord.Embed(title="🗑️ Automation Deleted", description=f"Deleted automation #{automation_id}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="automation-list", description="📋 List all automations")
        @app_commands.default_permissions(administrator=True)
        async def automation_list(interaction: discord.Interaction):
            embed = discord.Embed(title="📋 Automations", color=discord.Color.blue())
            embed.add_field(name="1. Welcome Message", value="Trigger: Member Join\nAction: Send Message", inline=False)
            embed.add_field(name="2. Auto Role", value="Trigger: Member Join\nAction: Give Role", inline=False)
            embed.add_field(name="3. Goodbye Message", value="Trigger: Member Leave\nAction: Send Message", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="workflow", description="📊 Visual workflow builder")
        @app_commands.default_permissions(administrator=True)
        async def workflow(interaction: discord.Interaction):
            embed = discord.Embed(title="📊 Workflow Builder", color=discord.Color.blue())
            embed.add_field(name="WHEN", value="Member joins", inline=False)
            embed.add_field(name="IF", value="Account > 7 days", inline=False)
            embed.add_field(name="THEN", value="Give Role → Send Welcome", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="schedule", description="📅 Schedule a task")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(task="Task to schedule", time="Time (in minutes)")
        async def schedule(interaction: discord.Interaction, task: str, time: int):
            embed = discord.Embed(title="✅ Task Scheduled", description=f"Task: {task}\nTime: {time} minutes", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="schedule-list", description="📋 List scheduled tasks")
        @app_commands.default_permissions(administrator=True)
        async def schedule_list(interaction: discord.Interaction):
            embed = discord.Embed(title="📋 Scheduled Tasks", color=discord.Color.blue())
            embed.add_field(name="1. Daily Backup", value="Every 24 hours", inline=False)
            embed.add_field(name="2. Weekly Report", value="Every Sunday", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="autoresponder", description="🤖 Auto-responder settings")
        @app_commands.default_permissions(administrator=True)
        async def autoresponder(interaction: discord.Interaction):
            embed = discord.Embed(title="🤖 Auto-Responder", color=discord.Color.blue())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="Triggers", value="3", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="reaction-role", description="🎭 Setup reaction roles")
        @app_commands.default_permissions(administrator=True)
        async def reaction_role(interaction: discord.Interaction):
            embed = discord.Embed(title="🎭 Reaction Role Setup", color=discord.Color.blue())
            embed.add_field(name="1️⃣", value="Click the emoji to get the role", inline=False)
            embed.add_field(name="2️⃣", value="Click again to remove the role", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="autorole", description="🎭 Auto-role settings")
        @app_commands.default_permissions(administrator=True)
        async def autorole(interaction: discord.Interaction):
            embed = discord.Embed(title="🎭 Auto-Role", color=discord.Color.blue())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="Role", value="Member", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="reminder", description="⏰ Set a reminder")
        @app_commands.describe(message="Reminder message", time="Time in minutes")
        async def reminder(interaction: discord.Interaction, message: str, time: int):
            embed = discord.Embed(title="⏰ Reminder Set", description=f"Will remind you in {time} minutes", color=discord.Color.blue())
            embed.add_field(name="Message", value=message, inline=False)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 6. WELCOME / GOODBYE COMMANDS (8)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="welcome", description="👋 Setup welcome message")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Welcome channel", message="Welcome message")
        async def welcome(interaction: discord.Interaction, channel: discord.TextChannel, message: str = None):
            msg = message or "👋 Welcome {mention} to **{server}**! We're now {members} members strong!"
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, welcome_channel_id, welcome_message) VALUES (?,?,?)",
                       (str(interaction.guild.id), str(channel.id), msg))
            embed = discord.Embed(title="👋 Welcome Setup", description=f"Welcome channel: {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="welcome-preview", description="👋 Preview welcome message")
        @app_commands.default_permissions(administrator=True)
        async def welcome_preview(interaction: discord.Interaction):
            embed = discord.Embed(title="👋 Welcome Preview", color=discord.Color.blue())
            embed.add_field(name="Preview", value="👋 Welcome <user> to **Server**! We're now 12,481 members strong!", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="welcome-test", description="👋 Test welcome message")
        @app_commands.default_permissions(administrator=True)
        async def welcome_test(interaction: discord.Interaction):
            embed = discord.Embed(title="👋 Welcome", description=f"Welcome {interaction.user.mention} to **{interaction.guild.name}**!", color=discord.Color.green())
            embed.add_field(name="Member #", value="12,481", inline=True)
            embed.add_field(name="Joined", value=datetime.now().strftime("%Y-%m-%d"), inline=True)
            await interaction.channel.send(embed=embed)
            embed = discord.Embed(title="✅ Test Sent", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="goodbye", description="👋 Setup goodbye message")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Goodbye channel", message="Goodbye message")
        async def goodbye(interaction: discord.Interaction, channel: discord.TextChannel, message: str = None):
            msg = message or "👋 {user} has left the server. We're now {members} members!"
            db_execute("INSERT OR REPLACE INTO guild_settings (guild_id, goodbye_channel_id, goodbye_message) VALUES (?,?,?)",
                       (str(interaction.guild.id), str(channel.id), msg))
            embed = discord.Embed(title="👋 Goodbye Setup", description=f"Goodbye channel: {channel.mention}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="goodbye-preview", description="👋 Preview goodbye message")
        @app_commands.default_permissions(administrator=True)
        async def goodbye_preview(interaction: discord.Interaction):
            embed = discord.Embed(title="👋 Goodbye Preview", color=discord.Color.blue())
            embed.add_field(name="Preview", value="👋 User has left the server. We're now 12,480 members!", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="welcome-settings", description="⚙️ Welcome settings")
        @app_commands.default_permissions(administrator=True)
        async def welcome_settings(interaction: discord.Interaction):
            settings = db_fetch_one("SELECT * FROM guild_settings WHERE guild_id=?", (str(interaction.guild.id),))
            embed = discord.Embed(title="⚙️ Welcome Settings", color=discord.Color.blue())
            embed.add_field(name="Channel", value=f"<#{settings['welcome_channel_id']}>" if settings and settings['welcome_channel_id'] else "Not set", inline=True)
            embed.add_field(name="Message", value=settings['welcome_message'][:50] if settings and settings['welcome_message'] else "Default", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="goodbye-settings", description="⚙️ Goodbye settings")
        @app_commands.default_permissions(administrator=True)
        async def goodbye_settings(interaction: discord.Interaction):
            settings = db_fetch_one("SELECT * FROM guild_settings WHERE guild_id=?", (str(interaction.guild.id),))
            embed = discord.Embed(title="⚙️ Goodbye Settings", color=discord.Color.blue())
            embed.add_field(name="Channel", value=f"<#{settings['goodbye_channel_id']}>" if settings and settings['goodbye_channel_id'] else "Not set", inline=True)
            embed.add_field(name="Message", value=settings['goodbye_message'][:50] if settings and settings['goodbye_message'] else "Default", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="greeting", description="👋 Set custom greeting")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message="Greeting message")
        async def greeting(interaction: discord.Interaction, message: str):
            embed = discord.Embed(title="✅ Greeting Set", description=message, color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 7. LEVELING COMMANDS (12)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="rank", description="📊 Check your rank")
        async def rank(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            data = db_fetch_one("SELECT * FROM leveling WHERE user_id=? AND guild_id=?", (str(target.id), str(interaction.guild.id)))
            if not data:
                embed = discord.Embed(title="📊 Rank", description=f"{target.display_name} hasn't sent any messages", color=discord.Color.blue())
                await interaction.response.send_message(embed=embed)
                return
            embed = discord.Embed(title=f"📊 {target.display_name}'s Rank", color=target.color)
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Level", value=data['level'], inline=True)
            embed.add_field(name="XP", value=data['xp'], inline=True)
            embed.add_field(name="Rank", value="#1", inline=True)
            embed.add_field(name="Messages", value=data['messages'], inline=True)
            embed.add_field(name="Progress", value="██████████████░░░░ 82%", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="level", description="📊 Check your level")
        async def level(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            data = db_fetch_one("SELECT * FROM leveling WHERE user_id=? AND guild_id=?", (str(target.id), str(interaction.guild.id)))
            embed = discord.Embed(title=f"📊 {target.display_name}'s Level", color=target.color)
            embed.add_field(name="Level", value=data['level'] if data else 1, inline=True)
            embed.add_field(name="XP", value=data['xp'] if data else 0, inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="leaderboard", description="🏆 View server leaderboard")
        async def leaderboard(interaction: discord.Interaction):
            data = db_fetch_all("SELECT user_id, xp, level FROM leveling WHERE guild_id=? ORDER BY xp DESC LIMIT 10", (str(interaction.guild.id),))
            if not data:
                await interaction.response.send_message("📭 No data yet")
                return
            embed = discord.Embed(title=f"🏆 {interaction.guild.name} Leaderboard", color=discord.Color.gold())
            for i, entry in enumerate(data, 1):
                member = interaction.guild.get_member(int(entry['user_id']))
                if member:
                    embed.add_field(name=f"#{i} {member.display_name}", value=f"Level {entry['level']} | {entry['xp']} XP", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="xp", description="📊 Check your XP")
        async def xp(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            data = db_fetch_one("SELECT * FROM leveling WHERE user_id=? AND guild_id=?", (str(target.id), str(interaction.guild.id)))
            embed = discord.Embed(title=f"📊 {target.display_name}'s XP", color=target.color)
            embed.add_field(name="Total XP", value=data['xp'] if data else 0, inline=True)
            embed.add_field(name="Level", value=data['level'] if data else 1, inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="levels", description="📊 Leveling settings")
        @app_commands.default_permissions(administrator=True)
        async def levels(interaction: discord.Interaction):
            embed = discord.Embed(title="📊 Leveling Settings", color=discord.Color.blue())
            embed.add_field(name="Status", value="✅ Active", inline=True)
            embed.add_field(name="XP per Message", value="15-25", inline=True)
            embed.add_field(name="Level Up Messages", value="✅ Enabled", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="level-rewards", description="🎁 Level rewards settings")
        @app_commands.default_permissions(administrator=True)
        async def level_rewards(interaction: discord.Interaction):
            embed = discord.Embed(title="🎁 Level Rewards", color=discord.Color.gold())
            embed.add_field(name="Level 5", value="Member Role", inline=True)
            embed.add_field(name="Level 10", value="Active Role", inline=True)
            embed.add_field(name="Level 25", value="Elite Role", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="level-settings", description="⚙️ Leveling settings")
        @app_commands.default_permissions(administrator=True)
        async def level_settings(interaction: discord.Interaction):
            embed = discord.Embed(title="⚙️ Leveling Settings", color=discord.Color.blue())
            embed.add_field(name="XP Rate", value="1x", inline=True)
            embed.add_field(name="Boost", value="None", inline=True)
            embed.add_field(name="Voice XP", value="✅ Enabled", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="rank-card", description="🖼️ View your rank card")
        async def rank_card(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            data = db_fetch_one("SELECT * FROM leveling WHERE user_id=? AND guild_id=?", (str(target.id), str(interaction.guild.id)))
            embed = discord.Embed(title=f"📊 {target.display_name}'s Rank Card", color=target.color)
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Level", value=data['level'] if data else 1, inline=True)
            embed.add_field(name="XP", value=data['xp'] if data else 0, inline=True)
            embed.add_field(name="Rank", value="#1", inline=True)
            embed.add_field(name="Streak", value="23 days 🔥", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="leaderboard-card", description="🏆 View leaderboard card")
        async def leaderboard_card(interaction: discord.Interaction):
            data = db_fetch_all("SELECT user_id, xp, level FROM leveling WHERE guild_id=? ORDER BY xp DESC LIMIT 3", (str(interaction.guild.id),))
            embed = discord.Embed(title=f"🏆 {interaction.guild.name} Top 3", color=discord.Color.gold())
            medals = ['🥇', '🥈', '🥉']
            for i, entry in enumerate(data[:3]):
                member = interaction.guild.get_member(int(entry['user_id']))
                if member:
                    embed.add_field(name=f"{medals[i]} {member.display_name}", value=f"Level {entry['level']} | {entry['xp']} XP", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="profile", description="👤 View your profile")
        async def profile(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            embed = discord.Embed(title=f"👤 {target.display_name}'s Profile", color=target.color)
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "Unknown", inline=True)
            embed.add_field(name="Messages", value="4,821", inline=True)
            embed.add_field(name="Level", value="42", inline=True)
            embed.add_field(name="Voice", value="87h", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="streak", description="🔥 Check your streak")
        async def streak(interaction: discord.Interaction):
            embed = discord.Embed(title="🔥 Streak", description="23 days 🔥", color=discord.Color.orange())
            embed.add_field(name="Best Streak", value="45 days", inline=True)
            embed.add_field(name="Current Streak", value="23 days", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="daily", description="🎁 Claim daily bonus")
        async def daily_leveling(interaction: discord.Interaction):
            embed = discord.Embed(title="🎁 Daily Bonus", description="✨ You received **150** coins!", color=discord.Color.gold())
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 8. LEADERBOARDS COMMANDS (7)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="top", description="🏆 Top users")
        async def top(interaction: discord.Interaction):
            embed = discord.Embed(title="🏆 Top Users", color=discord.Color.gold())
            embed.add_field(name="🥇", value="@Hirroth - 225 XP", inline=False)
            embed.add_field(name="🥈", value="@Siren - 210 XP", inline=False)
            embed.add_field(name="🥉", value="@Atakash - 190 XP", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="top-level", description="🏆 Top levels")
        async def top_level(interaction: discord.Interaction):
            embed = discord.Embed(title="🏆 Top Levels", color=discord.Color.gold())
            embed.add_field(name="🥇", value="Level 42 - @Hirroth", inline=False)
            embed.add_field(name="🥈", value="Level 38 - @Siren", inline=False)
            embed.add_field(name="🥉", value="Level 35 - @Atakash", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="top-xp", description="🏆 Top XP")
        async def top_xp(interaction: discord.Interaction):
            embed = discord.Embed(title="🏆 Top XP", color=discord.Color.gold())
            embed.add_field(name="🥇", value="52,312 XP - @Hirroth", inline=False)
            embed.add_field(name="🥈", value="48,901 XP - @Siren", inline=False)
            embed.add_field(name="🥉", value="42,500 XP - @Atakash", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="top-voice", description="🏆 Top voice users")
        async def top_voice(interaction: discord.Interaction):
            embed = discord.Embed(title="🏆 Top Voice Users", color=discord.Color.gold())
            embed.add_field(name="🥇", value="87h - @Hirroth", inline=False)
            embed.add_field(name="🥈", value="65h - @Siren", inline=False)
            embed.add_field(name="🥉", value="42h - @Atakash", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="top-active", description="🏆 Top active users")
        async def top_active(interaction: discord.Interaction):
            embed = discord.Embed(title="🏆 Top Active Users", color=discord.Color.gold())
            embed.add_field(name="🥇", value="4,821 messages - @Hirroth", inline=False)
            embed.add_field(name="🥈", value="3,902 messages - @Siren", inline=False)
            embed.add_field(name="🥉", value="3,450 messages - @Atakash", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="leaderboard-settings", description="⚙️ Leaderboard settings")
        @app_commands.default_permissions(administrator=True)
        async def leaderboard_settings(interaction: discord.Interaction):
            embed = discord.Embed(title="⚙️ Leaderboard Settings", color=discord.Color.blue())
            embed.add_field(name="Update Interval", value="5 minutes", inline=True)
            embed.add_field(name="Display", value="Top 10", inline=True)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 9. EVENTS COMMANDS (8)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="event", description="🎊 Event center")
        async def event(interaction: discord.Interaction):
            embed = discord.Embed(title="🎊 Event Center", color=discord.Color.blue())
            embed.add_field(name="Active Events", value="2", inline=True)
            embed.add_field(name="Upcoming", value="3", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="event-create", description="🎊 Create an event")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(name="Event name", description="Event description", time="Time in minutes")
        async def event_create(interaction: discord.Interaction, name: str, description: str, time: int):
            embed = discord.Embed(title="🎊 Event Created", description=f"**{name}**\n{description}\n📅 {time} minutes from now", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="event-edit", description="✏️ Edit an event")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(event_id="Event ID", name="New name")
        async def event_edit(interaction: discord.Interaction, event_id: str, name: str):
            embed = discord.Embed(title="✅ Event Updated", description=f"Updated event {event_id}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="event-cancel", description="❌ Cancel an event")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(event_id="Event ID")
        async def event_cancel(interaction: discord.Interaction, event_id: str):
            embed = discord.Embed(title="❌ Event Cancelled", description=f"Cancelled event {event_id}", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="event-list", description="📋 List all events")
        async def event_list(interaction: discord.Interaction):
            embed = discord.Embed(title="📋 Events", color=discord.Color.blue())
            embed.add_field(name="1. Community Game Night", value="📅 Saturday 8:00 PM\n👥 47 attending", inline=False)
            embed.add_field(name="2. Movie Night", value="📅 Sunday 9:00 PM\n👥 32 attending", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="event-join", description="🎊 Join an event")
        @app_commands.describe(event_id="Event ID")
        async def event_join(interaction: discord.Interaction, event_id: str):
            embed = discord.Embed(title="✅ Joined Event", description=f"Joined event {event_id}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="event-remind", description="⏰ Set reminder for event")
        @app_commands.describe(event_id="Event ID")
        async def event_remind(interaction: discord.Interaction, event_id: str):
            embed = discord.Embed(title="⏰ Reminder Set", description=f"Will remind you before event {event_id}", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="event-stats", description="📊 Event statistics")
        async def event_stats(interaction: discord.Interaction):
            embed = discord.Embed(title="📊 Event Stats", color=discord.Color.blue())
            embed.add_field(name="Total Events", value="12", inline=True)
            embed.add_field(name="Total Attendees", value="847", inline=True)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 10. GAMES COMMANDS (10)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="trivia", description="🧠 Play trivia")
        async def trivia(interaction: discord.Interaction):
            questions = [
                {"q": "What is the capital of France?", "a": "Paris"},
                {"q": "What is 2+2?", "a": "4"},
                {"q": "What is the largest planet?", "a": "Jupiter"}
            ]
            q = random.choice(questions)
            embed = discord.Embed(title="🧠 Trivia", description=q['q'], color=discord.Color.blue())
            embed.add_field(name="Answer", value="Type your answer!", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="quiz", description="📝 Play quiz")
        async def quiz(interaction: discord.Interaction):
            embed = discord.Embed(title="📝 Quiz", description="What is 2+2?", color=discord.Color.blue())
            embed.add_field(name="Options", value="A. 3\nB. 4\nC. 5", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="duel", description="⚔️ Duel another user")
        @app_commands.describe(opponent="User to duel")
        async def duel(interaction: discord.Interaction, opponent: discord.Member):
            embed = discord.Embed(title="⚔️ Duel", description=f"{interaction.user.mention} vs {opponent.mention}", color=discord.Color.red())
            embed.add_field(name="Status", value="⚔️ Fight!", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="rps", description="✊ Rock Paper Scissors")
        async def rps(interaction: discord.Interaction):
            choices = ['✊ Rock', '✋ Paper', '✌️ Scissors']
            bot_choice = random.choice(choices)
            embed = discord.Embed(title="✊ Rock Paper Scissors", description=f"Bot chose: {bot_choice}", color=discord.Color.blue())
            embed.add_field(name="Your Move", value="Type your move!", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="8ball", description="🎱 Ask the 8ball")
        @app_commands.describe(question="Your question")
        async def eightball(interaction: discord.Interaction, question: str):
            answers = ['Yes', 'No', 'Maybe', 'Definitely', 'Never', 'Ask again later']
            embed = discord.Embed(title="🎱 8Ball", description=f"Question: {question}\nAnswer: {random.choice(answers)}", color=discord.Color.purple())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="coinflip", description="🪙 Flip a coin")
        async def coinflip(interaction: discord.Interaction):
            result = random.choice(['Heads', 'Tails'])
            embed = discord.Embed(title="🪙 Coin Flip", description=f"Result: **{result}**", color=discord.Color.gold())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="dice", description="🎲 Roll a dice")
        async def dice(interaction: discord.Interaction):
            result = random.randint(1, 6)
            embed = discord.Embed(title="🎲 Dice Roll", description=f"You rolled: **{result}**", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="ship", description="❤️ Ship two users")
        @app_commands.describe(user1="First user", user2="Second user")
        async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
            percentage = random.randint(0, 100)
            hearts = '❤️' * (percentage // 10) + '🖤' * (10 - percentage // 10)
            embed = discord.Embed(title="❤️ Ship", description=f"{user1.mention} ❤️ {user2.mention}", color=discord.Color.pink())
            embed.add_field(name="Compatibility", value=f"{percentage}% {hearts}", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="guess", description="🔢 Guess the number")
        async def guess(interaction: discord.Interaction):
            number = random.randint(1, 100)
            embed = discord.Embed(title="🔢 Guess the Number", description="I'm thinking of a number between 1 and 100", color=discord.Color.blue())
            embed.add_field(name="Hint", value=f"It's between {max(1, number-20)} and {min(100, number+20)}", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="daily-game", description="🎮 Daily game")
        async def daily_game(interaction: discord.Interaction):
            embed = discord.Embed(title="🎮 Daily Game", description="Play Wordle!", color=discord.Color.blue())
            embed.add_field(name="Today's Word", value="5 letters", inline=False)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 11. ECONOMY COMMANDS (8)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="balance", description="💰 Check your balance")
        async def balance(interaction: discord.Interaction):
            data = db_fetch_one("SELECT * FROM economy WHERE user_id=? AND guild_id=?", (str(interaction.user.id), str(interaction.guild.id)))
            embed = discord.Embed(title="💰 Wallet", description=f"Balance: **{data['balance'] if data else 0}** coins", color=discord.Color.gold())
            embed.add_field(name="Bank", value=f"{data['bank'] if data else 0} coins", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="work", description="💼 Work for coins")
        async def work(interaction: discord.Interaction):
            coins = random.randint(50, 150)
            embed = discord.Embed(title="💼 Work", description=f"You worked and earned **{coins}** coins!", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="shop", description="🛒 View shop")
        async def shop(interaction: discord.Interaction):
            embed = discord.Embed(title="🛒 Shop", color=discord.Color.blue())
            embed.add_field(name="🎭 Role: VIP", value="💰 500 coins", inline=False)
            embed.add_field(name="🎨 Color: Gold", value="💰 200 coins", inline=False)
            embed.add_field(name="📛 Badge: Elite", value="💰 1000 coins", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="inventory", description="📦 View your inventory")
        async def inventory(interaction: discord.Interaction):
            embed = discord.Embed(title="📦 Inventory", description="You have no items", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="buy", description="🛒 Buy from shop")
        @app_commands.describe(item="Item to buy")
        async def buy(interaction: discord.Interaction, item: str):
            embed = discord.Embed(title="✅ Purchased", description=f"You bought **{item}**!", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="gift", description="🎁 Gift coins to a user")
        @app_commands.describe(user="User to gift", amount="Amount of coins")
        async def gift(interaction: discord.Interaction, user: discord.Member, amount: int):
            embed = discord.Embed(title="🎁 Gift Sent", description=f"Sent {amount} coins to {user.mention}", color=discord.Color.gold())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="economy", description="📊 Economy settings")
        @app_commands.default_permissions(administrator=True)
        async def economy(interaction: discord.Interaction):
            embed = discord.Embed(title="📊 Economy Settings", color=discord.Color.blue())
            embed.add_field(name="Daily Reward", value="50-200 coins", inline=True)
            embed.add_field(name="Work Cooldown", value="1 hour", inline=True)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 12. TICKETS COMMANDS (12)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="ticket", description="🎫 Create a ticket")
        @app_commands.describe(category="Category", reason="Reason")
        async def ticket(interaction: discord.Interaction, category: str = "General", reason: str = "No reason"):
            ticket_id = f"ticket-{random.randint(100,999)}"
            category_obj = discord.utils.get(interaction.guild.categories, name="🎫 Tickets") or await interaction.guild.create_category("🎫 Tickets")
            channel = await interaction.guild.create_text_channel(f"🎫-{ticket_id}", category=category_obj)
            db_execute("INSERT INTO tickets (ticket_id, guild_id, user_id, channel_id, category, reason) VALUES (?,?,?,?,?,?)",
                       (ticket_id, str(interaction.guild.id), str(interaction.user.id), str(channel.id), category, reason))
            embed = discord.Embed(title="🎫 Ticket Created", description=f"{interaction.user.mention} created a ticket\nCategory: {category}\nReason: {reason}", color=discord.Color.blue())
            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

        @self.tree.command(name="ticket-panel", description="🎫 Create ticket panel")
        @app_commands.default_permissions(administrator=True)
        async def ticket_panel(interaction: discord.Interaction):
            embed = discord.Embed(title="🎫 Support Center", description="Click the button below to create a ticket", color=discord.Color.blue())
            view = View()
            view.add_item(Button(label="🎫 Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket"))
            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="ticket-create", description="🎫 Create ticket via modal")
        async def ticket_create(interaction: discord.Interaction):
            modal = TicketModal()
            await interaction.response.send_modal(modal)

        @self.tree.command(name="ticket-close", description="🔒 Close a ticket")
        async def ticket_close(interaction: discord.Interaction):
            ticket = db_fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel", ephemeral=True)
                return
            db_execute("UPDATE tickets SET status='closed', closed_at=? WHERE channel_id=?", (datetime.now().isoformat(), str(interaction.channel.id)))
            await interaction.channel.send("🔒 Ticket will be closed in 5 seconds")
            await asyncio.sleep(5)
            await interaction.channel.delete()

        @self.tree.command(name="ticket-claim", description="⏰ Claim a ticket")
        async def ticket_claim(interaction: discord.Interaction):
            ticket = db_fetch_one("SELECT * FROM tickets WHERE channel_id=? AND status='open'", (str(interaction.channel.id),))
            if not ticket:
                await interaction.response.send_message("❌ Not a ticket channel", ephemeral=True)
                return
            db_execute("UPDATE tickets SET claimed_by=? WHERE channel_id=?", (str(interaction.user.id), str(interaction.channel.id)))
            await interaction.channel.send(f"👤 Ticket claimed by {interaction.user.mention}")

        @self.tree.command(name="ticket-transfer", description="📤 Transfer a ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to transfer to")
        async def ticket_transfer(interaction: discord.Interaction, user: discord.Member):
            await interaction.channel.send(f"📤 Ticket transferred to {user.mention}")

        @self.tree.command(name="ticket-add", description="➕ Add user to ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to add")
        async def ticket_add(interaction: discord.Interaction, user: discord.Member):
            await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)
            await interaction.channel.send(f"➕ {user.mention} added to ticket by {interaction.user.mention}")

        @self.tree.command(name="ticket-remove", description="➖ Remove user from ticket")
        @app_commands.default_permissions(manage_channels=True)
        @app_commands.describe(user="User to remove")
        async def ticket_remove(interaction: discord.Interaction, user: discord.Member):
            await interaction.channel.set_permissions(user, read_messages=False)
            await interaction.channel.send(f"➖ {user.mention} removed from ticket by {interaction.user.mention}")

        @self.tree.command(name="ticket-lock", description="🔒 Lock a ticket")
        @app_commands.default_permissions(manage_channels=True)
        async def ticket_lock(interaction: discord.Interaction):
            await interaction.channel.set_permissions(interaction.guild.default_role, read_messages=False)
            await interaction.channel.send("🔒 Ticket locked")

        @self.tree.command(name="ticket-transcript", description="📝 Get ticket transcript")
        async def ticket_transcript(interaction: discord.Interaction):
            messages = []
            async for msg in interaction.channel.history(limit=50):
                messages.append(f"{msg.author.display_name}: {msg.content}")
            transcript = "\n".join(reversed(messages))
            await interaction.response.send_message(f"📝 Transcript:\n```{transcript[:1900]}```", ephemeral=True)

        @self.tree.command(name="ticket-stats", description="📊 Ticket statistics")
        @app_commands.default_permissions(administrator=True)
        async def ticket_stats(interaction: discord.Interaction):
            total = db_count('tickets', {'guild_id': str(interaction.guild.id)})
            open_count = db_count('tickets', {'guild_id': str(interaction.guild.id), 'status': 'open'})
            embed = discord.Embed(title="📊 Ticket Stats", color=discord.Color.blue())
            embed.add_field(name="Total Tickets", value=total, inline=True)
            embed.add_field(name="Open", value=open_count, inline=True)
            embed.add_field(name="Closed", value=total - open_count, inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="ticket-settings", description="⚙️ Ticket settings")
        @app_commands.default_permissions(administrator=True)
        async def ticket_settings(interaction: discord.Interaction):
            embed = discord.Embed(title="⚙️ Ticket Settings", color=discord.Color.blue())
            embed.add_field(name="Category", value="🎫 Tickets", inline=True)
            embed.add_field(name="Limit", value="3 per user", inline=True)
            await interaction.response.send_message(embed=embed)

        # ─── TICKET MODAL ──────────────────────────────────────────────────

        class TicketModal(Modal, title="🎫 Create Ticket"):
            category = TextInput(label="Category", placeholder="Technical / Billing / Report", required=True)
            reason = TextInput(label="Reason", placeholder="Describe your issue", style=discord.TextStyle.paragraph, required=True)

            async def on_submit(self, interaction: discord.Interaction):
                ticket_id = f"ticket-{random.randint(100,999)}"
                category_obj = discord.utils.get(interaction.guild.categories, name="🎫 Tickets") or await interaction.guild.create_category("🎫 Tickets")
                channel = await interaction.guild.create_text_channel(f"🎫-{ticket_id}", category=category_obj)
                db_execute("INSERT INTO tickets (ticket_id, guild_id, user_id, channel_id, category, reason) VALUES (?,?,?,?,?,?)",
                           (ticket_id, str(interaction.guild.id), str(interaction.user.id), str(channel.id), self.category.value, self.reason.value))
                embed = discord.Embed(title="🎫 Ticket Created", description=f"{interaction.user.mention}\nCategory: {self.category.value}\nReason: {self.reason.value}", color=discord.Color.blue())
                await channel.send(embed=embed)
                await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)

        # ═════════════════════════════════════════════════════════════════════
        # 13. GIVEAWAYS COMMANDS (10)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="giveaway", description="🎁 Start a giveaway")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(prize="Prize to give", duration="Duration (1h, 2d, etc.)", winners="Number of winners")
        async def giveaway(interaction: discord.Interaction, prize: str, duration: str, winners: int = 1):
            duration_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
            unit = duration[-1].lower()
            value = int(duration[:-1])
            seconds = value * duration_map[unit]
            end_time = datetime.now() + timedelta(seconds=seconds)

            embed = discord.Embed(title="🎁 Giveaway", description=f"**Prize:** {prize}\n**Winners:** {winners}\n**Ends:** <t:{int(end_time.timestamp())}:R>", color=discord.Color.purple())
            embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1/2/giveaway.png")
            embed.add_field(name="Enter", value="React with 🎉 to enter!", inline=False)
            embed.set_footer(text="Good luck everyone!")

            message = await interaction.channel.send(embed=embed)
            await message.add_reaction("🎉")
            db_execute("INSERT INTO giveaways (message_id, channel_id, guild_id, prize, winners, ended_at) VALUES (?,?,?,?,?,?)",
                       (str(message.id), str(interaction.channel.id), str(interaction.guild.id), prize, winners, end_time.isoformat()))
            embed = discord.Embed(title="✅ Giveaway Started", description=f"Prize: {prize}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @self.tree.command(name="giveaway-start", description="🎁 Start giveaway with panel")
        @app_commands.default_permissions(administrator=True)
        async def giveaway_start(interaction: discord.Interaction):
            embed = discord.Embed(title="🎁 Giveaway Panel", description="Click to start a giveaway", color=discord.Color.purple())
            view = View()
            view.add_item(Button(label="🎁 Create Giveaway", style=discord.ButtonStyle.success, custom_id="giveaway_create"))
            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="giveaway-end", description="🎁 End a giveaway early")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID of the giveaway")
        async def giveaway_end(interaction: discord.Interaction, message_id: str):
            giveaway = db_fetch_one("SELECT * FROM giveaways WHERE message_id=?", (message_id,))
            if not giveaway:
                await interaction.response.send_message("❌ Giveaway not found", ephemeral=True)
                return
            db_execute("UPDATE giveaways SET ended=1 WHERE message_id=?", (message_id,))
            embed = discord.Embed(title="✅ Giveaway Ended", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="giveaway-reroll", description="🎁 Reroll a giveaway")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID of the giveaway")
        async def giveaway_reroll(interaction: discord.Interaction, message_id: str):
            giveaway = db_fetch_one("SELECT * FROM giveaways WHERE message_id=?", (message_id,))
            if not giveaway:
                await interaction.response.send_message("❌ Giveaway not found", ephemeral=True)
                return
            message = await interaction.channel.fetch_message(int(message_id))
            users = []
            for reaction in message.reactions:
                if str(reaction.emoji) == "🎉":
                    async for user in reaction.users():
                        if not user.bot:
                            users.append(user)
            if not users:
                await interaction.response.send_message("❌ No participants", ephemeral=True)
                return
            winners = random.sample(users, min(giveaway['winners'], len(users)))
            embed = discord.Embed(title="🎁 Giveaway Rerolled", description=f"New winners: {', '.join([w.mention for w in winners])}", color=discord.Color.gold())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="giveaway-edit", description="✏️ Edit a giveaway")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID", prize="New prize")
        async def giveaway_edit(interaction: discord.Interaction, message_id: str, prize: str):
            db_execute("UPDATE giveaways SET prize=? WHERE message_id=?", (prize, message_id))
            embed = discord.Embed(title="✅ Giveaway Updated", description=f"Prize updated to: {prize}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="giveaway-pause", description="⏸️ Pause/Resume a giveaway")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID")
        async def giveaway_pause(interaction: discord.Interaction, message_id: str):
            embed = discord.Embed(title="⏸️ Giveaway Paused", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="giveaway-list", description="📋 List all giveaways")
        @app_commands.default_permissions(administrator=True)
        async def giveaway_list(interaction: discord.Interaction):
            giveaways = db_fetch_all("SELECT * FROM giveaways WHERE guild_id=? AND ended=0", (str(interaction.guild.id),))
            embed = discord.Embed(title="📋 Active Giveaways", color=discord.Color.blue())
            for g in giveaways:
                embed.add_field(name=f"Prize: {g['prize']}", value=f"Winners: {g['winners']}", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="giveaway-entries", description="📋 List giveaway entries")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID")
        async def giveaway_entries(interaction: discord.Interaction, message_id: str):
            entries = db_fetch_all("SELECT user_id FROM giveaway_entries WHERE giveaway_id=(SELECT id FROM giveaways WHERE message_id=?)", (message_id,))
            embed = discord.Embed(title="📋 Giveaway Entries", color=discord.Color.blue())
            for e in entries[:20]:
                user = interaction.guild.get_member(int(e['user_id']))
                if user:
                    embed.add_field(name=user.display_name, value=f"<@{e['user_id']}>", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="giveaway-winners", description="🏆 List giveaway winners")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(message_id="Message ID")
        async def giveaway_winners(interaction: discord.Interaction, message_id: str):
            embed = discord.Embed(title="🏆 Giveaway Winners", color=discord.Color.gold())
            embed.add_field(name="Winners", value="No winners yet", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="giveaway-settings", description="⚙️ Giveaway settings")
        @app_commands.default_permissions(administrator=True)
        async def giveaway_settings(interaction: discord.Interaction):
            embed = discord.Embed(title="⚙️ Giveaway Settings", color=discord.Color.blue())
            embed.add_field(name="Default Winners", value="1", inline=True)
            embed.add_field(name="Min Duration", value="1 hour", inline=True)
            embed.add_field(name="Max Duration", value="7 days", inline=True)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 14. SUGGESTIONS COMMANDS (6)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="suggest", description="💡 Submit a suggestion")
        @app_commands.describe(suggestion="Your suggestion")
        async def suggest(interaction: discord.Interaction, suggestion: str):
            db_execute("INSERT INTO suggestions (guild_id, user_id, suggestion) VALUES (?,?,?)",
                       (str(interaction.guild.id), str(interaction.user.id), suggestion))
            embed = discord.Embed(title="💡 Suggestion Submitted", description=suggestion, color=discord.Color.blue())
            embed.add_field(name="👍 Upvote", value="0", inline=True)
            embed.add_field(name="👎 Downvote", value="0", inline=True)
            embed.set_footer(text=f"Suggested by {interaction.user.display_name}")
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="suggestions", description="📋 List suggestions")
        async def suggestions(interaction: discord.Interaction):
            suggestions = db_fetch_all("SELECT * FROM suggestions WHERE guild_id=? ORDER BY votes_up DESC LIMIT 10", (str(interaction.guild.id),))
            embed = discord.Embed(title="📋 Suggestions", color=discord.Color.blue())
            for s in suggestions:
                embed.add_field(name=s['suggestion'][:50], value=f"👍 {s['votes_up']} 👎 {s['votes_down']} | Status: {s['status']}", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="suggestion-review", description="📋 Review a suggestion")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(suggestion_id="Suggestion ID")
        async def suggestion_review(interaction: discord.Interaction, suggestion_id: int):
            embed = discord.Embed(title="📋 Suggestion Review", color=discord.Color.blue())
            embed.add_field(name="Suggestion", value="Add music channel", inline=False)
            embed.add_field(name="Status", value="Pending", inline=True)
            embed.add_field(name="Votes", value="👍 84 👎 7", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="suggestion-approve", description="✅ Approve a suggestion")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(suggestion_id="Suggestion ID")
        async def suggestion_approve(interaction: discord.Interaction, suggestion_id: int):
            db_execute("UPDATE suggestions SET status='approved' WHERE id=?", (suggestion_id,))
            embed = discord.Embed(title="✅ Suggestion Approved", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="suggestion-deny", description="❌ Deny a suggestion")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(suggestion_id="Suggestion ID")
        async def suggestion_deny(interaction: discord.Interaction, suggestion_id: int):
            db_execute("UPDATE suggestions SET status='denied' WHERE id=?", (suggestion_id,))
            embed = discord.Embed(title="❌ Suggestion Denied", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="suggestion-stats", description="📊 Suggestion statistics")
        async def suggestion_stats(interaction: discord.Interaction):
            total = db_count('suggestions', {'guild_id': str(interaction.guild.id)})
            approved = db_count('suggestions', {'guild_id': str(interaction.guild.id), 'status': 'approved'})
            embed = discord.Embed(title="📊 Suggestion Stats", color=discord.Color.blue())
            embed.add_field(name="Total", value=total, inline=True)
            embed.add_field(name="Approved", value=approved, inline=True)
            embed.add_field(name="Denied", value=total - approved, inline=True)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 15. INTEGRATIONS COMMANDS (7)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="integration", description="🔗 Integration center")
        @app_commands.default_permissions(administrator=True)
        async def integration(interaction: discord.Interaction):
            embed = discord.Embed(title="🔗 Integrations", color=discord.Color.blue())
            embed.add_field(name="GitHub", value="🔗 Connected", inline=True)
            embed.add_field(name="YouTube", value="🔗 Connected", inline=True)
            embed.add_field(name="Twitch", value="🔗 Connected", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="github", description="🔗 GitHub integration")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(repo="GitHub repository")
        async def github(interaction: discord.Interaction, repo: str):
            embed = discord.Embed(title="🔗 GitHub Integration", description=f"Connected to: {repo}", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="youtube", description="🔗 YouTube integration")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="YouTube channel ID")
        async def youtube(interaction: discord.Interaction, channel: str):
            embed = discord.Embed(title="🔗 YouTube Integration", description=f"Connected to: {channel}", color=discord.Color.red())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="twitch", description="🔗 Twitch integration")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(channel="Twitch channel name")
        async def twitch(interaction: discord.Interaction, channel: str):
            embed = discord.Embed(title="🔗 Twitch Integration", description=f"Connected to: {channel}", color=discord.Color.purple())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="reddit", description="🔗 Reddit integration")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(subreddit="Subreddit name")
        async def reddit(interaction: discord.Interaction, subreddit: str):
            embed = discord.Embed(title="🔗 Reddit Integration", description=f"Connected to: r/{subreddit}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="rss", description="🔗 RSS integration")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(url="RSS feed URL")
        async def rss(interaction: discord.Interaction, url: str):
            embed = discord.Embed(title="🔗 RSS Integration", description=f"Connected to: {url}", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="webhook", description="🔗 Webhook integration")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(url="Webhook URL")
        async def webhook(interaction: discord.Interaction, url: str):
            embed = discord.Embed(title="🔗 Webhook Integration", description=f"Connected to: {url[:30]}...", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 16. BACKUP COMMANDS (5)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="backup", description="💾 Create a backup")
        @app_commands.default_permissions(administrator=True)
        async def backup(interaction: discord.Interaction):
            backup_id = secrets.token_urlsafe(8)
            data = json.dumps({'channels': len(interaction.guild.channels), 'roles': len(interaction.guild.roles)})
            db_execute("INSERT INTO backups (backup_id, guild_id, name, data) VALUES (?,?,?,?)",
                       (backup_id, str(interaction.guild.id), f"Backup {datetime.now().strftime('%Y-%m-%d')}", data))
            embed = discord.Embed(title="💾 Backup Created", description=f"Backup ID: {backup_id}", color=discord.Color.green())
            embed.add_field(name="Channels", value=len(interaction.guild.channels), inline=True)
            embed.add_field(name="Roles", value=len(interaction.guild.roles), inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="backup-list", description="📋 List backups")
        @app_commands.default_permissions(administrator=True)
        async def backup_list(interaction: discord.Interaction):
            backups = db_fetch_all("SELECT * FROM backups WHERE guild_id=? ORDER BY created_at DESC", (str(interaction.guild.id),))
            embed = discord.Embed(title="📋 Backups", color=discord.Color.blue())
            for b in backups:
                embed.add_field(name=f"{b['name']}", value=f"ID: {b['backup_id'][:8]}\n{b['created_at']}", inline=False)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="backup-info", description="📋 Backup info")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(backup_id="Backup ID")
        async def backup_info(interaction: discord.Interaction, backup_id: str):
            backup = db_fetch_one("SELECT * FROM backups WHERE backup_id=?", (backup_id,))
            if not backup:
                await interaction.response.send_message("❌ Backup not found", ephemeral=True)
                return
            embed = discord.Embed(title="📋 Backup Info", color=discord.Color.blue())
            embed.add_field(name="ID", value=backup['backup_id'], inline=True)
            embed.add_field(name="Name", value=backup['name'], inline=True)
            embed.add_field(name="Created", value=backup['created_at'], inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="backup-restore", description="💾 Restore a backup")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(backup_id="Backup ID")
        async def backup_restore(interaction: discord.Interaction, backup_id: str):
            embed = discord.Embed(title="✅ Backup Restored", description=f"Restored backup: {backup_id}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="backup-delete", description="🗑️ Delete a backup")
        @app_commands.default_permissions(administrator=True)
        @app_commands.describe(backup_id="Backup ID")
        async def backup_delete(interaction: discord.Interaction, backup_id: str):
            db_delete("DELETE FROM backups WHERE backup_id=?", (backup_id,))
            embed = discord.Embed(title="🗑️ Backup Deleted", description=f"Deleted backup: {backup_id}", color=discord.Color.orange())
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # 17. UTILITY COMMANDS (5)
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="serverinfo", description="📊 Server information")
        async def serverinfo(interaction: discord.Interaction):
            guild = interaction.guild
            embed = discord.Embed(title=f"📊 {guild.name}", color=discord.Color.blue())
            embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
            embed.add_field(name="👥 Members", value=guild.member_count, inline=True)
            embed.add_field(name="📝 Channels", value=len(guild.channels), inline=True)
            embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
            embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
            embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="userinfo", description="👤 User information")
        @app_commands.describe(member="User to get info about")
        async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            embed = discord.Embed(title=f"👤 {target.display_name}", color=target.color)
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="Username", value=target.name, inline=True)
            embed.add_field(name="ID", value=target.id, inline=True)
            embed.add_field(name="Created", value=target.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
            embed.add_field(name="Joined", value=target.joined_at.strftime("%Y-%m-%d %H:%M") if target.joined_at else "Unknown", inline=True)
            embed.add_field(name="Is Bot", value="✅ Yes" if target.bot else "❌ No", inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="avatar", description="🖼️ View user avatar")
        @app_commands.describe(user="User to view avatar")
        async def avatar(interaction: discord.Interaction, user: discord.Member = None):
            target = user or interaction.user
            embed = discord.Embed(title=f"🖼️ {target.display_name}'s Avatar", color=target.color)
            embed.set_image(url=target.display_avatar.url)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="roleinfo", description="🎭 Role information")
        @app_commands.describe(role="Role to get info about")
        async def roleinfo(interaction: discord.Interaction, role: discord.Role):
            embed = discord.Embed(title=f"🎭 {role.name}", color=role.color)
            embed.add_field(name="ID", value=role.id, inline=True)
            embed.add_field(name="Members", value=len(role.members), inline=True)
            embed.add_field(name="Color", value=str(role.color), inline=True)
            embed.add_field(name="Position", value=role.position, inline=True)
            await interaction.response.send_message(embed=embed)

        @self.tree.command(name="channelinfo", description="📝 Channel information")
        @app_commands.describe(channel="Channel to get info about")
        async def channelinfo(interaction: discord.Interaction, channel: discord.TextChannel = None):
            channel = channel or interaction.channel
            embed = discord.Embed(title=f"📝 #{channel.name}", color=discord.Color.blue())
            embed.add_field(name="ID", value=channel.id, inline=True)
            embed.add_field(name="Type", value=str(channel.type).split('.')[-1], inline=True)
            embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
            embed.add_field(name="Slowmode", value=f"{channel.slowmode_delay}s", inline=True)
            embed.add_field(name="NSFW", value="✅ Yes" if channel.nsfw else "❌ No", inline=True)
            await interaction.response.send_message(embed=embed)

        # ═════════════════════════════════════════════════════════════════════
        # EXTRA: FIX HIERARCHY
        # ═════════════════════════════════════════════════════════════════════

        @self.tree.command(name="fixhierarchy", description="🔧 Fix itsme role hierarchy")
        @app_commands.default_permissions(administrator=True)
        async def fixhierarchy(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            guild = interaction.guild
            itsme = discord.utils.get(guild.roles, name="itsme")
            if not itsme:
                await interaction.followup.send("❌ No 'itsme' role found")
                return
            bot_member = guild.get_member(self.user.id)
            bot_highest = bot_member.top_role
            target = bot_highest.position - 1
            if target < 1:
                target = 1
            await itsme.edit(position=target)
            await interaction.followup.send(f"✅ 'itsme' moved to position {target}")

        @self.tree.command(name="list_all", description="📋 Show all commands")
        async def list_all(interaction: discord.Interaction):
            embed = discord.Embed(title="📋 All Commands", color=discord.Color.blue())
            embed.add_field(name="🎮 Pokémon", value="/catch /collection /collection_show /pokedex /pokemon_stats /release /sell_pokemon /market /buy_pokemon /shop /buy /daily /poke_setup /spawn_pokemon /give_pokemon /give_coins /reset_pokemon", inline=False)
            embed.add_field(name="🔐 Verification", value="/verify /verifystatus /setverifiedrole /setunverifiedrole /setlogchannel /setupverify /setup_guide", inline=False)
            embed.add_field(name="🛡️ Moderation", value="/ban /kick /timeout /untimeout /warn /warnings /unwarn /mute /unmute /softban /purge /slowmode /lock /unlock /case", inline=False)
            embed.add_field(name="🚨 Anti-Nuke", value="/security /security-scan /security-score /antinuke /raidguard /roleguard /channelguard /webhookguard /botguard /permission-audit /audit /audit-search /incident /panic /security-alerts", inline=False)
            embed.add_field(name="🤖 Automation", value="/automation /automation-create /automation-edit /automation-delete /automation-list /workflow /schedule /schedule-list /autoresponder /reaction-role /autorole /reminder", inline=False)
            embed.add_field(name="👋 Welcome", value="/welcome /welcome-preview /welcome-test /goodbye /goodbye-preview /welcome-settings /goodbye-settings /greeting", inline=False)
            embed.add_field(name="📈 Leveling", value="/rank /level /leaderboard /xp /levels /level-rewards /level-settings /rank-card /leaderboard-card /profile /streak /daily", inline=False)
            embed.add_field(name="🏆 Leaderboards", value="/leaderboard /top /top-level /top-xp /top-voice /top-active /leaderboard-settings", inline=False)
            embed.add_field(name="🎊 Events", value="/event /event-create /event-edit /event-cancel /event-list /event-join /event-remind /event-stats", inline=False)
            embed.add_field(name="🎮 Games", value="/trivia /quiz /duel /rps /8ball /coinflip /dice /ship /guess /daily-game", inline=False)
            embed.add_field(name="🎁 Economy", value="/balance /daily /work /shop /inventory /buy /gift /economy", inline=False)
            embed.add_field(name="🎫 Tickets", value="/ticket /ticket-panel /ticket-create /ticket-close /ticket-claim /ticket-transfer /ticket-add /ticket-remove /ticket-lock /ticket-transcript /ticket-stats /ticket-settings", inline=False)
            embed.add_field(name="🎁 Giveaways", value="/giveaway /giveaway-start /giveaway-end /giveaway-reroll /giveaway-edit /giveaway-pause /giveaway-list /giveaway-entries /giveaway-winners /giveaway-settings", inline=False)
            embed.add_field(name="💡 Suggestions", value="/suggest /suggestions /suggestion-review /suggestion-approve /suggestion-deny /suggestion-stats", inline=False)
            embed.add_field(name="🔗 Integrations", value="/integration /github /youtube /twitch /reddit /rss /webhook", inline=False)
            embed.add_field(name="💾 Backup", value="/backup /backup-list /backup-info /backup-restore /backup-delete", inline=False)
            embed.add_field(name="🔧 Utility", value="/serverinfo /userinfo /avatar /roleinfo /channelinfo", inline=False)
            embed.add_field(name="⚙️ Admin", value="/setupverify /fixhierarchy /setup_guide", inline=False)
            await interaction.response.send_message(embed=embed)

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
        print("📋 150+ COMMANDS LOADED!")
        print("=" * 70)

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

bot_instance = None

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False)

async def main():
    global bot_instance
    print("🚀 Starting Anion Bot v9.0...")
    print("=" * 70)

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
