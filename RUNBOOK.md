# Taren Game Studio — Core v0.1 Runbook

## Local development

Install:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Start the API/HQ:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 3020
```

Open:

```text
http://localhost:3020
```

## Development database

Without configuration, the service uses:

```text
sqlite+pysqlite:///./taren_game_studio.db
```

Production should set:

```bash
export TGS_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/DB'
alembic upgrade head
```

## Minimal FakeAgent verification

1. Create project:

```bash
curl -X POST http://localhost:3020/api/projects \
  -H 'content-type: application/json' \
  -d '{"name":"Pong Verification"}'
```

2. Send owner prompt using the returned project UUID:

```bash
curl -X POST http://localhost:3020/api/projects/PROJECT_ID/prompt \
  -H 'content-type: application/json' \
  -d '{"prompt":"Create a very simple Pong game for Windows."}'
```

3. Execute one deterministic studio cycle:

```bash
curl -X POST http://localhost:3020/api/projects/PROJECT_ID/run-cycle
```

Or complete all currently reachable FakeAgent work:

```bash
curl -X POST http://localhost:3020/api/projects/PROJECT_ID/run-until-idle
```

4. Paste the project UUID into Game Studio HQ and press **Connect**.

HQ loads current state from `/api/studio/state` and then consumes incremental events from `/ws/events`.
