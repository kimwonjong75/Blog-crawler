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
    if "gemini_api_key" not in st.session_state:
        st.session_state["gemini_api_key"] = ""
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
    st.header("앱 설정")
    st.session_state["gemini_api_key"] = st.text_input(
        "Google Gemini API 키",
        value=st.session_state.get("gemini_api_key", ""),
        type="password",
    )

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

    if st.session_state["blogs"]:
        df_sidebar = pd.DataFrame(st.session_state["blogs"])
        st.dataframe(df_sidebar[["name", "url"]], use_container_width=True, height=200)
        st.subheader("재수집 대상")
        for b in st.session_state["blogs"]:
            st.checkbox(f"{b['name']}", key=f"collect_chk_{b['id']}")

    st.header("수집 기간")
    default_start, default_end = st.session_state["date_range"]
    picked = st.date_input(
        "기간 선택",
        
        value=(default_start, default_end),
        max_value=date.today(),
    )
    if isinstance(picked, tuple) and len(picked) == 2:
        st.session_state["date_range"] = picked

    if st.button("데이터 수집 시작", use_container_width=True):
        if not st.session_state.get("selected_blog_id"):
            st.sidebar.error("메인 화면에서 블로그를 선택하세요")
        else:
            sel = [b for b in st.session_state["blogs"] if b["id"] == st.session_state["selected_blog_id"]]
            if not sel:
                st.sidebar.error("블로그 선택 정보가 없습니다")
            else:
                selected_ids = [b["id"] for b in st.session_state["blogs"] if st.session_state.get(f"collect_chk_{b['id']}", False)]
                targets = [b for b in st.session_state["blogs"] if b["id"] in selected_ids] or sel
                start_date, end_date = st.session_state["date_range"]
                st.session_state["scrape_logs"] = []
                st.session_state["cancel_scrape"] = False
                st.session_state["scraping"] = True
                total_saved = 0
                total_found = 0
                for blog in targets:
                    if st.session_state.get("cancel_scrape", False):
                        break
                    bar = st.progress(0)
                    def cb(p):
                        try:
                            bar.progress(min(max(int(p), 0), 100))
                        except Exception:
                            pass
                    def log_cb(msg):
                        try:
                            st.session_state["scrape_logs"].append(f"[{blog['name']}] {str(msg)}")
                        except Exception:
                            pass
                    def should_stop():
                        return bool(st.session_state.get("cancel_scrape", False))
                    res = collect_blog_posts(blog["name"], blog["url"], start_date, end_date, cb, log_cb, should_stop)
                    total_saved += res.get("saved", 0)
                    total_found += res.get("total", 0)
                st.sidebar.success(f"총 {total_found}개 중 {total_saved}개 저장 완료")
                st.session_state["scraping"] = False


st.title("블로그 AI 분석기")

col1, col2 = st.columns([3, 2])
with col1:
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

with col2:
    st.session_state.setdefault("ai_question", "")
    st.session_state["ai_question"] = st.text_area("AI 질문", value=st.session_state.get("ai_question", ""), height=120)
    if st.session_state.get("scraping"):
        if st.button("수집중단"):
            st.session_state["cancel_scrape"] = True
    if st.button("AI 분석 요청"):
        api_key = st.session_state.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)
        if not api_key:
            st.warning("사이드바에서 API 키를 입력하세요")
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
                system_prompt = "너는 블로그 전문가야. 아래 제공된 블로그 글들을 바탕으로 사용자의 질문에 대해 요약하고, 유용한 조언을 해줘."
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
                            ans = getattr(resp, "text", None) or str(resp)
                        except Exception as e:
                            ans = f"Gemini 호출 중 오류: {e}"
                    finally:
                        st.session_state["ai_answer"] = ans or "응답을 받을 수 없습니다."
                        st.session_state["chat_history"].append({"role": "user", "content": question})
                        st.session_state["chat_history"].append({"role": "assistant", "content": st.session_state["ai_answer"]})

st.divider()

if st.session_state["selected_blog_id"] is not None:
    sel = [b for b in st.session_state["blogs"] if b["id"] == st.session_state["selected_blog_id"]]
    if sel:
        st.subheader(f"선택된 블로그: {sel[0]['name']}")
else:
    st.subheader("선택된 블로그: 없음")

st.subheader("글 목록")
def query_posts(blog_name: Optional[str], start_date: date, end_date: date, keyword: str) -> List[Dict]:
    conn = sqlite3.connect("blog_data.db")
    try:
        where = ["date BETWEEN ? AND ?"]
        params: List = [start_date.isoformat(), end_date.isoformat()]
        if blog_name:
            where.append("blog_name = ?")
            params.append(blog_name)
        kw = keyword.strip()
        if kw:
            where.append("(title LIKE ? OR content LIKE ?)")
            like = f"%{kw}%"
            params.extend([like, like])
        sql = "SELECT blog_name, title, date, content, link, created_at FROM posts WHERE " + " AND ".join(where) + " ORDER BY date DESC, created_at DESC"
        df = pd.read_sql_query(sql, conn, params=params)
        return df.to_dict("records") if not df.empty else []
    finally:
        conn.close()

def render_posts(posts: List[Dict]):
    if not posts:
        st.info("관련된 글이 없습니다.")
        return
    for row in posts:
        with st.container():
            t = str(row.get("title", "")).strip()
            d = str(row.get("date", "")).strip()
            c = str(row.get("content", "")).replace("\n", " ")
            s = c[:100]
            l = str(row.get("link", "")).strip()
            st.write(f"[{d}] {t}")
            st.write(s)
            if l:
                st.markdown(f'<a href="{l}" target="_blank">원본 보기</a>', unsafe_allow_html=True)
        st.divider()

selected_blog_name = None
selected_blog_url = None
if st.session_state.get("selected_blog_id") is not None:
    sel = [b for b in st.session_state["blogs"] if b["id"] == st.session_state["selected_blog_id"]]
    if sel:
        selected_blog_name = sel[0]["name"]
        selected_blog_url = sel[0]["url"]

start_date, end_date = st.session_state["date_range"]
keyword = st.session_state.get("search_query", "")
posts = dbm.query_posts_for_blog(selected_blog_url, start_date, end_date, keyword)
if st.session_state.get("ai_answer"):
    st.subheader("AI 분석 결과")
    st.markdown(st.session_state["ai_answer"])
if st.session_state.get("chat_history"):
    st.subheader("AI 대화 기록")
    for m in st.session_state["chat_history"][-10:]:
        st.write(f"{m['role']}: {m['content']}")
if st.session_state.get("scrape_logs"):
    st.subheader("수집 로그")
    st.text("\n".join(st.session_state["scrape_logs"]))
render_posts(posts)

