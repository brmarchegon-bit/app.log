from flask import Flask, render_template_string, request, jsonify, session
import pandas as pd
import os, re, hashlib

app = Flask(__name__)
app.secret_key = "sakaniyet-2025-secret-key"

ADMIN_USER = "admin"
ADMIN_PASS = hashlib.sha256("admin2025".encode()).hexdigest()

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.xlsx")

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


def logged_in():
    return session.get("user") == ADMIN_USER


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    u = (data.get("username") or "").strip()
    p = hashlib.sha256((data.get("password") or "").encode()).hexdigest()
    if u == ADMIN_USER and p == ADMIN_PASS:
        session["user"] = u
        return jsonify({"ok": True})
    return jsonify({"ok": False, "msg": "اسم المستخدم أو كلمة المرور غير صحيحة"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def api_me():
    if logged_in():
        return jsonify({"logged": True, "user": ADMIN_USER})
    return jsonify({"logged": False})


@app.route("/api/stats")
def api_stats():
    if not logged_in():
        return jsonify({"error": "unauthorized"}), 401
    if DF.empty:
        return jsonify({"institutions": 0, "housing": 0, "occupied": 0, "vacant": 0})
    total    = len(DF)
    occupied = int(DF["statut"].str.contains("مستعمل|مشغول|محتل", na=False, regex=True).sum())
    vacant   = int(DF["statut"].str.contains("شاغر|فارغ",          na=False, regex=True).sum())
    urban    = int((DF["milieu"].str.contains("حضري", na=False)).sum())
    rural    = int((DF["milieu"].str.contains("قروي", na=False)).sum())
    by_type   = DF.groupby("type").size().to_dict()
    by_statut = DF.groupby("statut").size().to_dict()
    return jsonify({
        "institutions":  int(DF["institution"].nunique()),
        "housing":       total,
        "occupied":      occupied,
        "vacant":        vacant,
        "urban":         urban,
        "rural":         rural,
        "by_type":       by_type,
        "by_statut":     by_statut,
        "rate_occupied": round(occupied / total * 100, 1) if total else 0,
        "rate_vacant":   round(vacant   / total * 100, 1) if total else 0,
    })


@app.route("/api/search")
def api_search():
    if not logged_in():
        return jsonify({"error": "unauthorized"}), 401
    q = request.args.get("q", "").strip()
    if len(q) < 1:
        return jsonify([])
    ql = q.lower()
    mask = (
        DF["institution"].str.lower().str.contains(ql, na=False) |
        DF["gresa"].str.lower().str.contains(ql, na=False)       |
        DF["occupant"].str.lower().str.contains(ql, na=False)    |
        DF["commune"].str.lower().str.contains(ql, na=False)
    )
    names = DF[mask]["institution"].unique().tolist()
    return jsonify(names[:20])


@app.route("/api/institution")
def api_institution():
    if not logged_in():
        return jsonify({"error": "unauthorized"}), 401
    name = request.args.get("name", "").strip()
    rows = DF[DF["institution"] == name]
    if rows.empty:
        return jsonify({"error": "not found"}), 404
    info    = rows.iloc[0]
    housing = rows.to_dict(orient="records")
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
            "occupied": sum(1 for h in housing if re.search(r"مستعمل|مشغول|محتل", str(h.get("statut", "")))),
            "vacant":   sum(1 for h in housing if re.search(r"شاغر|فارغ",          str(h.get("statut", "")))),
        }
    })


# ── NEW: endpoint للسكنيات الشاغرة ──────────────────────────────────────────
@app.route("/api/vacant")
def api_vacant():
    if not logged_in():
        return jsonify({"error": "unauthorized"}), 401
    mask = DF["statut"].str.contains("شاغر|فارغ", na=False, regex=True)
    rows = DF[mask].to_dict(orient="records")
    return jsonify({"vacant": rows, "total": len(rows)})


HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>منظومة تدبير السكنيات الوظيفية والإدارية</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
<link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet"/>
<style>
:root{
  --bg:#f0f4fa;--surface:#fff;--surface2:#f5f7fb;
  --primary:#1a56db;--primary-lt:#e8f0fe;--primary-dk:#1547c0;
  --text:#1a1d23;--muted:#64748b;--border:#e2e8f0;
  --green:#059669;--green-bg:#ecfdf5;
  --amber:#d97706;--amber-bg:#fffbeb;
  --red:#dc2626;--red-bg:#fef2f2;
  --r:12px;--sh:0 2px 16px rgba(0,0,0,.07);
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Cairo',sans-serif;background:var(--bg);color:var(--text)}

/* ─── Sidebar ─── */
.sb{position:fixed;top:0;right:0;width:68px;height:100vh;
    background:#0f172a;display:flex;flex-direction:column;align-items:center;
    padding:1.2rem 0;gap:4px;z-index:20;transition:width .25s ease;overflow:hidden}
.sb:hover{width:220px}
.sb-logo{width:42px;height:42px;border-radius:10px;background:var(--primary);
         display:flex;align-items:center;justify-content:center;
         color:#fff;font-size:21px;margin-bottom:1.2rem;flex-shrink:0}
.ni{display:flex;align-items:center;gap:10px;width:100%;padding:10px 13px;
    color:#94a3b8;font-size:13.5px;font-weight:500;cursor:pointer;
    border-right:3px solid transparent;overflow:hidden;white-space:nowrap;
    transition:background .15s,color .15s;text-decoration:none}
.ni:hover,.ni.on{background:rgba(255,255,255,.07);color:#fff;border-right-color:var(--primary)}
.ni i{font-size:19px;flex-shrink:0;min-width:20px;text-align:center}
.nl{opacity:0;transition:opacity .18s .04s;white-space:nowrap}
.sb:hover .nl{opacity:1}
.ni.bot{margin-top:auto}
.ni.logout{color:#f87171}
.ni.logout:hover{background:rgba(248,113,113,.12);color:#f87171;border-right-color:#f87171}

/* ─── Main ─── */
.main{margin-right:68px;min-height:100vh;display:flex;flex-direction:column}

/* ─── Topbar ─── */
.tb{background:var(--surface);border-bottom:1px solid var(--border);
    padding:.9rem 2rem;display:flex;align-items:center;justify-content:space-between;
    position:sticky;top:0;z-index:10}
.tb-left div:first-child{font-size:17px;font-weight:800;color:var(--text)}
.tb-left div:last-child{font-size:11.5px;color:var(--muted);margin-top:2px}
.uc-wrap{position:relative}
.uc{display:flex;align-items:center;gap:8px;background:var(--primary-lt);
    padding:7px 16px;border-radius:50px;font-size:13px;font-weight:700;
    color:var(--primary);cursor:pointer;user-select:none;
    border:1.5px solid transparent;transition:border-color .15s,box-shadow .15s}
.uc:hover{border-color:var(--primary);box-shadow:0 0 0 3px rgba(26,86,219,.12)}
.uc i.arr{font-size:11px;margin-right:2px;transition:transform .2s}
.uc-wrap.open .uc i.arr{transform:rotate(180deg)}
.uc-menu{position:absolute;top:calc(100% + 8px);left:0;
         background:var(--surface);border:1px solid var(--border);
         border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,.12);
         min-width:180px;overflow:hidden;display:none;z-index:100;animation:fu .18s ease}
.uc-wrap.open .uc-menu{display:block}
.uc-menu-item{display:flex;align-items:center;gap:9px;padding:11px 15px;
              font-size:13px;font-weight:600;cursor:pointer;
              color:var(--text);transition:background .12s}
.uc-menu-item:hover{background:var(--surface2)}
.uc-menu-item.danger{color:var(--red)}
.uc-menu-item.danger:hover{background:var(--red-bg)}
.uc-menu-sep{height:1px;background:var(--border)}

.ct{padding:1.75rem 2rem 5rem;flex:1}

/* ─── Stat cards ─── */
.sg{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:1.75rem}
.sc{background:var(--surface);border-radius:var(--r);padding:1.1rem 1.4rem;
    border:1px solid var(--border);display:flex;align-items:center;gap:.9rem;
    transition:box-shadow .15s,transform .15s}
.sc.clickable{cursor:pointer}
.sc.clickable:hover{box-shadow:0 4px 20px rgba(0,0,0,.1);transform:translateY(-2px)}
.si{width:46px;height:46px;border-radius:10px;display:flex;align-items:center;
    justify-content:center;font-size:21px;flex-shrink:0}
.si.b{background:var(--primary-lt);color:var(--primary)}
.si.g{background:var(--green-bg);color:var(--green)}
.si.a{background:var(--amber-bg);color:var(--amber)}
.sn{font-size:25px;font-weight:700;line-height:1}
.sl{font-size:11.5px;color:var(--muted);margin-top:3px}
.sc-hint{font-size:10.5px;color:var(--primary);margin-top:4px;font-weight:600;display:none}
.sc.clickable:hover .sc-hint{display:block}

/* ─── Search box ─── */
.sb-box{background:var(--surface);border-radius:var(--r);border:1px solid var(--border);
        padding:1.5rem;margin-bottom:1.5rem}
.sb-box h2{font-size:15px;font-weight:700;margin-bottom:1rem;
           display:flex;align-items:center;gap:8px}
.sw{position:relative}
.sw .ic{position:absolute;right:13px;top:50%;transform:translateY(-50%);
        font-size:18px;color:var(--muted);pointer-events:none}
.sw input{width:100%;padding:12px 44px 12px 14px;
          border:1.5px solid var(--border);border-radius:10px;
          font-family:'Cairo',sans-serif;font-size:14.5px;
          background:var(--bg);color:var(--text);outline:none;
          transition:border-color .2s,box-shadow .2s}
.sw input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(26,86,219,.1)}
.ac{position:absolute;top:calc(100% + 5px);right:0;left:0;
    background:var(--surface);border:1px solid var(--border);
    border-radius:10px;box-shadow:var(--sh);z-index:99;display:none;
    max-height:260px;overflow-y:auto}
.aci{padding:10px 15px;cursor:pointer;font-size:13.5px;
     display:flex;align-items:center;gap:9px;border-bottom:1px solid var(--border)}
.aci:last-child{border-bottom:none}
.aci:hover,.aci.hi{background:var(--primary-lt);color:var(--primary)}
.aci i{color:var(--primary);font-size:15px;flex-shrink:0}

/* ─── Institution card ─── */
.inst-card{background:var(--surface);border-radius:var(--r);
           border:1px solid var(--border);margin-bottom:1.5rem;
           overflow:hidden;animation:fu .3s ease}
.inst-header{background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);
             padding:1.5rem;display:flex;align-items:flex-start;gap:1.2rem;flex-wrap:wrap}
.inst-av{width:60px;height:60px;border-radius:13px;
         background:rgba(255,255,255,.15);border:2px solid rgba(255,255,255,.25);
         color:#fff;display:flex;align-items:center;justify-content:center;
         font-size:26px;flex-shrink:0}
.inst-name{font-size:18px;font-weight:700;color:#fff;margin-bottom:4px}
.inst-type{font-size:12.5px;color:rgba(255,255,255,.65);margin-bottom:10px}
.inst-chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{display:inline-flex;align-items:center;gap:4px;
      padding:3px 9px;border-radius:20px;font-size:11.5px;font-weight:600}
.chip-w{background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.2)}
.inst-stats{display:flex;gap:0;border-top:1px solid var(--border)}
.ist{flex:1;text-align:center;padding:.9rem .5rem;border-left:1px solid var(--border)}
.ist:last-child{border-left:none}
.ist .n{font-size:22px;font-weight:700}
.ist .l{font-size:11px;color:var(--muted);margin-top:2px}

/* ─── Housing table ─── */
.ic-card{background:var(--surface);border-radius:var(--r);
         border:1px solid var(--border);margin-bottom:1.5rem;
         overflow:hidden;animation:fu .3s ease}
@keyframes fu{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
.card-title{padding:1rem 1.4rem;border-bottom:1px solid var(--border);
            font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.card-title-count{margin-right:auto;font-size:12px;font-weight:600;
                  color:var(--muted);background:var(--surface2);
                  padding:3px 10px;border-radius:20px}
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{padding:9px 14px;text-align:right;font-size:11.5px;color:var(--muted);
   font-weight:600;background:var(--surface2);border-bottom:1px solid var(--border)}
td{padding:11px 14px;font-size:13px;border-bottom:1px solid var(--border);vertical-align:middle}
tr:last-child td{border-bottom:none}
tr.hr:hover td{background:var(--primary-lt);cursor:pointer}
.badge{padding:3px 9px;border-radius:20px;font-size:11px;font-weight:700}
.bg{background:var(--green-bg);color:var(--green)}
.ba{background:var(--amber-bg);color:var(--amber)}
.br{background:var(--red-bg);color:var(--red)}
.bx{background:var(--surface2);color:var(--muted)}
.db{padding:5px 11px;border-radius:8px;border:1.5px solid var(--border);
    background:transparent;color:var(--muted);font-family:'Cairo',sans-serif;
    font-size:11.5px;cursor:pointer;transition:all .15s;white-space:nowrap}
.db:hover{background:var(--primary);color:#fff;border-color:var(--primary)}

/* ─── Stats Panel ─── */
.stats-panel{background:var(--surface);border-radius:var(--r);
             border:1px solid var(--border);margin-bottom:1.5rem;
             overflow:hidden;animation:fu .3s ease}
.sp-header{padding:1rem 1.4rem;border-bottom:1px solid var(--border);
           font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px}
.sp-body{padding:1.4rem;display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}
.sp-item{background:var(--surface2);border-radius:10px;padding:1rem 1.2rem}
.sp-item .label{font-size:11.5px;color:var(--muted);margin-bottom:8px;font-weight:600}
.sp-item .val{font-size:22px;font-weight:700}
.sp-bar{height:8px;border-radius:4px;background:var(--border);margin-top:8px;overflow:hidden}
.sp-fill{height:100%;border-radius:4px;transition:width .6s ease}
.sp-table{width:100%;border-collapse:collapse;font-size:13px}
.sp-table td{padding:6px 10px;border-bottom:1px solid var(--border)}
.sp-table tr:last-child td{border-bottom:none}
.sp-full{grid-column:1/-1}

/* ─── Vacant banner button ─── */
.vacant-btn{
  display:flex;align-items:center;gap:12px;
  background:linear-gradient(135deg,#92400e,#d97706);
  border-radius:var(--r);padding:1.1rem 1.5rem;
  cursor:pointer;margin-bottom:1.5rem;
  border:none;width:100%;font-family:'Cairo',sans-serif;
  color:#fff;text-align:right;transition:opacity .15s,transform .15s;
  box-shadow:0 4px 16px rgba(217,119,6,.3);animation:fu .3s ease}
.vacant-btn:hover{opacity:.92;transform:translateY(-2px)}
.vacant-btn i{font-size:28px;flex-shrink:0}
.vacant-btn .vb-text{flex:1}
.vacant-btn .vb-title{font-size:15px;font-weight:700}
.vacant-btn .vb-sub{font-size:12px;opacity:.85;margin-top:3px}
.vacant-btn .vb-arrow{font-size:22px;opacity:.7}

/* ─── Floating back-to-home button ─── */
.fab-home{
  position:fixed;bottom:28px;left:50%;transform:translateX(-50%);
  display:none;align-items:center;gap:8px;
  background:#0f172a;color:#fff;
  padding:11px 22px;border-radius:50px;
  font-family:'Cairo',sans-serif;font-size:14px;font-weight:700;
  cursor:pointer;border:none;
  box-shadow:0 6px 24px rgba(0,0,0,.25);
  transition:background .15s,transform .15s;z-index:50;
  animation:fu .3s ease}
.fab-home.show{display:flex}
.fab-home:hover{background:var(--primary);transform:translateX(-50%) translateY(-3px)}
.fab-home i{font-size:18px}

/* ─── Occupant modal ─── */
.ov{position:fixed;inset:0;background:rgba(15,23,42,.5);
    display:none;align-items:center;justify-content:center;z-index:200;
    backdrop-filter:blur(3px)}
.ov.show{display:flex}
.mo{background:var(--surface);border-radius:16px;
    width:min(92%,620px);max-height:87vh;
    display:flex;flex-direction:column;overflow:hidden;
    animation:mi .22s ease}
@keyframes mi{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:none}}
.moh{padding:1.1rem 1.4rem;border-bottom:1px solid var(--border);
     display:flex;align-items:center;justify-content:space-between}
.moh h3{font-size:15px;font-weight:700}
.cx{width:31px;height:31px;border-radius:7px;border:none;
    background:var(--surface2);color:var(--muted);font-size:17px;
    cursor:pointer;display:flex;align-items:center;justify-content:center;
    transition:background .15s}
.cx:hover{background:var(--red-bg);color:var(--red)}
.mob{padding:1.4rem;overflow-y:auto;flex:1}
.occ-header{background:linear-gradient(135deg,#0f172a,#1e3a8a);
            border-radius:12px;padding:1.1rem 1.3rem;
            margin-bottom:1rem;display:flex;align-items:center;gap:.9rem}
.occ-av{width:48px;height:48px;border-radius:50%;
        background:rgba(255,255,255,.15);border:2px solid rgba(255,255,255,.25);
        color:#fff;display:flex;align-items:center;justify-content:center;font-size:20px}
.occ-name{font-size:15px;font-weight:700;color:#fff}
.occ-sub{font-size:12px;color:rgba(255,255,255,.65);margin-top:2px}
.dg{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.df{background:var(--surface2);border-radius:9px;padding:.65rem .9rem}
.df .dl{font-size:10.5px;color:var(--muted);margin-bottom:3px;font-weight:600}
.df .dv{font-size:13.5px;font-weight:600;color:var(--text);word-break:break-word}
.df.full{grid-column:1/-1}
.sec-title{font-size:12px;font-weight:700;color:var(--muted);
           text-transform:uppercase;letter-spacing:.5px;
           margin:1rem 0 .6rem;display:flex;align-items:center;gap:6px}

/* ─── Login ─── */
.login-ov{position:fixed;inset:0;
          background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 60%,#1a56db 100%);
          display:flex;align-items:center;justify-content:center;z-index:999}
.login-ov.hidden{display:none}
.login-box{background:#fff;border-radius:20px;padding:2.5rem;
           width:min(92%,440px);box-shadow:0 24px 64px rgba(0,0,0,.35)}
.login-logo{text-align:center;margin-bottom:1.8rem}
.login-logo .ic{width:64px;height:64px;border-radius:15px;background:var(--primary-lt);
                color:var(--primary);font-size:28px;display:flex;align-items:center;
                justify-content:center;margin:0 auto .9rem}
.login-logo h2{font-size:16px;font-weight:800;margin-bottom:6px;line-height:1.4}
.login-logo p{font-size:12px;color:var(--muted);line-height:1.6}
.lf{margin-bottom:1rem}
.lf label{display:block;font-size:12.5px;font-weight:600;color:var(--muted);margin-bottom:5px}
.lf input{width:100%;padding:11px 13px;border:1.5px solid var(--border);
          border-radius:9px;font-family:'Cairo',sans-serif;font-size:14px;
          outline:none;transition:border-color .2s}
.lf input:focus{border-color:var(--primary);box-shadow:0 0 0 3px rgba(26,86,219,.1)}
.btn-login{width:100%;padding:12px;background:var(--primary);color:#fff;
           border:none;border-radius:9px;font-family:'Cairo',sans-serif;
           font-size:15px;font-weight:700;cursor:pointer;margin-top:.5rem;
           transition:background .2s}
.btn-login:hover{background:var(--primary-dk)}
.login-err{color:var(--red);font-size:12.5px;margin-top:.6rem;
           text-align:center;display:none}

.empty{text-align:center;padding:3.5rem;color:var(--muted)}
.empty i{font-size:48px;display:block;margin-bottom:.9rem;color:var(--border)}
.empty p{font-size:14px}

@media(max-width:700px){
  .sg{grid-template-columns:1fr 1fr}
  .sb{display:none}.main{margin-right:0}
  .ct{padding:1rem 1rem 5rem}
  .dg{grid-template-columns:1fr}
  .sp-body{grid-template-columns:1fr 1fr}
}
</style>
</head>
<body>

<!-- LOGIN -->
<div class="login-ov" id="loginOv">
  <div class="login-box">
    <div class="login-logo">
      <div class="ic"><i class="bi bi-buildings-fill"></i></div>
      <h2>منظومة تدبير السكنيات الوظيفية والإدارية</h2>
      <p>مصلحة البناءات والتجهيز والممتلكات<br>المديرية الإقليمية إنزكان آيت ملول</p>
    </div>
    <div class="lf">
      <label>اسم المستخدم</label>
      <input type="text" id="liU" placeholder="admin" autocomplete="username"/>
    </div>
    <div class="lf">
      <label>كلمة المرور</label>
      <input type="password" id="liP" placeholder="••••••••" autocomplete="current-password"
             onkeydown="if(event.key==='Enter')doLogin()"/>
    </div>
    <button class="btn-login" onclick="doLogin()">
      <i class="bi bi-box-arrow-in-right"></i> تسجيل الدخول
    </button>
    <div class="login-err" id="liErr"></div>
  </div>
</div>

<!-- SIDEBAR -->
<nav class="sb">
  <div class="sb-logo"><i class="bi bi-buildings-fill"></i></div>
  <div class="ni on" onclick="showTab('home',this)"><i class="bi bi-house-door"></i><span class="nl">السكنيات</span></div>
  <div class="ni" onclick="showTab('stats',this)"><i class="bi bi-bar-chart-line"></i><span class="nl">الإحصائيات</span></div>
  <div class="ni bot logout" onclick="doLogout()"><i class="bi bi-box-arrow-left"></i><span class="nl">تسجيل الخروج</span></div>
</nav>

<!-- MAIN -->
<div class="main">
  <div class="tb">
    <div class="tb-left">
      <div>منظومة تدبير السكنيات الوظيفية والإدارية</div>
      <div>الموسم الدراسي 2025 / 2026 — مصلحة البناءات والتجهيز والممتلكات</div>
    </div>
    <div class="uc-wrap" id="ucWrap">
      <div class="uc" onclick="toggleUserMenu()">
        <i class="bi bi-person-circle"></i>
        <span id="tbUser">—</span>
        <i class="bi bi-chevron-down arr"></i>
      </div>
      <div class="uc-menu" id="ucMenu">
        <div class="uc-menu-item"><i class="bi bi-person-badge"></i><span>مدير النظام</span></div>
        <div class="uc-menu-sep"></div>
        <div class="uc-menu-item danger" onclick="doLogout()">
          <i class="bi bi-box-arrow-left"></i><span>تسجيل الخروج</span>
        </div>
      </div>
    </div>
  </div>

  <div class="ct">
    <!-- STAT CARDS -->
    <div class="sg">
      <div class="sc"><div class="si b"><i class="bi bi-building"></i></div>
        <div><div class="sn" id="s1">—</div><div class="sl">مجموع المؤسسات</div></div></div>
      <div class="sc"><div class="si b"><i class="bi bi-house-door"></i></div>
        <div><div class="sn" id="s2">—</div><div class="sl">مجموع السكنيات</div></div></div>
      <div class="sc"><div class="si g"><i class="bi bi-person-check"></i></div>
        <div><div class="sn" id="s3">—</div><div class="sl">مشغولة</div></div></div>
      <!-- كارد الشاغرة قابل للضغط -->
      <div class="sc clickable" onclick="openVacantModal()" title="اضغط لعرض قائمة الشاغرة">
        <div class="si a"><i class="bi bi-house-x"></i></div>
        <div>
          <div class="sn" id="s4">—</div>
          <div class="sl">شاغرة</div>
          <div class="sc-hint"><i class="bi bi-arrow-left-circle"></i> عرض التفاصيل</div>
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
            placeholder="اكتب اسم المؤسسة أو كود GRESA أو اسم القاطن أو الجماعة..."
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
          <div class="empty sp-full"><i class="bi bi-hourglass-split"></i><p>جاري التحميل...</p></div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ═══ FLOATING BACK-TO-HOME BUTTON ═══ -->
<button class="fab-home" id="fabHome" onclick="goHome()">
  <i class="bi bi-house-door-fill"></i>
  الرجوع للصفحة الرئيسية
</button>

<!-- ═══ OCCUPANT MODAL ═══ -->
<div class="ov" id="ov" onclick="cmo(event)">
  <div class="mo">
    <div class="moh">
      <h3 id="mt">تفاصيل القاطن الحالي</h3>
      <button class="cx" onclick="cmo()"><i class="bi bi-x-lg"></i></button>
    </div>
    <div class="mob" id="mb"></div>
  </div>
</div>

<!-- ═══ VACANT MODAL ═══ -->
<div class="ov" id="ovVacant" onclick="closeVacant(event)">
  <div class="mo" style="width:min(96%,860px);max-height:90vh">
    <div class="moh" style="background:linear-gradient(135deg,#92400e,#d97706);border-radius:0">
      <h3 style="color:#fff;display:flex;align-items:center;gap:8px">
        <i class="bi bi-house-x"></i>
        <span>قائمة السكنيات الشاغرة</span>
        <span id="vacantCount" style="background:rgba(255,255,255,.2);padding:2px 10px;border-radius:20px;font-size:12px;margin-right:6px"></span>
      </h3>
      <button class="cx" onclick="closeVacant()" style="background:rgba(255,255,255,.15);color:#fff">
        <i class="bi bi-x-lg"></i>
      </button>
    </div>
    <div style="padding:.75rem 1rem;border-bottom:1px solid var(--border);background:var(--surface2)">
      <div style="position:relative">
        <i class="bi bi-search" style="position:absolute;right:12px;top:50%;transform:translateY(-50%);color:var(--muted)"></i>
        <input type="text" id="vacantSearch"
          placeholder="بحث داخل الشاغرة..." oninput="filterVacant()"
          style="width:100%;padding:8px 36px 8px 12px;border:1.5px solid var(--border);
                 border-radius:8px;font-family:'Cairo',sans-serif;font-size:13.5px;
                 background:var(--surface);outline:none"/>
      </div>
    </div>
    <div class="mob" id="mbVacant" style="padding:0"></div>
  </div>
</div>

<script>
/* ══ USER MENU ══ */
function toggleUserMenu(){
  document.getElementById('ucWrap').classList.toggle('open');
}
document.addEventListener('click', e => {
  const w = document.getElementById('ucWrap');
  if(w && !w.contains(e.target)) w.classList.remove('open');
});

/* ══ AUTH ══ */
async function doLogin(){
  const u = document.getElementById('liU').value.trim();
  const p = document.getElementById('liP').value;
  const btn = document.querySelector('.btn-login');
  btn.disabled = true; btn.textContent = 'جاري التحقق...';
  try{
    const r = await fetch('/api/login',{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({username:u, password:p})
    });
    const d = await r.json();
    if(d.ok){
      document.getElementById('loginOv').classList.add('hidden');
      document.getElementById('tbUser').textContent = u;
      initApp();
    } else { showErr(d.msg || 'خطأ في تسجيل الدخول'); }
  } catch(e){ showErr('تعذر الاتصال بالخادم'); }
  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-box-arrow-in-right"></i> تسجيل الدخول';
}
function showErr(m){
  const el = document.getElementById('liErr');
  el.textContent = m; el.style.display = 'block';
  setTimeout(() => el.style.display='none', 3500);
}
async function doLogout(){
  document.getElementById('ucWrap').classList.remove('open');
  await fetch('/api/logout', {method:'POST'});
  document.getElementById('loginOv').classList.remove('hidden');
  document.getElementById('liP').value = '';
  document.getElementById('liU').value = '';
  hideFab();
}

/* ══ INIT ══ */
async function initApp(){
  const r = await fetch('/api/stats');
  if(r.status === 401){ document.getElementById('loginOv').classList.remove('hidden'); return; }
  const d = await r.json();
  document.getElementById('s1').textContent = d.institutions;
  document.getElementById('s2').textContent = d.housing;
  document.getElementById('s3').textContent = d.occupied;
  document.getElementById('s4').textContent = d.vacant;
  window._statsData = d;
}
fetch('/api/me').then(r => r.json()).then(d => {
  if(d.logged){
    document.getElementById('loginOv').classList.add('hidden');
    document.getElementById('tbUser').textContent = d.user;
    initApp();
  }
});

/* ══ TABS ══ */
let currentTab = 'home';
function showTab(t, el){
  document.getElementById('tabHome').style.display  = t==='home'  ? '' : 'none';
  document.getElementById('tabStats').style.display = t==='stats' ? '' : 'none';
  document.querySelectorAll('.ni').forEach(n => n.classList.remove('on'));
  if(el) el.classList.add('on');
  currentTab = t;
  if(t === 'stats') renderStats();
  // إخفاء زر الرجوع عند التبويب الرئيسي وعرض نتيجة فارغة
  if(t === 'home' && document.getElementById('res').querySelector('.empty')) hideFab();
}

/* ══ FAB HOME BUTTON ══ */
function showFab(){ document.getElementById('fabHome').classList.add('show'); }
function hideFab(){ document.getElementById('fabHome').classList.remove('show'); }
function goHome(){
  // مسح البحث والنتيجة
  document.getElementById('si').value = '';
  document.getElementById('res').innerHTML =
    '<div class="empty"><i class="bi bi-search"></i><p>ابحث عن مؤسسة لعرض السكنيات المرتبطة بها</p></div>';
  hideFab();
  // التأكد من أننا في تاب home
  if(currentTab !== 'home'){
    showTab('home', document.querySelector('.ni'));
  }
  window.scrollTo({top:0, behavior:'smooth'});
}

/* ══ STATS ══ */
function renderStats(){
  const d = window._statsData;
  if(!d){
    document.getElementById('spBody').innerHTML =
      '<div class="empty sp-full"><i class="bi bi-exclamation-circle"></i><p>لم يتم تحميل البيانات بعد</p></div>';
    return;
  }
  const pctO = d.rate_occupied || 0, pctV = d.rate_vacant || 0;
  const typeRows  = Object.entries(d.by_type  ||{}).map(([k,v])=>
    `<tr><td>${k}</td><td style="font-weight:700;color:var(--primary)">${v}</td></tr>`).join('');
  const statRows = Object.entries(d.by_statut||{}).map(([k,v])=>
    `<tr><td>${k}</td><td style="font-weight:700">${v}</td></tr>`).join('');
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
      <div class="label">الوسط الحضري / القروي</div>
      <div class="val" style="color:var(--primary)">${d.urban||0}
        <small style="font-size:13px;color:var(--muted)">/ ${d.rural||0}</small></div>
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

/* ══ SEARCH ══ */
let tmr, aci=[], idx=-1;
function onSI(){
  clearTimeout(tmr);
  const q = document.getElementById('si').value.trim();
  if(q.length<1){ closeAC(); return; }
  tmr = setTimeout(()=>{
    fetch('/api/search?q='+encodeURIComponent(q))
      .then(r=>r.json()).then(items=>{
        aci=items; idx=-1;
        const ac = document.getElementById('ac');
        if(!items.length){ ac.style.display='none'; return; }
        ac.innerHTML = items.map((n,i)=>
          `<div class="aci" onmousedown="pick(${i})">
             <i class="bi bi-building"></i><span>${n}</span>
           </div>`).join('');
        ac.style.display='block';
      });
  },180);
}
function pick(i){
  document.getElementById('si').value = aci[i];
  closeAC(); loadInst(aci[i]);
}
function closeAC(){ document.getElementById('ac').style.display='none'; }
function onKey(e){
  const els = document.querySelectorAll('.aci');
  if(e.key==='ArrowDown')    { idx=Math.min(idx+1,els.length-1); hilite(els); }
  else if(e.key==='ArrowUp') { idx=Math.max(idx-1,0);            hilite(els); }
  else if(e.key==='Enter'){
    if(idx>=0){ pick(idx); }
    else{ const q=document.getElementById('si').value.trim();
          if(aci.length===1) pick(0); else if(q) loadInst(q); }
  }
  else if(e.key==='Escape') closeAC();
}
function hilite(els){ els.forEach((el,i)=>el.classList.toggle('hi',i===idx)); }
document.addEventListener('click', e=>{
  if(!e.target.closest('.sw')) closeAC();
});

/* ══ LOAD INSTITUTION ══ */
function loadInst(name){
  document.getElementById('res').innerHTML =
    '<div class="empty"><i class="bi bi-arrow-repeat" style="animation:spin 1s linear infinite;display:block;margin-bottom:.9rem;font-size:40px"></i><p>جاري التحميل...</p></div>';
  fetch('/api/institution?name='+encodeURIComponent(name))
    .then(r=>r.json()).then(data=>{
      if(data.error){ showEmpty('لم يتم العثور على المؤسسة'); return; }
      render(data);
      showFab(); // ← إظهار زر الرجوع
    }).catch(()=>showEmpty('حدث خطأ أثناء التحميل'));
}
function showEmpty(msg){
  document.getElementById('res').innerHTML =
    `<div class="empty"><i class="bi bi-exclamation-circle"></i><p>${msg}</p></div>`;
}

/* ══ BADGE ══ */
function badge(s){
  s = s||'';
  if(/مستعمل|مشغول/.test(s)) return `<span class="badge bg">مشغول</span>`;
  if(/محتل/.test(s))          return `<span class="badge br">محتل</span>`;
  if(/شاغر|فارغ/.test(s))     return `<span class="badge ba">شاغر</span>`;
  if(/إصلاح|تعطل/.test(s))    return `<span class="badge br">جاري الإصلاح</span>`;
  return `<span class="badge bx">${s||'—'}</span>`;
}

/* ══ RENDER INSTITUTION ══ */
function render(data){
  const {institution:inst, housing, stats} = data;
  const mc = inst.milieu==='قروي'
    ? '<span class="chip chip-w"><i class="bi bi-tree"></i>قروي</span>'
    : '<span class="chip chip-w"><i class="bi bi-buildings"></i>حضري</span>';
  const rows = housing.map((h,i)=>`
    <tr class="hr" onclick='sd(${JSON.stringify(h).replace(/'/g,"&#39;")})'>
      <td style="color:var(--muted);font-size:11px">${i+1}</td>
      <td style="font-weight:600">${h.makhzani||'—'}</td>
      <td>${h.nature||'—'}</td>
      <td>${h.categorie||'—'}</td>
      <td>${h.etat||'—'}</td>
      <td>${badge(h.statut)}</td>
      <td><button class="db" onclick="event.stopPropagation();sd(${JSON.stringify(h).replace(/'/g,"&#39;")})">
        <i class="bi bi-person"></i> القاطن
      </button></td>
    </tr>`).join('');
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
      <div class="ist"><div class="n" style="color:var(--primary)">${stats.total}</div><div class="l">إجمالي السكنيات</div></div>
      <div class="ist"><div class="n" style="color:var(--green)">${stats.occupied}</div><div class="l">مشغولة</div></div>
      <div class="ist"><div class="n" style="color:var(--amber)">${stats.vacant}</div><div class="l">شاغرة</div></div>
      <div class="ist"><div class="n" style="color:var(--muted)">${stats.total-stats.occupied-stats.vacant}</div><div class="l">أخرى</div></div>
    </div>
  </div>
  <div class="ic-card">
    <div class="card-title">
      <i class="bi bi-house-door" style="color:var(--primary)"></i> قائمة السكنيات
      <span class="card-title-count">${housing.length} سكنية</span>
    </div>
    <div class="tw">
      <table>
        <thead><tr>
          <th>#</th><th>الرقم المخزني</th><th>طبيعة السكن</th>
          <th>الصنف</th><th>الحالة</th><th>الوضعية</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  </div>`;
}

/* ══ OCCUPANT MODAL ══ */
function sd(h){
  const occ=h.occupant||'', cadre=h.cadre||'', mission=h.mission||'';
  const statutOcc=h.statut_occ||'', numBail=h.num_bail||'';
  const typeAff=h.type_aff||'', dateOcc=h.date_occ||'', notes=h.notes||'';
  const hasOcc = occ.trim() !== '' && occ.trim() !== '—';
  const hasAny = hasOcc || cadre!=='—' || mission!=='—' || statutOcc!=='—' || numBail!=='—';
  document.getElementById('mt').textContent = 'معلومات القاطن الحالي';
  let body = '';
  if(!hasAny){
    body = `<div class="empty">
      <i class="bi bi-house-x" style="color:var(--amber)"></i>
      <p>هذه السكنية شاغرة — لا يوجد قاطن حالي</p>
    </div>`;
  } else {
    const sub = [mission,cadre].filter(x=>x&&x!=='—').join(' — ');
    body = `
    <div class="occ-header">
      <div class="occ-av"><i class="bi bi-person"></i></div>
      <div><div class="occ-name">${hasOcc?occ:'غير محدد'}</div>
           ${sub?`<div class="occ-sub">${sub}</div>`:''}</div>
    </div>
    <div class="sec-title"><i class="bi bi-person-badge"></i> المعلومات الوظيفية</div>
    <div class="dg">
      <div class="df"><div class="dl">الاسم الكامل</div><div class="dv">${hasOcc?occ:'—'}</div></div>
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
    </div>`;
  }
  document.getElementById('mb').innerHTML = body;
  document.getElementById('ov').classList.add('show');
}
function cmo(e){
  if(!e||e.target===document.getElementById('ov'))
    document.getElementById('ov').classList.remove('show');
}

/* ══ VACANT MODAL ══ */
let _vacantAll = [];

async function openVacantModal(){
  document.getElementById('ovVacant').classList.add('show');
  document.getElementById('mbVacant').innerHTML =
    '<div class="empty"><i class="bi bi-arrow-repeat" style="animation:spin 1s linear infinite;display:block;margin-bottom:.9rem;font-size:36px"></i><p>جاري التحميل...</p></div>';
  document.getElementById('vacantSearch').value = '';
  try{
    const r = await fetch('/api/vacant');
    const d = await r.json();
    _vacantAll = d.vacant || [];
    document.getElementById('vacantCount').textContent = _vacantAll.length + ' سكنية شاغرة';
    renderVacantTable(_vacantAll);
  } catch(e){
    document.getElementById('mbVacant').innerHTML =
      '<div class="empty"><i class="bi bi-exclamation-circle"></i><p>حدث خطأ أثناء التحميل</p></div>';
  }
}

function filterVacant(){
  const q = document.getElementById('vacantSearch').value.trim().toLowerCase();
  if(!q){ renderVacantTable(_vacantAll); return; }
  const filtered = _vacantAll.filter(h =>
    (h.institution||'').toLowerCase().includes(q) ||
    (h.makhzani||'').toLowerCase().includes(q)    ||
    (h.commune||'').toLowerCase().includes(q)     ||
    (h.nature||'').toLowerCase().includes(q)
  );
  renderVacantTable(filtered);
}

function renderVacantTable(list){
  if(!list.length){
    document.getElementById('mbVacant').innerHTML =
      '<div class="empty"><i class="bi bi-house-check"></i><p>لا توجد نتائج مطابقة</p></div>';
    return;
  }
  const rows = list.map((h,i)=>`
    <tr class="hr" onclick='sd(${JSON.stringify(h).replace(/'/g,"&#39;")})' title="اضغط لعرض التفاصيل">
      <td style="color:var(--muted);font-size:11px">${i+1}</td>
      <td style="font-weight:600;font-size:13px">${h.institution||'—'}</td>
      <td>${h.gresa||'—'}</td>
      <td>${h.commune||'—'}</td>
      <td>${h.makhzani||'—'}</td>
      <td>${h.nature||'—'}</td>
      <td>${h.categorie||'—'}</td>
      <td>${h.etat||'—'}</td>
      <td><span class="badge ba">شاغر</span></td>
    </tr>`).join('');
  document.getElementById('mbVacant').innerHTML = `
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>#</th><th>المؤسسة</th><th>GRESA</th><th>الجماعة</th>
          <th>الرقم المخزني</th><th>الطبيعة</th><th>الصنف</th><th>الحالة</th><th>الوضعية</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function closeVacant(e){
  if(!e||e.target===document.getElementById('ovVacant'))
    document.getElementById('ovVacant').classList.remove('show');
}
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)