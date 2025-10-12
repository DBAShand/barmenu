from flask import Flask, jsonify, render_template_string
import sqlite3

app = Flask(__name__, static_folder="static")

def query_db(query, args=()):
    conn = sqlite3.connect('menu.db')
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.route('/api/beer')
def beer_api():
    return jsonify(query_db('SELECT name, abv, style FROM beer WHERE active=1 ORDER BY name'))

@app.route('/api/spirits')
def spirits_api():
    return jsonify(query_db('SELECT name, type, origin FROM spirits WHERE active=1 ORDER BY type, name'))

@app.route('/api/cocktails')
def cocktails_api():
    return jsonify(query_db('SELECT name, base, style, abv FROM cocktails WHERE active=1 ORDER BY name'))

@app.route('/')
def home():
    return render_template_string("""
    <html>
      <body style='font-family:sans-serif;text-align:center;margin-top:30vh;'>
        <h1>MizzouGlenn’s Tavern</h1>
        <p><a href="/beer">Beer on Tap</a> | <a href="/spirits">House Spirits</a></p>
      </body>
    </html>
    """)

@app.route('/beer')
def beer_page():
    return app.send_static_file('beer.html')

@app.route('/spirits')
def spirits_page():
    return app.send_static_file('spirits.html')

@app.route('/cocktails')
def cocktails_page():
    return app.send_static_file('cocktails.html')

@app.route('/seasonal')
def seasonal_page():
    return app.send_static_file('seasonal.html')

@app.route('/display')
def display_page():
    return app.send_static_file('display.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
