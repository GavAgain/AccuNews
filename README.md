# AccuNews

**Information belongs to everyone.** A multi-publisher news reader with transparent sourcing and a free GitHub Pages deployment.

## GitHub Pages version

The public website is static HTML, CSS, JavaScript and publisher-attributed JSON. GitHub Actions fetches RSS/Atom feeds, groups similar headlines, and publishes a fresh site snapshot about every 15 minutes. GitHub Pages serves the site at `https://gavagain.github.io/AccuNews/` once Pages is enabled for the repository.

The scheduled publisher collection is implemented in `backend/static_export.py`; `.github/workflows/pages.yml` builds and publishes the site without a separate hosting account or API keys. The workflow requests only the GitHub Pages deployment permissions (`pages: write`, `id-token: write`) and repository read access.

## Features

- Fourteen public RSS and Atom feeds spanning world news, business, technology, science and analysis.
- Headline search and category filters.
- Article-link deduplication and conservative headline-and-time story grouping.
- Story detail pages with publisher headlines, dates, regions, links and short feed descriptions.
- Live publisher status and a responsive mobile layout.

## Transparency and limits

AccuNews stores publisher metadata, titles, links, publication times and short descriptions supplied in feeds. It does not reproduce full articles. Feed access and reuse terms can change; the site shows the last collection's availability for each publisher.

Story clusters are a deterministic headline-overlap heuristic. Similar headlines can describe separate events and reports on the same event can use different wording. The clusters help with discovery; they do not confirm a shared event or prove factual agreement. Summaries are attribution-oriented and use publisher-provided headlines/descriptions. AI claim extraction, evidence comparison, fact-checking and independent verification are not implemented.

The GitHub Pages site is public. GitHub Free Pages requires a public repository, so publishing this project there makes its source code public as well. Do not store secrets, API keys or private data in the repository. Collection is periodic, not minute-by-minute live; scheduled runs can be delayed by GitHub.

## Local development

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

The FastAPI service can run the API and collect feeds locally. Its SQLite database is for single-instance local use; the Pages publication uses a scheduled static snapshot rather than a continuously running API server.

## API (local FastAPI mode)

- `GET /api/health` — collection status
- `GET /api/feeds` — configured sources and latest feed status
- `GET /api/stories?q=&category=&limit=` — grouped stories
- `GET /api/stories/{id}` — cluster detail
- `POST /api/refresh` — request a local refresh
- `GET /docs` — FastAPI API documentation

## Publisher feeds

The feed list is in `backend/app.py`. Feeds use public RSS/Atom endpoints; publishers control availability and terms. Review each publisher's current terms before public or commercial operation.
