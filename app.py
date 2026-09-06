import sqlite3
import secrets
import html
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_PATH = 'grid_data.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
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
        ('ref_code', 'TEXT')
    ]
    for col_name, col_type in missing_cols:
        if col_name not in columns:
            c.execute(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()

init_db()

def calculate_node_coordinates(c, parent_id):
    """
    Calculates collision-free coordinates for spatial branching.
    - If parent_id is None: Placed along top row (y = 150) as a new main edition pillar.
    - If parent_id is set: Placed on child row (parent.y + 340) centered beneath parent,
      symmetrically branching outward with collision avoidance.
    """
    # 1. New Root Newsletter Edition
    if not parent_id:
        c.execute("SELECT MAX(x) FROM nodes WHERE parent_id IS NULL")
        max_root_x = c.fetchone()[0]
        if max_root_x:
            return max_root_x + 2200, 150
        return 3000, 150

    # 2. Branching Reply to an existing article or reply
    c.execute("SELECT x, y FROM nodes WHERE id = ?", (parent_id,))
    parent_row = c.fetchone()
    if not parent_row:
        return 3000, 450
        
    px, py = parent_row[0], parent_row[1]
    ny = py + 340
    
    c.execute("SELECT COUNT(*) FROM nodes WHERE parent_id = ?", (parent_id,))
    child_count = c.fetchone()[0]
    
    # Symmetrical alternating spread: [0, +290, -290, +580, -580, +870, -870, ...]
    offsets = [0, 290, -290, 580, -580, 870, -870, 1160, -1160, 1450, -1450]
    if child_count < len(offsets):
        ideal_offset = offsets[child_count]
    else:
        direction = 1 if child_count % 2 == 1 else -1
        ideal_offset = direction * ((child_count + 1) // 2) * 290
        
    ideal_x = px + ideal_offset
    
    # Collision detection with all nodes at row ny
    c.execute("SELECT x FROM nodes WHERE y = ? ORDER BY x ASC", (ny,))
    existing_xs = [r[0] for r in c.fetchall()]
    
    candidate_x = ideal_x
    step = 0
    while any(abs(candidate_x - ex) < 270 for ex in existing_xs) or candidate_x < 200:
        step += 1
        direction = 1 if step % 2 == 1 else -1
        candidate_x = ideal_x + (direction * ((step + 1) // 2) * 60)
        if candidate_x < 200:
            candidate_x = 200 + step * 60
            
    return candidate_x, ny

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/nodes', methods=['GET', 'POST'])
def handle_nodes():
    conn = get_db()
    c = conn.cursor()
    
    # -------------------------------------------------------------
    # POST: Publish a New Article / Newsletter Edition or Reply Node
    # -------------------------------------------------------------
    if request.method == 'POST':
        data = request.json or {}
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        
        # Anti-spam IP check
        c.execute("SELECT count(*) FROM nodes WHERE ip = ? AND created_at > datetime('now', '-1 hour')", (ip,))
        recent_ip_count = c.fetchone()[0]
        if recent_ip_count >= 15:
            conn.close()
            return jsonify({"error": "Shield active: Please wait a moment before publishing more articles."}), 429
            
        raw_name = (data.get('name') or '').strip()
        raw_title = (data.get('title') or '').strip()
        raw_content = (data.get('content') or '').strip()
        raw_category = (data.get('category') or 'Perspective').strip()
        raw_image = (data.get('image') or '').strip()
        raw_cover = (data.get('cover_image') or '').strip()
        parent_id = data.get('parent_id')
        
        if parent_id in ('', 'null', 0, '0', None):
            parent_id = None
        else:
            try:
                parent_id = int(parent_id)
            except (ValueError, TypeError):
                parent_id = None

        if not raw_title:
            conn.close()
            return jsonify({"error": "Please provide an Article Headline / Title."}), 400
        if not raw_name:
            raw_name = "Anonymous Thinker"
            
        # Clean text
        title = html.escape(raw_title[:100])
        name = html.escape(raw_name[:40])
        category = html.escape(raw_category[:25])
        content = raw_content[:15000] # Cap longform to 15KB
        
        # Excerpt generation
        clean_preview = re.sub(r'[#*`_>\[\]]', '', content).strip()
        text = html.escape(clean_preview[:130] + ('...' if len(clean_preview) > 130 else ''))
        if not text:
            text = title
            
        # Estimated reading time
        words = len(content.split())
        read_time = f"{max(1, words // 160)} min read" if words > 30 else "1 min read"
        
        # Avatar generation
        if not raw_image or len(raw_image) < 10:
            avatar_bg = secrets.choice(['2563eb', '7c3aed', '059669', 'd97706', 'dc2626'])
            image = f"https://api.dicebear.com/7.x/bottts/svg?seed={name}&backgroundColor={avatar_bg}"
        else:
            image = raw_image
            
        # Cover image preset fallback
        if not raw_cover:
            covers = [
                "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800&auto=format&fit=crop&q=80",
                "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=800&auto=format&fit=crop&q=80",
                "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&auto=format&fit=crop&q=80",
                "https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=800&auto=format&fit=crop&q=80",
                "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&auto=format&fit=crop&q=80",
                "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&auto=format&fit=crop&q=80"
            ]
            cover_image = secrets.choice(covers)
        else:
            cover_image = raw_cover

        # Calculate position
        nx, ny = calculate_node_coordinates(c, parent_id)
        ref_code = secrets.token_hex(4)
        
        c.execute('''
            INSERT INTO nodes 
            (name, title, category, text, content, read_time, claps, image, cover_image, parent_id, sponsor_id, ip, x, y, ref_code, is_spillover, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
        ''', (name, title, category, text, content, read_time, 0, image, cover_image, parent_id, parent_id, ip, nx, ny, ref_code))
        
        new_id = c.lastrowid
        conn.commit()
        
        # Query parent meta for client feedback
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
               par.name as parent_name,
               par.title as parent_title,
               (SELECT COUNT(*) FROM nodes r WHERE r.parent_id = n.id) as reply_count
        FROM nodes n
        LEFT JOIN nodes par ON n.parent_id = par.id
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
            "x": r['x'],
            "y": r['y'],
            "depth": depth,
            "ref_code": r['ref_code'],
            "created_at": created_str,
            "reply_count": r['reply_count']
        })
        
    # Top Writers Leaderboard (Ranked by Total Claps + Articles)
    c.execute('''
        SELECT name, image, 
               COUNT(id) as article_count, 
               COALESCE(SUM(claps), 0) as total_claps,
               MIN(id) as representative_id
        FROM nodes 
        GROUP BY name 
        ORDER BY total_claps DESC, article_count DESC 
        LIMIT 10
    ''')
    top_authors = [
        {
            "name": r[0],
            "image": r[1],
            "article_count": r[2],
            "total_claps": r[3],
            "id": r[4]
        }
        for r in c.fetchall()
    ]
    
    # Trending Articles (Ranked by Claps * 2 + Reply Count * 3)
    c.execute('''
        SELECT n.id, n.title, n.name, n.category, n.claps,
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
            "replies": r[5] or 0
        }
        for r in c.fetchall()
    ]

    stats = {
        "total_nodes": len(nodes),
        "total_editions": total_editions,
        "total_replies": total_replies,
        "total_claps": total_claps
    }
    
    conn.close()
    return jsonify({
        "nodes": nodes,
        "leaders": top_authors,
        "trending": trending,
        "stats": stats
    })

# -------------------------------------------------------------
# GET: Retrieve single node with full replies and parent metadata
# -------------------------------------------------------------
@app.route('/api/nodes/<int:node_id>', methods=['GET'])
def get_node_details(node_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT n.id, n.name, n.title, n.category, n.text, n.content, n.read_time, n.claps,
               n.image, n.cover_image, n.parent_id, n.x, n.y, n.ref_code, n.created_at,
               par.name as parent_name,
               par.title as parent_title
        FROM nodes n
        LEFT JOIN nodes par ON n.parent_id = par.id
        WHERE n.id = ?
    ''', (node_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Article node not found"}), 404
        
    # Get all direct replies to this node
    c.execute('''
        SELECT id, name, title, category, text, read_time, claps, image, created_at
        FROM nodes
        WHERE parent_id = ?
        ORDER BY id ASC
    ''', (node_id,))
    replies = [dict(r) for r in c.fetchall()]
    
    node = dict(row)
    node['replies'] = replies
    node['reply_count'] = len(replies)
    conn.close()
    return jsonify({"node": node})

# -------------------------------------------------------------
# POST: Clap / Upvote an Article or Reply Node
# -------------------------------------------------------------
@app.route('/api/nodes/<int:node_id>/clap', methods=['POST'])
def clap_node(node_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT claps FROM nodes WHERE id = ?", (node_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Node not found"}), 404
        
    new_claps = (row['claps'] or 0) + 1
    c.execute("UPDATE nodes SET claps = ? WHERE id = ?", (new_claps, node_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "node_id": node_id, "claps": new_claps})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=True)
