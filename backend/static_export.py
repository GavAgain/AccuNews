"""Build a publisher-attributed static snapshot for the GitHub Pages site."""
from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import httpx

from backend.app import Article, SOURCES, article_date, article_json, clean_text, group_articles

ROOT = Path(__file__).resolve().parent.parent

async def fetch_source(client: httpx.AsyncClient, source: dict) -> tuple[list[Article], dict]:
    status = {**source, "checked": datetime.now(timezone.utc).isoformat(), "ok": False, "count": 0, "error": ""}
    try:
        response = await client.get(source["url"])
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if parsed.bozo and not parsed.entries:
            raise ValueError("Feed could not be parsed")
        status.update(ok=True, count=len(parsed.entries))
        articles=[]
        for entry in parsed.entries[:40]:
            title=clean_text(entry.get("title", ""))
            link=(entry.get("link") or "").strip()
            if not title or not link or urlparse(link).scheme not in ("http", "https"):
                continue
            import hashlib
            key=hashlib.sha256(link.split("?")[0].rstrip("/").encode()).hexdigest()
            summary=clean_text(entry.get("summary", "") or entry.get("description", ""))[:900]
            articles.append(Article(id=key,title=title[:500],publisher=source["publisher"],region=source["region"],category=source["category"],url=link,summary=summary,published=article_date(entry),source_name=source["name"]))
        return articles,status
    except Exception as exc:
        status["error"]=str(exc)[:250]
        return [],status

async def main() -> None:
    headers={"User-Agent":"AccuNews/0.1 (+https://github.com/GavAgain/AccuNews; RSS reader)"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(20,connect=8),follow_redirects=True,headers=headers) as client:
        results=await asyncio.gather(*(fetch_source(client,source) for source in SOURCES))
    by_id={}
    for articles,_ in results:
        for article in articles:
            by_id.setdefault(article.id,article)
    grouped=group_articles(list(by_id.values()))
    payload={"generated_at":datetime.now(timezone.utc).isoformat(),"stories":grouped}
    output=ROOT/"site"
    if output.exists(): shutil.rmtree(output)
    shutil.copytree(ROOT/"frontend",output)
    (output/"stories.json").write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    feed_rows=[]
    for source,(_,status) in zip(SOURCES,results):
        feed_rows.append({"name":source["name"],"publisher":source["publisher"],"region":source["region"],"category":source["category"],"url":source["url"],"checked":status["checked"],"ok":status["ok"],"count":status["count"],"error":status["error"]})
    (output/"feeds.json").write_text(json.dumps(feed_rows,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"Published snapshot with {len(by_id)} unique articles; {sum(1 for row in feed_rows if row['ok'])}/{len(feed_rows)} feeds responded.")

if __name__ == "__main__":
    asyncio.run(main())
