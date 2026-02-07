import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash

bp = Blueprint(
    "inventory_admin",
    __name__,
    url_prefix="/admin/inventory"
)

DB_PATH = "menu.db"   # SAME db as app.py


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@bp.route("/")
def inventory_home():
    conn = get_db()

    beer = conn.execute(
        "SELECT * FROM beer ORDER BY active DESC, name"
    ).fetchall()

    spirits = conn.execute(
        "SELECT * FROM spirits ORDER BY active DESC, type, name"
    ).fetchall()

    cocktails = conn.execute(
        "SELECT * FROM cocktails ORDER BY active DESC, name"
    ).fetchall()

    conn.close()

    return render_template(
        "admin_inventory.html",
        beer=beer,
        spirits=spirits,
        cocktails=cocktails
    )


# ──────────────────────────────
# BEER
# ──────────────────────────────
@bp.route("/beer/save", methods=["POST"])
def beer_save():
    f = request.form

    beer_id = f.get("id")
    name = f.get("name", "").strip()
    abv = f.get("abv") or None
    style = f.get("style", "").strip()
    brewery = f.get("brewery", "").strip()
    active = 1 if f.get("active", "1") == "1" else 0

    if not name:
        flash("Beer name is required")
        return redirect(url_for("inventory_admin.inventory_home"))

    conn = get_db()

    if beer_id:
        conn.execute("""
            UPDATE beer
               SET name = ?, abv = ?, style = ?, brewery = ?, active = ?
             WHERE id = ?
        """, (name, abv, style, brewery, active, beer_id))
    else:
        conn.execute("""
            INSERT INTO beer (name, abv, style, brewery, active)
            VALUES (?, ?, ?, ?, ?)
        """, (name, abv, style, brewery, active))

    conn.commit()
    conn.close()

    return redirect(url_for("inventory_admin.inventory_home"))


# ──────────────────────────────
# SPIRITS
# ──────────────────────────────
@bp.route("/spirits/save", methods=["POST"])
def spirits_save():
    f = request.form

    spirit_id = f.get("id")
    name = f.get("name", "").strip()
    type_ = f.get("type", "").strip()
    origin = f.get("origin", "").strip()
    active = 1 if f.get("active", "1") == "1" else 0

    if not name:
        flash("Spirit name is required")
        return redirect(url_for("inventory_admin.inventory_home"))

    conn = get_db()

    if spirit_id:
        conn.execute("""
            UPDATE spirits
               SET name = ?, type = ?, origin = ?, active = ?
             WHERE id = ?
        """, (name, type_, origin, active, spirit_id))
    else:
        conn.execute("""
            INSERT INTO spirits (name, type, origin, active)
            VALUES (?, ?, ?, ?)
        """, (name, type_, origin, active))

    conn.commit()
    conn.close()

    return redirect(url_for("inventory_admin.inventory_home"))


# ──────────────────────────────
# COCKTAILS
# ──────────────────────────────
@bp.route("/cocktails/save", methods=["POST"])
def cocktails_save():
    f = request.form

    cocktail_id = f.get("id")
    name = f.get("name", "").strip()
    base = f.get("base", "").strip()
    style = f.get("style", "").strip()
    abv = f.get("abv") or None
    active = 1 if f.get("active", "1") == "1" else 0

    if not name:
        flash("Cocktail name is required")
        return redirect(url_for("inventory_admin.inventory_home"))

    conn = get_db()

    if cocktail_id:
        conn.execute("""
            UPDATE cocktails
               SET name = ?, base = ?, style = ?, abv = ?, active = ?
             WHERE id = ?
        """, (name, base, style, abv, active, cocktail_id))
    else:
        conn.execute("""
            INSERT INTO cocktails (name, base, style, abv, active)
            VALUES (?, ?, ?, ?, ?)
        """, (name, base, style, abv, active))

    conn.commit()
    conn.close()

    return redirect(url_for("inventory_admin.inventory_home"))