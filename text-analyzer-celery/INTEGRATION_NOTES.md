# What to do with these files

Drop these into your existing `text-analyzer-celery/` repo, overwriting the
existing files where paths match.

## New files

- `backend/api/Dockerfile`
- `backend/api/requirements.txt`
- `backend/worker/Dockerfile`
- `backend/worker/requirements.txt`

## Overwritten files

- `docker-compose.yml`
- `backend/requirements-dev.txt`
- `README.md`

## Files to DELETE from your existing repo

- `backend/Dockerfile`           ← replaced by api/Dockerfile + worker/Dockerfile
- `backend/requirements.txt`     ← replaced by api/requirements.txt + worker/requirements.txt

## Verify after integrating

```bash
# 1. Clean rebuild — both images should build with no errors
docker compose down -v
docker compose up --build -d

# 2. Smoke + unit tests still pass
pip install -r backend/requirements-dev.txt
python -m pytest tests/ -v

# 3. Prove the worker image really doesn't have FastAPI (the whole point)
docker compose run --rm --no-deps worker python -c "import fastapi" \
  && echo "FAIL: worker should not have fastapi" \
  || echo "OK: worker image is fastapi-free"
```

The last command is worth pasting into your reply to the reviewer — it shows
the decoupling is real, not just a folder rename.
