import streamlit as st
import pandas as pd
import os
import re
import hashlib

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="منظومة تدبير السكنيات الوظيفية والإدارية",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Auth ────────────────────────────────────────────────────────────────────
ADMIN_USER = "admin"
ADMIN_PASS = hashlib.sha256("admin2025".encode()).hexdigest()

# ─── Column Mapping ──────────────────────────────────────────────────────────
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

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.xlsx")


def normalize(s):
    return re.sub(r'\s+', ' ', str(s).strip())


@st.cache_data
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


# ─── CSS Styling ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');
@import url('https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css');

:root {
  --primary: #1a56db;
  --primary-lt: #e8f0fe;
  --green: #059669;
  --green-bg: #ecfdf5;
  --amber: #d97706;
  --amber-bg: #fffbeb;
  --red: #dc2626;
  --red-bg: #fef2f2;
  --muted: #64748b;
  --border: #e2e8f0;
  --surface2: #f5f7fb;
  --r: 12px;
}

html, body, [class*="css"] {
  font-family: 'Cairo', sans-serif !important;
  direction: rtl;
}

/* Hide default Streamlit elements */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

/* Topbar */
.top-bar {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
  border-radius: 14px;
  padding: 1.1rem 1.6rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.4rem;
  color: #fff;
}
.top-bar-title { font-size: 17px; font-weight: 800; }
.top-bar-sub { font-size: 11.5px; color: rgba(255,255,255,.65); margin-top: 3px; }
.top-bar-user {
  background: rgba(255,255,255,.15);
  border: 1px solid rgba(255,255,255,.25);
  border-radius: 50px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 700;
}

/* Stat cards */
.stat-card {
  background: #fff;
  border-radius: var(--r);
  padding: 1.1rem 1.3rem;
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: .9rem;
  margin-bottom: .5rem;
}
.stat-icon {
  width: 46px; height: 46px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 21px; flex-shrink: 0;
}
.si-blue { background: var(--primary-lt); color: var(--primary); }
.si-green { background: var(--green-bg); color: var(--green); }
.si-amber { background: var(--amber-bg); color: var(--amber); }
.stat-num { font-size: 26px; font-weight: 700; line-height: 1; }
.stat-label { font-size: 11.5px; color: var(--muted); margin-top: 3px; }

/* Badges */
.badge {
  padding: 3px 9px; border-radius: 20px;
  font-size: 11px; font-weight: 700; display: inline-block;
}
.badge-green { background: var(--green-bg); color: var(--green); }
.badge-amber { background: var(--amber-bg); color: var(--amber); }
.badge-red { background: var(--red-bg); color: var(--red); }
.badge-gray { background: var(--surface2); color: var(--muted); }

/* Section header */
.sec-header {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--r);
  padding: 1.3rem 1.5rem;
  margin-bottom: 1.2rem;
}
.sec-header h3 {
  font-size: 15px; font-weight: 700;
  margin: 0 0 4px 0;
  display: flex; align-items: center; gap: 8px;
}

/* Institution header */
.inst-header {
  background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
  border-radius: var(--r) var(--r) 0 0;
  padding: 1.4rem;
  color: #fff;
}
.inst-name { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
.inst-type { font-size: 12px; color: rgba(255,255,255,.65); margin-bottom: 10px; }
.chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 9px; border-radius: 20px; font-size: 11.5px; font-weight: 600;
  background: rgba(255,255,255,.15); color: #fff;
  border: 1px solid rgba(255,255,255,.2);
  margin-left: 6px; margin-bottom: 4px;
}

/* Stats row inside inst card */
.inst-stats {
  display: flex;
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 var(--r) var(--r);
  background: #fff;
  margin-bottom: 1.2rem;
  overflow: hidden;
}
.ist {
  flex: 1; text-align: center; padding: .9rem .5rem;
  border-left: 1px solid var(--border);
}
.ist:last-child { border-left: none; }
.ist .n { font-size: 22px; font-weight: 700; }
.ist .l { font-size: 11px; color: var(--muted); margin-top: 2px; }

/* Occupant detail box */
.occ-box {
  background: var(--surface2);
  border-radius: 10px;
  padding: 1rem 1.2rem;
  margin-bottom: .75rem;
}
.occ-label { font-size: 11px; color: var(--muted); font-weight: 600; margin-bottom: 3px; }
.occ-value { font-size: 14px; font-weight: 600; }

/* Progress bar */
.prog-bar {
  height: 8px; border-radius: 4px;
  background: var(--border); overflow: hidden; margin-top: 8px;
}
.prog-fill { height: 100%; border-radius: 4px; }

/* Sidebar nav */
.sidebar-logo {
  text-align: center;
  padding: 1rem 0;
  margin-bottom: .5rem;
}
.sidebar-logo .icon {
  width: 52px; height: 52px;
  background: var(--primary);
  border-radius: 12px;
  display: inline-flex; align-items: center; justify-content: center;
  color: #fff; font-size: 24px; margin-bottom: .5rem;
}
.sidebar-logo h4 {
  font-size: 13px; font-weight: 700; margin: 0;
}

/* Login form wrapper */
.login-wrap {
  max-width: 420px;
  margin: 4rem auto;
  background: #fff;
  border-radius: 20px;
  padding: 2.5rem;
  border: 1px solid var(--border);
  box-shadow: 0 8px 40px rgba(0,0,0,.1);
}
.login-wrap h2 {
  font-size: 17px; font-weight: 800;
  text-align: center; margin-bottom: .4rem;
}
.login-wrap p {
  font-size: 12px; color: var(--muted);
  text-align: center; margin-bottom: 1.5rem;
}

.dataframe-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th {
  padding: 9px 14px; text-align: right;
  font-size: 11.5px; color: var(--muted);
  font-weight: 600; background: var(--surface2);
  border-bottom: 1px solid var(--border);
}
td {
  padding: 10px 14px; font-size: 13px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--primary-lt); }

/* Streamlit overrides */
div[data-testid="stTextInput"] > div > div > input {
  text-align: right !important;
  font-family: 'Cairo', sans-serif !important;
}
div[data-testid="stSelectbox"] select {
  text-align: right !important;
  font-family: 'Cairo', sans-serif !important;
}
.stButton > button {
  font-family: 'Cairo', sans-serif !important;
  font-weight: 700 !important;
  border-radius: 9px !important;
  direction: rtl;
}
/* Sidebar */
section[data-testid="stSidebar"] {
  direction: rtl;
}
</style>
""", unsafe_allow_html=True)


# ─── Session State ───────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "page" not in st.session_state:
    st.session_state.page = "home"
if "selected_institution" not in st.session_state:
    st.session_state.selected_institution = None


# ─── Helper Functions ─────────────────────────────────────────────────────────
def badge_html(s):
    s = s or ""
    if re.search(r"مستعمل|مشغول", s):
        return '<span class="badge badge-green">مشغول</span>'
    if re.search(r"محتل", s):
        return '<span class="badge badge-red">محتل</span>'
    if re.search(r"شاغر|فارغ", s):
        return '<span class="badge badge-amber">شاغر</span>'
    if re.search(r"إصلاح|تعطل", s):
        return '<span class="badge badge-red">جاري الإصلاح</span>'
    return f'<span class="badge badge-gray">{s or "—"}</span>'


def stat_card(icon, num, label, color_class="si-blue"):
    st.markdown(f"""
    <div class="stat-card">
      <div class="stat-icon {color_class}">{icon}</div>
      <div>
        <div class="stat-num">{num}</div>
        <div class="stat-label">{label}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Login Screen ─────────────────────────────────────────────────────────────
def show_login():
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] {
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 60%, #1a56db 100%);
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding: 2rem 0 1rem;">
          <div style="width:64px;height:64px;background:#1a56db;border-radius:15px;
                      display:inline-flex;align-items:center;justify-content:center;
                      font-size:28px;color:#fff;margin-bottom:.8rem;">🏢</div>
          <h2 style="color:#fff;font-size:18px;font-weight:800;margin:0 0 .4rem;">
            منظومة تدبير السكنيات الوظيفية والإدارية
          </h2>
          <p style="color:rgba(255,255,255,.65);font-size:12px;line-height:1.6;">
            مصلحة البناءات والتجهيز والممتلكات<br>
            المديرية الإقليمية إنزكان آيت ملول
          </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            st.markdown('<p style="color:#fff;font-size:13px;font-weight:600;margin-bottom:4px;">اسم المستخدم</p>', unsafe_allow_html=True)
            username = st.text_input("", placeholder="admin", label_visibility="collapsed")
            st.markdown('<p style="color:#fff;font-size:13px;font-weight:600;margin-bottom:4px;">كلمة المرور</p>', unsafe_allow_html=True)
            password = st.text_input("", type="password", placeholder="••••••••", label_visibility="collapsed")
            submitted = st.form_submit_button("🔐  تسجيل الدخول", use_container_width=True)

        if submitted:
            p_hash = hashlib.sha256(password.encode()).hexdigest()
            if username == ADMIN_USER and p_hash == ADMIN_PASS:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.rerun()
            else:
                st.error("❌  اسم المستخدم أو كلمة المرور غير صحيحة")


# ─── Main App ─────────────────────────────────────────────────────────────────
def show_app():
    # Load data
    try:
        df = load_data()
        data_ok = True
    except Exception as e:
        df = pd.DataFrame()
        data_ok = False
        st.error(f"⚠️ خطأ في تحميل البيانات: {e}")

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-logo">
          <div class="icon">🏢</div>
          <h4>منظومة السكنيات</h4>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🏠  السكنيات", use_container_width=True,
                     type="primary" if st.session_state.page == "home" else "secondary"):
            st.session_state.page = "home"
            st.session_state.selected_institution = None
            st.rerun()

        if st.button("📊  الإحصائيات", use_container_width=True,
                     type="primary" if st.session_state.page == "stats" else "secondary"):
            st.session_state.page = "stats"
            st.rerun()

        if st.button("🏚️  السكنيات الشاغرة", use_container_width=True,
                     type="primary" if st.session_state.page == "vacant" else "secondary"):
            st.session_state.page = "vacant"
            st.rerun()

        st.markdown("---")
        if st.button("🚪  تسجيل الخروج", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.page = "home"
            st.session_state.selected_institution = None
            st.rerun()

        st.markdown(f"""
        <div style="margin-top:1rem;padding:.7rem;background:var(--primary-lt);
                    border-radius:9px;text-align:center;font-size:12px;font-weight:700;color:var(--primary);">
          👤 {st.session_state.username}
        </div>
        """, unsafe_allow_html=True)

    # ── Topbar ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="top-bar">
      <div>
        <div class="top-bar-title">منظومة تدبير السكنيات الوظيفية والإدارية</div>
        <div class="top-bar-sub">الموسم الدراسي 2025 / 2026 — مصلحة البناءات والتجهيز والممتلكات</div>
      </div>
      <div class="top-bar-user">👤 {st.session_state.username}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Stats Cards (always visible) ─────────────────────────────────────────
    if data_ok and not df.empty:
        total = len(df)
        institutions = df["institution"].nunique()
        occupied = int(df["statut"].str.contains("مستعمل|مشغول|محتل", na=False, regex=True).sum())
        vacant = int(df["statut"].str.contains("شاغر|فارغ", na=False, regex=True).sum())

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            stat_card("🏫", institutions, "مجموع المؤسسات", "si-blue")
        with c2:
            stat_card("🏠", total, "مجموع السكنيات", "si-blue")
        with c3:
            stat_card("✅", occupied, "مشغولة", "si-green")
        with c4:
            stat_card("🔑", vacant, "شاغرة", "si-amber")

    # ── PAGE: Home ────────────────────────────────────────────────────────────
    if st.session_state.page == "home":
        st.markdown("""
        <div class="sec-header">
          <h3>🔍 البحث عن مؤسسة</h3>
        </div>
        """, unsafe_allow_html=True)

        if data_ok and not df.empty:
            institutions_list = sorted(df["institution"].unique().tolist())

            search_q = st.text_input(
                "", placeholder="اكتب اسم المؤسسة أو كود GRESA أو الجماعة...",
                label_visibility="collapsed", key="search_input"
            )

            if search_q.strip():
                ql = search_q.strip().lower()
                mask = (
                    df["institution"].str.lower().str.contains(ql, na=False) |
                    df["gresa"].str.lower().str.contains(ql, na=False)       |
                    df["commune"].str.lower().str.contains(ql, na=False)     |
                    df["occupant"].str.lower().str.contains(ql, na=False)
                )
                matches = df[mask]["institution"].unique().tolist()

                if matches:
                    selected = st.selectbox(
                        "اختر مؤسسة:", matches, index=0,
                        label_visibility="visible"
                    )
                    if selected:
                        st.session_state.selected_institution = selected
                else:
                    st.info("🔍 لم يتم العثور على نتائج")
                    st.session_state.selected_institution = None
            else:
                selected_from_list = st.selectbox(
                    "أو اختر من القائمة:", ["— اختر مؤسسة —"] + institutions_list,
                    label_visibility="visible", key="inst_select"
                )
                if selected_from_list != "— اختر مؤسسة —":
                    st.session_state.selected_institution = selected_from_list
                elif not search_q:
                    st.session_state.selected_institution = None

            # ── Show institution detail ───────────────────────────────────────
            inst_name = st.session_state.selected_institution
            if inst_name:
                rows = df[df["institution"] == inst_name]
                if not rows.empty:
                    info = rows.iloc[0]
                    milieu = info.get("milieu", "—")
                    milieu_icon = "🌳 قروي" if "قروي" in str(milieu) else "🏙️ حضري"

                    total_h = len(rows)
                    occ_h = int(rows["statut"].str.contains("مستعمل|مشغول|محتل", na=False, regex=True).sum())
                    vac_h = int(rows["statut"].str.contains("شاغر|فارغ", na=False, regex=True).sum())
                    other_h = total_h - occ_h - vac_h

                    st.markdown(f"""
                    <div class="inst-header">
                      <div style="display:flex;align-items:flex-start;gap:1.2rem;flex-wrap:wrap;">
                        <div style="width:56px;height:56px;border-radius:12px;
                                    background:rgba(255,255,255,.15);border:2px solid rgba(255,255,255,.25);
                                    color:#fff;display:flex;align-items:center;justify-content:center;
                                    font-size:24px;flex-shrink:0;">🏫</div>
                        <div>
                          <div class="inst-name">{info['institution']}</div>
                          <div class="inst-type">{info.get('type','—')}</div>
                          <span class="chip">{milieu_icon}</span>
                          <span class="chip">📋 {info.get('gresa','—')}</span>
                          <span class="chip">📍 {info.get('commune','—')}</span>
                        </div>
                      </div>
                    </div>
                    <div class="inst-stats">
                      <div class="ist"><div class="n" style="color:var(--primary)">{total_h}</div><div class="l">إجمالي السكنيات</div></div>
                      <div class="ist"><div class="n" style="color:var(--green)">{occ_h}</div><div class="l">مشغولة</div></div>
                      <div class="ist"><div class="n" style="color:var(--amber)">{vac_h}</div><div class="l">شاغرة</div></div>
                      <div class="ist"><div class="n" style="color:var(--muted)">{other_h}</div><div class="l">أخرى</div></div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Housing table
                    st.markdown(f"""
                    <div style="background:#fff;border:1px solid var(--border);border-radius:var(--r);
                                padding:1rem 1.4rem .5rem;margin-bottom:1rem;">
                      <div style="font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px;
                                  justify-content:space-between;margin-bottom:.8rem;">
                        <span>🏠 قائمة السكنيات</span>
                        <span style="font-size:12px;font-weight:600;color:var(--muted);
                                     background:var(--surface2);padding:3px 10px;border-radius:20px;">
                          {len(rows)} سكنية
                        </span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Build HTML table
                    table_rows = ""
                    for i, (_, h) in enumerate(rows.iterrows()):
                        table_rows += f"""
                        <tr>
                          <td style="color:var(--muted);font-size:11px">{i+1}</td>
                          <td style="font-weight:600">{h.get('makhzani','—')}</td>
                          <td>{h.get('nature','—')}</td>
                          <td>{h.get('categorie','—')}</td>
                          <td>{h.get('etat','—')}</td>
                          <td>{badge_html(h.get('statut',''))}</td>
                          <td>{h.get('occupant','—')}</td>
                        </tr>"""

                    st.markdown(f"""
                    <div style="background:#fff;border:1px solid var(--border);border-radius:var(--r);overflow:hidden;margin-bottom:1rem;">
                      <div style="overflow-x:auto">
                        <table>
                          <thead><tr>
                            <th>#</th><th>الرقم المخزني</th><th>طبيعة السكن</th>
                            <th>الصنف</th><th>الحالة</th><th>الوضعية</th><th>القاطن الحالي</th>
                          </tr></thead>
                          <tbody>{table_rows}</tbody>
                        </table>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Expanders for occupant details
                    st.markdown("#### 👤 تفاصيل القاطنين")
                    for i, (_, h) in enumerate(rows.iterrows()):
                        occ = h.get('occupant', '—')
                        label = f"{i+1}. {occ} — {h.get('makhzani','—')}"
                        with st.expander(label):
                            c1, c2 = st.columns(2)
                            fields_left = [
                                ("الاسم الكامل", h.get('occupant','—')),
                                ("الإطار", h.get('cadre','—')),
                                ("المهمة", h.get('mission','—')),
                                ("وضعية القاطن", h.get('statut_occ','—')),
                            ]
                            fields_right = [
                                ("رقم التأجير", h.get('num_bail','—')),
                                ("نوع الإسناد", h.get('type_aff','—')),
                                ("تاريخ الإسناد", h.get('date_occ','—')),
                                ("وضعية السكن", badge_html(h.get('statut',''))),
                            ]
                            with c1:
                                for lbl, val in fields_left:
                                    st.markdown(f"""
                                    <div class="occ-box">
                                      <div class="occ-label">{lbl}</div>
                                      <div class="occ-value">{val}</div>
                                    </div>""", unsafe_allow_html=True)
                            with c2:
                                for lbl, val in fields_right:
                                    st.markdown(f"""
                                    <div class="occ-box">
                                      <div class="occ-label">{lbl}</div>
                                      <div class="occ-value">{val}</div>
                                    </div>""", unsafe_allow_html=True)
                            notes = h.get('notes','—')
                            if notes and notes != '—':
                                st.markdown(f"""
                                <div class="occ-box" style="grid-column:1/-1">
                                  <div class="occ-label">ملاحظات</div>
                                  <div class="occ-value">{notes}</div>
                                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="text-align:center;padding:3rem;color:var(--muted);">
                  <div style="font-size:48px;margin-bottom:.9rem;">🔍</div>
                  <p style="font-size:14px;">ابحث عن مؤسسة أو اختر من القائمة لعرض السكنيات المرتبطة بها</p>
                </div>
                """, unsafe_allow_html=True)

    # ── PAGE: Stats ───────────────────────────────────────────────────────────
    elif st.session_state.page == "stats":
        st.markdown("""
        <div style="font-size:18px;font-weight:800;margin-bottom:1.2rem;">
          📊 لوحة الإحصائيات التفصيلية
        </div>
        """, unsafe_allow_html=True)

        if data_ok and not df.empty:
            total = len(df)
            occupied = int(df["statut"].str.contains("مستعمل|مشغول|محتل", na=False, regex=True).sum())
            vacant = int(df["statut"].str.contains("شاغر|فارغ", na=False, regex=True).sum())
            urban = int(df["milieu"].str.contains("حضري", na=False).sum())
            rural = int(df["milieu"].str.contains("قروي", na=False).sum())
            pct_o = round(occupied / total * 100, 1) if total else 0
            pct_v = round(vacant / total * 100, 1) if total else 0
            pct_u = round(urban / total * 100, 0) if total else 0

            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"""
                <div class="stat-card" style="flex-direction:column;align-items:flex-start;">
                  <div class="occ-label">نسبة الاشغال</div>
                  <div class="stat-num" style="color:var(--green)">{pct_o}%</div>
                  <div class="prog-bar" style="width:100%">
                    <div class="prog-fill" style="width:{pct_o}%;background:var(--green)"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="stat-card" style="flex-direction:column;align-items:flex-start;">
                  <div class="occ-label">نسبة الشغور</div>
                  <div class="stat-num" style="color:var(--amber)">{pct_v}%</div>
                  <div class="prog-bar" style="width:100%">
                    <div class="prog-fill" style="width:{pct_v}%;background:var(--amber)"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            with c3:
                st.markdown(f"""
                <div class="stat-card" style="flex-direction:column;align-items:flex-start;">
                  <div class="occ-label">الوسط الحضري / القروي</div>
                  <div class="stat-num" style="color:var(--primary)">{urban}
                    <small style="font-size:14px;color:var(--muted)"> / {rural}</small>
                  </div>
                  <div class="prog-bar" style="width:100%">
                    <div class="prog-fill" style="width:{pct_u}%;background:var(--primary)"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)

            with c1:
                st.markdown("**توزيع حسب نوع المؤسسة**")
                by_type = df.groupby("type").size().reset_index(name="عدد السكنيات")
                by_type.columns = ["نوع المؤسسة", "عدد السكنيات"]
                st.dataframe(by_type, use_container_width=True, hide_index=True)

            with c2:
                st.markdown("**توزيع حسب وضعية السكن**")
                by_statut = df.groupby("statut").size().reset_index(name="عدد")
                by_statut.columns = ["الوضعية", "العدد"]
                st.dataframe(by_statut, use_container_width=True, hide_index=True)

            # Charts
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**مخطط الوضعية**")
                chart_data = pd.DataFrame({
                    "الوضعية": ["مشغولة", "شاغرة", "أخرى"],
                    "العدد": [occupied, vacant, total - occupied - vacant]
                })
                st.bar_chart(chart_data.set_index("الوضعية"))
            with c2:
                st.markdown("**مخطط الوسط**")
                milieu_data = pd.DataFrame({
                    "الوسط": ["حضري", "قروي"],
                    "العدد": [urban, rural]
                })
                st.bar_chart(milieu_data.set_index("الوسط"))

    # ── PAGE: Vacant ──────────────────────────────────────────────────────────
    elif st.session_state.page == "vacant":
        if data_ok and not df.empty:
            vacant_df = df[df["statut"].str.contains("شاغر|فارغ", na=False, regex=True)].copy()

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,#92400e,#d97706);
                        border-radius:var(--r);padding:1.1rem 1.5rem;
                        color:#fff;margin-bottom:1.2rem;
                        display:flex;align-items:center;gap:12px;">
              <div style="font-size:28px;">🏚️</div>
              <div>
                <div style="font-size:15px;font-weight:700;">قائمة السكنيات الشاغرة</div>
                <div style="font-size:12px;opacity:.85;margin-top:3px;">{len(vacant_df)} سكنية شاغرة</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            search_v = st.text_input("🔍 بحث داخل الشاغرة...", placeholder="المؤسسة، الجماعة، الرقم المخزني...",
                                     label_visibility="visible", key="vacant_search")

            if search_v.strip():
                ql = search_v.strip().lower()
                mask = (
                    vacant_df["institution"].str.lower().str.contains(ql, na=False) |
                    vacant_df["makhzani"].str.lower().str.contains(ql, na=False)    |
                    vacant_df["commune"].str.lower().str.contains(ql, na=False)     |
                    vacant_df["nature"].str.lower().str.contains(ql, na=False)
                )
                vacant_df = vacant_df[mask]

            # Build table
            table_rows = ""
            for i, (_, h) in enumerate(vacant_df.iterrows()):
                table_rows += f"""
                <tr>
                  <td style="color:var(--muted);font-size:11px">{i+1}</td>
                  <td style="font-weight:600;font-size:13px">{h.get('institution','—')}</td>
                  <td>{h.get('gresa','—')}</td>
                  <td>{h.get('commune','—')}</td>
                  <td>{h.get('makhzani','—')}</td>
                  <td>{h.get('nature','—')}</td>
                  <td>{h.get('categorie','—')}</td>
                  <td>{h.get('etat','—')}</td>
                  <td><span class="badge badge-amber">شاغر</span></td>
                </tr>"""

            st.markdown(f"""
            <div style="background:#fff;border:1px solid var(--border);border-radius:var(--r);
                        overflow:hidden;margin-top:.8rem;">
              <div style="overflow-x:auto">
                <table>
                  <thead><tr>
                    <th>#</th><th>المؤسسة</th><th>GRESA</th><th>الجماعة</th>
                    <th>الرقم المخزني</th><th>الطبيعة</th><th>الصنف</th><th>الحالة</th><th>الوضعية</th>
                  </tr></thead>
                  <tbody>{table_rows if table_rows else '<tr><td colspan="9" style="text-align:center;padding:2rem;color:var(--muted)">لا توجد نتائج</td></tr>'}</tbody>
                </table>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Export button
            st.markdown("<br>", unsafe_allow_html=True)
            export_cols = ["institution","gresa","commune","makhzani","nature","categorie","etat","statut"]
            export_df = vacant_df[[c for c in export_cols if c in vacant_df.columns]]
            csv = export_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="⬇️  تصدير قائمة الشاغرة (CSV)",
                data=csv,
                file_name="سكنيات_شاغرة.csv",
                mime="text/csv",
            )


# ─── Main Entry ──────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    show_login()
else:
    show_app()
