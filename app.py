from flask import Flask, jsonify, render_template, render_template_string
import sqlite3
import sys

app = Flask(__name__, static_folder="static", template_folder="templates")

# ──────────────────────────────
# Helper for DB access
# ──────────────────────────────
def query_db(query, args=()):
    conn = sqlite3.connect('menu.db')
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, args).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ──────────────────────────────
# API endpoints
# ──────────────────────────────
@app.route('/api/beer')
def beer_api():
    # Include brewery now that schema has changed
    beers = query_db('SELECT name, abv, style, brewery FROM beer WHERE active=1 ORDER BY name')
    # Ensure abv is always a float (avoid JS errors on null)
    for b in beers:
        b['abv'] = float(b['abv']) if b['abv'] is not None else 0.0
    return jsonify(beers)

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

# ──────────────────────────────
# Static HTML pages
# ──────────────────────────────
@app.route('/')
def home():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8">
        <title>MizzouGlenn’s Tavern</title>
        <--<link rel="stylesheet" href="/static/chalk.css">-->
        <link rel="stylesheet" href="/static/main.css">                         
      </head>
      <body style='font-family:sans-serif;text-align:center;margin-top:30vh;'>
        <h1>MizzouGlenn’s Tavern</h1>
        <p class="nav">
          <a href="/beer">Beer on Tap</a> |
          <a href="/spirits">House Spirits</a> |
          <a href="/cocktails">House Cocktails</a> |
          <a href="/seasonal">Seasonal Menu</a> |
          <a href="/menu">Rotating Spirits</a> |
          <a href="/beer/menu">Rotating Beer</a>                    
        </p>
      </body>
    </html>
    """)

@app.route('/beer')
def beer_page():
    return app.send_static_file('beer.html')


@app.route('/beer/menu')
def beer_menu_page():
    return app.send_static_file('beer_menu.html')

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

# ──────────────────────────────
# Rotating Beer Menu
# ──────────────────────────────
@app.route('/beer/menu')
@app.route('/beer/menu/<int:page>')
def beer_menu(page: int = 1):
    """Rotating beer menu with pagination."""
    per_page = 15
    offset = (page - 1) * per_page

    conn = sqlite3.connect('menu.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    total_beers = cur.execute("SELECT COUNT(*) as cnt FROM beer WHERE active=1").fetchone()["cnt"]
    rows = cur.execute(
        "SELECT name, style, abv FROM beer WHERE active=1 ORDER BY name LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()
    conn.close()

    total_pages = max(1, (total_beers + per_page - 1) // per_page)
    next_page = 1 if page >= total_pages else page + 1
    rotate = total_pages > 1  # only rotate if more than one page

    return render_template(
        "beer_menu.html",
        rows=rows,
        page=page,
        next_page=next_page,
        total_pages=total_pages,
        rotate=rotate
    )

# ──────────────────────────────
# Rotating Spirits Display
# ──────────────────────────────
SPIRIT_GROUPS = {
  "Bourbon": ["bourbon"],
  "Rye": ["Rye"],
  "Scotch / Whiskey": ["whiskey", "scotch"],
  "Gin": ["gin"],
  "Vodka": ["vodka"],
  "Rum": ["rum"],
  "Liqueurs & Cordials & Aperitifs & Absinthe": ["liqueur", "cream liqueur", "orange liqueur", "herbal liqueur", "elderflower liqueur","aperitif", "absinthe"],
  "Tequila / Mezcal": ["Tequila", "Mezcal"],
}

def get_spirits(types):
    conn = sqlite3.connect('menu.db')
    conn.row_factory = sqlite3.Row
    placeholders = ','.join(['?'] * len(types))
    rows = conn.execute(
        f"SELECT name, origin FROM spirits WHERE active=1 AND type IN ({placeholders}) ORDER BY name",
        types
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.route('/menu/<group_name>')
def show_group(group_name):
    if group_name not in SPIRIT_GROUPS:
        return "Unknown group", 404

    rows = get_spirits(SPIRIT_GROUPS[group_name])
    group_names = list(SPIRIT_GROUPS.keys())
    next_group = group_names[(group_names.index(group_name) + 1) % len(group_names)]

    return render_template('menu.html',
                           group_name=group_name,
                           rows=rows,
                           next_group=next_group)

@app.route('/menu')
def menu_home():
    first = list(SPIRIT_GROUPS.keys())[0]
    return f'<meta http-equiv="refresh" content="0;url=/menu/{first}">'

# ──────────────────────────────
# Run
# ──────────────────────────────
if __name__ == '__main__':
    port = 5000
    if '--port' in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index('--port') + 1])
        except (IndexError, ValueError):
            pass
    app.run(host='0.0.0.0', port=port)