import os
import sqlite3
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint("inventory_admin", __name__, url_prefix="/inventory")
DB_PATH = "menu.db"
PASSWORD_FILE = Path(__file__).resolve().parent / ".admin_password"


def _stored_hash():
    if PASSWORD_FILE.exists():
        return PASSWORD_FILE.read_text(encoding="utf-8").strip()
    return ""


def _password_is_set():
    return bool(os.environ.get("ADMIN_PASSWORD") or _stored_hash())


def _password_ok(password):
    env = os.environ.get("ADMIN_PASSWORD")
    if env:
        return password == env
    stored = _stored_hash()
    if not stored:
        return False
    return check_password_hash(stored, password)


@bp.before_request
def require_admin():
    if request.endpoint in ("inventory_admin.login", "inventory_admin.setup"):
        return None
    if session.get("admin"):
        return None
    return redirect(url_for("inventory_admin.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not _password_is_set():
        return redirect(url_for("inventory_admin.setup"))
    if request.method == "POST":
        if _password_ok(request.form.get("password") or ""):
            session["admin"] = True
            return redirect(url_for("inventory_admin.inventory_home"))
        flash("Nope. Wrong password.")
    return render_template("admin_login.html", setup=False)


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    if _password_is_set():
        return redirect(url_for("inventory_admin.login"))
    if request.method == "POST":
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""
        if len(password) < 4:
            flash("Use at least 4 characters.")
        elif password != confirm:
            flash("Passwords did not match.")
        else:
            PASSWORD_FILE.write_text(
                generate_password_hash(password, method="pbkdf2:sha256"),
                encoding="utf-8",
            )
            session["admin"] = True
            return redirect(url_for("inventory_admin.inventory_home"))
    return render_template("admin_login.html", setup=True)


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("inventory_admin.login"))


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


def _is_wildcard(q):
    return (q or "").strip().lower() in {"all", "*", "%"}


def _search_state():
    q = (request.args.get("q") or "").strip()
    type_filter = (request.args.get("type") or "").strip()
    if _is_wildcard(q):
        q = ""
    if _is_wildcard(type_filter):
        type_filter = ""
    return q, type_filter


# ──────────────────────────────
# GET pages
# ──────────────────────────────

@bp.get("/")
@bp.get("")
def inventory_home():
    return render_template("admin_inventory_home.html")


@bp.get("/beer")
def inventory_beer():
    q, type_filter = _search_state()

    conn = get_db()
    types = _lookup_names(conn, "beer_styles", "SELECT DISTINCT style FROM beer WHERE style IS NOT NULL AND TRIM(style) != ''")
    sql = "SELECT * FROM beer WHERE 1=1"
    args = []
    if q:
        like = f"%{q}%"
        sql += " AND (name LIKE ? COLLATE NOCASE OR style LIKE ? COLLATE NOCASE OR brewery LIKE ? COLLATE NOCASE)"
        args.extend([like, like, like])
    if type_filter:
        sql += " AND style = ?"
        args.append(type_filter)
    sql += " ORDER BY active DESC, name"
    beer = conn.execute(sql, args).fetchall()
    conn.close()

    type_exists = (not q) or any(t.lower() == q.lower() for t in types)
    return render_template(
        "admin_inventory_beer.html",
        beer=beer,
        types=types,
        q=q,
        type_filter=type_filter,
        type_exists=type_exists,
    )


def _ensure_lookup(conn, table, seed_select):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(f"INSERT OR IGNORE INTO {table} (name) {seed_select}")
    conn.commit()


def _lookup_names(conn, table, seed_select):
    _ensure_lookup(conn, table, seed_select)
    return [
        r["name"]
        for r in conn.execute(
            f"SELECT name FROM {table} ORDER BY name COLLATE NOCASE"
        ).fetchall()
    ]


def _ensure_spirit_types(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spirit_types (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO spirit_types (name)
        SELECT DISTINCT type FROM spirits
         WHERE type IS NOT NULL AND TRIM(type) != ''
        """
    )
    conn.commit()


def _spirit_type_names(conn):
    _ensure_spirit_types(conn)
    return [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM spirit_types ORDER BY name COLLATE NOCASE"
        ).fetchall()
    ]


TYPE_KINDS = {
    "beer": {
        "label": "Beer styles",
        "lookup": "beer_styles",
        "seed": "SELECT DISTINCT style FROM beer WHERE style IS NOT NULL AND TRIM(style) != ''",
        "item_updates": [("beer", "style")],
    },
    "spirits": {
        "label": "Spirit types",
        "lookup": "spirit_types",
        "seed": "SELECT DISTINCT type FROM spirits WHERE type IS NOT NULL AND TRIM(type) != ''",
        "item_updates": [("spirits", "type")],
    },
    "cocktails": {
        "label": "Cocktail bases / styles",
        "lookup": "cocktail_types",
        "seed": """
            SELECT DISTINCT base FROM cocktails WHERE base IS NOT NULL AND TRIM(base) != ''
            UNION
            SELECT DISTINCT style FROM cocktails WHERE style IS NOT NULL AND TRIM(style) != ''
        """,
        "item_updates": [("cocktails", "base"), ("cocktails", "style")],
    },
}


def _kind_spec(kind):
    return TYPE_KINDS.get(kind)


def _type_usage(conn, spec, name):
    total = 0
    for table, col in spec["item_updates"]:
        total += conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} = ?",
            (name,),
        ).fetchone()[0]
    return total


@bp.get("/types")
def inventory_types():
    conn = get_db()
    groups = []
    for kind, spec in TYPE_KINDS.items():
        _ensure_lookup(conn, spec["lookup"], spec["seed"])
        rows = []
        for row in conn.execute(
            f"SELECT name FROM {spec['lookup']} ORDER BY name COLLATE NOCASE"
        ).fetchall():
            rows.append({"name": row["name"], "used": _type_usage(conn, spec, row["name"])})
        groups.append({"kind": kind, "label": spec["label"], "rows": rows})
    conn.close()
    return render_template("admin_types.html", groups=groups)


@bp.post("/types/add")
def types_add():
    kind = (request.form.get("kind") or "").strip()
    name = (request.form.get("name") or "").strip()
    spec = _kind_spec(kind)
    if not spec or not name:
        flash("Type name is required.")
        return redirect(url_for("inventory_admin.inventory_types"))
    conn = get_db()
    _ensure_lookup(conn, spec["lookup"], spec["seed"])
    conn.execute(f"INSERT OR IGNORE INTO {spec['lookup']} (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    flash(f"Added “{name}”.")
    return redirect(url_for("inventory_admin.inventory_types"))


@bp.post("/types/save")
def types_save():
    kind = (request.form.get("kind") or "").strip()
    old = (request.form.get("old") or "").strip()
    new = (request.form.get("name") or "").strip()
    spec = _kind_spec(kind)
    if not spec or not old or not new:
        flash("Old and new type names are required.")
        return redirect(url_for("inventory_admin.inventory_types"))
    conn = get_db()
    _ensure_lookup(conn, spec["lookup"], spec["seed"])
    for table, col in spec["item_updates"]:
        conn.execute(f"UPDATE {table} SET {col} = ? WHERE {col} = ?", (new, old))
    conn.execute(f"INSERT OR IGNORE INTO {spec['lookup']} (name) VALUES (?)", (new,))
    if old != new:
        conn.execute(f"DELETE FROM {spec['lookup']} WHERE name = ?", (old,))
    conn.commit()
    conn.close()
    if old == new:
        flash("No change.")
    else:
        flash(f"Renamed “{old}” to “{new}” on the lookup and every matching item.")
    return redirect(url_for("inventory_admin.inventory_types"))


@bp.post("/types/delete")
def types_delete():
    kind = (request.form.get("kind") or "").strip()
    name = (request.form.get("name") or "").strip()
    spec = _kind_spec(kind)
    if not spec or not name:
        return redirect(url_for("inventory_admin.inventory_types"))
    conn = get_db()
    _ensure_lookup(conn, spec["lookup"], spec["seed"])
    used = _type_usage(conn, spec, name)
    if used:
        conn.close()
        flash(f"Cannot delete “{name}”: {used} item(s) still use it. Rename those first, or rename this type to merge.")
        return redirect(url_for("inventory_admin.inventory_types"))
    conn.execute(f"DELETE FROM {spec['lookup']} WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    flash(f"Deleted type “{name}”.")
    return redirect(url_for("inventory_admin.inventory_types"))


@bp.get("/spirits")
def inventory_spirits():
    q, type_filter = _search_state()

    conn = get_db()
    types = _spirit_type_names(conn)
    sql = "SELECT * FROM spirits WHERE 1=1"
    args = []
    if q:
        like = f"%{q}%"
        sql += " AND (name LIKE ? COLLATE NOCASE OR type LIKE ? COLLATE NOCASE OR origin LIKE ? COLLATE NOCASE)"
        args.extend([like, like, like])
    if type_filter:
        sql += " AND type = ?"
        args.append(type_filter)
    sql += " ORDER BY active DESC, type, name"
    spirits = conn.execute(sql, args).fetchall()
    conn.close()

    type_exists = (not q) or any(t.lower() == q.lower() for t in types)
    return render_template(
        "admin_inventory_spirits.html",
        spirits=spirits,
        types=types,
        q=q,
        type_filter=type_filter,
        type_exists=type_exists,
    )


@bp.get("/cocktails")
def inventory_cocktails():
    q, type_filter = _search_state()

    conn = get_db()
    types = _lookup_names(
        conn,
        "cocktail_types",
        """
        SELECT DISTINCT base FROM cocktails WHERE base IS NOT NULL AND TRIM(base) != ''
        UNION
        SELECT DISTINCT style FROM cocktails WHERE style IS NOT NULL AND TRIM(style) != ''
        """,
    )
    sql = "SELECT * FROM cocktails WHERE 1=1"
    args = []
    if q:
        like = f"%{q}%"
        sql += " AND (name LIKE ? COLLATE NOCASE OR base LIKE ? COLLATE NOCASE OR style LIKE ? COLLATE NOCASE)"
        args.extend([like, like, like])
    if type_filter:
        sql += " AND (base = ? OR style = ?)"
        args.extend([type_filter, type_filter])
    sql += " ORDER BY active DESC, name"
    cocktails = conn.execute(sql, args).fetchall()
    conn.close()

    type_exists = (not q) or any(t.lower() == q.lower() for t in types)
    return render_template(
        "admin_inventory_cocktails.html",
        cocktails=cocktails,
        types=types,
        q=q,
        type_filter=type_filter,
        type_exists=type_exists,
    )


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
    if style:
        _ensure_lookup(
            conn,
            "beer_styles",
            "SELECT DISTINCT style FROM beer WHERE style IS NOT NULL AND TRIM(style) != ''",
        )
        conn.execute("INSERT OR IGNORE INTO beer_styles (name) VALUES (?)", (style,))

    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_beer", q=name))


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
    _ensure_spirit_types(conn)
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
    if type_:
        conn.execute(
            "INSERT OR IGNORE INTO spirit_types (name) VALUES (?)",
            (type_,),
        )

    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_spirits", q=name))


@bp.post("/spirits/types/add")
def spirits_type_add():
    name = (request.form.get("type") or "").strip()
    if not name:
        return redirect(url_for("inventory_admin.inventory_spirits"))
    conn = get_db()
    _ensure_spirit_types(conn)
    conn.execute("INSERT OR IGNORE INTO spirit_types (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_spirits", type=name))


@bp.post("/beer/types/add")
def beer_type_add():
    name = (request.form.get("type") or "").strip()
    if not name:
        return redirect(url_for("inventory_admin.inventory_beer"))
    conn = get_db()
    _ensure_lookup(
        conn,
        "beer_styles",
        "SELECT DISTINCT style FROM beer WHERE style IS NOT NULL AND TRIM(style) != ''",
    )
    conn.execute("INSERT OR IGNORE INTO beer_styles (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_beer", type=name))


@bp.post("/cocktails/types/add")
def cocktails_type_add():
    name = (request.form.get("type") or "").strip()
    if not name:
        return redirect(url_for("inventory_admin.inventory_cocktails"))
    conn = get_db()
    _ensure_lookup(
        conn,
        "cocktail_types",
        """
        SELECT DISTINCT base FROM cocktails WHERE base IS NOT NULL AND TRIM(base) != ''
        UNION
        SELECT DISTINCT style FROM cocktails WHERE style IS NOT NULL AND TRIM(style) != ''
        """,
    )
    conn.execute("INSERT OR IGNORE INTO cocktail_types (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_cocktails", type=name))


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
    _ensure_lookup(
        conn,
        "cocktail_types",
        """
        SELECT DISTINCT base FROM cocktails WHERE base IS NOT NULL AND TRIM(base) != ''
        UNION
        SELECT DISTINCT style FROM cocktails WHERE style IS NOT NULL AND TRIM(style) != ''
        """,
    )
    for label in (base, style):
        if label:
            conn.execute("INSERT OR IGNORE INTO cocktail_types (name) VALUES (?)", (label,))

    conn.commit()
    conn.close()
    return redirect(url_for("inventory_admin.inventory_cocktails", q=name))


def _redirect_search(endpoint, form):
    return redirect(
        url_for(
            endpoint,
            q=(form.get("q") or "").strip() or None,
            type=(form.get("type") or "").strip() or None,
        )
    )


def _selected_ids():
    ids = []
    for raw in request.form.getlist("ids"):
        if str(raw).isdigit():
            ids.append(int(raw))
    return ids


def _bulk_change(table, endpoint):
    ids = _selected_ids()
    action = (request.form.get("action") or "").strip()
    if not ids:
        flash("Select at least one row.")
        return _redirect_search(endpoint, request.form)
    placeholders = ",".join("?" * len(ids))
    conn = get_db()
    if action == "inactive":
        conn.execute(f"UPDATE {table} SET active = 0 WHERE id IN ({placeholders})", ids)
        flash(f"Marked {len(ids)} inactive.")
    elif action == "active":
        conn.execute(f"UPDATE {table} SET active = 1 WHERE id IN ({placeholders})", ids)
        flash(f"Marked {len(ids)} active.")
    elif action == "delete":
        conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
        flash(f"Deleted {len(ids)}.")
    else:
        conn.close()
        flash("Unknown bulk action.")
        return _redirect_search(endpoint, request.form)
    conn.commit()
    conn.close()
    return _redirect_search(endpoint, request.form)


@bp.post("/beer/bulk")
def beer_bulk():
    return _bulk_change("beer", "inventory_admin.inventory_beer")


@bp.post("/spirits/bulk")
def spirits_bulk():
    return _bulk_change("spirits", "inventory_admin.inventory_spirits")


@bp.post("/cocktails/bulk")
def cocktails_bulk():
    return _bulk_change("cocktails", "inventory_admin.inventory_cocktails")


@bp.post("/beer/delete")
def beer_delete():
    beer_id = request.form.get("id")
    if beer_id:
        conn = get_db()
        conn.execute("DELETE FROM beer WHERE id = ?", (beer_id,))
        conn.commit()
        conn.close()
    return _redirect_search("inventory_admin.inventory_beer", request.form)


@bp.post("/spirits/delete")
def spirits_delete():
    spirit_id = request.form.get("id")
    if spirit_id:
        conn = get_db()
        conn.execute("DELETE FROM spirits WHERE id = ?", (spirit_id,))
        conn.commit()
        conn.close()
    return _redirect_search("inventory_admin.inventory_spirits", request.form)


@bp.post("/cocktails/delete")
def cocktails_delete():
    cocktail_id = request.form.get("id")
    if cocktail_id:
        conn = get_db()
        conn.execute("DELETE FROM cocktails WHERE id = ?", (cocktail_id,))
        conn.commit()
        conn.close()
    return _redirect_search("inventory_admin.inventory_cocktails", request.form)