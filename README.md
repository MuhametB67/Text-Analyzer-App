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
Browser  <--->  FastAPI (api)  <--->  Redis  <--->  Celery workers
```

- **FastAPI** takes the request and kicks off the job
- **Redis** is the message broker + stores the results
- **Celery workers** run the 5 tasks in parallel
- **Frontend** is just an HTML file with vanilla JS, it polls the API every ~400ms
- Everything runs in Docker via docker compose

## Job flow

1. You submit text to `POST /api/jobs`
2. The API creates a Celery `chord` with 5 subtasks + an aggregator at the end
3. Workers pick up the 5 tasks and run them at the same time
4. Frontend polls `GET /api/jobs/{job_id}` every 400ms
5. API tells the frontend how many tasks are done (using Celery's GroupResult)
6. Once all 5 are finished, the aggregator merges them into one result
7. Next poll gets `ready: true` and the dashboard renders

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

You can also see all the endpoints at http://localhost:8000/docs (the Swagger page FastAPI generates automatically).

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

### Test it quickly (manual)

1. Click the "Load sample" button (it fills in some example text)
2. Click "Analyze"
3. The 5 pills at the top turn green one by one as each worker finishes its task
4. Then the dashboard shows up with the stats, sentiment gauge, readability bar, keyword cloud, and per-sentence sentiment

If you want to test with your own text just paste something in the textarea instead.

### Automated smoke test

There's an end-to-end test in `tests/test_smoke.py`. Start the app in one terminal with `docker compose up`, then in another terminal:

```bash
pip install httpx pytest
pytest tests/ -v
```

Or just run it as a plain script:

```bash
python tests/test_smoke.py
```

It hits `/api/health`, submits a real job, polls until completion, and verifies that all 5 analyses came back with the expected keys (and that known emails/URLs from the sample text were correctly extracted).

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

Stuff I'd add if I had more time:
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
- More tests (unit tests for each task, not just the integration smoke test)

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
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── celery_app.py    # celery config
│   │   ├── main.py          # fastapi endpoints
│   │   └── tasks.py         # the 5 analysis tasks + aggregator
│   └── static/
│       └── index.html       # frontend (single html file)
├── docs/
│   ├── README.md
│   ├── 01-input-and-progress.png
│   └── 02-dashboard.png
└── tests/
    ├── __init__.py
    └── test_smoke.py        # end-to-end smoke test
```
