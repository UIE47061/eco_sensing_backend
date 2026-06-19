# eco_sensing_backend

FastAPI backend project using routers.

## Project Structure

```text
app.py
routers/
  organizations.py
  sensors.py
  supabase_test.py
services/
  crud.py
  sensors.py
  supabase_test.py
util/
  config.py
db/
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
uvicorn app:app --reload
```

Or:

```bash
python app.py
```

Open:

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health
- Companies: http://127.0.0.1:8000/api/companies
- Departments: http://127.0.0.1:8000/api/departments
- Employees: http://127.0.0.1:8000/api/employees
- Sensors: http://127.0.0.1:8000/api/sensors
- Supabase test: http://127.0.0.1:8000/api/supabase/test
