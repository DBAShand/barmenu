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

@app.route('/api/restaurant')
def api_restaurant():
    return jsonify(query_db(
        'SELECT name, category, description, price FROM restaurant WHERE active=1 ORDER BY category, name'
    ))

@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8">
        <title>MizzouGlenn’s Tavern</title>
        <link rel="stylesheet" href="/static/chalk.css">
      </head>
      <body style='font-family:sans-serif;text-align:center;margin-top:30vh;'>
        <h1>MizzouGlenn’s Tavern</h1>
        <p class="nav">
          <a href="/beer">Beer on Tap</a> |
          <a href="/spirits">House Spirits</a> |
          <a href="/cocktails">House Cocktails</a> |
          <a href="/seasonal">Seasonal Menu</a>
        </p>
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

@app.route('/restaurant')
def restaurant_page():
    return app.send_static_file('restaurant.html')

@app.route('/display')
def display_page():
    return app.send_static_file('display.html')

if __name__ == '__main__':
    import sys
    port = 5000
    if '--port' in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index('--port') + 1])
        except (IndexError, ValueError):
            pass
    app.run(host='0.0.0.0', port=port)