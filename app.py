import sqlite3
import secrets
import html
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_FILE = 'grid_data.db'

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create nodes table with full dual-node and security tracking
    c.execute('''CREATE TABLE IF NOT EXISTS nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        text TEXT NOT NULL,
        image TEXT,
        parent_id INTEGER,
        sponsor_id INTEGER,
        ip TEXT,
        x INTEGER,
        y INTEGER,
        ref_code TEXT UNIQUE,
        is_spillover INTEGER DEFAULT 0,
        created_at DATETIME
    )''')
    
    # Safe migrations for existing databases
    c.execute("PRAGMA table_info(nodes)")
    columns = [row[1] for row in c.fetchall()]
    if 'is_spillover' not in columns:
        c.execute("ALTER TABLE nodes ADD COLUMN is_spillover INTEGER DEFAULT 0")
    if 'created_at' not in columns:
        c.execute("ALTER TABLE nodes ADD COLUMN created_at DATETIME")
        c.execute("UPDATE nodes SET created_at = datetime('now') WHERE created_at IS NULL")
    if 'sponsor_id' not in columns:
        c.execute("ALTER TABLE nodes ADD COLUMN sponsor_id INTEGER")
    if 'ref_code' not in columns:
        c.execute("ALTER TABLE nodes ADD COLUMN ref_code TEXT")
        
    # Populate initial root Genesis node if empty
    c.execute("SELECT count(*) FROM nodes")
    if c.fetchone()[0] == 0:
        admin_ref = secrets.token_hex(4)
        c.execute('''INSERT INTO nodes 
            (name, text, image, parent_id, sponsor_id, ip, x, y, ref_code, is_spillover, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
            ('Nexus-Core', 'BlockTree Genesis Matrix', 
             'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=150&auto=format&fit=crop&q=80',
             None, None, '127.0.0.1', 3000, 150, admin_ref, 0))
    else:
        # If root node exists but missing ref_code or created_at
        c.execute("SELECT id, ref_code, created_at FROM nodes WHERE parent_id IS NULL LIMIT 1")
        root = c.fetchone()
        if root:
            if not root[1]:
                c.execute("UPDATE nodes SET ref_code = ? WHERE id = ?", (secrets.token_hex(4), root[0]))
            if not root[2]:
                c.execute("UPDATE nodes SET created_at = datetime('now') WHERE id = ?", (root[0],))
            
    conn.commit()
    conn.close()

init_db()

def calculate_node_coordinates(c, parent_id, child_index):
    """
    Calculates intelligent, collision-free (x, y) coordinates for a 1x5 matrix child.
    Guarantees positive, well-spaced coordinates that never overlap or escape canvas.
    """
    c.execute("SELECT x, y, parent_id FROM nodes WHERE id = ?", (parent_id,))
    parent_row = c.fetchone()
    if not parent_row:
        return 3000, 450
        
    px, py, grand_parent_id = parent_row[0], parent_row[1], parent_row[2]
    ny = py + 300
    
    # If parent is root (grand_parent_id is None): 5 wide branches
    if grand_parent_id is None or parent_id == 1:
        spacing = 750
    else:
        spacing = 180
        
    offset_multiplier = child_index - 2  # [-2, -1, 0, 1, 2]
    ideal_x = px + (offset_multiplier * spacing)
    
    # Check for horizontal collisions with any other nodes at the same Y level
    c.execute("SELECT x FROM nodes WHERE y = ? ORDER BY x ASC", (ny,))
    existing_xs = [r[0] for r in c.fetchall()]
    
    candidate_x = ideal_x
    step = 0
    while any(abs(candidate_x - ex) < 170 for ex in existing_xs) or candidate_x < 200:
        step += 1
        direction = 1 if step % 2 == 1 else -1
        candidate_x = ideal_x + (direction * (step // 2 + 1) * 60)
        if candidate_x < 200:
            candidate_x = 200 + step * 60
        
    return candidate_x, ny

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/check-ref/<ref_code>', methods=['GET'])
def check_ref(ref_code):
    """Instant lookup to validate a referral link and display sponsor details."""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT n.id, n.name, n.text, n.image, n.ref_code,
               (SELECT COUNT(*) FROM nodes s WHERE s.sponsor_id = n.id) as ref_count
        FROM nodes n 
        WHERE LOWER(n.ref_code) = LOWER(?)
    ''', (ref_code.strip(),))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify({
            "valid": True,
            "sponsor": {
                "id": row['id'],
                "name": row['name'],
                "text": row['text'],
                "image": row['image'],
                "ref_code": row['ref_code'],
                "direct_referrals": row['ref_count']
            }
        })
    return jsonify({"valid": False, "error": "Referral code not found in matrix"}), 404

@app.route('/api/nodes', methods=['GET', 'POST'])
def handle_nodes():
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'POST':
        data = request.json or {}
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        
        # 1. Anti-Spam Security: Check accounts per IP
        c.execute("SELECT count(*) FROM nodes WHERE ip = ?", (ip,))
        ip_count = c.fetchone()[0]
        if ip_count >= 10:
            conn.close()
            return jsonify({
                "error": "🛡️ Anti-Spam Triggered: Maximum 10 node registrations reached from this IP address/device."
            }), 429
            
        # 2. Scarcity & FOMO Check: Public Genesis Phase (1-100) vs Invite-Only
        c.execute("SELECT count(*) FROM nodes")
        total_users = c.fetchone()[0]
        
        req_ref = (data.get('ref_id') or '').strip()
        
        if total_users >= 100 and not req_ref:
            conn.close()
            return jsonify({
                "error": "🔒 Matrix Locked: The initial 100 Genesis public slots are completely full. An official invitation link from an existing member is now strictly required."
            }), 403
            
        # 3. Dual-Node Tracking: Resolve Sponsor ID
        sponsor_name = "Genesis Root"
        if req_ref:
            c.execute("SELECT id, name FROM nodes WHERE LOWER(ref_code) = LOWER(?)", (req_ref,))
            user_row = c.fetchone()
            if not user_row:
                conn.close()
                return jsonify({"error": "Invalid Referral Code: The provided invite code does not exist in the matrix."}), 400
            sponsor_id = user_row['id']
            sponsor_name = user_row['name']
        else:
            # Fallback to root node for early Genesis public entrants
            c.execute("SELECT id, name FROM nodes WHERE parent_id IS NULL LIMIT 1")
            root_row = c.fetchone()
            sponsor_id = root_row['id']
            sponsor_name = root_row['name']
            
        # 4. 1x5 Auto-Spillover Matrix Placement via BFS
        # Breadth-First Search queue starting at sponsor's subtree
        queue = [sponsor_id]
        pid = sponsor_id
        while queue:
            curr = queue.pop(0)
            c.execute("SELECT id FROM nodes WHERE parent_id = ? ORDER BY id ASC", (curr,))
            children = [row[0] for row in c.fetchall()]
            if len(children) < 5:
                pid = curr
                break
            queue.extend(children)
            
        # Dual-node resolution: Is this a spillover placement?
        is_spillover = 1 if (pid != sponsor_id) else 0
        
        # 5. Position & Coordinate Assignment
        c.execute("SELECT count(*) FROM nodes WHERE parent_id = ?", (pid,))
        child_count = c.fetchone()[0]
        nx, ny = calculate_node_coordinates(c, pid, child_count)
        
        # 6. Input Sanitization & Payload Validation
        raw_name = data.get('name', '').strip()
        raw_text = data.get('text', '').strip()
        raw_image = data.get('image', '').strip()
        
        if not raw_name or not raw_text:
            conn.close()
            return jsonify({"error": "Please enter both a Name and Tagline!"}), 400
            
        name = html.escape(raw_name[:40])
        text = html.escape(raw_text[:60])
        
        # Default avatar generator if none provided or invalid
        if not raw_image or len(raw_image) < 10:
            avatar_bg = secrets.choice(['2563eb', '7c3aed', '059669', 'd97706', 'dc2626'])
            image = f"https://api.dicebear.com/7.x/bottts/svg?seed={name}&backgroundColor={avatar_bg}"
        else:
            if len(raw_image) > 3 * 1024 * 1024:
                conn.close()
                return jsonify({"error": "Uploaded image is too large (Max 2MB)."}), 400
            image = raw_image
            
        # 7. Generate Cryptographic 8-Character Hex Token
        new_ref = secrets.token_hex(4)
        while True:
            c.execute("SELECT id FROM nodes WHERE ref_code = ?", (new_ref,))
            if not c.fetchone():
                break
            new_ref = secrets.token_hex(4)
            
        # Insert new node
        c.execute('''INSERT INTO nodes 
            (name, text, image, parent_id, sponsor_id, ip, x, y, ref_code, is_spillover, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))''',
            (name, text, image, pid, sponsor_id, ip, nx, ny, new_ref, is_spillover))
        new_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            "status": "success",
            "node_id": new_id,
            "ref_code": new_ref,
            "is_spillover": bool(is_spillover),
            "sponsor_name": sponsor_name,
            "placed_under_id": pid
        })
        
    # GET: Retrieve entire matrix, stats, and leaderboard
    c.execute('''
        SELECT n.id, n.name, n.text, n.image, n.parent_id, n.sponsor_id, n.x, n.y, 
               n.ref_code, n.is_spillover, n.created_at,
               (SELECT COUNT(*) FROM nodes d WHERE d.sponsor_id = n.id) as direct_refs,
               (SELECT COUNT(*) FROM nodes ch WHERE ch.parent_id = n.id) as direct_children,
               sp.name as sponsor_name,
               par.name as parent_name
        FROM nodes n
        LEFT JOIN nodes sp ON n.sponsor_id = sp.id
        LEFT JOIN nodes par ON n.parent_id = par.id
        ORDER BY n.id ASC
    ''')
    raw_nodes = c.fetchall()
    
    nodes = []
    for r in raw_nodes:
        depth = max(0, (r['y'] - 150) // 300)
        created_str = r['created_at'] or datetime.now().strftime("%Y-%m-%d %H:%M")
        nodes.append({
            "id": r['id'],
            "name": r['name'],
            "text": r['text'],
            "image": r['image'],
            "parent_id": r['parent_id'],
            "sponsor_id": r['sponsor_id'],
            "sponsor_name": r['sponsor_name'] or "Root Core",
            "parent_name": r['parent_name'] or "Root Core",
            "x": r['x'],
            "y": r['y'],
            "ref_code": r['ref_code'],
            "is_spillover": bool(r['is_spillover']),
            "created_at": created_str,
            "direct_refs": r['direct_refs'],
            "direct_children": r['direct_children'],
            "depth": depth
        })
        
    # Top Referrers Leaderboard (Ranked by Sponsor ID credits)
    c.execute('''
        SELECT p.id, p.name, p.image, p.ref_code, COUNT(c.id) as ref_count 
        FROM nodes c 
        JOIN nodes p ON c.sponsor_id = p.id 
        GROUP BY p.id 
        ORDER BY ref_count DESC, p.id ASC 
        LIMIT 10
    ''')
    leaders = [
        {
            "id": r[0],
            "name": r[1],
            "image": r[2],
            "ref_code": r[3],
            "count": r[4]
        }
        for r in c.fetchall()
    ]
    
    # System Stats & Scarcity Data
    total_users = len(nodes)
    genesis_slots_left = max(0, 100 - total_users)
    is_invite_only = total_users >= 100
    
    c.execute("SELECT count(*) FROM nodes WHERE is_spillover = 1")
    total_spillovers = c.fetchone()[0]
    
    max_depth = max([n['depth'] for n in nodes], default=0)
    
    stats = {
        "total_users": total_users,
        "genesis_limit": 100,
        "genesis_slots_left": genesis_slots_left,
        "is_invite_only": is_invite_only,
        "total_spillovers": total_spillovers,
        "max_depth": max_depth
    }
    
    conn.close()
    return jsonify({
        "nodes": nodes,
        "leaders": leaders,
        "stats": stats
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9999, debug=True)
