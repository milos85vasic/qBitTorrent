# Load Testing with Locust

## Prerequisites

```bash
pip install locust
```

## Running

Headless (CI-friendly):

```bash
locust -f tests/load/locustfile.py --host http://localhost:7187 -u 100 -r 10 --headless --run-time 60s
```

Web UI (interactive):

```bash
locust -f tests/load/locustfile.py --host http://localhost:7187
```

Then open http://localhost:8089 to configure and watch live metrics.

## Profile

| Weight | Endpoint | Description |
|--------|----------|-------------|
| 3 | `GET /api/v1/search?q=ubuntu&trackers=nyaa` | Main search |
| 2 | `GET /` | Dashboard page |
| 1 | `GET /health` | Health check |
