import sqlite3
from datetime import date
import pandas as pd
import os
from urllib.parse import urlparse, parse_qs


def _extract_blog_id(blog_url: str) -> str | None:
    try:
        p = urlparse(blog_url)
        if p.netloc in {"blog.naver.com", "m.blog.naver.com"}:
            path = p.path.strip("/")
            if path:
                return path.split("/")[0]
        qs = parse_qs(p.query)
        bid = qs.get("blogId", [None])[0]
        return bid
    except Exception:
        return None


def _post_db_path(blog_url: str) -> str:
    bid = _extract_blog_id(blog_url) or "default"
    fname = f"posts_{bid}.db"
    return os.path.join(os.getcwd(), fname)


def get_blog_conn():
    return sqlite3.connect("data.db", check_same_thread=False)


def get_post_conn():
    return sqlite3.connect("blog_data.db", check_same_thread=False)


def get_post_conn_for(blog_url: str):
    return sqlite3.connect(_post_db_path(blog_url), check_same_thread=False)


def ensure_blogs_table():
    conn = get_blog_conn()
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


def ensure_posts_table():
    conn = get_post_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_name TEXT NOT NULL,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            content TEXT NOT NULL,
            link TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_posts_table_for(blog_url: str):
    conn = get_post_conn_for(blog_url)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_name TEXT NOT NULL,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            content TEXT NOT NULL,
            link TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def load_blogs():
    conn = get_blog_conn()
    try:
        df = pd.read_sql_query("SELECT id, name, url FROM blogs ORDER BY id DESC", conn)
        return df.to_dict("records") if not df.empty else []
    finally:
        conn.close()


def add_blog(name: str, url: str, created_at: str):
    conn = get_blog_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO blogs(name, url, created_at) VALUES (?, ?, ?)",
            (name, url, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def query_posts(blog_name: str | None, start_date: date, end_date: date, keyword: str):
    conn = get_post_conn()
    try:
        where = ["date BETWEEN ? AND ?"]
        params = [start_date.isoformat(), end_date.isoformat()]
        if blog_name:
            where.append("blog_name = ?")
            params.append(blog_name)
        kw = (keyword or "").strip()
        if kw:
            where.append("(title LIKE ? OR content LIKE ?)" )
            like = f"%{kw}%"
            params.extend([like, like])
        sql = (
            "SELECT blog_name, title, date, content, link, created_at FROM posts WHERE "
            + " AND ".join(where)
            + " ORDER BY date DESC, created_at DESC"
        )
        df = pd.read_sql_query(sql, conn, params=params)
        return df.to_dict("records") if not df.empty else []
    finally:
        conn.close()


def query_posts_for_blog(blog_url: str | None, start_date: date, end_date: date, keyword: str):
    if not blog_url:
        # fallback to global db
        return query_posts(None, start_date, end_date, keyword)
    # ensure table exists for this blog DB
    ensure_posts_table_for(blog_url)
    conn = get_post_conn_for(blog_url)
    try:
        # auto-migrate from global DB if this blog DB is empty and global has data
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM posts")
            count = cur.fetchone()[0]
        except Exception:
            count = 0
        if count == 0:
            try:
                # lookup blog_name by url from blogs table
                bconn = get_blog_conn()
                bcur = bconn.cursor()
                bcur.execute("SELECT name FROM blogs WHERE url = ? LIMIT 1", (blog_url,))
                row = bcur.fetchone()
                bconn.close()
                blog_name = row[0] if row else None
                if blog_name:
                    gconn = get_post_conn()
                    gcur = gconn.cursor()
                    gcur.execute("SELECT blog_name, title, date, content, link, created_at FROM posts WHERE blog_name = ?", (blog_name,))
                    rows = gcur.fetchall()
                    gconn.close()
                    if rows:
                        cur2 = conn.cursor()
                        for r in rows:
                            # r: (blog_name, title, date, content, link, created_at)
                            cur2.execute(
                                "SELECT 1 FROM posts WHERE blog_name = ? AND title = ? AND date = ? LIMIT 1",
                                (r[0], r[1], r[2]),
                            )
                            if cur2.fetchone() is None:
                                cur2.execute(
                                    "INSERT INTO posts(blog_name, title, date, content, link, created_at) VALUES(?,?,?,?,?,?)",
                                    r,
                                )
                        conn.commit()
            except Exception:
                pass
        where = ["date BETWEEN ? AND ?"]
        params = [start_date.isoformat(), end_date.isoformat()]
        kw = (keyword or "").strip()
        if kw:
            where.append("(title LIKE ? OR content LIKE ?)" )
            like = f"%{kw}%"
            params.extend([like, like])
        sql = (
            "SELECT blog_name, title, date, content, link, created_at FROM posts WHERE "
            + " AND ".join(where)
            + " ORDER BY date DESC, created_at DESC"
        )
        df = pd.read_sql_query(sql, conn, params=params)
        return df.to_dict("records") if not df.empty else []
    finally:
        conn.close()


def is_duplicate(cur, blog_name: str, title: str, d: str) -> bool:
    cur.execute(
        "SELECT 1 FROM posts WHERE blog_name = ? AND title = ? AND date = ? LIMIT 1",
        (blog_name, title, d),
    )
    return cur.fetchone() is not None


def save_post(cur, blog_name: str, title: str, d: str, content: str, link: str):
    cur.execute(
        "INSERT INTO posts(blog_name, title, date, content, link, created_at) VALUES(?,?,?,?,?,?)",
        (blog_name, title, d, content, link, pd.Timestamp.utcnow().isoformat()),
    )


def create_chats_table():
    conn = get_blog_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def save_chat_history(session_id: str, role: str, content: str):
    conn = get_blog_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chats(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, pd.Timestamp.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def load_chat_history(session_id: str):
    conn = get_blog_conn()
    try:
        df = pd.read_sql_query(
            "SELECT session_id, role, content, timestamp FROM chats WHERE session_id = ? ORDER BY timestamp ASC",
            conn,
            params=(session_id,),
        )
        return df.to_dict("records") if not df.empty else []
    finally:
        conn.close()
