"""
トンネル技術ニュース 自動収集スクリプト（完全無料版）
Anthropic API不要 — requests + BeautifulSoup で各社サイトを直接スクレイピング
"""

import re
import datetime
import os
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

# ==============================
# 設定
# ==============================
KEYWORDS = ["トンネル", "シールド", "NATM", "地下工事", "掘削", "坑道", "tunnel", "shield"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

@dataclass
class Article:
    company: str
    title: str
    url: str
    date: str = ""


# ==============================
# 汎用スクレイパー
# ==============================

def scrape(company_name: str, list_url: str, base_url: str) -> list[Article]:
    """ニュース一覧ページからキーワードに一致するリンクを抽出する汎用関数"""
    articles = []
    try:
        r = requests.get(list_url, headers=HEADERS, timeout=20)
        r.encoding = r.apparent_encoding
        soup = BeautifulSoup(r.text, "html.parser")

        seen_urls = set()
        for a_tag in soup.find_all("a", href=True):
            title = a_tag.get_text(strip=True)
            href = a_tag["href"].strip()

            # タイトルが短すぎるものはスキップ
            if len(title) < 8:
                continue

            # キーワードチェック
            if not any(kw.lower() in title.lower() for kw in KEYWORDS):
                continue

            # 絶対URLに変換
            if href.startswith("http"):
                full_url = href
            elif href.startswith("/"):
                full_url = base_url.rstrip("/") + href
            else:
                continue

            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            date = extract_date(title + " " + full_url)
            articles.append(Article(company_name, title, full_url, date))

    except Exception as e:
        print(f"  [{company_name}] エラー: {e}")

    return articles


def extract_date(text: str) -> str:
    """テキストやURLから日付を抽出"""
    for pat in [r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", r"(\d{4})(\d{2})(\d{2})"]:
        m = re.search(pat, text)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            try:
                return f"{y}/{int(mo):02d}/{int(d):02d}"
            except ValueError:
                continue
    return ""


def dedup(articles: list[Article]) -> list[Article]:
    seen, result = set(), []
    for a in articles:
        if a.url not in seen:
            seen.add(a.url)
            result.append(a)
    return result


# ==============================
# HTML生成
# ==============================

def build_html(articles: list[Article], generated_at: str) -> str:
    rows = "".join(f"""
        <tr>
          <td class="co">{a.company}</td>
          <td class="dt">{a.date}</td>
          <td><a href="{a.url}" target="_blank" rel="noopener">{a.title}</a></td>
        </tr>""" for a in articles)

    count = len(articles)
    table = (
        f"<table><thead><tr><th>会社名</th><th>日付</th><th>タイトル</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        if articles else '<p class="empty">本日は該当するニュースが見つかりませんでした。</p>'
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>トンネル技術ニュース</title>
<style>
  body {{ font-family: 'Helvetica Neue', Arial, 'Hiragino Kaku Gothic ProN', sans-serif;
         margin: 0; padding: 2rem; background: #f8f8f6; color: #1a1a1a; font-size: 14px; }}
  h1 {{ font-size: 22px; font-weight: 500; margin-bottom: 4px; }}
  .meta {{ font-size: 12px; color: #888; margin-bottom: 0.5rem; }}
  .kw  {{ font-size: 12px; color: #aaa; margin-bottom: 1.5rem; }}
  .badge {{ display: inline-block; background: #E1F5EE; color: #0F6E56;
            font-size: 12px; padding: 2px 10px; border-radius: 6px; margin-left: 8px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  th {{ background: #f0f0ee; text-align: left; padding: 10px 14px;
        font-size: 11px; font-weight: 500; color: #555; border-bottom: 1px solid #e8e8e6; }}
  td {{ padding: 10px 14px; border-bottom: 0.5px solid #eee; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #fafaf8; }}
  td.co {{ white-space: nowrap; color: #185FA5; font-size: 12px; font-weight: 500; min-width: 90px; }}
  td.dt {{ white-space: nowrap; color: #888; font-size: 12px; min-width: 80px; }}
  a {{ color: #1a1a1a; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .empty {{ text-align: center; padding: 3rem; color: #888; }}
</style>
</head>
<body>
<h1>トンネル技術ニュース <span class="badge">{count} 件</span></h1>
<p class="meta">最終更新: {generated_at}（毎朝8時 JST 自動更新）</p>
<p class="kw">キーワード: {' ／ '.join(KEYWORDS)}</p>
{table}
</body>
</html>"""


# ==============================
# メイン
# ==============================

TARGETS = [
    ("鹿島建設",     "https://www.kajima.co.jp/news/press/index-j.html", "https://www.kajima.co.jp"),
    ("大成建設",     "https://www.taisei.co.jp/about_us/wn/",            "https://www.taisei.co.jp"),
    ("清水建設",     "https://www.shimz.co.jp/company/news/",            "https://www.shimz.co.jp"),
    ("大林組",       "https://www.obayashi.co.jp/news/press/",           "https://www.obayashi.co.jp"),
    ("前田建設工業", "https://www.maeda.co.jp/news/",                    "https://www.maeda.co.jp"),
]

def main():
    all_articles = []

    for company, list_url, base_url in TARGETS:
        print(f"🔍 {company} を取得中...")
        articles = scrape(company, list_url, base_url)
        print(f"   → {len(articles)} 件 マッチ")
        all_articles.extend(articles)

    all_articles = dedup(all_articles)
    all_articles.sort(key=lambda a: a.date, reverse=True)

    jst = datetime.timezone(datetime.timedelta(hours=9))
    generated_at = datetime.datetime.now(jst).strftime("%Y年%m月%d日 %H:%M JST")

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(build_html(all_articles, generated_at))

    print(f"\n✅ 完了: {len(all_articles)} 件 → docs/index.html に保存しました")


if __name__ == "__main__":
    main()
