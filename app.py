import sqlite3
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
DB_FILE = 'grid_data.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS nodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, text TEXT, image TEXT,
        parent_id INTEGER, ip TEXT, x INTEGER, y INTEGER)''')
    c.execute("SELECT count(*) FROM nodes")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO nodes (name, text, image, parent_id, ip, x, y) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                  ('Admin', 'Infinity Grid Core', 'https://upload.wikimedia.org/wikipedia/commons/8/89/Portrait_Placeholder.png', None, '127.0.0.1', 1925, 200))
    conn.commit()
    conn.close()
init_db()

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/nodes', methods=['GET', 'POST'])
def handle_nodes():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    if request.method == 'POST':
        data = request.json
        ip = request.remote_addr
        
        c.execute("SELECT count(*) FROM nodes WHERE ip = ?", (ip,))
        if c.fetchone()[0] >= 10: return jsonify({"error": "Spam Detected: Too many accounts from this device!"}), 400
        
        c.execute("SELECT count(*) FROM nodes")
        total_users = c.fetchone()[0]
        
        raw_pid = data.get('ref_id')
        pid = int(raw_pid) if raw_pid else 1
        
        if total_users >= 100 and not raw_pid:
            return jsonify({"error": "Public joining is closed! You need a referral link."}), 400
            
        c.execute("SELECT x, y FROM nodes WHERE id = ?", (pid,))
        parent = c.fetchone()
        if not parent: return jsonify({"error": "Invalid Referral Link!"}), 400
        px, py = parent
        
        c.execute("SELECT count(*) FROM nodes WHERE parent_id = ?", (pid,))
        child_count = c.fetchone()[0]
        
        row = child_count // 5
        col = child_count % 5
        nx = px + (col * 240) - 480
        ny = py + 300 + (row * 280)
        
        c.execute("INSERT INTO nodes (name, text, image, parent_id, ip, x, y) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (data['name'], data['text'], data['image'], pid, ip, nx, ny))
        conn.commit(); conn.close()
        return jsonify({"status": "success"})
        
    c.execute("SELECT * FROM nodes")
    nodes = [{"id": r[0], "name": r[1], "text": r[2], "image": r[3], "parent_id": r[4], "x": r[6], "y": r[7]} for r in c.fetchall()]
    
    c.execute('''SELECT p.name, COUNT(c.id) as ref_count FROM nodes c 
                 JOIN nodes p ON c.parent_id = p.id 
                 GROUP BY p.id ORDER BY ref_count DESC LIMIT 5''')
    leaders = [{"name": r[0], "count": r[1]} for r in c.fetchall()]
    conn.close()
    return jsonify({"nodes": nodes, "leaders": leaders})

if __name__ == '__main__': app.run(host='0.0.0.0', port=9999, debug=True)
