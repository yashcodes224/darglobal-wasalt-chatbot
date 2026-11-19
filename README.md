---
title: DarGlobal and Wasalt Assistant
emoji: 🏙️
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# DarGlobal & Wasalt Assistant

A retrieval-augmented chatbot that answers questions about **DarGlobal** (luxury developer: projects,
locations, brand partners, press) and **Wasalt** (Saudi property marketplace: features, property types, how it works).
It uses a free model from **OpenRouter**, runs in **Docker**, and has a built-in web UI.

## How it works

```
data/raw/*.jsonl  --process_data.py-->  data/processed/chunks.jsonl
                                               |
user question --> BM25 retrieval (app/rag.py) --> top chunks + question --> OpenRouter free model (app/llm.py)
                                                                              |
                                      answer + source links  <----------------+
```

- **Retrieval:** dependency-free BM25 with light stemming, month normalisation and a little query expansion (`app/rag.py`).
  Chosen deliberately over a vector DB: the dataset is small, so BM25 is fast, deterministic and keeps the image tiny.
- **Grounding:** the system prompt tells the model to answer only from the retrieved context, never invent prices or
  contact details, and treat context text as untrusted data (prompt-injection guard).
- **Resilience:** free models are rate-limited. `app/llm.py` tries several model IDs in order (the last is `openrouter/free`,
  OpenRouter's router for whatever free model is currently available). If every model fails, the API returns a
  **retrieval-only** answer instead of an error. There is also a per-IP rate limit (`RATE_LIMIT_PER_MIN`, default 12).
- **API:** `POST /api/chat {"message": "...", "history": [...]}` -> `{answer, sources, mode, model}`; `GET /health`.

## Data: provenance and limitations (please read)

The task asks for publicly available data from darglobal.co.uk and wasalt.sa. I wrote a scraper (`scrape.py`:
`robots.txt`-aware, polite delays, Playwright for JavaScript pages, diagnostics). In practice **both sites sit behind bot
protection** (DarGlobal: Imperva Incapsula; Wasalt: Cloudflare), which blocked most automated requests; I did not try to
circumvent that protection. The scraper stops at the first block page.

So the dataset is a **curated snapshot of the public pages, collected on 19 Nov 2026** (`build_seed_data.py`):

| File | Content |
|---|---|
| `data/raw/darglobal.jsonl` | all 38 projects on darglobal.co.uk/projects (name, location, country, URL, tagline) |
| `data/raw/darglobal_info.jsonl` | company overview, key figures, business lines, partners, press items |
| `data/raw/wasalt_info.jsonl` | Wasalt overview, features, property types, URL patterns, listing-volume snapshot, price guidance |
| `data/raw/wasalt.jsonl` (optional) | listing cards that `scrape.py` managed to read before a challenge page appeared |

Limitations: project pages are not detailed (no prices/unit sizes), Wasalt coverage is mostly descriptive rather than
a full listing database, and everything is a snapshot that goes stale. The bot says so instead of guessing. With official
API/feed access, the same pipeline (`process_data.py`) would ingest it unchanged.

## Run locally

```bash
python -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python process_data.py                                  # builds data/processed/chunks.jsonl
export OPENROUTER_API_KEY=sk-or-v1-...                  # Windows PowerShell: $env:OPENROUTER_API_KEY="sk-or-v1-..."
uvicorn app.main:app --port 7860                        # open http://localhost:7860
```

## Docker

```bash
cp .env.example .env            # put your OpenRouter key in .env (never commit it)
docker build -t darglobal-chatbot .
docker run --rm -p 7860:7860 --env-file .env darglobal-chatbot
# or: docker compose up --build
```

## Deploy (free) - Hugging Face Spaces, Docker SDK

1. Create a Space at huggingface.co/new-space: SDK **Docker**, template **Blank**, visibility **Public**.
2. Space **Settings -> Variables and secrets -> New secret**: `OPENROUTER_API_KEY` = your key.
3. Push this folder (the YAML block at the top of this README configures the Space):
   ```bash
   git clone https://huggingface.co/spaces/<user>/<space-name>
   cp -r darglobal-chatbot/* <space-name>/ && cd <space-name>
   git add . && git commit -m "Deploy chatbot" && git push
   ```
4. Wait for the build (~2-3 min). Your URL: `https://<user>-<space-name>.hf.space`.

Alternative: **Render** -> New Web Service -> connect the GitHub repo -> Runtime *Docker* -> add `OPENROUTER_API_KEY`.
Free instances sleep when idle, so open the URL yourself shortly before sending it.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | - | required for LLM answers (without it the bot runs retrieval-only) |
| `OPENROUTER_MODELS` | gemma-4-31b/26b `:free`, nemotron-3-ultra `:free`, `openrouter/free` | comma-separated, tried in order |
| `RATE_LIMIT_PER_MIN` | 12 | per-IP requests per minute |

Free model IDs change often. If answers show `retrieval-only`, check `GET /health` and openrouter.ai/models?q=free.
Free usage is also capped per account (reported as about 50 requests/day without credits), so keep test traffic modest.

## Tests

`python -c "from tests.test_smoke import test_retrieval; test_retrieval()"` (or `pytest`) checks retrieval on the dataset.
