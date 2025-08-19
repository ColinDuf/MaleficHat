from flask import Flask, jsonify, request, render_template
import sqlite3

DB_PATH = "database.db"

app = Flask(__name__, template_folder='templates')

def query_db(query, args=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(query, args)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

@app.route('/api/members')
def api_members():
    rank = request.args.get('rank')
    if rank:
        rows = query_db("SELECT username, rank, tier FROM player WHERE rank = ?", (rank,))
    else:
        rows = query_db("SELECT username, rank, tier FROM player")
    members = [dict(r) for r in rows]
    return jsonify({"members": members, "count": len(members)})

@app.route('/api/rank_counts')
def api_rank_counts():
    rows = query_db("SELECT COALESCE(rank, 'Unranked') as rank, COUNT(*) as count FROM player GROUP BY rank")
    counts = {r['rank']: r['count'] for r in rows}
    return jsonify(counts)

@app.route('/')
def index():
    return render_template('members.html')

if __name__ == '__main__':
    app.run(debug=True)