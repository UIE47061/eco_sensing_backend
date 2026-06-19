# eco_sensing_backend

FastAPI backend project using routers.

## Project Structure

```text
app.py
routers/
  eco_records.py
  organizations.py
  supabase_test.py
services/
  crud.py
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
- Emission factors: http://127.0.0.1:8000/api/emission-factors
- Travel records: http://127.0.0.1:8000/api/travel-records
- Waste bins: http://127.0.0.1:8000/api/waste-bins
- Devices: http://127.0.0.1:8000/api/devices
- Waste sessions: http://127.0.0.1:8000/api/waste-sessions
- Waste events: http://127.0.0.1:8000/api/waste-events
- Elevator trips: http://127.0.0.1:8000/api/elevator-trips
- Digital usages: http://127.0.0.1:8000/api/digital-usages
- Supabase test: http://127.0.0.1:8000/api/supabase/test
