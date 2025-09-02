# Safe Python Script Execution Service

A tiny Flask + nsjail service that executes a user-provided Python script safely
by calling `main()` inside a sandbox and returning both the `result` (JSON) and
captured `stdout`.

## API

**POST** `/execute`

Request:
```json
{
  "script": "def main():\n    print('hello')\n    return {'ok': True}\n"
}
```

Response (200):
```json
{
  "result": {"ok": true},
  "stdout": "hello\n"
}
```

Errors (examples):
```json
{ "error": { "type":"ValidationError", "message":"missing 'script' field" } }
{ "error": { "type":"ExecutionError", "message":"main() is missing or not callable" }, "stdout": "..." }
{ "error": { "type":"SerializationError", "message":"main() must return JSON-serializable data" }, "stdout": "..." }
```

## Security model

- **nsjail** with PID/Mount/User/Net namespaces, read-only root FS.
- No network (even loopback is disabled).
- Tight resource limits: 1 CPU, 3s wall time, 256 MiB memory, 10 MiB file size, max 64 pids.
- Writable paths: `/sandbox` (bind of a per-request temp dir), `/tmp` (tmpfs).
- Cloud Run adds an extra sandbox layer.

## Local quickstart

Build and run:
```bash
docker build -t safe-py:latest .
docker run --rm -p 8080:8080 safe-py:latest
```

Try it:
```bash
curl -s -X POST http://localhost:8080/execute \
  -H 'Content-Type: application/json' \
  -d '{"script":"def main():\n    import numpy as np\n    print(np.arange(3))\n    return {\"sum\": int(np.sum([1,2,3])) }\n"}' | jq
```

Expected:
```json
{
  "result": { "sum": 6 },
  "stdout": "[0 1 2]\n"
}
```

## Deploy to Cloud Run

```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/safe-py
gcloud run deploy safe-py \
  --image gcr.io/$PROJECT_ID/safe-py \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1
```

Test (replace `$URL` with Cloud Run URL):
```bash
curl -s -X POST "$URL/execute" \
  -H 'Content-Type: application/json' \
  -d '{"script":"def main():\n    import os, pandas as pd\n    print(list(sorted(os.listdir(\"/\")))[:5])\n    return { \"rows\": int(pd.DataFrame({\"a\":[1,2,3]}).shape[0]) }\n"}' | jq
```

## Notes

- The service allows importing `os`, `numpy`, and `pandas`.

