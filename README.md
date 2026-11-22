# AccuNews

**Information belongs to everyone.** AccuNews is a free-first, multi-publisher news reader built with HTML, CSS, JavaScript, FastAPI and SQLModel.

## What works

- Fourteen RSS and Atom feeds across international, regional, business, technology and science coverage.
- Polling at startup and every 15 minutes; article-link deduplication and persistent SQLite storage by default.
- A responsive homepage with search, topic filters, live publisher health and original source links.
- Conservative, explainable headline-and-time clustering. Each story exposes publisher headlines, dates, regions and feed descriptions.
- Docker packaging and a Render deployment blueprint.

## Transparency and limits

AccuNews does not fetch or republish full publisher articles. It stores the title, URL, publication time, publisher metadata and short descriptions supplied in public feeds. The service uses RSS only; a source can change access or terms at any time, and feed failures appear in Publisher feed status. Review each publisher's feed terms before public/commercial operation.

Story clusters are a deterministic headline-overlap heuristic. Similar titles can describe different events, while reports about the same event can use very different words. Open a cluster and inspect the original sources. Current summaries are attribution-oriented feed summaries, not AI-generated analysis. Claim extraction, fact checking, bias scoring and independent verification are not implemented. No claim is presented as independently verified.

## Run locally

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Open `http://127.0.0.1:8000`. On the first run, RSS collection starts in the background and may take a minute. Set `DATABASE_URL` to a PostgreSQL connection string for a multi-instance deployment; SQLite is suitable only for a single instance with persistent disk. `REFRESH_SECONDS` defaults to 900. Set a truthful contact address in the `User-Agent` before operating a public service.

## Deploy

The repository includes `render.yaml` and a `Dockerfile`. Create a Render web service from this repository, attach a persistent disk at `/data`, and deploy the blueprint. Render account access is required. For a growing service, provision managed PostgreSQL and set `DATABASE_URL`; configure backups, monitoring, and a contact address. No AI key is needed for the current deterministic version. Never put secrets in frontend files.

## API

- `GET /api/health` — service and collection status
- `GET /api/feeds` — configured sources and feed status
- `GET /api/stories?q=&category=&limit=` — grouped story feed
- `GET /api/stories/{id}` — cluster detail
- `POST /api/refresh` — request an on-demand collection
- `GET /docs` — FastAPI OpenAPI interface

## Data sources

The initial source list is defined in `backend/app.py`. Feeds are public RSS/Atom endpoints; availability and reuse terms are publisher-controlled. Add only feeds whose current publisher terms permit the intended use.
