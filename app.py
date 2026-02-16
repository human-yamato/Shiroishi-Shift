import streamlit as st
import jpholiday
import calendar
import random
import pandas as pd
import io
import base64
import copy
import json
from datetime import datetime, date, timedelta
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors

# ==========================================
# 🔒 合言葉（パスワード）の設定
# ==========================================
# 以下の "shiroishi" の部分を好きな文字に変えると、合言葉を変更できます。
SECRET_PASSWORD = "shiroishi"

def check_password():
    """合言葉をチェックする画面の仕組み"""
    def password_entered():
        if st.session_state["password"] == SECRET_PASSWORD:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # パスワードを記憶させない
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align: center; margin-top: 100px; color: #31333F;'>🔒 白石シフト作成アプリ</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("合言葉を入力して、キーボードの「確定（Enter）」を押してください", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align: center; margin-top: 100px; color: #31333F;'>🔒 白石シフト作成アプリ</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.text_input("合言葉を入力して、キーボードの「確定（Enter）」を押してください", type="password", on_change=password_entered, key="password")
            st.error("😕 合言葉が違います。もう一度お試しください。")
        return False
    else:
        return True

# --- PDF作成関数 ---
def create_shiroishi_pdf(year, month, schedule, prev_history, holidays):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    c.setFont("HeiseiKakuGo-W5", 16)
    c.drawString(30, height - 40, f"やまと在宅診療所白石｜待機医師シフト表 ({year}年{month}月)")
    c.setFont("HeiseiKakuGo-W5", 10)
    c.drawString(width - 200, height - 40, "作成日: " + date.today().strftime("%Y/%m/%d"))

    margin_x, margin_y = 30, 60
    table_width = width - (margin_x * 2)
    table_height = height - 100
    
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)
    
    col_width = table_width / 7
    row_height = table_height / (len(month_days) + 1)

    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    header_y = height - margin_y - row_height
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)

    # ヘッダー
    for i, w in enumerate(weekdays):
        x = margin_x + (i * col_width)
        c.rect(x, header_y, col_width, row_height)
        if i == 5: c.setFillColor(colors.blue)
        elif i == 6: c.setFillColor(colors.red)
        else: c.setFillColor(colors.black)
        c.setFont("HeiseiKakuGo-W5", 12)
        c.drawCentredString(x + col_width/2, header_y + row_height/2 - 4, w)
        c.setFont("HeiseiKakuGo-W5", 8)
        sub = "日中|夜間" if i >= 5 else "(夜間のみ)"
        c.drawCentredString(x + col_width/2, header_y + 5, sub)

    first_day_of_month = date(year, month, 1)
    
    # 本体
    for r, week in enumerate(month_days):
        y = header_y - ((r + 1) * row_height)
        for d_idx, day in enumerate(week):
            x = margin_x + (d_idx * col_width)
            c.rect(x, y, col_width, row_height)
            
            if day == 0 and r == 0:
                diff = first_day_of_month.weekday() - d_idx
                p_date = first_day_of_month - timedelta(days=diff)
                if p_date in prev_history:
                    p_info = prev_history[p_date]
                    c.setFillColor(colors.lightgrey)
                    c.setFont("HeiseiKakuGo-W5", 8)
                    c.drawString(x + 4, y + row_height - 10, f"{p_date.month}/{p_date.day}")
                    
                    c.setFont("HeiseiKakuGo-W5", 9)
                    if p_info.get('day') or p_info.get('night'):
                        c.line(x, y + row_height/2, x + col_width, y + row_height/2)
                        if p_info.get('day'):
                            c.drawCentredString(x + col_width/2, y + row_height*0.75 - 4, p_info['day'])
                        if p_info.get('night'):
                            c.drawCentredString(x + col_width/2, y + row_height*0.25 - 4, p_info['night'])
                continue
            
            if day == 0: continue
            
            dt = date(year, month, day)
            is_custom = dt in holidays
            is_hol = jpholiday.is_holiday(dt) or is_custom
            is_we = (d_idx >= 5) or is_hol
            
            c.setFont("HeiseiKakuGo-W5", 10)
            if d_idx == 6 or is_hol: c.setFillColor(colors.red)
            elif d_idx == 5: c.setFillColor(colors.blue)
            else: c.setFillColor(colors.black)
            
            day_str = str(day)
            if is_custom: day_str += "(休)"
            c.drawString(x + 4, y + row_height - 12, day_str)
            
            data = schedule.get(day, {})
            d_nm = data.get("day", "")
            n_nm = data.get("night", "")
            
            c.setFillColor(colors.black)
            if not is_we:
                if n_nm and n_nm != "❌未定":
                    c.setFont("HeiseiKakuGo-W5", 13)
                    c.drawCentredString(x + col_width/2, y + row_height/2 - 4, n_nm)
            else:
                c.line(x, y + row_height/2, x + col_width, y + row_height/2)
                c.setFont("HeiseiKakuGo-W5", 11)
                if d_nm and d_nm != "❌未定": c.drawCentredString(x + col_width/2, y + row_height*0.75 - 4, d_nm)
                if n_nm and n_nm != "❌未定": c.drawCentredString(x + col_width/2, y + row_height*0.25 - 4, n_nm)
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- アプリ本体 ---
def run_app():
    st.set_page_config(layout="wide", page_title="白石シフト作成")
    
    # 🔒 ここで合言葉をチェック！合っていなければ画面を表示しない
    if not check_password():
        st.stop()
    
    # CSS: V45 (完成版デザイン・ロック済)
    st.markdown("""
        <style>
        .block-container {padding-top: 3rem; padding-bottom: 2rem;}
        
        h1 {
            font-size: 33px !important;
            font-weight: bold !important;
            padding-bottom: 10px !important;
        }

        .section-header {
            font-size: 30px !important;
            font-weight: bold !important;
            margin-top: 50px !important;
            margin-bottom: 40px !important;
            color: #31333F;
        }

        /* --- サイドバーのボタン (Save/Downloadのみ220px) --- */
        section[data-testid="stSidebar"] div[data-testid="stButton"],
        section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] {
            margin-top: 5px !important;
            margin-bottom: 5px !important;
            width: 220px !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        
        section[data-testid="stSidebar"] div[data-testid="stButton"] button,
        section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button {
            font-size: 16px !important;
            height: auto !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            width: 220px !important;
            display: flex !important;
            justify-content: center !important;
            align-items: center !important;
        }
        
        section[data-testid="stSidebar"] div[data-testid="stButton"] button p,
        section[data-testid="stSidebar"] div[data-testid="stDownloadButton"] button p {
            font-size: 16px !important;
        }

        /* --- サイドバーの他の要素 (LOCKED) --- */
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            font-size: 25px !important;
            font-weight: bold !important;
            margin-top: 15px !important;
            margin-bottom: 5px !important;
        }
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] p {
            font-size: 20px !important;
        }
        [data-testid="stSidebar"] textarea, [data-testid="stSidebar"] div[data-baseweb="select"] span {
            font-size: 20px !important;
        }
        [data-testid="stSidebar"] div[data-baseweb="select"] > div {
            min-height: 40px !important;
        }

        /* --- カレンダー (LOCKED) --- */
        div[data-testid="column"] > div > div[data-testid="stVerticalBlock"] > div.element-container {
            gap: 0px !important; margin-bottom: 0px !important;
        }
        div[data-testid="stVerticalBlock"] { gap: 0px !important; }
        
        .cal-header {
            height: 53px; display: flex; align-items: flex-start; justify-content: center;
            padding-top: 10px; font-weight: bold; font-size: 18px;
            margin: 0px; background-color: #ffffff; border-bottom: 2px solid #ddd;
        }
        .cal-date {
            height: 47px; display: flex; align-items: flex-start; justify-content: center;
            padding-top: 2px; font-weight: bold; font-size: 18px;
            margin: 0px; background-color: #ffffff;
        }
        div[data-testid="stTabs"] div[data-testid="stSelectbox"] {
            margin: 0px !important; height: 32px !important;
        }
        div[data-testid="stTabs"] div[data-testid="stSelectbox"] > label {display: none;}
        div[data-testid="stTabs"] div[data-testid="stSelectbox"] > div > div {
            min-height: 32px !important; height: 32px !important; line-height: 32px !important;
            padding: 0px 0px !important; font-size: 13px !important;
            display: flex; align-items: center; justify-content: center; border-radius: 4px;
        }
        div[data-baseweb="select"] span { display: flex; align-items: center; justify-content: center; width: 100%; }
        
        .cal-spacer-32 { height: 32px; width: 100%; margin: 0px; }
        .prev-box {
            height: 32px; width: 100%; background-color: #f0f2f6; color: #555;
            font-size: 12px; font-weight: bold; display: flex; align-items: center;
            justify-content: center; border: 1px solid #ccc; border-radius: 4px; margin: 0px;
        }
        .gap-3 { height: 3px; width: 100%; margin: 0px; }
        
        .stTabs [data-baseweb="tab-list"] { gap: 2px; }
        .stTabs [data-baseweb="tab"] {
            height: 33px; white-space: pre-wrap; background-color: #f0f2f6;
            border-radius: 4px 4px 0px 0px; gap: 1px; padding: 0px; flex: 1;
            font-size: 14px; font-weight: bold; display: flex; align-items: center; justify-content: center;
        }
        .stTabs [aria-selected="true"] { background-color: #ffffff; border-bottom: 3px solid #ff4b4b; }
        
        /* --- メインエリアのボタン余白 (LOCKED) --- */
        section.main div[data-testid="stButton"] {
            margin-top: 50px !important;
            margin-bottom: 40px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("やまと在宅診療所白石待機医師シフト表")

    if 'generated' not in st.session_state: st.session_state.generated = False
    if 'plans' not in st.session_state: st.session_state.plans = []
    if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0

    # --- 保存・読込エリア ---
    with st.sidebar.expander("💾 データ保存・読込", expanded=True):
        
        st.markdown(
            '<div style="font-size:16px !important; color:#555; line-height:1.2;">保存ファイルをここにドロップ</div>', 
            unsafe_allow_html=True
        )
        st.markdown('<div style="height: 45px; width: 100%;"></div>', unsafe_allow_html=True)
        
        def load_json_file():
            key = f"loader_{st.session_state.uploader_key}"
            uploaded = st.session_state.get(key)
            if uploaded is not None:
                try:
                    data = json.load(uploaded)
                    for k, v in data.items():
                        st.session_state[k] = v
                    st.toast("✅ データを読み込みました！")
                except Exception as e:
                    st.toast(f"❌ 読込エラー: {e}")
                st.session_state.uploader_key += 1

        st.file_uploader(
            "ファイル読込", 
            type=["json"], 
            label_visibility="collapsed",
            key=f"loader_{st.session_state.uploader_key}",
            on_change=load_json_file
        )

        st.markdown("---")

        if st.button("現在の設定をファイル保存"):
            save_data = {}
            for k, v in st.session_state.items():
                if isinstance(v, (str, int, float, bool, list)):
                    save_data[k] = v
            
            now_jst = datetime.now() + timedelta(hours=9)
            time_str = now_jst.strftime('%Y%m%d%H%M')
            file_name = f"{time_str}_shift_data.json"
            
            json_str = json.dumps(save_data, ensure_ascii=False, indent=2)
            st.download_button(
                label="ファイルをダウンロード",
                data=json_str,
                file_name=file_name,
                mime="application/json"
            )

    # --- サイドバー設定 ---
    st.sidebar.header("📅 設定")
    year = st.sidebar.selectbox("年", list(range(2025, 2041)), index=1)
    month = st.sidebar.selectbox("月", list(range(1, 13)), index=1)

    try:
        start_date = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
    except: st.error("日付エラー"); st.stop()

    st.sidebar.markdown("---")
    st.sidebar.header("👨‍⚕️ 医師リスト")
    
    default_docs = "大蔵(白)\n角田(白)\n平川(白)\n千田(白)\n羽隅(白)\n日野(白)\n西岡(白)\n郷内(あ)"
    if "docs_list_input" not in st.session_state:
        st.session_state["docs_list_input"] = default_docs
    
    docs_text = st.sidebar.text_area(
        "編集可", 
        height=180, 
        key="docs_list_input"
    )
    all_docs = [d.strip() for d in docs_text.split() if d.strip()]

    st.sidebar.markdown("---")
    st.sidebar.header("⏮️ 前月末の担当医")
    prev_month_end = start_date - timedelta(days=1)
    prev_history = {}
    
    for i in range(5, -1, -1):
        d = prev_month_end - timedelta(days=i)
        d_str = d.strftime("%m/%d")
        wd_idx = d.weekday()
        wd_str = ["月","火","水","木","金","土","日"][wd_idx]
        is_hol = jpholiday.is_holiday(d) or wd_idx >= 5
        st.sidebar.caption(f"{d_str}({wd_str})")
        if is_hol:
            c1, c2 = st.sidebar.columns(2)
            d_val = c1.selectbox("日", ["-"]+all_docs, key=f"p_d_{i}", label_visibility="collapsed")
            n_val = c2.selectbox("夜", ["-"]+all_docs, key=f"p_n_{i}", label_visibility="collapsed")
            if d_val != "-" or n_val != "-": prev_history[d] = {'day': d_val if d_val!="-" else None, 'night': n_val if n_val!="-" else None}
        else:
            n_val = st.sidebar.selectbox("夜", ["-"]+all_docs, key=f"p_n_{i}", label_visibility="collapsed")
            if n_val != "-": prev_history[d] = {'day': None, 'night': n_val}

    # --- メインエリア ---
    st.markdown('<div class="section-header">🎌 診療所独自の休診日</div>', unsafe_allow_html=True)
    with st.expander("カレンダーを開く", expanded=False):
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(year, month)
        custom_holidays = []
        cols = st.columns(7)
        for i, w in enumerate(["月","火","水","木","金","土","日"]):
            cols[i].markdown(f"<div style='text-align:center; color:gray'>{w}</div>", unsafe_allow_html=True)
        for week in month_days:
            cols = st.columns(7)
            for i, d in enumerate(week):
                if d == 0: cols[i].write(""); continue
                with cols[i]:
                    if st.checkbox(f"{d}", key=f"hol_{d}"): custom_holidays.append(date(year, month, d))

    st.write("") 
    
    st.markdown('<div class="section-header">1️⃣ 医師ごとの条件入力</div>', unsafe_allow_html=True)
    OPT_OK = "⚪️"
    OPT_FIX = "🔵確"
    OPT_PRI = "🟠選"
    OPT_NG = "🔴NG"
    OPTIONS = [OPT_OK, OPT_FIX, OPT_PRI, OPT_NG]

    user_inputs = {}
    tabs = st.tabs(all_docs)
    first_day_of_month = date(year, month, 1)

    for idx, doc in enumerate(all_docs):
        with tabs[idx]:
            cols = st.columns(7)
            for i, w in enumerate(["月","火","水","木","金","土","日"]):
                c = "blue" if i==5 else "red" if i==6 else "black"
                cols[i].markdown(f"<div class='cal-header' style='color:{c}'>{w}</div>", unsafe_allow_html=True)
            
            doc_inputs = {} 
            for week_idx, week in enumerate(month_days):
                # Row 1: 日付 (LOCKED)
                cols_date = st.columns(7)
                for i, d in enumerate(week):
                    if d == 0:
                        if week_idx == 0:
                            diff = first_day_of_month.weekday() - i
                            p_date = first_day_of_month - timedelta(days=diff)
                            cols_date[i].markdown(f"<div class='cal-date' style='color:#888'>{p_date.day}</div>", unsafe_allow_html=True)
                        else: cols_date[i].write("")
                    else:
                        dt = date(year, month, d)
                        is_custom = dt in custom_holidays
                        is_hol = jpholiday.is_holiday(dt) or is_custom
                        dc = "red" if (i==6 or is_hol) else "blue" if i==5 else "black"
                        lbl = f"{d}🔴" if is_custom else str(d)
                        cols_date[i].markdown(f"<div class='cal-date' style='color:{dc}'>{lbl}</div>", unsafe_allow_html=True)

                # Row 2: 日中 (LOCKED)
                cols_day = st.columns(7)
                for i, d in enumerate(week):
                    if d == 0:
                        if week_idx == 0:
                            diff = first_day_of_month.weekday() - i
                            p_date = first_day_of_month - timedelta(days=diff)
                            p_day = prev_history[p_date].get('day') if p_date in prev_history else None
                            if p_day: cols_day[i].markdown(f"<div class='prev-box'>{p_day}</div>", unsafe_allow_html=True)
                            else: cols_day[i].markdown(f"<div class='cal-spacer-32'></div>", unsafe_allow_html=True)
                        else: cols_day[i].write("")
                        continue
                    dt = date(year, month, d)
                    is_custom = dt in custom_holidays
                    is_hol = jpholiday.is_holiday(dt) or is_custom
                    is_we = (i >= 5) or is_hol
                    if is_we: cols_day[i].selectbox(f"d_{d}", OPTIONS, key=f"{doc}_{d}_d", label_visibility="collapsed")
                    else: cols_day[i].markdown(f"<div class='cal-spacer-32'></div>", unsafe_allow_html=True)

                # Row 3: 夜間 (LOCKED)
                cols_night = st.columns(7)
                for i, d in enumerate(week):
                    if d == 0:
                        if week_idx == 0:
                            diff = first_day_of_month.weekday() - i
                            p_date = first_day_of_month - timedelta(days=diff)
                            p_night = prev_history[p_date].get('night') if p_date in prev_history else None
                            if p_night: cols_night[i].markdown(f"<div class='prev-box'>{p_night}</div>", unsafe_allow_html=True)
                            else: cols_night[i].markdown(f"<div class='cal-spacer-32'></div>", unsafe_allow_html=True)
                        else: cols_night[i].write("")
                        continue
                    cols_night[i].selectbox(f"n_{d}", OPTIONS, key=f"{doc}_{d}_n", label_visibility="collapsed")

                st.markdown("<div class='gap-3'></div>", unsafe_allow_html=True)

            for d in range(1, len(month_days)*7 + 1):
                try: dt_check = date(year, month, d)
                except: continue
                d_key = f"{doc}_{d}_d"
                n_key = f"{doc}_{d}_n"
                day_val = st.session_state.get(d_key, OPT_OK)
                night_val = st.session_state.get(n_key, OPT_OK)
                doc_inputs[d] = {'day': day_val, 'night': night_val}
            user_inputs[doc] = doc_inputs

    st.markdown("---")
    if st.button("🚀 シフト案を3つ作成 (AI)", type="primary", use_container_width=True):
        st.session_state.generated = True
        fixed_map, priority_map, ng_map = {}, {}, {}
        for day in range(1, last_day + 1):
            fixed_map[day] = {'day': None, 'night': None}
            priority_map[day] = {'day': [], 'night': []}
            ng_map[day] = {'day': [], 'night': []}
            dt = date(year, month, day)
            is_custom = dt in custom_holidays
            is_we = (dt.weekday() >= 5) or jpholiday.is_holiday(dt) or is_custom
            slots = ['night']
            if is_we: slots.append('day')
            for slot in slots:
                for doc in all_docs:
                    if doc in user_inputs and day in user_inputs[doc]:
                        status = user_inputs[doc][day][slot]
                        if status == OPT_FIX: fixed_map[day][slot] = doc
                        elif status == OPT_PRI: priority_map[day][slot].append(doc)
                        elif status == OPT_NG: ng_map[day][slot].append(doc)

        plans = []
        for _ in range(3):
            schedule = copy.deepcopy(fixed_map)
            counts = {d: 0 for d in all_docs}
            for d_info in schedule.values():
                if d_info['day']: counts[d_info['day']] += 1
                if d_info['night']: counts[d_info['night']] += 1
            for day in range(1, last_day + 1):
                dt = date(year, month, day)
                is_custom = dt in custom_holidays
                is_we = (dt.weekday() >= 5) or jpholiday.is_holiday(dt) or is_custom
                target_slots = []
                if is_we and not schedule[day]['day']: target_slots.append('day')
                if not schedule[day]['night']: target_slots.append('night')
                for slot in target_slots:
                    candidates = []
                    pool = priority_map[day][slot] if priority_map[day][slot] else all_docs
                    for doc in pool:
                        if doc in ng_map[day][slot]: continue
                        prev_d = dt - timedelta(days=1)
                        prev_who = None
                        if prev_d.month == month:
                            if prev_d.day in schedule: prev_who = schedule[prev_d.day]['night']
                        else:
                            if prev_d in prev_history: prev_who = prev_history[prev_d].get('night')
                        if prev_who == doc: continue
                        if is_we:
                            fri_date = dt - timedelta(days=(dt.weekday() - 4))
                            fri_who = None
                            if fri_date.month == month:
                                if fri_date.day in schedule: fri_who = schedule[fri_date.day]['night']
                            else:
                                if fri_date in prev_history: fri_who = prev_history[fri_date].get('night')
                            if fri_who and fri_who == doc:
                                if doc in priority_map[day][slot]:
                                    for _ in range(100): candidates.append(doc)
                                else:
                                    for _ in range(10): candidates.append(doc)
                        candidates.append(doc)
                    if candidates:
                        candidates.sort(key=lambda x: counts[x] + random.random())
                        assigned = candidates[0]
                        schedule[day][slot] = assigned
                        counts[assigned] += 1
                    else: schedule[day][slot] = "❌未定"
            plans.append(schedule)
        st.session_state.plans = plans

    if st.session_state.generated:
        st.markdown('<div class="section-header">3️⃣ 作成結果</div>', unsafe_allow_html=True)
        tabs = st.tabs(["案①", "案②", "案③"])
        for idx, tab in enumerate(tabs):
            with tab:
                sch = st.session_state.plans[idx]
                html = "<table style='width:100%; border-collapse:collapse; text-align:center;'><tr>"
                for i, w in enumerate(["月","火","水","木","金","土","日"]):
                    bg = "#f0f2f6"
                    c = "blue" if i==5 else "red" if i==6 else "black"
                    html += f"<th style='border:1px solid #ddd; padding:5px; background:{bg}; color:{c}; width:14.2%'>{w}</th>"
                html += "</tr>"
                for r, week in enumerate(month_days):
                    html += "<tr>"
                    for i, d in enumerate(week):
                        if d == 0:
                            content = ""
                            if r == 0:
                                diff = first_day_of_month.weekday() - i
                                p_date = first_day_of_month - timedelta(days=diff)
                                if p_date in prev_history:
                                    info = prev_history[p_date]
                                    content = f"<div style='color:#ccc; font-size:10px'>{p_date.month}/{p_date.day}</div>"
                                    if info.get('day'): content += f"<div style='color:#999; font-size:11px'>{info['day']}(日)</div>"
                                    if info.get('night'): content += f"<div style='color:#999; font-size:11px'>{info['night']}(夜)</div>"
                            html += f"<td style='border:1px solid #ddd; background:#f9f9f9; vertical-align:middle'>{content}</td>"
                            continue
                        dt = date(year, month, d)
                        is_custom = dt in custom_holidays
                        is_we = (i>=5) or jpholiday.is_holiday(dt) or is_custom
                        bg = "#fff0f0" if is_we else "#fff"
                        d_val = sch.get(d, {}).get("day", "")
                        n_val = sch.get(d, {}).get("night", "")
                        dc = "red" if (i==6 or jpholiday.is_holiday(dt) or is_custom) else "blue" if i==5 else "black"
                        lbl = f"{d}🔴" if is_custom else str(d)
                        cell = f"<div style='font-weight:bold; color:{dc}; background:#eee'>{lbl}</div>"
                        d_st = "color:red;font-weight:bold;" if d_val == "❌未定" else ""
                        n_st = "color:red;font-weight:bold;" if n_val == "❌未定" else ""
                        if is_we:
                            cell += f"<div style='font-size:13px; font-weight:bold; border-bottom:1px solid #ccc; padding:4px; {d_st}'>{d_val or '-'}</div>"
                            cell += f"<div style='font-size:13px; font-weight:bold; padding:4px; {n_st}'>{n_val or '-'}</div>"
                        else:
                            cell += f"<div style='font-size:13px; font-weight:bold; padding:15px 0; {n_st}'>{n_val or '-'}</div>"
                        html += f"<td style='border:1px solid #ddd; vertical-align:top; background:{bg}'>{cell}</td>"
                    html += "</tr>"
                html += "</table>"
                st.markdown(html, unsafe_allow_html=True)
                
                st.markdown('<div class="section-header">📊 集計結果</div>', unsafe_allow_html=True)
                counts_data = []
                for doc in all_docs:
                    c_wd, c_we = 0, 0
                    for d, s in sch.items():
                        dt = date(year, month, d)
                        is_custom = dt in custom_holidays
                        is_w = (dt.weekday() >= 5) or jpholiday.is_holiday(dt) or is_custom
                        names = [s.get("day"), s.get("night")]
                        if doc in names:
                            count = names.count(doc)
                            if is_w: c_we += count
                            else: c_wd += count
                    if c_wd + c_we > 0:
                        counts_data.append({"医師": doc, "平日": c_wd, "週末": c_we, "合計": c_wd+c_we})
                if counts_data: st.table(pd.DataFrame(counts_data).set_index("医師"))

                pdf_bytes = create_shiroishi_pdf(year, month, sch, prev_history, custom_holidays)
                b64 = base64.b64encode(pdf_bytes.getvalue()).decode()
                href = f'<div style="margin-top: 50px; margin-bottom: 40px;"><a href="data:application/pdf;base64,{b64}" download="shift_{year}_{month}_plan{idx+1}.pdf" style="text-decoration:none; background-color:#ff4b4b; color:white; padding:10px 20px; border-radius:5px; font-weight:bold;">📥 案{idx+1}のPDFをダウンロード</a></div>'
                st.markdown(href, unsafe_allow_html=True)

if __name__ == '__main__':
    run_app()
