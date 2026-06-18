# eco_sensing_backend

FastAPI backend project using routers.

## Project Structure

```text
app/
  main.py
  api/
    router.py
    routes/
      health.py
      sensors.py
  core/
    config.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

Open:

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/v1/health
- Sensors: http://127.0.0.1:8000/api/v1/sensors
