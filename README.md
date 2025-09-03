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



## Local quickstart

Build and run:
```bash
docker build -t stacksync-demo:latest .
docker run --rm -p 8080:8080 stacksync-demo:latest
```

Try it:
```bash
curl -s -X POST http://localhost:8080/execute \
  -H 'Content-Type: application/json' \
  -d '{"script":"def main():\n    import numpy as np\n    print(np.arange(3))\n    return {\"sum\": int(np.sum([1,2,3])) }\n"}' | jq
```

```bash
curl -s -X POST https://stacksync-demo-7j7yxeecia-ew.a.run.app/execute \
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

## Notes

- The service allows importing `os`, `numpy`, and `pandas`.

