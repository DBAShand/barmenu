import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for

bp = Blueprint("inventory_admin", __name__, url_prefix="/inventory")
DB_PATH = "menu.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def form_active(value, default=1):
    """
    Accepts:
      - "1"/"0" from a select
      - "on" from a checkbox
      - missing/blank => default
    """
    if value is None or str(value).strip() == "":
        return default
    v = str(value).strip().lower()
    if v in ("1", "true", "yes", "on"):
        return 1
    if v in ("0", "false", "no", "off"):
        return 0
    return default


# ──────────────────────────────
# GET pages
# ──────────────────────────────

@bp.get("/")
@bp.get("")
def inventory_home():
    return render_template("admin_inventory_home.html")


@bp.get("/beer")
def inventory_beer():
    conn = get_db()
    beer = conn.execute("SELECT * FROM beer ORDER BY active DESC, name").fetchall()
    conn.close()
    return render_template("admin_inventory_beer.html", beer=beer)


@bp.get("/spirits")
def inventory_spirits():
    conn = get_db()
    spirits = conn.execute("SELECT * FROM spirits ORDER BY active DESC, type, name").fetchall()
    conn.close()
    return render_template("admin_inventory_spirits.html", spirits=spirits)


@bp.get("/cocktails")
def inventory_cocktails():
    conn = get_db()
    cocktails = conn.execute("SELECT * FROM cocktails ORDER BY active DESC, name").fetchall()
    conn.close()
    return render_template("admin_inventory_cocktails.html", cocktails=cocktails)


# ──────────────────────────────
# POST saves
# ──────────────────────────────

@bp.post("/beer/save")
def beer_save():
    f = request.form
    beer_id = f.get("id")

    name = (f.get("name") or "").strip()
    style = (f.get("style") or "").strip()
    abv = f.get("abv") or None
    brewery = (f.get("brewery") or "").strip()
    active = form_active(f.get("active"), default=1)

    if not name:
        # keep it simple: just bounce back
        return redirect(url_for("inventory_admin.inventory_beer"))

    conn = get_db()
    if beer_id:
        conn.execute(
            """
            UPDATE beer
               SET name = ?, abv = ?, style = ?, brewery = ?, active = ?
             WHERE id = ?
            """,
            (name, abv, style, brewery, active, beer_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO beer (name, abv, style, brewery, active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, abv, style, brewery, active),
        )

    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_beer"))


@bp.post("/spirits/save")
def spirits_save():
    f = request.form
    spirit_id = f.get("id")

    name = (f.get("name") or "").strip()
    type_ = (f.get("type") or "").strip()
    origin = (f.get("origin") or "").strip()
    active = form_active(f.get("active"), default=1)

    if not name:
        return redirect(url_for("inventory_admin.inventory_spirits"))

    conn = get_db()
    if spirit_id:
        conn.execute(
            """
            UPDATE spirits
               SET name = ?, type = ?, origin = ?, active = ?
             WHERE id = ?
            """,
            (name, type_, origin, active, spirit_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO spirits (name, type, origin, active)
            VALUES (?, ?, ?, ?)
            """,
            (name, type_, origin, active),
        )

    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_spirits"))


@bp.post("/cocktails/save")
def cocktails_save():
    f = request.form
    cocktail_id = f.get("id")

    name = (f.get("name") or "").strip()
    base = (f.get("base") or "").strip()
    style = (f.get("style") or "").strip()
    abv = f.get("abv") or None
    active = form_active(f.get("active"), default=1)

    if not name:
        return redirect(url_for("inventory_admin.inventory_cocktails"))

    conn = get_db()
    if cocktail_id:
        conn.execute(
            """
            UPDATE cocktails
               SET name = ?, base = ?, style = ?, abv = ?, active = ?
             WHERE id = ?
            """,
            (name, base, style, abv, active, cocktail_id),
        )
    else:
        conn.execute(
            """
            INSERT INTO cocktails (name, base, style, abv, active)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, base, style, abv, active),
        )

    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_cocktails"))