# text-analyzer-celery

Mini app for the coding task. You paste text and it runs 5 different analyses on it in parallel using Celery workers. The frontend shows a progress bar while the workers are running and then a dashboard with all the results.

## What it does

You type or paste text into the form, click Analyze, and 5 background tasks run at the same time:

1. **Basic stats** — word count, sentence count, reading time, etc.
2. **Readability** — Flesch score + grade level (tells you if the text is easy or hard to read)
3. **Sentiment** — checks if the text is positive, negative or neutral. Also does it per sentence.
4. **Keywords** — finds the most common words (skips common stuff like "the", "and")
5. **Entities** — pulls out emails, URLs, hashtags, @mentions, dates, and names

The frontend polls the API until everything is done and then renders a dashboard.

## Architecture

```
Browser  →  nginx  →  FastAPI (api)  →  Redis  ←→  Celery worker
```

Four services in `docker-compose.yml`, each in its own container:

- **nginx** — serves the static frontend (HTML/JS/CSS) and reverse-proxies `/api/*` to FastAPI. This separates web serving from API serving.
- **api** — FastAPI service. Handles `POST /api/jobs` (kick off work) and `GET /api/jobs/{id}` (poll progress). Built from `backend/api/Dockerfile` with its own pinned `requirements.txt` (fastapi + uvicorn + celery client + redis + pydantic).
- **worker** — Celery worker that runs the 5 analysis tasks. Concurrency is set to 5 so all 5 subtasks can run in parallel. Built from `backend/worker/Dockerfile` with its own pinned `requirements.txt` (celery + redis only — no FastAPI/uvicorn/pydantic, since the worker process never imports them). Each service has a separate build context for its dependencies; only the shared `app/` source tree is copied into both images.
- **redis** — message broker (api → worker queue) and result backend (where finished task results are stored).

## Job flow

1. You submit text to `POST /api/jobs`
2. The API creates a Celery `chord` with 5 subtasks + an aggregator at the end
3. Workers pick up the 5 tasks and run them at the same time
4. Frontend polls `GET /api/jobs/{job_id}` every ~400ms
5. API tells the frontend how many tasks are done (using Celery's GroupResult)
6. Once all 5 are finished, the aggregator merges them into one result
7. Next poll gets `ready: true` and the dashboard renders

### Task time limits

Each of the 5 analysis tasks has:
- `soft_time_limit=30s` — raises `SoftTimeLimitExceeded` inside the task. Caught by the task and returns a partial `{"error": "timeout", "partial": true}` result instead of crashing.
- `time_limit=60s` — hard kill if the task really hangs.

This means one slow input can't bring down the whole job — the chord still completes, with the timed-out task reporting partial.

### Chunked processing for large inputs

`keywords` and `entities` process the input in 10,000-character chunks instead of one giant pass:

- The text is split at sentence boundaries (`. ! ?`) so words and sentences are never broken
- Each chunk's results are merged: counters are summed, sets are unioned
- For `keywords`, the last word of each chunk is carried into the next so bigrams that span a chunk boundary are still counted
- The response includes a `chunks_processed` field so you can see how many chunks were used

This keeps memory bounded for large inputs and gives the worker natural yield points between chunks (where the soft time limit can be raised and caught cleanly).

`basic_stats`, `readability`, and `sentiment` are not chunked because their math is whole-text by nature — Flesch readability is a single document-level score, sentence-level sentiment already operates per sentence, and basic stats are just counts that don't need chunking to stay fast.

## API endpoints

### POST /api/jobs

Send JSON with the text you want to analyze.

Request:
```json
{ "text": "your text here" }
```

Response:
```json
{
  "job_id": "abc123...",
  "group_id": "def456...",
  "total_tasks": 5
}
```

You need to save both `job_id` and `group_id` because you pass them both to the next endpoint.

### GET /api/jobs/{job_id}?group_id={group_id}

Poll this to check progress / get the result.

While still running:
```json
{
  "status": "STARTED",
  "ready": false,
  "progress": { "completed": 3, "total": 5, "percent": 60.0 },
  "result": null
}
```

When done:
```json
{
  "status": "SUCCESS",
  "ready": true,
  "successful": true,
  "progress": { "completed": 5, "total": 5, "percent": 100.0 },
  "result": {
    "basic_stats": { "words": 170, "sentences": 15, ... },
    "readability": { "flesch_reading_ease": 68.2, ... },
    "sentiment": { "overall": "positive", "polarity": 0.33, "per_sentence": [...] },
    "keywords": { "top_keywords": [...], "top_phrases": [...] },
    "entities": { "emails": [...], "urls": [...], "dates": [...], ... }
  }
}
```

The `group_id` param is optional but you need it if you want the progress info.

### GET /api/health

Just a health check. Returns `{"status": "ok"}`. Used by the smoke test.

You can also see all the endpoints at http://localhost:8000/docs (the Swagger page FastAPI generates automatically — proxied through nginx).

## How to run it

You need Docker Desktop running.

```bash
git clone <this repo>
cd text-analyzer-celery
cp .env.example .env   # optional — only needed if you want to override REDIS_URL
docker compose up --build
```

First build takes a minute or two (pulling images + installing python deps). After that open:

http://localhost:8000

### Reproducibility

All Python dependencies are pinned to exact versions across three files:

- `backend/api/requirements.txt` — runtime deps for the FastAPI service
- `backend/worker/requirements.txt` — runtime deps for the Celery worker (a strict subset of the api's deps)
- `backend/requirements-dev.txt` — adds pytest + httpx for tests

No floating versions, no `>=` constraints, no minimum-only specifiers. `docker compose up --build` produces identical builds across machines. Each service installs only what its process actually imports — the worker image, for example, does not include FastAPI or uvicorn.

To verify the decoupling is real (worker image is fastapi-free):

```bash
docker compose run --rm --no-deps worker python -c "import fastapi" \
  && echo "FAIL: worker should not have fastapi" \
  || echo "OK: worker image is fastapi-free"
```

### Test it quickly (manual)

1. Click the "Load sample" button (it fills in some example text)
2. Click "Analyze"
3. The 5 pills at the top turn green one by one as each worker finishes its task
4. Then the dashboard shows up with the stats, sentiment gauge, readability bar, keyword cloud, and per-sentence sentiment

If you want to test with your own text just paste something in the textarea instead.

## Tests

There are two test files under `tests/`:

### Unit tests (`tests/test_tasks.py`)

26 unit tests that run each Celery task as a plain function — no broker or worker needed. They verify output shape, value ranges, known-correct outputs (e.g. that "I love this" classifies as positive, that emails are correctly extracted, that stopwords are filtered), and that chunked processing of large inputs (50k+ chars) produces correct merged results.

```bash
pip install -r backend/requirements-dev.txt
python -m pytest tests/test_tasks.py -v
```

### Smoke test (`tests/test_smoke.py`)

End-to-end test that hits the running app. Submits a real job, polls until completion, and verifies all 5 analyses came back. Requires `docker compose up` running in another terminal.

```bash
pip install -r backend/requirements-dev.txt
python -m pytest tests/test_smoke.py -v
```

### Run everything

```bash
python -m pytest tests/ -v
```

## How this satisfies the task requirements

The task said:
- "FastAPI endpoint kicks off a Celery job" → `POST /api/jobs` does that
- "split into parallel tasks" → 5 subtasks run at the same time (via Celery `group` + `chord`)
- "results can be polled by ID" → `GET /api/jobs/{job_id}`
- "simple frontend form submits jobs" → the textarea + button at `/`
- "displays progress/results" → progress bar + 5 green pills + dashboard at the end
- "runs locally via Docker Compose" → `docker compose up --build`

All of it works end to end.

## Known limitations

- **Sentiment is not ML-based.** I just use a list of positive/negative words and count matches. It won't catch sarcasm or stuff like "not good" (negation). A real version would use something like VADER or a trained model.
- **Entity detection is regex.** Works ok for emails/URLs/dates but proper nouns are just "words that start with a capital letter", which picks up false positives sometimes (like the first word of a sentence).
- **English only.** The stopword list and the positive/negative words are all English. Wouldn't work on other languages.
- **No login / auth.** Anyone who can hit the port can use it.
- **No database.** Results are stored in Redis for 1 hour and then gone.
- **Text limit is 100,000 characters.** Hardcoded in `main.py`.
- Each task has a tiny `time.sleep()` (0.4–0.6 seconds) so you can actually see the progress bar move during the demo. In a real app I'd remove these.

## Future improvements

- Real sentiment analysis with VADER or a proper model
- Use spaCy for entity detection instead of regex
- Support for other languages (detect language, use matching stopwords/sentiment lexicon)
- WebSockets instead of polling so progress updates are instant
- Flower dashboard to monitor Celery workers (`:5555`)
- A short GIF of the progress pills lighting up (currently only stills are included)
- Save jobs to Postgres so history doesn't disappear
- Export results to JSON/CSV/Markdown
- Rate limiting (slowapi)
- GitHub Actions workflow that runs the smoke test on every PR
- Switch to `pip-tools` / `pip-compile` for full transitive dependency locking
- Decouple the api from the worker module entirely by switching to string-based `celery_app.send_task("app.tasks.basic_stats", ...)` dispatch, so the api image no longer needs to import task definitions at all

## Screenshots

Two screenshots are in the `docs/` folder:
- `01-input-and-progress.png` — the form with sample text loaded and the progress bar at 100%
- `02-dashboard.png` — the final dashboard with sentiment, readability, keywords, and entities

## Folder layout

```
text-analyzer-celery/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── backend/
│   ├── requirements-dev.txt    # adds pytest + httpx for tests
│   ├── api/                    # FastAPI service — own Dockerfile + own pinned requirements
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── worker/                 # Celery worker — own Dockerfile + own pinned requirements
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── app/                    # shared application code (imported by both services)
│       ├── __init__.py
│       ├── celery_app.py       # celery config
│       ├── main.py             # fastapi endpoints (used by api)
│       └── tasks.py            # 5 analysis tasks + aggregator (executed by worker;
│                               # signatures imported by api to build the chord)
├── frontend/                   # nginx service
│   ├── Dockerfile
│   ├── nginx.conf              # serves static + proxies /api → api:8000
│   └── index.html              # the single-page UI
├── docs/
│   ├── 01-input-and-progress.png
│   └── 02-dashboard.png
└── tests/
    ├── __init__.py
    ├── test_tasks.py           # 26 unit tests (incl. chunked processing), no docker required
    └── test_smoke.py           # end-to-end smoke test
```
