#!/usr/bin/env python3
"""WordPress XML export to static HTML site generator."""

import xml.etree.ElementTree as ET
import re
import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

# ---- 設定 ----
XML_FILE = "WordPress.2026-04-29.xml"
OUTPUT_DIR = "docs"

SITE_TITLE = "半地下店舗兼用準防火第一種低層狭小住宅"
SITE_DESCRIPTION = "東京都内サラリーマン「てんすけち」による家づくり記録。\n半地下・店舗兼用・狭小住宅という変わった家づくりの全記録。"
AUTHOR_NAME = "てんすけち"

NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt":  "http://wordpress.org/export/1.2/excerpt/",
    "dc":       "http://purl.org/dc/elements/1.1/",
    "wp":       "http://wordpress.org/export/1.2/",
}

# ---- XMLパース ----

def parse_xml(filepath):
    tree = ET.parse(filepath)
    return tree.getroot().find("channel")


def get_text(el, tag, ns_key=None):
    child = el.find(f"{{{NS[ns_key]}}}{tag}") if ns_key else el.find(tag)
    if child is None:
        return ""
    return (child.text or "").strip()


def parse_categories(channel):
    cats = {}
    for cat in channel.findall(f"{{{NS['wp']}}}category"):
        nicename = get_text(cat, "category_nicename", "wp")
        name = get_text(cat, "cat_name", "wp")
        if nicename and name:
            cats[nicename] = name
    return cats


def parse_attachments(channel):
    """attachment_id -> url のマップを返す。"""
    att = {}
    for item in channel.findall("item"):
        if get_text(item, "post_type", "wp") != "attachment":
            continue
        pid = get_text(item, "post_id", "wp")
        aurl_el = item.find(f"{{{NS['wp']}}}attachment_url")
        aurl = (aurl_el.text or "").strip() if aurl_el is not None else ""
        if pid and aurl:
            att[pid] = aurl
    return att


def parse_posts(channel, attachments):
    posts = []
    for item in channel.findall("item"):
        if get_text(item, "post_type", "wp") != "post":
            continue
        if get_text(item, "status", "wp") != "publish":
            continue

        title = get_text(item, "title")
        slug = unquote(get_text(item, "post_name", "wp"))
        pub_date_str = get_text(item, "post_date", "wp")
        content_el = item.find(f"{{{NS['content']}}}encoded")
        content = (content_el.text or "") if content_el is not None else ""
        excerpt_el = item.find(f"{{{NS['excerpt']}}}encoded")
        excerpt = (excerpt_el.text or "") if excerpt_el is not None else ""

        cats = []
        for cat_el in item.findall("category"):
            if cat_el.get("domain") == "category":
                nn = cat_el.get("nicename", "")
                name = (cat_el.text or "").strip()
                if nn and name:
                    cats.append({"nicename": nn, "name": name})

        # サムネイルURL
        thumb_id = None
        for meta in item.findall(f"{{{NS['wp']}}}postmeta"):
            k = meta.find(f"{{{NS['wp']}}}meta_key")
            v = meta.find(f"{{{NS['wp']}}}meta_value")
            if k is not None and k.text == "_thumbnail_id" and v is not None:
                thumb_id = (v.text or "").strip()
        thumb_url = attachments.get(thumb_id, "") if thumb_id else ""

        try:
            pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pub_date = datetime.now()

        if not slug:
            slug = get_text(item, "post_id", "wp")
        if not slug.isascii():
            slug = f"post_{get_text(item, 'post_id', 'wp')}"

        posts.append({
            "title": title,
            "slug": slug,
            "pub_date": pub_date,
            "pub_date_str": pub_date.strftime("%Y/%m/%d"),
            "content": content,
            "excerpt": excerpt,
            "categories": cats,
            "thumb_url": thumb_url,
        })

    posts.sort(key=lambda p: p["pub_date"])
    return posts


# ---- コンテンツ変換 ----

def wp_content_to_html(content):
    content = re.sub(r'\[/?[a-z_-]+[^\]]*\]', '', content)
    content = re.sub(r'<!--\s*/?wp:[^\-].*?-->', '', content, flags=re.DOTALL)
    content = re.sub(r'<!-- notionvc:[^>]+-->', '', content)
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


def make_excerpt(content, excerpt, length=100):
    src = excerpt if excerpt else content
    text = re.sub(r'<[^>]+>', '', src).strip()
    text = re.sub(r'\s+', ' ', text)
    return text[:length] + ("…" if len(text) > length else "")


def build_cat_posts(posts):
    cat_posts = {}
    for p in posts:
        for c in p["categories"]:
            nn = c["nicename"]
            if nn not in cat_posts:
                cat_posts[nn] = {"name": c["name"], "posts": []}
            cat_posts[nn]["posts"].append(p)
    return dict(sorted(cat_posts.items(), key=lambda x: x[1]["name"]))


# ---- CSS ----

CSS = """
/* ===== Google Fonts ===== */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');

:root {
  --accent:      #d9381e;
  --accent-dark: #b02e18;
  --accent-light:#fdf0ee;
  --bg:          #f0ede8;
  --card-bg:     #ffffff;
  --text:        #333333;
  --muted:       #888888;
  --border:      #e0dbd4;
  --header-bg:   #ffffff;
  --footer-bg:   #2b2b2b;
  --sidebar-w:   300px;
  --main-max:    1100px;
  --radius:      6px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Noto Sans JP', "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 15px;
  line-height: 1.8;
}

a { color: var(--accent); text-decoration: none; }
a:hover { color: var(--accent-dark); text-decoration: underline; }
img { max-width: 100%; height: auto; }

/* ===== ヘッダー ===== */
.site-header {
  background: var(--header-bg);
  border-bottom: 3px solid var(--accent);
  box-shadow: 0 2px 6px rgba(0,0,0,0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-inner {
  max-width: var(--main-max);
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  min-height: 64px;
}
.site-logo {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}
.site-name {
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text);
  white-space: nowrap;
}
.site-name a { color: inherit; }
.site-name a:hover { text-decoration: none; color: var(--accent); }
.site-tagline {
  font-size: 0.72rem;
  color: var(--muted);
}
.header-nav {
  display: flex;
  gap: 0.2rem;
  flex-shrink: 0;
}
.header-nav a {
  font-size: 0.78rem;
  padding: 0.3rem 0.8rem;
  border-radius: 3px;
  color: var(--text);
  white-space: nowrap;
  transition: background 0.15s;
}
.header-nav a:hover {
  background: var(--accent-light);
  color: var(--accent);
  text-decoration: none;
}

/* ===== パンくず ===== */
.breadcrumb-bar {
  background: #f7f4f0;
  border-bottom: 1px solid var(--border);
}
.breadcrumb {
  max-width: var(--main-max);
  margin: 0 auto;
  padding: 0.5rem 20px;
  font-size: 0.78rem;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.breadcrumb a { color: var(--accent); }
.breadcrumb-sep { color: #ccc; }

/* ===== メインレイアウト ===== */
.page-wrap {
  max-width: var(--main-max);
  margin: 0 auto;
  padding: 28px 20px 48px;
  display: grid;
  grid-template-columns: 1fr var(--sidebar-w);
  gap: 28px;
  align-items: start;
}
.page-wrap.full-width {
  grid-template-columns: 1fr;
}

/* ===== カテゴリー見出し ===== */
.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--accent);
}
.section-title h2 {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text);
}
.section-title h2 a { color: inherit; }
.section-title h2 a:hover { color: var(--accent); text-decoration: none; }
.section-count {
  font-size: 0.72rem;
  color: #fff;
  background: var(--accent);
  padding: 0.1rem 0.5rem;
  border-radius: 10px;
}
.section-more {
  margin-left: auto;
  font-size: 0.78rem;
  color: var(--accent);
}
.section-more:hover { text-decoration: underline; }
.category-section { margin-bottom: 36px; }

/* ===== 記事カードグリッド ===== */
.post-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  list-style: none;
}
.post-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: box-shadow 0.2s, transform 0.2s;
}
.post-card:hover {
  box-shadow: 0 6px 22px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}
.post-thumb {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  background: #e8e2da;
}
.post-thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: linear-gradient(135deg, #e8e0d4 0%, #d4cbbf 100%);
  color: #aaa;
  font-size: 2rem;
}
.post-card-body {
  padding: 12px 14px 14px;
}
.post-cat-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 6px;
}
.cat-badge {
  font-size: 0.68rem;
  color: var(--accent);
  background: var(--accent-light);
  border: 1px solid #f0c0b0;
  padding: 0.1rem 0.5rem;
  border-radius: 3px;
  line-height: 1.6;
}
.cat-badge:hover { background: var(--accent); color: #fff; text-decoration: none; border-color: var(--accent); }
.post-card-body h3 {
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.5;
  margin-bottom: 5px;
}
.post-card-body h3 a { color: var(--text); }
.post-card-body h3 a:hover { color: var(--accent); text-decoration: none; }
.post-date {
  font-size: 0.72rem;
  color: var(--muted);
}

/* カテゴリーページ・横並びリスト */
.post-list-rows { list-style: none; }
.post-row {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 12px;
  display: flex;
  gap: 0;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.post-row:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.09); }
.post-row-thumb {
  width: 160px;
  flex-shrink: 0;
  object-fit: cover;
  display: block;
  background: #e8e2da;
}
.post-row-thumb-placeholder {
  width: 160px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #e8e0d4 0%, #d4cbbf 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #bbb;
  font-size: 1.5rem;
}
.post-row-body {
  padding: 12px 16px;
  flex: 1;
  min-width: 0;
}
.post-row-body h3 {
  font-size: 0.95rem;
  font-weight: 700;
  margin-bottom: 5px;
  line-height: 1.5;
}
.post-row-body h3 a { color: var(--text); }
.post-row-body h3 a:hover { color: var(--accent); text-decoration: none; }
.post-row-excerpt { font-size: 0.82rem; color: #666; line-height: 1.65; margin-top: 5px; }

/* ===== 記事ページ ===== */
article.post {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.post-hero-img {
  width: 100%;
  max-height: 380px;
  object-fit: cover;
  display: block;
}
.post-header {
  padding: 22px 26px 18px;
  border-bottom: 1px solid var(--border);
}
article.post h1 {
  font-size: 1.45rem;
  line-height: 1.5;
  margin-bottom: 10px;
  color: var(--text);
}
.post-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.post-body {
  padding: 22px 26px 28px;
  font-size: 0.95rem;
  line-height: 1.9;
}
.post-body h2 {
  font-size: 1.15rem;
  font-weight: 700;
  margin: 2rem 0 0.7rem;
  padding: 0.5rem 0.9rem;
  background: var(--accent-light);
  border-left: 4px solid var(--accent);
  color: var(--text);
  border-radius: 0 4px 4px 0;
}
.post-body h3 {
  font-size: 1.02rem;
  font-weight: 700;
  margin: 1.6rem 0 0.55rem;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--border);
}
.post-body h4 {
  font-size: 0.95rem;
  font-weight: 700;
  margin: 1.3rem 0 0.45rem;
  color: var(--accent-dark);
}
.post-body p { margin-bottom: 1rem; }
.post-body ul, .post-body ol { margin: 0.7rem 0 1rem 1.6rem; }
.post-body li { margin-bottom: 0.4rem; }
.post-body img {
  max-width: 100%;
  height: auto;
  border-radius: 6px;
  margin: 1rem 0;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.post-body blockquote {
  border-left: 4px solid var(--accent);
  background: var(--accent-light);
  padding: 0.8rem 1.2rem;
  margin: 1.1rem 0;
  border-radius: 0 6px 6px 0;
  color: #555;
}
.post-body table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
.post-body th, .post-body td { border: 1px solid var(--border); padding: 0.5rem 0.8rem; }
.post-body th { background: var(--accent-light); font-weight: 700; }
.post-body tr:nth-child(even) td { background: #faf8f5; }

/* 前後ナビ */
.post-footer {
  padding: 18px 26px;
  border-top: 1px solid var(--border);
  background: #faf8f5;
}
.post-nav {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}
.post-nav a {
  display: block;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 0.82rem;
  color: var(--text);
  background: var(--card-bg);
  line-height: 1.5;
  transition: border-color 0.15s, color 0.15s;
}
.post-nav a:hover { border-color: var(--accent); color: var(--accent); text-decoration: none; }
.nav-label { font-size: 0.68rem; color: var(--muted); display: block; margin-bottom: 2px; }
.nav-next { text-align: right; }
.back-link { font-size: 0.82rem; }

/* ===== サイドバー ===== */
.sidebar { display: flex; flex-direction: column; gap: 20px; }
.widget {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.widget-title {
  background: var(--accent);
  color: #fff;
  font-size: 0.85rem;
  font-weight: 700;
  padding: 8px 14px;
  letter-spacing: 0.03em;
}
.widget-body { padding: 12px 14px; }

/* カテゴリーウィジェット */
.widget-cats { list-style: none; }
.widget-cats li {
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.widget-cats li:last-child { border-bottom: none; }
.widget-cats a { color: var(--text); }
.widget-cats a:hover { color: var(--accent); text-decoration: none; }
.widget-cat-count {
  font-size: 0.72rem;
  color: var(--muted);
  background: var(--bg);
  padding: 0.1rem 0.45rem;
  border-radius: 10px;
}

/* 最近の投稿ウィジェット */
.widget-posts { list-style: none; }
.widget-post {
  display: flex;
  gap: 9px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
  align-items: flex-start;
}
.widget-post:last-child { border-bottom: none; }
.widget-post-thumb {
  width: 60px;
  height: 45px;
  object-fit: cover;
  border-radius: 4px;
  flex-shrink: 0;
  background: #e8e2da;
}
.widget-post-thumb-placeholder {
  width: 60px;
  height: 45px;
  border-radius: 4px;
  flex-shrink: 0;
  background: linear-gradient(135deg, #e8e0d4 0%, #d4cbbf 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  color: #bbb;
}
.widget-post-info { flex: 1; min-width: 0; }
.widget-post-info a {
  font-size: 0.8rem;
  color: var(--text);
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.widget-post-info a:hover { color: var(--accent); text-decoration: none; }
.widget-post-date { font-size: 0.68rem; color: var(--muted); margin-top: 2px; }

/* プロフィールウィジェット */
.widget-profile {
  text-align: center;
  padding: 16px 14px;
}
.profile-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--accent-light);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 10px;
  font-size: 2rem;
  border: 3px solid var(--accent);
}
.profile-name { font-size: 0.95rem; font-weight: 700; margin-bottom: 6px; }
.profile-desc { font-size: 0.78rem; color: #666; line-height: 1.7; text-align: left; }

/* ===== カテゴリーページ hero ===== */
.cat-page-hero {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 22px;
  margin-bottom: 18px;
  border-left: 5px solid var(--accent);
}
.cat-page-hero h1 { font-size: 1.2rem; font-weight: 700; color: var(--text); }
.cat-page-hero .cat-count { font-size: 0.8rem; color: var(--muted); margin-top: 3px; }

/* ===== フッター ===== */
footer {
  background: var(--footer-bg);
  color: rgba(255,255,255,0.6);
  padding: 36px 20px 24px;
  font-size: 0.82rem;
  margin-top: 0;
}
.footer-inner {
  max-width: var(--main-max);
  margin: 0 auto;
}
.footer-nav {
  display: flex;
  gap: 1.2rem;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.footer-nav a { color: rgba(255,255,255,0.7); }
.footer-nav a:hover { color: #fff; text-decoration: none; }
.footer-cats-section { margin-bottom: 18px; }
.footer-cats-title { font-size: 0.75rem; color: rgba(255,255,255,0.4); margin-bottom: 8px; letter-spacing: 0.05em; text-transform: uppercase; }
.footer-cats-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.footer-cat-link {
  font-size: 0.75rem;
  color: rgba(255,255,255,0.6);
  border: 1px solid rgba(255,255,255,0.15);
  padding: 0.2rem 0.6rem;
  border-radius: 3px;
  transition: all 0.15s;
}
.footer-cat-link:hover { color: #fff; border-color: rgba(255,255,255,0.4); text-decoration: none; }
.footer-copy { color: rgba(255,255,255,0.35); font-size: 0.75rem; }

/* ===== note バナー ===== */
.note-banner-wrap {
  background: #fff;
  border-top: 1px solid var(--border);
  padding: 24px 20px;
}
.note-banner {
  max-width: var(--main-max);
  margin: 0 auto;
}
.note-banner-link {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(135deg, #41c9b4 0%, #00b294 100%);
  color: #fff !important;
  border-radius: 10px;
  padding: 18px 24px;
  text-decoration: none !important;
  box-shadow: 0 4px 16px rgba(0,178,148,0.3);
  transition: transform 0.2s, box-shadow 0.2s;
}
.note-banner-link:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,178,148,0.4);
  text-decoration: none !important;
  color: #fff !important;
}
.note-banner-icon {
  font-size: 2.2rem;
  flex-shrink: 0;
  line-height: 1;
}
.note-banner-text { flex: 1; }
.note-banner-label {
  font-size: 0.72rem;
  opacity: 0.85;
  letter-spacing: 0.05em;
  margin-bottom: 3px;
  display: block;
}
.note-banner-title {
  font-size: 1.0rem;
  font-weight: 700;
  line-height: 1.45;
}
.note-banner-arrow {
  font-size: 1.4rem;
  flex-shrink: 0;
  opacity: 0.8;
}

/* ===== レスポンシブ ===== */
@media (max-width: 768px) {
  .page-wrap {
    grid-template-columns: 1fr;
    padding: 16px 12px 36px;
  }
  .post-grid { grid-template-columns: 1fr 1fr; gap: 10px; }
  .header-inner { flex-direction: column; align-items: flex-start; padding: 10px 16px; min-height: unset; }
  .header-nav { flex-wrap: wrap; }
  .post-row-thumb, .post-row-thumb-placeholder { width: 100px; }
  .post-header, .post-body, .post-footer { padding: 16px; }
  article.post h1 { font-size: 1.2rem; }
}
@media (max-width: 480px) {
  .post-grid { grid-template-columns: 1fr; }
  .post-nav { grid-template-columns: 1fr; }
}
"""


# ---- ヘルパー ----

def thumb_html(url, alt="", cls="post-thumb"):
    if url:
        return f'<img src="{url}" alt="{html.escape(alt)}" class="{cls}" loading="lazy">'
    return f'<div class="{cls}-placeholder">🏠</div>'


def sidebar_html(all_posts, cat_posts, base_path=""):
    # 最近の投稿（新しい順 10件）
    recent = list(reversed(all_posts))[:10]
    recent_items = ""
    for p in recent:
        t = thumb_html(p["thumb_url"], p["title"], "widget-post-thumb")
        recent_items += f"""<li class="widget-post">
  <a href="{base_path}posts/{p['slug']}.html">{t}</a>
  <div class="widget-post-info">
    <a href="{base_path}posts/{p['slug']}.html">{html.escape(p['title'])}</a>
    <div class="widget-post-date">{p['pub_date_str']}</div>
  </div>
</li>"""

    # カテゴリーリスト
    cat_items = ""
    for nn, data in cat_posts.items():
        if nn == "uncategorized":
            continue
        cnt = len(data["posts"])
        cat_items += f"""<li>
  <a href="{base_path}categories/{nn}.html">{html.escape(data['name'])}</a>
  <span class="widget-cat-count">{cnt}</span>
</li>"""

    return f"""<aside class="sidebar">
  <div class="widget">
    <div class="widget-title">プロフィール</div>
    <div class="widget-body widget-profile">
      <div class="profile-avatar">🏠</div>
      <div class="profile-name">{html.escape(AUTHOR_NAME)}</div>
      <div class="profile-desc">東京都内に住むサラリーマン。<br>変わった家づくりの全記録を公開中。</div>
    </div>
  </div>
  <div class="widget">
    <div class="widget-title">最近の投稿</div>
    <div class="widget-body" style="padding:6px 14px">
      <ul class="widget-posts">{recent_items}</ul>
    </div>
  </div>
  <div class="widget">
    <div class="widget-title">カテゴリー</div>
    <div class="widget-body" style="padding:6px 14px">
      <ul class="widget-cats">{cat_items}</ul>
    </div>
  </div>
</aside>"""


def page_shell(title, body_content, base_path="", all_posts=None, cat_posts=None, breadcrumb="", is_top=False):
    page_title = SITE_TITLE if is_top else f"{title} | {SITE_TITLE}"
    sidebar = sidebar_html(all_posts, cat_posts, base_path) if (all_posts and cat_posts) else ""

    # ヘッダーナビ（カテゴリー）
    nav_links = ""
    if cat_posts:
        for nn, d in cat_posts.items():
            if nn != "uncategorized":
                nav_links += f'<a href="{base_path}categories/{nn}.html">{html.escape(d["name"])}</a>'

    breadcrumb_bar = f'<div class="breadcrumb-bar"><nav class="breadcrumb">{breadcrumb}</nav></div>' if breadcrumb else ""

    # フッターカテゴリー
    footer_cats = ""
    if cat_posts:
        for nn, d in cat_posts.items():
            if nn != "uncategorized":
                footer_cats += f'<a class="footer-cat-link" href="{base_path}categories/{nn}.html">{html.escape(d["name"])}</a>'

    wrap_class = "page-wrap" if sidebar else "page-wrap full-width"

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(SITE_DESCRIPTION.replace(chr(10), ' '))}">
  <style>{CSS}</style>
</head>
<body>
<header class="site-header">
  <div class="header-inner">
    <div class="site-logo">
      <div class="site-name"><a href="{base_path}index.html">{html.escape(SITE_TITLE)}</a></div>
      <div class="site-tagline">by {html.escape(AUTHOR_NAME)}</div>
    </div>
    <nav class="header-nav">{nav_links}</nav>
  </div>
</header>
{breadcrumb_bar}
<div class="{wrap_class}">
  <main>{body_content}</main>
  {sidebar}
</div>
<div class="note-banner-wrap">
  <div class="note-banner">
    <a class="note-banner-link" href="https://note.com/vast_acacia8657/n/nbbd0dd62acf4" target="_blank" rel="noopener">
      <span class="note-banner-icon">📝</span>
      <span class="note-banner-text">
        <span class="note-banner-label">note で読む</span>
        <span class="note-banner-title">地下室はやるべきか？5坪で1300万円かかった実体験｜tensukechi</span>
      </span>
      <span class="note-banner-arrow">→</span>
    </a>
  </div>
</div>
<footer>
  <div class="footer-inner">
    <div class="footer-cats-section">
      <div class="footer-cats-title">カテゴリー</div>
      <div class="footer-cats-list">{footer_cats}</div>
    </div>
    <div class="footer-copy">&copy; 2024-2026 {html.escape(SITE_TITLE)}</div>
  </div>
</footer>
</body>
</html>"""


# ---- ページ生成 ----

def build_index(posts, categories, cat_posts):
    sections = []
    for nicename, data in cat_posts.items():
        if nicename == "uncategorized":
            continue
        cards = []
        for p in data["posts"]:
            t = thumb_html(p["thumb_url"], p["title"])
            cat_badges = "".join(
                f'<a class="cat-badge" href="categories/{c["nicename"]}.html">{html.escape(c["name"])}</a>'
                for c in p["categories"]
            )
            cards.append(f"""<li class="post-card">
  <a href="posts/{p['slug']}.html">{t}</a>
  <div class="post-card-body">
    <div class="post-cat-badges">{cat_badges}</div>
    <h3><a href="posts/{p['slug']}.html">{html.escape(p['title'])}</a></h3>
    <div class="post-date">{p['pub_date_str']}</div>
  </div>
</li>""")

        count = len(data["posts"])
        sections.append(f"""<section class="category-section">
<div class="section-title">
  <h2><a href="categories/{nicename}.html">{html.escape(data['name'])}</a></h2>
  <span class="section-count">{count}</span>
  <a class="section-more" href="categories/{nicename}.html">すべて見る →</a>
</div>
<ul class="post-grid">{"".join(cards)}</ul>
</section>""")

    body = "\n".join(sections)
    return page_shell(SITE_TITLE, body, all_posts=posts, cat_posts=cat_posts, is_top=True)


def build_post_page(post, all_posts, cat_posts):
    body = wp_content_to_html(post["content"])

    cat_badges = "".join(
        f'<a class="cat-badge" href="../categories/{c["nicename"]}.html">{html.escape(c["name"])}</a>'
        for c in post["categories"]
    )

    # パンくず
    first_cat = post["categories"][0] if post["categories"] else None
    bc_cat = ""
    if first_cat:
        bc_cat = f'<a href="../categories/{first_cat["nicename"]}.html">{html.escape(first_cat["name"])}</a><span class="breadcrumb-sep">›</span>'
    breadcrumb = f'<a href="../index.html">HOME</a><span class="breadcrumb-sep">›</span>{bc_cat}<span>{html.escape(post["title"])}</span>'

    # サムネイルヒーロー
    hero = ""
    if post["thumb_url"]:
        hero = f'<img src="{post["thumb_url"]}" alt="{html.escape(post["title"])}" class="post-hero-img">'

    # 前後ナビ
    idx = next((i for i, p in enumerate(all_posts) if p["slug"] == post["slug"]), None)
    prev_html = '<span></span>'
    next_html = '<span></span>'
    if idx is not None and idx > 0:
        pp = all_posts[idx - 1]
        prev_html = f'<a href="{pp["slug"]}.html"><span class="nav-label">← 前の記事</span>{html.escape(pp["title"])}</a>'
    if idx is not None and idx < len(all_posts) - 1:
        np_ = all_posts[idx + 1]
        next_html = f'<a class="nav-next" href="{np_["slug"]}.html"><span class="nav-label">次の記事 →</span>{html.escape(np_["title"])}</a>'

    article = f"""<article class="post">
  {hero}
  <div class="post-header">
    <h1>{html.escape(post['title'])}</h1>
    <div class="post-meta-row">
      <span class="post-date">{post['pub_date_str']}</span>
      {cat_badges}
    </div>
  </div>
  <div class="post-body">{body}</div>
  <div class="post-footer">
    <div class="post-nav">{prev_html}{next_html}</div>
    <div class="back-link"><a href="../index.html">← 記事一覧に戻る</a></div>
  </div>
</article>"""

    return page_shell(post["title"], article, base_path="../",
                      all_posts=all_posts, cat_posts=cat_posts, breadcrumb=breadcrumb)


def build_category_page(nicename, cat_name, posts, all_posts, cat_posts):
    bc = f'<a href="../index.html">HOME</a><span class="breadcrumb-sep">›</span><span>{html.escape(cat_name)}</span>'

    rows = []
    for p in posts:
        t = thumb_html(p["thumb_url"], p["title"], "post-row-thumb")
        excerpt = make_excerpt(p["content"], p["excerpt"])
        rows.append(f"""<li class="post-row">
  <a href="../posts/{p['slug']}.html">{t}</a>
  <div class="post-row-body">
    <h3><a href="../posts/{p['slug']}.html">{html.escape(p['title'])}</a></h3>
    <div class="post-date">{p['pub_date_str']}</div>
    <div class="post-row-excerpt">{html.escape(excerpt)}</div>
  </div>
</li>""")

    body = f"""<div class="cat-page-hero">
  <h1>{html.escape(cat_name)}</h1>
  <div class="cat-count">{len(posts)}記事</div>
</div>
<ul class="post-list-rows">{"".join(rows)}</ul>
<div style="margin-top:16px"><a class="back-link" href="../index.html">← トップに戻る</a></div>"""

    return page_shell(cat_name, body, base_path="../",
                      all_posts=all_posts, cat_posts=cat_posts, breadcrumb=bc)


# ---- メイン ----

def main():
    print(f"[1/5] XML読み込み: {XML_FILE}")
    channel = parse_xml(XML_FILE)

    print("[2/5] カテゴリーパース中...")
    categories = parse_categories(channel)
    print(f"  {len(categories)} カテゴリー")

    print("[3/5] 添付ファイル・記事パース中...")
    attachments = parse_attachments(channel)
    posts = parse_posts(channel, attachments)
    print(f"  {len(posts)} 記事 (サムネイルあり: {sum(1 for p in posts if p['thumb_url'])})")

    cat_posts = build_cat_posts(posts)

    print("[4/5] 出力ディレクトリ準備...")
    out = Path(OUTPUT_DIR)
    (out / "posts").mkdir(parents=True, exist_ok=True)
    (out / "categories").mkdir(parents=True, exist_ok=True)

    print("[5/5] HTML生成中...")

    idx_html = build_index(posts, categories, cat_posts)
    (out / "index.html").write_text(idx_html, encoding="utf-8")
    print("  → index.html")

    for post in posts:
        h = build_post_page(post, posts, cat_posts)
        (out / "posts" / f"{post['slug']}.html").write_text(h, encoding="utf-8")
        print(f"  → posts/{post['slug']}.html")

    for nn, data in cat_posts.items():
        h = build_category_page(nn, data["name"], data["posts"], posts, cat_posts)
        (out / "categories" / f"{nn}.html").write_text(h, encoding="utf-8")
        print(f"  → categories/{nn}.html")

    stats = {
        "total_posts": len(posts),
        "categories": {nn: {"name": n, "count": len(cat_posts.get(nn, {}).get("posts", []))}
                       for nn, n in categories.items()},
    }
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n完了！ {OUTPUT_DIR}/ に {len(posts)} 記事を生成しました。")


if __name__ == "__main__":
    main()
