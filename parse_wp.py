#!/usr/bin/env python3
"""WordPress XML export to static HTML site generator."""

import xml.etree.ElementTree as ET
import os
import re
import html
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

# ---- 設定 ----
XML_FILE = "WordPress.2026-04-29.xml"
OUTPUT_DIR = "docs"  # GitHub Pages用

SITE_TITLE = "半地下店舗兼用準防火第一種低層狭小住宅"
SITE_URL = ""  # GitHub Pages公開後に設定（例: /repo-name）

# XML名前空間
NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt":  "http://wordpress.org/export/1.2/excerpt/",
    "dc":       "http://purl.org/dc/elements/1.1/",
    "wp":       "http://wordpress.org/export/1.2/",
}


# ---- XMLパース ----

def parse_xml(filepath):
    tree = ET.parse(filepath)
    root = tree.getroot()
    channel = root.find("channel")
    return channel


def get_text(el, tag, ns_key=None):
    """要素のテキストをCDATAも含めて取得。"""
    if ns_key:
        child = el.find(f"{{{NS[ns_key]}}}{tag}")
    else:
        child = el.find(tag)
    if child is None:
        return ""
    return (child.text or "").strip()


def parse_categories(channel):
    """カテゴリー一覧を {nicename: display_name} で返す。"""
    cats = {}
    for cat in channel.findall(f"{{{NS['wp']}}}category"):
        nicename = get_text(cat, "category_nicename", "wp")
        name = get_text(cat, "cat_name", "wp")
        if nicename and name:
            cats[nicename] = name
    return cats


def parse_posts(channel):
    """publishedなpostをリストで返す。"""
    posts = []
    for item in channel.findall("item"):
        post_type = get_text(item, "post_type", "wp")
        status = get_text(item, "status", "wp")

        if post_type != "post" or status != "publish":
            continue

        title = get_text(item, "title")
        slug = get_text(item, "post_name", "wp")
        slug = unquote(slug)  # URLエンコードされたスラッグを戻す
        pub_date_str = get_text(item, "post_date", "wp")
        content_el = item.find(f"{{{NS['content']}}}encoded")
        content = (content_el.text or "") if content_el is not None else ""
        excerpt_el = item.find(f"{{{NS['excerpt']}}}encoded")
        excerpt = (excerpt_el.text or "") if excerpt_el is not None else ""

        # カテゴリー
        cats = []
        for cat_el in item.findall("category"):
            domain = cat_el.get("domain", "")
            nicename = cat_el.get("nicename", "")
            name = (cat_el.text or "").strip()
            if domain == "category" and nicename and name:
                cats.append({"nicename": nicename, "name": name})

        # 投稿日パース
        try:
            pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pub_date = datetime.now()

        # スラッグが空の場合はpost_idを使う
        if not slug:
            slug = get_text(item, "post_id", "wp")

        # 非ASCII文字が含まれる場合はpost_idにフォールバック
        if not slug.isascii():
            post_id = get_text(item, "post_id", "wp")
            slug = f"post_{post_id}"

        posts.append({
            "title": title,
            "slug": slug,
            "pub_date": pub_date,
            "pub_date_str": pub_date.strftime("%Y年%m月%d日"),
            "content": content,
            "excerpt": excerpt,
            "categories": cats,
        })

    # 日付の古い順にソート
    posts.sort(key=lambda p: p["pub_date"])
    return posts


# ---- コンテンツ変換 ----

def wp_content_to_html(content):
    """WordPressのGutenberg/クラシックコンテンツを整形。"""
    # WordPressショートコードを除去
    content = re.sub(r'\[/?[a-z_-]+[^\]]*\]', '', content)

    # <!-- wp:... --> ブロックコメントを除去
    content = re.sub(r'<!-- /?wp:[^\-].*?-->', '', content, flags=re.DOTALL)

    # 空白行の整理
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip()


def make_excerpt(content, excerpt, length=120):
    """抜粋テキストを生成。"""
    if excerpt:
        text = re.sub(r'<[^>]+>', '', excerpt)
        return text[:length] + ("…" if len(text) > length else "")
    text = re.sub(r'<[^>]+>', '', content)
    text = text.strip()
    return text[:length] + ("…" if len(text) > length else "")


# ---- HTMLテンプレート ----

CSS = """
:root {
  --bg: #fafaf8;
  --text: #2d2d2d;
  --muted: #666;
  --accent: #5c6bc0;
  --accent-light: #e8eaf6;
  --border: #e0e0e0;
  --card-bg: #fff;
  --max-w: 860px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.8;
  font-size: 16px;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ヘッダー */
header {
  background: var(--accent);
  color: #fff;
  padding: 1.2rem 1.5rem;
}
header a { color: #fff; }
.site-title { font-size: 1.1rem; font-weight: bold; line-height: 1.4; }
.site-nav { margin-top: 0.5rem; font-size: 0.88rem; opacity: 0.9; }
.site-nav a { margin-right: 1rem; color: #fff; }

/* メインレイアウト */
.container {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

/* 記事カード（一覧） */
.post-list { list-style: none; }
.post-card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.4rem 1.6rem;
  margin-bottom: 1.2rem;
  transition: box-shadow 0.2s;
}
.post-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.08); }
.post-card h2 { font-size: 1.1rem; margin-bottom: 0.35rem; }
.post-meta { font-size: 0.82rem; color: var(--muted); margin-bottom: 0.6rem; }
.post-excerpt { font-size: 0.93rem; color: #444; }
.cat-badge {
  display: inline-block;
  background: var(--accent-light);
  color: var(--accent);
  font-size: 0.75rem;
  padding: 0.15rem 0.55rem;
  border-radius: 4px;
  margin-right: 0.3rem;
}

/* カテゴリーセクション見出し */
.category-section { margin-bottom: 2.5rem; }
.category-heading {
  font-size: 1.05rem;
  font-weight: bold;
  color: var(--accent);
  border-left: 4px solid var(--accent);
  padding-left: 0.75rem;
  margin-bottom: 1rem;
}
.category-heading a { color: inherit; }

/* 記事本文 */
article.post {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 2rem 2.2rem;
}
article.post h1 { font-size: 1.5rem; margin-bottom: 0.5rem; line-height: 1.5; }
article.post .post-meta { margin-bottom: 1.5rem; }
.post-body { margin-top: 1.5rem; }
.post-body h2 { font-size: 1.25rem; margin: 2rem 0 0.8rem; padding-bottom: 0.3rem; border-bottom: 2px solid var(--border); }
.post-body h3 { font-size: 1.1rem; margin: 1.5rem 0 0.6rem; }
.post-body h4 { font-size: 1rem; margin: 1.2rem 0 0.5rem; }
.post-body p { margin-bottom: 1.1rem; }
.post-body ul, .post-body ol { margin: 0.8rem 0 1rem 1.6rem; }
.post-body li { margin-bottom: 0.4rem; }
.post-body img { max-width: 100%; height: auto; border-radius: 6px; margin: 0.8rem 0; }
.post-body blockquote {
  border-left: 4px solid var(--accent);
  background: var(--accent-light);
  padding: 0.8rem 1.2rem;
  margin: 1rem 0;
  border-radius: 0 6px 6px 0;
}
.post-body table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
.post-body th, .post-body td { border: 1px solid var(--border); padding: 0.5rem 0.8rem; text-align: left; }
.post-body th { background: var(--accent-light); }

/* ナビゲーション */
.post-nav { margin-top: 2rem; display: flex; gap: 1rem; flex-wrap: wrap; }
.post-nav a {
  display: inline-block;
  padding: 0.5rem 1.2rem;
  border: 1px solid var(--accent);
  border-radius: 6px;
  font-size: 0.9rem;
}
.back-to-list { margin-top: 1.5rem; }

/* カテゴリーページ */
.page-heading {
  font-size: 1.3rem;
  font-weight: bold;
  margin-bottom: 1.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid var(--accent);
}

/* フッター */
footer {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--muted);
  font-size: 0.82rem;
  border-top: 1px solid var(--border);
  margin-top: 3rem;
}

@media (max-width: 600px) {
  article.post { padding: 1.2rem 1rem; }
  .container { padding: 1.2rem 1rem; }
}
"""


def page_shell(title, content, base_path=""):
    """共通HTMLラッパー。"""
    site_url = SITE_URL.rstrip("/")
    nav_home = f'<a href="{base_path}index.html">トップ</a>'
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} | {html.escape(SITE_TITLE)}</title>
  <style>{CSS}</style>
</head>
<body>
<header>
  <div class="site-title"><a href="{base_path}index.html">{html.escape(SITE_TITLE)}</a></div>
  <nav class="site-nav">{nav_home}</nav>
</header>
<div class="container">
{content}
</div>
<footer>
  <p>&copy; {SITE_TITLE}</p>
</footer>
</body>
</html>"""


# ---- ページ生成 ----

def build_index(posts, categories):
    """トップページ（カテゴリー別記事一覧）を生成。"""
    # カテゴリー別に記事を分類
    cat_posts = {}
    for p in posts:
        for c in p["categories"]:
            nn = c["nicename"]
            if nn not in cat_posts:
                cat_posts[nn] = {"name": c["name"], "posts": []}
            cat_posts[nn]["posts"].append(p)

    # カテゴリー名でソート（番号付きカテゴリー名を想定）
    sorted_cats = sorted(cat_posts.items(), key=lambda x: x[1]["name"])

    sections = []
    for nicename, data in sorted_cats:
        cards = []
        for p in data["posts"]:
            excerpt = make_excerpt(p["content"], p["excerpt"])
            cat_badges = " ".join(
                f'<span class="cat-badge">{html.escape(c["name"])}</span>'
                for c in p["categories"]
            )
            cards.append(f"""<li class="post-card">
  <h2><a href="posts/{p['slug']}.html">{html.escape(p['title'])}</a></h2>
  <div class="post-meta">{p['pub_date_str']} &nbsp; {cat_badges}</div>
  <div class="post-excerpt">{html.escape(excerpt)}</div>
</li>""")

        sections.append(f"""<section class="category-section">
<h2 class="category-heading">
  <a href="categories/{nicename}.html">{html.escape(data['name'])}</a>
</h2>
<ul class="post-list">
{"".join(cards)}
</ul>
</section>""")

    content = "\n".join(sections)
    return page_shell(SITE_TITLE, content)


def build_post_page(post, all_posts):
    """個別記事ページを生成。"""
    body = wp_content_to_html(post["content"])
    cat_badges = " ".join(
        f'<a class="cat-badge" href="../categories/{c["nicename"]}.html">{html.escape(c["name"])}</a>'
        for c in post["categories"]
    )

    # 前後記事ナビゲーション
    idx = next((i for i, p in enumerate(all_posts) if p["slug"] == post["slug"]), None)
    nav_links = []
    if idx is not None and idx > 0:
        prev_p = all_posts[idx - 1]
        nav_links.append(f'<a href="{prev_p["slug"]}.html">← {html.escape(prev_p["title"])}</a>')
    if idx is not None and idx < len(all_posts) - 1:
        next_p = all_posts[idx + 1]
        nav_links.append(f'<a href="{next_p["slug"]}.html">{html.escape(next_p["title"])} →</a>')

    nav_html = f'<div class="post-nav">{"".join(nav_links)}</div>' if nav_links else ""

    content = f"""<article class="post">
  <h1>{html.escape(post['title'])}</h1>
  <div class="post-meta">{post['pub_date_str']} &nbsp; {cat_badges}</div>
  <div class="post-body">{body}</div>
  {nav_html}
  <div class="back-to-list"><a href="../index.html">← 記事一覧に戻る</a></div>
</article>"""

    return page_shell(post["title"], content, base_path="../")


def build_category_page(nicename, cat_name, posts):
    """カテゴリーページを生成。"""
    cards = []
    for p in posts:
        excerpt = make_excerpt(p["content"], p["excerpt"])
        cards.append(f"""<li class="post-card">
  <h2><a href="../posts/{p['slug']}.html">{html.escape(p['title'])}</a></h2>
  <div class="post-meta">{p['pub_date_str']}</div>
  <div class="post-excerpt">{html.escape(excerpt)}</div>
</li>""")

    content = f"""<h1 class="page-heading">{html.escape(cat_name)}</h1>
<ul class="post-list">
{"".join(cards)}
</ul>
<div class="back-to-list"><a href="../index.html">← トップに戻る</a></div>"""

    return page_shell(cat_name, content, base_path="../")


# ---- メイン ----

def main():
    print(f"[1/5] XMLを読み込み中: {XML_FILE}")
    channel = parse_xml(XML_FILE)

    print("[2/5] カテゴリーをパース中...")
    categories = parse_categories(channel)
    print(f"  カテゴリー数: {len(categories)}")
    for nn, name in categories.items():
        print(f"  - {name} ({nn})")

    print("[3/5] 記事をパース中...")
    posts = parse_posts(channel)
    print(f"  公開記事数: {len(posts)}")
    for p in posts:
        cats = ", ".join(c["name"] for c in p["categories"])
        print(f"  - [{p['pub_date_str']}] {p['title']} ({cats})")

    print("[4/5] 出力ディレクトリを準備中...")
    out = Path(OUTPUT_DIR)
    (out / "posts").mkdir(parents=True, exist_ok=True)
    (out / "categories").mkdir(parents=True, exist_ok=True)

    print("[5/5] HTMLを生成中...")

    # トップページ
    index_html = build_index(posts, categories)
    (out / "index.html").write_text(index_html, encoding="utf-8")
    print("  → index.html")

    # 個別記事ページ
    for post in posts:
        html_content = build_post_page(post, posts)
        path = out / "posts" / f"{post['slug']}.html"
        path.write_text(html_content, encoding="utf-8")
        print(f"  → posts/{post['slug']}.html")

    # カテゴリーページ
    cat_posts = {}
    for p in posts:
        for c in p["categories"]:
            nn = c["nicename"]
            if nn not in cat_posts:
                cat_posts[nn] = {"name": c["name"], "posts": []}
            cat_posts[nn]["posts"].append(p)

    for nicename, data in cat_posts.items():
        html_content = build_category_page(nicename, data["name"], data["posts"])
        path = out / "categories" / f"{nicename}.html"
        path.write_text(html_content, encoding="utf-8")
        print(f"  → categories/{nicename}.html")

    # 統計をJSONで出力（デバッグ用）
    stats = {
        "total_posts": len(posts),
        "categories": {nn: {"name": name, "count": len(cat_posts.get(nn, {}).get("posts", []))}
                       for nn, name in categories.items()},
        "posts": [{"title": p["title"], "slug": p["slug"], "date": p["pub_date_str"]} for p in posts],
    }
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n完了！ {OUTPUT_DIR}/ に {len(posts)} 記事を生成しました。")
    print(f"GitHub Pagesの設定: リポジトリの Settings > Pages > Source を 'docs/' フォルダに設定してください。")


if __name__ == "__main__":
    main()
