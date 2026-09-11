import os
import sqlite3
import secrets
import html
import re
import unicodedata
import time
import base64
import hmac
import hashlib
import struct
import json
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'blocktree-cyber-editorial-secret-2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
DB_PATH = 'grid_data.db'

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================================================
# MILITARY-GRADE DEFENSE-IN-DEPTH SECURITY SUITE
# Zero-Tolerance SQLi Shield, Timing Defense, Persistent Lockouts & 2FA/TOTP
# ==========================================================================
ADMIN_USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{3,32}$')
SQLI_SUSPICIOUS_REGEX = re.compile(r"(\b(SELECT|UNION|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|BENCHMARK|PG_SLEEP)\b|--|/\*|\*/|;\s*$|'|\"|`|\bOR\b\s+[\d'\"=]|\bAND\b\s+[\d'\"=])", re.IGNORECASE)
DUMMY_PASSWORD_HASH = generate_password_hash("BlocktreeTimingMitigationConstantTime2026!", method='pbkdf2:sha256:600000')

def is_sqli_payload(val):
    if not val:
        return False
    return bool(SQLI_SUSPICIOUS_REGEX.search(str(val)))

def get_client_ip(req):
    fwd = req.headers.get('X-Forwarded-For')
    if fwd:
        return fwd.split(',')[0].strip()
    return req.remote_addr or '127.0.0.1'

def compute_device_fingerprint(ip, user_agent):
    data = f"{ip}:{user_agent}:{app.secret_key}".encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def log_admin_audit(event_type, status, admin_user=None, target_id=None, details=None):
    try:
        ip = get_client_ip(request)
        ua = request.headers.get('User-Agent', '')[:250]
        conn = get_db()
        c = conn.cursor()
        c.execute('''
            INSERT INTO admin_audit_logs 
            (admin_user, event_type, target_id, ip_address, user_agent, status, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ''', (admin_user, event_type, target_id, ip, ua, status, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit log writing error: {e}")

def check_persistent_rate_limit(identifier):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT failed_count, locked_until FROM admin_lockouts WHERE identifier = ?", (identifier,))
    row = c.fetchone()
    conn.close()
    if not row or not row['locked_until']:
        return True, None
    try:
        locked_until = datetime.strptime(row['locked_until'], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True, None
    now = datetime.now()
    if locked_until > now:
        rem = int((locked_until - now).total_seconds())
        mins = max(1, rem // 60)
        return False, f"Security Lockdown Active: Account / IP quarantined for {mins} more minute(s) due to multiple failed authentication attempts."
    return True, None

def record_persistent_failed_attempt(identifier):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now()
    c.execute("SELECT id, failed_count FROM admin_lockouts WHERE identifier = ?", (identifier,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO admin_lockouts (identifier, failed_count, first_failed_at, last_failed_at) VALUES (?, 1, datetime('now'), datetime('now'))", (identifier,))
        conn.commit()
        conn.close()
        return 4
    else:
        new_count = row['failed_count'] + 1
        locked_until = None
        if new_count >= 10:
            locked_until = (now + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        elif new_count >= 5:
            locked_until = (now + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute('''
            UPDATE admin_lockouts 
            SET failed_count = ?, last_failed_at = datetime('now'), locked_until = ?
            WHERE id = ?
        ''', (new_count, locked_until, row['id']))
        conn.commit()
        conn.close()
        return max(0, 5 - new_count)

def clear_persistent_lockout(identifier):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM admin_lockouts WHERE identifier = ?", (identifier,))
    conn.commit()
    conn.close()

# RFC 6238 TOTP Engine & Backup Codes
def generate_totp_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode('utf-8').replace('=', '')

def get_totp_uri(username, secret):
    return f"otpauth://totp/Blocktree:{username}?secret={secret}&issuer=Blocktree"

def verify_totp(secret_b32, code_str, window=1):
    try:
        secret = base64.b32decode(secret_b32.upper() + '=' * ((8 - len(secret_b32) % 8) % 8))
        current_counter = int(time.time() // 30)
        code_int = int(code_str.strip())
        for offset in range(-window, window + 1):
            counter = current_counter + offset
            h = hmac.new(secret, struct.pack('>Q', counter), hashlib.sha1).digest()
            o = h[-1] & 0x0F
            expected = (struct.unpack('>I', h[o:o+4])[0] & 0x7FFFFFFF) % 1000000
            if expected == code_int:
                return True
        return False
    except Exception:
        return False

def generate_backup_codes(n=5):
    plain = [secrets.token_hex(4).upper() for _ in range(n)]
    hashed = [hashlib.sha256(c.encode()).hexdigest() for c in plain]
    return plain, hashed

def verify_and_consume_backup_code(conn, admin_id, input_code):
    input_hash = hashlib.sha256(input_code.strip().upper().encode()).hexdigest()
    c = conn.cursor()
    c.execute("SELECT backup_codes FROM admins WHERE id = ?", (admin_id,))
    row = c.fetchone()
    if not row or not row['backup_codes']:
        return False
    try:
        codes = json.loads(row['backup_codes'])
        if input_hash in codes:
            codes.remove(input_hash)
            c.execute("UPDATE admins SET backup_codes = ? WHERE id = ?", (json.dumps(codes), admin_id))
            conn.commit()
            return True
    except Exception:
        return False
    return False

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = session.get('admin_id')
        if not admin_id:
            return jsonify({"error": "Admin access required. Please authenticate."}), 401
            
        ip = get_client_ip(request)
        ua = request.headers.get('User-Agent', '')[:250]
        
        # 1. Device Fingerprint Anti-Hijack Check
        expected_fp = compute_device_fingerprint(ip, ua)
        stored_fp = session.get('admin_fingerprint')
        if stored_fp and stored_fp != expected_fp:
            log_admin_audit("SESSION_HIJACK_DETECTED", "BLOCKED", session.get('admin_username'), details=f"Fingerprint mismatch from IP {ip}")
            session.clear()
            return jsonify({"error": "Security Alert: Session invalidated due to device or network mismatch."}), 401

        # 2. Idle Session Timeout (30 mins)
        last_act = session.get('admin_last_activity', 0)
        now_ts = int(time.time())
        if now_ts - last_act > 1800:
            session.clear()
            return jsonify({"error": "Admin session expired due to inactivity. Please log in again."}), 401
        session['admin_last_activity'] = now_ts

        # 3. Anti-CSRF Token Verification on Mutating HTTP Verbs
        if request.method in ('POST', 'DELETE', 'PUT', 'PATCH'):
            csrf_hdr = request.headers.get('X-CSRF-Token')
            if not csrf_hdr or csrf_hdr != session.get('admin_csrf'):
                log_admin_audit("CSRF_VIOLATION", "BLOCKED", session.get('admin_username'), details=f"Invalid CSRF token on {request.path}")
                return jsonify({"error": "Security Alert: CSRF token verification failed."}), 403

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, username, role, totp_enabled FROM admins WHERE id = ?", (admin_id,))
        admin = c.fetchone()
        conn.close()
        if not admin:
            session.clear()
            return jsonify({"error": "Invalid or revoked admin session."}), 401
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # 1. Authors table
    c.execute('''CREATE TABLE IF NOT EXISTS authors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        pen_name TEXT NOT NULL,
        email TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        bio TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        badge TEXT DEFAULT 'Verified Author',
        is_verified INTEGER DEFAULT 1,
        reputation_score INTEGER DEFAULT 100,
        is_banned INTEGER DEFAULT 0,
        ban_reason TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute("PRAGMA table_info(authors)")
    author_cols = [row[1] for row in c.fetchall()]
    if 'is_banned' not in author_cols:
        c.execute("ALTER TABLE authors ADD COLUMN is_banned INTEGER DEFAULT 0")
    if 'ban_reason' not in author_cols:
        c.execute("ALTER TABLE authors ADD COLUMN ban_reason TEXT")
    
    # 2. Admins table with 2FA & Backup Codes
    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'superadmin',
        totp_secret TEXT,
        totp_enabled INTEGER DEFAULT 0,
        backup_codes TEXT,
        failed_attempts INTEGER DEFAULT 0,
        locked_until DATETIME,
        last_login DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # Add missing 2FA columns non-destructively
    c.execute("PRAGMA table_info(admins)")
    admin_cols = [row[1] for row in c.fetchall()]
    if 'totp_secret' not in admin_cols:
        c.execute("ALTER TABLE admins ADD COLUMN totp_secret TEXT")
    if 'totp_enabled' not in admin_cols:
        c.execute("ALTER TABLE admins ADD COLUMN totp_enabled INTEGER DEFAULT 0")
    if 'backup_codes' not in admin_cols:
        c.execute("ALTER TABLE admins ADD COLUMN backup_codes TEXT")

    # Seed default superadmin if not exists
    c.execute("SELECT id FROM admins WHERE username = 'admin'")
    if not c.fetchone():
        default_pw_hash = generate_password_hash("Admin@Blocktree2026!", method='pbkdf2:sha256:600000')
        c.execute('''INSERT INTO admins (username, password_hash, role) VALUES (?, ?, ?)''',
                  ('admin', default_pw_hash, 'superadmin'))
        print("Initialized default superadmin account ('admin').")

    # 3. Persistent Lockouts Table (Survives Server Restarts)
    c.execute('''CREATE TABLE IF NOT EXISTS admin_lockouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        identifier TEXT UNIQUE NOT NULL,
        failed_count INTEGER DEFAULT 1,
        first_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        locked_until DATETIME
    )''')

    # Author/User Persistent Lockouts Table
    c.execute('''CREATE TABLE IF NOT EXISTS author_lockouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        identifier TEXT UNIQUE NOT NULL,
        failed_count INTEGER DEFAULT 1,
        first_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_failed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        locked_until DATETIME
    )''')

    # 4. Immutable Security Audit Log Table
    c.execute('''CREATE TABLE IF NOT EXISTS admin_audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_user TEXT,
        event_type TEXT NOT NULL,
        target_id INTEGER,
        ip_address TEXT NOT NULL,
        user_agent TEXT,
        status TEXT NOT NULL,
        details TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 5. Nodes table
    c.execute('''CREATE TABLE IF NOT EXISTS nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        title TEXT,
        text TEXT,
        content TEXT,
        category TEXT DEFAULT 'Newsletter',
        read_time TEXT DEFAULT '2 min',
        claps INTEGER DEFAULT 0,
        image TEXT,
        cover_image TEXT,
        parent_id INTEGER,
        sponsor_id INTEGER,
        ip TEXT,
        x INTEGER,
        y INTEGER,
        ref_code TEXT UNIQUE,
        is_spillover INTEGER DEFAULT 0,
        author_id INTEGER,
        series_title TEXT,
        series_part INTEGER,
        is_verified_author INTEGER DEFAULT 0,
        is_revoked INTEGER DEFAULT 0,
        revoked_reason TEXT,
        revoked_at DATETIME,
        revoked_by TEXT,
        created_at DATETIME
    )''')
    
    c.execute("PRAGMA table_info(nodes)")
    columns = [row[1] for row in c.fetchall()]
    
    missing_cols = [
        ('title', 'TEXT'),
        ('content', 'TEXT'),
        ('category', "TEXT DEFAULT 'Newsletter'"),
        ('read_time', "TEXT DEFAULT '2 min'"),
        ('claps', 'INTEGER DEFAULT 0'),
        ('cover_image', 'TEXT'),
        ('is_spillover', 'INTEGER DEFAULT 0'),
        ('created_at', 'DATETIME'),
        ('sponsor_id', 'INTEGER'),
        ('ref_code', 'TEXT'),
        ('author_id', 'INTEGER'),
        ('series_title', 'TEXT'),
        ('series_part', 'INTEGER'),
        ('is_verified_author', 'INTEGER DEFAULT 0'),
        ('is_revoked', 'INTEGER DEFAULT 0'),
        ('revoked_reason', 'TEXT'),
        ('revoked_at', 'DATETIME'),
        ('revoked_by', 'TEXT')
    ]
    for col_name, col_type in missing_cols:
        if col_name not in columns:
            c.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()

init_db()

CARD_WIDTH = 270
CARD_HEIGHT = 280
MIN_DIST_X = 350  # 270px card + 80px clean visual clearance
MIN_DIST_Y = 360  # card height with photo cover + generous gap
SPACING = 360     # slot spacing between sibling replies

def calculate_node_coordinates(c, parent_id, exclude_node_id=None):
    """
    Calculates collision-free coordinates for spatial branching.
    - If parent_id is None: Placed along top row (y = 150) spaced generously.
    - If parent_id is set: Placed on child row (parent.y + 420) centered beneath parent,
      fanning outward symmetrically with full 2D collision avoidance.
    """
    if not parent_id:
        c.execute("SELECT MAX(x) FROM nodes WHERE parent_id IS NULL")
        row = c.fetchone()
        max_root_x = row[0] if row and row[0] is not None else None
        if max_root_x:
            return max_root_x + 2400, 150
        return 3000, 150

    c.execute("SELECT x, y FROM nodes WHERE id = ?", (parent_id,))
    parent_row = c.fetchone()
    if not parent_row:
        return 3000, 570
        
    px, py = parent_row[0], parent_row[1]
    ny = py + 420

    # Fetch all nodes in the database for 2D AABB collision detection
    c.execute("SELECT id, x, y, parent_id FROM nodes")
    raw_nodes = c.fetchall()
    all_nodes = [n for n in raw_nodes if exclude_node_id is None or n[0] != exclude_node_id]

    def has_collision(cx, cy):
        for n in all_nodes:
            if abs(cx - n[1]) < MIN_DIST_X and abs(cy - n[2]) < MIN_DIST_Y:
                return True
        return False

    # Check existing children of this parent
    children = [n for n in all_nodes if n[3] == parent_id]
    existing_child_xs = set(n[1] for n in children)

    # Candidate offsets: try outward from parent px symmetrically
    candidate_offsets = [0]
    for step in range(1, 50):
        candidate_offsets.append(step * SPACING)
        candidate_offsets.append(-step * SPACING)

    for offset in candidate_offsets:
        cx = px + offset
        if cx < 200:
            continue
        # If this slot is already occupied by a sibling, skip
        if any(abs(cx - ex) < MIN_DIST_X for ex in existing_child_xs):
            continue
        # Check 2D collision against all nodes
        if not has_collision(cx, ny):
            return cx, ny

    # Fallback scan
    step = 1
    while True:
        for sign in (1, -1):
            cx = px + sign * step * SPACING
            if cx >= 200 and not has_collision(cx, ny):
                return cx, ny
        step += 1

def fix_overlapping_nodes():
    """Scans and resolves any overlapping nodes in the database."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, parent_id, x, y FROM nodes ORDER BY id ASC")
    nodes = list(c.fetchall())
    
    repositioned = 0
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            n1 = nodes[i]
            n2 = nodes[j]
            dx = abs(n1['x'] - n2['x'])
            dy = abs(n1['y'] - n2['y'])
            if dx < MIN_DIST_X and dy < MIN_DIST_Y:
                # Target the later node to reposition
                target_node = n2 if n2['id'] > n1['id'] else n1
                nx, ny = calculate_node_coordinates(c, target_node['parent_id'], exclude_node_id=target_node['id'])
                c.execute("UPDATE nodes SET x = ?, y = ? WHERE id = ?", (nx, ny, target_node['id']))
                conn.commit()
                repositioned += 1
                for idx, item in enumerate(nodes):
                    if item['id'] == target_node['id']:
                        nodes[idx] = {'id': target_node['id'], 'parent_id': target_node['parent_id'], 'x': nx, 'y': ny}
    conn.close()
    if repositioned > 0:
        print(f"Repositioned {repositioned} overlapping node(s) successfully.")

fix_overlapping_nodes()

# ==========================================================================
# AUTHOR/USER RATE LIMITING & BRUTE-FORCE LOCKOUT SUITE
# ==========================================================================
def check_author_rate_limit(req, identifier):
    try:
        ip = get_client_ip(req)
        conn = get_db()
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
            SELECT failed_count, locked_until FROM author_lockouts 
            WHERE (identifier = ? OR identifier = ?) AND locked_until > ?
        ''', (identifier.lower(), ip, now))
        row = c.fetchone()
        if row:
            locked_until = datetime.strptime(row['locked_until'], '%Y-%m-%d %H:%M:%S')
            rem = int((locked_until - datetime.now()).total_seconds() / 60) + 1
            return True, max(1, rem)
        return False, 0
    except Exception:
        return False, 0

def record_failed_author_attempt(req, identifier):
    try:
        ip = get_client_ip(req)
        conn = get_db()
        c = conn.cursor()
        now = datetime.now()
        now_str = now.strftime('%Y-%m-%d %H:%M:%S')
        is_locked = False
        rem_mins = 0
        
        for key in [identifier.lower(), ip]:
            c.execute('SELECT id, failed_count FROM author_lockouts WHERE identifier = ?', (key,))
            row = c.fetchone()
            if row:
                new_count = row['failed_count'] + 1
                locked_until_str = None
                if new_count >= 5:
                    locked_until = now + timedelta(minutes=15)
                    locked_until_str = locked_until.strftime('%Y-%m-%d %H:%M:%S')
                    is_locked = True
                    rem_mins = 15
                c.execute('''
                    UPDATE author_lockouts 
                    SET failed_count = ?, last_failed_at = ?, locked_until = ?
                    WHERE id = ?
                ''', (new_count, now_str, locked_until_str, row['id']))
            else:
                c.execute('''
                    INSERT INTO author_lockouts (identifier, failed_count, first_failed_at, last_failed_at)
                    VALUES (?, 1, ?, ?)
                ''', (key, now_str, now_str))
        conn.commit()
        return is_locked, rem_mins
    except Exception:
        return False, 0

def clear_author_rate_limit(req, identifier):
    try:
        ip = get_client_ip(req)
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM author_lockouts WHERE identifier = ? OR identifier = ?', (identifier.lower(), ip))
        conn.commit()
    except Exception:
        pass

@app.route('/')
def home():
    return render_template('index.html')

# ==========================================================================
# SECRET OBSCURE ADMIN GATEWAY & SCANNER PROBE TRAP
# Keyword after slash: matrix-vault-9921
# ==========================================================================
SECRET_ADMIN_SLUG = "matrix-vault-9921"

@app.route('/' + SECRET_ADMIN_SLUG)
def secret_admin_gateway():
    """The ONLY valid obscure route to open the administrative portal."""
    return render_template('index.html', open_admin=True, secret_slug=SECRET_ADMIN_SLUG)

@app.route('/admin')
@app.route('/administrator')
@app.route('/admin-login')
@app.route('/wp-admin')
@app.route('/backend')
@app.route('/cpanel')
def decoy_scanner_trap():
    """Silently drops and logs automated scanner probes attempting to find admin paths."""
    ip = get_client_ip(request)
    log_admin_audit("SCANNER_PROBE_BLOCKED", "BLOCKED", None, details=f"Automated probe targeting forbidden URL: {request.path} from IP {ip}")
    return "Not Found", 404

# ==========================================================================
# PHOTO ATTACHMENT / UPLOAD API
# ==========================================================================
@app.route('/api/upload', methods=['POST'])
def upload_photo():
    """Uploads user's attached photo and returns the exact URL."""
    if 'file' not in request.files:
        return jsonify({"error": "No image file provided."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected."}), 400
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_name = f"photo_{secrets.token_hex(8)}_{int(datetime.now().timestamp())}.{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_name)
        file.save(filepath)
        url = f"/static/uploads/{unique_name}"
        return jsonify({"status": "success", "url": url, "filename": unique_name})
    return jsonify({"error": "Unsupported file format. Supported: PNG, JPG, JPEG, WEBP, GIF."}), 400

# ==========================================================================
# VERIFIED AUTHOR REGISTRATION & AUTHENTICATION (MILITARY-GRADE HARDENED)
# ==========================================================================
AUTHOR_USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_]{3,30}$')
AUTHOR_EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

@app.route('/api/auth/register', methods=['POST'])
def register_author():
    data = request.json or {}
    
    # 1. Anti-Bot Honeypot Trap
    hp_trap = data.get('hp_reg_token')
    if hp_trap:
        log_admin_audit("AUTHOR_BOT_TRAP", "BLOCKED", None, details="Automated bot filled author registration honeypot trap")
        return jsonify({"error": "Security alert: Automated registration rejected."}), 400

    username = (data.get('username') or '').strip().lower()
    pen_name = (data.get('pen_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    bio = (data.get('bio') or '').strip()
    avatar = (data.get('avatar') or '').strip()

    # 2. Strict Input Validation & Boundary Regex Shield
    if not username or not pen_name or not password:
        return jsonify({"error": "Username, Pen Name, and Password are required."}), 400

    if not AUTHOR_USERNAME_REGEX.match(username):
        return jsonify({"error": "Username must be 3-30 characters containing only letters, numbers, and underscores."}), 400

    if is_sqli_payload(username) or is_sqli_payload(pen_name) or (email and is_sqli_payload(email)):
        log_admin_audit("AUTHOR_SQLI_BLOCKED", "QUARANTINED", username, details="SQL injection syntax in author registration")
        return jsonify({"error": "Security Firewall Alert: Input contains forbidden SQL injection syntax or illegal characters."}), 400

    if email and not AUTHOR_EMAIL_REGEX.match(email):
        return jsonify({"error": "Invalid email address format."}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    ip = get_client_ip(request)
    ua = request.headers.get('User-Agent', '')[:250]

    if not avatar:
        avatar_bg = secrets.choice(['2563eb', '7c3aed', '059669', 'd97706', 'dc2626'])
        avatar = f"https://api.dicebear.com/7.x/bottts/svg?seed={username}&backgroundColor={avatar_bg}"

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM authors WHERE username = ?", (username,))
    if c.fetchone():
        conn.close()
        return jsonify({"error": f"Username '@{username}' is already registered. Please choose another."}), 409

    if email:
        c.execute("SELECT id FROM authors WHERE email = ?", (email,))
        if c.fetchone():
            conn.close()
            return jsonify({"error": "This email address is already registered."}), 409

    pw_hash = generate_password_hash(password, method='pbkdf2:sha256:600000')
    c.execute('''
        INSERT INTO authors (username, pen_name, email, password_hash, bio, avatar, badge, is_verified, reputation_score)
        VALUES (?, ?, ?, ?, ?, ?, 'Verified Author', 1, 150)
    ''', (username, pen_name, email or None, pw_hash, bio, avatar))
    author_id = c.lastrowid
    conn.commit()
    conn.close()

    session['author_id'] = author_id
    session['author_fingerprint'] = compute_device_fingerprint(ip, ua)
    log_admin_audit("AUTHOR_REGISTERED", "SUCCESS", username, target_id=author_id, details=f"New verified author registered from {ip}")

    return jsonify({
        "status": "success",
        "author": {
            "id": author_id,
            "username": username,
            "pen_name": pen_name,
            "email": email,
            "bio": bio,
            "avatar": avatar,
            "badge": "Verified Author",
            "is_verified": True,
            "reputation_score": 150
        }
    })

@app.route('/api/auth/login', methods=['POST'])
def login_author():
    data = request.json or {}
    
    # 1. Anti-Bot Automated Honeypot Trap
    hp_trap = data.get('hp_auth_token')
    if hp_trap:
        log_admin_audit("AUTHOR_BOT_TRAP", "BLOCKED", None, details="Automated bot filled author login honeypot trap")
        return jsonify({"error": "Security alert: Automated scan detected."}), 400

    identifier = (data.get('identifier') or '').strip().lower()
    password = (data.get('password') or '').strip()

    if not identifier or not password:
        return jsonify({"error": "Username/Email and Password are required."}), 400

    ip = get_client_ip(request)
    ua = request.headers.get('User-Agent', '')[:250]

    # 2. Persistent Brute-Force Rate Limiting (Survives Restarts)
    is_locked, rem_mins = check_author_rate_limit(request, identifier)
    if is_locked:
        log_admin_audit("AUTHOR_RATE_LIMIT_EXCEEDED", "LOCKED_OUT", identifier, details=f"Quarantined for {rem_mins} more minutes")
        return jsonify({"error": f"Security Lockdown Active: Account / IP quarantined for {rem_mins} more minute(s) due to multiple failed authentication attempts."}), 429

    # 3. SQL Injection Boundary Shield
    if is_sqli_payload(identifier):
        record_failed_author_attempt(request, identifier)
        log_admin_audit("AUTHOR_SQLI_ATTEMPT_BLOCKED", "QUARANTINED", identifier, details="SQL injection syntax in author login")
        return jsonify({"error": "Security Firewall Alert: Input contains forbidden SQL injection syntax or illegal characters."}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM authors WHERE LOWER(username) = ? OR LOWER(email) = ?", (identifier, identifier))
    author = c.fetchone()
    conn.close()

    # 4. Anti-Enumeration Timing Side-Channel Defense
    # Constant-time hashing computation guarantees non-existent users take the same ~200ms
    if not author:
        check_password_hash(DUMMY_PASSWORD_HASH, password)
        locked_now, lock_mins = record_failed_author_attempt(request, identifier)
        log_admin_audit("AUTHOR_LOGIN_FAILED", "FAILED", identifier, details=f"Non-existent author attempt from {ip}")
        if locked_now:
            return jsonify({"error": f"Security Lockdown Active: Account / IP quarantined for {lock_mins} minutes due to multiple failed attempts."}), 429
        return jsonify({"error": "Invalid username/email or password."}), 401

    if not check_password_hash(author['password_hash'], password):
        locked_now, lock_mins = record_failed_author_attempt(request, identifier)
        log_admin_audit("AUTHOR_LOGIN_FAILED", "FAILED", identifier, details=f"Invalid password for author {author['username']} from {ip}")
        if locked_now:
            return jsonify({"error": f"Security Lockdown Active: Account / IP quarantined for {lock_mins} minutes due to multiple failed attempts."}), 429
        return jsonify({"error": "Invalid username/email or password."}), 401

    if author['is_banned']:
        log_admin_audit("AUTHOR_BANNED_LOGIN_BLOCKED", "BLOCKED", author['username'], details="Banned author attempted login")
        return jsonify({"error": f"This author account is suspended. Reason: {author['ban_reason'] or 'Violation of community guidelines'}."}), 403

    # Success: Clear lockouts, bind HMAC session fingerprint
    clear_author_rate_limit(request, identifier)
    session['author_id'] = author['id']
    session['author_fingerprint'] = compute_device_fingerprint(ip, ua)
    log_admin_audit("AUTHOR_LOGIN_SUCCESS", "SUCCESS", author['username'], target_id=author['id'], details=f"Author authenticated from {ip}")

    return jsonify({
        "status": "success",
        "author": {
            "id": author['id'],
            "username": author['username'],
            "pen_name": author['pen_name'],
            "email": author['email'],
            "bio": author['bio'],
            "avatar": author['avatar'],
            "badge": author['badge'],
            "is_verified": bool(author['is_verified']),
            "reputation_score": author['reputation_score']
        }
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout_author():
    session.pop('author_id', None)
    session.pop('author_fingerprint', None)
    return jsonify({"status": "success"})

@app.route('/api/auth/me', methods=['GET'])
def get_current_author():
    author_id = session.get('author_id')
    if not author_id:
        return jsonify({"logged_in": False, "author": None})

    ip = get_client_ip(request)
    ua = request.headers.get('User-Agent', '')[:250]

    # Device Fingerprint Anti-Hijack Check
    expected_fp = compute_device_fingerprint(ip, ua)
    stored_fp = session.get('author_fingerprint')
    if stored_fp and stored_fp != expected_fp:
        log_admin_audit("AUTHOR_SESSION_HIJACK_DETECTED", "BLOCKED", None, target_id=author_id, details=f"Author session fingerprint mismatch from IP {ip}")
        session.pop('author_id', None)
        session.pop('author_fingerprint', None)
        return jsonify({"logged_in": False, "author": None})

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM authors WHERE id = ?", (author_id,))
    author = c.fetchone()

    if not author:
        session.pop('author_id', None)
        conn.close()
        return jsonify({"logged_in": False, "author": None})

    # Query author series
    c.execute('''
        SELECT DISTINCT series_title 
        FROM nodes 
        WHERE author_id = ? AND series_title IS NOT NULL AND series_title != ''
    ''', (author_id,))
    series_rows = c.fetchall()
    series_list = [r[0] for r in series_rows]

    # Query articles count and claps count
    c.execute('''
        SELECT COUNT(id), COALESCE(SUM(claps), 0) 
        FROM nodes 
        WHERE author_id = ? AND is_revoked = 0
    ''', (author_id,))
    art_count, total_claps = c.fetchone()
    conn.close()

    return jsonify({
        "logged_in": True,
        "author": {
            "id": author['id'],
            "username": author['username'],
            "pen_name": author['pen_name'],
            "email": author['email'],
            "bio": author['bio'],
            "avatar": author['avatar'],
            "badge": author['badge'],
            "is_verified": bool(author['is_verified']),
            "is_banned": bool(author['is_banned']),
            "reputation_score": author['reputation_score'],
            "series": series_list,
            "articles_count": art_count,
            "total_claps": total_claps
        }
    })

@app.route('/api/authors/<int:author_id>', methods=['GET'])
def get_author_portfolio(author_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM authors WHERE id = ?", (author_id,))
    author = c.fetchone()
    if not author:
        conn.close()
        return jsonify({"error": "Author not found."}), 404
        
    # Get all non-revoked articles written by this author
    c.execute('''
        SELECT id, title, category, text, read_time, claps, cover_image, series_title, series_part, created_at,
               (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = nodes.id AND r.is_revoked = 0) as reply_count
        FROM nodes
        WHERE author_id = ? AND is_revoked = 0
        ORDER BY id DESC
    ''', (author_id,))
    articles = [dict(r) for r in c.fetchall()]
    
    # Group into series
    series_dict = {}
    standalone = []
    for a in articles:
        if a.get('series_title'):
            st = a['series_title']
            if st not in series_dict:
                series_dict[st] = []
            series_dict[st].append(a)
        else:
            standalone.append(a)
            
    # Sort series parts
    for st in series_dict:
        series_dict[st].sort(key=lambda x: x.get('series_part') or 0)
        
    total_claps = sum(a['claps'] or 0 for a in articles)
    conn.close()
    
    return jsonify({
        "author": {
            "id": author['id'],
            "username": author['username'],
            "pen_name": author['pen_name'],
            "bio": author['bio'],
            "avatar": author['avatar'],
            "badge": author['badge'],
            "is_verified": bool(author['is_verified']),
            "is_banned": bool(author['is_banned']),
            "reputation_score": author['reputation_score'],
            "total_claps": total_claps,
            "article_count": len(articles)
        },
        "series": series_dict,
        "standalone_articles": standalone
    })

@app.route('/api/series/<path:series_title>', methods=['GET'])
def get_series_parts(series_title):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT n.id, n.title, n.name, n.category, n.read_time, n.claps, n.cover_image, n.series_part, n.x, n.y,
               auth.username, auth.badge, auth.is_verified
        FROM nodes n
        LEFT JOIN authors auth ON n.author_id = auth.id
        WHERE LOWER(n.series_title) = LOWER(?) AND n.is_revoked = 0
        ORDER BY n.series_part ASC, n.id ASC
    ''', (series_title,))
    parts = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"series_title": series_title, "parts": parts})

# ==========================================================================
# SECURE ADMIN AUTHENTICATION & MODERATION DASHBOARD API
# ==========================================================================
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json or {}
    raw_user = (data.get('username') or '').strip()
    raw_pass = (data.get('password') or '').strip()
    totp_code = (data.get('totp_code') or '').strip()
    hp_trap = data.get('hp_sec_token')
    ip = get_client_ip(request)
    ua = request.headers.get('User-Agent', '')[:250]

    # 1. BOT HONEYPOT TRAP: If hidden field is filled, silently discard & quarantine
    if hp_trap:
        log_admin_audit("BOT_HONEYPOT_TRIGGERED", "BLOCKED", raw_user, details="Automated scanner filled honeypot trap field.")
        record_persistent_failed_attempt(ip)
        time.sleep(2.0)
        return jsonify({"error": "Security alert: Automated scan detected."}), 400

    # 2. ZERO-TOLERANCE SQL INJECTION SHIELD & INPUT NORMALIZATION
    norm_user = unicodedata.normalize('NFKC', raw_user)
    if not norm_user or not raw_pass:
        return jsonify({"error": "Administrator credentials required."}), 400

    if len(norm_user) > 32 or len(raw_pass) > 128:
        log_admin_audit("INPUT_OVERFLOW_ATTEMPT", "BLOCKED", norm_user[:20], details="Length violation on credentials")
        return jsonify({"error": "Credentials exceed allowed parameter length."}), 400

    # Check for SQL injection patterns
    if SQLI_SUSPICIOUS_REGEX.search(norm_user) or not ADMIN_USERNAME_REGEX.match(norm_user):
        log_admin_audit("SQLI_ATTEMPT_BLOCKED", "QUARANTINED", norm_user[:30], details=f"SQL injection metacharacters detected in username from {ip}")
        record_persistent_failed_attempt(ip)
        time.sleep(1.5)
        return jsonify({"error": "Security Firewall Alert: Input contains forbidden SQL injection syntax or illegal characters. Characters are strictly restricted to alphanumeric and underscore."}), 400

    # 3. PERSISTENT BRUTE-FORCE & DISTRIBUTED BOTNET DEFENSE
    allowed_ip, lock_ip_msg = check_persistent_rate_limit(ip)
    if not allowed_ip:
        log_admin_audit("RATE_LIMIT_EXCEEDED", "LOCKED_OUT", norm_user, details=f"IP {ip} locked out")
        return jsonify({"error": lock_ip_msg}), 429

    allowed_user, lock_user_msg = check_persistent_rate_limit(norm_user)
    if not allowed_user:
        log_admin_audit("ACCOUNT_LOCKOUT_ACTIVE", "LOCKED_OUT", norm_user, details=f"Account {norm_user} locked out")
        return jsonify({"error": lock_user_msg}), 429

    # Progressive penalty sleep against timing scanners
    time.sleep(0.3)

    # 4. STRICT BOUND PARAMETERIZED QUERY (No string interpolation)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM admins WHERE username = ?", (norm_user,))
    admin = c.fetchone()

    # 5. CONSTANT-TIME TIMING ATTACK MITIGATION
    # If user doesn't exist, still compute 600,000-round PBKDF2 hash so response time is identical!
    if not admin:
        check_password_hash(DUMMY_PASSWORD_HASH, raw_pass)
        left = record_persistent_failed_attempt(ip)
        record_persistent_failed_attempt(norm_user)
        conn.close()
        log_admin_audit("LOGIN_FAILED", "REJECTED", norm_user, details=f"Unknown username attempt from {ip}")
        warning = f" (Attempts remaining before temporary lockout: {left})" if left > 0 else " (Security lockout triggered)"
        return jsonify({"error": f"Invalid administrator credentials.{warning}"}), 401

    # Check password hash
    if not check_password_hash(admin['password_hash'], raw_pass):
        left = record_persistent_failed_attempt(ip)
        record_persistent_failed_attempt(norm_user)
        c.execute("UPDATE admins SET failed_attempts = failed_attempts + 1 WHERE id = ?", (admin['id'],))
        conn.commit()
        conn.close()
        log_admin_audit("LOGIN_FAILED", "REJECTED", norm_user, details=f"Incorrect password attempt from {ip}")
        warning = f" (Attempts remaining before temporary lockout: {left})" if left > 0 else " (Security lockout triggered)"
        return jsonify({"error": f"Invalid administrator credentials.{warning}"}), 401

    # 6. MULTI-FACTOR AUTHENTICATION (2FA / TOTP)
    if admin['totp_enabled']:
        if not totp_code:
            conn.close()
            return jsonify({
                "status": "mfa_required",
                "mfa_required": True,
                "message": "Two-factor authentication code required to complete login."
            }), 200

        # Verify dynamic TOTP code or emergency backup recovery code
        totp_valid = verify_totp(admin['totp_secret'], totp_code)
        backup_valid = False
        if not totp_valid and len(totp_code) == 8:
            backup_valid = verify_and_consume_backup_code(conn, admin['id'], totp_code)

        if not totp_valid and not backup_valid:
            left = record_persistent_failed_attempt(ip)
            conn.close()
            log_admin_audit("2FA_VERIFICATION_FAILED", "REJECTED", norm_user, details=f"Invalid TOTP/backup code from {ip}")
            warning = f" (Attempts remaining: {left})" if left > 0 else ""
            return jsonify({"error": f"Invalid Two-Factor Authentication code or recovery key.{warning}"}), 401

    # 7. SUCCESSFUL AUTHENTICATION: Reset lockouts & bind cryptographic device fingerprint
    clear_persistent_lockout(ip)
    clear_persistent_lockout(norm_user)
    c.execute("UPDATE admins SET failed_attempts = 0, last_login = datetime('now') WHERE id = ?", (admin['id'],))
    conn.commit()
    conn.close()

    # Session fixation mitigation: Clear session completely before assigning new tokens
    session.clear()
    session['admin_id'] = admin['id']
    session['admin_username'] = admin['username']
    session['admin_role'] = admin['role']
    session['admin_fingerprint'] = compute_device_fingerprint(ip, ua)
    session['admin_csrf'] = secrets.token_hex(32)
    session['admin_last_activity'] = int(time.time())

    log_admin_audit("LOGIN_SUCCESS", "VERIFIED", norm_user, details=f"Superadmin session established from {ip}")

    return jsonify({
        "status": "success",
        "csrf_token": session['admin_csrf'],
        "admin": {
            "id": admin['id'],
            "username": admin['username'],
            "role": admin['role'],
            "totp_enabled": bool(admin['totp_enabled']),
            "last_login": admin['last_login']
        }
    })

@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('admin_role', None)
    session.pop('admin_token', None)
    return jsonify({"status": "success", "message": "Admin session terminated."})

@app.route('/api/admin/me', methods=['GET'])
def admin_me():
    admin_id = session.get('admin_id')
    if not admin_id:
        return jsonify({"logged_in": False})
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, role, last_login FROM admins WHERE id = ?", (admin_id,))
    admin = c.fetchone()
    conn.close()
    if not admin:
        session.pop('admin_id', None)
        return jsonify({"logged_in": False})
    return jsonify({"logged_in": True, "admin": dict(admin)})

@app.route('/api/admin/dashboard', methods=['GET'])
@admin_required
def admin_dashboard():
    """Returns comprehensive moderation data and telemetry for the admin control center."""
    conn = get_db()
    c = conn.cursor()

    # 1. Node counts & statistics
    c.execute("SELECT COUNT(*) FROM nodes")
    total_nodes = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM nodes WHERE is_revoked = 0")
    active_nodes = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM nodes WHERE is_revoked = 1")
    revoked_nodes = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM authors")
    total_authors = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM authors WHERE is_verified = 1")
    verified_authors = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(claps), 0) FROM nodes")
    total_claps = c.fetchone()[0]

    c.execute("SELECT COUNT(DISTINCT series_title) FROM nodes WHERE series_title IS NOT NULL AND series_title != ''")
    total_series = c.fetchone()[0]

    # 2. Retrieve all nodes with moderation state and creator metadata
    c.execute('''
        SELECT n.id, n.title, n.name, n.category, n.read_time, n.claps, n.cover_image,
               n.parent_id, n.ip, n.x, n.y, n.created_at, n.is_revoked, n.revoked_reason,
               n.revoked_at, n.revoked_by, n.series_title, n.series_part,
               n.author_id, auth.username as author_username, auth.pen_name as author_pen_name,
               auth.badge as author_badge, auth.is_verified as author_is_verified,
               auth.is_banned as author_is_banned,
               par.title as parent_title, par.name as parent_author,
               (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = n.id) as reply_count
        FROM nodes n
        LEFT JOIN nodes par ON n.parent_id = par.id
        LEFT JOIN authors auth ON n.author_id = auth.id
        ORDER BY n.id DESC
    ''')
    all_nodes = [dict(r) for r in c.fetchall()]

    # 3. Retrieve all authors
    c.execute('''
        SELECT a.id, a.username, a.pen_name, a.email, a.bio, a.avatar, a.badge,
               a.is_verified, a.is_banned, a.ban_reason, a.reputation_score, a.created_at,
               (SELECT COUNT(*) FROM nodes n WHERE n.author_id = a.id) as article_count,
               (SELECT COALESCE(SUM(claps), 0) FROM nodes n WHERE n.author_id = a.id) as total_claps
        FROM authors a
        ORDER BY a.id DESC
    ''')
    all_authors = [dict(r) for r in c.fetchall()]

    conn.close()

    return jsonify({
        "stats": {
            "total_nodes": total_nodes,
            "active_nodes": active_nodes,
            "revoked_nodes": revoked_nodes,
            "total_authors": total_authors,
            "verified_authors": verified_authors,
            "total_claps": total_claps,
            "total_series": total_series
        },
        "nodes": all_nodes,
        "authors": all_authors
    })

@app.route('/api/admin/nodes/<int:node_id>/revoke', methods=['POST'])
@admin_required
def admin_revoke_node(node_id):
    """Revokes / unpublishes a node (e.g. vulgar or inappropriate content). Immediately hides it from the public canvas."""
    data = request.json or {}
    reason = (data.get('reason') or 'Vulgar / Inappropriate Content').strip()
    admin_user = session.get('admin_username', 'admin')

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, title, is_revoked FROM nodes WHERE id = ?", (node_id,))
    node = c.fetchone()
    if not node:
        conn.close()
        return jsonify({"error": "Node not found."}), 404

    c.execute('''
        UPDATE nodes 
        SET is_revoked = 1, revoked_reason = ?, revoked_at = datetime('now'), revoked_by = ?
        WHERE id = ?
    ''', (reason, admin_user, node_id))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": f"Article #{node_id} ('{node['title']}') successfully revoked.",
        "node_id": node_id,
        "is_revoked": 1,
        "reason": reason
    })

@app.route('/api/admin/nodes/<int:node_id>/restore', methods=['POST'])
@admin_required
def admin_restore_node(node_id):
    """Restores a previously revoked node back to the live public canvas."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, title FROM nodes WHERE id = ?", (node_id,))
    node = c.fetchone()
    if not node:
        conn.close()
        return jsonify({"error": "Node not found."}), 404

    c.execute('''
        UPDATE nodes 
        SET is_revoked = 0, revoked_reason = NULL, revoked_at = NULL, revoked_by = NULL
        WHERE id = ?
    ''', (node_id,))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "message": f"Article #{node_id} ('{node['title']}') restored to the public matrix.",
        "node_id": node_id,
        "is_revoked": 0
    })

@app.route('/api/admin/nodes/<int:node_id>', methods=['DELETE'])
@admin_required
def admin_delete_node(node_id):
    """Permanently deletes a node and unbinds or re-roots any children."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, title, parent_id FROM nodes WHERE id = ?", (node_id,))
    node = c.fetchone()
    if not node:
        conn.close()
        return jsonify({"error": "Node not found."}), 404

    # Update any child replies so their parent_id points to grandparent or NULL
    c.execute("UPDATE nodes SET parent_id = ? WHERE parent_id = ?", (node['parent_id'], node_id))
    c.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": f"Article #{node_id} deleted permanently."})

@app.route('/api/admin/authors/<int:author_id>/toggle-ban', methods=['POST'])
@admin_required
def admin_toggle_ban_author(author_id):
    data = request.json or {}
    reason = (data.get('reason') or 'Violation of community editorial standards').strip()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, is_banned FROM authors WHERE id = ?", (author_id,))
    author = c.fetchone()
    if not author:
        conn.close()
        return jsonify({"error": "Author not found."}), 404

    new_banned_state = 0 if author['is_banned'] else 1
    new_reason = reason if new_banned_state else None

    c.execute("UPDATE authors SET is_banned = ?, ban_reason = ? WHERE id = ?", (new_banned_state, new_reason, author_id))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "author_id": author_id,
        "is_banned": bool(new_banned_state),
        "message": f"Author @{author['username']} {'suspended' if new_banned_state else 'reinstated'}."
    })

@app.route('/api/admin/authors/<int:author_id>/toggle-verify', methods=['POST'])
@admin_required
def admin_toggle_verify_author(author_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, is_verified FROM authors WHERE id = ?", (author_id,))
    author = c.fetchone()
    if not author:
        conn.close()
        return jsonify({"error": "Author not found."}), 404

    new_verify_state = 0 if author['is_verified'] else 1
    c.execute("UPDATE authors SET is_verified = ? WHERE id = ?", (new_verify_state, author_id))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "author_id": author_id,
        "is_verified": bool(new_verify_state),
        "message": f"Author @{author['username']} verification status updated to {bool(new_verify_state)}."
    })

@app.route('/api/admin/change-password', methods=['POST'])
@admin_required
def admin_change_password():
    data = request.json or {}
    old_pw = (data.get('old_password') or '').strip()
    new_pw = (data.get('new_password') or '').strip()

    if not new_pw or len(new_pw) < 8:
        return jsonify({"error": "New password must be at least 8 characters."}), 400

    admin_id = session['admin_id']
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT password_hash FROM admins WHERE id = ?", (admin_id,))
    admin = c.fetchone()

    if not admin or not check_password_hash(admin['password_hash'], old_pw):
        conn.close()
        return jsonify({"error": "Current password incorrect."}), 401

    new_hash = generate_password_hash(new_pw, method='pbkdf2:sha256:600000')
    c.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (new_hash, admin_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "success", "message": "Admin password updated successfully."})

# ==========================================================================
# EDITORIAL NODES API (Publishing with Photo & Series)
# ==========================================================================
@app.route('/api/nodes', methods=['GET', 'POST'])
def handle_nodes():
    conn = get_db()
    c = conn.cursor()
    
    # -------------------------------------------------------------
    # POST: Publish Article or Reply (Bound to Verified Author & Series)
    # -------------------------------------------------------------
    if request.method == 'POST':
        data = request.json or {}
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        
        # Check active author session
        author_id = session.get('author_id')
        is_verified_author = 0

        # Check if author is banned
        if author_id:
            c.execute("SELECT is_banned, ban_reason FROM authors WHERE id = ?", (author_id,))
            a_check = c.fetchone()
            if a_check and a_check['is_banned']:
                conn.close()
                return jsonify({"error": f"Author account is suspended ({a_check['ban_reason'] or 'Guideline violation'}). Cannot publish."}), 403
        
        raw_name = (data.get('name') or '').strip()
        raw_title = (data.get('title') or '').strip()
        raw_content = (data.get('content') or '').strip()
        raw_category = (data.get('category') or 'Perspective').strip()
        raw_image = (data.get('image') or '').strip()
        cover_image = (data.get('cover_image') or '').strip()
        
        # Series fields
        series_title = (data.get('series_title') or '').strip()
        series_part = data.get('series_part')
        try:
            series_part = int(series_part) if series_part else None
        except (ValueError, TypeError):
            series_part = None
            
        parent_id = data.get('parent_id')
        if parent_id in ('', 'null', 0, '0', None):
            parent_id = None
        else:
            try:
                parent_id = int(parent_id)
            except (ValueError, TypeError):
                parent_id = None

        # Verify parent_id actually exists in nodes table to guarantee branch integrity
        if parent_id is not None:
            c.execute("SELECT id FROM nodes WHERE id = ?", (parent_id,))
            if not c.fetchone():
                parent_id = None

        if not raw_title:
            conn.close()
            return jsonify({"error": "Please provide an Article Headline / Title."}), 400
            
        # If logged in as verified author, bind profile
        if author_id:
            c.execute("SELECT * FROM authors WHERE id = ?", (author_id,))
            author_row = c.fetchone()
            if author_row:
                name = author_row['pen_name']
                raw_image = author_row['avatar']
                is_verified_author = author_row['is_verified']
            else:
                name = html.escape(raw_name[:40]) if raw_name else "Anonymous Thinker"
        else:
            name = html.escape(raw_name[:40]) if raw_name else "Anonymous Thinker"

        title = html.escape(raw_title[:100])
        category = html.escape(raw_category[:25])
        content = raw_content[:25000]
        
        # Excerpt generation
        clean_preview = re.sub(r'[#*`_>\[\]]', '', content).strip()
        text = html.escape(clean_preview[:130] + ('...' if len(clean_preview) > 130 else ''))
        if not text:
            text = title
            
        words = len(content.split())
        read_time = f"{max(1, words // 160)} min read" if words > 30 else "1 min read"
        
        if not raw_image:
            avatar_bg = secrets.choice(['2563eb', '7c3aed', '059669', 'd97706', 'dc2626'])
            image = f"https://api.dicebear.com/7.x/bottts/svg?seed={name}&backgroundColor={avatar_bg}"
        else:
            image = raw_image

        # Photo Attachment check: Use the exact user photo provided
        if not cover_image:
            cover_image = None

        nx, ny = calculate_node_coordinates(c, parent_id)
        ref_code = secrets.token_hex(4)
        
        c.execute('''
            INSERT INTO nodes 
            (name, title, category, text, content, read_time, claps, image, cover_image, 
             parent_id, sponsor_id, ip, x, y, ref_code, is_spillover, 
             author_id, series_title, series_part, is_verified_author, is_revoked, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0, datetime('now'))
        ''', (name, title, category, text, content, read_time, 0, image, cover_image,
              parent_id, parent_id, ip, nx, ny, ref_code,
              author_id, series_title or None, series_part, is_verified_author))
        
        new_id = c.lastrowid
        conn.commit()
        
        parent_name = None
        parent_title = None
        if parent_id:
            c.execute("SELECT name, title FROM nodes WHERE id = ?", (parent_id,))
            p_row = c.fetchone()
            if p_row:
                parent_name = p_row['name']
                parent_title = p_row['title']

        conn.close()
        return jsonify({
            "status": "success",
            "node": {
                "id": new_id,
                "title": title,
                "name": name,
                "category": category,
                "text": text,
                "content": content,
                "read_time": read_time,
                "claps": 0,
                "image": image,
                "cover_image": cover_image,
                "parent_id": parent_id,
                "parent_name": parent_name,
                "parent_title": parent_title,
                "author_id": author_id,
                "series_title": series_title,
                "series_part": series_part,
                "is_verified_author": bool(is_verified_author),
                "x": nx,
                "y": ny,
                "created_at": "Just now",
                "reply_count": 0
            }
        })

    # -------------------------------------------------------------
    # GET: Retrieve all Editorial Nodes, Connections, and Leaderboard
    # Filters out revoked nodes from the public spatial canvas!
    # -------------------------------------------------------------
    c.execute('''
        SELECT n.id, n.name, n.title, n.category, n.text, n.content, n.read_time, n.claps,
               n.image, n.cover_image, n.parent_id, n.x, n.y, n.ref_code, n.created_at,
               n.author_id, n.series_title, n.series_part, n.is_verified_author,
               par.name as parent_name,
               par.title as parent_title,
               auth.badge as author_badge,
               auth.username as author_username,
               (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = n.id AND r.is_revoked = 0) as reply_count
        FROM nodes n
        LEFT JOIN nodes par ON n.parent_id = par.id
        LEFT JOIN authors auth ON n.author_id = auth.id
        WHERE COALESCE(n.is_revoked, 0) = 0
        ORDER BY n.id ASC
    ''')
    raw_nodes = c.fetchall()
    
    nodes = []
    total_claps = 0
    total_editions = 0
    total_replies = 0
    
    for r in raw_nodes:
        claps = r['claps'] or 0
        total_claps += claps
        if r['parent_id'] is None:
            total_editions += 1
        else:
            total_replies += 1
            
        depth = max(0, (r['y'] - 150) // 340)
        created_str = r['created_at'] or datetime.now().strftime("%Y-%m-%d %H:%M")
        
        nodes.append({
            "id": r['id'],
            "name": r['name'] or "Citizen",
            "title": r['title'] or (r['name'] + " Note"),
            "category": r['category'] or "Newsletter",
            "text": r['text'] or "",
            "content": r['content'] or r['text'] or "",
            "read_time": r['read_time'] or "2 min read",
            "claps": claps,
            "image": r['image'],
            "cover_image": r['cover_image'],
            "parent_id": r['parent_id'],
            "parent_name": r['parent_name'],
            "parent_title": r['parent_title'],
            "author_id": r['author_id'],
            "author_username": r['author_username'],
            "author_badge": r['author_badge'] or "Verified Author",
            "series_title": r['series_title'],
            "series_part": r['series_part'],
            "is_verified_author": bool(r['is_verified_author']),
            "x": r['x'],
            "y": r['y'],
            "depth": depth,
            "ref_code": r['ref_code'],
            "created_at": created_str,
            "reply_count": r['reply_count']
        })
        
    # Top Verified Writers Leaderboard (Ranked by Total Claps + Articles)
    c.execute('''
        SELECT a.id, a.pen_name, a.username, a.avatar, a.badge,
               COUNT(n.id) as article_count, 
               COALESCE(SUM(n.claps), 0) as total_claps
        FROM authors a
        JOIN nodes n ON n.author_id = a.id AND n.is_revoked = 0
        WHERE a.is_banned = 0
        GROUP BY a.id 
        ORDER BY total_claps DESC, article_count DESC 
        LIMIT 10
    ''')
    top_authors = [
        {
            "id": r[0],
            "name": r[1],
            "username": r[2],
            "image": r[3],
            "badge": r[4],
            "article_count": r[5],
            "total_claps": r[6]
        }
        for r in c.fetchall()
    ]
    
    # Active Series across the platform
    c.execute('''
        SELECT n.series_title, n.name as author_name, n.author_id, COUNT(n.id) as parts_count,
               MIN(n.id) as first_node_id
        FROM nodes n
        WHERE n.series_title IS NOT NULL AND n.series_title != '' AND n.is_revoked = 0
        GROUP BY n.series_title
        ORDER BY parts_count DESC
    ''')
    active_series = [
        {
            "title": r[0],
            "author_name": r[1],
            "author_id": r[2],
            "parts_count": r[3],
            "first_node_id": r[4]
        }
        for r in c.fetchall()
    ]
    
    # Trending Articles
    c.execute('''
        SELECT n.id, n.title, n.name, n.category, n.claps, n.series_title, n.series_part,
               (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = n.id AND r.is_revoked = 0) as replies
        FROM nodes n
        WHERE n.is_revoked = 0
        ORDER BY (COALESCE(n.claps, 0) * 2 + (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = n.id AND r.is_revoked = 0) * 4) DESC
        LIMIT 8
    ''')
    trending = [
        {
            "id": r[0],
            "title": r[1] or "Untitled",
            "name": r[2],
            "category": r[3] or "Article",
            "claps": r[4] or 0,
            "series_title": r[5],
            "series_part": r[6],
            "replies": r[7] or 0
        }
        for r in c.fetchall()
    ]

    stats = {
        "total_nodes": len(nodes),
        "total_editions": total_editions,
        "total_replies": total_replies,
        "total_claps": total_claps,
        "total_series": len(active_series)
    }
    
    conn.close()
    return jsonify({
        "nodes": nodes,
        "leaders": top_authors,
        "trending": trending,
        "active_series": active_series,
        "stats": stats
    })

# -------------------------------------------------------------
# GET: Retrieve single node with full details & series siblings
# -------------------------------------------------------------
@app.route('/api/nodes/<int:node_id>', methods=['GET'])
def get_node_details(node_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT n.id, n.name, n.title, n.category, n.text, n.content, n.read_time, n.claps,
               n.image, n.cover_image, n.parent_id, n.x, n.y, n.ref_code, n.created_at,
               n.author_id, n.series_title, n.series_part, n.is_verified_author,
               n.is_revoked, n.revoked_reason,
               par.name as parent_name,
               par.title as parent_title,
               auth.badge as author_badge,
               auth.username as author_username,
               auth.bio as author_bio
        FROM nodes n
        LEFT JOIN nodes par ON n.parent_id = par.id
        LEFT JOIN authors auth ON n.author_id = auth.id
        WHERE n.id = ?
    ''', (node_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Article node not found."}), 404
        
    is_admin = bool(session.get('admin_id'))
    if row['is_revoked'] and not is_admin:
        conn.close()
        return jsonify({"error": f"This article has been revoked by editorial moderation ({row['revoked_reason'] or 'Community standards'})."}), 404

    c.execute('''
        SELECT id, name, title, category, text, read_time, claps, image, cover_image, created_at, is_verified_author
        FROM nodes
        WHERE parent_id = ? AND is_revoked = 0
        ORDER BY id ASC
    ''', (node_id,))
    replies = [dict(r) for r in c.fetchall()]
    
    node = dict(row)
    node['replies'] = replies
    node['reply_count'] = len(replies)
    
    # If part of a series, fetch all sibling parts
    if node.get('series_title'):
        c.execute('''
            SELECT id, title, series_part, read_time, claps
            FROM nodes
            WHERE LOWER(series_title) = LOWER(?) AND is_revoked = 0
            ORDER BY series_part ASC, id ASC
        ''', (node['series_title'],))
        node['series_siblings'] = [dict(r) for r in c.fetchall()]
    else:
        node['series_siblings'] = []
        
    conn.close()
    return jsonify({"node": node})

# -------------------------------------------------------------
# POST: Clap / Upvote
# -------------------------------------------------------------
@app.route('/api/nodes/<int:node_id>/clap', methods=['POST'])
def clap_node(node_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT claps, is_revoked FROM nodes WHERE id = ?", (node_id,))
    row = c.fetchone()
    if not row or row['is_revoked']:
        conn.close()
        return jsonify({"error": "Node not found."}), 404
        
    new_claps = (row['claps'] or 0) + 1
    c.execute("UPDATE nodes SET claps = ? WHERE id = ?", (new_claps, node_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "node_id": node_id, "claps": new_claps})


# ==========================================================================
# ADVANCED SECURITY: 2FA / TOTP MANAGEMENT & AUDIT TELEMETRY API
# ==========================================================================
@app.route('/api/admin/security/status', methods=['GET'])
@admin_required
def admin_security_status():
    admin_id = session['admin_id']
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT username, totp_enabled, last_login, created_at FROM admins WHERE id = ?", (admin_id,))
    admin = c.fetchone()
    
    # Audit log counts
    c.execute("SELECT COUNT(*) FROM admin_audit_logs")
    total_audits = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM admin_lockouts WHERE locked_until > datetime('now')")
    active_lockouts = c.fetchone()[0]
    conn.close()

    return jsonify({
        "username": admin['username'],
        "totp_enabled": bool(admin['totp_enabled']),
        "ip": get_client_ip(request),
        "total_audit_events": total_audits,
        "active_lockouts": active_lockouts,
        "encryption": "PBKDF2-SHA256 (600,000 rounds)",
        "firewall": "Active Zero-Tolerance Regex + Parameterized SQL",
        "timing_mitigation": "Constant-Time Dummy Comparison Active"
    })

@app.route('/api/admin/security/2fa/generate', methods=['POST'])
@admin_required
def admin_generate_2fa():
    admin_id = session['admin_id']
    admin_user = session['admin_username']
    secret = generate_totp_secret()
    uri = get_totp_uri(admin_user, secret)
    plain_codes, hashed_codes = generate_backup_codes(5)

    conn = get_db()
    c = conn.cursor()
    # Save temporary secret and backup codes
    c.execute("UPDATE admins SET totp_secret = ?, backup_codes = ? WHERE id = ?",
              (secret, json.dumps(hashed_codes), admin_id))
    conn.commit()
    conn.close()

    log_admin_audit("2FA_SECRET_GENERATED", "PENDING", admin_user, details="New TOTP secret and backup keys generated")

    return jsonify({
        "status": "success",
        "secret": secret,
        "otpauth_uri": uri,
        "backup_codes": plain_codes,
        "message": "Scan the URI or enter the secret into Google Authenticator or 1Password, then confirm with a 6-digit code."
    })

@app.route('/api/admin/security/2fa/activate', methods=['POST'])
@admin_required
def admin_activate_2fa():
    data = request.json or {}
    code = (data.get('code') or '').strip()
    admin_id = session['admin_id']
    admin_user = session['admin_username']

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT totp_secret FROM admins WHERE id = ?", (admin_id,))
    admin = c.fetchone()

    if not admin or not admin['totp_secret']:
        conn.close()
        return jsonify({"error": "No 2FA setup in progress. Please generate a secret first."}), 400

    if not verify_totp(admin['totp_secret'], code):
        conn.close()
        log_admin_audit("2FA_ACTIVATION_FAILED", "REJECTED", admin_user, details="Invalid confirmation code")
        return jsonify({"error": "Invalid 6-digit code. Please verify device time synchronization and try again."}), 400

    c.execute("UPDATE admins SET totp_enabled = 1 WHERE id = ?", (admin_id,))
    conn.commit()
    conn.close()

    log_admin_audit("2FA_ACTIVATED", "ENABLED", admin_user, details="Two-factor authentication permanently activated")
    return jsonify({"status": "success", "message": "Two-Factor Authentication is now permanently active on this account!"})

@app.route('/api/admin/security/2fa/disable', methods=['POST'])
@admin_required
def admin_disable_2fa():
    data = request.json or {}
    password = (data.get('password') or '').strip()
    admin_id = session['admin_id']
    admin_user = session['admin_username']

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT password_hash FROM admins WHERE id = ?", (admin_id,))
    admin = c.fetchone()

    if not admin or not check_password_hash(admin['password_hash'], password):
        conn.close()
        log_admin_audit("2FA_DISABLE_FAILED", "REJECTED", admin_user, details="Invalid master password")
        return jsonify({"error": "Master password required to disable 2FA."}), 401

    c.execute("UPDATE admins SET totp_enabled = 0, totp_secret = NULL, backup_codes = NULL WHERE id = ?", (admin_id,))
    conn.commit()
    conn.close()

    log_admin_audit("2FA_DISABLED", "DISABLED", admin_user, details="Two-factor authentication turned off")
    return jsonify({"status": "success", "message": "Two-Factor Authentication has been disabled."})

@app.route('/api/admin/security/audit-logs', methods=['GET'])
@admin_required
def admin_get_audit_logs():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT id, admin_user, event_type, target_id, ip_address, user_agent, status, details, created_at
        FROM admin_audit_logs
        ORDER BY id DESC
        LIMIT 60
    ''')
    logs = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"status": "success", "logs": logs})

# -------------------------------------------------------------
# SEED DEMO KNOWLEDGE MATRIX
# -------------------------------------------------------------
@app.route('/api/seed-demo', methods=['POST'])
def seed_demo_matrix():
    """Populate matrix with rich curated sample discourse branches for live exploration."""
    conn = get_db()
    c = conn.cursor()
    
    # Ensure demo authors exist
    authors = [
        ("satoshi_ed", "Satoshi Editorial", "editorial@blocktree.org", generate_password_hash("DemoSecret123!"), "Core Editorial Dispatch for the Spatial Knowledge Graph", "https://api.dicebear.com/7.x/bottts/svg?seed=Satoshi", "Founding Editor", 1),
        ("elena_vance", "Elena Vance", "elena@discourse.org", generate_password_hash("DemoSecret123!"), "Cognitive Architect & Digital Epistemology Researcher", "https://api.dicebear.com/7.x/bottts/svg?seed=Elena", "Senior Fellow", 1),
        ("aris_thorne", "Dr. Aris Thorne", "aris@distributed.tech", generate_password_hash("DemoSecret123!"), "Distributed Systems & Graph Database Architect", "https://api.dicebear.com/7.x/bottts/svg?seed=Aris", "Distinguished Architect", 1),
        ("marcus_chen", "Marcus Chen", "marcus@systems.io", generate_password_hash("DemoSecret123!"), "Full-Stack Reliability & Visual Scaling Specialist", "https://api.dicebear.com/7.x/bottts/svg?seed=Marcus", "Verified Critic", 1),
    ]
    
    for u, p, e, ph, b, av, bg, iv in authors:
        c.execute("""
            INSERT OR IGNORE INTO authors (username, pen_name, email, password_hash, bio, avatar, badge, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (u, p, e, ph, b, av, bg, iv))
    
    # Retrieve author IDs
    c.execute("SELECT id, username FROM authors")
    auth_map = {r['username']: r['id'] for r in c.fetchall()}

    # 7 Rich Editorial Nodes (with spatial layout and branching references)
    demo_nodes = [
        {
            "id": 1,
            "name": "Satoshi Editorial",
            "author_id": auth_map.get("satoshi_ed", 1),
            "parent_id": None,
            "title": "Matrix Dispatch #01: The Dawn of Spatial Knowledge",
            "category": "Newsletter",
            "text": "Welcome to the world's first spatial newsletter where ideas branch organically like neural pathways instead of flat feeds.",
            "read_time": "3 min read",
            "claps": 64,
            "x": 3000,
            "y": 250,
            "ref_code": "ROOT-001",
            "cover_image": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop&q=80",
            "content": """# Matrix Dispatch #01: The Dawn of Spatial Knowledge\n\n### Why Flat Feeds Are Broken\nFor over fifteen years, social networks and digital publications have forced human discourse into a single vertical scroll. From algorithmic feeds to comment sections, every complex thought is reduced to a flat, chronologically squashed column.\n\nWhen an author writes a comprehensive essay, fifty distinct sub-arguments occur in the replies. Yet in a flat feed:\n- Brilliant technical counterpoints get buried under memes.\n- Contextual replies lose their semantic tether.\n- Branching debates cannot be visualized.\n\n---\n\n### The Spatial Tree Paradigm\n**BlockTree is the antithesis of the flat timeline.** Here, every article and every reply exists as an autonomous node on an infinite 2D canvas.\n\nWhen you reply to an article, you don't post a comment beneath it—you **spawn a new node connected by a visual circuit branch**.\n\n> "We do not think in single columns. Human knowledge is a dense, multi-dimensional hypergraph of hypotheses, counter-arguments, and synthesis."\n\n---\n\n### How to Engage With This Edition\n1. **Explore the Canvas**: Pan and zoom freely across the tree. Follow the glowing circuit branches to see who replied to whom.\n2. **Read Deep Dives**: Click any card to open this sleek reader drawer with formatted markdown, claps, and parent references.\n3. **Branch the Conversation**: Click **Reply as Node** below to attach your own perspective or counter-argument directly to this article!\n\nLet the discourse begin.\n\n*— The Editorial Core*"""
        },
        {
            "id": 2,
            "name": "Elena Vance",
            "author_id": auth_map.get("elena_vance", 2),
            "parent_id": 1,
            "title": "Perspective: Why Linear Threads Kill High-Level Discourse",
            "category": "Perspective",
            "text": "Linear comment threads collapse nuances into shouting matches. Visual branching restores context and intellectual integrity.",
            "read_time": "2 min read",
            "claps": 42,
            "x": 2350,
            "y": 720,
            "ref_code": "PERS-002",
            "cover_image": "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=800&auto=format&fit=crop&q=80",
            "content": """## Linear Comment Feeds Are Cognitively Defective\n\nReading through traditional social media replies feels like listening to twenty people speaking into a single microphone simultaneously.\n\n### The Problem of Context Decay\nWhen a commenter responds to paragraph 4 of an essay, and someone replies to that comment disagreeing about paragraph 2, the entire context breaks down.\n\n### How Spatial Trees Fix This:\n1. **Topological Lineage**: You see the exact ancestor path. If I reply to the *Matrix Dispatch*, my card attaches directly below it.\n2. **Parallel Sub-Debates**: Multiple perspectives can flourish side-by-side without drowning each other out.\n3. **Self-Balancing Structure**: Popular branches expand horizontally and vertically based on engagement rather than algorithmic rage-bait.\n\nSpatial organization gives thoughts the breathing room they deserve."""
        },
        {
            "id": 3,
            "name": "Dr. Aris Thorne",
            "author_id": auth_map.get("aris_thorne", 3),
            "parent_id": 1,
            "title": "Deep Dive: Graph Databases vs Relational Trees",
            "category": "Deep Dive",
            "text": "A technical examination of hierarchical tree storage, adjacency lists, and spatial index querying in decentralized newsrooms.",
            "read_time": "4 min read",
            "claps": 51,
            "x": 2980,
            "y": 720,
            "ref_code": "DIVE-003",
            "cover_image": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&auto=format&fit=crop&q=80",
            "content": """## Engineering the Spatial Publication Backbone\n\nHow do we represent an arbitrary branching network of articles, counterpoints, and rebuttals without crippling database performance?\n\n```python\n# BFS Traversal for Dynamic Branch Layout\ndef get_branch_lineage(node_id):\n    lineage = []\n    curr = node_id\n    while curr:\n        node = db.get_node(curr)\n        lineage.append(node)\n        curr = node.parent_id\n    return list(reversed(lineage))\n```\n\n### Key Architectural Choices:\n- **Adjacency Lists**: Pointers via `parent_id` provide $O(1)$ node insertion time, which is critical for real-time collaborative publishing.\n- **Dynamic Collision Avoidance**: As reply depth increases, sibling repulsion forces prevent nodes from overlapping horizontally.\n- **Hardware-Accelerated Canvas**: CSS matrix transforms guarantee 60fps canvas traversal even with thousands of editorial cards."""
        },
        {
            "id": 4,
            "name": "Kai Soren",
            "author_id": auth_map.get("satoshi_ed", 1),
            "parent_id": 1,
            "title": "Discussion: The Infinite Canvas as an Editorial Medium",
            "category": "Discussion",
            "text": "How spatial navigation stimulates spatial memory, making long-form investigative journalism far more retentive and engaging.",
            "read_time": "3 min read",
            "claps": 31,
            "x": 3610,
            "y": 720,
            "ref_code": "DISC-004",
            "cover_image": "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=800&auto=format&fit=crop&q=80",
            "content": """## Spatial Memory in Digital Journalism\n\nPsychological research into the *Method of Loci* shows that humans recall information dramatically better when associated with physical or 2D spatial landmarks.\n\nWhen you read a traditional article on a website:\n- You scroll past text that vanishes off the top edge.\n- You have no spatial mental map of where ideas were situated relative to one another.\n\n### On the BlockTree Canvas:\n- You remember that the **Technical Deep Dive** was on the left branch.\n- You remember that the **Ethical Counterpoint** was located two levels down in the middle.\n- Your brain forms an intuitive geographic memory of the entire debate.\n\nThis is the future of interactive long-form publishing."""
        },
        {
            "id": 5,
            "name": "Elena Vance",
            "author_id": auth_map.get("elena_vance", 2),
            "parent_id": 2,
            "title": "Deep Dive: Three Rules for High-Signal Branching",
            "category": "Deep Dive",
            "text": "Editorial standards to ensure each new reply node adds substantial value, context, or constructive critique to the tree.",
            "read_time": "2 min read",
            "claps": 25,
            "x": 2050,
            "y": 1200,
            "ref_code": "DIVE-005",
            "cover_image": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=800&auto=format&fit=crop&q=80",
            "content": """## Maintaining High Signal in Visual Trees\n\nBecause each reply creates a prominent physical node on the canvas, low-effort replies must be discouraged by community design.\n\n### The Three Tenets:\n1. **Substantiate Your Branch**: Don't just agree or disagree—explain *why*, provide a reference, or introduce an alternative paradigm.\n2. **Anchor to the Exact Node**: If you are rebutting a specific sub-argument, reply directly to that node rather than the root article.\n3. **Keep Excerpts Crisp**: Make your title and card excerpt evocative and clear so passersby can navigate the tree effortlessly."""
        },
        {
            "id": 6,
            "name": "Marcus Chen",
            "author_id": auth_map.get("marcus_chen", 4),
            "parent_id": 2,
            "title": "Counterpoint: Can Spatial Trees Prevent Visual Sprawl?",
            "category": "Counterpoint",
            "text": "Trees are magnificent for focused essays with 10-50 replies, but what happens when a topic blows up to 5,000 nodes?",
            "read_time": "3 min read",
            "claps": 48,
            "x": 2650,
            "y": 1200,
            "ref_code": "CP-006",
            "cover_image": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop&q=80",
            "content": """## A Challenge to the Infinite Tree Thesis\n\n*In direct reply to Elena Vance's thesis on linear vs spatial feeds.*\n\nWhile I completely agree that linear comment sections are broken, spatial trees introduce a different engineering challenge: **Visual Sprawl**.\n\n### The Complexity Scaling Problem\nWhen 5,000 people reply to an explosive news story:\n- Sibling nodes could stretch across 100,000 horizontal pixels.\n- The user feels overwhelmed trying to find the highest-quality branches.\n\n### Potential Solutions:\n1. **Dual Views**: Allow readers to switch to an Editorial Stream / Feed View.\n2. **Category Discovery Filters**: Isolate perspectives and counterpoints.\n3. **Semantic LOD (Level-of-Detail)**: When zoomed out, spotlight verified branches.\n\nWhat does the community think?"""
        },
        {
            "id": 7,
            "name": "Dr. Aris Thorne",
            "author_id": auth_map.get("aris_thorne", 3),
            "parent_id": 3,
            "title": "Perspective: Micro-Daemons & Zero-Copy Topology",
            "category": "Perspective",
            "text": "Exploring event-driven pub/sub daemons for sub-millisecond propagation of tree updates across global matrix subscribers.",
            "read_time": "3 min read",
            "claps": 39,
            "x": 3300,
            "y": 1200,
            "ref_code": "PERS-007",
            "cover_image": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&auto=format&fit=crop&q=80",
            "content": """## Sub-Millisecond Matrix Propagation\n\nWhen a new branch is attached, all active viewers should see the bezier curve sprout in real time with hardware-accelerated fluid motion.\n\n### Key Pipeline:\n- WebSocket / SSE broadcast ring\n- Differential tree delta payload (< 1KB)\n- Local canvas client-side spline interpolation"""
        }
    ]

    for n in demo_nodes:
        c.execute("""
            INSERT OR REPLACE INTO nodes (id, name, title, category, text, content, read_time, claps, x, y, parent_id, author_id, ref_code, cover_image, is_verified_author, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        """, (n['id'], n['name'], n['title'], n['category'], n['text'], n['content'], n['read_time'], n['claps'], n['x'], n['y'], n['parent_id'], n['author_id'], n['ref_code'], n['cover_image']))

    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Demo knowledge matrix seeded successfully with 7 connected branches!"})

@app.route('/api/reset-blank', methods=['POST'])
def reset_blank_matrix():
    """Reset the nodes database back to 0 (pristine production state)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM nodes")
    c.execute("DELETE FROM sqlite_sequence WHERE name='nodes'")
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "Database reset to pristine blank state."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=True)
