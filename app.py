from flask import Flask, render_template_string, request, jsonify, session
import pandas as pd
import os, re, hashlib, json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sakaniyet-2025-secret-key"

ADMIN_USER = "admin"
ADMIN_PASS = hashlib.sha256("admin2025".encode()).hexdigest()

BASE_DIR    = "/home/brmarche"
DATA_FILE   = os.path.join(BASE_DIR, "data.xlsx")
USERS_FILE  = os.path.join(BASE_DIR, "users.json")
EDITS_FILE  = os.path.join(BASE_DIR, "edits.json")

COL_RENAME = {
    "ر,ت":                                          "rt",
    "المؤسسة":                                      "institution",
    "نوعها":                                        "type",
    "رمز GRESA":                                    "gresa",
    "الجماعة الترابية":                             "commune",
    "الوسط":                                        "milieu",
    "طبيعة السكن":                                  "nature",
    "صنف السكن":                                    "categorie",
    "حالة السكن":                                   "etat",
    "وضعية السكن :":                                "statut",
    "اسم ونسب القاطن الحالي":                       "occupant",
    "رقم تأجيره":                                   "num_bail",
    "إطاره":                                        "cadre",
    "Date d'occupation/تاريخ إسناد السكن 2":        "date_occ",
    "مهمته":                                        "mission",
    "نوع الإسناد":                                  "type_aff",
    "وضعية القاطن":                                 "statut_occ",
    "ملاحظات  إضافية":                              "notes",
}

def normalize(s):
    return re.sub(r'\s+', ' ', str(s).strip())

def load_data():
    df = pd.read_excel(DATA_FILE, header=2, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for orig, short in COL_RENAME.items():
        for col in df.columns:
            if normalize(col) == normalize(orig):
                rename[col] = short
                break
    for col in df.columns:
        if "الرقم المخزني" in col and col not in rename:
            rename[col] = "makhzani"
            break
    df = df.rename(columns=rename)
    for col in ["rt","institution","type","gresa","commune","milieu","makhzani",
                "nature","categorie","etat","statut","occupant","num_bail",
                "cadre","date_occ","mission","type_aff","statut_occ","notes"]:
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("—")
    df["institution"] = df["institution"].str.strip()
    df = df[df["institution"].str.len() > 2]
    df = df[df["institution"] != "—"]
    df = df.reset_index(drop=True)
    return df

try:
    DF = load_data()
    print(f"[OK] تم تحميل {len(DF)} سكنية في {DF['institution'].nunique()} مؤسسة")
except Exception as e:
    DF = pd.DataFrame()
    print(f"[خطأ] {e}")

def load_edits():
    if os.path.exists(EDITS_FILE):
        with open(EDITS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_edits(edits):
    with open(EDITS_FILE, "w", encoding="utf-8") as f:
        json.dump(edits, f, ensure_ascii=False, indent=2)

EDITS = load_edits()

def row_key(h):
    return f"{h.get('gresa','')}__{h.get('makhzani','')}"

def apply_edits(row_dict):
    k = row_key(row_dict)
    if k in EDITS:
        row_dict = {**row_dict, **EDITS[k]["data"]}
        row_dict["_edit_log"] = EDITS[k].get("log", [])
    return row_dict

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

USERS = load_users()

def logged_in():
    return session.get("user") == ADMIN_USER

def current_user():
    return session.get("user")

def is_admin():
    return session.get("user") == ADMIN_USER

def is_institution_user():
    u = session.get("user")
    return u and u != ADMIN_USER and u in USERS and USERS[u].get("approved")

def get_inst_gresa():
    u = session.get("user")
    if u and u in USERS:
        return USERS[u].get("gresa")
    return None

# ════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    u = (data.get("username") or "").strip()
    p = hashlib.sha256((data.get("password") or "").encode()).hexdigest()
    if u == ADMIN_USER and p == ADMIN_PASS:
        session["user"] = u
        return jsonify({"ok": True, "role": "admin"})
    if u in USERS:
        usr = USERS[u]
        if usr.get("password") == p:
            if not usr.get("approved"):
                return jsonify({"ok": False, "msg": "حسابك في انتظار موافقة المدير"}), 403
            session["user"] = u
            return jsonify({"ok": True, "role": "institution",
                            "gresa": usr.get("gresa"), "name": usr.get("name"),
                            "can_edit": usr.get("can_edit", False)})
        return jsonify({"ok": False, "msg": "كلمة المرور غير صحيحة"}), 401
    return jsonify({"ok": False, "msg": "اسم المستخدم غير موجود"}), 401

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.route("/api/me")
def api_me():
    u = current_user()
    if not u:
        return jsonify({"logged": False})
    if u == ADMIN_USER:
        return jsonify({"logged": True, "user": u, "role": "admin"})
    if u in USERS and USERS[u].get("approved"):
        usr = USERS[u]
        return jsonify({"logged": True, "user": u, "role": "institution",
                        "gresa": usr.get("gresa"), "name": usr.get("name"),
                        "can_edit": usr.get("can_edit", False)})
    return jsonify({"logged": False})

@app.route("/api/register", methods=["POST"])
def api_register():
    global USERS
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    gresa    = (data.get("gresa")    or "").strip()
    num_bail = (data.get("num_bail") or "").strip()
    name     = (data.get("name")     or "").strip()

    if not all([username, password, gresa, num_bail, name]):
        return jsonify({"ok": False, "msg": "جميع الحقول إلزامية"}), 400
    if username == ADMIN_USER:
        return jsonify({"ok": False, "msg": "اسم المستخدم محجوز"}), 400
    if username in USERS:
        return jsonify({"ok": False, "msg": "اسم المستخدم موجود مسبقاً"}), 400

    if not DF.empty:
        match = DF[DF["gresa"].str.strip() == gresa]
        if match.empty:
            return jsonify({"ok": False, "msg": f"كود GRESA '{gresa}' غير موجود في قاعدة البيانات"}), 400
        bail_match = match[match["num_bail"].str.strip() == num_bail]
        if bail_match.empty:
            return jsonify({"ok": False, "msg": "رقم التأجير غير مطابق لكود GRESA المدخل"}), 400

    USERS[username] = {
        "password": hashlib.sha256(password.encode()).hexdigest(),
        "gresa": gresa,
        "num_bail": num_bail,
        "name": name,
        "phone": "",
        "email": "",
        "approved": False,
        "can_edit": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_users(USERS)
    return jsonify({"ok": True, "msg": "تم إرسال طلبك، بانتظار موافقة المدير"})

@app.route("/api/admin/users")
def api_admin_users():
    if not is_admin():
        return jsonify({"error": "unauthorized"}), 401
    result = []
    for uname, udata in USERS.items():
        result.append({
            "username": uname,
            "name": udata.get("name",""),
            "gresa": udata.get("gresa",""),
            "num_bail": udata.get("num_bail",""),
            "approved": udata.get("approved", False),
            "can_edit": udata.get("can_edit", False),
            "created_at": udata.get("created_at",""),
        })
    return jsonify(result)

@app.route("/api/admin/approve", methods=["POST"])
def api_admin_approve():
    global USERS
    if not is_admin():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json()
    uname = data.get("username","")
    action = data.get("action","approve")
    if uname not in USERS:
        return jsonify({"ok": False, "msg": "المستخدم غير موجود"}), 404
    if action == "approve":
        USERS[uname]["approved"] = True
    elif action == "reject":
        USERS[uname]["approved"] = False
    elif action == "delete":
        del USERS[uname]
    save_users(USERS)
    return jsonify({"ok": True})

@app.route("/api/admin/set_edit_permission", methods=["POST"])
def api_set_edit_permission():
    global USERS
    if not is_admin():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json()
    usernames = data.get("usernames", [])
    can_edit  = data.get("can_edit", False)
    updated = 0
    for uname in usernames:
        if uname in USERS:
            USERS[uname]["can_edit"] = can_edit
            updated += 1
    save_users(USERS)
    return jsonify({"ok": True, "updated": updated})

# ── الملف الشخصي للمستخدم ──────────────────────────────────────────────────
@app.route("/api/profile", methods=["GET","POST"])
def api_profile():
    global USERS
    u = current_user()
    if not u or u == ADMIN_USER:
        return jsonify({"error": "unauthorized"}), 401
    if u not in USERS:
        return jsonify({"error": "not found"}), 404
    if request.method == "GET":
        usr = USERS[u]
        return jsonify({
            "name":     usr.get("name",""),
            "gresa":    usr.get("gresa",""),
            "num_bail": usr.get("num_bail",""),
            "phone":    usr.get("phone",""),
            "email":    usr.get("email",""),
        })
    data = request.get_json()
    USERS[u]["phone"] = (data.get("phone") or "").strip()
    USERS[u]["email"] = (data.get("email") or "").strip()
    save_users(USERS)
    return jsonify({"ok": True})

# ════════════════════════════════════════════════════════════════════════════
# DATA ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════

@app.route("/api/stats")
def api_stats():
    if not (is_admin() or is_institution_user()):
        return jsonify({"error": "unauthorized"}), 401
    if DF.empty:
        return jsonify({"institutions": 0, "housing": 0, "occupied": 0, "vacant": 0, "occupied_illegal": 0})

    if is_institution_user():
        gresa = get_inst_gresa()
        df = DF[DF["gresa"].str.strip() == gresa]
    else:
        df = DF

    total    = len(df)
    occupied = int(df["statut"].str.contains("مستعمل|مشغول|مشغولة", na=False, regex=True).sum())
    vacant   = int(df["statut"].str.contains("شاغر|فارغ", na=False, regex=True).sum())
    occ_ill  = int(df["statut"].str.contains("محتل", na=False, regex=True).sum())
    urban    = int((df["milieu"].str.contains("حضري", na=False)).sum())
    rural    = int((df["milieu"].str.contains("قروي", na=False)).sum())
    by_type   = df.groupby("type").size().to_dict()
    by_statut = df.groupby("statut").size().to_dict()
    return jsonify({
        "institutions":    int(df["institution"].nunique()),
        "housing":         total,
        "occupied":        occupied,
        "vacant":          vacant,
        "occupied_illegal": occ_ill,
        "urban":           urban,
        "rural":           rural,
        "by_type":         by_type,
        "by_statut":       by_statut,
        "rate_occupied":   round(occupied / total * 100, 1) if total else 0,
        "rate_vacant":     round(vacant   / total * 100, 1) if total else 0,
        "rate_illegal":    round(occ_ill  / total * 100, 1) if total else 0,
    })

@app.route("/api/search")
def api_search():
    if not (is_admin() or is_institution_user()):
        return jsonify({"error": "unauthorized"}), 401
    q = request.args.get("q", "").strip()
    if len(q) < 1:
        return jsonify([])

    if is_institution_user():
        gresa = get_inst_gresa()
        df = DF[DF["gresa"].str.strip() == gresa]
    else:
        df = DF

    ql = q.lower()
    mask = (
        df["institution"].str.lower().str.contains(ql, na=False) |
        df["gresa"].str.lower().str.contains(ql, na=False)       |
        df["occupant"].str.lower().str.contains(ql, na=False)    |
        df["commune"].str.lower().str.contains(ql, na=False)
    )
    names = df[mask]["institution"].unique().tolist()
    return jsonify(names[:20])

@app.route("/api/institution")
def api_institution():
    if not (is_admin() or is_institution_user()):
        return jsonify({"error": "unauthorized"}), 401
    name = request.args.get("name", "").strip()

    if is_institution_user():
        gresa = get_inst_gresa()
        rows = DF[(DF["institution"] == name) & (DF["gresa"].str.strip() == gresa)]
        if rows.empty:
            return jsonify({"error": "not authorized"}), 403
    else:
        rows = DF[DF["institution"] == name]

    if rows.empty:
        return jsonify({"error": "not found"}), 404

    info    = rows.iloc[0]
    housing = [apply_edits(h) for h in rows.to_dict(orient="records")]
    return jsonify({
        "institution": {
            "name":    info["institution"],
            "type":    info.get("type",    "—"),
            "gresa":   info.get("gresa",   "—"),
            "commune": info.get("commune", "—"),
            "milieu":  info.get("milieu",  "—"),
        },
        "housing": housing,
        "stats": {
            "total":    len(housing),
            "occupied": sum(1 for h in housing if re.search(r"مستعمل|مشغول|مشغولة", str(h.get("statut", "")))),
            "vacant":   sum(1 for h in housing if re.search(r"شاغر|فارغ", str(h.get("statut", "")))),
            "illegal":  sum(1 for h in housing if re.search(r"محتل", str(h.get("statut", "")))),
        }
    })

@app.route("/api/vacant")
def api_vacant():
    if not (is_admin() or is_institution_user()):
        return jsonify({"error": "unauthorized"}), 401
    if is_institution_user():
        gresa = get_inst_gresa()
        df = DF[DF["gresa"].str.strip() == gresa]
    else:
        df = DF
    mask = df["statut"].str.contains("شاغر|فارغ", na=False, regex=True)
    rows = [apply_edits(h) for h in df[mask].to_dict(orient="records")]
    return jsonify({"vacant": rows, "total": len(rows)})

@app.route("/api/occupied_illegal")
def api_occupied_illegal():
    if not (is_admin() or is_institution_user()):
        return jsonify({"error": "unauthorized"}), 401
    if is_institution_user():
        gresa = get_inst_gresa()
        df = DF[DF["gresa"].str.strip() == gresa]
    else:
        df = DF
    mask = df["statut"].str.contains("محتل", na=False, regex=True)
    rows = [apply_edits(h) for h in df[mask].to_dict(orient="records")]
    return jsonify({"illegal": rows, "total": len(rows)})

@app.route("/api/edit_occupant", methods=["POST"])
def api_edit_occupant():
    global EDITS
    u = current_user()
    if not u:
        return jsonify({"error": "unauthorized"}), 401
    if u != ADMIN_USER:
        if u not in USERS or not USERS[u].get("can_edit"):
            return jsonify({"error": "unauthorized", "msg": "ليس لديك صلاحية التعديل"}), 401

    data = request.get_json()
    gresa    = data.get("gresa","").strip()
    makhzani = data.get("makhzani","").strip()
    fields   = data.get("fields", {})

    key = f"{gresa}__{makhzani}"

    match = DF[(DF["gresa"].str.strip() == gresa) & (DF["makhzani"].str.strip() == makhzani)]
    if match.empty:
        return jsonify({"ok": False, "msg": "السكنية غير موجودة"}), 404

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": now,
        "admin": u,
        "changes": fields
    }

    if key not in EDITS:
        EDITS[key] = {"data": {}, "log": []}

    EDITS[key]["data"].update(fields)
    EDITS[key]["log"].append(log_entry)
    save_edits(EDITS)

    return jsonify({"ok": True, "timestamp": now})

@app.route("/api/edit_log")
def api_edit_log():
    if not is_admin():
        return jsonify({"error": "unauthorized"}), 401
    gresa    = request.args.get("gresa","").strip()
    makhzani = request.args.get("makhzani","").strip()
    key = f"{gresa}__{makhzani}"
    log = EDITS.get(key, {}).get("log", [])
    return jsonify({"log": log})

# ════════════════════════════════════════════════════════════════════════════
# HTML
# ════════════════════════════════════════════════════════════════════════════
HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>منظومة تدبير السكنيات الوظيفية والإدارية</title>
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800;900&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet"/>
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet"/>
<style>
:root {
  --bg: #060a12;
  --bg2: #0c1220;
  --surface: #111827;
  --surface2: #1a2235;
  --surface3: #212d42;
  --border: rgba(255,255,255,0.07);
  --border2: rgba(255,255,255,0.12);

  --primary: #3b82f6;
  --primary-dk: #2563eb;
  --primary-lt: rgba(59,130,246,0.12);
  --primary-glow: rgba(59,130,246,0.3);

  --green: #10b981;
  --green-bg: rgba(16,185,129,0.1);
  --green-glow: rgba(16,185,129,0.25);

  --amber: #f59e0b;
  --amber-bg: rgba(245,158,11,0.1);
  --amber-glow: rgba(245,158,11,0.25);

  --red: #ef4444;
  --red-bg: rgba(239,68,68,0.1);
  --red-glow: rgba(239,68,68,0.25);

  --violet: #8b5cf6;
  --violet-bg: rgba(139,92,246,0.1);

  --text: #f1f5f9;
  --muted: #64748b;
  --muted2: #94a3b8;

  --r: 14px;
  --r2: 10px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Tajawal', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 0;
}

.orb {
  position: fixed;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
  z-index: 0;
  opacity: 0.35;
}
.orb-1 { width: 500px; height: 500px; background: radial-gradient(circle, #1d4ed8 0%, transparent 70%); top: -150px; right: -100px; }
.orb-2 { width: 400px; height: 400px; background: radial-gradient(circle, #065f46 0%, transparent 70%); bottom: -100px; left: -80px; }
.orb-3 { width: 300px; height: 300px; background: radial-gradient(circle, #7c3aed 0%, transparent 70%); top: 40%; left: 30%; opacity: 0.15; }

.sb {
  position: fixed; top: 0; right: 0;
  width: 70px; height: 100vh;
  background: rgba(8,14,26,0.85);
  backdrop-filter: blur(20px);
  border-left: 1px solid var(--border);
  display: flex; flex-direction: column; align-items: center;
  padding: 1.2rem 0; gap: 3px; z-index: 100;
  transition: width 0.3s cubic-bezier(0.4,0,0.2,1);
  overflow: hidden;
}
.sb:hover { width: 230px; }

.sb-logo {
  width: 44px; height: 44px; border-radius: 12px;
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 20px;
  margin-bottom: 1.5rem; flex-shrink: 0;
  box-shadow: 0 0 20px rgba(59,130,246,0.4);
}

.ni {
  display: flex; align-items: center; gap: 12px;
  width: 100%; padding: 11px 13px;
  color: var(--muted2); font-size: 13.5px; font-weight: 500;
  cursor: pointer; border-right: 2px solid transparent;
  overflow: hidden; white-space: nowrap;
  transition: all 0.2s; text-decoration: none;
  border-radius: 0; position: relative;
}
.ni::before {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, rgba(59,130,246,0.08));
  opacity: 0; transition: opacity 0.2s;
}
.ni:hover { color: #fff; border-right-color: var(--primary); }
.ni:hover::before { opacity: 1; }
.ni.on { color: #fff; border-right-color: var(--primary); background: rgba(59,130,246,0.08); }
.ni i { font-size: 20px; flex-shrink: 0; min-width: 22px; text-align: center; }
.nl { opacity: 0; transition: opacity 0.15s 0.05s; white-space: nowrap; }
.sb:hover .nl { opacity: 1; }
.ni.bot { margin-top: auto; }
.ni.logout { color: #f87171; }
.ni.logout:hover { background: rgba(248,113,113,0.1); border-right-color: var(--red); }

.main { margin-right: 70px; min-height: 100vh; display: flex; flex-direction: column; position: relative; z-index: 1; }

.tb {
  background: rgba(8,14,26,0.7);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  padding: 1rem 2rem;
  display: flex; align-items: center; justify-content: space-between;
  position: sticky; top: 0; z-index: 50;
}
.tb-brand { display: flex; align-items: center; gap: 12px; }
.tb-brand .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.6;transform:scale(0.85)} }
.tb-title { font-size: 15px; font-weight: 800; letter-spacing: -0.3px; }
.tb-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
.tb-right { display: flex; align-items: center; gap: 12px; }

.uc-wrap { position: relative; }
.uc {
  display: flex; align-items: center; gap: 8px;
  background: var(--surface2); border: 1px solid var(--border2);
  padding: 7px 14px; border-radius: 50px;
  font-size: 13px; font-weight: 600; color: var(--text);
  cursor: pointer; transition: all 0.2s;
}
.uc:hover { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
.uc .role-badge {
  font-size: 10px; padding: 2px 7px; border-radius: 10px;
  font-weight: 700; background: var(--primary-lt); color: var(--primary);
}
.uc .role-badge.inst { background: var(--violet-bg); color: var(--violet); }
.uc i.arr { font-size: 11px; color: var(--muted); transition: transform 0.2s; }
.uc-wrap.open .uc i.arr { transform: rotate(180deg); }
.uc-menu {
  position: absolute; top: calc(100% + 8px); left: 0;
  background: var(--surface); border: 1px solid var(--border2);
  border-radius: 12px; box-shadow: 0 16px 48px rgba(0,0,0,0.5);
  min-width: 200px; overflow: hidden; display: none;
  z-index: 200; animation: dropIn 0.18s ease;
}
@keyframes dropIn { from{opacity:0;transform:translateY(-8px)} to{opacity:1;transform:none} }
.uc-wrap.open .uc-menu { display: block; }
.uc-menu-item {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 16px; font-size: 13px; font-weight: 500;
  cursor: pointer; color: var(--text); transition: background 0.12s;
}
.uc-menu-item:hover { background: var(--surface2); }
.uc-menu-item.danger { color: var(--red); }
.uc-menu-item.danger:hover { background: var(--red-bg); }
.uc-menu-sep { height: 1px; background: var(--border); }

.ct { padding: 1.75rem 2rem 6rem; flex: 1; }

/* ══ STAT GRID — 5 columns, illegal card in same row ══ */
.sg {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
  margin-bottom: 1.75rem;
}

.sc {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 1.2rem 1.4rem;
  display: flex; align-items: center; gap: 1rem;
  position: relative; overflow: hidden;
  transition: all 0.25s;
}
.sc::before {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(135deg, rgba(255,255,255,0.03), transparent);
  pointer-events: none;
}
.sc.clickable { cursor: pointer; }
.sc.clickable:hover {
  border-color: var(--border2);
  transform: translateY(-3px);
  box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.sc.c-blue { border-top: 2px solid var(--primary); }
.sc.c-green { border-top: 2px solid var(--green); }
.sc.c-amber { border-top: 2px solid var(--amber); }
.sc.c-red { border-top: 2px solid var(--red); }

.si {
  width: 48px; height: 48px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; flex-shrink: 0;
}
.si.b { background: var(--primary-lt); color: var(--primary); box-shadow: 0 0 16px rgba(59,130,246,0.2); }
.si.g { background: var(--green-bg); color: var(--green); box-shadow: 0 0 16px rgba(16,185,129,0.2); }
.si.a { background: var(--amber-bg); color: var(--amber); box-shadow: 0 0 16px rgba(245,158,11,0.2); }
.si.r { background: var(--red-bg); color: var(--red); box-shadow: 0 0 16px rgba(239,68,68,0.2); }

.sn { font-size: 26px; font-weight: 800; line-height: 1; letter-spacing: -1px; }
.sl { font-size: 11.5px; color: var(--muted); margin-top: 3px; font-weight: 500; }
.sc-hint {
  font-size: 10px; color: var(--primary); margin-top: 5px;
  font-weight: 700; letter-spacing: 0.5px; display: none;
  text-transform: uppercase;
}
.sc.clickable:hover .sc-hint { display: block; }
.sc.c-red.clickable:hover .sc-hint { color: var(--red); }

.sb-box {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); padding: 1.5rem; margin-bottom: 1.5rem;
  position: relative; overflow: hidden;
}
.sb-box::before {
  content: ''; position: absolute; top: 0; right: 0; left: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--primary), transparent);
}
.sb-box h2 {
  font-size: 14px; font-weight: 700; margin-bottom: 1rem;
  display: flex; align-items: center; gap: 8px; color: var(--muted2);
  text-transform: uppercase; letter-spacing: 1px;
}
.sw { position: relative; }
.sw .ic {
  position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
  font-size: 18px; color: var(--muted); pointer-events: none;
}
.sw input {
  width: 100%; padding: 13px 46px 13px 16px;
  background: var(--bg2); border: 1.5px solid var(--border2);
  border-radius: 10px; color: var(--text);
  font-family: 'Tajawal', sans-serif; font-size: 14.5px; outline: none;
  transition: all 0.2s;
}
.sw input::placeholder { color: var(--muted); }
.sw input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-glow);
}
/* FIX: autocomplete z-index must be above everything */
.ac {
  position: absolute; top: calc(100% + 6px); right: 0; left: 0;
  background: var(--surface); border: 1px solid var(--border2);
  border-radius: 12px; box-shadow: 0 16px 48px rgba(0,0,0,0.5);
  z-index: 9999; display: none; max-height: 280px; overflow-y: auto;
}
.aci {
  padding: 11px 16px; cursor: pointer; font-size: 13.5px;
  display: flex; align-items: center; gap: 10px;
  border-bottom: 1px solid var(--border); transition: background 0.12s;
}
.aci:last-child { border-bottom: none; }
.aci:hover, .aci.hi { background: var(--primary-lt); color: var(--primary); }
.aci i { color: var(--primary); font-size: 16px; flex-shrink: 0; }

.inst-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); margin-bottom: 1.5rem;
  overflow: hidden; animation: fadeUp 0.35s ease;
}
@keyframes fadeUp { from{opacity:0;transform:translateY(14px)} to{opacity:1;transform:none} }
@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }

.inst-header {
  background: linear-gradient(135deg, #040d1a 0%, #0f2040 50%, #1a3a6b 100%);
  padding: 1.8rem; display: flex; align-items: flex-start; gap: 1.3rem; flex-wrap: wrap;
  border-bottom: 1px solid var(--border);
  position: relative; overflow: hidden;
}
.inst-header::before {
  content: ''; position: absolute; top: -40px; left: -40px;
  width: 200px; height: 200px; border-radius: 50%;
  background: radial-gradient(circle, rgba(59,130,246,0.2), transparent 70%);
}
.inst-av {
  width: 62px; height: 62px; border-radius: 14px;
  background: rgba(59,130,246,0.15); border: 1.5px solid rgba(59,130,246,0.3);
  color: var(--primary); display: flex; align-items: center;
  justify-content: center; font-size: 26px; flex-shrink: 0;
  box-shadow: 0 0 20px rgba(59,130,246,0.2);
}
.inst-name { font-size: 18px; font-weight: 800; color: #fff; margin-bottom: 4px; }
.inst-type { font-size: 12px; color: rgba(255,255,255,0.5); margin-bottom: 10px; }
.inst-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 4px 10px; border-radius: 20px; font-size: 11.5px; font-weight: 600;
}
.chip-w { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.85); border: 1px solid rgba(255,255,255,0.15); }

.inst-stats { display: flex; border-top: 1px solid var(--border); }
.ist { flex: 1; text-align: center; padding: 1rem .5rem; border-left: 1px solid var(--border); }
.ist:last-child { border-left: none; }
.ist .n { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }
.ist .l { font-size: 11px; color: var(--muted); margin-top: 3px; }

.ic-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); margin-bottom: 1.5rem;
  overflow: hidden; animation: fadeUp 0.4s ease;
}
.card-title {
  padding: 1rem 1.4rem; border-bottom: 1px solid var(--border);
  font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 8px;
  color: var(--muted2); text-transform: uppercase; letter-spacing: 1px;
  flex-wrap: wrap;
}
.card-title-count {
  margin-right: auto; font-size: 11.5px; font-weight: 700;
  color: var(--muted); background: var(--surface2);
  padding: 3px 10px; border-radius: 20px;
  font-family: 'IBM Plex Mono', monospace;
}
.tw { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th {
  padding: 10px 16px; text-align: right;
  font-size: 11px; color: var(--muted); font-weight: 700;
  background: var(--surface2); border-bottom: 1px solid var(--border);
  text-transform: uppercase; letter-spacing: 0.8px;
}
td {
  padding: 12px 16px; font-size: 13px;
  border-bottom: 1px solid var(--border); vertical-align: middle;
}
tr:last-child td { border-bottom: none; }
tr.hr td { transition: background 0.12s; }
tr.hr:hover td { background: rgba(59,130,246,0.06); cursor: pointer; }

.badge { padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }
.bg { background: var(--green-bg); color: var(--green); border: 1px solid rgba(16,185,129,0.2); }
.ba { background: var(--amber-bg); color: var(--amber); border: 1px solid rgba(245,158,11,0.2); }
.br { background: var(--red-bg); color: var(--red); border: 1px solid rgba(239,68,68,0.2); }
.bv { background: var(--violet-bg); color: var(--violet); border: 1px solid rgba(139,92,246,0.2); }
.bx { background: var(--surface2); color: var(--muted); border: 1px solid var(--border); }

.btn-sm {
  padding: 5px 12px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--surface2); color: var(--muted2);
  font-family: 'Tajawal', sans-serif; font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all 0.15s; white-space: nowrap; display: inline-flex;
  align-items: center; gap: 5px;
}
.btn-sm:hover { background: var(--primary); color: #fff; border-color: var(--primary); box-shadow: 0 0 12px var(--primary-glow); }
.btn-sm.edit { background: var(--violet-bg); color: var(--violet); border-color: rgba(139,92,246,0.3); }
.btn-sm.edit:hover { background: var(--violet); color: #fff; }

.stats-panel {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); margin-bottom: 1.5rem;
  overflow: hidden; animation: fadeUp 0.35s ease;
}
.sp-header {
  padding: 1rem 1.4rem; border-bottom: 1px solid var(--border);
  font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 8px;
  color: var(--muted2); text-transform: uppercase; letter-spacing: 1px;
}
.sp-body {
  padding: 1.4rem;
  display: grid; grid-template-columns: repeat(3,1fr); gap: 1rem;
}
.sp-item {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 10px; padding: 1.1rem 1.2rem;
}
.sp-item .label { font-size: 11px; color: var(--muted); margin-bottom: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }
.sp-item .val { font-size: 28px; font-weight: 800; letter-spacing: -1px; }
.sp-bar { height: 6px; border-radius: 3px; background: var(--surface3); margin-top: 10px; overflow: hidden; }
.sp-fill { height: 100%; border-radius: 3px; transition: width 0.8s cubic-bezier(0.4,0,0.2,1); }
.sp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sp-table td { padding: 7px 10px; border-bottom: 1px solid var(--border); }
.sp-table tr:last-child td { border-bottom: none; }
.sp-full { grid-column: 1/-1; }

.admin-panel {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); margin-bottom: 1.5rem;
  overflow: hidden; animation: fadeUp 0.35s ease;
}
.admin-header {
  padding: 1rem 1.4rem; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 8px;
}
.admin-header h2 {
  font-size: 13px; font-weight: 700; display: flex; align-items: center; gap: 8px;
  color: var(--muted2); text-transform: uppercase; letter-spacing: 1px;
}
.user-row {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 1.4rem; border-bottom: 1px solid var(--border);
  flex-wrap: wrap; transition: background 0.12s;
}
.user-row:last-child { border-bottom: none; }
.user-row:hover { background: rgba(255,255,255,0.02); }
.user-av {
  width: 38px; height: 38px; border-radius: 50%;
  background: var(--surface2); border: 1.5px solid var(--border2);
  color: var(--muted2); display: flex; align-items: center;
  justify-content: center; font-size: 16px; flex-shrink: 0;
}
.user-info { flex: 1; min-width: 0; }
.user-name { font-size: 13.5px; font-weight: 700; }
.user-meta { font-size: 11.5px; color: var(--muted); margin-top: 2px; }
.user-actions { display: flex; gap: 6px; flex-shrink: 0; flex-wrap: wrap; }

.btn-approve { background: var(--green-bg); color: var(--green); border-color: rgba(16,185,129,0.3); }
.btn-approve:hover { background: var(--green); color: #fff; }
.btn-reject { background: var(--red-bg); color: var(--red); border-color: rgba(239,68,68,0.3); }
.btn-reject:hover { background: var(--red); color: #fff; }

.pending-badge {
  background: var(--amber-bg); color: var(--amber);
  border: 1px solid rgba(245,158,11,0.3);
  padding: 2px 8px; border-radius: 10px;
  font-size: 10px; font-weight: 700; animation: blink 2s infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0.6} }

.edit-perm-badge {
  background: rgba(139,92,246,0.15); color: var(--violet);
  border: 1px solid rgba(139,92,246,0.3);
  padding: 2px 8px; border-radius: 10px;
  font-size: 10px; font-weight: 700;
}

.bulk-bar {
  padding: .9rem 1.4rem;
  background: rgba(139,92,246,0.05);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.bulk-bar span { font-size: 12px; color: var(--muted); font-weight: 700; }

.ov {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.7);
  backdrop-filter: blur(8px);
  display: none; align-items: center; justify-content: center;
  z-index: 300;
}
.ov.show { display: flex; }
.mo {
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: 18px;
  width: min(94%, 640px); max-height: 88vh;
  display: flex; flex-direction: column; overflow: hidden;
  animation: modalIn 0.22s cubic-bezier(0.34,1.56,0.64,1);
  box-shadow: 0 32px 64px rgba(0,0,0,0.6);
}
@keyframes modalIn { from{opacity:0;transform:scale(0.93)} to{opacity:1;transform:none} }
.moh {
  padding: 1.1rem 1.4rem; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
.moh h3 { font-size: 15px; font-weight: 700; }
.cx {
  width: 32px; height: 32px; border-radius: 8px; border: none;
  background: var(--surface2); color: var(--muted); font-size: 17px;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.cx:hover { background: var(--red-bg); color: var(--red); }
.mob { padding: 1.4rem; overflow-y: auto; flex: 1; }

.occ-header {
  background: linear-gradient(135deg, #040d1a, #0f2040);
  border-radius: 12px; padding: 1.2rem 1.3rem;
  margin-bottom: 1.1rem; display: flex; align-items: center; gap: 1rem;
  border: 1px solid var(--border);
}
.occ-av {
  width: 50px; height: 50px; border-radius: 50%;
  background: rgba(59,130,246,0.15); border: 2px solid rgba(59,130,246,0.3);
  color: var(--primary); display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.occ-name { font-size: 15px; font-weight: 800; color: #fff; }
.occ-sub { font-size: 12px; color: rgba(255,255,255,0.5); margin-top: 2px; }

.sec-title {
  font-size: 11px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 1px;
  margin: 1rem 0 .6rem; display: flex; align-items: center; gap: 7px;
}
.dg { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.df { background: var(--surface2); border: 1px solid var(--border); border-radius: 10px; padding: .7rem 1rem; }
.df .dl { font-size: 10px; color: var(--muted); margin-bottom: 4px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
.df .dv { font-size: 13.5px; font-weight: 600; color: var(--text); word-break: break-word; }
.df.full { grid-column: 1/-1; }

.ef-input {
  width: 100%; padding: 9px 12px;
  background: var(--bg2); border: 1.5px solid var(--border2);
  border-radius: 8px; color: var(--text);
  font-family: 'Tajawal', sans-serif; font-size: 13.5px; outline: none;
  transition: all 0.2s;
}
.ef-input:focus { border-color: var(--violet); box-shadow: 0 0 0 3px rgba(139,92,246,0.15); }

.log-entry {
  padding: 10px 12px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 8px; margin-bottom: 8px; font-size: 12px;
}
.log-ts { font-family: 'IBM Plex Mono', monospace; color: var(--muted); font-size: 11px; margin-bottom: 5px; }
.log-field { color: var(--violet); font-weight: 700; }
.log-val { color: var(--text); }

.login-ov {
  position: fixed; inset: 0;
  background: var(--bg);
  display: flex; align-items: center; justify-content: center;
  z-index: 999;
}
.login-ov.hidden { display: none; }
.login-scene {
  position: relative;
  width: min(94%, 460px);
}
.login-box {
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: 20px;
  padding: 2.5rem;
  box-shadow: 0 32px 80px rgba(0,0,0,0.5);
  position: relative; overflow: hidden;
}
.login-box::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--primary), transparent);
}
.login-logo { text-align: center; margin-bottom: 2rem; }
.login-logo .ic {
  width: 68px; height: 68px; border-radius: 18px;
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
  color: #fff; font-size: 30px;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 1rem; box-shadow: 0 0 30px rgba(59,130,246,0.4);
}
.login-logo h2 { font-size: 17px; font-weight: 800; margin-bottom: 5px; line-height: 1.4; }
.login-logo p { font-size: 12px; color: var(--muted); line-height: 1.7; }

.tabs-login {
  display: flex; gap: 0; margin-bottom: 1.5rem;
  background: var(--bg2); border-radius: 10px; padding: 4px;
}
.tab-btn {
  flex: 1; padding: 8px; border: none; border-radius: 7px;
  font-family: 'Tajawal', sans-serif; font-size: 13px; font-weight: 700;
  cursor: pointer; color: var(--muted); background: transparent; transition: all 0.2s;
}
.tab-btn.on { background: var(--surface); color: var(--text); box-shadow: 0 2px 8px rgba(0,0,0,0.2); }

.lf { margin-bottom: 1rem; }
.lf label {
  display: block; font-size: 11.5px; font-weight: 700;
  color: var(--muted); margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.5px;
}
.lf input {
  width: 100%; padding: 11px 14px;
  background: var(--bg2); border: 1.5px solid var(--border2);
  border-radius: 10px; font-family: 'Tajawal', sans-serif; font-size: 14px;
  color: var(--text); outline: none; transition: all 0.2s;
}
.lf input::placeholder { color: var(--muted); }
.lf input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-glow); }
.btn-login {
  width: 100%; padding: 13px;
  background: linear-gradient(135deg, #1d4ed8, #3b82f6); color: #fff;
  border: none; border-radius: 10px;
  font-family: 'Tajawal', sans-serif; font-size: 15px; font-weight: 800;
  cursor: pointer; margin-top: .5rem;
  transition: all 0.2s; letter-spacing: 0.5px;
  box-shadow: 0 4px 20px rgba(59,130,246,0.35);
}
.btn-login:hover { transform: translateY(-1px); box-shadow: 0 8px 28px rgba(59,130,246,0.45); }
.login-err {
  color: var(--red); font-size: 12.5px; margin-top: .8rem;
  text-align: center; display: none;
  background: var(--red-bg); padding: 8px; border-radius: 8px;
}
.login-ok {
  color: var(--green); font-size: 12.5px; margin-top: .8rem;
  text-align: center; display: none;
  background: var(--green-bg); padding: 8px; border-radius: 8px;
}

.fab-home {
  position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%);
  display: none; align-items: center; gap: 8px;
  background: var(--surface); border: 1px solid var(--border2); color: var(--text);
  padding: 11px 24px; border-radius: 50px;
  font-family: 'Tajawal', sans-serif; font-size: 14px; font-weight: 700;
  cursor: pointer; box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  transition: all 0.2s; z-index: 50;
  animation: fadeUp 0.3s ease;
}
.fab-home.show { display: flex; }
.fab-home:hover { background: var(--primary); border-color: var(--primary); transform: translateX(-50%) translateY(-3px); box-shadow: 0 12px 40px var(--primary-glow); }

.empty {
  text-align: center; padding: 4rem 2rem; color: var(--muted);
}
.empty i { font-size: 52px; display: block; margin-bottom: 1rem; opacity: 0.4; }
.empty p { font-size: 14px; }

.toast {
  position: fixed; bottom: 24px; right: 24px;
  background: var(--surface); border: 1px solid var(--border2);
  border-radius: 12px; padding: 12px 18px;
  display: flex; align-items: center; gap: 10px;
  font-size: 13.5px; font-weight: 600;
  box-shadow: 0 12px 40px rgba(0,0,0,0.4);
  z-index: 9999; animation: toastIn 0.3s ease;
  transform: translateX(0);
}
@keyframes toastIn { from{opacity:0;transform:translateX(20px)} to{opacity:1;transform:none} }
.toast.success { border-color: rgba(16,185,129,0.4); color: var(--green); }
.toast.error { border-color: rgba(239,68,68,0.4); color: var(--red); }

/* Profile panel */
.profile-panel {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--r); margin-bottom: 1.5rem;
  overflow: hidden; animation: fadeUp 0.35s ease;
}
.profile-header {
  padding: 1.5rem 1.6rem;
  background: linear-gradient(135deg, #040d1a 0%, #0f2040 60%, #1a3a6b 100%);
  border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 1.2rem;
  position: relative; overflow: hidden;
}
.profile-header::before {
  content: ''; position: absolute; top: -40px; left: -40px;
  width: 200px; height: 200px; border-radius: 50%;
  background: radial-gradient(circle, rgba(139,92,246,0.2), transparent 70%);
}
.profile-av {
  width: 64px; height: 64px; border-radius: 50%;
  background: rgba(139,92,246,0.15); border: 2px solid rgba(139,92,246,0.35);
  color: var(--violet); display: flex; align-items: center;
  justify-content: center; font-size: 28px; flex-shrink: 0;
  box-shadow: 0 0 20px rgba(139,92,246,0.25);
}
.profile-name { font-size: 17px; font-weight: 800; color: #fff; margin-bottom: 4px; }
.profile-sub { font-size: 12px; color: rgba(255,255,255,0.5); }
.profile-body { padding: 1.5rem 1.6rem; }
.readonly-notice {
  background: rgba(59,130,246,0.07); border: 1px solid rgba(59,130,246,0.18);
  border-radius: 8px; padding: 9px 14px; margin-bottom: 1.2rem;
  font-size: 12px; color: var(--muted2); display: flex; align-items: center; gap: 8px;
}
.editable-notice {
  background: rgba(139,92,246,0.07); border: 1px solid rgba(139,92,246,0.2);
  border-radius: 8px; padding: 9px 14px; margin: 1.2rem 0 1rem;
  font-size: 12px; color: var(--violet); display: flex; align-items: center; gap: 8px;
}

@media(max-width:768px) {
  .sg { grid-template-columns: 1fr 1fr; }
  .sb { display: none; } .main { margin-right: 0; }
  .ct { padding: 1rem 1rem 6rem; }
  .dg { grid-template-columns: 1fr; }
  .sp-body { grid-template-columns: 1fr 1fr; }
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--surface2); }
::-webkit-scrollbar-thumb { background: var(--surface3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }
</style>
</head>
<body>

<div class="orb orb-1"></div>
<div class="orb orb-2"></div>
<div class="orb orb-3"></div>

<!-- ═══ LOGIN ═══ -->
<div class="login-ov" id="loginOv">
  <div class="login-scene">
    <div class="login-box">
      <div class="login-logo">
        <div class="ic"><i class="bi bi-buildings-fill"></i></div>
        <h2>منظومة تدبير السكنيات الوظيفية والإدارية</h2>
        <p>مصلحة البناءات والتجهيز والممتلكات<br>المديرية الإقليمية إنزكان آيت ملول</p>
      </div>

      <div class="tabs-login">
        <button class="tab-btn on" onclick="switchLoginTab('login',this)">تسجيل الدخول</button>
        <button class="tab-btn" onclick="switchLoginTab('register',this)">طلب حساب جديد</button>
      </div>

      <!-- LOGIN -->
      <div id="loginForm">
        <div class="lf">
          <label>اسم المستخدم</label>
          <input type="text" id="liU" placeholder="admin" autocomplete="username"/>
        </div>
        <div class="lf">
          <label>كلمة المرور</label>
          <input type="password" id="liP" placeholder="••••••••" autocomplete="current-password"
                 onkeydown="if(event.key==='Enter')doLogin()"/>
        </div>
        <button class="btn-login" id="btnLogin" onclick="doLogin()">
          <i class="bi bi-arrow-left-circle"></i> دخول
        </button>
        <div class="login-err" id="liErr"></div>
      </div>

      <!-- REGISTER -->
      <div id="registerForm" style="display:none">
        <div class="lf">
          <label>الاسم الكامل (رئيس المؤسسة)</label>
          <input type="text" id="regName" placeholder="محمد أيت علي"/>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div class="lf">
            <label>كود GRESA</label>
            <input type="text" id="regGresa" placeholder="G123456"/>
          </div>
          <div class="lf">
            <label>رقم التأجير</label>
            <input type="text" id="regBail" placeholder="001"/>
          </div>
        </div>
        <div class="lf">
          <label>اسم المستخدم</label>
          <input type="text" id="regUser" placeholder="directeur_g123"/>
        </div>
        <div class="lf">
          <label>كلمة المرور</label>
          <input type="password" id="regPass" placeholder="كلمة مرور قوية"/>
        </div>
        <button class="btn-login" id="btnRegister" style="background:linear-gradient(135deg,#5b21b6,#8b5cf6);box-shadow:0 4px 20px rgba(139,92,246,0.35)" onclick="doRegister()">
          <i class="bi bi-person-plus"></i> إرسال الطلب
        </button>
        <div class="login-err" id="regErr"></div>
        <div class="login-ok" id="regOk"></div>
      </div>
    </div>
  </div>
</div>

<!-- ═══ SIDEBAR ═══ -->
<nav class="sb" id="sideNav">
  <div class="sb-logo"><i class="bi bi-buildings-fill"></i></div>
  <div class="ni on" id="navHome" onclick="goHome()"><i class="bi bi-house-door"></i><span class="nl">السكنيات</span></div>
  <div class="ni" onclick="showTab('stats',this)"><i class="bi bi-bar-chart-line"></i><span class="nl">الإحصائيات</span></div>
  <div class="ni" onclick="showTab('admin',this)" id="navAdmin" style="display:none"><i class="bi bi-shield-check"></i><span class="nl">إدارة المستخدمين</span></div>
  <div class="ni" onclick="showTab('profile',this)" id="navProfile" style="display:none"><i class="bi bi-person-circle"></i><span class="nl">ملفي الشخصي</span></div>
  <div class="ni bot logout" onclick="doLogout()"><i class="bi bi-box-arrow-left"></i><span class="nl">تسجيل الخروج</span></div>
</nav>

<!-- ═══ MAIN ═══ -->
<div class="main">
  <div class="tb">
    <div class="tb-brand">
      <div class="dot"></div>
      <div>
        <div class="tb-title">منظومة تدبير السكنيات الوظيفية والإدارية</div>
        <div class="tb-sub">الموسم الدراسي 2025/2026 — مصلحة البناءات والتجهيز والممتلكات</div>
      </div>
    </div>
    <div class="tb-right">
      <div class="uc-wrap" id="ucWrap">
        <div class="uc" onclick="toggleUserMenu()">
          <i class="bi bi-person-circle"></i>
          <span id="tbUser">—</span>
          <span class="role-badge" id="tbRole">—</span>
          <i class="bi bi-chevron-down arr"></i>
        </div>
        <div class="uc-menu" id="ucMenu">
          <div class="uc-menu-item"><i class="bi bi-person-badge"></i><span id="menuUserInfo">—</span></div>
          <div class="uc-menu-sep"></div>
          <div class="uc-menu-item" id="menuProfileLink" style="display:none" onclick="showTab('profile',null);document.getElementById('ucWrap').classList.remove('open')">
            <i class="bi bi-person-circle"></i><span>ملفي الشخصي</span>
          </div>
          <div class="uc-menu-sep" id="menuProfileSep" style="display:none"></div>
          <div class="uc-menu-item danger" onclick="doLogout()">
            <i class="bi bi-box-arrow-left"></i><span>تسجيل الخروج</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="ct">
    <!-- ══ STAT CARDS — 5 in same row ══ -->
    <div class="sg">
      <div class="sc c-blue">
        <div class="si b"><i class="bi bi-building"></i></div>
        <div><div class="sn" id="s1">—</div><div class="sl">المؤسسات</div></div>
      </div>
      <div class="sc c-blue">
        <div class="si b"><i class="bi bi-house-door"></i></div>
        <div><div class="sn" id="s2">—</div><div class="sl">إجمالي السكنيات</div></div>
      </div>
      <div class="sc c-green">
        <div class="si g"><i class="bi bi-person-check"></i></div>
        <div><div class="sn" id="s3">—</div><div class="sl">مستعملة للسكن</div></div>
      </div>
      <div class="sc c-amber clickable" onclick="openVacantModal()">
        <div class="si a"><i class="bi bi-house-x"></i></div>
        <div>
          <div class="sn" id="s4">—</div><div class="sl">شاغرة</div>
          <div class="sc-hint"><i class="bi bi-eye"></i> عرض القائمة</div>
        </div>
      </div>
      <!-- البطاقة الحمراء في نفس الصف -->
      <div class="sc c-red clickable" id="illegalCard" style="display:none" onclick="openIllegalModal()">
        <div class="si r"><i class="bi bi-exclamation-triangle"></i></div>
        <div>
          <div class="sn" id="s5" style="color:var(--red)">—</div>
          <div class="sl">سكنيات محتلة</div>
          <div class="sc-hint"><i class="bi bi-eye"></i> عرض القائمة</div>
        </div>
      </div>
    </div>

    <!-- HOME TAB -->
    <div id="tabHome">
      <div class="sb-box">
        <h2><i class="bi bi-search" style="color:var(--primary)"></i> البحث عن مؤسسة</h2>
        <div class="sw">
          <i class="bi bi-building ic"></i>
          <input type="text" id="si"
            placeholder="اسم المؤسسة — كود GRESA — اسم القاطن — الجماعة..."
            autocomplete="off" oninput="onSI()" onkeydown="onKey(event)"/>
          <div class="ac" id="ac"></div>
        </div>
      </div>
      <div id="res">
        <div class="empty">
          <i class="bi bi-search"></i>
          <p>ابحث عن مؤسسة لعرض السكنيات المرتبطة بها</p>
        </div>
      </div>
    </div>

    <!-- STATS TAB -->
    <div id="tabStats" style="display:none">
      <div class="stats-panel">
        <div class="sp-header"><i class="bi bi-bar-chart-line" style="color:var(--primary)"></i> لوحة الإحصائيات التفصيلية</div>
        <div class="sp-body" id="spBody">
          <div class="empty sp-full"><i class="bi bi-hourglass"></i><p>جاري التحميل...</p></div>
        </div>
      </div>
    </div>

    <!-- ADMIN TAB -->
    <div id="tabAdmin" style="display:none">
      <div class="admin-panel">
        <div class="admin-header">
          <h2><i class="bi bi-shield-check" style="color:var(--violet)"></i> إدارة حسابات مدراء المؤسسات</h2>
          <button class="btn-sm" onclick="loadAdminUsers()"><i class="bi bi-arrow-clockwise"></i> تحديث</button>
        </div>
        <div id="adminUsersList">
          <div class="empty"><i class="bi bi-people"></i><p>جاري التحميل...</p></div>
        </div>
      </div>
    </div>

    <!-- PROFILE TAB -->
    <div id="tabProfile" style="display:none">
      <div class="profile-panel">
        <div class="profile-header">
          <div class="profile-av"><i class="bi bi-person-circle"></i></div>
          <div>
            <div class="profile-name" id="profHeaderName">—</div>
            <div class="profile-sub" id="profHeaderGresa">—</div>
          </div>
        </div>
        <div class="profile-body" id="profileContent">
          <div class="empty"><i class="bi bi-hourglass"></i><p>جاري التحميل...</p></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- FAB -->
<button class="fab-home" id="fabHome" onclick="goHome()">
  <i class="bi bi-house-door-fill"></i> الرجوع للرئيسية
</button>

<!-- ═══ OCCUPANT MODAL ═══ -->
<div class="ov" id="ov" onclick="cmo(event)">
  <div class="mo" style="width:min(96%,700px)">
    <div class="moh">
      <h3 id="mt">معلومات القاطن</h3>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn-sm edit" id="btnEdit" onclick="toggleEditMode()" style="display:none">
          <i class="bi bi-pencil"></i> تعديل
        </button>
        <button class="cx" onclick="cmo()"><i class="bi bi-x-lg"></i></button>
      </div>
    </div>
    <div class="mob" id="mb"></div>
  </div>
</div>

<!-- ═══ VACANT MODAL ═══ -->
<div class="ov" id="ovVacant" onclick="closeVacant(event)">
  <div class="mo" style="width:min(98%,920px);max-height:92vh">
    <div class="moh" style="background:linear-gradient(135deg,#78350f,#d97706)">
      <h3 style="color:#fff;display:flex;align-items:center;gap:8px">
        <i class="bi bi-house-x"></i> السكنيات الشاغرة
        <span id="vacantCount" style="background:rgba(255,255,255,.2);padding:2px 10px;border-radius:20px;font-size:11px"></span>
      </h3>
      <button class="cx" onclick="closeVacant()" style="background:rgba(255,255,255,.15);color:#fff"><i class="bi bi-x-lg"></i></button>
    </div>
    <div style="padding:.75rem 1rem;border-bottom:1px solid var(--border);background:var(--surface2)">
      <div style="position:relative">
        <i class="bi bi-search" style="position:absolute;right:12px;top:50%;transform:translateY(-50%);color:var(--muted)"></i>
        <input type="text" id="vacantSearch" placeholder="بحث..." oninput="filterVacant()"
          style="width:100%;padding:8px 36px 8px 12px;border:1.5px solid var(--border2);border-radius:8px;font-family:'Tajawal',sans-serif;font-size:13.5px;background:var(--bg2);color:var(--text);outline:none"/>
      </div>
    </div>
    <div class="mob" id="mbVacant" style="padding:0"></div>
  </div>
</div>

<!-- ═══ ILLEGAL MODAL ═══ -->
<div class="ov" id="ovIllegal" onclick="closeIllegal(event)">
  <div class="mo" style="width:min(98%,920px);max-height:92vh">
    <div class="moh" style="background:linear-gradient(135deg,#7f1d1d,#ef4444)">
      <h3 style="color:#fff;display:flex;align-items:center;gap:8px">
        <i class="bi bi-exclamation-triangle"></i> السكنيات المحتلة
        <span id="illegalCount" style="background:rgba(255,255,255,.2);padding:2px 10px;border-radius:20px;font-size:11px"></span>
      </h3>
      <button class="cx" onclick="closeIllegal()" style="background:rgba(255,255,255,.15);color:#fff"><i class="bi bi-x-lg"></i></button>
    </div>
    <div style="padding:.75rem 1rem;border-bottom:1px solid var(--border);background:var(--surface2)">
      <div style="position:relative">
        <i class="bi bi-search" style="position:absolute;right:12px;top:50%;transform:translateY(-50%);color:var(--muted)"></i>
        <input type="text" id="illegalSearch" placeholder="بحث..." oninput="filterIllegal()"
          style="width:100%;padding:8px 36px 8px 12px;border:1.5px solid var(--border2);border-radius:8px;font-family:'Tajawal',sans-serif;font-size:13.5px;background:var(--bg2);color:var(--text);outline:none"/>
      </div>
    </div>
    <div class="mob" id="mbIllegal" style="padding:0"></div>
  </div>
</div>

<script>
/* ══ STATE ══ */
let _role = null, _canEdit = false, _currentH = null, _editMode = false;
let _vacantAll = [], _illegalAll = [];

/* ══ USER MENU ══ */
function toggleUserMenu(){ document.getElementById('ucWrap').classList.toggle('open'); }
document.addEventListener('click', e => {
  const w = document.getElementById('ucWrap');
  if(w && !w.contains(e.target)) w.classList.remove('open');
});

/* ══ LOGIN TAB SWITCH ══ */
function switchLoginTab(tab, el){
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('on'));
  el.classList.add('on');
  document.getElementById('loginForm').style.display    = tab==='login'    ? '' : 'none';
  document.getElementById('registerForm').style.display = tab==='register' ? '' : 'none';
}

/* ══ LOGIN ══ */
async function doLogin(){
  const u = document.getElementById('liU').value.trim();
  const p = document.getElementById('liP').value;
  if(!u || !p){ showErr('liErr','يرجى إدخال اسم المستخدم وكلمة المرور'); return; }
  const btn = document.getElementById('btnLogin');
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> جاري التحقق...';
  try {
    const r = await fetch('/api/login', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({username:u, password:p})
    });
    const d = await r.json();
    if(d.ok){
      document.getElementById('loginOv').classList.add('hidden');
      initApp(d);
    } else {
      showErr('liErr', d.msg || 'خطأ في تسجيل الدخول');
    }
  } catch(e){
    showErr('liErr','تعذر الاتصال بالخادم');
  }
  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-arrow-left-circle"></i> دخول';
}

/* ══ REGISTER ══ */
async function doRegister(){
  const name  = document.getElementById('regName').value.trim();
  const gresa = document.getElementById('regGresa').value.trim();
  const bail  = document.getElementById('regBail').value.trim();
  const uname = document.getElementById('regUser').value.trim();
  const pass  = document.getElementById('regPass').value;
  if(!name||!gresa||!bail||!uname||!pass){ showErr('regErr','يرجى ملء جميع الحقول'); return; }
  const btn = document.getElementById('btnRegister');
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> جاري الإرسال...';
  try {
    const r = await fetch('/api/register', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name, gresa, num_bail:bail, username:uname, password:pass})
    });
    const d = await r.json();
    if(d.ok){
      document.getElementById('regOk').textContent = d.msg;
      document.getElementById('regOk').style.display = 'block';
      document.getElementById('regErr').style.display = 'none';
    } else {
      showErr('regErr', d.msg);
      document.getElementById('regOk').style.display = 'none';
    }
  } catch(e){
    showErr('regErr','تعذر الاتصال بالخادم');
  }
  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-person-plus"></i> إرسال الطلب';
}

function showErr(id, m){
  const el = document.getElementById(id);
  el.textContent = m; el.style.display = 'block';
  setTimeout(()=>{ el.style.display='none'; }, 4500);
}

async function doLogout(){
  document.getElementById('ucWrap').classList.remove('open');
  await fetch('/api/logout', {method:'POST'});
  _role = null; _canEdit = false;
  document.getElementById('loginOv').classList.remove('hidden');
  document.getElementById('liP').value = '';
  hideFab(); goHome();
}

/* ══ INIT APP ══ */
function initApp(d){
  _role    = d.role;
  _canEdit = d.role === 'admin' || d.can_edit === true;
  document.getElementById('tbUser').textContent =
    d.role==='admin' ? 'مدير النظام' : (d.name || d.user || 'مدير المؤسسة');
  document.getElementById('tbRole').textContent = d.role==='admin' ? 'أدمين' : 'مؤسسة';
  document.getElementById('tbRole').className   = d.role==='admin' ? 'role-badge' : 'role-badge inst';
  document.getElementById('menuUserInfo').textContent = d.user || '';
  document.getElementById('navAdmin').style.display   = d.role==='admin'       ? '' : 'none';
  document.getElementById('navProfile').style.display = d.role==='institution' ? '' : 'none';
  document.getElementById('menuProfileLink').style.display = d.role==='institution' ? '' : 'none';
  document.getElementById('menuProfileSep').style.display  = d.role==='institution' ? '' : 'none';
  document.getElementById('illegalCard').style.display = '';
  document.getElementById('btnEdit').style.display = _canEdit ? '' : 'none';
  loadStats();
}

/* ══ STATS ══ */
async function loadStats(){
  try {
    const r = await fetch('/api/stats');
    if(r.status===401){ document.getElementById('loginOv').classList.remove('hidden'); return; }
    const d = await r.json();
    document.getElementById('s1').textContent = d.institutions  || 0;
    document.getElementById('s2').textContent = d.housing       || 0;
    document.getElementById('s3').textContent = d.occupied      || 0;
    document.getElementById('s4').textContent = d.vacant        || 0;
    document.getElementById('s5').textContent = d.occupied_illegal || 0;
    window._statsData = d;
    renderStats();
  } catch(e){ console.error('stats error', e); }
}

/* ══ AUTO-LOGIN CHECK ══ */
fetch('/api/me').then(r=>r.json()).then(d=>{
  if(d.logged){
    document.getElementById('loginOv').classList.add('hidden');
    initApp(d);
    if(d.role==='institution' && d.gresa){
      document.getElementById('si').value = d.gresa;
      onSI();
    }
  }
}).catch(e => console.error('me check error', e));

/* ══ TABS ══ */
let currentTab = 'home';
function showTab(t, el){
  ['Home','Stats','Admin','Profile'].forEach(x=>{
    document.getElementById('tab'+x).style.display = t===x.toLowerCase() ? '' : 'none';
  });
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('on'));
  if(el) el.classList.add('on');
  currentTab = t;
  if(t==='stats')   renderStats();
  if(t==='admin')   loadAdminUsers();
  if(t==='profile') loadProfile();
}

/* ══ FAB ══ */
function showFab(){ document.getElementById('fabHome').classList.add('show'); }
function hideFab(){ document.getElementById('fabHome').classList.remove('show'); }

function goHome(){
  document.getElementById('si').value = '';
  document.getElementById('res').innerHTML =
    '<div class="empty"><i class="bi bi-search"></i><p>ابحث عن مؤسسة لعرض السكنيات المرتبطة بها</p></div>';
  hideFab();
  ['Home','Stats','Admin','Profile'].forEach(x=>{
    document.getElementById('tab'+x).style.display = x==='Home' ? '' : 'none';
  });
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('on'));
  document.getElementById('navHome').classList.add('on');
  currentTab = 'home';
  window.scrollTo({top:0, behavior:'smooth'});
}

/* ══ RENDER STATS ══ */
function renderStats(){
  const d = window._statsData;
  if(!d){
    document.getElementById('spBody').innerHTML =
      '<div class="empty sp-full"><i class="bi bi-exclamation-circle"></i><p>لم يتم تحميل البيانات</p></div>';
    return;
  }
  const pctO=d.rate_occupied||0, pctV=d.rate_vacant||0, pctI=d.rate_illegal||0;
  const typeRows  = Object.entries(d.by_type||{}).map(([k,v])=>
    `<tr><td>${k}</td><td style="font-weight:700;color:var(--primary);font-family:'IBM Plex Mono',monospace">${v}</td></tr>`).join('');
  const statRows  = Object.entries(d.by_statut||{}).map(([k,v])=>
    `<tr><td>${k}</td><td style="font-weight:700;font-family:'IBM Plex Mono',monospace">${v}</td></tr>`).join('');
  document.getElementById('spBody').innerHTML = `
    <div class="sp-item">
      <div class="label">نسبة الاشغال</div>
      <div class="val" style="color:var(--green)">${pctO}%</div>
      <div class="sp-bar"><div class="sp-fill" style="width:${pctO}%;background:var(--green)"></div></div>
    </div>
    <div class="sp-item">
      <div class="label">نسبة الشغور</div>
      <div class="val" style="color:var(--amber)">${pctV}%</div>
      <div class="sp-bar"><div class="sp-fill" style="width:${pctV}%;background:var(--amber)"></div></div>
    </div>
    <div class="sp-item">
      <div class="label">السكنيات المحتلة</div>
      <div class="val" style="color:var(--red)">${pctI}%</div>
      <div class="sp-bar"><div class="sp-fill" style="width:${pctI}%;background:var(--red)"></div></div>
    </div>
    <div class="sp-item">
      <div class="label">الوسط الحضري / القروي</div>
      <div class="val" style="color:var(--primary)">${d.urban||0} <small style="font-size:14px;color:var(--muted)">/ ${d.rural||0}</small></div>
      <div class="sp-bar">
        <div class="sp-fill" style="width:${d.housing?Math.round((d.urban||0)/d.housing*100):0}%;background:var(--primary)"></div>
      </div>
    </div>
    <div class="sp-item sp-full">
      <div class="label">توزيع حسب نوع المؤسسة</div>
      <table class="sp-table" style="margin-top:8px">${typeRows||'<tr><td colspan="2">—</td></tr>'}</table>
    </div>
    <div class="sp-item sp-full">
      <div class="label">توزيع حسب وضعية السكن</div>
      <table class="sp-table" style="margin-top:8px">${statRows||'<tr><td colspan="2">—</td></tr>'}</table>
    </div>`;
}

/* ══ ADMIN USERS ══ */
async function loadAdminUsers(){
  document.getElementById('adminUsersList').innerHTML =
    '<div class="empty"><i class="bi bi-arrow-repeat" style="animation:spin 1s linear infinite"></i><p>جاري التحميل...</p></div>';
  const r = await fetch('/api/admin/users');
  if(r.status===401) return;
  const users = await r.json();
  if(!users.length){
    document.getElementById('adminUsersList').innerHTML =
      '<div class="empty"><i class="bi bi-people"></i><p>لا توجد طلبات حسابات بعد</p></div>';
    return;
  }
  const pending  = users.filter(u=>!u.approved);
  const approved = users.filter(u=> u.approved);

  let html = '';

  if(approved.length){
    const allNames = approved.map(u=>`'${u.username}'`).join(',');
    html += `
    <div class="bulk-bar">
      <span><i class="bi bi-people-fill"></i> تحديد الكل (${approved.length} مستخدم نشط):</span>
      <button class="btn-sm" style="background:var(--violet-bg);color:var(--violet);border-color:rgba(139,92,246,0.3)"
        onclick="setEditPerm([${allNames}], true)">
        <i class="bi bi-pencil-fill"></i> COCHER TOUS — منح التعديل للكل
      </button>
      <button class="btn-sm" style="background:var(--red-bg);color:var(--red);border-color:rgba(239,68,68,0.3)"
        onclick="setEditPerm([${allNames}], false)">
        <i class="bi bi-pencil-slash"></i> سحب التعديل من الكل
      </button>
    </div>`;
  }

  if(pending.length){
    html += `<div style="padding:.75rem 1.4rem;background:rgba(245,158,11,0.05);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--amber);text-transform:uppercase;letter-spacing:1px;display:flex;align-items:center;gap:6px"><i class="bi bi-clock"></i> طلبات في الانتظار (${pending.length})</div>`;
    pending.forEach(u => html += userRow(u));
  }
  if(approved.length){
    html += `<div style="padding:.75rem 1.4rem;background:rgba(16,185,129,0.05);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--green);text-transform:uppercase;letter-spacing:1px;display:flex;align-items:center;gap:6px"><i class="bi bi-check-circle"></i> حسابات نشطة (${approved.length})</div>`;
    approved.forEach(u => html += userRow(u));
  }
  document.getElementById('adminUsersList').innerHTML = html;
}

function userRow(u){
  const pending = !u.approved;
  const canEdit = u.can_edit;
  return `<div class="user-row">
    <div class="user-av" style="background:${pending?'var(--amber-bg)':'var(--green-bg)'};color:${pending?'var(--amber)':'var(--green)'}">
      <i class="bi bi-person"></i></div>
    <div class="user-info">
      <div class="user-name" style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
        ${u.name}
        ${pending?'<span class="pending-badge">في الانتظار</span>':''}
        ${(!pending && canEdit)?'<span class="edit-perm-badge"><i class="bi bi-pencil"></i> يملك التعديل</span>':''}
      </div>
      <div class="user-meta">
        <span style="font-family:'IBM Plex Mono',monospace">${u.username}</span>
        &nbsp;·&nbsp; GRESA: <b>${u.gresa}</b>
        &nbsp;·&nbsp; رقم التأجير: <b>${u.num_bail}</b>
        &nbsp;·&nbsp; <i class="bi bi-clock" style="font-size:10px"></i> ${u.created_at}
      </div>
    </div>
    <div class="user-actions">
      ${pending?`<button class="btn-sm btn-approve" onclick="adminAction('${u.username}','approve')"><i class="bi bi-check-lg"></i> موافقة</button>`:''}
      ${pending?`<button class="btn-sm btn-reject"  onclick="adminAction('${u.username}','reject')"><i class="bi bi-x-lg"></i> رفض</button>`
               :'<span style="font-size:11px;color:var(--green)"><i class="bi bi-check-circle-fill"></i> نشط</span>'}
      ${!pending ? `
        <button class="btn-sm" onclick="setEditPerm(['${u.username}'], ${!canEdit})"
          style="background:${canEdit?'var(--red-bg)':'var(--violet-bg)'};color:${canEdit?'var(--red)':'var(--violet)'};border-color:${canEdit?'rgba(239,68,68,0.3)':'rgba(139,92,246,0.3)'}">
          <i class="bi bi-pencil${canEdit?'-slash':''}"></i> ${canEdit?'سحب التعديل':'منح التعديل'}
        </button>` : ''}
      <button class="btn-sm" onclick="adminAction('${u.username}','delete')"
        style="background:var(--red-bg);color:var(--red);border-color:rgba(239,68,68,0.3)" title="حذف">
        <i class="bi bi-trash"></i></button>
    </div>
  </div>`;
}

async function setEditPerm(usernames, canEdit){
  const label = canEdit ? 'منح صلاحية التعديل' : 'سحب صلاحية التعديل';
  if(!confirm(`هل تريد ${label} لـ ${usernames.length} مستخدم؟`)) return;
  const r = await fetch('/api/admin/set_edit_permission', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({usernames, can_edit: canEdit})
  });
  const d = await r.json();
  if(d.ok){
    showToast(`تم ${label} لـ ${d.updated} مستخدم`, 'success');
    loadAdminUsers();
  } else {
    showToast('حدث خطأ', 'error');
  }
}

async function adminAction(username, action){
  if(action==='delete' && !confirm(`هل تريد حذف حساب "${username}"؟`)) return;
  const r = await fetch('/api/admin/approve',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({username, action})
  });
  const d = await r.json();
  if(d.ok){
    showToast(action==='approve'?'تمت الموافقة':action==='delete'?'تم الحذف':'تم الرفض','success');
    loadAdminUsers();
  }
}

/* ══ SEARCH ══ */
let tmr, aci=[], idx=-1;
function onSI(){
  clearTimeout(tmr);
  const q = document.getElementById('si').value.trim();
  if(q.length<1){ closeAC(); return; }
  tmr = setTimeout(()=>{
    fetch('/api/search?q='+encodeURIComponent(q))
      .then(r=>r.json())
      .then(items=>{
        aci=items; idx=-1;
        const ac=document.getElementById('ac');
        if(!items.length){ ac.style.display='none'; return; }
        ac.innerHTML=items.map((n,i)=>
          `<div class="aci" onmousedown="pick(${i})"><i class="bi bi-building"></i><span>${n}</span></div>`).join('');
        ac.style.display='block';
      });
  },180);
}
function pick(i){ document.getElementById('si').value=aci[i]; closeAC(); loadInst(aci[i]); }
function closeAC(){ document.getElementById('ac').style.display='none'; }
function onKey(e){
  const els=document.querySelectorAll('.aci');
  if(e.key==='ArrowDown')   { idx=Math.min(idx+1,els.length-1); hilite(els); }
  else if(e.key==='ArrowUp'){ idx=Math.max(idx-1,0);            hilite(els); }
  else if(e.key==='Enter'){
    if(idx>=0) pick(idx);
    else { const q=document.getElementById('si').value.trim(); if(aci.length===1)pick(0); else if(q)loadInst(q); }
  }
  else if(e.key==='Escape') closeAC();
}
function hilite(els){ els.forEach((el,i)=>el.classList.toggle('hi',i===idx)); }
document.addEventListener('click',e=>{ if(!e.target.closest('.sw')) closeAC(); });

/* ══ LOAD INSTITUTION ══ */
function loadInst(name){
  document.getElementById('res').innerHTML=
    '<div class="empty"><i class="bi bi-arrow-repeat" style="animation:spin 1s linear infinite;display:block;margin-bottom:.9rem;font-size:40px"></i><p>جاري التحميل...</p></div>';
  fetch('/api/institution?name='+encodeURIComponent(name))
    .then(r=>r.json())
    .then(data=>{
      if(data.error){ showEmptyRes('لم يتم العثور على المؤسسة'); return; }
      render(data); showFab();
    }).catch(()=>showEmptyRes('حدث خطأ أثناء التحميل'));
}
function showEmptyRes(msg){
  document.getElementById('res').innerHTML=
    `<div class="empty"><i class="bi bi-exclamation-circle"></i><p>${msg}</p></div>`;
}

/* ══ BADGE ══ */
function badge(s){
  s=s||'';
  if(/مستعمل|مشغول|مشغولة/.test(s)) return `<span class="badge bg">مستعمل للسكن</span>`;
  if(/محتل/.test(s))                 return `<span class="badge br">محتل</span>`;
  if(/شاغر|فارغ/.test(s))            return `<span class="badge ba">شاغر</span>`;
  if(/إصلاح|تعطل/.test(s))           return `<span class="badge bv">إصلاح</span>`;
  return `<span class="badge bx">${s||'—'}</span>`;
}

/* ══ RENDER INSTITUTION ══ */
function render(data){
  const {institution:inst, housing, stats} = data;
  const mc = inst.milieu==='قروي'
    ? '<span class="chip chip-w"><i class="bi bi-tree"></i>قروي</span>'
    : '<span class="chip chip-w"><i class="bi bi-buildings"></i>حضري</span>';

  const rows = housing.map((h,i)=>{
    const hj = JSON.stringify(h).replace(/'/g,"&#39;");
    const hasEdit = h._edit_log && h._edit_log.length;
    return `<tr class="hr" onclick='sd(${hj})'>
      <td style="color:var(--muted);font-size:11px;font-family:'IBM Plex Mono',monospace">${i+1}</td>
      <td style="font-weight:700;font-family:'IBM Plex Mono',monospace">${h.makhzani||'—'}</td>
      <td>${h.nature||'—'}</td>
      <td>${h.categorie||'—'}</td>
      <td>${h.etat||'—'}</td>
      <td>${badge(h.statut)}</td>
      <td>
        <div style="display:flex;gap:5px;align-items:center">
          <button class="btn-sm" onclick="event.stopPropagation();sd(${hj})"><i class="bi bi-eye"></i> القاطن</button>
          ${_canEdit?`<button class="btn-sm edit" onclick="event.stopPropagation();openEdit(${hj})"><i class="bi bi-pencil"></i></button>`:''}
          ${hasEdit?`<span style="width:8px;height:8px;border-radius:50%;background:var(--violet);display:inline-block" title="تم التعديل"></span>`:''}
        </div>
      </td>
    </tr>`;
  }).join('');

  document.getElementById('res').innerHTML = `
  <div class="inst-card">
    <div class="inst-header">
      <div class="inst-av"><i class="bi bi-building"></i></div>
      <div style="flex:1">
        <div class="inst-name">${inst.name}</div>
        <div class="inst-type">${inst.type}</div>
        <div class="inst-chips">
          ${mc}
          <span class="chip chip-w"><i class="bi bi-upc"></i>${inst.gresa}</span>
          <span class="chip chip-w"><i class="bi bi-geo-alt"></i>${inst.commune}</span>
        </div>
      </div>
    </div>
    <div class="inst-stats">
      <div class="ist"><div class="n" style="color:var(--primary)">${stats.total}</div><div class="l">إجمالي</div></div>
      <div class="ist"><div class="n" style="color:var(--green)">${stats.occupied}</div><div class="l">مستعمل للسكن</div></div>
      <div class="ist"><div class="n" style="color:var(--amber)">${stats.vacant}</div><div class="l">شاغر</div></div>
      <div class="ist"><div class="n" style="color:var(--red)">${stats.illegal||0}</div><div class="l">محتل</div></div>
      <div class="ist"><div class="n" style="color:var(--muted)">${stats.total-stats.occupied-stats.vacant-(stats.illegal||0)}</div><div class="l">أخرى</div></div>
    </div>
  </div>
  <div class="ic-card">
    <div class="card-title">
      <i class="bi bi-house-door" style="color:var(--primary)"></i> قائمة السكنيات
      <span class="card-title-count">${housing.length} سكنية</span>
    </div>
    <div class="tw"><table>
      <thead><tr>
        <th>#</th><th>الرقم المخزني</th><th>طبيعة السكن</th>
        <th>الصنف</th><th>الحالة</th><th>الوضعية</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
  </div>`;
}

/* ══ OCCUPANT MODAL ══ */
function sd(h){
  _currentH = h;
  _editMode = false;
  document.getElementById('mt').textContent = 'معلومات القاطن الحالي';
  document.getElementById('btnEdit').innerHTML = '<i class="bi bi-pencil"></i> تعديل';
  document.getElementById('btnEdit').style.display = _canEdit ? '' : 'none';
  renderOccupantView(h);
  document.getElementById('ov').classList.add('show');
}

function renderOccupantView(h){
  const occ=h.occupant||'', cadre=h.cadre||'', mission=h.mission||'';
  const statutOcc=h.statut_occ||'', numBail=h.num_bail||'';
  const typeAff=h.type_aff||'', dateOcc=h.date_occ||'', notes=h.notes||'';
  const hasOcc = occ.trim()!=='' && occ.trim()!=='—';
  const hasAny = hasOcc || cadre!=='—' || mission!=='—' || statutOcc!=='—' || numBail!=='—';

  const log = h._edit_log || [];
  const logHtml = log.length ? `
    <div class="sec-title"><i class="bi bi-clock-history"></i> سجل التعديلات (${log.length})</div>
    ${log.slice().reverse().map(e=>`
      <div class="log-entry">
        <div class="log-ts"><i class="bi bi-clock"></i> ${e.timestamp}</div>
        ${Object.entries(e.changes).map(([k,v])=>`<div><span class="log-field">${fieldLabel(k)}</span>: <span class="log-val">${v}</span></div>`).join('')}
      </div>`).join('')}` : '';

  if(!hasAny){
    document.getElementById('mb').innerHTML=`
      <div class="empty"><i class="bi bi-house-x" style="color:var(--amber)"></i><p>السكنية شاغرة — لا يوجد قاطن</p></div>
      ${logHtml}`;
    return;
  }
  const sub=[mission,cadre].filter(x=>x&&x!=='—').join(' — ');
  document.getElementById('mb').innerHTML=`
    <div class="occ-header">
      <div class="occ-av"><i class="bi bi-person"></i></div>
      <div><div class="occ-name">${hasOcc?occ:'غير محدد'}</div>${sub?`<div class="occ-sub">${sub}</div>`:''}</div>
    </div>
    <div class="sec-title"><i class="bi bi-person-badge"></i> المعلومات الوظيفية</div>
    <div class="dg">
      <div class="df full"><div class="dl">الاسم الكامل</div><div class="dv">${hasOcc?occ:'—'}</div></div>
      <div class="df"><div class="dl">الإطار</div><div class="dv">${cadre||'—'}</div></div>
      <div class="df"><div class="dl">المهمة</div><div class="dv">${mission||'—'}</div></div>
      <div class="df"><div class="dl">وضعية القاطن</div><div class="dv">${statutOcc||'—'}</div></div>
      <div class="df"><div class="dl">رقم التأجير</div><div class="dv">${numBail||'—'}</div></div>
      <div class="df"><div class="dl">نوع الإسناد</div><div class="dv">${typeAff||'—'}</div></div>
      <div class="df full"><div class="dl">تاريخ الإسناد</div><div class="dv">${dateOcc||'—'}</div></div>
    </div>
    <div class="sec-title"><i class="bi bi-house"></i> معلومات السكنية</div>
    <div class="dg">
      <div class="df"><div class="dl">الرقم المخزني</div><div class="dv">${h.makhzani||'—'}</div></div>
      <div class="df"><div class="dl">طبيعة السكن</div><div class="dv">${h.nature||'—'}</div></div>
      <div class="df"><div class="dl">صنف السكن</div><div class="dv">${h.categorie||'—'}</div></div>
      <div class="df"><div class="dl">حالة السكن</div><div class="dv">${h.etat||'—'}</div></div>
      <div class="df"><div class="dl">وضعية السكن</div><div class="dv">${badge(h.statut)}</div></div>
      ${notes&&notes!=='—'?`<div class="df full"><div class="dl">ملاحظات</div><div class="dv">${notes}</div></div>`:''}
    </div>
    ${logHtml}`;
}

/* ══ EDIT MODE ══ */
function openEdit(h){
  _currentH=h; _editMode=true;
  document.getElementById('mt').textContent='تعديل بيانات القاطن';
  document.getElementById('btnEdit').innerHTML='<i class="bi bi-eye"></i> عرض';
  renderEditForm(h);
  document.getElementById('ov').classList.add('show');
}

function toggleEditMode(){
  if(_editMode){
    _editMode=false;
    document.getElementById('mt').textContent='معلومات القاطن الحالي';
    document.getElementById('btnEdit').innerHTML='<i class="bi bi-pencil"></i> تعديل';
    renderOccupantView(_currentH);
  } else {
    _editMode=true;
    document.getElementById('mt').textContent='تعديل بيانات القاطن';
    document.getElementById('btnEdit').innerHTML='<i class="bi bi-eye"></i> عرض';
    renderEditForm(_currentH);
  }
}

function renderEditForm(h){
  const fields=['occupant','cadre','mission','statut_occ','num_bail','type_aff','date_occ','statut','notes'];
  document.getElementById('mb').innerHTML=`
    <div style="background:rgba(139,92,246,0.08);border:1px solid rgba(139,92,246,0.2);border-radius:10px;padding:10px 14px;margin-bottom:1rem;font-size:12px;color:var(--violet)">
      <i class="bi bi-info-circle"></i> سيتم تسجيل التعديل بالتاريخ والساعة تلقائياً
    </div>
    <div class="dg">
      ${fields.map(f=>`
        <div class="df ${f==='notes'||f==='occupant'?'full':''}">
          <div class="dl">${fieldLabel(f)}</div>
          <input class="ef-input" id="ef_${f}" value="${escHtml(h[f]||'')}" placeholder="${fieldLabel(f)}"/>
        </div>`).join('')}
    </div>
    <div style="display:flex;justify-content:flex-start;gap:10px;margin-top:1.2rem">
      <button class="btn-sm edit" onclick="saveEdit()" style="padding:9px 20px;font-size:14px">
        <i class="bi bi-check2"></i> حفظ التعديلات
      </button>
      <button class="btn-sm" onclick="toggleEditMode()" style="padding:9px 20px;font-size:14px">إلغاء</button>
    </div>`;
}

async function saveEdit(){
  const fields=['occupant','cadre','mission','statut_occ','num_bail','type_aff','date_occ','statut','notes'];
  const changes={};
  fields.forEach(f=>{
    const el=document.getElementById('ef_'+f);
    if(el && el.value!==(_currentH[f]||'') && !(el.value===''&&(_currentH[f]==='—'||!_currentH[f]))){
      changes[f]=el.value;
    }
  });
  if(!Object.keys(changes).length){ showToast('لا توجد تغييرات','error'); return; }
  const r=await fetch('/api/edit_occupant',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({gresa:_currentH.gresa, makhzani:_currentH.makhzani, fields:changes})
  });
  const d=await r.json();
  if(d.ok){
    Object.assign(_currentH, changes);
    if(!_currentH._edit_log) _currentH._edit_log=[];
    _currentH._edit_log.push({timestamp:d.timestamp, admin:_role==='admin'?'admin':'مدير المؤسسة', changes});
    showToast(`تم حفظ التعديلات — ${d.timestamp}`,'success');
    _editMode=false;
    document.getElementById('mt').textContent='معلومات القاطن الحالي';
    document.getElementById('btnEdit').innerHTML='<i class="bi bi-pencil"></i> تعديل';
    renderOccupantView(_currentH);
  } else { showToast(d.msg||'فشل الحفظ','error'); }
}

function fieldLabel(f){
  const m={occupant:'الاسم الكامل',cadre:'الإطار',mission:'المهمة',
    statut_occ:'وضعية القاطن',num_bail:'رقم التأجير',type_aff:'نوع الإسناد',
    date_occ:'تاريخ الإسناد',statut:'وضعية السكن',notes:'ملاحظات',
    makhzani:'الرقم المخزني',nature:'طبيعة السكن',categorie:'الصنف',
    etat:'الحالة',institution:'المؤسسة',gresa:'GRESA',commune:'الجماعة'};
  return m[f]||f;
}
function escHtml(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
function cmo(e){ if(!e||e.target===document.getElementById('ov')) document.getElementById('ov').classList.remove('show'); }

/* ══ VACANT MODAL ══ */
async function openVacantModal(){
  document.getElementById('ovVacant').classList.add('show');
  document.getElementById('mbVacant').innerHTML=
    '<div class="empty"><i class="bi bi-arrow-repeat" style="animation:spin 1s linear infinite;display:block;margin-bottom:.9rem;font-size:36px"></i><p>جاري التحميل...</p></div>';
  document.getElementById('vacantSearch').value='';
  const r=await fetch('/api/vacant');
  const d=await r.json();
  _vacantAll=d.vacant||[];
  document.getElementById('vacantCount').textContent=_vacantAll.length+' شاغرة';
  renderListTable(_vacantAll,'mbVacant');
}
function filterVacant(){
  const q=document.getElementById('vacantSearch').value.trim().toLowerCase();
  renderListTable(q?_vacantAll.filter(h=>JSON.stringify(h).toLowerCase().includes(q)):_vacantAll,'mbVacant');
}
function closeVacant(e){ if(!e||e.target===document.getElementById('ovVacant')) document.getElementById('ovVacant').classList.remove('show'); }

/* ══ ILLEGAL MODAL ══ */
async function openIllegalModal(){
  document.getElementById('ovIllegal').classList.add('show');
  document.getElementById('mbIllegal').innerHTML=
    '<div class="empty"><i class="bi bi-arrow-repeat" style="animation:spin 1s linear infinite;display:block;margin-bottom:.9rem;font-size:36px"></i><p>جاري التحميل...</p></div>';
  document.getElementById('illegalSearch').value='';
  const r=await fetch('/api/occupied_illegal');
  const d=await r.json();
  _illegalAll=d.illegal||[];
  document.getElementById('illegalCount').textContent=_illegalAll.length+' سكنية محتلة';
  renderListTable(_illegalAll,'mbIllegal');
}
function filterIllegal(){
  const q=document.getElementById('illegalSearch').value.trim().toLowerCase();
  renderListTable(q?_illegalAll.filter(h=>JSON.stringify(h).toLowerCase().includes(q)):_illegalAll,'mbIllegal');
}
function closeIllegal(e){ if(!e||e.target===document.getElementById('ovIllegal')) document.getElementById('ovIllegal').classList.remove('show'); }

function renderListTable(list, target){
  if(!list.length){
    document.getElementById(target).innerHTML='<div class="empty"><i class="bi bi-check-circle"></i><p>لا توجد نتائج</p></div>';
    return;
  }
  const rows=list.map((h,i)=>`
    <tr class="hr" onclick='sd(${JSON.stringify(h).replace(/'/g,"&#39;")})'>
      <td style="color:var(--muted);font-size:11px;font-family:'IBM Plex Mono',monospace">${i+1}</td>
      <td style="font-weight:700;font-size:12.5px">${h.institution||'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace;font-size:12px">${h.gresa||'—'}</td>
      <td>${h.commune||'—'}</td>
      <td style="font-family:'IBM Plex Mono',monospace">${h.makhzani||'—'}</td>
      <td>${h.nature||'—'}</td>
      <td>${h.categorie||'—'}</td>
      <td>${badge(h.statut)}</td>
    </tr>`).join('');
  document.getElementById(target).innerHTML=`
    <div style="overflow-x:auto"><table>
      <thead><tr><th>#</th><th>المؤسسة</th><th>GRESA</th><th>الجماعة</th><th>الرقم المخزني</th><th>الطبيعة</th><th>الصنف</th><th>الوضعية</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}

/* ══ PROFILE ══ */
async function loadProfile(){
  const r = await fetch('/api/profile');
  if(r.status===401) return;
  const d = await r.json();
  if(d.error) return;
  document.getElementById('profHeaderName').textContent = d.name || '—';
  document.getElementById('profHeaderGresa').textContent = 'GRESA: ' + (d.gresa||'—') + '  ·  رقم التأجير: ' + (d.num_bail||'—');
  document.getElementById('profileContent').innerHTML=`
    <div class="readonly-notice">
      <i class="bi bi-lock-fill" style="color:var(--primary)"></i>
      البيانات التالية للاطلاع فقط — لا يمكن تعديلها
    </div>
    <div class="dg" style="margin-bottom:0">
      <div class="df"><div class="dl">الاسم الكامل</div><div class="dv">${escHtml(d.name||'—')}</div></div>
      <div class="df"><div class="dl">كود GRESA</div><div class="dv" style="font-family:'IBM Plex Mono',monospace">${escHtml(d.gresa||'—')}</div></div>
      <div class="df"><div class="dl">رقم التأجير</div><div class="dv" style="font-family:'IBM Plex Mono',monospace">${escHtml(d.num_bail||'—')}</div></div>
      <div class="df"><div class="dl">الدور</div><div class="dv"><span class="badge bv"><i class="bi bi-person-badge"></i> مدير مؤسسة</span></div></div>
    </div>
    <div class="editable-notice">
      <i class="bi bi-pencil-square"></i>
      يمكنك تعديل معلومات الاتصال أدناه
    </div>
    <div class="dg">
      <div class="df">
        <div class="dl">رقم الهاتف</div>
        <input class="ef-input" id="profPhone" value="${escHtml(d.phone||'')}" placeholder="0600000000" type="tel"/>
      </div>
      <div class="df">
        <div class="dl">البريد الإلكتروني</div>
        <input class="ef-input" id="profEmail" value="${escHtml(d.email||'')}" placeholder="exemple@edu.gov.ma" type="email"/>
      </div>
    </div>
    <div style="margin-top:1.2rem;display:flex;gap:10px">
      <button class="btn-sm edit" onclick="saveProfile()" style="padding:9px 22px;font-size:14px">
        <i class="bi bi-check2-circle"></i> حفظ التغييرات
      </button>
    </div>`;
}

async function saveProfile(){
  const phone = document.getElementById('profPhone').value.trim();
  const email = document.getElementById('profEmail').value.trim();
  const r = await fetch('/api/profile',{
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({phone, email})
  });
  const d = await r.json();
  if(d.ok) showToast('تم حفظ معلومات الاتصال بنجاح','success');
  else showToast('حدث خطأ أثناء الحفظ','error');
}

/* ══ TOAST ══ */
function showToast(msg, type='success'){
  const t=document.createElement('div');
  t.className=`toast ${type}`;
  t.innerHTML=`<i class="bi bi-${type==='success'?'check-circle-fill':'exclamation-circle-fill'}"></i> ${msg}`;
  document.body.appendChild(t);
  setTimeout(()=>{ t.style.opacity='0'; t.style.transition='opacity 0.3s'; setTimeout(()=>t.remove(),300); },3500);
}
</script>
</body>
</html>"""

@app.route("/")
def index():
    from flask import Response
    return Response(HTML, mimetype='text/html')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
