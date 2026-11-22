"""AccuNews API: RSS collection, lightweight event grouping, and transparent comparison."""
from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Field, Session, SQLModel, create_engine, select

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("accunews")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./accunews.db")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})

SOURCES = [
    {"name":"BBC News · World", "publisher":"BBC News", "region":"United Kingdom", "url":"https://feeds.bbci.co.uk/news/world/rss.xml", "category":"World"},
    {"name":"BBC News · Business", "publisher":"BBC News", "region":"United Kingdom", "url":"https://feeds.bbci.co.uk/news/business/rss.xml", "category":"Business"},
    {"name":"Al Jazeera · All news", "publisher":"Al Jazeera", "region":"Qatar", "url":"https://www.aljazeera.com/xml/rss/all.xml", "category":"World"},
    {"name":"The Guardian · World", "publisher":"The Guardian", "region":"United Kingdom", "url":"https://www.theguardian.com/world/rss", "category":"World"},
    {"name":"France 24 · English", "publisher":"France 24", "region":"France", "url":"https://www.france24.com/en/rss", "category":"World"},
    {"name":"NPR · News", "publisher":"NPR", "region":"United States", "url":"https://feeds.npr.org/1001/rss.xml", "category":"World"},
    {"name":"DW · Top Stories", "publisher":"Deutsche Welle", "region":"Germany", "url":"https://rss.dw.com/rdf/rss-en-top", "category":"World"},
    {"name":"CBC · World", "publisher":"CBC News", "region":"Canada", "url":"https://www.cbc.ca/webfeed/rss/rss-world", "category":"World"},
    {"name":"The Hindu · International", "publisher":"The Hindu", "region":"India", "url":"https://www.thehindu.com/news/international/feeder/default.rss", "category":"World"},
    {"name":"The Japan Times · News", "publisher":"The Japan Times", "region":"Japan", "url":"https://www.japantimes.co.jp/feed/", "category":"World"},
    {"name":"SCMP · China", "publisher":"South China Morning Post", "region":"Hong Kong", "url":"https://www.scmp.com/rss/4/feed", "category":"World"},
    {"name":"The Conversation · Global", "publisher":"The Conversation", "region":"International", "url":"https://theconversation.com/global/articles.atom", "category":"Analysis"},
    {"name":"TechCrunch", "publisher":"TechCrunch", "region":"United States", "url":"https://techcrunch.com/feed/", "category":"Technology"},
    {"name":"Nature · News", "publisher":"Nature", "region":"International", "url":"https://www.nature.com/subjects/news.rss", "category":"Science"},
]

class Article(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str
    publisher: str
    region: str
    category: str
    url: str = Field(index=True)
    summary: str = ""
    published: datetime = Field(index=True)
    fetched: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_name: str

class FeedStatus(SQLModel, table=True):
    publisher: str = Field(primary_key=True)
    url: str
    checked: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ok: bool = False
    count: int = 0
    error: str = ""

def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()

def article_date(entry) -> datetime:
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if raw:
            try:
                dt = parsedate_to_datetime(raw) if "," in raw else datetime(*entry.get(key + "_parsed")[:6], tzinfo=timezone.utc)
                return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)

async def ingest_once() -> dict:
    result = {"feeds": 0, "articles": 0, "errors": []}
    headers = {"User-Agent": "AccuNews/0.1 (+https://github.com/; RSS reader; contact: admin@accunews.example)"}
    timeout = httpx.Timeout(18.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for source in SOURCES:
            try:
                response = await client.get(source["url"])
                response.raise_for_status()
                parsed = feedparser.parse(response.content)
                if parsed.bozo and not parsed.entries:
                    raise ValueError("Feed could not be parsed")
                added = 0
                with Session(engine) as session:
                    for entry in parsed.entries[:40]:
                        title, link = clean_text(entry.get("title", "")), (entry.get("link") or "").strip()
                        if not title or not link or urlparse(link).scheme not in ("http", "https"):
                            continue
                        key = hashlib.sha256(link.split("?")[0].rstrip("/").encode()).hexdigest()
                        if session.get(Article, key):
                            continue
                        raw_summary = entry.get("summary", "") or entry.get("description", "")
                        session.add(Article(id=key, title=title[:500], publisher=source["publisher"], region=source["region"], category=source["category"], url=link, summary=clean_text(raw_summary)[:900], published=article_date(entry), source_name=source["name"]))
                        added += 1
                    session.merge(FeedStatus(publisher=source["name"], url=source["url"], checked=datetime.now(timezone.utc), ok=True, count=len(parsed.entries), error=""))
                    session.commit()
                result["feeds"] += 1
                result["articles"] += added
            except Exception as exc:
                msg = f"{source['name']}: {str(exc)[:180]}"
                log.warning("Feed failure: %s", msg)
                result["errors"].append(msg)
                with Session(engine) as session:
                    session.merge(FeedStatus(publisher=source["name"], url=source["url"], checked=datetime.now(timezone.utc), ok=False, count=0, error=str(exc)[:250]))
                    session.commit()
    return result

STOP = set("about after again against all also among another any are because been before being between both but can could did does doing down during each few for from further had has have having here how into its itself just more most much must not now off once only other our out over own same she should some such than that the their them there these they this those through too under until upon very was were what when where which while who will with would your and then says say says a an as at be by he her his in is it of on or we us you to this new their its will amid over into".split())
def tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", title.lower()) if w not in STOP}

def group_articles(articles: list[Article]) -> list[dict]:
    # Title overlap is a conservative, deterministic clustering heuristic. It never infers factual agreement.
    groups: list[list[Article]] = []
    for article in articles:
        words = tokens(article.title)
        match = None
        for group in groups:
            lead = group[0]
            age = abs((article.published - lead.published).total_seconds())
            other = tokens(lead.title)
            overlap = len(words & other) / max(1, len(words | other))
            if age < 60 * 60 * 36 and (overlap >= 0.24 or SequenceMatcher(None, article.title.lower(), lead.title.lower()).ratio() >= 0.55):
                match = group
                break
        if match is None:
            groups.append([article])
        else:
            match.append(article)
    out=[]
    for group in groups:
        group.sort(key=lambda a:a.published, reverse=True)
        ids=sorted(a.id for a in group)
        out.append({"id": hashlib.sha1("".join(ids).encode()).hexdigest()[:16], "title": group[0].title, "updated": max(a.published for a in group).isoformat(), "sources_count": len({a.publisher for a in group}), "articles": [article_json(a) for a in group], "summary": consolidated(group), "category": group[0].category, "publishers": list(dict.fromkeys(a.publisher for a in group))})
    out.sort(key=lambda g: g["updated"], reverse=True)
    return out

def article_json(a: Article) -> dict:
    return {"id":a.id,"title":a.title,"publisher":a.publisher,"region":a.region,"category":a.category,"url":a.url,"summary":a.summary,"published":a.published.isoformat(),"source_name":a.source_name}

def consolidated(group: list[Article]) -> str:
    if len(group) == 1:
        return "One publisher is currently reporting this. Open the source for its account; independent corroboration has not yet appeared in this collection."
    # Grounded summary is deliberately limited to the shared title vocabulary and feed descriptions.
    descriptions=[a.summary for a in group if a.summary]
    if descriptions:
        return "Across " + str(len({a.publisher for a in group})) + " publishers, coverage centers on “" + group[0].title + ".” Publisher descriptions vary; read the linked reports to compare their details and framing."
    return f"{len({a.publisher for a in group})} publishers have headlines grouped by similar wording. This is an automated match, not confirmation that every reported detail agrees."

@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    async def loop():
        while True:
            await ingest_once()
            await asyncio.sleep(int(os.getenv("REFRESH_SECONDS", "900")))
    task=asyncio.create_task(loop())
    yield
    task.cancel()
    try: await task
    except asyncio.CancelledError: pass

app=FastAPI(title="AccuNews API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/health")
def health():
    with Session(engine) as session:
        count=len(session.exec(select(Article)).all())
        statuses=session.exec(select(FeedStatus)).all()
    return {"status":"ok","articles":count,"feeds_configured":len(SOURCES),"feeds_ok":sum(1 for s in statuses if s.ok),"last_refresh":max((s.checked for s in statuses),default=None)}

@app.get("/api/feeds")
def feeds():
    with Session(engine) as session:
        states={s.publisher:s for s in session.exec(select(FeedStatus)).all()}
    return [{**src,"status":({"ok":states[src["name"]].ok,"checked":states[src["name"]].checked.isoformat(),"count":states[src["name"]].count,"error":states[src["name"]].error} if src["name"] in states else None)} for src in SOURCES]

@app.get("/api/stories")
def stories(q: str = Query(default="", max_length=120), category: str = "", limit: int = Query(default=100, ge=1, le=300)):
    with Session(engine) as session:
        articles=session.exec(select(Article).order_by(Article.published.desc()).limit(1500)).all()
    groups=group_articles(articles)
    if q:
        needle=q.lower()
        groups=[g for g in groups if needle in g["title"].lower() or any(needle in (a["publisher"]+" "+a["summary"]).lower() for a in g["articles"])]
    if category and category.lower()!="all": groups=[g for g in groups if g["category"].lower()==category.lower()]
    return {"stories":groups[:limit],"total":len(groups),"refreshed":"live RSS collection; see feed status for publisher availability"}

@app.get("/api/stories/{story_id}")
def story(story_id: str):
    with Session(engine) as session: articles=session.exec(select(Article).order_by(Article.published.desc()).limit(1500)).all()
    for item in group_articles(articles):
        if item["id"]==story_id: return item
    raise HTTPException(404,"Story not found")

@app.post("/api/refresh")
async def refresh():
    return await ingest_once()

frontend_dir=Path(__file__).resolve().parent.parent/"frontend"
if frontend_dir.exists(): app.mount("/",StaticFiles(directory=frontend_dir,html=True),name="frontend")
