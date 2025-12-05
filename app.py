import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta, datetime
from urllib.parse import urlparse
from scraper import collect_blog_posts
import db_manager as dbm
from typing import Optional, List, Dict
from textwrap import shorten
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    if "=" in s:
                        k, v = s.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if k and v and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass


def get_conn():
    return sqlite3.connect("data.db", check_same_thread=False)


def ensure_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS blogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def load_blogs():
    conn = get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT id, name, url FROM blogs ORDER BY id DESC", conn
        )
    finally:
        conn.close()
    st.session_state["blogs"] = df.to_dict("records") if not df.empty else []


def is_valid_blog_url(u: str) -> bool:
    if not u:
        return False
    p = urlparse(u)
    if p.scheme not in {"http", "https"}:
        return False
    if p.netloc != "blog.naver.com":
        return False
    if not p.path.strip("/"):
        return False
    return True


def add_blog(name: str, url: str):
    name = (name or "").strip()
    url = (url or "").strip()
    if not name:
        st.sidebar.error("블로그 이름을 입력하세요")
        return
    if not is_valid_blog_url(url):
        st.sidebar.error("유효한 네이버 블로그 URL을 입력하세요")
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO blogs(name, url, created_at) VALUES (?, ?, ?)",
            (name, url, datetime.utcnow().isoformat()),
        )
        conn.commit()
        st.sidebar.success("블로그가 추가되었습니다")
        load_blogs()
    except sqlite3.IntegrityError:
        st.sidebar.warning("이미 등록된 블로그입니다")
    finally:
        conn.close()


def init_state():
    if "api_provider" not in st.session_state:
        st.session_state["api_provider"] = "OpenAI"
    if "openai_api_key" not in st.session_state:
        st.session_state["openai_api_key"] = ""
    if "blogs" not in st.session_state:
        st.session_state["blogs"] = []
    if "selected_blog_id" not in st.session_state:
        st.session_state["selected_blog_id"] = None
    if "date_range" not in st.session_state:
        today = date.today()
        st.session_state["date_range"] = (today - timedelta(days=7), today)
    if "search_query" not in st.session_state:
        st.session_state["search_query"] = ""
    if "blog_name_input" not in st.session_state:
        st.session_state["blog_name_input"] = ""
    if "blog_url_input" not in st.session_state:
        st.session_state["blog_url_input"] = ""
    if "last_add_success" not in st.session_state:
        st.session_state["last_add_success"] = ""
    if "last_add_warning" not in st.session_state:
        st.session_state["last_add_warning"] = ""
    if "last_add_error" not in st.session_state:
        st.session_state["last_add_error"] = ""
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []


st.set_page_config(page_title="블로그 AI 분석기", layout="wide")
dbm.ensure_blogs_table()
init_state()
st.session_state["blogs"] = dbm.load_blogs()


with st.sidebar:
    st.header("블로그 관리")
    blog_name = st.text_input("블로그 이름", key="blog_name_input")
    blog_url = st.text_input(
        "블로그 URL",
        key="blog_url_input",
        placeholder="https://blog.naver.com/id",
    )
    def on_add_blog():
        name = st.session_state.get("blog_name_input", "").strip()
        url = st.session_state.get("blog_url_input", "").strip()
        if not name or not is_valid_blog_url(url):
            st.session_state["last_add_error"] = "입력 값을 확인하세요"
        else:
            try:
                dbm.add_blog(name, url, datetime.utcnow().isoformat())
                st.session_state["blogs"] = dbm.load_blogs()
                st.session_state["last_add_success"] = "블로그가 추가되었습니다"
            except sqlite3.IntegrityError:
                st.session_state["last_add_warning"] = "이미 등록된 블로그입니다"
        st.session_state["blog_name_input"] = ""
        st.session_state["blog_url_input"] = ""
    st.button("추가", use_container_width=True, on_click=on_add_blog)
    if st.session_state.get("last_add_success"):
        st.sidebar.success(st.session_state["last_add_success"])
        st.session_state["last_add_success"] = ""
    if st.session_state.get("last_add_warning"):
        st.sidebar.warning(st.session_state["last_add_warning"])
        st.session_state["last_add_warning"] = ""
    if st.session_state.get("last_add_error"):
        st.sidebar.error(st.session_state["last_add_error"])
        st.session_state["last_add_error"] = ""

    st.divider()
    st.header("수집 대상 선택")
    
    selected_targets = []
    if st.session_state["blogs"]:
        _df = pd.DataFrame(st.session_state["blogs"])
        target_data = _df[["name", "url"]].copy()
        target_data.insert(0, "선택", False)
        
        edited_df = st.data_editor(
            target_data,
            column_config={
                "선택": st.column_config.CheckboxColumn("V", help="수집할 블로그 선택", default=False, width="small"),
                "name": st.column_config.TextColumn("블로그명", disabled=True),
                "url": st.column_config.TextColumn("URL", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="blog_selector_editor"
        )
        
        if not edited_df.empty:
            selected_rows = edited_df[edited_df["선택"]]
            selected_urls = set(selected_rows["url"])
            selected_targets = [b for b in st.session_state["blogs"] if b["url"] in selected_urls]
    else:
        st.info("등록된 블로그가 없습니다.")

    st.header("수집 기간")
    default_start, default_end = st.session_state["date_range"]
    picked = st.date_input(
        "기간 선택",
        value=(default_start, default_end),
        max_value=date.today(),
    )
    if isinstance(picked, tuple) and len(picked) == 2:
        st.session_state["date_range"] = picked

    if st.session_state.get("scraping"):
        if st.button("수집중단", use_container_width=True):
            st.session_state["cancel_scrape"] = True

    if st.button("데이터 수집 시작", use_container_width=True):
        targets = []
        if selected_targets:
            targets = selected_targets
        elif st.session_state.get("selected_blog_id"):
             sel = [b for b in st.session_state["blogs"] if b["id"] == st.session_state["selected_blog_id"]]
             if sel:
                 targets = sel
        
        if not targets:
             st.sidebar.error("수집할 블로그를 선택하세요")
        else:
             start_date, end_date = st.session_state["date_range"]
             st.session_state["scrape_logs"] = []
             st.session_state["cancel_scrape"] = False
             st.session_state["scraping"] = True
             
             total_saved = 0
             total_found = 0
             
             with st.status("데이터 수집 중...", expanded=True) as status:
                 for blog in targets:
                     if st.session_state.get("cancel_scrape", False):
                         status.write("⛔ 수집이 중단되었습니다.")
                         break
                     
                     current_msg = status.empty()
                     prog_bar = status.empty()
                     current_msg.write(f"**[{blog['name']}]** 준비 중...")
                     
                     def cb(p):
                         prog_bar.progress(p)

                     def log_cb(msg):
                         msg_str = str(msg)
                         st.session_state["scrape_logs"].append(f"[{blog['name']}] {msg_str}")
                         
                         if msg_str.startswith("Title: "):
                             t = msg_str.replace("Title: ", "").strip()
                             current_msg.markdown(f"**[{blog['name']}]**\n📄 {t}")
                         elif msg_str.startswith("Processing"):
                             current_msg.markdown(f"**[{blog['name']}]**\n⏳ {msg_str}")
                         elif msg_str.startswith("Found"):
                             status.markdown(f"🔍 {msg_str}")
                         elif "error" in msg_str.lower() or "fatal" in msg_str.lower():
                             status.markdown(f"⚠️ {msg_str}")

                     def should_stop():
                         return bool(st.session_state.get("cancel_scrape", False))

                     res = collect_blog_posts(blog["name"], blog["url"], start_date, end_date, cb, log_cb, should_stop)
                     prog_bar.empty()
                     
                     saved = res.get("saved", 0)
                     found = res.get("total", 0)
                     duplicates = res.get("duplicates", 0)
                     
                     total_saved += saved
                     total_found += found
                     
                     current_msg.empty()
                     status.write(f"✅ **{blog['name']}**: 총 {found}개 발견, {saved}개 저장 ({duplicates}개 중복 스킵)")

                 if not st.session_state.get("cancel_scrape", False):
                     status.update(label="수집 완료!", state="complete", expanded=False)
                 else:
                     status.update(label="수집 중단됨", state="error", expanded=False)
                
             st.sidebar.success(f"총 {total_found}개 중 {total_saved}개 저장 완료")
             st.session_state["scraping"] = False


st.title("블로그 AI 분석기")

if st.session_state["blogs"]:
    options = {b["name"]: b["id"] for b in st.session_state["blogs"]}
    names = list(options.keys())
    default_index = 0
    if st.session_state["selected_blog_id"] in options.values():
        for i, n in enumerate(names):
            if options[n] == st.session_state["selected_blog_id"]:
                default_index = i
                break
    selected_name = st.selectbox("블로그 선택", names, index=default_index)
    st.session_state["selected_blog_id"] = options[selected_name]
else:
    st.info("블로그를 추가하세요")


def render_posts(posts: List[Dict]):
    if not posts:
        st.info("표시할 데이터가 없습니다.")
        return
    for row in posts:
        t = str(row.get("title", "")).strip()
        d = str(row.get("date", "")).strip()
        content_raw = str(row.get("content", "")).strip()
        preview_text = content_raw[:500] + ("..." if len(content_raw) > 500 else "")
        l = str(row.get("link", "")).strip()
        
        label = f"[{d}] {t}"
        with st.expander(label):
            st.write(preview_text)
            if l:
                st.markdown(f"[원본 보기]({l})")


def style_header(text, bg_color="#f0f2f6", text_color="#31333f"):
    return f"""<span style='background-color: {bg_color}; color: {text_color}; padding: 4px 10px; border-radius: 5px; font-weight: bold; font-size: 1.05em;'>{text}</span>"""


tab1, tab2 = st.tabs(["AI 분석 및 대화", "수집 데이터 조회"])

with tab1:
    # UX 개선: 가로 폭 제한 및 중앙 정렬
    _, col_main, _ = st.columns([1, 2, 1])
    
    with col_main:
        st.header("AI 분석 및 대화")
        st.session_state.setdefault("ai_question", "")
        st.session_state["ai_question"] = st.text_area("AI 질문", value=st.session_state.get("ai_question", ""), height=120)
        
        if st.button("AI 분석 요청"):
            api_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY")
            if not api_key:
                st.error("Google Gemini API 키가 설정되지 않았습니다. 환경 변수(GEMINI_API_KEY)를 확인하세요.")
            else:
                sel_name = None
                sel_url = None
                if st.session_state.get("selected_blog_id") is not None:
                    sel_list = [b for b in st.session_state["blogs"] if b["id"] == st.session_state["selected_blog_id"]]
                    if sel_list:
                        sel_name = sel_list[0]["name"]
                        sel_url = sel_list[0]["url"]
                
                start_date, end_date = st.session_state["date_range"]
                posts_for_ai = dbm.query_posts_for_blog(sel_url, start_date, end_date, "")
                
                if not posts_for_ai:
                    st.info("관련된 글이 없습니다.")
                else:
                    ctx_parts = []
                    for r in posts_for_ai:
                        ctx_parts.append(str(r.get("content", "")))
                    context_text = "\n\n".join(ctx_parts)
                    context_text = context_text[:8000]
                    system_prompt = """당신은 매크로 경제 및 산업 사이클을 분석하는 수석 투자 전략가입니다. 
제공된 블로그 글들은 단순 종목 추천이 아니라, 시장 현상의 근본 원인을 파헤치는 글들입니다. 
블로그 글에서 언급된 '현상'과 '원인'을 분리하고, 그 원인이 향후 어떤 산업이나 자산군에 영향을 미칠지 논리적으로 연결해야 합니다. 

사용자의 질문에 대해 다음 Markdown 형식(st.markdown 호환)으로 답변하세요. 
각 섹션은 반드시 '###' 헤더로 시작하고, 섹션 간에는 '---' 구분선을 넣어주세요. 

1. ### [핵심 논거] 
   - 저자가 지목하는 현상의 근본 원인(Fundamental Driver) 분석
   - 핵심 키워드는 **굵게** 표시

---

2. ### [인과 관계] 
   - 해당 원인이 초래할 연쇄적인 경제/산업적 파급 효과(Second-order Effect)
   - 논리적 흐름을 명확히 설명

---

3. ### [투자 인사이트] 
   - 주목해야 할 섹터, 자산군, 또는 주의해야 할 리스크
   - 구체적인 근거 제시

---

4. ### 결론 
   - 저자의 뷰를 바탕으로 한 투자 아이디어 3줄 요약

답변은 전문적이고 통찰력 있게 작성하되, 블로그 내용을 벗어난 없는 사실을 지어내지 마세요."""
                    question = st.session_state.get("ai_question", "")
                    with st.spinner("AI 분석 중..."):
                        ans = None
                        try:
                            try:
                                import google.generativeai as genai
                                genai.configure(api_key=api_key)
                                model_names = [
                                    "models/gemini-flash-latest",
                                    "models/gemini-2.5-flash",
                                    "models/gemini-pro-latest",
                                ]
                                last_err = None
                                resp = None
                                for mn in model_names:
                                    try:
                                        model = genai.GenerativeModel(mn)
                                        resp = model.generate_content([
                                            system_prompt,
                                            f"Context:\n{context_text}",
                                            f"Question:\n{question}",
                                        ])
                                        break
                                    except Exception as _e:
                                        last_err = _e
                                        continue
                                if resp is None and last_err is not None:
                                    raise last_err
                                ans = getattr(resp, "text", None) or str(resp)
                            except Exception as e:
                                ans = f"Gemini 호출 중 오류: {e}"
                        finally:
                            st.session_state["ai_answer"] = ans or "응답을 받을 수 없습니다."
                            st.session_state["chat_history"].append({"role": "user", "content": question})
                            st.session_state["chat_history"].append({"role": "assistant", "content": st.session_state["ai_answer"]})

        if st.session_state.get("ai_answer"):
            # 디자인 개선: 제목 아이콘 및 스타일
            st.markdown("## 💡 AI 분석 결과", unsafe_allow_html=True)
            
            raw_ans = st.session_state["ai_answer"]
            
            # 구조적 구분 및 강조
            # 예상되는 구조: ### [핵심 논거] ... --- ### [인과 관계] ... --- ### [투자 인사이트] ... --- ### 결론 ...
            
            parts = raw_ans.split("---")
            for part in parts:
                part = part.strip()
                if not part: continue
                
                # 투자 인사이트 강조
                if "### [투자 인사이트]" in part:
                    content = part.replace("### [투자 인사이트]", "").strip()
                    st.warning(f"### 💰 [투자 인사이트]\n\n{content}", icon="💰")
                else:
                    # 헤더 스타일링
                    if "### [핵심 논거]" in part:
                        new_header = style_header("🎯 [핵심 논거]", "#e8f0fe", "#174ea6")
                        part = part.replace("### [핵심 논거]", new_header)
                        st.markdown(part, unsafe_allow_html=True)
                    elif "### [인과 관계]" in part:
                        new_header = style_header("🔗 [인과 관계]", "#e6f4ea", "#137333")
                        part = part.replace("### [인과 관계]", new_header)
                        st.markdown(part, unsafe_allow_html=True)
                    elif "### 결론" in part:
                        new_header = style_header("📝 결론", "#f1f3f4", "#202124")
                        part = part.replace("### 결론", new_header)
                        st.markdown(part, unsafe_allow_html=True)
                    else:
                        st.markdown(part)
                
                st.write("") # 간격

        if st.session_state.get("chat_history"):
            st.divider()
            st.subheader("AI 대화 기록")
            # 디자인 개선: st.chat_message 사용
            for m in st.session_state["chat_history"][-10:]:
                with st.chat_message(m["role"]):
                    st.write(m["content"])

with tab2:
    # UX 개선: 가로 폭 제한 및 중앙 정렬
    _, col_main, _ = st.columns([1, 2, 1])
    
    with col_main:
        st.header("수집 데이터 조회")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            default_start, default_end = st.session_state.get("date_range", (date.today() - timedelta(days=7), date.today()))
            view_picked = st.date_input(
                "조회 기간",
                value=(default_start, default_end),
                max_value=date.today(),
                key="view_date_range"
            )
        with c2:
            st.text_input("검색어", key="search_query")

        selected_blog_url = None
        if st.session_state.get("selected_blog_id") is not None:
            sel = [b for b in st.session_state["blogs"] if b["id"] == st.session_state["selected_blog_id"]]
            if sel:
                selected_blog_url = sel[0]["url"]
        
        if selected_blog_url:
            if isinstance(view_picked, tuple) and len(view_picked) == 2:
                v_start, v_end = view_picked
                posts = dbm.query_posts_for_blog(
                    selected_blog_url, 
                    v_start, 
                    v_end, 
                    st.session_state.get("search_query", "")
                )
                
                if not posts:
                    st.info("데이터가 없습니다.")
                else:
                    items_per_page = 30
                    total_items = len(posts)
                    total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
                    
                    if "view_page" not in st.session_state:
                        st.session_state["view_page"] = 1
                    
                    if st.session_state["view_page"] > total_pages:
                        st.session_state["view_page"] = total_pages
                    if st.session_state["view_page"] < 1:
                        st.session_state["view_page"] = 1
                    
                    col_p1, col_p2 = st.columns([1, 5])
                    with col_p1:
                        page = st.number_input(
                            "페이지 이동", 
                            min_value=1, 
                            max_value=total_pages, 
                            key="view_page"
                        )
                    with col_p2:
                        st.write("") 
                        st.caption(f"전체 {total_items}개 데이터 중 {page} / {total_pages} 페이지")

                    start_idx = (page - 1) * items_per_page
                    end_idx = start_idx + items_per_page
                    current_posts = posts[start_idx:end_idx]
                    
                    render_posts(current_posts)
            else:
                st.info("기간을 선택하세요 (시작일 - 종료일)")
        else:
            st.info("블로그를 선택하세요")

if st.session_state.get("scrape_logs"):
    with st.sidebar.expander("수집 로그"):
        st.text("\n".join(st.session_state["scrape_logs"]))
