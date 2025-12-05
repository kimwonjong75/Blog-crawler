import re
import sqlite3
from datetime import datetime, date
from urllib.parse import urlparse, parse_qs
import time
import random
import sys

import requests
from bs4 import BeautifulSoup
import db_manager as dbm
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

HTTP_SESSION = requests.Session()


def get_conn():
    return sqlite3.connect("blog_data.db", check_same_thread=False)


def ensure_posts_table(blog_url: str):
    dbm.ensure_posts_table_for(blog_url)


def is_duplicate(cur, blog_name: str, title: str, d: str) -> bool:
    return dbm.is_duplicate(cur, blog_name, title, d)


def save_post(cur, blog_name: str, title: str, d: str, content: str, link: str):
    dbm.save_post(cur, blog_name, title, d, content, link)


def normalize_to_mobile(url: str) -> str:
    if not url:
        return url
    p = urlparse(url)
    if p.netloc == "m.blog.naver.com":
        return url
    if p.netloc != "blog.naver.com":
        return url
    path = p.path.strip("/")
    if path:
        return f"https://m.blog.naver.com/{path}"
    qs = parse_qs(p.query)
    blog_id = qs.get("blogId", [None])[0]
    log_no = qs.get("logNo", [None])[0]
    if blog_id and log_no:
        return f"https://m.blog.naver.com/{blog_id}/{log_no}"
    if blog_id:
        return f"https://m.blog.naver.com/{blog_id}"
    return url


def extract_iframe_src(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    iframe = soup.find("iframe", id="mainFrame")
    if iframe and iframe.get("src"):
        return iframe["src"]
    return None


def precise_sleep(seconds: float):
    end = time.monotonic() + max(0.0, float(seconds))
    while True:
        now = time.monotonic()
        if now >= end:
            break
        time.sleep(min(0.1, end - now))


def fetch(url: str, log_cb=None) -> str:
    delay = random.uniform(5, 20)
    if log_cb:
        try:
            log_cb(f"Delay {delay:.2f}s before GET {url}")
        except Exception:
            pass
    precise_sleep(delay)
    try:
        r = HTTP_SESSION.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://blog.naver.com/",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            timeout=15,
        )
        if r.status_code == 200:
            return r.text
        else:
            if log_cb:
                try:
                    log_cb(f"Status {r.status_code} for {url}")
                except Exception:
                    pass
            raise RuntimeError(f"HTTP {r.status_code} for {url}")
    except BaseException as e:
        if log_cb:
            try:
                log_cb(f"Request error {e.__class__.__name__}: {e}")
            except Exception:
                pass
        raise


def find_post_links(html: str, blog_id_hint: str | None = None) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            href = f"https://m.blog.naver.com{href}"
        if "m.blog.naver.com" in href:
            if re.search(r"/([A-Za-z0-9._-]+)/([0-9]{7,})", href):
                links.append(href)
        elif "PostView.nhn" in href and "blog.naver.com" in href:
            p = urlparse(href)
            qs = parse_qs(p.query)
            bid = (qs.get("blogId", [None])[0]) or blog_id_hint
            logno = qs.get("logNo", [None])[0]
            if bid and logno:
                links.append(f"https://m.blog.naver.com/{bid}/{logno}")
    return list(dict.fromkeys(links))


def extract_text_only(soup: BeautifulSoup) -> str:
    for img in soup.find_all("img"):
        img.decompose()
    for tag in soup(["script", "style"]):
        tag.decompose()
    container = (
        soup.select_one("div.se-main-container")
        or soup.select_one("#postViewArea")
        or soup.select_one(".se_component_wrap")
        or soup.body
    )
    text = container.get_text("\n", strip=True) if container else soup.get_text("\n", strip=True)
    text = re.sub(r"\n{2,}", "\n", text)
    return text


def parse_date_from_soup(soup: BeautifulSoup) -> date | None:
    candidates = []
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        candidates.append(meta["content"]) 
    for sel in [
        "span.se_publishDate",
        "p.se_date",
        "span.date",
        "em.pcol2",
        "span._postAddDate",
    ]:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            candidates.append(el.get_text(strip=True))

    for raw in candidates:
        for fmt in ["%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"]:
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.date()
            except Exception:
                pass
        m = re.search(r"(\d{4})[년.\-/](\d{1,2})[월.\-/](\d{1,2})", raw)
        if m:
            try:
                y, mm, dd = map(int, m.groups())
                return date(y, mm, dd)
            except Exception:
                pass
    return None


def parse_title_from_soup(soup: BeautifulSoup) -> str | None:
    for sel in ["h3.se_text_area", 
                "div.se_title h3", 
                "h3.se_title_text", 
                "span.pcol1", 
                "meta[property='og:title']"]:
        el = soup.select_one(sel)
        if el:
            if el.name == "meta":
                return el.get("content")
            t = el.get_text(strip=True)
            if t:
                return t
    return None


def collect_blog_posts(blog_name: str, blog_url: str, start_date: date, end_date: date, progress_cb=None, log_cb=None, should_stop_cb=None) -> dict:
    conn = None
    try:
        ensure_posts_table(blog_url)
        conn = dbm.get_post_conn_for(blog_url)
        cur = conn.cursor()

        mobile_url = normalize_to_mobile(blog_url)
        html = fetch(mobile_url, log_cb=log_cb)
        if not html:
            base_html = fetch(blog_url, log_cb=log_cb)
            if base_html:
                iframe_src = extract_iframe_src(base_html)
                if iframe_src:
                    html = fetch(iframe_src, log_cb=log_cb)
        if not html:
            conn.close()
            return {"total": 0, "saved": 0}

        blog_id_hint = get_blog_id_from_url(mobile_url)

        links = find_post_links(html, blog_id_hint)
        if not links and blog_id_hint:
            alt_links = fetch_post_list_links(blog_id_hint, max_pages=10, log_cb=log_cb)
            if alt_links:
                links = alt_links
        rss_date_map: dict[str, date] = {}
        items_ordered: list[tuple[str, date | None]] = []
        if blog_id_hint:
            rss_items = fetch_rss_items(blog_id_hint, log_cb=log_cb)
            if rss_items:
                for li, dd in rss_items:
                    rss_date_map[li] = dd
                items_ordered = sorted(rss_items, key=lambda x: (x[1] is not None, x[1]), reverse=True)
        if items_ordered:
            filtered_items: list[tuple[str, date | None]] = []
            for li, dd in items_ordered:
                if dd is None:
                    continue
                if dd < start_date:
                    break
                if dd <= end_date:
                    filtered_items.append((li, dd))
            iter_items = filtered_items
            total = len(iter_items)
        else:
            iter_items = [(li, None) for li in links]
            total = len(iter_items)
        if log_cb:
            try:
                log_cb(f"Found {total} post links")
            except Exception:
                pass
        saved = 0
        for i, (link, dd_hint) in enumerate(iter_items):
            if should_stop_cb and should_stop_cb():
                if log_cb:
                    try:
                        log_cb("Cancelled by user")
                    except Exception:
                        pass
                break
            if progress_cb:
                progress_cb(int((i / max(total, 1)) * 100))
            if log_cb:
                try:
                    log_cb(f"Processing [{i+1}/{total}] {link}")
                except Exception:
                    pass
            post_html = fetch(link, log_cb=log_cb)
            if not post_html:
                continue
            soup = BeautifulSoup(post_html, "html.parser")
            d = parse_date_from_soup(soup)
            if not d and dd_hint is not None:
                d = dd_hint
            if not d:
                if log_cb:
                    try:
                        log_cb("Skip: date parse failed")
                    except Exception:
                        pass
                continue
            if d < start_date or d > end_date:
                if log_cb:
                    try:
                        log_cb(f"Skip: {d.isoformat()} out of range")
                    except Exception:
                        pass
                continue
            title = parse_title_from_soup(soup) or ""
            content = extract_text_only(soup)
            d_str = d.isoformat()
            if not title:
                title = content.split("\n")[0][:80]
            
            # [중복 수집 방지]
            # 이미 DB에 (블로그명, 제목, 날짜)가 동일한 글이 있다면
            # 내용은 비교하지 않고 건너뜁니다.
            if is_duplicate(cur, blog_name, title, d_str):
                if log_cb:
                    try:
                        log_cb("Skip duplicate (Same title & date)")
                    except Exception:
                        pass
                continue
                
            save_post(cur, blog_name, title, d_str, content, link)
            saved += 1
            delay = random.uniform(5, 20)
            if log_cb:
                try:
                    log_cb(f"Sleep {delay:.2f}s")
                except Exception:
                    pass
            end = time.monotonic() + delay
            while True:
                if should_stop_cb and should_stop_cb():
                    if log_cb:
                        try:
                            log_cb("Cancelled during sleep")
                        except Exception:
                            pass
                    conn.commit()
                    conn.close()
                    if progress_cb:
                        progress_cb(100)
                    return {"total": total, "saved": saved}
                now = time.monotonic()
                if now >= end:
                    break
                time.sleep(min(0.1, end - now))

        conn.commit()
        conn.close()
        if progress_cb:
            progress_cb(100)
        return {"total": total, "saved": saved}
    except BaseException as e:
        try:
            if log_cb:
                try:
                    log_cb(f"Fatal {e.__class__.__name__}: {e}")
                except Exception:
                    pass
        finally:
            try:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
            finally:
                try:
                    HTTP_SESSION.close()
                except Exception:
                    pass
        sys.exit(1)

def get_blog_id_from_url(u: str) -> str | None:
    try:
        p = urlparse(u)
        if p.netloc in {"blog.naver.com", "m.blog.naver.com"}:
            path = p.path.strip("/")
            if path:
                return path.split("/")[0]
        qs = parse_qs(p.query)
        bid = qs.get("blogId", [None])[0]
        return bid
    except Exception:
        return None


def fetch_post_list_links(blog_id: str, max_pages: int = 3, log_cb=None) -> list[str]:
    links: list[str] = []
    for page in range(1, max_pages + 1):
        url = f"https://m.blog.naver.com/PostList.naver?blogId={blog_id}&categoryNo=0&currentPage={page}"
        html = fetch(url, log_cb=log_cb)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/"):
                href = f"https://m.blog.naver.com{href}"
            m = re.search(rf"m\.blog\.naver\.com/{re.escape(blog_id)}/(\d{7,})", href)
            if m:
                links.append(href)
            else:
                # desktop style view
                if "PostView.nhn" in href and "blog.naver.com" in href:
                    p = urlparse(href)
                    qs = parse_qs(p.query)
                    bid = qs.get("blogId", [None])[0]
                    logno = qs.get("logNo", [None])[0]
                    if bid == blog_id and logno:
                        links.append(f"https://m.blog.naver.com/{blog_id}/{logno}")
        if log_cb:
            try:
                log_cb(f"PostList page {page} collected {len(links)} links so far")
            except Exception:
                pass
    return list(dict.fromkeys(links))

def fetch_rss_items(blog_id: str, log_cb=None) -> list[tuple[str, date]]:
    url = f"https://rss.blog.naver.com/{blog_id}.xml"
    xml_text = fetch(url, log_cb=log_cb)
    items: list[tuple[str, date]] = []
    if not xml_text:
        return items
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return items
    for it in root.findall('.//item'):
        link_el = it.find('link')
        date_el = it.find('pubDate')
        if link_el is None or (link_el.text or '').strip() == '':
            continue
        link = (link_el.text or '').strip()
        p = urlparse(link)
        if p.netloc == 'blog.naver.com':
            path = p.path.strip('/')
            if path:
                link = f"https://m.blog.naver.com/{path}"
        d: date | None = None
        raw = (date_el.text or '').strip() if date_el is not None else ''
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                d = dt.date()
            except Exception:
                for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
                    try:
                        dt = datetime.strptime(raw, fmt)
                        d = dt.date()
                        break
                    except Exception:
                        pass
        items.append((link, d))
    if log_cb:
        try:
            log_cb(f"RSS items: {len(items)}")
        except Exception:
            pass
    return items
