import os
import sqlite3
import secrets
import html
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'blocktree-cyber-editorial-secret-2026')
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

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Authors table (Verified customer/author registration system)
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
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Nodes table
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
        created_at DATETIME
    )''')
    
    # Check and add any missing columns non-destructively
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
        ('is_verified_author', 'INTEGER DEFAULT 0')
    ]
    for col_name, col_type in missing_cols:
        if col_name not in columns:
            c.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()

init_db()

CARD_WIDTH = 270
CARD_HEIGHT = 200
MIN_DIST_X = 350  # 270px card + 80px clean visual clearance
MIN_DIST_Y = 340  # card height + generous gap
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

@app.route('/')
def home():
    return render_template('index.html')

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
# VERIFIED AUTHOR REGISTRATION & AUTHENTICATION
# ==========================================================================
@app.route('/api/auth/register', methods=['POST'])
def register_author():
    data = request.json or {}
    username = (data.get('username') or '').strip().lower()
    pen_name = (data.get('pen_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    bio = (data.get('bio') or '').strip()
    avatar = (data.get('avatar') or '').strip()
    
    if not username or not pen_name or not password:
        return jsonify({"error": "Username, Pen Name, and Password are required."}), 400
    if len(username) < 3 or not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return jsonify({"error": "Username must be at least 3 characters and contain only letters, numbers, hyphens, or underscores."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
        
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

    pw_hash = generate_password_hash(password)
    c.execute('''
        INSERT INTO authors (username, pen_name, email, password_hash, bio, avatar, badge, is_verified, reputation_score)
        VALUES (?, ?, ?, ?, ?, ?, 'Verified Author', 1, 150)
    ''', (username, pen_name, email or None, pw_hash, bio, avatar))
    author_id = c.lastrowid
    conn.commit()
    conn.close()
    
    session['author_id'] = author_id
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
    identifier = (data.get('identifier') or '').strip().lower()
    password = (data.get('password') or '').strip()
    
    if not identifier or not password:
        return jsonify({"error": "Username/Email and Password are required."}), 400
        
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM authors WHERE LOWER(username) = ? OR LOWER(email) = ?", (identifier, identifier))
    author = c.fetchone()
    conn.close()
    
    if not author or not check_password_hash(author['password_hash'], password):
        return jsonify({"error": "Invalid username/email or password."}), 401
        
    session['author_id'] = author['id']
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
    return jsonify({"status": "success"})

@app.route('/api/auth/me', methods=['GET'])
def get_current_author():
    author_id = session.get('author_id')
    if not author_id:
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
    series_list = [r[0] for r in c.fetchall()]
    
    # Query articles count and claps count
    c.execute('''
        SELECT COUNT(id), COALESCE(SUM(claps), 0) 
        FROM nodes 
        WHERE author_id = ?
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
            "reputation_score": author['reputation_score'],
            "series": series_list,
            "article_count": art_count,
            "total_claps": total_claps
        }
    })

# ==========================================================================
# AUTHOR PORTFOLIO & SERIES DISCOVERY
# ==========================================================================
@app.route('/api/authors/<int:author_id>', methods=['GET'])
def get_author_portfolio(author_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM authors WHERE id = ?", (author_id,))
    author = c.fetchone()
    if not author:
        conn.close()
        return jsonify({"error": "Author not found."}), 404
        
    # Get all articles written by this author
    c.execute('''
        SELECT id, title, category, text, read_time, claps, cover_image, series_title, series_part, created_at,
               (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = nodes.id) as reply_count
        FROM nodes
        WHERE author_id = ?
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
        WHERE LOWER(n.series_title) = LOWER(?)
        ORDER BY n.series_part ASC, n.id ASC
    ''', (series_title,))
    parts = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({"series_title": series_title, "parts": parts})

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
        # If user didn't provide any, use a fallback
        if not cover_image:
            cover_image = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop&q=80"

        nx, ny = calculate_node_coordinates(c, parent_id)
        ref_code = secrets.token_hex(4)
        
        c.execute('''
            INSERT INTO nodes 
            (name, title, category, text, content, read_time, claps, image, cover_image, 
             parent_id, sponsor_id, ip, x, y, ref_code, is_spillover, 
             author_id, series_title, series_part, is_verified_author, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, datetime('now'))
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
    # -------------------------------------------------------------
    c.execute('''
        SELECT n.id, n.name, n.title, n.category, n.text, n.content, n.read_time, n.claps,
               n.image, n.cover_image, n.parent_id, n.x, n.y, n.ref_code, n.created_at,
               n.author_id, n.series_title, n.series_part, n.is_verified_author,
               par.name as parent_name,
               par.title as parent_title,
               auth.badge as author_badge,
               auth.username as author_username,
               (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = n.id) as reply_count
        FROM nodes n
        LEFT JOIN nodes par ON n.parent_id = par.id
        LEFT JOIN authors auth ON n.author_id = auth.id
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
        JOIN nodes n ON n.author_id = a.id
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
        WHERE n.series_title IS NOT NULL AND n.series_title != ''
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
               (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = n.id) as replies
        FROM nodes n
        ORDER BY (COALESCE(n.claps, 0) * 2 + (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = n.id) * 4) DESC
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
        
    c.execute('''
        SELECT id, name, title, category, text, read_time, claps, image, created_at, is_verified_author
        FROM nodes
        WHERE parent_id = ?
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
            WHERE LOWER(series_title) = LOWER(?)
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
    c.execute("SELECT claps FROM nodes WHERE id = ?", (node_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Node not found."}), 404
        
    new_claps = (row['claps'] or 0) + 1
    c.execute("UPDATE nodes SET claps = ? WHERE id = ?", (new_claps, node_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "node_id": node_id, "claps": new_claps})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=True)
