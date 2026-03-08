from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import hashlib
import time
from datetime import datetime, timedelta
import requests
import pymysql
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
import random
import string
import bcrypt
import json
import secrets
import traceback
from lib.util import parse_object
from flask_dance.contrib.google import make_google_blueprint, google


app = Flask(__name__, template_folder='templates')
# Keep user logged in for 24 hours unless they explicitly logout
app.permanent_session_lifetime = timedelta(hours=24)

# DB Config
DB_CONFIG = {
    'host': 'server156.secureclouddns.net',
    'user': 'kendyen1_admin',
    'password': 'Admin@2862',
    'database': 'kendyen1_web',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
	"""
	Create and return a database connection using the configured DB_CONFIG.
	"""
	return pymysql.connect(**DB_CONFIG)

def get_bharatpe_credentials():
    """
    Fetch active BharatPe credentials from payment_method table.
    Returns (merchant_id, token) or (None, None) if not found.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT bharatpe_merchant_id, bharatpe_token
                FROM payment_method
                WHERE status = 1
                AND bharatpe_merchant_id IS NOT NULL
                AND bharatpe_token IS NOT NULL
                LIMIT 1
            """)
            row = cursor.fetchone()
        conn.close()

        if row:
            return row['bharatpe_merchant_id'], row['bharatpe_token']
        return None, None

    except Exception as e:
        print(f"[BharatPe DB Error] {e}")
        return None, None

BHARATPE_MERCHANT_ID, BHARATPE_TOKEN = get_bharatpe_credentials()

# MUST exist or OAuth will crash
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "xtreme_topup_super_secret_2025_change_this"
)

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True

# --------------------------- Kanglei -----------------------
KANGLEI_USER_TOKEN = "524316cfa21498ad061dd66638d0dbcb"

KANGLEI_CREATE_URL = "https://payment.kendyenterprises.in/api/create-order"
KANGLEI_STATUS_URL = "https://payment.kendyenterprises.in/api/check-order-status"

# Add max and min functions to Jinja2 globals
app.jinja_env.globals.update(max=max, min=min)

# ---------------------------
# Google OAuth configuration
# ---------------------------
# Replace with environment variables in production
GOOGLE_CLIENT_ID = '1095349822480-9iendb3n6desdcont5llj6an85dpjiol.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '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'

# register flask-dance google blueprint
google_bp = make_google_blueprint(
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    scope=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
    redirect_to='google_oauth_callback',
    storage=None   # ðŸš¨ THIS PREVENTS TOKEN STORAGE CRASH
)

app.register_blueprint(google_bp, url_prefix="/login")

@app.before_request
def check_maintenance():
    # Allow access to maintenance page, admin routes, and static files
    if request.endpoint in ['maintenance', 'static'] or request.path.startswith('/admin') or request.path.startswith('/login'):
        return
    
    # Check if user is admin - admins bypass maintenance mode
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT is_admin FROM users WHERE id = %s LIMIT 1", (session['user_id'],))
                user = cur.fetchone()
                if user and user.get('is_admin') == 1:
                    conn.close()
                    return
            conn.close()
        except Exception:
            pass
    
    # Check if maintenance mode file exists
    maintenance_file = os.path.join(os.path.dirname(__file__), 'maintenance_mode.txt')
    if os.path.exists(maintenance_file):
        return redirect(url_for('maintenance'))

def send_otp_email(receiver_email, otp):
    smtp_server = 'mail.kendyenterprises.in'
    smtp_port = 465
    sender_email = 'noreply@kendyenterprises.in'
    sender_password = 'Renedy@123'

    subject = 'Your OTP Code'

    # Plain-text fallback
    plain_text = f"Your OTP for verification is {otp}. It is valid for 10 minutes."

    # HTML email using clean and simple template
    year = datetime.now().year
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>OTP Verification</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            margin: 0;
            padding: 0;
            background-color: #f4f6f8;
            font-family: Arial, Helvetica, sans-serif;
        }}
        .email-container {{
            max-width: 520px;
            margin: 30px auto;
            background: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        }}
        .email-header {{
            background: #0d6efd;
            color: #ffffff;
            text-align: center;
            padding: 20px;
            font-size: 22px;
            font-weight: bold;
        }}
        .email-body {{
            padding: 25px;
            color: #333333;
            line-height: 1.6;
            font-size: 15px;
        }}
        .otp-box {{
            margin: 25px auto;
            text-align: center;
            font-size: 32px;
            letter-spacing: 6px;
            font-weight: bold;
            color: #0d6efd;
            background: #f1f5ff;
            padding: 15px;
            border-radius: 6px;
            width: fit-content;
        }}
        .email-footer {{
            background: #f4f6f8;
            padding: 15px;
            text-align: center;
            font-size: 12px;
            color: #777777;
        }}
        .warning {{
            color: #dc3545;
            font-size: 13px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>

<div class="email-container">
    <div class="email-header">
        OTP Verification
    </div>

    <div class="email-body">
        <p>Hello,</p>

        <p>Thank you for registering with us. Please use the following One-Time Password (OTP) to verify your email address:</p>

        <div class="otp-box">
            {otp}
        </div>

        <p>This OTP is valid for <strong>10 minutes</strong>. Please do not share it with anyone.</p>

        <p class="warning">
            If you did not request this OTP, please ignore this email.
        </p>

        <p>Best regards,<br>
        <strong>Kendy Enterprises</strong></p>
    </div>

    <div class="email-footer">
        Â© {year} Kendy Enterprises. All rights reserved.
    </div>
</div>
    
</body>
</html>"""

    # Construct multipart/alternative message with plain text and HTML
    message = MIMEMultipart('alternative')
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject
    message.attach(MIMEText(plain_text, 'plain'))
    message.attach(MIMEText(html_body, 'html'))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, message.as_string())


def _ensure_password_resets_table():
    """Create password_resets table if it doesn't exist."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS password_resets (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(255),
                    token VARCHAR(255),
                    expires_at DATETIME,
                    used TINYINT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) CHARSET=utf8mb4;
            """)
        try:
            conn.close()
        except Exception:
            pass
    except Exception:
        pass


def send_reset_email(receiver_email, token):
    """Send password reset email containing a link to the front-end redirect page.
    The link will point to `/reset_pasword?token=<token>` which will redirect
    to `/reset_password?token=<token>` (or your front-end route).
    """
    smtp_server = 'mail.kendyenterprises.in'
    smtp_port = 465
    sender_email = 'noreply@kendyenterprises.in'
    sender_password = 'Renedy@123'

    subject = 'Reset your password'


    # Build absolute URL using request.host_url if available
    try:
        base = request.host_url.rstrip('/')
    except Exception:
        base = ''

    reset_path = f"/reset_pasword?token={token}"
    reset_url = f"{base}{reset_path}" if base else reset_path

    plain_text = f"To reset your password, click the following link: {reset_url}\nThis link expires in 10 minutes."

    year = datetime.now().year
    html_body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Reset Your Access</title>
  <style>
    /* Reset styles for email clients */
    body {{
      margin: 0;
      padding: 0;
      width: 100% !important;
      background-color: #0a0a0c;
      font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #ffffff;
    }}
    img {{ outline: none; text-decoration: none; border: none; }}
    a {{ color: #00f2ff; text-decoration: none; }}
    
    /* Layout */
    .wrapper {{
      width: 100%;
      table-layout: fixed;
      background-color: #0a0a0c;
      padding-bottom: 40px;
    }}
    
    .main-card {{
      max-width: 600px;
      margin: 40px auto;
      background-color: #141417;
      border: 1px solid #2d2d35;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
    }}

    /* VFX Header Bar */
    .vfx-header {{
      background: linear-gradient(90deg, #7000ff 0%, #00f2ff 100%);
      height: 4px;
      width: 100%;
    }}

    .content {{
      padding: 40px 30px;
      text-align: center;
    }}

    .logo-text {{
      font-size: 24px;
      font-weight: 800;
      letter-spacing: 2px;
      text-transform: uppercase;
      margin-bottom: 30px;
      color: #ffffff;
    }}

    .logo-accent {{
      color: #00f2ff;
    }}

    h1 {{
      font-size: 22px;
      margin-top: 0;
      letter-spacing: 1px;
      text-transform: uppercase;
      color: #ffffff;
    }}

    p {{
      line-height: 1.6;
      color: #a0a0ab;
      font-size: 16px;
    }}

    /* VFX Button */
    .btn-container {{
      padding: 30px 0;
    }}

    .vfx-button {{
      background: linear-gradient(45deg, #7000ff, #00f2ff);
      color: #ffffff !important;
      padding: 16px 32px;
      border-radius: 6px;
      font-weight: bold;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 2px;
      display: inline-block;
      text-decoration: none;
      box-shadow: 0 4px 15px rgba(0, 242, 255, 0.3);
    }}

    .expiry-note {{
      font-size: 13px;
      border-top: 1px solid #2d2d35;
      padding-top: 20px;
      margin-top: 30px;
      color: #666670;
    }}

    .footer {{
      text-align: center;
      padding: 20px;
    }}

    .footer p {{
      font-size: 12px;
      color: #4a4a52;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <table class="main-card" cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td>
          <div class="vfx-header"></div>
          <div class="content">
            <div class="logo-text">
              XTREAM <span class="logo-accent">TOP-UP</span>
            </div>
            
            <h1>Security Verification</h1>
            
            <p>Hello,</p>
            <p>A request has been initiated to reset the credentials for your Xtream account. Secure your account by clicking the button below:</p>
            
            <div class="btn-container">
              <a href="{reset_url}" class="vfx-button">Authorize Reset</a>
            </div>
            
            <p class="expiry-note">
              <strong>SECURITY ALERT:</strong> This link expires in 10 minutes.<br>
              If you did not request this, please secure your account immediately.
            </p>
          </div>
        </td>
      </tr>
    </table>
    
    <div class="footer">
      <p>â€” THE XTREAM TEAM</p>
      <p>&copy; {year} Kendy Enterprises. All Rights Reserved.</p>
    </div>
  </div>
</body>
</html>"""

    message = MIMEMultipart('alternative')
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject
    message.attach(MIMEText(plain_text, 'plain'))
    message.attach(MIMEText(html_body, 'html'))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, message.as_string())

def generate_otp(length=6):
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

def generate_referrer_id():
    """Generate a random 6-digit referrer ID (100000-999999, no all-same-digit patterns)"""
    while True:
        # Generate number from 100000 to 999999
        num = random.randint(100000, 999999)
        # Check if all digits are NOT the same (e.g., exclude 111111, 222222, etc.)
        if len(set(str(num))) > 1:
            return str(num)

def generate_api_key(length):
    """Generate random API key with numeric and capital alphabetic characters"""
    chars = string.digits + string.ascii_uppercase
    return ''.join(random.choice(chars) for _ in range(length))


@app.route('/login/google')
def login_google():
    return redirect(url_for('google.login'))


@app.route('/login/google/complete')
def google_oauth_callback():
    # This endpoint is called AFTER flask-dance completes the token exchange.
    if not google.authorized:
        return redirect(url_for('google.login'))

    resp = None
    try:
        resp = google.get('/oauth2/v2/userinfo')
    except Exception as e:
        print(f"[Google OAuth] userinfo request failed: {e}")
        traceback.print_exc()
        return redirect(url_for('auth'))

    if not resp or not resp.ok:
        return redirect(url_for('auth'))

    info = resp.json()
    email = info.get('email')
    name = info.get('name') or info.get('given_name') or (email.split('@')[0] if email else 'user')

    if not email:
        return redirect(url_for('auth'))

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Generate username from Google name
            base = ''.join([c for c in name if c.isalnum()])[:32]
            if not base:
                base = email.split('@')[0]
            username = base
            i = 1
            while True:
                cur.execute("SELECT id FROM users WHERE username=%s", (username,))
                if not cur.fetchone():
                    break
                username = f"{base}{i}"
                i += 1

            cur.execute("SELECT id, username, email, balance FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
            if user:
                # Update username with latest from Google
                cur.execute("UPDATE users SET username=%s WHERE email=%s", (username, email))
                conn.commit()
                session.permanent = True
                session['user_id'] = int(user['id'])
                session['username'] = username
                session['email'] = user.get('email')
                session['balance'] = float(user.get('balance') or 0.0)
            else:
                raw_pw = secrets.token_urlsafe(12)
                hashed_pw = bcrypt.hashpw(raw_pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

                cur.execute(
                    "INSERT INTO users (username, email, password, created_at) VALUES (%s, %s, %s, NOW())",
                    (username, email, hashed_pw)
                )
                conn.commit()
                user_id = cur.lastrowid if hasattr(cur, 'lastrowid') else None
                if not user_id:
                    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
                    row = cur.fetchone()
                    user_id = int(row['id']) if row else None

                session.permanent = True
                session['user_id'] = int(user_id) if user_id else None
                session['username'] = username
                session['email'] = email
                session['balance'] = 0.0

    except Exception as e:
        print(f"[Google OAuth] DB error: {e}")
        traceback.print_exc()
        if conn:
            conn.close()
        return redirect(url_for('auth'))

    if conn:
        conn.close()
    return redirect(url_for('index'))


def save_base64_image(data_url, upload_dir='static/uploads/categories'):
    """Save a base64 data URL to a file and return the web-accessible path.
    Returns None on failure."""
    try:
        if not data_url or not data_url.startswith('data:'):
            return None
        header, encoded = data_url.split(',', 1)
        # infer extension from header
        mime = header.split(';')[0].split(':')[-1]
        ext = 'png'
        if mime == 'image/jpeg' or mime == 'image/jpg':
            ext = 'jpg'
        elif mime == 'image/gif':
            ext = 'gif'

        # ensure upload dir exists
        full_dir = os.path.join(os.path.dirname(__file__), 'templates', '..', upload_dir)
        full_dir = os.path.normpath(full_dir)
        os.makedirs(full_dir, exist_ok=True)

        filename = f"cat_{int(time.time())}_{random.randint(1000,9999)}.{ext}"
        file_path = os.path.join(full_dir, filename)

        import base64
        with open(file_path, 'wb') as f:
            f.write(base64.b64decode(encoded))

        # return a web path relative to the app root
        web_path = f"/{upload_dir}/{filename}".replace('\\', '/')
        return web_path
    except Exception:
        return None

def save_uploaded_image(file, upload_dir='static/uploads/banners'):
    """Save an uploaded file to a directory and return the web-accessible path.
    Returns None on failure."""
    try:
        if not file:
            return None
        
        # Get file extension from filename
        filename = file.filename
        if '.' in filename:
            ext = filename.rsplit('.', 1)[1].lower()
        else:
            # Try to determine from mimetype
            mime = file.mimetype
            ext = 'png'
            if mime == 'image/jpeg':
                ext = 'jpg'
            elif mime == 'image/gif':
                ext = 'gif'
            elif mime == 'image/png':
                ext = 'png'
        
        # ensure upload dir exists
        full_dir = os.path.join(os.path.dirname(__file__), 'templates', '..', upload_dir)
        full_dir = os.path.normpath(full_dir)
        os.makedirs(full_dir, exist_ok=True)

        # Generate unique filename
        filename = f"banner_{int(time.time())}_{random.randint(1000,9999)}.{ext}"
        file_path = os.path.join(full_dir, filename)

        # Save file
        file.save(file_path)

        # return a web path relative to the app root
        web_path = f"/{upload_dir}/{filename}".replace('\\', '/')
        return web_path
    except Exception as e:
        print(f"[ERROR] Failed to save uploaded image: {str(e)}")
        return None
# Lightweight DB helper that returns a connection with autocommit enabled.
def _get_db_conn():
    conn = get_db_connection()
    try:
        # PyMySQL connection supports autocommit(True)
        conn.autocommit(True)
    except Exception:
        # if setting autocommit fails, continue with the connection anyway
        pass
    return conn

def send_telegram_notification(message):
    bot_token = '7277766883:AAGwJBo0jfr2J7DJzIZubtFXfzPzOdut78A'
    chat_id = '6501929376'
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {'chat_id': chat_id, 'text': message}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram notification: {e}")

def send_admin_telegram_notification(message):
    """Send telegram notification to admin"""
    bot_token = '7277766883:AAGwJBo0jfr2J7DJzIZubtFXfzPzOdut78A'
    admin_chat_id = '6415302380'  # Admin telegram ID
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {'chat_id': admin_chat_id, 'text': message}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to send admin Telegram notification: {e}")

def send_order_failure_notification(order_id, region, provider, user_email, user_id, zone_id, product_name, category_name, payment_method, utr=None):
    """
    Send admin notification when an order fails with detailed information.
    """
    message = f"""🔴 ORDER FAILED - URGENT

Order ID: {order_id}
Region: {region or 'N/A'}
Provider: {provider}
User Email: {user_email}
Game User ID: {user_id}
Zone ID: {zone_id or 'N/A'}
Product: {product_name}
Category: {category_name}
Payment Method: {payment_method}
{f'UTR: {utr}' if utr else ''}

Order status set to PROCESSING for manual review.
"""
    send_admin_telegram_notification(message)

def send_order_insufficient_balance_notification(order_id, region, provider, user_email, user_id, zone_id, product_name, category_name, payment_method, required_balance, current_balance, utr=None):
    """
    Send admin notification when order is created but API provider has insufficient balance.
    """
    message = f"""⚠️ INSUFFICIENT API BALANCE - ACTION NEEDED

Order ID: {order_id}
Region: {region or 'N/A'}
Provider: {provider}
User Email: {user_email}
Game User ID: {user_id}
Zone ID: {zone_id or 'N/A'}
Product: {product_name}
Category: {category_name}
Payment Method: {payment_method}
{f'UTR: {utr}' if utr else ''}

Required Balance: {required_balance}
Current Balance: {current_balance}
Shortage: {required_balance - current_balance}

Order status set to PROCESSING - waiting for API balance to be topped up.
Please recharge {provider} balance and process this order manually.
"""
    send_admin_telegram_notification(message)

def check_provider_balance_sufficient(provider, required_amount, region=None):
    """
    Check if API provider has sufficient balance for the order amount.
    Returns: {'sufficient': True/False, 'balance': actual_balance, 'error': error_message_if_any}
    """
    try:
        if provider.lower() == 'smile':
            result = get_smile_balance(region=region)
            if result.get('success'):
                balance = result.get('smile_points', 0)
                return {
                    'sufficient': balance >= required_amount,
                    'balance': balance,
                    'error': None
                }
            else:
                return {
                    'sufficient': False,
                    'balance': 0,
                    'error': result.get('message', 'Failed to fetch balance')
                }
        elif provider.lower() == 'bushan':
            result = get_1gamestopup_balance()
            if result.get('success'):
                balance = result.get('balance', 0)
                return {
                    'sufficient': balance >= required_amount,
                    'balance': balance,
                    'error': None
                }
            else:
                return {
                    'sufficient': False,
                    'balance': 0,
                    'error': result.get('message', 'Failed to fetch balance')
                }
        elif provider.lower() == 'hopestore':
            result = get_hopstore_balance()
            if result.get('success'):
                balance = result.get('balance', 0)
                return {
                    'sufficient': balance >= required_amount,
                    'balance': balance,
                    'error': None
                }
            else:
                return {
                    'sufficient': False,
                    'balance': 0,
                    'error': result.get('message', 'Failed to fetch balance')
                }
        else:
            # For unknown providers, assume balance is sufficient
            return {
                'sufficient': True,
                'balance': required_amount,
                'error': None
            }
    except Exception as e:
        print(f"[ERROR] Failed to check {provider} balance: {str(e)}")
        return {
            'sufficient': False,
            'balance': 0,
            'error': str(e)
        }

def send_whatsapp_notification(phone_number, message):
    """Send WhatsApp notification via third-party API (e.g., Twilio, WhatsApp Business API, etc.)"""
    try:
        # Replace with your actual WhatsApp API endpoint and authentication
        # Example using a generic WhatsApp API structure
        whatsapp_api_url = "https://api.whatsapp.com/send"  # Update with your actual endpoint
        
        # Format phone number for WhatsApp (ensure it has country code)
        if not phone_number.startswith('+'):
            phone_number = '+91' + phone_number if len(phone_number) == 10 else '+' + phone_number
        
        payload = {
            "phone": phone_number,
            "message": message
        }
        
        # Optional: Implement actual WhatsApp API call here
        # For now, we'll log it
        print(f"[WHATSAPP] Message sent to {phone_number}: {message}")
        
    except Exception as e:
        print(f"[ERROR] Failed to send WhatsApp notification: {e}")

# ensure table exists (safe to call repeatedly)
_TABLE_CREATED = False
def _ensure_table():
    global _TABLE_CREATED
    if _TABLE_CREATED:
        return
    create_sql = """
    CREATE TABLE IF NOT EXISTS id_validation_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        player_id VARCHAR(255),
        server_id VARCHAR(255),
        nickname VARCHAR(255),
        country_code VARCHAR(50),
        country_name VARCHAR(255),
        parsed_obj TEXT,
        raw_response TEXT,
        request_meta TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) CHARSET=utf8mb4;
    """
    try:
        conn = _get_db_conn()
        with conn.cursor() as cur:
            cur.execute(create_sql)
        try:
            conn.close()
        except Exception:
            pass
        _TABLE_CREATED = True
    except Exception:
        # swallow table creation errors; caller will handle logging errors
        pass

# Replacement for previous lib.db.log_search_if_configured
def log_search_if_configured(player_id=None,
                             server_id=None,
                             nickname=None,
                             country_code=None,
                             country_name=None,
                             parsed_obj=None,
                             raw_response=None,
                             request_meta=None):
    """
    Insert a search/log record into the database. Swallows errors to avoid
    breaking calling code (matching previous behavior).
    """
    try:
        _ensure_table()
        conn = _get_db_conn()
        with conn.cursor() as cur:
            insert_sql = """
            INSERT INTO id_validation_logs
            (player_id, server_id, nickname, country_code, country_name, parsed_obj, raw_response, request_meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            parsed_json = json.dumps(parsed_obj, ensure_ascii=False) if parsed_obj is not None else None
            raw_json = json.dumps(raw_response, ensure_ascii=False) if raw_response is not None else None
            meta_json = json.dumps(request_meta, ensure_ascii=False) if request_meta is not None else None

            cur.execute(insert_sql, (
                str(player_id) if player_id is not None else None,
                str(server_id) if server_id is not None else None,
                nickname,
                country_code,
                country_name,
                parsed_json,
                raw_json,
                meta_json
            ))
        try:
            conn.close()
        except Exception:
            pass
    except Exception:
        # preserve previous behavior: do not raise from logging failures
        pass

# Collect request metadata to store with the search record.
def _get_request_meta():
    return {
        "client_ip": request.headers.get('X-Forwarded-For', request.remote_addr),
        "user_agent": request.headers.get('User-Agent'),
        "referer": request.headers.get('Referer'),
        "forwarded_proto": request.headers.get('X-Forwarded-Proto'),
        "host": request.headers.get('Host')
    }

def get_api_credentials(provider='smile', status=1):
	"""
	Fetch active API credentials from database for the given provider.
	Returns dict with uid, email, api_key or None if not found.
	"""
	try:
		conn = get_db_connection()
		with conn.cursor() as cursor:
			cursor.execute("""
				SELECT uid, email, api_key 
				FROM api_credentials 
				WHERE provider = %s AND status = %s 
				LIMIT 1
			""", (provider, status))
			result = cursor.fetchone()
		conn.close()
		
		if result:
			return {
				'uid': result.get('uid'),
				'email': result.get('email'),
				'api_key': result.get('api_key')
			}
		else:
			print(f"[ERROR] No active {provider} API credentials found in database")
			return None
	except Exception as e:
		print(f"[ERROR] Failed to fetch {provider} API credentials: {str(e)}")
		return None

def generate_smile_sign(params: dict, key: str) -> str:
	"""
	Generate Smile.one API sign parameter.
	All params are sorted by key, concatenated as key1=value1&key2=value2&...&key,
	then double MD5 hashed.
	"""
	sorted_items = sorted(params.items())
	sign_str = ''.join(f"{k}={v}&" for k, v in sorted_items)
	sign_str += key
	first_md5 = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
	final_md5 = hashlib.md5(first_md5.encode('utf-8')).hexdigest()
	return final_md5


def get_smile_role(userid, zoneid, product, productid, uid=None, email=None, key=None):
	"""
	Query role info for a specific user/product from Smile.one API.
	If uid, email, or key not provided, fetch from database.
	Returns parsed JSON or an error dict on failure.
	"""
	# Fetch credentials from DB if not provided
	if not all([uid, email, key]):
		creds = get_api_credentials('smile')
		if not creds:
			return {"error": "no_credentials", "message": "Smile.one API credentials not found"}
		uid = uid or creds.get('uid')
		email = email or creds.get('email')
		key = key or creds.get('api_key')
	
	api_url = "https://www.smile.one/smilecoin/api/getrole"
	now = int(time.time())
	params = {
		"uid": uid,
		"email": email,
		"userid": userid,
		"zoneid": zoneid,
		"product": product,
		"productid": productid,
		"time": now,
	}
	sign = generate_smile_sign(params, key)
	params["sign"] = sign
	try:
		resp = requests.post(api_url, data=params, timeout=10)
	except requests.RequestException as e:
		return {"error": "request_exception", "message": str(e)}
	try:
		return resp.json()
	except ValueError:
		return {"error": "invalid_json", "text": resp.text, "status_code": resp.status_code}

# Extract username from Smile.one API response
def extract_username_from_response(resp_json):
	if not isinstance(resp_json, dict):
		return None
	# common possible fields
	for key in ("username", "nick", "name", "player", "role", "nickname"):
		if key in resp_json:
			return resp_json[key]
	data = resp_json.get('data')
	if isinstance(data, dict):
		for key in ("username", "nick", "name", "player", "role", "nickname"):
			if key in data:
				return data[key]
	return None

# Create Smile.one order
def create_smile_order(userid, zoneid, product, productid, region=None, uid=None, email=None, key=None):
    """
    Create a purchase order via Smile.one API.
    Supports multiple regional endpoints:
    - Production (default): https://www.smile.one
    - Brazil: https://www.smile.one/br
    - Russia: https://www.smile.one/ru
    - Philippines: https://www.smile.one/ph
    
    If uid, email, or key not provided, fetch from database api_credentials table.
    
    API Response Format:
    Success: {"status": 200, "message": "success", "order_id": "..."}
    Error: {"status": error_code, "message": error_message}
    """
    # Fetch credentials from DB if not provided
    if not all([uid, email, key]):
        creds = get_api_credentials('smile')
        if not creds:
            return {
                'success': False,
                'status': 'error',
                'error_type': 'no_credentials',
                'message': 'Smile.one API credentials not found in database'
            }
        uid = uid or creds.get('uid')
        email = email or creds.get('email')
        key = key or creds.get('api_key')
    
    base_url = "https://www.smile.one"
    
    # Select regional endpoint (case-insensitive)
    region_lower = region.lower() if region else None
    if region_lower == "br":
        api_url = f"{base_url}/br/smilecoin/api/createorder"
    elif region_lower == "ru":
        api_url = f"{base_url}/ru/smilecoin/api/createorder"
    elif region_lower == "ph":
        api_url = f"{base_url}/ph/smilecoin/api/createorder"
    else:
        api_url = f"{base_url}/smilecoin/api/createorder"  # Production
    
    print(f"[DEBUG] Smile.one Order - ProductID: {productid}, Region: {region}, Region_Lower: {region_lower}, URL: {api_url}")
    
    # Prepare parameters (without sign initially)
    now = int(time.time())
    params = {
        "uid": uid,
        "email": email,
        "userid": userid,
        "zoneid": zoneid,
        "product": product,
        "productid": productid,
        "time": now
    }
    
    # Generate sign using double MD5 hash
    sign = generate_smile_sign(params, key)
    params["sign"] = sign
    
    try:
        # Make POST request to Smile.one API
        response = requests.post(api_url, data=params, timeout=10)
        result = response.json()
        
        # Smile.one API returns status code in response body
        # Success: status=200, Error: status!=200
        if result.get('status') == 200 and result.get('order_id'):
            return {
                'success': True,
                'status': 'success',
                'order_id': result.get('order_id'),
                'message': result.get('message')
            }
        else:
            return {
                'success': False,
                'status': 'error',
                'error_code': result.get('status'),
                'message': result.get('message', 'Unknown error')
            }
    except requests.RequestException as e:
        return {
            'success': False,
            'status': 'error',
            'error_type': 'request_exception',
            'message': str(e)
        }
    except ValueError as e:
        return {
            'success': False,
            'status': 'error',
            'error_type': 'json_parse_error',
            'message': f'Failed to parse API response: {str(e)}'
        }

def create_bushan_order(playerId, zoneId, productId, api_key):
    url = "https://1gamestopup.com/api/v1/api-service/order"

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    payload = {
        "playerId": str(playerId),
        "zoneId": str(zoneId),
        "productId": str(productId),
        "currency": "USD"   # ✅ MUST BE USD
    }

    print("[DEBUG] Bushan REQUEST PAYLOAD:", json.dumps(payload))
    print("[DEBUG] Bushan REQUEST HEADERS:", headers)

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)

        print("[DEBUG] Bushan HTTP STATUS:", r.status_code)
        print("[DEBUG] Bushan RAW RESPONSE:", r.text)

        if r.status_code != 200:
            return {
                "success": False,
                "message": f"HTTP {r.status_code}",
                "raw": r.text
            }

        data = r.json()

        if data.get("success") is True:
            return {
                "success": True,
                "order_id": data["data"]["orderId"],
                "raw": data
            }

        return {
            "success": False,
            "message": data.get("message", "Bushan order failed"),
            "raw": data
        }

    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

def create_xtreme_order(userid, zoneid, product_id, public_key=None, private_key=None):
    """
    Create an order via Xtreme API.
    If public_key or private_key not provided, use defaults.
    
    API Response Format:
    Success: {"success": true, "order_id": 12345, "status": "success", "balance_before": 1000.00, "balance_after": 950.00, "message": "Order created successfully"}
    Error: {"success": false, "error": "error_message", "balance": 500.00, "required": 1000.00, "message": "..."}
    """
    if not public_key:
        public_key = 'W6STC3K'
    if not private_key:
        private_key = 'ZNT91RQ5IYKW'
    
    url = "https://xtremeofficial.in/api/create-order"  # Update with actual Xtreme API endpoint
    
    payload = {
        "public_key": public_key,
        "private_key": private_key,
        "userid": str(userid),
        "zoneid": str(zoneid),
        "product_id": int(product_id),
        "payment_method": "wallet"
    }
    
    print(f"[DEBUG] Xtreme Order REQUEST - URL: {url}, Payload: {payload}")
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        
        print(f"[DEBUG] Xtreme HTTP STATUS: {r.status_code}")
        print(f"[DEBUG] Xtreme RAW RESPONSE: {r.text}")
        
        if r.status_code != 200:
            return {
                "success": False,
                "message": f"HTTP {r.status_code}",
                "raw": r.text
            }
        
        data = r.json()
        
        if data.get("success") is True:
            return {
                "success": True,
                "order_id": data.get("order_id"),
                "status": data.get("status", "success"),
                "balance_before": data.get("balance_before"),
                "balance_after": data.get("balance_after"),
                "message": data.get("message", "Order created successfully"),
                "raw": data
            }
        
        return {
            "success": False,
            "error": data.get("error"),
            "message": data.get("message", "Xtreme order failed"),
            "balance": data.get("balance"),
            "required": data.get("required"),
            "raw": data
        }
    
    except requests.RequestException as e:
        print(f"[ERROR] Xtreme API request failed: {str(e)}")
        return {
            "success": False,
            "message": f"Request failed: {str(e)}"
        }
    except ValueError as e:
        print(f"[ERROR] Xtreme API response parsing failed: {str(e)}")
        return {
            "success": False,
            "message": f"Response parsing failed: {str(e)}"
        }

def fetch_hopestore_checkip():
    """
    Fetch server-visible IP address from Hopestore helper endpoint.
    Falls back to ifconfig.me if Hopestore fails.
    Returns dict {'success': True, 'ip': 'x.x.x.x'} or {'success': False, 'error': '...'}
    """
    # Try Hopestore first
    try:
        url = "https://a-api.hopestore.id/v3/checkip"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json() if r.text else {}
        # Hopestore may return {'ip': 'x.x.x.x'} or plain text; handle both
        ip = None
        if isinstance(data, dict):
            ip = data.get('ip') or data.get('IP')
        if not ip:
            # fallback: try parse plain text
            text = r.text.strip()
            if text and len(text) < 50:  # sanity check for IP-like string
                ip = text
        if ip:
            return {'success': True, 'ip': ip, 'source': 'hopestore', 'raw': data}
    except Exception as e:
        print(f"[Hopestore CheckIP] Failed: {e}")
    
    # Fallback to ifconfig.me
    try:
        url = "https://ifconfig.me"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        ip = r.text.strip()
        if ip and len(ip) < 50:  # sanity check
            return {'success': True, 'ip': ip, 'source': 'ifconfig.me', 'raw': ip}
    except Exception as e:
        print(f"[ifconfig.me] Failed: {e}")
    
    # Fallback to icanhazip.com
    try:
        url = "https://icanhazip.com"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        ip = r.text.strip()
        if ip and len(ip) < 50:  # sanity check
            return {'success': True, 'ip': ip, 'source': 'icanhazip.com', 'raw': ip}
    except Exception as e:
        print(f"[icanhazip.com] Failed: {e}")
    
    return {'success': False, 'error': 'all_sources_failed', 'message': 'Could not fetch IP from any source'}


def create_hopestore_order(api_key, service_id, target, kontak, idtrx, callback=None, timeout=20):
    """
    Create an order at Hopestore.
    Returns dict with at least 'success' boolean and raw response.
    """
    url = "https://api.hopestore.id/order"
    payload = {
        'api_key': api_key,
        'service_id': str(service_id),
        'target': str(target),
        'kontak': str(kontak) if kontak is not None else '',
        'idtrx': str(idtrx)
    }
    if callback:
        payload['callback'] = callback

    try:
        r = requests.post(url, json=payload, timeout=timeout)
    except Exception as e:
        # network error
        return {'success': False, 'message': str(e)}

    try:
        data = r.json()
    except Exception:
        return {'success': False, 'message': 'invalid_json', 'raw_text': r.text, 'status_code': r.status_code}

    # Normalize response
    if data.get('status') is True:
        # success creating order; hopestore returns data object with 'id' (invoice)
        return {'success': True, 'raw': data, 'order_id': data.get('data', {}).get('id')}
    else:
        return {'success': False, 'message': data.get('msg') or 'hopestore_error', 'raw': data}


def get_hopstore_status(api_key, order_id, timeout=10):
    """
    Query Hopestore /status endpoint for a specific invoice/order_id.
    Returns {'success': True, 'status': 'success'|'pending'|... , 'raw': data}
    """
    url = "https://api.hopestore.id/status"
    payload = {'api_key': api_key, 'order_id': str(order_id)}
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        return {'success': False, 'message': str(e)}

    try:
        data = r.json()
    except Exception:
        return {'success': False, 'message': 'invalid_json', 'raw_text': r.text}

    if data.get('status') is True:
        d = data.get('data') or {}
        return {'success': True, 'status': d.get('status'), 'raw': data, 'keterangan': d.get('keterangan')}
    else:
        return {'success': False, 'message': data.get('msg', 'order_not_found'), 'raw': data}

def process_kanglei_success(data):
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        order_id = data.get("orderId") or data.get("order_id")
        utr = data.get("utr")
        amount = float(data.get("amount", 0))
        if not order_id or not utr or not amount:
            return

        # Lock order
        cur.execute("SELECT status, user_id FROM kanglei_orders WHERE order_id=%s", (order_id,))
        row = cur.fetchone()
        if not row or row["status"] == "SUCCESS":
            return
        user_id = row["user_id"]

        # Credit wallet
        cur.execute("SELECT balance FROM users WHERE id=%s", (user_id,))
        before_balance = float(cur.fetchone()["balance"])
        after_balance = before_balance + amount
        cur.execute("UPDATE users SET balance = balance + %s WHERE id=%s", (amount, user_id))

        # Wallet history
        cur.execute("""
            INSERT INTO wallet_history
            (user_id, amount_before, amount, transaction_type, reason, current_amount)
            VALUES (%s,%s,%s,'credit','UPI Payment',%s)
        """, (user_id, before_balance, amount, after_balance))

        # Transactions log
        cur.execute("""
            INSERT INTO transactions (user_id, txn_type, amount, utr, reference_id, description)
            VALUES (%s, 'credit', %s, %s, %s, %s)
        """, (user_id, amount, utr, order_id, 'UPI Topup'))

        # Wallet topups log
        cur.execute("""
            INSERT INTO wallet_topups (user_id, amount, order_id)
            VALUES (%s, %s, %s)
        """, (user_id, amount, order_id))

        # Update order
        cur.execute("""
            UPDATE kanglei_orders
            SET status='SUCCESS', utr=%s
            WHERE order_id=%s
        """, (utr, order_id))

        conn.commit()
        print("[KANGLEI] Payment credited:", order_id)

    except Exception as e:
        conn.rollback()
        print("[KANGLEI ERROR]", e)
    finally:
        conn.close()

# ==================== ORDER CREATION AFTER PAYMENT SUCCESS ====================
def process_create_order_success(data):
    """
    Create order in DB after payment success.
    data: dict with keys: db_user_id, user_id, zone_id, product_id, amount, utr
    Returns: (success, response) tuple
    """

    db_user_id = data.get('db_user_id')
    user_id = data.get('user_id')
    zone_id = data.get('zone_id')
    product_id = data.get('product_id')
    amount = float(data.get('amount', 0)) if data.get('amount') is not None else None
    utr = data.get('utr')

    # If any required field is missing, fetch from kanglei_orders using order_id/utr
    if not all([user_id, product_id, amount]):
        order_id = data.get('orderId') or data.get('order_id')
        conn = get_db_connection()
        with conn.cursor() as cur:
            if order_id:
                cur.execute("SELECT user_id, userid, zoneid, product_id, amount, utr FROM kanglei_orders WHERE order_id=%s", (order_id,))
            elif utr:
                cur.execute("SELECT user_id, userid, zoneid, product_id, amount, utr FROM kanglei_orders WHERE utr=%s", (utr,))
            else:
                return False, {'success': False, 'error': 'Missing order_id and utr'}
            row = cur.fetchone()
        conn.close()
        if not row:
            return False, {'success': False, 'error': 'Order not found in kanglei_orders'}
        db_user_id = row.get('user_id') or db_user_id
        user_id = row.get('userid') or user_id
        zone_id = row.get('zoneid') or zone_id
        product_id = row.get('product_id') or product_id
        amount = float(row.get('amount', 0))
        utr = row.get('utr') or utr

    connection = get_db_connection()
    cursor = connection.cursor(pymysql.cursors.DictCursor)
    try:
        # Check if user is a reseller
        cursor.execute("SELECT is_reseller FROM users WHERE id = %s", (db_user_id,))
        user_info = cursor.fetchone()
        is_user_reseller = bool(user_info.get('is_reseller', False)) if user_info else False

        # Fetch product
        cursor.execute("""
            SELECT p.product_name, p.price, p.reseller_price, p.product_id, p.api_provider, p.region, c.category_name, c.category_type
            FROM product p
            JOIN category c ON p.category = c.category_name
            WHERE p.id=%s AND p.status='active'
        """, (product_id,))
        product = cursor.fetchone()
        if not product:
            connection.rollback()
            return False, {'success': False, 'error': 'Product not found'}

        # Use reseller_price if user is reseller and reseller_price exists, otherwise use the provided amount
        if is_user_reseller and product.get('reseller_price'):
            final_amount = float(product['reseller_price'])
        else:
            final_amount = amount

        # Create order FIRST (pending)
        cursor.execute("""
            INSERT INTO orders
            (user_id, userid, zoneid, product_name, price, payment_method_id, status, create_date)
            VALUES (%s, %s, %s, %s, %s, 2, 'pending', NOW());
        """, (db_user_id, user_id, zone_id, product['product_name'], final_amount))
        order_id = cursor.lastrowid

        # Save UTR to used_utrs
        cursor.execute("INSERT INTO used_utrs (utr, user_id, amount, used_at) VALUES (%s, %s, %s, NOW())", 
                      (utr, db_user_id, amount))

        # Handle Smile.one and Bushan order creation
        if product['api_provider'].lower() == 'smile':
            # Check API provider balance FIRST
            balance_check = check_provider_balance_sufficient(
                provider='smile',
                required_amount=final_amount,
                region=product.get('region')
            )
            
            if not balance_check['sufficient']:
                # Insufficient balance - mark as processing and notify admin
                cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                connection.commit()
                
                # Fetch user email for notification
                cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                user_email_row = cursor.fetchone()
                user_email = user_email_row['email'] if user_email_row else 'N/A'
                
                send_order_insufficient_balance_notification(
                    order_id=order_id,
                    region=product.get('region'),
                    provider='Smile.one',
                    user_email=user_email,
                    user_id=user_id,
                    zone_id=zone_id,
                    product_name=product['product_name'],
                    category_name=product.get('category_name'),
                    payment_method='wallet',
                    required_balance=final_amount,
                    current_balance=balance_check['balance'],
                    utr=utr
                )
                
                return False, {
                    'success': False,
                    'error': 'Insufficient API provider balance',
                    'order_id': order_id,
                    'status': 'processing',
                    'message': 'Order created but API provider has insufficient balance. Admin has been notified.',
                    'provider_balance': balance_check['balance'],
                    'required_amount': final_amount
                }
            
            # Fetch API credentials from database
            creds = get_api_credentials('smile')
            if not creds:
                creds = {'uid': '913332', 'email': 'renedysanasam13@gmail.com', 'api_key': '3984a50cd116b3c06a05c784e16d0fb0'}
            product_ids = [p.strip() for p in product['product_id'].split('&') if p.strip()]
            smile_orders = []
            failed = []
            print(f"[DEBUG] Processing Smile.one order - Product: {product['product_name']}, Region: {product.get('region')}, ProductIDs: {product_ids}")
            for idx, pid in enumerate(product_ids, 1):
                result = create_smile_order(
                    userid=user_id,
                    zoneid=zone_id,
                    product='mobilelegends',
                    productid=pid,
                    region=product.get('region'),
                    uid=creds.get('uid'),
                    email=creds.get('email'),
                    key=creds.get('api_key')
                )
                smile_orders.append({
                    'product_id': pid,
                    'order_id': result.get('order_id'),
                    'success': result.get('success')
                })
                if not result.get('success'):
                    failed.append({
                        'product_id': pid,
                        'error': result.get('message')
                    })
            if failed:
                # Fetch user email and info for notification
                cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                user_email_row = cursor.fetchone()
                user_email = user_email_row['email'] if user_email_row else 'N/A'
                
                cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                connection.commit()
                
                # Send admin notification
                send_order_failure_notification(
                    order_id=order_id,
                    region=product.get('region'),
                    provider=product.get('api_provider'),
                    user_email=user_email,
                    user_id=user_id,
                    zone_id=zone_id,
                    product_name=product['product_name'],
                    category_name=product.get('category_name'),
                    payment_method='wallet',
                    utr=utr
                )
                
                return False, {
                    'success': False,
                    'error': 'Failed to create order',
                    'order_id': order_id,
                    'status': 'processing',
                    'failed_orders': failed,
                    'message': 'Order failed. Admin has been notified for manual processing.'
                }
            cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))
            # Log transaction
            cursor.execute("""
                INSERT INTO transactions
                (user_id, txn_type, amount, utr, description, created_at)
                VALUES (%s, 'debit', %s, %s, %s, NOW())
            """, (db_user_id, amount, utr, f"Order purchase #{order_id} - {product['product_name']}"))
            # Log wallet history
            cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
            user_balance = cursor.fetchone()
            amount_before = float(user_balance['balance'] or 0) if user_balance else 0.0
            cursor.execute("""
                INSERT INTO wallet_history
                (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
            """, (db_user_id, amount_before, amount, amount_before,
                  f"Order purchase #{order_id} - {product['product_name']} (UTR: {utr})"))
        elif product['api_provider'].lower() == 'bushan':
            # Check API provider balance FIRST
            balance_check = check_provider_balance_sufficient(
                provider='bushan',
                required_amount=final_amount,
                region=None
            )
            
            if not balance_check['sufficient']:
                # Insufficient balance - mark as processing and notify admin
                cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                connection.commit()
                
                # Fetch user email for notification
                cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                user_email_row = cursor.fetchone()
                user_email = user_email_row['email'] if user_email_row else 'N/A'
                
                send_order_insufficient_balance_notification(
                    order_id=order_id,
                    region=None,
                    provider='Bushan (1GameStopUp)',
                    user_email=user_email,
                    user_id=user_id,
                    zone_id=zone_id,
                    product_name=product['product_name'],
                    category_name=product.get('category_name'),
                    payment_method='wallet',
                    required_balance=final_amount,
                    current_balance=balance_check['balance'],
                    utr=utr
                )
                
                return False, {
                    'success': False,
                    'error': 'Insufficient API provider balance',
                    'order_id': order_id,
                    'status': 'processing',
                    'message': 'Order created but API provider has insufficient balance. Admin has been notified.',
                    'provider_balance': balance_check['balance'],
                    'required_amount': final_amount
                }
            
            product_ids = [p.strip() for p in product['product_id'].split('&') if p.strip()]
            if not user_id or not zone_id:
                connection.rollback()
                return False, {
                    "success": False,
                    "error": "Invalid playerId or zoneId"
                }
            creds = get_api_credentials('bushan')
            if not creds:
                creds = {'api_key': 'busan_b372f70f97df1fc40028bd2c32cdbf4eb2522c183004c6a41acf83e8587e9189'}
            bushan_orders = []
            failed = []
            for idx, pid in enumerate(product_ids, 1):
                result = create_bushan_order(
                    playerId=user_id,
                    zoneId=zone_id,
                    productId=pid,
                    api_key=creds.get('api_key')
                )
                bushan_orders.append({
                    'index': idx,
                    'product_id': pid,
                    'response': result
                })
                if not result.get('success'):
                    failed.append({
                        'product_id': pid,
                        'error': result.get('message')
                    })
            if failed:
                # Fetch user email and info for notification
                cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                user_email_row = cursor.fetchone()
                user_email = user_email_row['email'] if user_email_row else 'N/A'
                
                cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                connection.commit()
                
                # Send admin notification
                send_order_failure_notification(
                    order_id=order_id,
                    region=product.get('region'),
                    provider=product.get('api_provider'),
                    user_email=user_email,
                    user_id=user_id,
                    zone_id=zone_id,
                    product_name=product['product_name'],
                    category_name=product.get('category_name'),
                    payment_method='wallet',
                    utr=utr
                )
                
                return False, {
                    'success': False,
                    'error': 'Failed to create order',
                    'order_id': order_id,
                    'status': 'processing',
                    'failed_orders': failed,
                    'message': 'Order failed. Admin has been notified for manual processing.'
                }
            cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))
            # Log transaction
            cursor.execute("""
                INSERT INTO transactions
                (user_id, txn_type, amount, utr, description, created_at)
                VALUES (%s, 'debit', %s, %s, %s, NOW())
            """, (db_user_id, amount, utr, f"Order purchase #{order_id} - {product['product_name']}"))
            # Log wallet history
            cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
            user_balance = cursor.fetchone()
            amount_before = float(user_balance['balance'] or 0) if user_balance else 0.0
            cursor.execute("""
                INSERT INTO wallet_history
                (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
            """, (db_user_id, amount_before, amount, amount_before,
                  f"Order purchase #{order_id} - {product['product_name']} (UTR: {utr})"))
        elif product['api_provider'].lower() == 'xtreme':
            # Check API provider balance FIRST
            balance_check = check_provider_balance_sufficient(
                provider='xtreme',
                required_amount=final_amount,
                region=None
            )
            
            if not balance_check['sufficient']:
                # Insufficient balance - mark as processing and notify admin
                cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                connection.commit()
                
                # Fetch user email for notification
                cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                user_email_row = cursor.fetchone()
                user_email = user_email_row['email'] if user_email_row else 'N/A'
                
                send_order_insufficient_balance_notification(
                    order_id=order_id,
                    region=None,
                    provider='Xtreme',
                    user_email=user_email,
                    user_id=user_id,
                    zone_id=zone_id,
                    product_name=product['product_name'],
                    category_name=product.get('category_name'),
                    payment_method='wallet',
                    required_balance=final_amount,
                    current_balance=balance_check['balance'],
                    utr=utr
                )
                
                return False, {
                    'success': False,
                    'error': 'Insufficient API provider balance',
                    'order_id': order_id,
                    'status': 'processing',
                    'message': 'Order created but API provider has insufficient balance. Admin has been notified.',
                    'provider_balance': balance_check['balance'],
                    'required_amount': final_amount
                }
            
            # Get Xtreme API credentials (use defaults if not in DB)
            creds = get_api_credentials('xtreme')
            if not creds:
                creds = {'public_key': 'W6STC3K', 'private_key': 'ZNT91RQ5IYKW'}
            
            result = create_xtreme_order(
                userid=user_id,
                zoneid=zone_id,
                product_id=product['product_id'],
                public_key=creds.get('public_key') or 'W6STC3K',
                private_key=creds.get('private_key') or 'ZNT91RQ5IYKW'
            )
            
            if not result.get('success'):
                # Fetch user email and info for notification
                cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                user_email_row = cursor.fetchone()
                user_email = user_email_row['email'] if user_email_row else 'N/A'
                
                cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                connection.commit()
                
                # Send admin notification
                send_order_failure_notification(
                    order_id=order_id,
                    region=None,
                    provider=product.get('api_provider'),
                    user_email=user_email,
                    user_id=user_id,
                    zone_id=zone_id,
                    product_name=product['product_name'],
                    category_name=product.get('category_name'),
                    payment_method='wallet',
                    utr=utr
                )
                
                return False, {
                    'success': False,
                    'error': 'Failed to create order',
                    'order_id': order_id,
                    'status': 'processing',
                    'error_details': result.get('message'),
                    'message': 'Order failed. Admin has been notified for manual processing.'
                }
            
            cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))
            # Log transaction
            cursor.execute("""
                INSERT INTO transactions
                (user_id, txn_type, amount, utr, description, created_at)
                VALUES (%s, 'debit', %s, %s, %s, NOW())
            """, (db_user_id, amount, utr, f"Order purchase #{order_id} - {product['product_name']}"))
            # Log wallet history
            cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
            user_balance = cursor.fetchone()
            amount_before = float(user_balance['balance'] or 0) if user_balance else 0.0
            cursor.execute("""
                INSERT INTO wallet_history
                (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
            """, (db_user_id, amount_before, amount, amount_before,
                  f"Order purchase #{order_id} - {product['product_name']} (UTR: {utr})"))
        else:
            # For non-Smile/Bushan/Xtreme providers, mark as pending for manual processing
            cursor.execute("UPDATE orders SET status='pending' WHERE id=%s", (order_id,))
            send_telegram_notification(f"New Manual Order From {product['category_name']}\nOrder ID : {order_id}\nProduct : {product['product_name']}\nAmount : {amount}\nUTR : {utr}\nProvider : {product['api_provider']}\n\nPlease process this order manually.")
            cursor.execute("""
                INSERT INTO transactions
                (user_id, txn_type, amount, utr, description, created_at)
                VALUES (%s, 'pending', %s, %s, %s, NOW())
            """, (db_user_id, amount, utr, f"Order purchase #{order_id} - {product['product_name']} - Pending Manual Processing"))
        connection.commit()
        # Determine returned status: mark as 'success' for Smile, Bushan, and Xtreme (auto-fulfilled),
        # otherwise keep 'pending' for manual providers.
        provider = (product.get('api_provider') or '').lower()
        returned_status = 'success' if provider in ('smile', 'bushan', 'xtreme') else 'pending'
        returned_message = 'Order created successfully' if returned_status == 'success' else 'Order created. Awaiting manual processing.'
        return True, {
            'success': True,
            'order_id': order_id,
            'status': returned_status,
            'message': returned_message,
            'utr': utr,
            'amount': amount
        }
    except Exception as e:
        connection.rollback()
        print(f"[ERROR] Order creation failed: {str(e)}")
        return False, {'success': False, 'error': str(e)}
    finally:
        cursor.close()
        connection.close()

def get_smile_product_list(product='mobilelegends', region=None, uid=None, email=None, key=None):
    """
    Fetch product list from Smile.one `productlist` API.
    Returns dict with 'success' and either 'data' or error info.
    """
    # Fetch credentials if not provided
    if not all([uid, email, key]):
        creds = get_api_credentials('smile')
        if not creds:
            return {'success': False, 'error': 'no_credentials', 'message': 'Smile.one API credentials not found in database'}
        uid = uid or creds.get('uid')
        email = email or creds.get('email')
        key = key or creds.get('api_key')

    base_url = "https://www.smile.one"
    if region == "br":
        api_url = f"{base_url}/br/smilecoin/api/productlist"
    elif region == "ru":
        api_url = f"{base_url}/ru/smilecoin/api/productlist"
    elif region == "ph":
        api_url = f"{base_url}/ph/smilecoin/api/productlist"
    else:
        api_url = f"{base_url}/smilecoin/api/productlist"

    now = int(time.time())
    params = {
        'uid': uid,
        'email': email,
        'product': product,
        'time': now,
    }
    params['sign'] = generate_smile_sign(params, key)

    try:
        resp = requests.post(api_url, data=params, timeout=10)
    except requests.RequestException as e:
        return {'success': False, 'error': 'request_exception', 'message': str(e)}

    try:
        result = resp.json()
    except ValueError:
        return {'success': False, 'error': 'invalid_json', 'text': resp.text, 'status_code': resp.status_code}

    # Expecting status==200 and data.product list
    if result.get('status') == 200 and isinstance(result.get('data'), dict):
        return {'success': True, 'status': 'success', 'data': result.get('data'), 'message': result.get('message')}
    else:
        return {'success': False, 'status': 'error', 'error_code': result.get('status'), 'message': result.get('message', 'Unknown error'), 'raw': result}


def get_smile_balance(region=None, uid=None, email=None, key=None):
    """
    Query Smile.one account points using `querypoints` API.
    Returns dict: {'success': True, 'smile_points': float} on success or {'success': False, 'message': ...}
    """
    if not all([uid, email, key]):
        creds = get_api_credentials('smile')
        if not creds:
            return {'success': False, 'error': 'no_credentials', 'message': 'Smile.one API credentials not found'}
        uid = uid or creds.get('uid')
        email = email or creds.get('email')
        key = key or creds.get('api_key')

    base_url = "https://www.smile.one"
    if region == "br":
        api_url = f"{base_url}/br/smilecoin/api/querypoints"
    elif region == "ru":
        api_url = f"{base_url}/ru/smilecoin/api/querypoints"
    elif region == "ph":
        api_url = f"{base_url}/ph/smilecoin/api/querypoints"
    else:
        api_url = f"{base_url}/smilecoin/api/querypoints"

    now = int(time.time())
    params = {
        'uid': uid,
        'email': email,
        'product': 'mobilelegends',
        'time': now,
    }
    params['sign'] = generate_smile_sign(params, key)

    try:
        resp = requests.post(api_url, data=params, timeout=8)
    except requests.RequestException as e:
        return {'success': False, 'error': 'request_exception', 'message': str(e)}

    try:
        result = resp.json()
    except ValueError:
        return {'success': False, 'error': 'invalid_json', 'text': resp.text, 'status_code': resp.status_code}

    if result.get('status') == 200:
        # Some responses return smile_points as string
        pts = result.get('smile_points') or result.get('points') or None
        try:
            pts_val = float(pts) if pts is not None else 0.0
        except Exception:
            pts_val = 0.0
        return {'success': True, 'smile_points': pts_val, 'raw': result}
    else:
        return {'success': False, 'error_code': result.get('status'), 'message': result.get('message', 'Unknown error'), 'raw': result}

def get_1gamestopup_balance(api_key=None, currency='INR'):
	"""
	Fetch account balance from 1gamestopup API.
	Returns dict: {'success': True, 'balance': float, 'currency': str} on success
	or {'success': False, 'message': ...} on failure.
	"""
	# Use hardcoded API key (do not fetch from database)
	if not api_key:
		api_key = 'busan_b372f70f97df1fc40028bd2c32cdbf4eb2522c183004c6a41acf83e8587e9189'
	
	try:
		url = "https://1gamestopup.com/api/v1/api-service/balance"
		headers = {
			'x-api-key': api_key,
			'Content-Type': 'application/json'
		}
		params = {'currency': currency}
		
		resp = requests.get(url, headers=headers, params=params, timeout=10)
		resp.raise_for_status()
	except requests.RequestException as e:
		print(f"[ERROR] 1gamestopup API error: {str(e)}")
		return {'success': False, 'error': 'api_error', 'message': str(e)}
	
	try:
		resp_json = resp.json()
	except ValueError:
		return {'success': False, 'error': 'invalid_json', 'message': 'Invalid JSON response from 1gamestopup'}
	
	if resp_json.get('success') and resp_json.get('statusCode') == 200:
		balance = resp_json.get('data', {}).get('balance')
		if balance is not None:
			# Extract numeric value if it includes currency text (e.g., "50 INR" -> 50)
			try:
				balance = float(str(balance).split()[0])
			except (ValueError, IndexError):
				balance = 0
			return {'success': True, 'balance': balance, 'currency': currency}
	
	error_msg = resp_json.get('message', 'Unknown error')
	return {'success': False, 'error': 'api_error', 'message': error_msg}

def get_hopstore_balance(api_key=None):
    """
    Fetch Hopestore account balance.
    Returns dict: {'success': True, 'balance': float, 'raw': resp_json} or {'success': False, 'message': ...}
    """
    # prefer provided api_key, fall back to DB-stored credential (provider 'hopestore'), then to default
    if not api_key:
        try:
            creds = get_api_credentials('hopestore')
            if creds and creds.get('api_key'):
                api_key = creds.get('api_key')
        except Exception:
            api_key = None

    if not api_key:
        api_key = 'APILEQNC71765200725999'

    url = "https://api.hopestore.id/saldo"
    payload = {"api_key": api_key}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[Hopestore Balance Error] {e}")
        # attempt to fetch hopestore visible IP for debugging
        ip_info = fetch_hopestore_checkip()
        res = {'success': False, 'message': f'API request failed: {str(e)}', 'checkip': ip_info}
        return res

    try:
        data = resp.json()
    except ValueError:
        # attempt to fetch hopestore visible IP for debugging
        ip_info = fetch_hopestore_checkip()
        return {'success': False, 'message': 'Invalid JSON response', 'raw_text': resp.text, 'checkip': ip_info}

    if data.get('status') is True:
        d = data.get('data') or {}
        # data may be an object with 'saldo'
        saldo = None
        if isinstance(d, dict):
            saldo = d.get('saldo') or d.get('balance')
        try:
            saldo_val = float(saldo) if saldo is not None else 0.0
        except Exception:
            saldo_val = 0.0
        return {'success': True, 'balance': saldo_val, 'raw': data}
    else:
        # include checkip info to aid debugging when hopestore reports failure
        ip_info = fetch_hopestore_checkip()
        return {'success': False, 'message': data.get('msg', 'Failed to fetch balance'), 'raw': data, 'checkip': ip_info}


@app.route('/api/checkip', methods=['GET'])
def api_checkip():
    """API route to check server-visible IP address from Hopestore."""
    res = fetch_hopestore_checkip()
    return jsonify(res)

@app.route('/api/hopstore_balance', methods=['GET'])
def api_hopstore_balance():
    """API route to return Hopestore balance. Optional query param `api_key` to override."""
    api_key = request.args.get('api_key') or None
    res = get_hopstore_balance(api_key=api_key)
    return jsonify(res)

@app.route('/api/smile_products', methods=['GET', 'POST'])
def api_smile_products():
    """Return Smile.one product list. Accepts optional `region` and `product` params."""
    region = request.values.get('region')
    product = request.values.get('product', 'mobilelegends')

    creds = get_api_credentials('smile')
    if not creds:
        return jsonify({'ok': False, 'error': 'no_credentials', 'message': 'Smile.one API credentials not configured'})

    res = get_smile_product_list(product=product, region=region, uid=creds.get('uid'), email=creds.get('email'), key=creds.get('api_key'))
    return jsonify(res)

# Home route
@app.route('/', methods=['GET'])
def index():
    user = None
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, username, email, phone FROM users WHERE id=%s", (session['user_id'],))
                user = cursor.fetchone()
            conn.close()
        except Exception:
            user = None
    return render_template('index.html', user=user)

@app.route('/auth')
def auth():
    return render_template('auth.html')

@app.route('/send_otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    otp = generate_otp()
    session['otp'] = otp
    session['otp_email'] = email
    try:
        send_otp_email(email, otp)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')
    name = data.get('name')
    password = data.get('password')
    phone = data.get('phone')
    
    if session.get('otp_email') != email or session.get('otp') != otp:
        return jsonify({'error': 'Invalid OTP'}), 400
    
    # Hash password
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Check uniqueness: username, email, phone must not already exist
            cursor.execute("SELECT id FROM users WHERE username=%s OR email=%s OR phone=%s LIMIT 1", (name, email, phone))
            if cursor.fetchone():
                return jsonify({'error': 'Username, email or phone already registered'}), 400

            # Insert new user (include phone)
            cursor.execute("INSERT INTO users (username, email, phone, password) VALUES (%s, %s, %s, %s)", (name, email, phone, hashed.decode('utf-8')))
            conn.commit()
            
            # Get the newly created user ID
            user_id = cursor.lastrowid
            
            # Generate API keys and referrer ID
            referrer_id = generate_referrer_id()
            public_key = generate_api_key(7)
            private_key = generate_api_key(12)
            
            # Update user with generated keys
            cursor.execute("""
                UPDATE users 
                SET referrer_id = %s, public_key = %s, private_key = %s 
                WHERE id = %s
            """, (referrer_id, public_key, private_key, user_id))
            conn.commit()
            
        conn.close()
        session.pop('otp', None)
        session.pop('otp_email', None)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    # If the client is attempting an admin login, they should send {"admin": true}
    admin_login = bool(data.get('admin'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Allow login by email OR phone number
            cursor.execute("SELECT id, password, referrer_id, public_key, private_key, is_admin FROM users WHERE email = %s OR phone = %s LIMIT 1", (email, email))
            user = cursor.fetchone()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            user_id = user['id']
            
            # Check if referrer_id, public_key, or private_key are empty
            if not user.get('referrer_id') or not user.get('public_key') or not user.get('private_key'):
                # Generate missing keys
                referrer_id = generate_referrer_id() if not user.get('referrer_id') else user['referrer_id']
                public_key = generate_api_key(7) if not user.get('public_key') else user['public_key']
                private_key = generate_api_key(12) if not user.get('private_key') else user['private_key']
                
                # Update user with generated keys
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE users 
                        SET referrer_id = %s, public_key = %s, private_key = %s 
                        WHERE id = %s
                    """, (referrer_id, public_key, private_key, user_id))
                    conn.commit()
            
            # If this is an admin login request, ensure the user is admin
            if admin_login:
                if not user.get('is_admin') or int(user.get('is_admin')) != 1:
                    conn.close()
                    return jsonify({'error': 'Not authorized', 'redirect': url_for('index')}), 403

            # Make session persistent for the configured lifetime (24 hours)
            session.permanent = True
            session['user_id'] = user_id
            conn.close()
            return jsonify({'success': True})
        else:
            conn.close()
            return jsonify({'error': 'Invalid credentials'}), 401
    except pymysql.Error as e:
        if 'Unknown column' in str(e):
            # Columns don't exist yet, try basic select
            try:
                conn = get_db_connection()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id, password, is_admin FROM users WHERE email = %s", (email,))
                    user = cursor.fetchone()

                if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                    # enforce admin requirement for admin login attempts
                    if admin_login:
                        if not user.get('is_admin') or int(user.get('is_admin')) != 1:
                            conn.close()
                            return jsonify({'error': 'Not authorized', 'redirect': url_for('index')}), 403

                    session['user_id'] = user['id']
                    conn.close()
                    return jsonify({'success': True})
                else:
                    conn.close()
                    return jsonify({'error': 'Invalid credentials'}), 401
            except Exception as e2:
                return jsonify({'error': str(e2)}), 500
        else:
            return jsonify({'error': str(e)}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')
    # Generate a secure reset token, store it and email a reset URL
    try:
        # ensure table exists
        _ensure_password_resets_table()

        # generate token and expiry (10 minutes)
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')

        # store token in DB
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO password_resets (email, token, expires_at) VALUES (%s, %s, %s)", (email, token, expires_at))
                conn.commit()
            try:
                conn.close()
            except Exception:
                pass
        except Exception:
            # swallow DB errors but continue to send email (avoid leaking info)
            pass

        # send reset email
        send_reset_email(email, token)
        return jsonify({'message': 'Password reset link sent'})
    except Exception as e:
        print(f"[ERROR] forgot_password failed: {e}")
        traceback.print_exc()
        return jsonify({'message': 'Error sending reset email', 'error': str(e)}), 500

@app.route('/reset_pasword', methods=['GET'])
def reset_pasword_page():
    """Serve the client-side redirect page which reads `?token=` and forwards
    the browser to `/reset_password?token=...` (or the front-end route).
    """
    token = request.args.get('token')
    try:
        return render_template('reset_pasword.html', token=token)
    except Exception:
        # If template rendering fails for any reason, return a minimal HTML
        # response that performs a client-side redirect as a fallback.
        if token:
            redirect_url = f"/reset_password?token={token}"
        else:
            redirect_url = '/reset_password'
        fallback_html = f"<html><head><meta http-equiv=\"refresh\" content=\"0;url={redirect_url}\" /></head><body>Redirecting...</body></html>"
        return (fallback_html, 200)

@app.route('/check_login')
def check_login():
    return jsonify({'logged_in': 'user_id' in session})


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    """Handle password reset form display (GET) and submission (POST).
    POST expects form-encoded or JSON body with `token` and `password`.
    """
    if request.method == 'GET':
        token = request.args.get('token')
        try:
            return render_template('reset_password.html', token=token)
        except Exception:
            # Minimal fallback HTML form
            token_input = f'<input type="hidden" name="token" value="{token}">' if token else ''
            return (f"<html><body><form method=\"post\">{token_input}<input name=\"password\" type=\"password\" placeholder=\"New password\" required><button type=\"submit\">Reset</button></form></body></html>", 200)

    # POST: perform reset
    # Support form or JSON
    data = None
    if request.form:
        data = request.form
    else:
        data = request.get_json(silent=True) or {}

    token = data.get('token') or request.args.get('token')
    new_password = data.get('password') or data.get('new_password')

    if not token or not new_password:
        return jsonify({'error': 'token and password are required'}), 400

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT email, expires_at, used FROM password_resets WHERE token=%s LIMIT 1", (token,))
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'invalid_token'}), 400
            if row.get('used'):
                return jsonify({'error': 'token_already_used'}), 400

            expires_at = row.get('expires_at')
            # Normalize expires_at to datetime for comparison
            if isinstance(expires_at, str):
                try:
                    expires_dt = datetime.strptime(expires_at, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    expires_dt = datetime.now() + timedelta(seconds=0)
            else:
                expires_dt = expires_at
            
            if expires_dt < datetime.now():
                return jsonify({'error': 'token_expired'}), 400

            user_email = row.get('email')

            # Hash new password and update users table
            hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, user_email))

            # Mark token used
            cursor.execute("UPDATE password_resets SET used=1 WHERE token=%s", (token,))
            conn.commit()
        try:
            conn.close()
        except Exception:
            pass

        return jsonify({'success': True, 'message': 'Password updated successfully'})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# API endpoint to get categories
@app.route('/api/categories', methods=['GET'])
def api_categories():
    category_type = request.args.get('type')  # Optional filter by type
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if category_type:
                cursor.execute("""
                    SELECT id, category_name, image as category_image, status, category_type
                    FROM category
                    WHERE status = 1 AND category_type = %s
                    ORDER BY created_at DESC
                """, (category_type,))
            else:
                cursor.execute("""
                    SELECT id, category_name, image as category_image, status, category_type
                    FROM category
                    WHERE status = 1
                    ORDER BY category_type, created_at ASC
                """)
            categories = cursor.fetchall()
        conn.close()
        
        # Group by category_type if no specific type filter
        if not category_type:
            grouped = {}
            for cat in categories:
                cat_type = cat.get('category_type', 'OTHER GAME')
                if cat_type not in grouped:
                    grouped[cat_type] = []
                grouped[cat_type].append(cat)
            return jsonify({'categories': categories, 'grouped': grouped})
        
        return jsonify({'categories': categories})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/category/<path:category_name>')
def api_category_detail(category_name):
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, category_name, description, image, status, category_type
                FROM category
                WHERE LOWER(category_name) = LOWER(%s) AND status = 1
                LIMIT 1
            """, (category_name,))
            category = cursor.fetchone()
        conn.close()
        
        if not category:
            return jsonify({'error': 'Category not found'}), 404
        
        return jsonify({
            'id': category['id'],
            'category_name': category['category_name'],
            'description': category['description'],
            'image': category['image'],
            'category_type': category['category_type']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API endpoint to get products by category
@app.route('/api/products', methods=['GET'])
def api_products():
    category_name = request.args.get('category')
    if not category_name:
        return jsonify({'error': 'category parameter required'}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Try querying by category_id join first (preferred method if category_id is set)
            cursor.execute("""
                SELECT p.id, p.product_name, p.price, p.reseller_price, p.product_id, 
                       p.image, p.status, p.api_provider, p.region, c.category_name
                FROM product p
                LEFT JOIN category c ON p.category_id = c.id
                WHERE (c.category_name = %s OR p.category = %s) AND p.status = 'active'
                ORDER BY p.id ASC
            """, (category_name, category_name))
            products = cursor.fetchall()
            
            # Check if user is a reseller
            is_user_reseller = False
            if 'user_id' in session:
                cursor.execute("SELECT is_reseller FROM users WHERE id = %s", (session['user_id'],))
                user_info = cursor.fetchone()
                if user_info:
                    is_user_reseller = bool(user_info.get('is_reseller', False))
            
            # If user is a reseller, use reseller_price instead of regular price
            if is_user_reseller:
                for product in products:
                    if product.get('reseller_price'):
                        product['display_price'] = product['reseller_price']
                        product['is_reseller_price'] = True
                    else:
                        product['display_price'] = product['price']
                        product['is_reseller_price'] = False
            else:
                for product in products:
                    product['display_price'] = product['price']
                    product['is_reseller_price'] = False
            
            return jsonify({'products': products, 'is_user_reseller': is_user_reseller})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()

# API endpoint to get payment methods
@app.route('/api/payment_methods', methods=['GET'])
def api_payment_methods():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, method_name, image
                FROM payment_method
                WHERE status = 1
                ORDER BY created_at DESC
            """)
            methods = cursor.fetchall()
        conn.close()
        return jsonify({'payment_methods': methods})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API endpoint to get active banners
@app.route('/api/banners', methods=['GET'])
def api_banners():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, image
                FROM banner
                WHERE status = 1
                ORDER BY created_at DESC
            """)
            banners = cursor.fetchall()
        conn.close()
        return jsonify({'success': True, 'banners': banners})
    except Exception as e:
        print(f"[ERROR] Banners API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Category page route - Handles both underscores and spaces
@app.route('/category/<path:category_name>')
def category_page(category_name):
    # Convert underscores to spaces for database query
    # e.g., /category/Mobile_Legends -> "Mobile Legends"
    # Also handles URL-encoded spaces: MLBB%20IND -> MLBB IND
    from urllib.parse import unquote
    
    # Decode URL-encoded characters
    category_display_name = unquote(category_name)
    # Also replace underscores with spaces
    category_display_name = category_display_name.replace('_', ' ')
    
    # Fetch category_type, description, and image from DB
    category_type = 'OTHER GAME'
    description = ''
    image = ''
    user = None
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT category_type, description, image FROM category WHERE LOWER(category_name) = LOWER(%s) LIMIT 1", (category_display_name,))
            row = cursor.fetchone()
            if row:
                category_type = row.get('category_type', 'OTHER GAME')
                description = row.get('description', '') or ''
                image = row.get('image', '') or ''
        conn.close()
    except Exception:
        pass
    
    # Fetch user data if logged in
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, username, email, phone, balance, brl_balance, is_reseller, is_admin FROM users WHERE id = %s", (session['user_id'],))
                user = cursor.fetchone()
                if user:
                    user['balance'] = float(user.get('balance') or 0.00)
                    user['brl_balance'] = float(user.get('brl_balance') or 0.00)
                    user['is_reseller'] = bool(user.get('is_reseller', False))
            conn.close()
        except Exception:
            pass

    is_reseller = bool(user.get('is_reseller', False)) if user else False
    
    return render_template(
        'product.html',
        category_name=category_display_name,
        category_type=category_type,
        description=description,
        image=image,
        user=user,
        is_reseller=is_reseller
    )

# API endpoint to get total user count
@app.route('/api/stats/total_users', methods=['GET'])
def api_total_users():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM users")
            result = cursor.fetchone()
        conn.close()
        total = result.get('total', 0) if result else 0
        return jsonify({'total_users': total})
    except Exception as e:
        print(f"[ERROR] Failed to fetch total users: {str(e)}")
        return jsonify({'error': str(e)}), 500

# API endpoint to get order success rate
@app.route('/api/stats/success_rate', methods=['GET'])
def api_success_rate():
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as total FROM orders")
            total_result = cursor.fetchone()
            total_orders = total_result.get('total', 0) if total_result else 0
            
            cursor.execute("SELECT COUNT(*) as successful FROM orders WHERE status = 'success'")
            success_result = cursor.fetchone()
            successful_orders = success_result.get('successful', 0) if success_result else 0
        conn.close()
        
        success_rate = 0
        if total_orders > 0:
            success_rate = round((successful_orders / total_orders) * 100, 2)
        
        return jsonify({
            'success_rate': success_rate,
            'successful_orders': successful_orders,
            'total_orders': total_orders
        })
    except Exception as e:
        print(f"[ERROR] Failed to fetch success rate: {str(e)}")
        return jsonify({'error': str(e)}), 500

# API endpoint to get username from Smile.one
@app.route('/api/get_username', methods=['POST'])
def api_get_username():
	# Accept JSON or form-encoded bodies
	data = request.get_json(silent=True) or request.form
	userid = data.get('USERID') or data.get('userid') or ''
	zoneid = data.get('ZONEID') or data.get('zoneid') or ''
	
	if not userid or not zoneid:
		return jsonify({'ok': False, 'error': 'USERID and ZONEID required'})
	
	# Fetch credentials from database
	creds = get_api_credentials('smile')
	if not creds:
		return jsonify({'ok': False, 'error': 'Smile.one API credentials not configured'})
	
	resp = get_smile_role(
		userid=userid,
		zoneid=zoneid,
		product='mobilelegends',
		productid='13',
		uid=creds.get('uid'),
		email=creds.get('email'),
		key=creds.get('api_key')
	)
	username = extract_username_from_response(resp)
	return jsonify({
		'ok': True,
		'username': username,
		'raw': resp
	})



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            # Query all available columns including brl_balance
            cursor.execute("""
                SELECT id, username, email, phone, balance, brl_balance, created_at, referrer_id, 
                       public_key, private_key, is_reseller, is_admin, language, knd_coin, membership_type
                FROM users 
                WHERE id = %s
            """, (session['user_id'],))
            user = cursor.fetchone()
            
            if not user:
                return redirect(url_for('auth'))
            
            # Ensure all fields have defaults if NULL
            user['phone'] = user.get('phone') or None
            user['balance'] = float(user.get('balance') or 0.00)
            user['brl_balance'] = float(user.get('brl_balance') or 0.00)
            user['created_at'] = user.get('created_at')
            user['referrer_id'] = user.get('referrer_id')
            user['public_key'] = user.get('public_key')
            user['private_key'] = user.get('private_key')
            user['is_reseller'] = bool(user.get('is_reseller', False))
            user['is_admin'] = bool(user.get('is_admin', False))
                        
            # Get dashboard statistics
            stats = {}
            try:
                # Total orders
                cursor.execute("SELECT COUNT(*) as total_orders FROM orders WHERE user_id = %s", (session['user_id'],))
                stats['total_orders'] = cursor.fetchone()['total_orders']
                
                # Total spent
                cursor.execute("SELECT COALESCE(SUM(price), 0) as total_spent FROM orders WHERE user_id = %s AND status IN ('success', 'processing')", (session['user_id'],))
                stats['total_spent'] = cursor.fetchone()['total_spent']
                
                # Average order value
                if stats['total_orders'] > 0:
                    stats['avg_order'] = stats['total_spent'] / stats['total_orders']
                else:
                    stats['avg_order'] = 0
                
                # Pending orders
                cursor.execute("SELECT COUNT(*) as pending_orders FROM orders WHERE user_id = %s AND status IN ('pending', 'processing')", (session['user_id'],))
                stats['pending_orders'] = cursor.fetchone()['pending_orders']
                
                # Monthly growth (compare current month vs last month)
                cursor.execute("""
                    SELECT 
                        COUNT(CASE WHEN MONTH(create_date) = MONTH(CURRENT_DATE()) AND YEAR(create_date) = YEAR(CURRENT_DATE()) THEN 1 END) as current_month,
                        COUNT(CASE WHEN MONTH(create_date) = MONTH(CURRENT_DATE() - INTERVAL 1 MONTH) AND YEAR(create_date) = YEAR(CURRENT_DATE() - INTERVAL 1 MONTH) THEN 1 END) as last_month
                    FROM orders 
                    WHERE user_id = %s AND create_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 MONTH)
                """, (session['user_id'],))
                growth_data = cursor.fetchone()
                if growth_data['last_month'] > 0:
                    stats['monthly_growth'] = ((growth_data['current_month'] - growth_data['last_month']) / growth_data['last_month']) * 100
                else:
                    stats['monthly_growth'] = 0 if growth_data['current_month'] == 0 else 100
                
            except pymysql.Error as e:
                print(f"Error fetching stats: {e}")
                stats = {'total_orders': 0, 'total_spent': 0, 'avg_order': 0, 'pending_orders': 0, 'monthly_growth': 0}
            
            # Get recent orders (last 5)
            recent_orders = []
            try:
                cursor.execute("""
                    SELECT id, userid, zoneid, product_name, price, status, create_date 
                    FROM orders 
                    WHERE user_id = %s 
                    ORDER BY create_date DESC 
                    LIMIT 5
                """, (session['user_id'],))
                recent_orders = cursor.fetchall()
            except pymysql.Error as e:
                print(f"Error fetching recent orders: {e}")
                recent_orders = []
            
            # Get all orders for orders tab
            all_orders = []
            try:
                cursor.execute("""
                    SELECT id, userid, zoneid, product_name, price, status, create_date 
                    FROM orders 
                    WHERE user_id = %s 
                    ORDER BY create_date DESC
                """, (session['user_id'],))
                all_orders = cursor.fetchall()
            except pymysql.Error as e:
                print(f"Error fetching all orders: {e}")
                all_orders = []
            
            # Get transactions
            transactions = []
            try:
                cursor.execute("""
                    SELECT txn_type, amount, utr, reference_id, description, created_at 
                    FROM transactions 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 20
                """, (session['user_id'],))
                transactions = cursor.fetchall()
            except pymysql.Error as e:
                print(f"Error fetching transactions: {e}")
                transactions = []
            
        return render_template('dashboard.html', user=user, stats=stats, recent_orders=recent_orders, all_orders=all_orders, transactions=transactions)
    except Exception as e:
        print(f"Error fetching dashboard data: {e}")
        return redirect(url_for('index'))
    finally:
        connection.close()

@app.route('/region_checker')
def region_checker():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    return render_template('region_checker.html')

@app.route('/upi_order')
def upi_order():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    return render_template('upi_order.html')

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    # Get query parameters
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    status_filter = request.args.get('status', 'all')
    
    db_user_id = session['user_id']
    orders_list = []
    total_orders = 0
    total_pages = 0
    
    connection = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            # Get user data with balance, brl_balance, and is_reseller
            cursor.execute("SELECT id, username, email, balance, brl_balance, is_reseller FROM users WHERE id = %s", (db_user_id,))
            user = cursor.fetchone()
            
            if not user:
                return redirect(url_for('auth'))
            
            # Initialize balance fields as float and is_reseller as bool
            user['balance'] = float(user.get('balance') or 0.00)
            user['brl_balance'] = float(user.get('brl_balance') or 0.00)
            user['is_reseller'] = bool(user.get('is_reseller', False))
            
            print(f"[DEBUG] Fetching orders for user_id: {db_user_id}")
            
            # Build WHERE clause for filtering
            where_clause = "WHERE user_id = %s"
            params = [db_user_id]
            
            if status_filter != 'all':
                where_clause += " AND status = %s"
                params.append(status_filter)
            
            # Get total count for pagination
            count_query = f"SELECT COUNT(*) as total FROM orders {where_clause}"
            print(f"[DEBUG] Count Query: {count_query}")
            print(f"[DEBUG] Count Params: {params}")
            
            cursor.execute(count_query, params)
            count_result = cursor.fetchone()
            total_orders = count_result['total'] if count_result else 0
            print(f"[DEBUG] Total orders found: {total_orders}")
            
            total_pages = (total_orders + per_page - 1) // per_page if total_orders > 0 else 1
            
            # Ensure page is within bounds
            page = max(1, min(page, total_pages)) if total_pages > 0 else 1
            offset = (page - 1) * per_page
            
            # Get orders with pagination
            order_query = f"""
                SELECT id, userid, zoneid, product_name, price, status, create_date 
                FROM orders 
                {where_clause}
                ORDER BY create_date DESC 
                LIMIT %s OFFSET %s
            """
            print(f"[DEBUG] Order Query: {order_query}")
            print(f"[DEBUG] Order Params: {params + [per_page, offset]}")
            
            cursor.execute(order_query, params + [per_page, offset])
            orders_list = cursor.fetchall()
            
            print(f"[DEBUG] Orders fetched: {len(orders_list)}")
            for idx, order in enumerate(orders_list):
                print(f"[DEBUG] Order {idx}: {order}")
        
        print(f"[DEBUG] Rendering template with {len(orders_list)} orders")
        
        # Calculate pagination values
        start_index = ((page - 1) * per_page) + 1 if total_orders > 0 else 0
        end_index = min(page * per_page, total_orders)
        
        # Calculate page range for pagination controls
        page_range_start = max(1, page - 2)
        page_range_end = min(total_pages + 1, page + 3)
        page_range = list(range(page_range_start, page_range_end))
        
        return render_template('orders.html', 
                             user=user,
                             orders=orders_list, 
                             page=page, 
                             per_page=per_page, 
                             total_orders=total_orders, 
                             total_pages=total_pages,
                             current_filter=status_filter,
                             start_index=start_index,
                             end_index=end_index,
                             page_range=page_range)
    
    except pymysql.Error as db_err:
        print(f"[ERROR] Database error: {str(db_err)}")
        import traceback
        traceback.print_exc()
        page_range = [1]
        return render_template('orders.html', 
                             orders=[], 
                             page=1, 
                             per_page=per_page, 
                             total_orders=0, 
                             total_pages=1,
                             current_filter=status_filter,
                             error=f"Database error: {str(db_err)}",
                             start_index=0,
                             end_index=0,
                             page_range=page_range)
    
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        page_range = [1]
        return render_template('orders.html', 
                             orders=[], 
                             page=1, 
                             per_page=per_page, 
                             total_orders=0, 
                             total_pages=1,
                             current_filter=status_filter,
                             error=str(e),
                             start_index=0,
                             end_index=0,
                             page_range=page_range)
    
    finally:
        if connection:
            try:
                connection.close()
            except:
                pass

@app.route('/account')
def account():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            # Query all available columns including brl_balance
            cursor.execute("""
                SELECT id, username, email, phone, balance, brl_balance, created_at, referrer_id, 
                       public_key, private_key, is_reseller, is_admin, language, knd_coin, membership_type
                FROM users 
                WHERE id = %s
            """, (session['user_id'],))
            user = cursor.fetchone()
            
            if not user:
                return redirect(url_for('auth'))
            
            # Ensure all fields have defaults if NULL
            user['phone'] = user.get('phone') or None
            user['balance'] = float(user.get('balance') or 0.00)
            user['brl_balance'] = float(user.get('brl_balance') or 0.00)
            user['created_at'] = user.get('created_at')
            user['referrer_id'] = user.get('referrer_id')
            user['public_key'] = user.get('public_key')
            user['private_key'] = user.get('private_key')
            user['is_reseller'] = bool(user.get('is_reseller', False))
            user['is_admin'] = bool(user.get('is_admin', False))
            
            # Get recent transactions from transactions table only
            transactions = []
            try:
                cursor.execute("""
                    SELECT 
                        txn_type as type, 
                        amount, 
                        description, 
                        created_at
                    FROM transactions 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                    LIMIT 5
                """, (session['user_id'],))
                transactions = cursor.fetchall()
                
            except pymysql.Error as e:
                print(f"Error fetching transactions: {e}")
                transactions = []
            
        return render_template('account.html', user=user, transactions=transactions)
    except Exception as e:
        print(f"Error fetching user data: {e}")
        return redirect(url_for('index'))
    finally:
        connection.close()

@app.route('/api/update_account', methods=['POST'])
def api_update_account():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    updates = {}
    
    # Only include fields that are being updated
    if 'email' in data and data['email']:
        updates['email'] = data['email']
    if 'phone' in data and data['phone']:
        updates['phone'] = data['phone']
    
    # If no updates, return error
    if not updates:
        return jsonify({'success': False, 'error': 'No fields to update'}), 400
    
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            # Build dynamic UPDATE query
            set_clause = ', '.join([f"{key} = %s" for key in updates.keys()])
            values = list(updates.values()) + [session['user_id']]
            
            query = f"UPDATE users SET {set_clause} WHERE id = %s"
            cursor.execute(query, values)
            connection.commit()
        
        connection.close()
        return jsonify({'success': True, 'message': 'Account updated successfully'})
    except Exception as e:
        print(f"Error updating account: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update_password', methods=['POST'])
def api_update_password():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()
    
    if not current_password or not new_password:
        return jsonify({'success': False, 'error': 'Both passwords are required'}), 400
    
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'New password must be at least 6 characters'}), 400
    
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            # Get current password from database
            cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            
            if not user:
                connection.close()
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            # Verify current password
            if not bcrypt.checkpw(current_password.encode('utf-8'), user['password'].encode('utf-8')):
                connection.close()
                return jsonify({'success': False, 'error': 'Current password is incorrect'}), 401
            
            # Hash new password
            hashed_new = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            
            # Update password in database
            cursor.execute(
                "UPDATE users SET password = %s WHERE id = %s",
                (hashed_new.decode('utf-8'), session['user_id'])
            )
            connection.commit()
        
        connection.close()
        return jsonify({'success': True, 'message': 'Password updated successfully'})
    except Exception as e:
        print(f"Error updating password: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/transactions')
def transactions_page():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    connection = pymysql.connect(**DB_CONFIG)
    try:
        with connection.cursor() as cursor:
            # Get user data with balance, brl_balance, and is_reseller
            cursor.execute("SELECT id, username, email, balance, brl_balance, is_reseller FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            
            if not user:
                return redirect(url_for('auth'))
            
            # Initialize balance fields as float and is_reseller as bool
            user['balance'] = float(user.get('balance') or 0.00)
            user['brl_balance'] = float(user.get('brl_balance') or 0.00)
            user['is_reseller'] = bool(user.get('is_reseller', False))
            
            # Get stats
            stats = {}
            try:
                cursor.execute("SELECT SUM(amount) as total_credited FROM wallet_history WHERE user_id = %s AND transaction_type = 'credit'", (session['user_id'],))
                credited = cursor.fetchone()['total_credited'] or 0
                stats['total_credited'] = float(credited)
                
                cursor.execute("SELECT SUM(amount) as total_debited FROM wallet_history WHERE user_id = %s AND transaction_type = 'debit'", (session['user_id'],))
                debited = cursor.fetchone()['total_debited'] or 0
                stats['total_debited'] = float(debited)
            except pymysql.Error as e:
                print(f"Error fetching stats: {e}")
                stats = {'total_credited': 0, 'total_debited': 0}
            
            # Get wallet history
            transactions = []
            try:
                cursor.execute("""
                    SELECT id, amount_before, amount, current_amount, transaction_type, reason, created_at
                    FROM wallet_history 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT 50
                """, (session['user_id'],))
                raw_txns = cursor.fetchall()
                
                for txn in raw_txns:
                    # Parse reason
                    reason = txn['reason']
                    utr = None
                    title = reason
                    description = reason
                    verified_by = 'System'
                    
                    if 'UPI Top-up' in reason:
                        title = 'Wallet Top-up'
                        description = 'Direct deposit via QR Payment'
                        verified_by = 'Verified by System'
                        if 'UTR:' in reason:
                            utr = reason.split('UTR:')[1].strip()
                    elif 'Order purchase' in reason:
                        title = reason.split(' for ')[0]
                        description = reason
                        verified_by = 'Automatic Checkout'
                    elif 'Order Refund' in reason:
                        title = 'Order Refund'
                        description = reason
                        verified_by = 'Manual Admin Refund'
                    else:
                        description = reason
                    
                    transactions.append({
                        'transaction_type': txn['transaction_type'],
                        'amount': float(txn['amount']),
                        'amount_before': float(txn['amount_before']),
                        'current_amount': float(txn['current_amount']),
                        'title': title,
                        'description': description,
                        'utr': utr,
                        'verified_by': verified_by,
                        'created_at': txn['created_at']
                    })
            except pymysql.Error as e:
                print(f"Error fetching wallet history: {e}")
                transactions = []
            
        return render_template('transaction.html', user=user, stats=stats, transactions=transactions)
    except Exception as e:
        print(f"Error fetching transactions data: {e}")
        return redirect(url_for('index'))
    finally:
        connection.close()

@app.route('/order_status/<int:order_id>')
def order_status(order_id):
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch user data
            cursor.execute("SELECT id, username, email, phone, balance, brl_balance, is_reseller, is_admin FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            if user:
                user['balance'] = float(user.get('balance') or 0.00)
                user['brl_balance'] = float(user.get('brl_balance') or 0.00)
                user['is_reseller'] = bool(user.get('is_reseller', False))
            
            # Fetch order data
            cursor.execute("""
                SELECT o.id, o.userid, o.zoneid, o.product_name, o.price, o.status, o.create_date, c.category_name
                FROM orders o
                LEFT JOIN product p ON o.product_name = p.product_name
                LEFT JOIN category c ON p.category_id = c.id
                WHERE o.id = %s AND o.user_id = %s
            """, (order_id, session['user_id']))
            order = cursor.fetchone()
        conn.close()
        
        if not order:
            return jsonify({'success': False, 'error': 'Order not found'}), 404
        
        return render_template('order_status.html',
                             user=user,
                             order_id=order['id'],
                             user_id=order['userid'],
                             zone_id=order['zoneid'],
                             product_name=order['product_name'],
                             price=order['price'],
                             category=order.get('category_name', 'Unknown'),
                             status=order['status'])
    except Exception as e:
        print(f"Error fetching order status: {e}")
        return jsonify({'success': False, 'error': 'Error loading order details'}), 500

@app.route('/add_fund')
def add_fund():
    if 'user_id' not in session:
        return redirect(url_for('auth'))
    
    # Check if user is a reseller
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT is_reseller FROM users WHERE id=%s", (session['user_id'],))
        user = cur.fetchone()
    conn.close()
    
    is_reseller = bool(user.get('is_reseller', False)) if user else False
    
    return render_template('add_fund.html', is_reseller=is_reseller)

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/refund')
def refund():
    return render_template('refund.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/verify-upi', methods=['POST'])
def api_verify_upi():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    user_id = session['user_id']
    utr = request.form.get('utr', '').strip()
    amount = float(request.form.get('amount', 0))
    
    if not utr or amount <= 0:
        return jsonify({'success': False, 'message': 'Invalid UTR or amount.'})
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if UTR already used
            cursor.execute("SELECT id FROM used_utrs WHERE utr=%s", (utr,))
            if cursor.fetchone():
                return jsonify({'success': False, 'message': 'This UTR is already used.'})

            # Call BharatPe API
            BHARATPE_MERCHANT_ID = "62438063"
            BHARATPE_TOKEN = "968b4012d8554111b807d3080909376e"
            BHARATPE_API_URL = "https://payments-tesseract.bharatpe.in/api/v1/merchant/transactions"
            fromDate = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
            toDate = datetime.now().strftime('%Y-%m-%d')
            url = f"{BHARATPE_API_URL}?module=PAYMENT_QR&merchantId={BHARATPE_MERCHANT_ID}&sDate={fromDate}&eDate={toDate}"
            headers = {
                'token': BHARATPE_TOKEN,
                'user-agent': 'Mozilla/5.0',
            }
            resp = requests.get(url, headers=headers, timeout=15)
            data = resp.json()
            found = None
            for txn in data.get("data", {}).get("transactions", []):
                if txn.get("bankReferenceNo") == utr:
                    found = txn
                    break
            if not found:
                return jsonify({'success': False, 'message': 'UTR not found or not valid.'})
            if found.get("status") != "SUCCESS" or float(found.get("amount", 0)) != amount:
                return jsonify({'success': False, 'message': 'Payment not successful or amount mismatch.'})

            # Get previous balance for wallet history
            cursor.execute("SELECT balance FROM users WHERE id=%s", (user_id,))
            bal_row = cursor.fetchone()
            amount_before = float(bal_row['balance']) if bal_row and bal_row.get('balance') is not None else 0.0

            # Save UTR to used_utrs
            cursor.execute("INSERT INTO used_utrs (utr, user_id, amount, used_at) VALUES (%s, %s, %s, NOW())", (utr, user_id, amount))
            # Insert into transactions
            cursor.execute("INSERT INTO transactions (user_id, txn_type, amount, utr, description) VALUES (%s, %s, %s, %s, %s)", (user_id, 'credit', amount, utr, 'UPI Top-up'))
            # Add to wallet_topups
            cursor.execute("INSERT INTO wallet_topups (user_id, amount, order_id, created_at) VALUES (%s, %s, %s, NOW())", (user_id, amount, utr))
            # Add balance to user
            cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, user_id))

            # Get current balance after update
            cursor.execute("SELECT balance FROM users WHERE id=%s", (user_id,))
            bal_row = cursor.fetchone()
            current_amount = float(bal_row['balance']) if bal_row and bal_row.get('balance') is not None else 0.0

            # Insert wallet history (credit)
            cursor.execute("""
                INSERT INTO wallet_history (user_id, amount_before, amount, transaction_type, reason, current_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, amount_before, amount, 'credit', f'UPI Top-up (UTR: {utr})', current_amount))

            # Referral order reward (UPI wallet top-up)
            cursor.execute("SELECT referrer_id FROM users WHERE id=%s", (user_id,))
            ref_row = cursor.fetchone()
            if ref_row and ref_row['referrer_id']:
                referrer_id = ref_row['referrer_id']
                ref_reward = round(amount * 0.01, 2)
                cursor.execute("UPDATE users SET knd_coin = knd_coin + %s WHERE id = %s", (ref_reward, referrer_id))
            
            # KND COIN reward logic
            cursor.execute("SELECT membership_type FROM users WHERE id=%s", (user_id,))
            mem_row = cursor.fetchone()
            knd_percent = 0.01
            if mem_row and mem_row['membership_type'] == 'pro':
                knd_percent = 0.02
            coins = round(amount * knd_percent, 2)
            cursor.execute("UPDATE users SET knd_coin = knd_coin + %s WHERE id = %s", (coins, user_id))
            
            conn.commit()
    finally:
        conn.close()
    
    return jsonify({'success': True, 'message': f'â‚¹{amount} added to your wallet. +{coins} KND COIN earned.'})

@app.route('/api/validasi', methods=['GET'])
def api_validasi():
    id_ = request.args.get('user_id') or request.args.get('userid') or request.args.get('player_id')
    serverid = request.args.get('server_id') or request.args.get('serverid') or request.args.get('zoneid')

    # allow product hints so we can handle Magic Chess via Smile.one
    product = request.args.get('product') or request.args.get('category')
    productid = request.args.get('productid') or request.args.get('product_id')

    if not id_:
        return ('', 400)

    # if server id not provided, use user id as fallback for products that require same field
    if not serverid:
        serverid = id_

    req_meta = _get_request_meta()

    # Detect MAGIC CHESS GO GO (product name or specific product id 23825)
    is_magic_chess = False
    try:
        if product and 'magic' in product.lower() and 'chess' in product.lower():
            is_magic_chess = True
        if productid and str(productid).strip() == '23825':
            is_magic_chess = True
    except Exception:
        is_magic_chess = False

    if is_magic_chess:
        # Query Smile.one getrole for magicchessgogo product
        try:
            resp = get_smile_role(userid=id_, zoneid=serverid, product='magicchessgogo', productid=productid or '23825')
        except Exception as e:
            try:
                log_search_if_configured(player_id=id_, server_id=serverid, raw_response={"error": str(e)}, request_meta=req_meta)
            except Exception:
                pass
            return jsonify({'status': 'failed', 'message': str(e)}), 500

        # Normalize Smile.one response
        if isinstance(resp, dict) and resp.get('status') == 200:
            nickname = resp.get('username') or extract_username_from_response(resp) or (resp.get('data') or {}).get('nickname')
            country = resp.get('country') or (resp.get('data') or {}).get('country')
            result = {'nickname': nickname or '-', 'id': id_, 'serverid': serverid, 'country': country or ''}
            try:
                log_search_if_configured(player_id=id_, server_id=serverid, nickname=result.get('nickname'), country_code=None, country_name=country, parsed_obj=None, raw_response=resp, request_meta=req_meta)
            except Exception:
                pass
            return jsonify({'status': 'success', 'result': result})
        else:
            try:
                log_search_if_configured(player_id=id_, server_id=serverid, raw_response=resp, request_meta=req_meta)
            except Exception:
                pass
            msg = resp.get('message') if isinstance(resp, dict) else 'invalid_response'
            return jsonify({'status': 'failed', 'message': msg, 'raw': resp}), 400

    # Fallback: existing moogold flow (preserve current behavior)
    try:
        # replicate the axios POST used by the upstream site
        url = "https://moogold.com/wp-content/plugins/id-validation-new/id-validation-ajax.php"
        payload = {
            "attribute_amount": "Weekly Pass",
            "text-5f6f144f8ffee": id_,
            "text-1601115253775": serverid,
            "quantity": 1,
            "add-to-cart": 15145,
            "product_id": 15145,
            "variation_id": 4690783
        }
        headers = {
            'Referer': 'https://moogold.com/product/mobile-legends/',
            'Origin': 'https://moogold.com'
        }

        r = requests.post(url, data=payload, headers=headers, timeout=10)
        r.raise_for_status()

        raw_text = r.text
        try:
            data = r.json()
        except Exception:
            # upstream returned non-json; store raw text
            data = {"raw": raw_text}

        message = data.get('message') if isinstance(data, dict) else None
        if not message:
            # Log failed search attempt with full context
            try:
                log_search_if_configured(
                    player_id=id_,
                    server_id=serverid,
                    nickname=None,
                    country_code=None,
                    country_name=None,
                    parsed_obj=None,
                    raw_response=data,
                    request_meta=req_meta
                )
            except Exception:
                # swallow DB errors to avoid breaking the API
                pass

            return jsonify({'status': 'failed', 'message': 'Invalid ID Player or Server ID'}), 400

        # parse the upstream message into structured data
        parsed = parse_object(message)
        country_code = parsed.get('country')
        country_name = None

        # optional country list lookup (utils/data.json)
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(base, 'utils', 'data.json')
            with open(data_path, 'r', encoding='utf-8') as f:
                countries = json.load(f)
                for c in countries:
                    if c.get('countryShortCode') == country_code:
                        country_name = c.get('countryName')
                        break
        except Exception:
            country_name = None

        result = {
            'nickname': parsed.get('in-game-nickname'),
            'id': id_,
            'serverid': serverid,
            'country': country_name or parsed.get('country') or 'Unknown'
        }

        # Persist the successful search (non-blocking)
        try:
            log_search_if_configured(
                player_id=id_,
                server_id=serverid,
                nickname=result.get('nickname'),
                country_code=parsed.get('Region') or parsed.get('region') or parsed.get('country'),
                country_name=country_name,
                parsed_obj=parsed,
                raw_response=data,
                request_meta=req_meta
            )
        except Exception:
            pass

        return jsonify({'status': 'success', 'result': result})

    except requests.exceptions.RequestException as re:
        # network / upstream error: log and return error
        try:
            log_search_if_configured(
                player_id=id_,
                server_id=serverid,
                nickname=None,
                country_code=None,
                country_name=None,
                parsed_obj=None,
                raw_response={"error": str(re)},
                request_meta=req_meta
            )
        except Exception:
            pass

        return jsonify({'status': 'failed', 'message': str(re)}), 500

    except Exception as e:
        # unexpected error: log context and return 500
        try:
            log_search_if_configured(
                player_id=id_,
                server_id=serverid,
                nickname=None,
                country_code=None,
                country_name=None,
                parsed_obj=None,
                raw_response={"error": str(e)},
                request_meta=req_meta
            )
        except Exception:
            pass

        return jsonify({'status': 'failed', 'message': str(e)}), 500

@app.route('/api/balance')
def api_balance():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor() as cursor:
            cursor.execute("SELECT balance, brl_balance, is_reseller FROM users WHERE id = %s", (session['user_id'],))
            user = cursor.fetchone()
            if user:
                is_reseller = user.get('is_reseller', 0)
                
                # Return brl_balance for resellers, balance for regular users
                if is_reseller:
                    balance = float(user.get('brl_balance', 0)) if user.get('brl_balance') is not None else 0.0
                else:
                    balance = float(user.get('balance', 0)) if user.get('balance') is not None else 0.0
                
                return jsonify({'balance': balance, 'is_reseller': is_reseller})
            else:
                return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()

@app.route('/api/create_order', methods=['POST'])
def api_create_order():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    connection = None
    cursor = None

    try:
        data = request.get_json()
        db_user_id = session['user_id']

        user_id = data.get('userId')
        zone_id = data.get('zoneId')
        product_id = data.get('productId')
        payment_method = data.get('paymentMethod', '').lower()

        if not all([user_id, product_id, payment_method]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # START TRANSACTION
        connection.begin()

        # Fetch user balance
        cursor.execute("SELECT balance FROM users WHERE id=%s FOR UPDATE", (db_user_id,))
        user = cursor.fetchone()
        if not user:
            connection.rollback()
            return jsonify({'success': False, 'error': 'User not found'}), 404

        balance_before = float(user['balance'] or 0)

        # Check if user is a reseller
        cursor.execute("SELECT is_reseller FROM users WHERE id = %s", (db_user_id,))
        user_info = cursor.fetchone()
        is_user_reseller = bool(user_info.get('is_reseller', False)) if user_info else False

        # Fetch product — support lookup by internal id (`p.id`) or external provider id (`p.product_id`)
        print(f"[DEBUG] api_create_order - productId param: {product_id}")
        cursor.execute("""
            SELECT p.product_name, p.price, p.reseller_price, p.product_id, p.api_provider, p.region, c.category_name, c.category_type
            FROM product p
            LEFT JOIN category c ON p.category = c.category_name
            WHERE (p.id=%s OR p.product_id=%s) AND p.status='active'
        """, (product_id, str(product_id)))
        product = cursor.fetchone()
        print(f"[DEBUG] product row fetched: {product}")
        if not product:
            connection.rollback()
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        category_type = product['category_type']
        # Use reseller_price if user is reseller and reseller_price exists, otherwise use regular price
        if is_user_reseller and product.get('reseller_price'):
            price = float(product['reseller_price'])
        else:
            price = float(product['price'])

        # Create order FIRST (pending)
        cursor.execute("""
            INSERT INTO orders
            (user_id, userid, zoneid, product_name, price, payment_method_id, status, create_date)
            VALUES (%s, %s, %s, %s, %s, 3, 'pending', NOW());

        """, (db_user_id, user_id, zone_id, product['product_name'], price))

        order_id = cursor.lastrowid

        # -------- WALLET PAYMENT FLOW --------
        if payment_method == 'wallet':

            if balance_before < price:
                connection.rollback()
                return jsonify({
                    'success': False,
                    'error': 'Insufficient balance',
                    'balance': balance_before,
                    'required': price
                }), 400

            # Only Smile.one and Bushan handled automatically
            if product['api_provider'].lower() not in ['smile', 'bushan', 'xtreme']:
                # Deduct balance for manual order
                cursor.execute(
                    "UPDATE users SET balance = balance - %s WHERE id=%s",
                    (price, db_user_id)
                )

                # Fetch updated balance
                cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
                new_balance = float(cursor.fetchone()['balance'])

                # Wallet history
                cursor.execute("""
                    INSERT INTO wallet_history
                    (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                    VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
                """, (db_user_id, balance_before, price, new_balance,
                      f"Order purchase #{order_id} - {product['product_name']}"))

                # Transactions log
                cursor.execute("""
                    INSERT INTO transactions
                    (user_id, txn_type, amount, description, created_at)
                    VALUES (%s, 'debit', %s, %s, NOW())
                """, (db_user_id, price, f"Order purchase #{order_id} - {product['product_name']}"))

                connection.commit()
                # Send Telegram notification for manual order
                message = f"New Manual Order From {product['category_name']}\nOrder ID : {order_id}\nProduct : {product['product_name']}\nUser ID : {db_user_id}\nPlayer ID: {user_id}\nZone ID : {zone_id}\nAmount : {price}"
                send_telegram_notification(message)
                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'status': 'pending',
                    'balance_before': balance_before,
                    'balance_after': new_balance,
                    'message': 'Manual coin order created'
                })
            if product['api_provider'].lower() == 'smile':
                # Check API provider balance FIRST
                balance_check = check_provider_balance_sufficient(
                    provider='smile',
                    required_amount=price,
                    region=product.get('region')
                )
                
                if not balance_check['sufficient']:
                    # Insufficient balance - mark as processing and notify admin
                    cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                    connection.commit()
                    
                    # Fetch user email for notification
                    cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                    user_email_row = cursor.fetchone()
                    user_email = user_email_row['email'] if user_email_row else 'N/A'
                    
                    send_order_insufficient_balance_notification(
                        order_id=order_id,
                        region=product.get('region'),
                        provider='Smile.one',
                        user_email=user_email,
                        user_id=user_id,
                        zone_id=zone_id,
                        product_name=product['product_name'],
                        category_name=product.get('category_name'),
                        payment_method='wallet',
                        required_balance=price,
                        current_balance=balance_check['balance']
                    )
                    
                    return jsonify({
                        'success': False,
                        'order_id': order_id,
                        'status': 'processing',
                        'error': 'API provider has insufficient balance',
                        'message': 'Order created as processing. Admin notified to recharge API balance.',
                        'provider_balance': balance_check['balance'],
                        'required_amount': price
                    })
                
                # Handle multiple Smile.one product IDs
                product_ids = [p.strip() for p in product['product_id'].split('&') if p.strip()]
                
                # Fetch API credentials from database
                creds = get_api_credentials('smile')
                if not creds:
                    # Fallback to provided credentials
                    creds = {'uid': '913332', 'email': 'renedysanasam13@gmail.com', 'api_key': '3984a50cd116b3c06a05c784e16d0fb0'}
                
                smile_orders = []
                failed = []

                for idx, pid in enumerate(product_ids, 1):
                    print(f"[DEBUG] Calling Smile.one API for product {idx}: {pid}")
                    
                    result = create_smile_order(
                        userid=user_id,
                        zoneid=zone_id,
                        product='mobilelegends',
                        productid=pid,
                        region=product.get('region'),
                        uid=creds.get('uid'),
                        email=creds.get('email'),
                        key=creds.get('api_key')
                    )
                    
                    print(f"[DEBUG] Smile.one response: {result}")

                    smile_orders.append({
                        'index': idx,
                        'product_id': pid,
                        'response': result
                    })

                    if not result.get('success'):
                        failed.append({
                            'product_id': pid,
                            'error': result.get('message')
                        })

                # If ANY Smile.one failed â†’ set failed
                if failed:
                    # Fetch user email for notification
                    cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                    user_email_row = cursor.fetchone()
                    user_email = user_email_row['email'] if user_email_row else 'N/A'
                    
                    cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                    connection.commit()
                    
                    # Send admin notification
                    send_order_failure_notification(
                        order_id=order_id,
                        region=product.get('region'),
                        provider=product.get('api_provider'),
                        user_email=user_email,
                        user_id=user_id,
                        zone_id=zone_id,
                        product_name=product['product_name'],
                        category_name=product.get('category_name'),
                        payment_method='wallet'
                    )

                    return jsonify({
                        'success': False,
                        'order_id': order_id,
                        'status': 'processing',
                        'smile_orders': smile_orders,
                        'failed_orders': failed,
                        'message': 'Order failed. Admin has been notified for manual processing.'
                    })

                # -------- ALL SMILE ORDERS SUCCESS --------

                # Deduct balance
                cursor.execute(
                    "UPDATE users SET balance = balance - %s WHERE id=%s",
                    (price, db_user_id)
                )

                # Fetch updated balance
                cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
                new_balance = float(cursor.fetchone()['balance'])

                # Wallet history
                cursor.execute("""
                    INSERT INTO wallet_history
                    (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                    VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
                """, (db_user_id, balance_before, price, new_balance,
                      f"Order purchase #{order_id} - {product['product_name']}"))

                # Transactions log
                cursor.execute("""
                    INSERT INTO transactions
                    (user_id, txn_type, amount, description, created_at)
                    VALUES (%s, 'debit', %s, %s, NOW())
                """, (db_user_id, price, f"Order purchase #{order_id} - {product['product_name']}"))

                # Update order success
                cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))

                # COMMIT EVERYTHING
                connection.commit()

                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'status': 'success',
                    'balance_before': balance_before,
                    'balance_after': new_balance,
                    'smile_orders': smile_orders
                })

            elif product['api_provider'].lower() == 'bushan':
                # Check API provider balance FIRST
                balance_check = check_provider_balance_sufficient(
                    provider='bushan',
                    required_amount=price,
                    region=None
                )
                
                if not balance_check['sufficient']:
                    # Insufficient balance - mark as processing and notify admin
                    cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                    connection.commit()
                    
                    # Fetch user email for notification
                    cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                    user_email_row = cursor.fetchone()
                    user_email = user_email_row['email'] if user_email_row else 'N/A'
                    
                    send_order_insufficient_balance_notification(
                        order_id=order_id,
                        region=None,
                        provider='Bushan (1GameStopUp)',
                        user_email=user_email,
                        user_id=user_id,
                        zone_id=zone_id,
                        product_name=product['product_name'],
                        category_name=product.get('category_name'),
                        payment_method='wallet',
                        required_balance=price,
                        current_balance=balance_check['balance']
                    )
                    
                    return jsonify({
                        'success': False,
                        'order_id': order_id,
                        'status': 'processing',
                        'error': 'API provider has insufficient balance',
                        'message': 'Order created as processing. Admin notified to recharge API balance.',
                        'provider_balance': balance_check['balance'],
                        'required_amount': price
                    })
                
                # Handle multiple Bushan product IDs
                product_ids = [p.strip() for p in product['product_id'].split('&') if p.strip()]
                
                if not user_id or not zone_id:
                    connection.rollback()
                    return jsonify({
                        "success": False,
                        "error": "Invalid playerId or zoneId"
                    }), 400
                # Deduct balance
                cursor.execute(
                    "UPDATE users SET balance = balance - %s WHERE id=%s",
                    (price, db_user_id)
                )

                # Fetch updated balance
                cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
                new_balance = float(cursor.fetchone()['balance'])

                # Wallet history
                cursor.execute("""
                    INSERT INTO wallet_history
                    (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                    VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
                """, (db_user_id, balance_before, price, new_balance,
                      f"Order purchase #{order_id} - {product['product_name']}"))

                # Transactions log
                cursor.execute("""
                    INSERT INTO transactions
                    (user_id, txn_type, amount, description, created_at)
                    VALUES (%s, 'debit', %s, %s, NOW())
                """, (db_user_id, price, f"Order purchase #{order_id} - {product['product_name']}"))

                # Fetch API credentials from database
                creds = get_api_credentials('bushan')
                if not creds:
                    # Fallback to provided credentials
                    creds = {'api_key': 'busan_b372f70f97df1fc40028bd2c32cdbf4eb2522c183004c6a41acf83e8587e9189'}
                
                bushan_orders = []
                failed = []

                for idx, pid in enumerate(product_ids, 1):
                    print(f"[DEBUG] Calling Bushan API for product {idx}: {pid}")
                    
                    result = create_bushan_order(
                        playerId=user_id,
                        zoneId=zone_id,
                        productId=pid,
                        api_key=creds.get('api_key')
                    )
                    
                    print(f"[DEBUG] Bushan response: {result}")

                    bushan_orders.append({
                        'index': idx,
                        'product_id': pid,
                        'response': result
                    })

                    if not result.get('success'):
                        failed.append({
                            'product_id': pid,
                            'error': result.get('message')
                        })

                # Transactions log credit
                    cursor.execute("""
                        INSERT INTO transactions
                        (user_id, txn_type, amount, description, created_at)
                        VALUES (%s, 'credit', %s, %s, NOW())
                    """, (db_user_id, price, f"Refund for failed order #{order_id} - {product['product_name']}"))
                    
                    # Fetch user email for notification
                    cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                    user_email_row = cursor.fetchone()
                    user_email = user_email_row['email'] if user_email_row else 'N/A'
                    
                    cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                    connection.commit()
                    
                    # Send admin notification
                    send_order_failure_notification(
                        order_id=order_id,
                        region=product.get('region'),
                        provider=product.get('api_provider'),
                        user_email=user_email,
                        user_id=user_id,
                        zone_id=zone_id,
                        product_name=product['product_name'],
                        category_name=product.get('category_name'),
                        payment_method='wallet'
                    )

                    return jsonify({
                        'success': False,
                        'order_id': order_id,
                        'status': 'processing',
                        'bushan_orders': bushan_orders,
                        'failed_orders': failed,
                        'message': 'Order failed. Admin has been notified for manual processing.'
                    })

                # -------- ALL BUSHAN ORDERS SUCCESS --------

                # Update order success
                cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))

                # COMMIT EVERYTHING
                connection.commit()

                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'status': 'success',
                    'balance_before': balance_before,
                    'balance_after': new_balance,
                    'bushan_orders': bushan_orders
                })

            elif product['api_provider'].lower() == 'xtreme':
                # Check API provider balance FIRST
                balance_check = check_provider_balance_sufficient(
                    provider='xtreme',
                    required_amount=price,
                    region=None
                )
                
                if not balance_check['sufficient']:
                    # Insufficient balance - mark as processing and notify admin
                    cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                    connection.commit()
                    
                    # Fetch user email for notification
                    cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                    user_email_row = cursor.fetchone()
                    user_email = user_email_row['email'] if user_email_row else 'N/A'
                    
                    send_order_insufficient_balance_notification(
                        order_id=order_id,
                        region=None,
                        provider='Xtreme',
                        user_email=user_email,
                        user_id=user_id,
                        zone_id=zone_id,
                        product_name=product['product_name'],
                        category_name=product.get('category_name'),
                        payment_method='wallet',
                        required_balance=price,
                        current_balance=balance_check['balance']
                    )
                    
                    return jsonify({
                        'success': False,
                        'order_id': order_id,
                        'status': 'processing',
                        'error': 'API provider has insufficient balance',
                        'message': 'Order created as processing. Admin notified to recharge API balance.',
                        'provider_balance': balance_check['balance'],
                        'required_amount': price
                    })
                
                # Deduct balance
                cursor.execute(
                    "UPDATE users SET balance = balance - %s WHERE id=%s",
                    (price, db_user_id)
                )

                # Fetch updated balance
                cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
                new_balance = float(cursor.fetchone()['balance'])

                # Wallet history
                cursor.execute("""
                    INSERT INTO wallet_history
                    (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                    VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
                """, (db_user_id, balance_before, price, new_balance,
                      f"Order purchase #{order_id} - {product['product_name']}"))

                # Transactions log
                cursor.execute("""
                    INSERT INTO transactions
                    (user_id, txn_type, amount, description, created_at)
                    VALUES (%s, 'debit', %s, %s, NOW())
                """, (db_user_id, price, f"Order purchase #{order_id} - {product['product_name']}"))

                # Get Xtreme API credentials (use defaults if not in DB)
                creds = get_api_credentials('xtreme')
                if not creds:
                    creds = {'public_key': 'W6STC3K', 'private_key': 'ZNT91RQ5IYKW'}
                
                result = create_xtreme_order(
                    userid=user_id,
                    zoneid=zone_id,
                    product_id=product['product_id'],
                    public_key=creds.get('public_key') or 'W6STC3K',
                    private_key=creds.get('private_key') or 'ZNT91RQ5IYKW'
                )
                
                xtreme_orders = [{
                    'product_id': product['product_id'],
                    'response': result
                }]
                
                if not result.get('success'):
                    # Fetch user email for notification
                    cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                    user_email_row = cursor.fetchone()
                    user_email = user_email_row['email'] if user_email_row else 'N/A'
                    
                    cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                    connection.commit()
                    
                    # Send admin notification
                    send_order_failure_notification(
                        order_id=order_id,
                        region=None,
                        provider=product.get('api_provider'),
                        user_email=user_email,
                        user_id=user_id,
                        zone_id=zone_id,
                        product_name=product['product_name'],
                        category_name=product.get('category_name'),
                        payment_method='wallet'
                    )

                    return jsonify({
                        'success': False,
                        'order_id': order_id,
                        'status': 'processing',
                        'xtreme_orders': xtreme_orders,
                        'error': result.get('error'),
                        'message': 'Order failed. Admin has been notified for manual processing.'
                    })

                # -------- XTREME ORDER SUCCESS --------

                # Update order success
                cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))

                # COMMIT EVERYTHING
                connection.commit()

                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'status': 'success',
                    'balance_before': balance_before,
                    'balance_after': new_balance,
                    'xtreme_orders': xtreme_orders
                })

        # -------- NON-COIN PAYMENT --------
        connection.commit()
        return jsonify({
            'success': True,
            'order_id': order_id,
            'status': 'pending',
            'message': 'Awaiting payment'
        })

    except Exception as e:
        if connection:
            connection.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/api/generate_order_token', methods=['POST'])
def api_generate_order_token():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    data = request.get_json()
    db_user_id = session['user_id']
    user_id = data.get('userId', '').strip()
    zone_id = data.get('zoneId', '').strip()
    product_id = data.get('productId')
    product_name = data.get('productName', '').strip()
    price = data.get('price', 0)

    if not all([user_id, product_id, product_name, price]):
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400

    # Check if user is a reseller and adjust price if needed
    connection = None
    cursor = None
    try:
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        # Check if user is a reseller
        cursor.execute("SELECT is_reseller FROM users WHERE id = %s", (db_user_id,))
        user_info = cursor.fetchone()
        is_user_reseller = bool(user_info.get('is_reseller', False)) if user_info else False
        
        # Fetch product to get reseller_price if applicable
        if is_user_reseller:
            cursor.execute("SELECT reseller_price FROM product WHERE id = %s", (product_id,))
            product = cursor.fetchone()
            if product and product.get('reseller_price'):
                price = float(product['reseller_price'])
    except Exception as e:
        print(f"[ERROR] Error checking reseller status: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    # Generate token: user_id={db_user_id}+userid={userId}+zoneid={zoneId}+productId={productId}+product={product_name}+price={price}
    token = f"user_id={db_user_id}+userid={user_id}+zoneid={zone_id}+productId={product_id}+product={product_name}+price={price}"

    return jsonify({'success': True, 'order_token': token})

@app.route('/api/verify_upi_order', methods=['POST'])
def api_verify_upi_order():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    connection = None
    cursor = None

    try:
        data = request.get_json()
        db_user_id = session['user_id']

        utr = data.get('utr', '').strip()
        user_id = data.get('userId', '').strip()
        zone_id = data.get('zoneId', '').strip()
        product_id = data.get('productId')
        amount = float(data.get('amount', 0))
        payment_method = data.get('paymentMethod', 'UPI').lower()

        if not all([utr, user_id, product_id, amount > 0]):
            return jsonify({'success': False, 'error': 'Missing or invalid required fields'}), 400

        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor(pymysql.cursors.DictCursor)

        # Check if UTR already used
        cursor.execute("SELECT id FROM used_utrs WHERE utr=%s", (utr,))
        if cursor.fetchone():
            return jsonify({'success': False, 'error': 'This UTR is already used.'}), 400

        # Verify UTR with BharatPe
        
        BHARATPE_API_URL = "https://payments-tesseract.bharatpe.in/api/v1/merchant/transactions"
        fromDate = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        toDate = datetime.now().strftime('%Y-%m-%d')
        bharatpe_url = f"{BHARATPE_API_URL}?module=PAYMENT_QR&merchantId={BHARATPE_MERCHANT_ID}&sDate={fromDate}&eDate={toDate}"
        headers = {
            'token': BHARATPE_TOKEN,
            'user-agent': 'Mozilla/5.0',
        }

        print(f"[DEBUG] Verifying UTR {utr} with BharatPe")
        bharatpe_resp = requests.get(bharatpe_url, headers=headers, timeout=15)
        bharatpe_data = bharatpe_resp.json()
        
        found = None
        for txn in bharatpe_data.get("data", {}).get("transactions", []):
            if txn.get("bankReferenceNo") == utr:
                found = txn
                break
        
        if not found:
            print(f"[ERROR] UTR {utr} not found in BharatPe transactions")
            return jsonify({'success': False, 'error': 'UTR not found or not valid.'}), 400
        
        if found.get("status") != "SUCCESS":
            print(f"[ERROR] BharatPe transaction status: {found.get('status')}")
            return jsonify({'success': False, 'error': f"Payment status is {found.get('status')}, expected SUCCESS"}), 400
        
        bharatpe_amount = float(found.get("amount", 0))
        
        # Use reseller_price if user is reseller and reseller_price exists
        # But first, we need to check reseller status before comparing amounts
        # Check if user is a reseller
        cursor.execute("SELECT is_reseller FROM users WHERE id = %s", (db_user_id,))
        user_info_check = cursor.fetchone()
        is_user_reseller_check = bool(user_info_check.get('is_reseller', False)) if user_info_check else False

        # We'll verify the amount against the original amount, but use reseller price for order creation
        if abs(bharatpe_amount - amount) > 0.01:  # Allow for floating point errors
            print(f"[ERROR] Amount mismatch: BharatPe={bharatpe_amount}, Order={amount}")
            return jsonify({'success': False, 'error': f'Amount mismatch: received ₹{bharatpe_amount}, expected ₹{amount}'}), 400

        print(f"[DEBUG] BharatPe verification successful for UTR {utr}")

        # START TRANSACTION
        connection.begin()

        # Check if user is a reseller
        cursor.execute("SELECT is_reseller FROM users WHERE id = %s", (db_user_id,))
        user_info = cursor.fetchone()
        is_user_reseller = bool(user_info.get('is_reseller', False)) if user_info else False

        # Fetch product
        cursor.execute("""
            SELECT p.product_name, p.price, p.reseller_price, p.product_id, p.api_provider, p.region, c.category_name, c.category_type
            FROM product p
            JOIN category c ON p.category = c.category_name
            WHERE p.id=%s AND p.status='active'
        """, (product_id,))
        product = cursor.fetchone()
        if not product:
            connection.rollback()
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        # Use reseller_price if user is reseller and reseller_price exists, otherwise use the provided amount
        if is_user_reseller and product.get('reseller_price'):
            final_amount = float(product['reseller_price'])
        else:
            final_amount = amount

        # Create order FIRST (pending)
        cursor.execute("""
            INSERT INTO orders
            (user_id, userid, zoneid, product_name, price, payment_method_id, status, create_date)
            VALUES (%s, %s, %s, %s, %s, 1, 'pending', NOW());
        """, (db_user_id, user_id, zone_id, product['product_name'], final_amount))

        order_id = cursor.lastrowid

        # Save UTR to used_utrs
        cursor.execute("INSERT INTO used_utrs (utr, user_id, amount, used_at) VALUES (%s, %s, %s, NOW())", 
                      (utr, db_user_id, amount))

        # Handle Smile.one and Bushan order creation
        if product['api_provider'].lower() == 'smile':
            print(f"[DEBUG] Creating Smile.one order for product {product_id}")
            
            # Fetch API credentials from database
            creds = get_api_credentials('smile')
            if not creds:
                # Fallback to provided credentials
                creds = {'uid': '913332', 'email': 'renedysanasam13@gmail.com', 'api_key': '3984a50cd116b3c06a05c784e16d0fb0'}
            
            # Handle multiple Smile.one product IDs
            product_ids = [p.strip() for p in product['product_id'].split('&') if p.strip()]
            smile_orders = []
            failed = []

            for idx, pid in enumerate(product_ids, 1):
                print(f"[DEBUG] Calling Smile.one API for product {idx}: {pid}")
                
                result = create_smile_order(
                    userid=user_id,
                    zoneid=zone_id,
                    product='mobilelegends',
                    productid=pid,
                    region=product.get('region'),
                    uid=creds.get('uid'),
                    email=creds.get('email'),
                    key=creds.get('api_key')
                )
                
                print(f"[DEBUG] Smile.one response: {result}")
                smile_orders.append({
                    'product_id': pid,
                    'order_id': result.get('order_id'),
                    'success': result.get('success')
                })

                if not result.get('success'):
                    failed.append({
                        'product_id': pid,
                        'error': result.get('message')
                    })

            # If ANY Smile.one failed â†’ rollback
            if failed:
                print(f"[ERROR] Smile.one order creation failed: {failed}")
                cursor.execute("UPDATE orders SET status='failed' WHERE id=%s", (order_id,))
                connection.rollback()

                return jsonify({
                    'success': False,
                    'error': 'Failed to create order',
                    'order_id': order_id,
                    'failed_orders': failed
                }), 400

            # Update order to success
            cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))

            # Log transaction
            cursor.execute("""
                INSERT INTO transactions
                (user_id, txn_type, amount, utr, description, created_at)
                VALUES (%s, 'debit', %s, %s, %s, NOW())
            """, (db_user_id, amount, utr, f"Order purchase #{order_id} - {product['product_name']}"))

            # Log wallet history
            cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
            user_balance = cursor.fetchone()
            amount_before = float(user_balance['balance'] or 0) if user_balance else 0.0

            cursor.execute("""
                INSERT INTO wallet_history
                (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
            """, (db_user_id, amount_before, amount, amount_before,
                  f"Order purchase #{order_id} - {product['product_name']} (UTR: {utr})"))

        elif product['api_provider'].lower() == 'bushan':
            print(f"[DEBUG] Creating Bushan order for product {product_id}")
            
            # Handle multiple Bushan product IDs
            product_ids = [p.strip() for p in product['product_id'].split('&') if p.strip()]
            
            if not user_id or not zone_id:
                connection.rollback()
                return jsonify({
                    "success": False,
                    "error": "Invalid playerId or zoneId"
                }), 400
            
            # Fetch API credentials from database
            creds = get_api_credentials('bushan')
            if not creds:
                # Fallback to provided credentials
                creds = {'api_key': 'busan_b372f70f97df1fc40028bd2c32cdbf4eb2522c183004c6a41acf83e8587e9189'}
            
            bushan_orders = []
            failed = []

            for idx, pid in enumerate(product_ids, 1):
                print(f"[DEBUG] Calling Bushan API for product {idx}: {pid}")
                
                result = create_bushan_order(
                    playerId=user_id,
                    zoneId=zone_id,
                    productId=pid,
                    api_key=creds.get('api_key')
                )
                
                print(f"[DEBUG] Bushan response: {result}")

                bushan_orders.append({
                    'index': idx,
                    'product_id': pid,
                    'response': result
                })

                if not result.get('success'):
                    failed.append({
                        'product_id': pid,
                        'error': result.get('message')
                    })

            # If ANY Bushan failed â†’ rollback
            if failed:
                print(f"[ERROR] Bushan order creation failed: {failed}")
                # Fetch user email for notification
                cursor.execute("SELECT email FROM users WHERE id=%s", (db_user_id,))
                user_email_row = cursor.fetchone()
                user_email = user_email_row['email'] if user_email_row else 'N/A'
                
                cursor.execute("UPDATE orders SET status='processing' WHERE id=%s", (order_id,))
                connection.commit()
                
                # Send admin notification
                send_order_failure_notification(
                    order_id=order_id,
                    region=product.get('region'),
                    provider=product.get('api_provider'),
                    user_email=user_email,
                    user_id=user_id,
                    zone_id=zone_id,
                    product_name=product['product_name'],
                    category_name=product.get('category_name'),
                    payment_method='wallet'
                )

                return jsonify({
                    'success': False,
                    'order_id': order_id,
                    'status': 'processing',
                    'bushan_orders': bushan_orders,
                    'failed_orders': failed,
                    'message': 'Order failed. Admin has been notified for manual processing.'
                })

            # Update order to success
            cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))

            # Log transaction
            cursor.execute("""
                INSERT INTO transactions
                (user_id, txn_type, amount, utr, description, created_at)
                VALUES (%s, 'debit', %s, %s, %s, NOW())
            """, (db_user_id, amount, utr, f"Order purchase #{order_id} - {product['product_name']}"))

            # Log wallet history
            cursor.execute("SELECT balance FROM users WHERE id=%s", (db_user_id,))
            user_balance = cursor.fetchone()
            amount_before = float(user_balance['balance'] or 0) if user_balance else 0.0

            cursor.execute("""
                INSERT INTO wallet_history
                (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
            """, (db_user_id, amount_before, amount, amount_before,
                  f"Order purchase #{order_id} - {product['product_name']} (UTR: {utr})"))

        else:
            # For non-Smile/Bushan providers, mark as pending for manual processing
            cursor.execute("UPDATE orders SET status='pending' WHERE id=%s", (order_id,))

            # Send Telegram notification for manual processing
            send_telegram_notification(f"New Manual Order From {product['category_name']}\nOrder ID : {order_id}\nProduct : {product['product_name']}\nAmount : {amount}\nUTR : {utr}\nProvider : {product['api_provider']}\n\nPlease process this order manually.")

            # Log transaction (but don't deduct balance yet)
            cursor.execute("""
                INSERT INTO transactions
                (user_id, txn_type, amount, utr, description, created_at)
                VALUES (%s, 'pending', %s, %s, %s, NOW())
            """, (db_user_id, amount, utr, f"Order purchase #{order_id} - {product['product_name']} - Pending Manual Processing"))

        # COMMIT EVERYTHING
        connection.commit()

        print(f"[DEBUG] UPI Order #{order_id} created successfully")

        provider = (product.get('api_provider') or '').lower()
        returned_status = 'success' if provider in ('smile', 'bushan') else 'pending'
        returned_message = 'Order created successfully' if returned_status == 'success' else 'Order created. Awaiting manual processing.'
        return jsonify({
            'success': True,
            'order_id': order_id,
            'status': returned_status,
            'message': returned_message,
            'utr': utr,
            'amount': amount
        })

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"[ERROR] UPI order creation failed: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# ---------------- CREATE ORDER ----------------
@app.route("/api/create-upi-order", methods=["POST"])
def create_upi_order():
    data = request.json
    print("[KANGLEI] Create Order Payload:", data)

    if "user_id" not in session:
        return jsonify({"success": False, "message": "Login required"}), 401

    db_user_id = session["user_id"]
    user_id = data.get("userId")
    zone_id = data.get("zoneId")
    product_id = data.get("productId")
    amount = float(data.get("amount", 0))

    # Get user mobile (from session user)
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT phone FROM users WHERE id=%s", (db_user_id,))
        user = cur.fetchone()

    if not user or not user.get("phone"):
        return jsonify({"success": False, "message": "Mobile number required"}), 400

    customer_mobile = user["phone"]
    order_id = str(int(time.time() * 1000))  # unique order id

    payload = {
        "customer_mobile": customer_mobile,
        "user_token": KANGLEI_USER_TOKEN,
        "amount": str(amount),
        "order_id": order_id,
        "redirect_url": "https://kendyenterprises.in/upi_create_order_status/" + order_id,
        "remark1": "wallet_topup",
        "remark2": "upi"
    }

    r = requests.post(KANGLEI_CREATE_URL, data=payload, timeout=30).json()
    print("[KANGLEI] API Response:", r)

    if r.get("status") is True:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO kanglei_orders
                    (order_id, customer_mobile, user_id, amount, status, payment_url, userid, zoneid, product_id)
                    VALUES (%s,%s,%s,%s,'PENDING',%s,%s,%s,%s)
                """, (
                    order_id,
                    customer_mobile,
                    db_user_id,
                    amount,
                    r["result"]["payment_url"],
                    user_id,
                    zone_id,
                    product_id
                ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("[DB ERROR]", e)
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "order_id": order_id,
            "payment_url": r["result"]["payment_url"]
        })

    return jsonify({"success": False, "error": r}), 400

@app.route("/api/check-upi-status/<order_id>")
def check_upi_status(order_id):
    payload = {
        "user_token": KANGLEI_USER_TOKEN,
        "order_id": order_id
    }

    try:
        r = requests.post(KANGLEI_STATUS_URL, data=payload, timeout=30).json()
        print("[KANGLEI STATUS]", r)
    except Exception as e:
        print("[KANGLEI STATUS ERROR]", e)
        # Mark as FAILED in DB
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE kanglei_orders SET status='FAILED' WHERE order_id=%s", (order_id,))
            conn.commit()
            conn.close()
        return jsonify({"success": False, "error": "API error"}), 500

    # If API returns error or not found
    if not r or r.get("status") in [None, "ERROR", "FAILED"]:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE kanglei_orders SET status='FAILED' WHERE order_id=%s", (order_id,))
            conn.commit()
            conn.close()
        return jsonify({"success": False, "error": r.get("message", "Order not found or failed")}), 404


    # If completed/success (handle both Kanglei and Xtragateway response structures)
    result = r.get("result")
    is_success = False
    utr = None
    # Kanglei: {"status": True, ... "result": {"txnStatus": "SUCCESS", ...}}
    if r.get("status") is True and result and result.get("txnStatus") == "SUCCESS":
        is_success = True
        utr = result.get("utr")
    # Xtragateway: {"status": "COMPLETED", ... "result": {"status": "SUCCESS", ...}}
    elif r.get("status") == "COMPLETED" and result and result.get("status") == "SUCCESS":
        is_success = True
        utr = result.get("utr")

    if is_success:
        if result:
            process_create_order_success(result)
        # Now mark order as SUCCESS (if not already)
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE kanglei_orders SET status='SUCCESS', utr=%s WHERE order_id=%s", (utr, order_id))
            conn.commit()
            conn.close()
        # Return status: SUCCESS for frontend redirect
        return jsonify({"success": True, "status": "SUCCESS", "utr": utr})

    # If result is None or not success, treat as failed
    if r.get("status") == "COMPLETED" and result is None:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE kanglei_orders SET status='FAILED' WHERE order_id=%s", (order_id,))
            conn.commit()
            conn.close()
        return jsonify({"success": False, "status": "FAILED", "error": r.get("message", "Order not found or failed")}), 404

    # Still pending
    return jsonify({"pending": True, "status": "PENDING"})

# Alias for frontend polling compatibility
@app.route('/check-order-status/<order_id>')
def check_order_status_alias(order_id):
    return check_upi_status(order_id)

@app.route('/upi_create_order_status/<order_id>')
def upi_create_order_status(order_id):
    return render_template("order-status.html", order_id=order_id)

# ---------------- UPDATE MOBILE ----------------
@app.route("/update-mobile", methods=["POST"])
def update_mobile():
    data = request.get_json()
    phone = data.get("phone")
    if not phone:
        return jsonify({"status": False, "message": "No phone number provided."}), 400

    # Get user_id from session or request context
    user_id = None
    if hasattr(request, 'user') and getattr(request, 'user', None):
        user_id = request.user.id
    elif 'user_id' in session:
        user_id = session['user_id']
    else:
        return jsonify({"status": False, "message": "User not logged in."}), 401

    db = get_db_connection()
    with db.cursor() as cur:
        cur.execute("UPDATE users SET phone=%s WHERE id=%s", (phone, user_id))
        db.commit()

    return jsonify({"status": True, "message": "Mobile number updated successfully."})
# ----------------ADD FUND CREATE ORDER ----------------
@app.route("/api/create-kanglei-upi-order", methods=["POST"])
def create_kanglei_upi_order():
    data = request.json
    print("[KANGLEI] Create Order Payload:", data)

    if "user_id" not in session:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id = session["user_id"]
    payment_method = data.get("payment_method", "upi").lower()

    # Get user mobile and check if reseller
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT phone, is_reseller FROM users WHERE id=%s", (user_id,))
        user = cur.fetchone()

    if not user or not user.get("phone"):
        return jsonify({"success": False, "message": "Mobile number required"}), 400

    customer_mobile = user["phone"]
    is_user_reseller = bool(user.get("is_reseller", False))
    
    # Handle SOC (Bank Transfer) Payment
    if payment_method == "soc":
        soc_reference = data.get("soc_reference", "")
        if not soc_reference:
            return jsonify({"success": False, "message": "SOC reference number is required"}), 400
        
        amount = str(data["amount"])
        order_id = str(int(time.time() * 1000))
        
        try:
            with conn.cursor() as cur:
                # First try to add columns if they don't exist
                try:
                    cur.execute("ALTER TABLE kanglei_orders ADD COLUMN payment_method VARCHAR(50) DEFAULT 'upi' AFTER status")
                except:
                    pass  # Column already exists
                try:
                    cur.execute("ALTER TABLE kanglei_orders ADD COLUMN soc_reference VARCHAR(100) NULL AFTER payment_method")
                except:
                    pass  # Column already exists
                
                # Now insert the order
                cur.execute("""
                    INSERT INTO kanglei_orders
                    (order_id, customer_mobile, user_id, amount, status, payment_method, soc_reference)
                    VALUES (%s,%s,%s,%s,'PENDING','soc',%s)
                """, (
                    order_id,
                    customer_mobile,
                    user_id,
                    amount,
                    soc_reference
                ))
            conn.commit()
            conn.close()
            
            # Send WhatsApp notification to user
            try:
                send_whatsapp_notification(
                    customer_mobile,
                    f"Your SOC payment for ₹{amount} has been received with reference: {soc_reference}. Order ID: {order_id}"
                )
            except Exception as e:
                print("[WHATSAPP ERROR]", e)
            
            # Send admin notification
            try:
                send_admin_telegram_notification(
                    f"🔔 New SOC Payment Received\n\n"
                    f"Order ID: {order_id}\n"
                    f"Amount: ₹{amount}\n"
                    f"SOC Reference: {soc_reference}\n"
                    f"User ID: {user_id}\n"
                    f"Mobile: {customer_mobile}\n\n"
                    f"Status: Pending verification"
                )
            except Exception as e:
                print("[ADMIN TELEGRAM ERROR]", e)
            
            return jsonify({
                "success": True,
                "order_id": order_id,
                "message": "Your SOC payment has been submitted. We'll verify it within 24 hours.",
                "payment_method": "soc"
            })
        except Exception as e:
            conn.rollback()
            conn.close()
            print("[DB ERROR]", e)
            return jsonify({"success": False, "error": str(e)}), 500

    # Handle UPI Payment (with 2% extra charge only for resellers)
    order_id = str(int(time.time() * 1000))  # unique order id
    amount = float(data["amount"])
    
    # Add 2% charge for UPI only if user is a reseller
    if is_user_reseller:
        final_amount = amount * 1.02
    else:
        final_amount = amount
    
    payload = {
        "customer_mobile": customer_mobile,
        "user_token": KANGLEI_USER_TOKEN,
        "amount": str(final_amount),
        "order_id": order_id,
        "redirect_url": "https://kendyenterprises.in/upi_order_status/" + order_id,
        "remark1": "wallet_topup",
        "remark2": "upi"
    }

    r = requests.post(KANGLEI_CREATE_URL, data=payload, timeout=30).json()
    print("[KANGLEI] API Response:", r)

    if r.get("status") is True:
        try:
            with conn.cursor() as cur:
                # First try to add columns if they don't exist
                try:
                    cur.execute("ALTER TABLE kanglei_orders ADD COLUMN payment_method VARCHAR(50) DEFAULT 'upi' AFTER status")
                except:
                    pass  # Column already exists
                try:
                    cur.execute("ALTER TABLE kanglei_orders ADD COLUMN soc_reference VARCHAR(100) NULL AFTER payment_method")
                except:
                    pass  # Column already exists
                
                # Now insert the order
                cur.execute("""
                    INSERT INTO kanglei_orders
                    (order_id, customer_mobile, user_id, amount, status, payment_url, payment_method)
                    VALUES (%s,%s,%s,%s,'PENDING',%s,'upi')
                """, (
                    order_id,
                    customer_mobile,
                    user_id,
                    str(final_amount),
                    r["result"]["payment_url"]
                ))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("[DB ERROR]", e)
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "order_id": order_id,
            "payment_url": r["result"]["payment_url"],
            "final_amount": final_amount
        })

    conn.close()
    return jsonify({"success": False, "error": r}), 400



@app.route("/api/check-kanglei-status/<order_id>")
def check_kanglei_status(order_id):
    payload = {
        "user_token": KANGLEI_USER_TOKEN,
        "order_id": order_id
    }

    try:
        r = requests.post(KANGLEI_STATUS_URL, data=payload, timeout=30).json()
        print("[KANGLEI STATUS]", r)
    except Exception as e:
        print("[KANGLEI STATUS ERROR]", e)
        # Mark as FAILED in DB
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE kanglei_orders SET status='FAILED' WHERE order_id=%s", (order_id,))
            conn.commit()
            conn.close()
        return jsonify({"success": False, "error": "API error"}), 500

    # If API returns error or not found
    if not r or r.get("status") in [None, "ERROR", "FAILED"]:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE kanglei_orders SET status='FAILED' WHERE order_id=%s", (order_id,))
            conn.commit()
            conn.close()
        return jsonify({"success": False, "error": r.get("message", "Order not found or failed")}), 404


    # If completed/success (handle both Kanglei and Xtragateway response structures)
    result = r.get("result")
    is_success = False
    utr = None
    # Kanglei: {"status": True, ... "result": {"txnStatus": "SUCCESS", ...}}
    if r.get("status") is True and result and result.get("txnStatus") == "SUCCESS":
        is_success = True
        utr = result.get("utr")
    # Xtragateway: {"status": "COMPLETED", ... "result": {"status": "SUCCESS", ...}}
    elif r.get("status") == "COMPLETED" and result and result.get("status") == "SUCCESS":
        is_success = True
        utr = result.get("utr")

    if is_success:
        if result:
            process_kanglei_success(result)
        # Now mark order as SUCCESS (if not already)
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE kanglei_orders SET status='SUCCESS', utr=%s WHERE order_id=%s", (utr, order_id))
            conn.commit()
            conn.close()
        # Return status: SUCCESS for frontend redirect
        return jsonify({"success": True, "status": "SUCCESS", "utr": utr})

    # If result is None or not success, treat as failed
    if r.get("status") == "COMPLETED" and result is None:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("UPDATE kanglei_orders SET status='FAILED' WHERE order_id=%s", (order_id,))
            conn.commit()
            conn.close()
        return jsonify({"success": False, "status": "FAILED", "error": r.get("message", "Order not found or failed")}), 404

    # Still pending
    return jsonify({"pending": True, "status": "PENDING"})

# Alias for frontend polling compatibility
@app.route('/check-status/<order_id>')
def check_status_alias(order_id):
    return check_kanglei_status(order_id)

@app.route('/payment/webhook', methods=['POST'])
def kanglei_webhook():
    data = request.form
    print("[KANGLEI WEBHOOK]", data)

    if data.get("status") == "SUCCESS":
        process_kanglei_success({
            "orderId": data.get("order_id"),
            "amount": data.get("amount"),
            "utr": data.get("utr")
        })
        return "OK"

    return "IGNORED", 400

@app.route('/upi_order_status/<order_id>')
def upi_order_status(order_id):
    return render_template("upi_order_status.html", order_id=order_id)

# ==================== ADMIN PANEL ROUTES ====================

def is_admin(user_id):
    """Check if user is admin"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT is_admin FROM users WHERE id=%s", (user_id,))
            user = cursor.fetchone()
        conn.close()
        return user and user.get('is_admin') == 1
    except Exception:
        return False

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Get statistics
            cursor.execute("SELECT COUNT(*) as total FROM users")
            total_users = cursor.fetchone().get('total', 0)
            
            cursor.execute("SELECT COUNT(*) as total FROM orders")
            total_orders = cursor.fetchone().get('total', 0)
            
            cursor.execute("SELECT COUNT(*) as total FROM orders WHERE status='success'")
            successful_orders = cursor.fetchone().get('total', 0)
            
            cursor.execute("SELECT SUM(price) as total FROM orders WHERE status='success'")
            revenue = cursor.fetchone().get('total', 0) or 0

            # Monthly sales: sum of successful orders from the first day of current month
            try:
                month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d 00:00:00')
                cursor.execute("SELECT SUM(price) as total FROM orders WHERE status='success' AND create_date >= %s", (month_start,))
                monthly_sales = cursor.fetchone().get('total') or 0
            except Exception:
                monthly_sales = 0

            # Lifetime sales: use revenue computed above (safe numeric)
            try:
                lifetime_sales = float(revenue or 0)
            except Exception:
                lifetime_sales = 0
            
            cursor.execute("SELECT COUNT(*) as total FROM product")
            total_products = cursor.fetchone().get('total', 0)
            
            cursor.execute("SELECT COUNT(*) as total FROM category")
            total_categories = cursor.fetchone().get('total', 0)
            
            # Recent orders
            cursor.execute("""
                SELECT o.id, o.product_name, o.price, o.status, o.create_date, u.username
                FROM orders o
                JOIN users u ON o.user_id = u.id
                ORDER BY o.create_date DESC
                LIMIT 10
            """)
            recent_orders = cursor.fetchall()
            
            # Recent users
            cursor.execute("""
                SELECT id, username, email, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent_users = cursor.fetchall()
        
        conn.close()
        # Attempt to fetch Smile.one points for Brazil and Philippines to display on admin dashboard
        smile_balance_br = None
        smile_balance_ph = None
        try:
            creds = get_api_credentials('smile')
            if creds:
                bal_br = get_smile_balance(region='br', uid=creds.get('uid'), email=creds.get('email'), key=creds.get('api_key'))
                if bal_br.get('success'):
                    smile_balance_br = bal_br.get('smile_points')
                else:
                    # API returned an error; mark explicitly so template can show 'Error'
                    smile_balance_br = 'error'

                bal_ph = get_smile_balance(region='ph', uid=creds.get('uid'), email=creds.get('email'), key=creds.get('api_key'))
                if bal_ph.get('success'):
                    smile_balance_ph = bal_ph.get('smile_points')
                else:
                    smile_balance_ph = 'error'
            else:
                # No credentials configured -> leave as None (template will show Empty)
                smile_balance_br = None
                smile_balance_ph = None
        except Exception as e:
            print(f"[WARN] Failed to fetch Smile.one balances: {e}")
            smile_balance_br = 'error'
            smile_balance_ph = 'error'

        # Fetch 1gamestopup balance
        gamestopup_balance_inr = None
        gamestopup_balance_usd = None
        try:
            bal_inr = get_1gamestopup_balance(currency='INR')
            if bal_inr.get('success'):
                gamestopup_balance_inr = bal_inr.get('balance')
            else:
                gamestopup_balance_inr = 'error'

            bal_usd = get_1gamestopup_balance(currency='USD')
            if bal_usd.get('success'):
                gamestopup_balance_usd = bal_usd.get('balance')
            else:
                gamestopup_balance_usd = 'error'
        except Exception as e:
            print(f"[WARN] Failed to fetch 1gamestopup balances: {e}")
            gamestopup_balance_inr = 'error'
            gamestopup_balance_usd = 'error'

        return render_template('admin/dashboard.html',
                     total_users=total_users,
                     total_orders=total_orders,
                     successful_orders=successful_orders,
                     revenue=revenue,
                     monthly_sales=monthly_sales,
                     lifetime_sales=lifetime_sales,
                     total_products=total_products,
                     total_categories=total_categories,
                     recent_orders=recent_orders,
                     recent_users=recent_users,
                     smile_balance_br=smile_balance_br,
                     smile_balance_ph=smile_balance_ph,
                     gamestopup_balance_inr=gamestopup_balance_inr,
                     gamestopup_balance_usd=gamestopup_balance_usd)
    except Exception as e:
        print(f"[ERROR] Admin dashboard error: {str(e)}")
        return render_template('admin/error.html', error=str(e))

@app.route('/admin/users')
def admin_users():
    """Manage users with search"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    page = int(request.args.get('page', 1))
    search = request.args.get('search', '')
    per_page = 20
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Build WHERE clause for search
            where_sql = ""
            params = []
            
            if search:
                where_sql = " WHERE username LIKE %s OR email LIKE %s OR phone LIKE %s"
                search_param = f"%{search}%"
                params = [search_param, search_param, search_param]
            
            # Count total
            count_sql = f"SELECT COUNT(*) as total FROM users {where_sql}"
            cursor.execute(count_sql, params)
            total_users = cursor.fetchone().get('total', 0)
            
            offset = (page - 1) * per_page
            
            # Fetch users with brl_balance and order count
            fetch_sql = f"""
                SELECT u.id, u.username, u.email, u.phone, u.balance, u.brl_balance, 
                       u.is_reseller, u.is_admin, u.created_at, u.knd_coin,
                       COUNT(o.id) as total_orders
                FROM users u
                LEFT JOIN orders o ON u.id = o.user_id
                {where_sql}
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(fetch_sql, params + [per_page, offset])
            users = cursor.fetchall()
        
        conn.close()
        
        total_pages = (total_users + per_page - 1) // per_page
        return render_template('admin/users.html',
                             users=users,
                             page=page,
                             total_pages=total_pages,
                             total_users=total_users,
                             search=search)
    except Exception as e:
        print(f"[ERROR] Admin users error: {str(e)}")
        return render_template('admin/error.html', error=str(e))

@app.route('/admin/products')
def admin_products():
    """Manage products with filters"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    category_filter = request.args.get('category_filter', '')
    provider_filter = request.args.get('provider_filter', '')
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Build WHERE clause
            where_clauses = []
            params = []
            
            if category_filter:
                where_clauses.append("c.category_name = %s")
                params.append(category_filter)
            
            if provider_filter:
                where_clauses.append("p.api_provider = %s")
                params.append(provider_filter)
            
            where_sql = ""
            if where_clauses:
                where_sql = " WHERE " + " AND ".join(where_clauses)
            
            # Fetch products
            fetch_sql = f"""
                SELECT p.id, p.product_name, p.price, p.reseller_price, p.product_id, 
                       p.category, c.category_name, p.status, p.api_provider, p.region, p.created_at, p.image
                FROM product p
                LEFT JOIN category c ON p.category_id = c.id
                {where_sql}
                ORDER BY p.id ASC
            """
            cursor.execute(fetch_sql, params)
            products = cursor.fetchall()
            
            # Get all categories for filter dropdown
            cursor.execute("SELECT id, category_name FROM category WHERE status=1 ORDER BY category_name")
            categories = cursor.fetchall()
            
            # Get all api providers for filter dropdown
            cursor.execute("SELECT DISTINCT api_provider FROM product WHERE api_provider IS NOT NULL ORDER BY api_provider")
            providers = cursor.fetchall()
        
        conn.close()
        
        return render_template('admin/products.html',
                             products=products,
                             categories=categories,
                             providers=providers,
                             category_filter=category_filter,
                             provider_filter=provider_filter)
    except Exception as e:
        print(f"[ERROR] Admin products error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/admin/categories')
def admin_categories():
    """Manage categories"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, category_name, description, status, category_type, created_at
                FROM category
                ORDER BY created_at DESC
            """)
            categories = cursor.fetchall()
        
        conn.close()
        
        return render_template('admin/categories.html', categories=categories)
    except Exception as e:
        print(f"[ERROR] Admin categories error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/admin/api-credentials')
def admin_api_credentials():
    """Manage API credentials"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, provider, uid, email, api_key, status, created_at, updated_at
                FROM api_credentials
                ORDER BY created_at DESC
            """)
            credentials = cursor.fetchall()
        
        conn.close()
        
        return render_template('admin/api-credentials.html', credentials=credentials)
    except Exception as e:
        print(f"[ERROR] Admin API credentials error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/admin/orders')
def admin_orders():
    """Manage orders with filters"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    page = int(request.args.get('page', 1))
    status_filter = request.args.get('status', 'all')
    user_filter = request.args.get('user_filter', '')
    product_filter = request.args.get('product_filter', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    per_page = 20
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Build WHERE clause dynamically
            where_clauses = []
            params = []
            
            if status_filter != 'all':
                where_clauses.append("o.status=%s")
                params.append(status_filter)
            
            if user_filter:
                where_clauses.append("(u.username LIKE %s OR u.email LIKE %s)")
                params.extend([f"%{user_filter}%", f"%{user_filter}%"])
            
            if product_filter:
                where_clauses.append("o.product_name LIKE %s")
                params.append(f"%{product_filter}%")
            
            if start_date:
                where_clauses.append("o.create_date >= %s")
                params.append(f"{start_date} 00:00:00")
            
            if end_date:
                where_clauses.append("o.create_date <= %s")
                params.append(f"{end_date} 23:59:59")
            
            where_sql = " AND ".join(where_clauses)
            if where_sql:
                where_sql = " WHERE " + where_sql
            
            # Count total
            count_sql = f"SELECT COUNT(*) as total FROM orders o JOIN users u ON o.user_id = u.id {where_sql}"
            cursor.execute(count_sql, params)
            total_orders = cursor.fetchone().get('total', 0)
            
            offset = (page - 1) * per_page
            
            # Fetch orders with payment method name
            fetch_sql = f"""
                SELECT o.id, o.userid, o.zoneid, o.product_name, o.price, o.status, o.create_date, u.username, u.email,
                       pm.method_name AS payment_method_name
                FROM orders o
                JOIN users u ON o.user_id = u.id
                LEFT JOIN payment_method pm ON o.payment_method_id = pm.id
                {where_sql}
                ORDER BY o.create_date DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(fetch_sql, params + [per_page, offset])
            orders = cursor.fetchall()
        
        conn.close()
        
        total_pages = (total_orders + per_page - 1) // per_page
        return render_template('admin/orders.html',
                             orders=orders,
                             page=page,
                             total_pages=total_pages,
                             total_orders=total_orders,
                             status_filter=status_filter,
                             user_filter=user_filter,
                             product_filter=product_filter,
                             start_date=start_date,
                             end_date=end_date)
    except Exception as e:
        print(f"[ERROR] Admin orders error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/admin/payment-methods')
def admin_payment_methods():
    """Manage payment methods"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, method_name, bharatpe_merchant_id, bharatpe_token, image, status, created_at
                FROM payment_method
                ORDER BY created_at DESC
            """)
            methods = cursor.fetchall()
        
        conn.close()
        
        return render_template('admin/payment-methods.html', methods=methods)
    except Exception as e:
        print(f"[ERROR] Admin payment methods error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/admin/banners')
def admin_banners():
    """Manage banners"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, image, status, created_at
                FROM banner
                ORDER BY created_at DESC
            """)
            banners = cursor.fetchall()
        
        conn.close()
        
        return render_template('admin/banners.html', banners=banners)
    except Exception as e:
        print(f"[ERROR] Admin banners error: {str(e)}")
        return render_template('error.html', error=str(e))

@app.route('/admin/hope')
def admin_hope():
    """Display Hopestore services management page"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    return render_template('admin/hope.html')

@app.route('/admin/hope-fetch')
def admin_hope_fetch():
    """Fetch services from Hopestore API"""
    api_key = "APILEQNC71765200725999"
    url = "https://api.hopestore.id/service"
    
    payload = {
        "api_key": api_key
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('status') == True:
            services = data.get('data', [])
            return jsonify({
                'success': True,
                'message': data.get('msg', 'Services fetched successfully'),
                'services': services,
                'count': len(services)
            })
        else:
            return jsonify({
                'success': False,
                'message': data.get('msg', 'Failed to fetch services')
            })
    
    except requests.exceptions.RequestException as e:
        print(f"[Hopestore API Error] {e}")
        return jsonify({
            'success': False,
            'message': f'API request failed: {str(e)}'
        })
    except Exception as e:
        print(f"[Hopestore API Error] {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })
# ==================== ADMIN API ENDPOINTS ====================

@app.route('/api/admin/user/<int:user_id>', methods=['GET', 'POST', 'PUT'])
@app.route('/api/admin/user', methods=['POST'])
def api_admin_user(user_id=None):
    """Get, add, or update user"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        
        # GET: Fetch single user by ID
        if request.method == 'GET':
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, username, email, phone, password, balance, brl_balance, is_reseller, is_admin, created_at, knd_coin
                    FROM users WHERE id=%s
                """, (user_id,))
                user = cursor.fetchone()
            conn.close()
            
            if not user:
                return jsonify({'success': False, 'error': 'User not found'}), 404
            
            return jsonify({'success': True, 'user': user})
        
        # POST: Add new user
        elif request.method == 'POST':
            data = request.get_json()
            
            # Validate required fields
            if not data.get('username') or not data.get('email') or not data.get('password'):
                return jsonify({'success': False, 'error': 'Username, email, and password are required'}), 400
            
            with conn.cursor() as cursor:
                # Check if user exists
                cursor.execute("SELECT id FROM users WHERE username=%s OR email=%s", 
                              (data['username'], data['email']))
                if cursor.fetchone():
                    conn.close()
                    return jsonify({'success': False, 'error': 'Username or email already exists'}), 409
                
                # Hash password
                hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                # Insert new user
                cursor.execute("""
                    INSERT INTO users (username, email, phone, password, balance, is_reseller, is_admin, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    data['username'],
                    data['email'],
                    data.get('phone') or None,
                    hashed_password,
                    float(data.get('balance', 0.00)),
                    int(data.get('is_reseller', 0)),
                    int(data.get('is_admin', 0))
                ))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'User created successfully'})
        
        # PUT: Update existing user
        elif request.method == 'PUT':
            data = request.get_json()
            
            with conn.cursor() as cursor:
                updates = []
                values = []
                
                # Update username
                if 'username' in data and data['username']:
                    updates.append("username=%s")
                    values.append(data['username'])
                
                # Update email
                if 'email' in data and data['email']:
                    updates.append("email=%s")
                    values.append(data['email'])
                
                # Update phone
                if 'phone' in data:
                    updates.append("phone=%s")
                    values.append(data['phone'] or None)
                
                # Update password (only if provided)
                if 'password' in data and data['password']:
                    hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    updates.append("password=%s")
                    values.append(hashed_password)
                
                # Update balance
                if 'balance' in data and data['balance'] is not None:
                    updates.append("balance=%s")
                    values.append(float(data['balance']))
                
                # Update brl_balance
                if 'brl_balance' in data and data['brl_balance'] is not None:
                    updates.append("brl_balance=%s")
                    values.append(float(data['brl_balance']))
                
                # Update knd_coin
                if 'knd_coin' in data and data['knd_coin'] is not None:
                    updates.append("knd_coin=%s")
                    values.append(float(data['knd_coin']))
                
                # Update is_reseller
                if 'is_reseller' in data:
                    updates.append("is_reseller=%s")
                    values.append(int(data['is_reseller']))
                
                # Update is_admin
                if 'is_admin' in data:
                    updates.append("is_admin=%s")
                    values.append(int(data['is_admin']))
                
                if updates:
                    values.append(user_id)
                    sql = f"UPDATE users SET {', '.join(updates)} WHERE id=%s"
                    cursor.execute(sql, values)
                    conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'User updated successfully'})
    
    except Exception as e:
        print(f"[ERROR] Admin user API error: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/product', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_product():
    """Get/Add/update/delete product"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        
        # GET: Fetch single product by ID
        if request.method == 'GET':
            product_id = request.args.get('id')
            if not product_id:
                return jsonify({'success': False, 'error': 'Product ID required'}), 400
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT p.*, c.category_name 
                    FROM product p 
                    LEFT JOIN category c ON p.category_id = c.id 
                    WHERE p.id=%s
                """, (product_id,))
                product = cursor.fetchone()
            
            conn.close()
            
            if not product:
                return jsonify({'success': False, 'error': 'Product not found'}), 404
            
            # Convert datetime to string
            product_data = dict(product)
            if product_data.get('created_at'):
                product_data['created_at'] = product_data['created_at'].strftime('%Y-%m-%d')
            
            return jsonify({'success': True, 'data': product_data})
        
        data = request.get_json()
        
        if request.method == 'POST':
            # Validate required fields
            if not data.get('product_name'):
                return jsonify({'success': False, 'error': 'Product name is required'}), 400
            if not data.get('price'):
                return jsonify({'success': False, 'error': 'Price is required'}), 400
            if not data.get('product_id'):
                return jsonify({'success': False, 'error': 'Product ID is required'}), 400
            if not data.get('api_provider'):
                return jsonify({'success': False, 'error': 'API Provider is required'}), 400
            
            # Validate category_id specifically
            category_id_raw = data.get('category_id')
            if not category_id_raw:
                return jsonify({'success': False, 'error': 'Category ID is required'}), 400
            
            try:
                category_id = int(category_id_raw)
            except (ValueError, TypeError) as e:
                print(f"[ERROR] Invalid category_id: {category_id_raw}, error: {str(e)}")
                return jsonify({'success': False, 'error': f'Invalid category ID: {category_id_raw}'}), 400
            
            with conn.cursor() as cursor:
                # Get category name - either from category field or fetch from category_id
                category = data.get('category')
                
                if not category:
                    # Fetch category name from database
                    cursor.execute("SELECT category_name FROM category WHERE id=%s", (category_id,))
                    result = cursor.fetchone()
                    category = result['category_name'] if result else 'Unknown'
                    print(f"[DEBUG] Fetched category name from DB: {category}")
                
                print(f"[DEBUG] Product POST - Name: {data.get('product_name')}, Category ID: {category_id}, Category Name: {category}")
                
                # Handle image field: save base64 data URL to file if provided
                # Only accept uploaded files from /static/uploads/categories/
                image = None
                if data.get('image'):
                    img_val = data.get('image')
                    if isinstance(img_val, str) and img_val.startswith('data:'):
                        saved = save_base64_image(img_val)
                        image = saved or None
                    # Ignore external URLs - only accept uploaded files
                    elif img_val.startswith('/static/uploads/categories/'):
                        image = img_val
                
                cursor.execute("""
                    INSERT INTO product
                    (product_name, price, reseller_price, product_id, category, category_id, image, status, api_provider, region)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    data.get('product_name'),
                    float(data.get('price', 0)),
                    float(data.get('reseller_price', 0)) if data.get('reseller_price') else None,
                    data.get('product_id'),
                    category,
                    category_id,
                    image,
                    data.get('status', 'active'),
                    data.get('api_provider'),
                    data.get('region', 'PH')
                ))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Product created successfully'})
        
        elif request.method == 'PUT':
            product_id = data.get('id')
            with conn.cursor() as cursor:
                # Get category name - either from category field or fetch from category_id
                category = data.get('category')
                category_id = data.get('category_id')
                
                if category_id and not category:
                    # Fetch category name from database if only ID provided
                    cursor.execute("SELECT category_name FROM category WHERE id=%s", (int(category_id),))
                    result = cursor.fetchone()
                    category = result['category_name'] if result else None
                
                # Build dynamic UPDATE query based on provided fields
                updates = []
                values = []
                
                if data.get('product_name'):
                    updates.append("product_name=%s")
                    values.append(data.get('product_name'))
                
                if data.get('price'):
                    updates.append("price=%s")
                    values.append(float(data.get('price')))

                if data.get('product_id'):
                    updates.append("product_id=%s")
                    values.append(data.get('product_id'))
                
                if 'reseller_price' in data:
                    updates.append("reseller_price=%s")
                    values.append(float(data.get('reseller_price')) if data.get('reseller_price') else None)
                
                if data.get('status'):
                    updates.append("status=%s")
                    values.append(data.get('status'))
                
                if data.get('api_provider'):
                    updates.append("api_provider=%s")
                    values.append(data.get('api_provider'))
                
                if data.get('region'):
                    updates.append("region=%s")
                    values.append(data.get('region'))
                
                if category:
                    updates.append("category=%s")
                    values.append(category)
                
                if category_id:
                    updates.append("category_id=%s")
                    values.append(int(category_id))
                
                if 'image' in data:
                    updates.append("image=%s")
                    img_val = data.get('image')
                    if isinstance(img_val, str) and img_val.startswith('data:'):
                        saved = save_base64_image(img_val)
                        values.append(saved or img_val)
                    elif isinstance(img_val, str) and img_val.startswith('/static/uploads/categories/'):
                        values.append(img_val)
                    else:
                        # Ignore external URLs - only accept uploaded files from static folder
                        values.append(None)
                
                if updates:
                    values.append(product_id)
                    sql = f"UPDATE product SET {', '.join(updates)} WHERE id=%s"
                    cursor.execute(sql, values)
                    conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Product updated successfully'})
        
        elif request.method == 'DELETE':
            product_id = data.get('id')
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM product WHERE id=%s", (product_id,))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Product deleted successfully'})
    
    except Exception as e:
        print(f"[ERROR] Admin product API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/category', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_category():
    """Get/Add/update/delete category"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        
        # GET: Fetch single category by ID
        if request.method == 'GET':
            cat_id = request.args.get('id')
            if not cat_id:
                return jsonify({'success': False, 'error': 'Category ID required'}), 400
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, category_name, description, image, status, category_type, created_at
                    FROM category
                    WHERE id=%s
                """, (cat_id,))
                category = cursor.fetchone()
            
            conn.close()
            
            if not category:
                return jsonify({'success': False, 'error': 'Category not found'}), 404
            
            return jsonify({'success': True, 'data': category})
        
        data = request.get_json()
        
        if request.method == 'POST':
            with conn.cursor() as cursor:
                # handle image: only accept uploaded files from /static/uploads/categories/
                image_path = None
                if data.get('image'):
                    img_val = data.get('image')
                    if isinstance(img_val, str) and img_val.startswith('data:'):
                        saved = save_base64_image(img_val)
                        image_path = saved
                    elif isinstance(img_val, str) and img_val.startswith('/static/uploads/categories/'):
                        image_path = img_val
                    # Ignore external URLs - only accept uploaded files

                cursor.execute("""
                    INSERT INTO category
                    (category_name, description, image, status, category_type)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    data.get('category_name'),
                    data.get('description'),
                    image_path,
                    data.get('status', 1),
                    data.get('category_type', 'OTHER GAME')
                ))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Category created successfully'})
        
        elif request.method == 'PUT':
            category_id = data.get('id')
            with conn.cursor() as cursor:
                # If image provided, only accept uploaded files from /static/uploads/categories/
                image_path = None
                if data.get('image'):
                    img_val = data.get('image')
                    if isinstance(img_val, str) and img_val.startswith('data:'):
                        image_path = save_base64_image(img_val)
                    elif isinstance(img_val, str) and img_val.startswith('/static/uploads/categories/'):
                        image_path = img_val
                    # Ignore external URLs - only accept uploaded files

                if image_path is not None:
                    cursor.execute("""
                        UPDATE category
                        SET category_name=%s, description=%s, image=%s, status=%s, category_type=%s
                        WHERE id=%s
                    """, (
                        data.get('category_name'),
                        data.get('description'),
                        image_path,
                        data.get('status'),
                        data.get('category_type'),
                        category_id
                    ))
                else:
                    cursor.execute("""
                        UPDATE category
                        SET category_name=%s, description=%s, status=%s, category_type=%s
                        WHERE id=%s
                    """, (
                        data.get('category_name'),
                        data.get('description'),
                        data.get('status'),
                        data.get('category_type'),
                        category_id
                    ))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Category updated successfully'})
        
        elif request.method == 'DELETE':
            category_id = data.get('id')
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM category WHERE id=%s", (category_id,))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Category deleted successfully'})
    
    except Exception as e:
        print(f"[ERROR] Admin category API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/api-credential', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_api_credential():
    """Get/Add/update/delete API credential"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        
        # GET: Fetch single credential by ID
        if request.method == 'GET':
            cred_id = request.args.get('id')
            if not cred_id:
                return jsonify({'success': False, 'error': 'Credential ID required'}), 400
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, provider, uid, email, api_key, status, created_at, updated_at
                    FROM api_credentials
                    WHERE id=%s
                """, (cred_id,))
                credential = cursor.fetchone()
            
            conn.close()
            
            if not credential:
                return jsonify({'success': False, 'error': 'Credential not found'}), 404
            
            return jsonify({'success': True, 'data': credential})
        
        data = request.get_json()
        
        if request.method == 'POST':
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO api_credentials
                    (provider, uid, email, api_key, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    data.get('provider', 'smile'),
                    data.get('uid'),
                    data.get('email'),
                    data.get('api_key'),
                    data.get('status', 1)
                ))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'API credential added successfully'})
        
        elif request.method == 'PUT':
            cred_id = data.get('id')
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE api_credentials
                    SET provider=%s, uid=%s, email=%s, api_key=%s, status=%s, updated_at=NOW()
                    WHERE id=%s
                """, (
                    data.get('provider', 'smile'),
                    data.get('uid'),
                    data.get('email'),
                    data.get('api_key'),
                    data.get('status'),
                    cred_id
                ))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'API credential updated successfully'})
        
        elif request.method == 'DELETE':
            cred_id = data.get('id')
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM api_credentials WHERE id=%s", (cred_id,))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'API credential deleted successfully'})
    
    except Exception as e:
        print(f"[ERROR] Admin API credential error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/order/<int:order_id>', methods=['PUT'])
def api_admin_order(order_id):
    """Update order status"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['pending', 'processing', 'success', 'failed', 'refunded']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, price FROM orders WHERE id=%s
            """, (order_id,))
            order = cursor.fetchone()
            
            if not order:
                conn.close()
                return jsonify({'success': False, 'error': 'Order not found'}), 404
            
            # If changing to refunded, refund the balance
            if new_status == 'refunded':
                cursor.execute("""
                    UPDATE users SET balance = balance + %s WHERE id=%s
                """, (order['price'], order['user_id']))
                
                # Log transaction
                cursor.execute("""
                    INSERT INTO transactions
                    (user_id, txn_type, amount, description, created_at)
                    VALUES (%s, 'credit', %s, %s, NOW())
                """, (order['user_id'], order['price'], f'Refund for order #{order_id}'))
            
            cursor.execute("""
                UPDATE orders SET status=%s WHERE id=%s
            """, (new_status, order_id))
            
            conn.commit()
        
        conn.close()
        return jsonify({'success': True, 'message': 'Order updated successfully'})
    
    except Exception as e:
        print(f"[ERROR] Admin order update error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/payment-method', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_payment_method():
    """Get/Add/update/delete payment method"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        
        # GET: Fetch single payment method by ID
        if request.method == 'GET':
            method_id = request.args.get('id')
            if not method_id:
                return jsonify({'success': False, 'error': 'Payment method ID required'}), 400
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, method_name, bharatpe_merchant_id, bharatpe_token, image, status, created_at
                    FROM payment_method
                    WHERE id=%s
                """, (method_id,))
                method = cursor.fetchone()
            
            conn.close()
            
            if not method:
                return jsonify({'success': False, 'error': 'Payment method not found'}), 404
            
            return jsonify({'success': True, 'data': method})
        
        data = request.get_json()
        
        if request.method == 'POST':
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO payment_method
                    (method_name, bharatpe_merchant_id, bharatpe_token, image, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    data.get('method_name'),
                    data.get('bharatpe_merchant_id'),
                    data.get('bharatpe_token'),
                    data.get('image'),
                    data.get('status', 1)
                ))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Payment method added successfully'})
        
        elif request.method == 'PUT':
            method_id = data.get('id')
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE payment_method
                    SET method_name=%s, bharatpe_merchant_id=%s, bharatpe_token=%s, image=%s, status=%s
                    WHERE id=%s
                """, (
                    data.get('method_name'),
                    data.get('bharatpe_merchant_id'),
                    data.get('bharatpe_token'),
                    data.get('image'),
                    data.get('status'),
                    method_id
                ))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Payment method updated successfully'})
        
        elif request.method == 'DELETE':
            method_id = data.get('id')
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM payment_method WHERE id=%s", (method_id,))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Payment method deleted successfully'})
    
    except Exception as e:
        print(f"[ERROR] Admin payment method error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/banner', methods=['GET', 'POST', 'PUT', 'DELETE'])
def api_admin_banner():
    """Get/Add/update/delete banner"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db_connection()
        
        # GET: Fetch single banner by ID
        if request.method == 'GET':
            banner_id = request.args.get('id')
            if not banner_id:
                return jsonify({'success': False, 'error': 'Banner ID required'}), 400
            
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, image, status, created_at
                    FROM banner
                    WHERE id=%s
                """, (banner_id,))
                banner = cursor.fetchone()
            
            conn.close()
            
            if not banner:
                return jsonify({'success': False, 'error': 'Banner not found'}), 404
            
            return jsonify({'success': True, 'data': banner})
        
        # Handle file uploads for POST and PUT
        if request.method in ['POST', 'PUT']:
            status = request.form.get('status', '1')
            image_file = request.files.get('image')
            
            if request.method == 'POST' and not image_file:
                return jsonify({'success': False, 'error': 'Image file is required'}), 400
            
            # Save uploaded image if provided
            image_path = None
            if image_file:
                image_path = save_uploaded_image(image_file, 'static/uploads/banners')
                if not image_path:
                    return jsonify({'success': False, 'error': 'Failed to save image'}), 500
            
            if request.method == 'POST':
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO banner
                        (image, status)
                        VALUES (%s, %s)
                    """, (image_path, status))
                    banner_id = cursor.lastrowid
                    conn.commit()
                
                conn.close()
                return jsonify({'success': True, 'message': 'Banner added successfully', 'banner_id': banner_id})
            
            elif request.method == 'PUT':
                banner_id = request.args.get('id') or request.form.get('id')
                if not banner_id:
                    return jsonify({'success': False, 'error': 'Banner ID required for update'}), 400
                
                # If no new image, keep existing
                if not image_path:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE banner
                            SET status=%s
                            WHERE id=%s
                        """, (status, banner_id))
                        conn.commit()
                else:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE banner
                            SET image=%s, status=%s
                            WHERE id=%s
                        """, (image_path, status, banner_id))
                        conn.commit()
                
                conn.close()
                return jsonify({'success': True, 'message': 'Banner updated successfully'})
        
        elif request.method == 'DELETE':
            banner_id = request.form.get('id') or request.get_json().get('id')
            if not banner_id:
                return jsonify({'success': False, 'error': 'Banner ID required'}), 400
            
            # Get banner info to delete file
            with conn.cursor() as cursor:
                cursor.execute("SELECT image FROM banner WHERE id=%s", (banner_id,))
                banner = cursor.fetchone()
                
                if banner and banner.get('image'):
                    # Delete physical file
                    try:
                        file_path = os.path.join(os.path.dirname(__file__), 'templates', '..', banner['image'].lstrip('/'))
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        print(f"[WARN] Failed to delete banner file: {str(e)}")
                
                cursor.execute("DELETE FROM banner WHERE id=%s", (banner_id,))
                conn.commit()
            
            conn.close()
            return jsonify({'success': True, 'message': 'Banner deleted successfully'})
    
    except Exception as e:
        print(f"[ERROR] Admin banner error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/fatchsmile')
def admin_fatchsmile():
    """Admin page to fetch Smile.one products."""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('index'))
    return render_template('admin/fatchsmile.html')

@app.route('/admin/verify-payments')
def admin_verify_payments():
    """Admin page to verify SOC (bank transfer) payments"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Fetch all SOC orders with non-null soc_reference and status not SUCCESS
            cursor.execute("""
                SELECT ko.id, ko.order_id, ko.customer_mobile, ko.user_id, ko.amount, 
                       ko.status, ko.soc_reference, ko.created_at, u.username, u.email
                FROM kanglei_orders ko
                JOIN users u ON ko.user_id = u.id
                WHERE ko.soc_reference IS NOT NULL 
                AND ko.payment_method = 'soc'
                AND ko.status != 'SUCCESS'
                ORDER BY ko.created_at DESC
            """)
            pending_payments = cursor.fetchall()
        
        conn.close()
        return render_template('admin/verify_payments.html', pending_payments=pending_payments)
    except Exception as e:
        print(f"[ERROR] Failed to fetch pending payments: {str(e)}")
        return render_template('admin/verify_payments.html', pending_payments=[])

@app.route('/api/admin/verify-payment', methods=['POST'])
def api_admin_verify_payment():
    """Verify SOC payment and credit user's brl_balance"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.get_json()
    kanglei_order_id = data.get('kanglei_order_id')
    
    if not kanglei_order_id:
        return jsonify({'success': False, 'message': 'Missing kanglei_order_id'}), 400
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Lock and fetch the SOC order
            cursor.execute("""
                SELECT id, order_id, user_id, amount, status, soc_reference
                FROM kanglei_orders
                WHERE id = %s AND soc_reference IS NOT NULL
                FOR UPDATE
            """, (kanglei_order_id,))
            order = cursor.fetchone()
            
            if not order:
                return jsonify({'success': False, 'message': 'Order not found or is not a SOC payment'}), 404
            
            # Check if already processed
            if order['status'] == 'SUCCESS':
                return jsonify({'success': False, 'message': 'Order already verified'}), 400
            
            user_id = order['user_id']
            amount = float(order['amount'])
            
            # Fetch user's current brl_balance
            cursor.execute("SELECT brl_balance FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return jsonify({'success': False, 'message': 'User not found'}), 404
            
            balance_before = float(user.get('brl_balance') or 0.00)
            balance_after = balance_before + amount
            
            # Update user's brl_balance
            cursor.execute("""
                UPDATE users SET brl_balance = brl_balance + %s WHERE id = %s
            """, (amount, user_id))
            
            # Update kanglei_orders status to SUCCESS
            cursor.execute("""
                UPDATE kanglei_orders SET status = 'SUCCESS' WHERE id = %s
            """, (kanglei_order_id,))
            
            # Log transaction in wallet_history
            cursor.execute("""
                INSERT INTO wallet_history 
                (user_id, amount_before, amount, transaction_type, reason, current_amount, created_at)
                VALUES (%s, %s, %s, 'credit', %s, %s, NOW())
            """, (user_id, balance_before, amount, f"SOC Payment Verified - Reference: {order['soc_reference']}", balance_after))
            
            conn.commit()
            
            # Send notification to user
            try:
                send_telegram_notification(f"✅ Your SOC payment of BRL {amount:.2f} has been verified and credited to your account!")
            except Exception as e:
                print(f"[ERROR] Failed to send telegram notification: {e}")
            
            return jsonify({
                'success': True,
                'message': 'Payment verified successfully',
                'amount': amount,
                'new_balance': balance_after
            })
    
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR] Payment verification failed: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500
    finally:
        if conn:
            conn.close()

@app.route('/maintenance')
def maintenance():
    return render_template('maintenance.html')

@app.route('/admin/maintenance', methods=['GET', 'POST'])
def admin_maintenance():
    """Toggle maintenance mode"""
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('auth'))
    
    maintenance_file = os.path.join(os.path.dirname(__file__), 'maintenance_mode.txt')
    maintenance_on = os.path.exists(maintenance_file)
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'enable':
            with open(maintenance_file, 'w') as f:
                f.write('1')
            maintenance_on = True
        elif action == 'disable':
            if os.path.exists(maintenance_file):
                os.remove(maintenance_file)
            maintenance_on = False
    
    return render_template('admin/maintenance.html', maintenance_on=maintenance_on)

@app.route('/api/docs')
def doc():
    return render_template('doc.html')
# ======================== USER BALANCE API ========================
@app.route('/api/v2/user/balance', methods=['POST', 'GET'])
def api_v2_user_balance():
    """
    Fetch user balance using public_key and private_key
    Requires whitelist_ip validation and positive brl_balance
    
    Request (POST):
    {
        "public_key": "user_public_key",
        "private_key": "user_private_key"
    }
    
    Request (GET):
    /api/v2/user/balance?public_key=xxx&private_key=yyy
    
    Response:
    {
        "success": true,
        "balance": 7500.25,
        "brl_balance": 7500.25,
        "inr_balance": 1500.50,
        "is_reseller": 1,
        "username": "username",
        "email": "user@email.com"
    }
    """
    try:
        # Get parameters from POST or GET
        if request.method == 'POST':
            data = request.get_json() or {}
            public_key = data.get('public_key', '').strip()
            private_key = data.get('private_key', '').strip()
        else:
            public_key = request.args.get('public_key', '').strip()
            private_key = request.args.get('private_key', '').strip()
        
        # Validate input
        if not public_key or not private_key:
            return jsonify({
                'success': False,
                'error': 'Missing public_key or private_key'
            }), 400
        
        # Query user by public_key and private_key
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    username,
                    balance,
                    brl_balance,
                    is_reseller,
                    email,
                    whitelist_ip
                FROM users
                WHERE public_key = %s AND private_key = %s
                LIMIT 1
            """, (public_key, private_key))
            user = cursor.fetchone()
        
        connection.close()
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid credentials. User not found.'
            }), 401
        
        # -------- IP WHITELIST CHECK --------
        whitelist_ip = user.get('whitelist_ip')
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        if whitelist_ip:
            allowed_ips = [ip.strip() for ip in whitelist_ip.split(',') if ip.strip()]
            if allowed_ips and client_ip not in allowed_ips:
                return jsonify({
                    'success': False,
                    'error': f'IP address {client_ip} is not whitelisted'
                }), 403
        
        # -------- BRL BALANCE CHECK --------
        brl_balance = float(user.get('brl_balance', 0)) if user.get('brl_balance') is not None else 0.0
        if brl_balance <= 0:
            return jsonify({
                'success': False,
                'error': 'No balance available. Please add funds to your account.'
            }), 402
        
        # Determine currency based on reseller status
        is_reseller = int(user.get('is_reseller', 0))
        balance = float(user.get('balance', 0)) if user.get('balance') is not None else 0.0
        
        return jsonify({
            'success': True,
            'balance': brl_balance,
            'is_reseller': is_reseller,
            'username': user.get('username'),
            'email': user.get('email')
        }), 200
        
    except Exception as e:
        print(f"[Balance API Error] {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

# ======================== RESELLER PRODUCTS API ========================
@app.route('/api/v2/products', methods=['POST', 'GET'])
def api_v2_reseller_products():
    """
    Fetch reseller products using private_key and public_key
    Only accessible to resellers (is_reseller = 1) with positive brl_balance
    
    Request (POST):
    {
        "private_key": "user_private_key",
        "public_key": "user_public_key"
    }
    
    Request (GET):
    /api/v2/products?private_key=xxx&public_key=yyy
    
    Response (Success):
    {
        "success": true,
        "username": "username",
        "email": "user@email.com",
        "product_count": 10,
        "products": [...]
    }
    """
    try:
        # Get parameters from POST or GET
        if request.method == 'POST':
            data = request.get_json() or {}
            private_key = data.get('private_key', '').strip()
            public_key = data.get('public_key', '').strip()
        else:
            private_key = request.args.get('private_key', '').strip()
            public_key = request.args.get('public_key', '').strip()
        
        # Validate input
        if not private_key or not public_key:
            return jsonify({
                'success': False,
                'error': 'Missing private_key or public_key'
            }), 400
        
        # Query user by private_key and public_key
        connection = pymysql.connect(**DB_CONFIG)
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT id, username, is_reseller, email, brl_balance, whitelist_ip
                FROM users
                WHERE private_key = %s AND public_key = %s
                LIMIT 1
            """, (private_key, public_key))
            user = cursor.fetchone()
        
        if not user:
            connection.close()
            return jsonify({
                'success': False,
                'error': 'Invalid credentials. User not found.'
            }), 401
        
        # -------- IP WHITELIST CHECK --------
        whitelist_ip = user.get('whitelist_ip')
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
        
        if whitelist_ip:
            allowed_ips = [ip.strip() for ip in whitelist_ip.split(',') if ip.strip()]
            if allowed_ips and client_ip not in allowed_ips:
                connection.close()
                return jsonify({
                    'success': False,
                    'error': f'IP address {client_ip} is not whitelisted'
                }), 403
        
        # Check if user is a reseller
        is_reseller = int(user.get('is_reseller', 0))
        if is_reseller != 1:
            connection.close()
            return jsonify({
                'success': False,
                'error': 'User is not a reseller. Access denied.'
            }), 403
        
        # -------- BRL BALANCE CHECK --------
        brl_balance = float(user.get('brl_balance', 0)) if user.get('brl_balance') is not None else 0.0
        if brl_balance <= 0:
            connection.close()
            return jsonify({
                'success': False,
                'error': 'No balance available. Please add funds to your account.'
            }), 402
        
        # Fetch all active products with reseller pricing
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    id,
                    product_name,
                    reseller_price,
                    category,
                    status
                FROM product
                WHERE status = 'active'
                ORDER BY category, product_name
            """)
            products = cursor.fetchall()
        
        connection.close()
        
        # Format products response
        formatted_products = []
        if products:
            for product in products:
                formatted_products.append({
                    'id': product.get('id'),
                    'product_name': product.get('product_name'),
                    'reseller_price': float(product.get('reseller_price', 0)) if product.get('reseller_price') else None,
                    'category': product.get('category'),
                    'status': product.get('status')
                })
        
        return jsonify({
            'success': True,
            'username': user.get('username'),
            'email': user.get('email'),
            'product_count': len(formatted_products),
            'products': formatted_products
        }), 200
        
    except Exception as e:
        print(f"[Reseller Products API Error] {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

# ======================== CREATE ORDER API V2 ========================
@app.route('/api/v2/create-order', methods=['POST', 'GET'])
def api_v2_create_order():
    """
    Create a reseller order using public_key & private_key authentication.
    
    Required Parameters:
    - public_key: User's public API key
    - private_key: User's private API key
    - userid: Player/User ID in game
    - zoneid: Zone/Server ID in game
    - product_id: Database product ID
    - payment_method: 'wallet' (currently only wallet supported)
    
    Returns: {success, order_id, status, balance_before, balance_after, ...}
    """
    try:
        # Get parameters from POST/GET
        public_key = request.values.get('public_key')
        private_key = request.values.get('private_key')
        userid = request.values.get('userid')
        zoneid = request.values.get('zoneid')
        product_id = request.values.get('product_id')
        payment_method = request.values.get('payment_method', 'wallet').lower()
        
        # Validate required parameters
        if not all([public_key, private_key, userid, product_id]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: public_key, private_key, userid, product_id'
            }), 400
        
        connection = None
        cursor = None
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor(pymysql.cursors.DictCursor)
            
            # -------- AUTHENTICATE USER --------
            cursor.execute("""
                SELECT id, username, email, balance, brl_balance, is_reseller
                FROM users
                WHERE public_key = %s AND private_key = %s
            """, (public_key, private_key))
            
            user = cursor.fetchone()
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'Invalid credentials (public_key or private_key mismatch)'
                }), 401
            
            db_user_id = user.get('id')
            is_user_reseller = bool(user.get('is_reseller', False))
            
            # -------- AUTHORIZATION CHECK --------
            if not is_user_reseller:
                return jsonify({
                    'success': False,
                    'error': 'Only resellers can use this endpoint'
                }), 403
            
            # -------- IP WHITELIST CHECK --------
            whitelist_ip = user.get('whitelist_ip')
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if client_ip and ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            if whitelist_ip:
                allowed_ips = [ip.strip() for ip in whitelist_ip.split(',') if ip.strip()]
                if allowed_ips and client_ip not in allowed_ips:
                    return jsonify({
                        'success': False,
                        'error': f'IP address {client_ip} is not whitelisted'
                    }), 403
            
            # -------- BRL BALANCE CHECK --------
            current_balance = float(user.get('brl_balance') or 0)
            if current_balance <= 0:
                return jsonify({
                    'success': False,
                    'error': 'No balance available. Please add funds to your account.'
                }), 402
            
            # -------- FETCH PRODUCT --------
            cursor.execute("""
                SELECT p.id, p.product_name, p.price, p.reseller_price, p.product_id, 
                       p.api_provider, p.region, c.category_name, c.category_type
                FROM product p
                JOIN category c ON p.category = c.category_name
                WHERE p.id = %s AND p.status = 'active'
            """, (product_id,))
            
            product = cursor.fetchone()
            if not product:
                return jsonify({
                    'success': False,
                    'error': 'Product not found or inactive'
                }), 404
            
            # -------- DETERMINE PRICE --------
            # Use reseller_price if available, otherwise use regular price
            if product.get('reseller_price'):
                price = float(product['reseller_price'])
            else:
                price = float(product['price'])
            
            # -------- CHECK BALANCE --------
            balance_before = float(user.get('brl_balance') or 0)
            
            if balance_before < price:
                return jsonify({
                    'success': False,
                    'error': 'Insufficient balance',
                    'balance': balance_before,
                    'required': price
                }), 400
            
            # -------- START TRANSACTION --------
            connection.begin()
            
            # CREATE ORDER (pending)
            cursor.execute("""
                INSERT INTO orders
                (user_id, userid, zoneid, product_name, price, payment_method_id, status, create_date)
                VALUES (%s, %s, %s, %s, %s, 3, 'pending', NOW())
            """, (db_user_id, userid, zoneid, product['product_name'], price))
            
            order_id = cursor.lastrowid
            
            # -------- HANDLE API PROVIDERS --------
            if product['api_provider'].lower() == 'smile':
                # Handle multiple Smile.one product IDs
                product_ids = [p.strip() for p in product['product_id'].split('&') if p.strip()]
                
                # Fetch API credentials from database
                creds = get_api_credentials('smile')
                if not creds:
                    creds = {'uid': '913332', 'email': 'renedysanasam13@gmail.com', 'api_key': '3984a50cd116b3c06a05c784e16d0fb0'}
                
                smile_orders = []
                failed = []
                
                for idx, pid in enumerate(product_ids, 1):
                    print(f"[DEBUG] Calling Smile.one API for product {idx}: {pid}")
                    
                    result = create_smile_order(
                        userid=userid,
                        zoneid=zoneid,
                        product='mobilelegends',
                        productid=pid,
                        region=product.get('region'),
                        uid=creds.get('uid'),
                        email=creds.get('email'),
                        key=creds.get('api_key')
                    )
                    
                    print(f"[DEBUG] Smile.one response: {result}")
                    smile_orders.append({
                        'index': idx,
                        'product_id': pid,
                        'response': result
                    })
                    
                    if not result.get('success'):
                        failed.append({
                            'product_id': pid,
                            'error': result.get('message')
                        })
                
                # If ANY Smile.one order failed
                if failed:
                    cursor.execute("UPDATE orders SET status='failed' WHERE id=%s", (order_id,))
                    connection.commit()
                    
                    return jsonify({
                        'success': False,
                        'order_id': order_id,
                        'status': 'failed',
                        'smile_orders': smile_orders,
                        'failed_orders': failed
                    }), 400
                
                # -------- ALL SMILE ORDERS SUCCESS --------
                # Deduct balance from brl_balance
                cursor.execute(
                    "UPDATE users SET brl_balance = brl_balance - %s WHERE id = %s",
                    (price, db_user_id)
                )
                
                # Fetch updated balance
                cursor.execute("SELECT brl_balance FROM users WHERE id = %s", (db_user_id,))
                balance_after = float(cursor.fetchone()['brl_balance'])
                
                # Wallet history
                cursor.execute("""
                    INSERT INTO wallet_history
                    (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                    VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
                """, (db_user_id, balance_before, price, balance_after,
                      f"Order purchase #{order_id} - {product['product_name']}"))
                
                # Transactions log
                cursor.execute("""
                    INSERT INTO transactions
                    (user_id, txn_type, amount, description, created_at)
                    VALUES (%s, 'debit', %s, %s, NOW())
                """, (db_user_id, price, f"Order purchase #{order_id} - {product['product_name']}"))
                
                # Update order to success
                cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))
                connection.commit()
                
                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'status': 'success',
                    'balance_before': balance_before,
                    'balance_after': balance_after,
                    'price': price,
                    'product_name': product['product_name'],
                    'smile_orders': smile_orders
                }), 200
            
            elif product['api_provider'].lower() == 'bushan':
                # Handle multiple Bushan product IDs
                product_ids = [p.strip() for p in product['product_id'].split('&') if p.strip()]
                
                if not userid or not zoneid:
                    connection.rollback()
                    return jsonify({
                        'success': False,
                        'error': 'Invalid userid or zoneid for Bushan'
                    }), 400
                
                # Fetch API credentials from database
                creds = get_api_credentials('bushan')
                if not creds:
                    creds = {'api_key': 'busan_b372f70f97df1fc40028bd2c32cdbf4eb2522c183004c6a41acf83e8587e9189'}
                
                bushan_orders = []
                failed = []
                
                for idx, pid in enumerate(product_ids, 1):
                    print(f"[DEBUG] Calling Bushan API for product {idx}: {pid}")
                    
                    result = create_bushan_order(
                        playerId=userid,
                        zoneId=zoneid,
                        productId=pid,
                        api_key=creds.get('api_key')
                    )
                    
                    print(f"[DEBUG] Bushan response: {result}")
                    bushan_orders.append({
                        'index': idx,
                        'product_id': pid,
                        'response': result
                    })
                    
                    if not result.get('success'):
                        failed.append({
                            'product_id': pid,
                            'error': result.get('message')
                        })
                
                # If ANY Bushan order failed - refund
                if failed:
                    cursor.execute("UPDATE orders SET status='failed' WHERE id=%s", (order_id,))
                    connection.commit()
                    
                    return jsonify({
                        'success': False,
                        'order_id': order_id,
                        'status': 'failed',
                        'bushan_orders': bushan_orders,
                        'failed_orders': failed
                    }), 400
                
                # -------- ALL BUSHAN ORDERS SUCCESS --------
                # Deduct balance from brl_balance
                cursor.execute(
                    "UPDATE users SET brl_balance = brl_balance - %s WHERE id = %s",
                    (price, db_user_id)
                )
                
                # Fetch updated balance
                cursor.execute("SELECT brl_balance FROM users WHERE id = %s", (db_user_id,))
                balance_after = float(cursor.fetchone()['brl_balance'])
                
                # Wallet history
                cursor.execute("""
                    INSERT INTO wallet_history
                    (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                    VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
                """, (db_user_id, balance_before, price, balance_after,
                      f"Order purchase #{order_id} - {product['product_name']}"))
                
                # Transactions log
                cursor.execute("""
                    INSERT INTO transactions
                    (user_id, txn_type, amount, description, created_at)
                    VALUES (%s, 'debit', %s, %s, NOW())
                """, (db_user_id, price, f"Order purchase #{order_id} - {product['product_name']}"))
                
                # Update order to success
                cursor.execute("UPDATE orders SET status='success' WHERE id=%s", (order_id,))
                connection.commit()
                
                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'status': 'success',
                    'balance_before': balance_before,
                    'balance_after': balance_after,
                    'price': price,
                    'product_name': product['product_name'],
                    'bushan_orders': bushan_orders
                }), 200
            
            else:
                # Manual order (no automatic processing)
                cursor.execute(
                    "UPDATE users SET brl_balance = brl_balance - %s WHERE id = %s",
                    (price, db_user_id)
                )
                
                # Fetch updated balance
                cursor.execute("SELECT brl_balance FROM users WHERE id = %s", (db_user_id,))
                balance_after = float(cursor.fetchone()['brl_balance'])
                
                # Wallet history
                cursor.execute("""
                    INSERT INTO wallet_history
                    (user_id, amount_before, amount, current_amount, transaction_type, reason, created_at)
                    VALUES (%s, %s, %s, %s, 'debit', %s, NOW())
                """, (db_user_id, balance_before, price, balance_after,
                      f"Order purchase #{order_id} - {product['product_name']}"))
                
                # Transactions log
                cursor.execute("""
                    INSERT INTO transactions
                    (user_id, txn_type, amount, description, created_at)
                    VALUES (%s, 'debit', %s, %s, NOW())
                """, (db_user_id, price, f"Order purchase #{order_id} - {product['product_name']}"))
                
                connection.commit()
                
                # Send Telegram notification for manual order
                message = f"New Manual Order (API v2) From {product.get('category_name', 'Unknown')}\nOrder ID: {order_id}\nProduct: {product['product_name']}\nUser ID: {db_user_id}\nPlayer ID: {userid}\nZone ID: {zoneid}\nAmount: {price} BRL"
                send_telegram_notification(message)
                
                return jsonify({
                    'success': True,
                    'order_id': order_id,
                    'status': 'pending',
                    'balance_before': balance_before,
                    'balance_after': balance_after,
                    'price': price,
                    'product_name': product['product_name'],
                    'message': 'Manual order created - awaiting processing'
                }), 200
        
        except Exception as e:
            if connection:
                connection.rollback()
            print(f"[ERROR] API v2 create-order error: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Order creation failed: {str(e)}'
            }), 500
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    except Exception as e:
        print(f"[ERROR] API v2 create-order outer error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ======================== ORDER STATUS API V2 ========================
@app.route('/api/v2/orders', methods=['POST', 'GET'])
def api_v2_orders():
    """
    Fetch order status using public_key & private_key authentication.
    
    Required Parameters:
    - public_key: User's public API key
    - private_key: User's private API key
    
    Optional Parameters:
    - order_id: Fetch specific order (if not provided, returns all user orders)
    - status: Filter by status (pending, processing, success, failed, refunded)
    - limit: Number of orders to return (default: 50, max: 500)
    - offset: Pagination offset (default: 0)
    
    Returns: {success, orders: [{id, userid, product_name, price, status, create_date}, ...]}
    """
    try:
        # Get parameters from POST/GET
        public_key = request.values.get('public_key')
        private_key = request.values.get('private_key')
        order_id = request.values.get('order_id')
        status_filter = request.values.get('status')
        
        # Pagination parameters
        try:
            limit = int(request.values.get('limit', 50))
            offset = int(request.values.get('offset', 0))
            # Enforce reasonable limits
            limit = min(max(limit, 1), 500)
            offset = max(offset, 0)
        except ValueError:
            limit = 50
            offset = 0
        
        # Validate required parameters
        if not all([public_key, private_key]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: public_key, private_key'
            }), 400
        
        connection = None
        cursor = None
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor(pymysql.cursors.DictCursor)
            
            # -------- AUTHENTICATE USER --------
            cursor.execute("""
                SELECT id, username, email, is_reseller
                FROM users
                WHERE public_key = %s AND private_key = %s
            """, (public_key, private_key))
            
            user = cursor.fetchone()
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'Invalid credentials (public_key or private_key mismatch)'
                }), 401
            
            db_user_id = user.get('id')
            
            # -------- IP WHITELIST CHECK --------
            whitelist_ip = user.get('whitelist_ip')
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if client_ip and ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            if whitelist_ip:
                allowed_ips = [ip.strip() for ip in whitelist_ip.split(',') if ip.strip()]
                if allowed_ips and client_ip not in allowed_ips:
                    connection.close()
                    return jsonify({
                        'success': False,
                        'error': f'IP address {client_ip} is not whitelisted'
                    }), 403
            
            # -------- BRL BALANCE CHECK --------
            cursor.execute("SELECT brl_balance FROM users WHERE id = %s", (db_user_id,))
            user_balance_row = cursor.fetchone()
            brl_balance = float(user_balance_row.get('brl_balance', 0)) if user_balance_row else 0.0
            if brl_balance <= 0:
                connection.close()
                return jsonify({
                    'success': False,
                    'error': 'No balance available. Please add funds to your account.'
                }), 402
            
            # -------- FETCH ORDERS --------
            if order_id:
                # Fetch specific order
                cursor.execute("""
                    SELECT id, user_id, userid, zoneid, product_name, price, 
                           payment_method_id, status, create_date
                    FROM orders
                    WHERE id = %s AND user_id = %s
                """, (order_id, db_user_id))
                
                order = cursor.fetchone()
                if not order:
                    return jsonify({
                        'success': False,
                        'error': 'Order not found'
                    }), 404
                
                orders = [order]
                total_count = 1
            else:
                # Fetch all user orders with optional status filter
                if status_filter:
                    # Validate status
                    valid_statuses = ['pending', 'processing', 'success', 'failed', 'refunded']
                    if status_filter.lower() not in valid_statuses:
                        return jsonify({
                            'success': False,
                            'error': f'Invalid status. Allowed: {", ".join(valid_statuses)}'
                        }), 400
                    
                    cursor.execute("""
                        SELECT id, user_id, userid, zoneid, product_name, price, 
                               payment_method_id, status, create_date
                        FROM orders
                        WHERE user_id = %s AND status = %s
                        ORDER BY create_date DESC
                        LIMIT %s OFFSET %s
                    """, (db_user_id, status_filter.lower(), limit, offset))
                else:
                    # Fetch all orders without status filter
                    cursor.execute("""
                        SELECT id, user_id, userid, zoneid, product_name, price, 
                               payment_method_id, status, create_date
                        FROM orders
                        WHERE user_id = %s
                        ORDER BY create_date DESC
                        LIMIT %s OFFSET %s
                    """, (db_user_id, limit, offset))
                
                orders = cursor.fetchall()
                
                # Get total count for pagination
                if status_filter:
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM orders
                        WHERE user_id = %s AND status = %s
                    """, (db_user_id, status_filter.lower()))
                else:
                    cursor.execute("""
                        SELECT COUNT(*) as count
                        FROM orders
                        WHERE user_id = %s
                    """, (db_user_id,))
                
                total_count = cursor.fetchone().get('count', 0)
            
            connection.close()
            
            # -------- FORMAT RESPONSE --------
            formatted_orders = []
            if orders:
                for order in orders:
                    formatted_orders.append({
                        'id': order.get('id'),
                        'userid': order.get('userid'),
                        'zoneid': order.get('zoneid'),
                        'product_name': order.get('product_name'),
                        'price': float(order.get('price', 0)),
                        'payment_method_id': order.get('payment_method_id'),
                        'status': order.get('status'),
                        'create_date': order.get('create_date').isoformat() if order.get('create_date') else None
                    })
            
            # Calculate pagination info
            total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
            current_page = (offset // limit) + 1 if limit > 0 else 1
            
            return jsonify({
                'success': True,
                'username': user.get('username'),
                'email': user.get('email'),
                'order_count': len(formatted_orders),
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'current_page': current_page,
                'total_pages': total_pages,
                'orders': formatted_orders
            }), 200
        
        except Exception as e:
            if connection:
                connection.close()
            print(f"[ERROR] API v2 orders error: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch orders: {str(e)}'
            }), 500
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    except Exception as e:
        print(f"[ERROR] API v2 orders outer error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ======================== VALIDATE PLAYER API V2 ========================
@app.route('/api/v2/validate', methods=['POST', 'GET'])
def api_v2_validate():
    """
    Validate player/user ID and fetch username & country.
    Uses public_key & private_key authentication with IP whitelist check.
    
    Required Parameters:
    - public_key: User's public API key
    - private_key: User's private API key
    - userid: Player/User ID in game
    - zoneid: Zone/Server ID in game
    
    Optional Parameters:
    - product: Product name (for Smile.one validation)
    - productid: Product ID (for Smile.one validation)
    
    Returns: {success, username, country, userid, zoneid}
    """
    try:
        # Get parameters from POST/GET
        public_key = request.values.get('public_key')
        private_key = request.values.get('private_key')
        userid = request.values.get('userid')
        zoneid = request.values.get('zoneid')
        product = request.values.get('product')
        productid = request.values.get('productid')
        
        # Validate required parameters
        if not all([public_key, private_key, userid]):
            return jsonify({
                'success': False,
                'error': 'Missing required parameters: public_key, private_key, userid'
            }), 400
        
        # Use userid as zoneid fallback if not provided
        if not zoneid:
            zoneid = userid
        
        connection = None
        cursor = None
        
        try:
            connection = get_db_connection()
            cursor = connection.cursor(pymysql.cursors.DictCursor)
            
            # -------- AUTHENTICATE USER --------
            cursor.execute("""
                SELECT id, username, email, whitelist_ip
                FROM users
                WHERE public_key = %s AND private_key = %s
            """, (public_key, private_key))
            
            user = cursor.fetchone()
            if not user:
                return jsonify({
                    'success': False,
                    'error': 'Invalid credentials (public_key or private_key mismatch)'
                }), 401
            
            # -------- IP WHITELIST CHECK --------
            whitelist_ip = user.get('whitelist_ip')
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            # Extract first IP if X-Forwarded-For contains multiple IPs
            if client_ip and ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            if whitelist_ip:
                # Parse whitelist_ip (can be single IP or comma-separated IPs)
                allowed_ips = [ip.strip() for ip in whitelist_ip.split(',') if ip.strip()]
                if allowed_ips and client_ip not in allowed_ips:
                    connection.close()
                    return jsonify({
                        'success': False,
                        'error': f'IP address {client_ip} is not whitelisted'
                    }), 403
            
            # -------- BRL BALANCE CHECK --------
            brl_balance = float(user.get('brl_balance', 0)) if user.get('brl_balance') is not None else 0.0
            if brl_balance <= 0:
                connection.close()
                return jsonify({
                    'success': False,
                    'error': 'No balance available. Please add funds to your account.'
                }), 402
            
            connection.close()
            
            # -------- FETCH USERNAME AND COUNTRY FROM SMILE.ONE --------
            req_meta = _get_request_meta()
            
            try:
                # Try Smile.one API first
                resp = get_smile_role(
                    userid=userid,
                    zoneid=zoneid,
                    product=product or 'mobilelegends',
                    productid=productid or '13'
                )
                
                # Check if Smile.one response is successful
                if isinstance(resp, dict) and resp.get('status') == 200:
                    username = resp.get('username') or extract_username_from_response(resp) or (resp.get('data') or {}).get('nickname')
                    country = resp.get('country') or (resp.get('data') or {}).get('country') or 'Unknown'
                    
                    try:
                        log_search_if_configured(
                            player_id=userid,
                            server_id=zoneid,
                            nickname=username,
                            country_code=None,
                            country_name=country,
                            parsed_obj=None,
                            raw_response=resp,
                            request_meta=req_meta
                        )
                    except Exception:
                        pass
                    
                    return jsonify({
                        'success': True,
                        'username': username or '-',
                        'country': country or 'Unknown',
                        'userid': userid,
                        'zoneid': zoneid,
                        'source': 'smile.one'
                    }), 200
                else:
                    # Smile.one failed, try fallback (moogold)
                    raise Exception("Smile.one validation failed")
            
            except Exception as smile_error:
                print(f"[DEBUG] Smile.one validation failed: {str(smile_error)}, trying moogold fallback")
                
                # -------- FALLBACK: FETCH USERNAME AND COUNTRY FROM MOOGOLD --------
                try:
                    url = "https://moogold.com/wp-content/plugins/id-validation-new/id-validation-ajax.php"
                    payload = {
                        "attribute_amount": "Weekly Pass",
                        "text-5f6f144f8ffee": userid,
                        "text-1601115253775": zoneid,
                        "quantity": 1,
                        "add-to-cart": 15145,
                        "product_id": 15145,
                        "variation_id": 4690783
                    }
                    headers = {
                        'Referer': 'https://moogold.com/product/mobile-legends/',
                        'Origin': 'https://moogold.com'
                    }
                    
                    r = requests.post(url, data=payload, headers=headers, timeout=10)
                    r.raise_for_status()
                    
                    data = None
                    try:
                        data = r.json()
                    except Exception:
                        data = {"raw": r.text}
                    
                    message = data.get('message') if isinstance(data, dict) else None
                    if not message:
                        try:
                            log_search_if_configured(
                                player_id=userid,
                                server_id=zoneid,
                                nickname=None,
                                country_code=None,
                                country_name=None,
                                parsed_obj=None,
                                raw_response=data,
                                request_meta=req_meta
                            )
                        except Exception:
                            pass
                        
                        return jsonify({
                            'success': False,
                            'error': 'Invalid ID Player or Server ID'
                        }), 400
                    
                    # Parse the moogold message
                    parsed = parse_object(message)
                    country_code = parsed.get('country')
                    country_name = None
                    
                    # Optional country list lookup
                    try:
                        base = os.path.dirname(os.path.abspath(__file__))
                        data_path = os.path.join(base, 'utils', 'data.json')
                        with open(data_path, 'r', encoding='utf-8') as f:
                            countries = json.load(f)
                            for c in countries:
                                if c.get('countryShortCode') == country_code:
                                    country_name = c.get('countryName')
                                    break
                    except Exception:
                        country_name = None
                    
                    username = parsed.get('in-game-nickname') or '-'
                    country = country_name or parsed.get('country') or 'Unknown'
                    
                    try:
                        log_search_if_configured(
                            player_id=userid,
                            server_id=zoneid,
                            nickname=username,
                            country_code=country_code,
                            country_name=country_name,
                            parsed_obj=parsed,
                            raw_response=data,
                            request_meta=req_meta
                        )
                    except Exception:
                        pass
                    
                    return jsonify({
                        'success': True,
                        'username': username,
                        'country': country,
                        'userid': userid,
                        'zoneid': zoneid,
                        'source': 'moogold'
                    }), 200
                
                except requests.exceptions.RequestException as re:
                    try:
                        log_search_if_configured(
                            player_id=userid,
                            server_id=zoneid,
                            nickname=None,
                            country_code=None,
                            country_name=None,
                            parsed_obj=None,
                            raw_response={"error": str(re)},
                            request_meta=req_meta
                        )
                    except Exception:
                        pass
                    
                    return jsonify({
                        'success': False,
                        'error': f'Validation service error: {str(re)}'
                    }), 500
                
                except Exception as e:
                    try:
                        log_search_if_configured(
                            player_id=userid,
                            server_id=zoneid,
                            nickname=None,
                            country_code=None,
                            country_name=None,
                            parsed_obj=None,
                            raw_response={"error": str(e)},
                            request_meta=req_meta
                        )
                    except Exception:
                        pass
                    
                    return jsonify({
                        'success': False,
                        'error': f'Validation failed: {str(e)}'
                    }), 500
        
        except Exception as e:
            if connection:
                connection.close()
            print(f"[ERROR] API v2 validate error: {str(e)}")
            return jsonify({
                'success': False,
                'error': f'Validation error: {str(e)}'
            }), 500
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    
    except Exception as e:
        print(f"[ERROR] API v2 validate outer error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========================== XTREME OFFICIAL API ==========================

@app.route('/xtreme/products', methods=['GET'])
def xtreme_products_page():
    """
    Serve the HTML page to display Xtreme Official products.
    """
    try:
        return render_template('xtreme_products.html')
    except Exception as e:
        print(f"[ERROR] Xtreme products page error: {str(e)}")
        return f"Error loading page: {str(e)}", 500

@app.route('/api/xtreme/products-list', methods=['GET'])
def xtreme_products_api():
    """
    Proxy endpoint to fetch products from Xtreme Official API.
    This handles CORS issues by making the request server-side.
    
    Query Parameters:
        public_key: Xtreme Official public API key
        private_key: Xtreme Official private API key
    """
    try:
        # Xtreme Official API credentials
        XTREME_PUBLIC_KEY = request.args.get('public_key', 'W6STC3K')
        XTREME_PRIVATE_KEY = request.args.get('private_key', 'ZNT91RQ5IYKW')
        XTREME_API_URL = 'https://xtremeofficial.in/api/products-list'
        
        # Build the API URL
        api_url = f"{XTREME_API_URL}?public_key={XTREME_PUBLIC_KEY}&private_key={XTREME_PRIVATE_KEY}"
        
        print(f"[Xtreme API] Fetching from: {XTREME_API_URL}")
        
        # Make the request to Xtreme Official API
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Log success
        if data.get('success'):
            print(f"[Xtreme API] Successfully fetched {len(data.get('products', []))} products")
        
        return jsonify(data), 200
        
    except requests.exceptions.Timeout:
        print("[Xtreme API] Request timeout")
        return jsonify({
            'success': False,
            'error': 'Request timeout - Xtreme API server is slow',
            'status_code': 504
        }), 504
        
    except requests.exceptions.ConnectionError:
        print("[Xtreme API] Connection error")
        return jsonify({
            'success': False,
            'error': 'Connection error - Unable to reach Xtreme Official API',
            'status_code': 503
        }), 503
        
    except requests.exceptions.HTTPError as e:
        print(f"[Xtreme API] HTTP error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Xtreme API returned error: {str(e)}',
            'status_code': e.response.status_code
        }), e.response.status_code
        
    except Exception as e:
        print(f"[Xtreme API] Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Error fetching products: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/xtreme/test', methods=['GET'])
def xtreme_test():
    """
    Test endpoint to verify Xtreme Official API connectivity.
    """
    try:
        XTREME_API_URL = 'https://xtremeofficial.in/api/products-list'
        XTREME_PUBLIC_KEY = 'W6STC3K'
        XTREME_PRIVATE_KEY = 'ZNT91RQ5IYKW'
        
        api_url = f"{XTREME_API_URL}?public_key={XTREME_PUBLIC_KEY}&private_key={XTREME_PRIVATE_KEY}"
        
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        return jsonify({
            'success': True,
            'message': 'Xtreme Official API is accessible',
            'api_url': XTREME_API_URL,
            'response_data': data
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to test Xtreme Official API'
        }), 500

if __name__ == '__main__':
	app.run(debug=True, port=5002)

