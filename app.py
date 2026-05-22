import streamlit as st
import pandas as pd
import os, re, hashlib

st.set_page_config(
    page_title="منظومة تدبير السكنيات الوظيفية والإدارية",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS مخصص ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap');
@import url('https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css');

:root {
  --primary:#1a56db; --primary-lt:#e8f0fe;
  --green:#059669;   --green-bg:#ecfdf5;
  --amber:#d97706;   --amber-bg:#fffbeb;
  --red:#dc2626;     --red-bg:#fef2f2;
  --muted:#64748b;   --border:#e2e8f0;
  --surface:#fff;    --surface2:#f5f7fb;
}
html, body, [class*="css"] { font-family: 'Cairo', sans-serif !important; direction: rtl; }
.block-container { padding: 1.5rem 2rem !important; }

/* بطاقات الإحصائيات */
.stat-card {
  background: var(--surface); border-radius: 12px;
  border: 1px solid var(--border); padding: 1.1rem 1.4rem;
  display: flex; align-items: center; gap: .9rem;
  margin-bottom: 1rem; box-shadow: 0 2px 8px rgba(0,0,0,.05);
}
.stat-icon {
  width: 46px; height: 46px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.si-blue  { background: var(--primary-lt); color: var(--primary); }
.si-green { background: var(--green-bg);   color: var(--green); }
.si-amber { background: var(--amber-bg);   color: var(--amber); }
.stat-num  { font-size: 26px; font-weight: 700; line-height: 1; }
.stat-lbl  { font-size: 12px; color: var(--muted); margin-top: 3px; }

/* رأس المؤسسة */
.inst-header {
  background: linear-gradient(135deg,#0f172a,#1e3a8a);
  border-radius: 12px; padding: 1.4rem; color: #fff; margin-bottom: 1rem;
}
.inst-name { font-size: 19px; font-weight: 800; margin-bottom: 4px; }
.inst-meta { font-size: 12.5px; opacity: .7; margin-bottom: 10px; }
.chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 20px; font-size: 11.5px; font-weight: 600;
  background: rgba(255,255,255,.15); color: #fff;
  border: 1px solid rgba(255,255,255,.2); margin-left: 6px;
}

/* badges */
.badge-green { background:var(--green-bg); color:var(--green);
               padding:3px 10px; border-radius:20px; font-size:11.5px; font-weight:700; }
.badge-amber { background:var(--amber-bg); color:var(--amber);
               padding:3px 10px; border-radius:20px; font-size:11.5px; font-weight:700; }
.badge-red   { background:var(--red-bg);   color:var(--red);
               padding:3px 10px; border-radius:20px; font-size:11.5px; font-weight:700; }
.badge-gray  { background:var(--surface2); color:var(--muted);
               padding:3px 10px; border-radius:20px; font-size:11.5px; font-weight:700; }

/* بطاقة القاطن */
.occ-card {
  background: var(--surface2); border-radius: 10px;
  padding: .7rem 1rem; margin-bottom: .5rem;
}
.occ-label { font-size: 10.5px; color: var(--muted); font-weight: 600; margin-bottom: 2px; }
.occ-val   { font-size: 13.5px; font-weight: 600; }

/* شريط جانبي */
section[data-testid="stSidebar"] > div {
  background: #0f172a !important; color: #fff !important;
}
section[data-testid="stSidebar"] .stRadio label { color: #94a3b8 !important; font-size: 14px !important; }
section[data-testid="stSidebar"] .stRadio label:hover { color: #fff !important; }

/* إخفاء عناصر Streamlit الافتراضية */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
</style>
""", unsafe_allow_html=True)

# ─── الإعدادات ───────────────────────────────────────────────────────────────
ADMIN_USER = "admin"
ADMIN_PASS = hashlib.sha256("admin2025".encode()).hexdigest()
DATA_FILE  = os.path.join(os.path.dirname(__file__), "data.xlsx")

COL_RENAME = {
    "ر,ت": "rt", "المؤسسة": "institution", "نوعها": "type",
    "رمز GRESA": "gresa", "الجماعة الترابية": "commune", "الوسط": "milieu",
    "طبيعة السكن": "nature", "صنف السكن": "categorie", "حالة السكن": "etat",
    "وضعية السكن :": "statut", "اسم ونسب القاطن الحالي": "occupant",
    "رقم تأجيره": "num_bail", "إطاره": "cadre",
    "Date d'occupation/تاريخ إسناد السكن 2": "date_occ",
    "مهمته": "mission", "نوع الإسناد": "type_aff",
    "وضعية القاطن": "statut_occ", "ملاحظات  إضافية": "notes",
}

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
            rename[col] = "makhzani"; break
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
    return df.reset_index(drop=True)

def badge_html(s):
    s = s or ''
    if re.search(r"مستعمل|مشغول", s): return f'<span class="badge-green">مشغول</span>'
    if re.search(r"محتل",          s): return f'<span class="badge-red">محتل</span>'
    if re.search(r"شاغر|فارغ",    s): return f'<span class="badge-amber">شاغر</span>'
    if re.search(r"إصلاح|تعطل",   s): return f'<span class="badge-red">جاري الإصلاح</span>'
    return f'<span class="badge-gray">{s or "—"}</span>'

# ─── حالة الجلسة ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "selected_inst" not in st.session_state:
    st.session_state.selected_inst = None
if "selected_housing" not in st.session_state:
    st.session_state.selected_housing = None

# ─── شاشة تسجيل الدخول ───────────────────────────────────────────────────────
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center;margin-bottom:1.5rem">
          <div style="width:64px;height:64px;border-radius:15px;background:#e8f0fe;
                      color:#1a56db;font-size:28px;display:flex;align-items:center;
                      justify-content:center;margin:0 auto .9rem">🏢</div>
          <h2 style="font-size:16px;font-weight:800;margin-bottom:6px">
            منظومة تدبير السكنيات الوظيفية والإدارية
          </h2>
          <p style="font-size:12px;color:#64748b">
            مصلحة البناءات والتجهيز والممتلكات<br>
            المديرية الإقليمية إنزكان آيت ملول
          </p>
        </div>
        """, unsafe_allow_html=True)
        username = st.text_input("اسم المستخدم", placeholder="admin")
        password = st.text_input("كلمة المرور", type="password", placeholder="••••••••")
        if st.button("تسجيل الدخول", use_container_width=True, type="primary"):
            ph = hashlib.sha256(password.encode()).hexdigest()
            if username == ADMIN_USER and ph == ADMIN_PASS:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

# ─── تحميل البيانات ───────────────────────────────────────────────────────────
try:
    DF = load_data()
except Exception as e:
    st.error(f"خطأ في تحميل البيانات: {e}")
    st.stop()

total    = len(DF)
occupied = int(DF["statut"].str.contains("مستعمل|مشغول|محتل", na=False, regex=True).sum())
vacant   = int(DF["statut"].str.contains("شاغر|فارغ", na=False, regex=True).sum())
inst_count = int(DF["institution"].nunique())

# ─── الشريط الجانبي ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:1rem 0 1.5rem">
      <div style="width:48px;height:48px;border-radius:10px;background:#1a56db;
                  color:#fff;font-size:22px;display:flex;align-items:center;
                  justify-content:center;margin:0 auto .8rem">🏢</div>
      <div style="color:#fff;font-size:13px;font-weight:700">منظومة السكنيات</div>
      <div style="color:#94a3b8;font-size:11px;margin-top:3px">إنزكان آيت ملول</div>
    </div>
    """, unsafe_allow_html=True)

    tab = st.radio("القائمة", ["🏠 السكنيات", "📊 الإحصائيات", "🏚️ الشاغرة"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown(f'<div style="color:#94a3b8;font-size:11px;text-align:center">مرحباً، {ADMIN_USER}</div>', unsafe_allow_html=True)
    if st.button("تسجيل الخروج", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.selected_inst = None
        st.rerun()

# ─── رأس الصفحة ──────────────────────────────────────────────────────────────
st.markdown("""
<div style="background:#fff;border-bottom:1px solid #e2e8f0;padding:.9rem 0;margin-bottom:1.5rem">
  <div style="font-size:17px;font-weight:800">منظومة تدبير السكنيات الوظيفية والإدارية</div>
  <div style="font-size:11.5px;color:#64748b;margin-top:2px">
    الموسم الدراسي 2025/2026 — مصلحة البناءات والتجهيز والممتلكات
  </div>
</div>
""", unsafe_allow_html=True)

# ─── بطاقات الإحصائيات ───────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f"""<div class="stat-card">
      <div class="stat-icon si-blue">🏫</div>
      <div><div class="stat-num">{inst_count}</div><div class="stat-lbl">مجموع المؤسسات</div></div>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="stat-card">
      <div class="stat-icon si-blue">🏠</div>
      <div><div class="stat-num">{total}</div><div class="stat-lbl">مجموع السكنيات</div></div>
    </div>""", unsafe_allow_html=True)
with c3:
    st.markdown(f"""<div class="stat-card">
      <div class="stat-icon si-green">✅</div>
      <div><div class="stat-num">{occupied}</div><div class="stat-lbl">مشغولة</div></div>
    </div>""", unsafe_allow_html=True)
with c4:
    st.markdown(f"""<div class="stat-card">
      <div class="stat-icon si-amber">🏚️</div>
      <div><div class="stat-num">{vacant}</div><div class="stat-lbl">شاغرة</div></div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ════════════════════════════════════════════════════════════════════════════
# تاب السكنيات
# ════════════════════════════════════════════════════════════════════════════
if tab == "🏠 السكنيات":
    st.markdown("### 🔍 البحث عن مؤسسة")

    search = st.text_input("", placeholder="اكتب اسم المؤسسة أو كود GRESA أو اسم القاطن أو الجماعة...", label_visibility="collapsed")

    if search and len(search) >= 1:
        ql = search.lower()
        mask = (
            DF["institution"].str.lower().str.contains(ql, na=False) |
            DF["gresa"].str.lower().str.contains(ql, na=False)       |
            DF["occupant"].str.lower().str.contains(ql, na=False)    |
            DF["commune"].str.lower().str.contains(ql, na=False)
        )
        names = DF[mask]["institution"].unique().tolist()[:20]

        if names:
            selected = st.selectbox("اختر مؤسسة:", ["— اختر —"] + names, label_visibility="collapsed")
            if selected != "— اختر —":
                st.session_state.selected_inst = selected
                st.session_state.selected_housing = None
        else:
            st.info("لم يتم العثور على نتائج مطابقة")

    # عرض تفاصيل المؤسسة
    if st.session_state.selected_inst:
        name = st.session_state.selected_inst
        rows = DF[DF["institution"] == name]

        if not rows.empty:
            info = rows.iloc[0]
            h_total    = len(rows)
            h_occupied = int(rows["statut"].str.contains("مستعمل|مشغول|محتل", na=False, regex=True).sum())
            h_vacant   = int(rows["statut"].str.contains("شاغر|فارغ", na=False, regex=True).sum())
            milieu_icon = "🌳 قروي" if "قروي" in str(info.get("milieu","")) else "🏙️ حضري"

            # رأس المؤسسة
            st.markdown(f"""
            <div class="inst-header">
              <div class="inst-name">🏫 {info['institution']}</div>
              <div class="inst-meta">{info.get('type','—')}</div>
              <span class="chip">{milieu_icon}</span>
              <span class="chip">🔢 {info.get('gresa','—')}</span>
              <span class="chip">📍 {info.get('commune','—')}</span>
            </div>
            """, unsafe_allow_html=True)

            # إحصائيات المؤسسة
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("إجمالي السكنيات", h_total)
            sc2.metric("مشغولة", h_occupied)
            sc3.metric("شاغرة", h_vacant)
            sc4.metric("أخرى", h_total - h_occupied - h_vacant)

            st.markdown("#### 🏠 قائمة السكنيات")

            # جدول السكنيات
            housing_list = rows.to_dict(orient="records")
            for i, h in enumerate(housing_list):
                s = str(h.get("statut",""))
                if re.search(r"مستعمل|مشغول|محتل", s): badge = "🟢"
                elif re.search(r"شاغر|فارغ", s):        badge = "🟡"
                else:                                     badge = "⚪"

                with st.expander(f"{badge} {i+1}. {h.get('makhzani','—')} — {h.get('nature','—')} — {h.get('statut','—')}"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**الرقم المخزني:** {h.get('makhzani','—')}")
                        st.markdown(f"**طبيعة السكن:** {h.get('nature','—')}")
                        st.markdown(f"**صنف السكن:** {h.get('categorie','—')}")
                        st.markdown(f"**حالة السكن:** {h.get('etat','—')}")
                        st.markdown(f"**وضعية السكن:** {h.get('statut','—')}")
                    with col_b:
                        st.markdown(f"**القاطن:** {h.get('occupant','—')}")
                        st.markdown(f"**الإطار:** {h.get('cadre','—')}")
                        st.markdown(f"**المهمة:** {h.get('mission','—')}")
                        st.markdown(f"**تاريخ الإسناد:** {h.get('date_occ','—')}")
                        st.markdown(f"**نوع الإسناد:** {h.get('type_aff','—')}")
                    if h.get('notes','—') != '—':
                        st.markdown(f"**ملاحظات:** {h.get('notes','')}")

            if st.button("🔙 الرجوع للبحث"):
                st.session_state.selected_inst = None
                st.rerun()
        else:
            st.error("لم يتم العثور على المؤسسة")
    elif not search:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:#64748b">
          <div style="font-size:48px;margin-bottom:1rem">🔍</div>
          <p>ابحث عن مؤسسة لعرض السكنيات المرتبطة بها</p>
        </div>
        """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# تاب الإحصائيات
# ════════════════════════════════════════════════════════════════════════════
elif tab == "📊 الإحصائيات":
    st.markdown("### 📊 لوحة الإحصائيات التفصيلية")

    pct_o = round(occupied / total * 100, 1) if total else 0
    pct_v = round(vacant   / total * 100, 1) if total else 0
    urban = int((DF["milieu"].str.contains("حضري", na=False)).sum())
    rural = int((DF["milieu"].str.contains("قروي", na=False)).sum())

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("نسبة الاشغال", f"{pct_o}%")
        st.progress(pct_o / 100)
    with col2:
        st.metric("نسبة الشغور", f"{pct_v}%")
        st.progress(pct_v / 100)
    with col3:
        st.metric("حضري / قروي", f"{urban} / {rural}")
        st.progress(urban / total if total else 0)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("#### توزيع حسب نوع المؤسسة")
        by_type = DF.groupby("type").size().reset_index(name="العدد")
        by_type.columns = ["نوع المؤسسة", "العدد"]
        st.dataframe(by_type, use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("#### توزيع حسب وضعية السكن")
        by_statut = DF.groupby("statut").size().reset_index(name="العدد")
        by_statut.columns = ["الوضعية", "العدد"]
        st.dataframe(by_statut, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### توزيع حسب الجماعة الترابية")
    by_commune = DF.groupby("commune").size().reset_index(name="العدد").sort_values("العدد", ascending=False)
    by_commune.columns = ["الجماعة", "العدد"]
    st.bar_chart(by_commune.set_index("الجماعة"))

# ════════════════════════════════════════════════════════════════════════════
# تاب الشاغرة
# ════════════════════════════════════════════════════════════════════════════
elif tab == "🏚️ الشاغرة":
    st.markdown("### 🏚️ قائمة السكنيات الشاغرة")

    vacant_df = DF[DF["statut"].str.contains("شاغر|فارغ", na=False, regex=True)].copy()
    st.info(f"إجمالي السكنيات الشاغرة: **{len(vacant_df)}** سكنية")

    search_v = st.text_input("🔍 بحث داخل الشاغرة", placeholder="اكتب اسم المؤسسة أو الجماعة...")
    if search_v:
        ql = search_v.lower()
        mask = (
            vacant_df["institution"].str.lower().str.contains(ql, na=False) |
            vacant_df["commune"].str.lower().str.contains(ql, na=False)     |
            vacant_df["makhzani"].str.lower().str.contains(ql, na=False)
        )
        vacant_df = vacant_df[mask]

    display_cols = ["institution", "gresa", "commune", "makhzani", "nature", "categorie", "etat"]
    col_labels   = {
        "institution": "المؤسسة", "gresa": "GRESA", "commune": "الجماعة",
        "makhzani": "الرقم المخزني", "nature": "الطبيعة",
        "categorie": "الصنف", "etat": "الحالة"
    }
    show_df = vacant_df[display_cols].rename(columns=col_labels)
    st.dataframe(show_df, use_container_width=True, hide_index=True)
