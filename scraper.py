"""
トンネル技術ニュース 自動収集スクリプト
毎朝8時(JST)にGitHub Actionsから実行され、結果をdocs/index.htmlに書き出す
"""

import os
import json
import datetime
import anthropic

# ==============================
# 設定: 対象サイトとキーワード
# ==============================
COMPANIES = [
    {"name": "鹿島建設",     "url": "https://www.kajima.co.jp/news/press/"},
    {"name": "大成建設",     "url": "https://www.taisei.co.jp/about_us/wn/"},
    {"name": "清水建設",     "url": "https://www.shimz.co.jp/company/news/"},
    {"name": "大林組",       "url": "https://www.obayashi.co.jp/news/"},
    {"name": "前田建設工業", "url": "https://www.maeda.co.jp/news/"},
]

KEYWORDS = ["トンネル", "シールド", "NATM", "地下工事", "掘削", "坑道"]

# ==============================
# Anthropic API でニュースを収集
# ==============================
def fetch_news_for_company(client: anthropic.Anthropic, company: dict) -> list[dict]:
    kw_str = "、".join(KEYWORDS)
    prompt = f"""あなたは建設業界のニュースリサーチャーです。
ウェブ検索で以下の会社の最新プレスリリースを調べてください。
会社名: {company['name']}
公式URL: {company['url']}
検索キーワード: {kw_str}

上記キーワードのいずれかに関連する技術プレスリリースを最大8件、
以下のJSON形式のみで返してください（前後に余分なテキスト不要）:
{{"articles":[{{"title":"タイトル","url":"記事のURL","date":"YYYY/MM/DD","summary":"内容の要点を70文字以内"}}]}}
見つからない場合は {{"articles":[]}} のみ返してください。"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(b.text for b in response.content if b.type == "text")
    import re
    m = re.search(r'\{[\s\S]*?"articles"[\s\S]*?\}', text)
    if not m:
        return []
    try:
        parsed = json.loads(m.group(0))
        articles = parsed.get("articles", [])
        for a in articles:
            a["company"] = company["name"]
        return articles
    except json.JSONDecodeError:
        return []


# ==============================
# HTMLレポートを生成
# ==============================
def build_html(all_news: list[dict], generated_at: str) -> str:
    rows = ""
    for n in all_news:
        rows += f"""
        <tr>
          <td class="co">{n.get('company','')}</td>
          <td class="dt">{n.get('date','')}</td>
          <td><a href="{n.get('url','#')}" target="_blank" rel="noopener">{n.get('title','')}</a></td>
          <td class="sm">{n.get('summary','')}</td>
        </tr>"""

    count = len(all_news)
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
  .meta {{ font-size: 12px; color: #888; margin-bottom: 1.5rem; }}
  .badge {{ display: inline-block; background: #E1F5EE; color: #0F6E56;
            font-size: 12px; padding: 2px 10px; border-radius: 6px; margin-left: 8px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 10px; overflow: hidden;
           box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
  th {{ background: #f0f0ee; text-align: left; padding: 10px 14px;
        font-size: 11px; font-weight: 500; color: #555;
        border-bottom: 1px solid #e8e8e6; }}
  td {{ padding: 10px 14px; border-bottom: 0.5px solid #eee; vertical-align: top; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #fafaf8; }}
  td.co {{ white-space: nowrap; color: #185FA5; font-size: 12px; font-weight: 500; }}
  td.dt {{ white-space: nowrap; color: #888; font-size: 12px; }}
  td.sm {{ color: #555; font-size: 12px; }}
  a {{ color: #1a1a1a; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .empty {{ text-align: center; padding: 3rem; color: #888; }}
</style>
</head>
<body>
<h1>トンネル技術ニュース <span class="badge">{count} 件</span></h1>
<p class="meta">最終更新: {generated_at}（毎朝8時 JST 自動更新）</p>
{"<table><thead><tr><th>会社名</th><th>日付</th><th>タイトル</th><th>概要</th></tr></thead><tbody>" + rows + "</tbody></table>"
  if all_news else '<p class="empty">本日は該当するニュースが見つかりませんでした。</p>'}
</body>
</html>"""


# ==============================
# メイン処理
# ==============================
def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY が設定されていません")

    client = anthropic.Anthropic(api_key=api_key)
    all_news = []

    for company in COMPANIES:
        print(f"🔍 {company['name']} を検索中...")
        articles = fetch_news_for_company(client, company)
        print(f"   → {len(articles)} 件見つかりました")
        all_news.extend(articles)

    jst = datetime.timezone(datetime.timedelta(hours=9))
    generated_at = datetime.datetime.now(jst).strftime("%Y年%m月%d日 %H:%M JST")

    os.makedirs("docs", exist_ok=True)
    html = build_html(all_news, generated_at)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ 完了: {len(all_news)} 件 → docs/index.html に保存しました")


if __name__ == "__main__":
    main()
