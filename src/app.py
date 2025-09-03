import json, os, tempfile, subprocess, pathlib, shutil
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- Tunables (all safe for Cloud Run) ---
MAX_SCRIPT_BYTES = int(os.environ.get("MAX_SCRIPT_BYTES", "200000"))
NSJAIL_TIMEOUT_SECONDS = float(os.environ.get("NSJAIL_TIMEOUT_SECONDS", "20"))
STDOUT_MAX_CHARS = int(os.environ.get("STDOUT_MAX_CHARS", "100000"))

# Result markers (obscure on purpose)
RESULT_TOKEN = "__NSJAIL_JSON_RESULT__:"
ERROR_TOKEN = "__NSJAIL_JSON_ERROR__:"

HARNESS_CODE = f"""\
import sys, json, types, traceback, pathlib
RESULT_TOKEN = "{RESULT_TOKEN}"
ERROR_TOKEN = "{ERROR_TOKEN}"

script_path = pathlib.Path(sys.argv[1])
try:
    code = script_path.read_text(encoding="utf-8")
except Exception as e:
    print(ERROR_TOKEN + f"read:{{e}}", file=sys.stderr); raise

mod = types.ModuleType("user_script")
try:
    exec(compile(code, str(script_path), "exec"), mod.__dict__)
except Exception as e:
    print(ERROR_TOKEN + f"import:{{e}}", file=sys.stderr); raise

main = getattr(mod, "main", None)
if not callable(main):
    print(ERROR_TOKEN + "missing_main", file=sys.stderr)
    raise SystemExit(1)

try:
    ret = main()
except Exception as e:
    print(ERROR_TOKEN + f"run:{{e}}", file=sys.stderr); raise

try:
    payload = json.dumps(ret)
except Exception as e:
    print(ERROR_TOKEN + f"not_json:{{e}}", file=sys.stderr)
    raise SystemExit(1)

# Emit the result marker as the final line on stdout
print(RESULT_TOKEN + payload)
"""

def _resolve_python_bin() -> str:
    explicit = os.environ.get("PYTHON_BIN")
    if explicit and shutil.which(explicit):
        return explicit
    for c in ("/usr/local/bin/python3","/usr/local/bin/python","/usr/bin/python3","/usr/bin/python","python3","python"):
        if shutil.which(c):
            return c
    return "/usr/local/bin/python3"

def _truncate(s: str, n: int) -> str:
    if not s or len(s) <= n: return s or ""
    return s[:n] + f"\n... [truncated {len(s) - n} chars]\n"

def _run_in_nsjail(script_path: str):
    pybin = _resolve_python_bin()
    # No bind mounts, no namespaces — purely Cloud Run–safe
    cmd = [
        "nsjail", "--config", '/app/nsjail.cfg',
        "--", pybin, "-c", HARNESS_CODE, script_path
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=NSJAIL_TIMEOUT_SECONDS,
    )

@app.post("/execute")
def execute():
    if not request.is_json:
        return jsonify(error={"type":"ValidationError","message":"Content-Type must be application/json"}), 400
    data = request.get_json(silent=True) or {}
    script = data.get("script")
    if not isinstance(script, str):
        return jsonify(error={"type":"ValidationError","message":"'script' must be a string"}), 400
    if len(script.encode("utf-8")) > MAX_SCRIPT_BYTES:
        return jsonify(error={"type":"ValidationError","message":"script too large"}), 413

    with tempfile.NamedTemporaryFile(prefix="exec-", suffix=".py", mode="w", encoding="utf-8", delete=True) as tf:
        tf.write(script)
        tf.flush()

        try:
            proc = _run_in_nsjail(tf.name)
        except subprocess.TimeoutExpired:
            return jsonify(error={"type":"ExecutionError","message":"time limit exceeded"}), 408
        except FileNotFoundError as e:
            return jsonify(error={"type":"ServerError","message":f"nsjail/python not available: {e}"}), 500

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        # Parse result from the LAST line starting with RESULT_TOKEN
        result_json = None
        user_stdout_lines = []
        for line in stdout.splitlines():
            if line.startswith(RESULT_TOKEN):
                result_json = line[len(RESULT_TOKEN):]
            else:
                user_stdout_lines.append(line)

        user_stdout = _truncate(("\n".join(user_stdout_lines) + ("\n" if user_stdout_lines else "")), STDOUT_MAX_CHARS)

        # If nsjail returned non-zero, try to map a structured error
        if proc.returncode != 0:
            # Check for structured harness error
            harness_err = None
            for line in (stderr.splitlines() or []):
                if line.startswith(ERROR_TOKEN):
                    harness_err = line[len(ERROR_TOKEN):]
            message = "script crashed"
            if harness_err == "missing_main":
                return jsonify(error={"type":"ExecutionError","message":"main() is missing or not callable"}, stdout=user_stdout), 400
            if harness_err:
                # Map common prefixes
                if harness_err.startswith("read:"):
                    message = f"failed to read script: {harness_err[5:]}"
                elif harness_err.startswith("import:"):
                    message = f"exception during import: {harness_err[7:]}"
                elif harness_err.startswith("run:"):
                    message = f"exception during main(): {harness_err[4:]}"
                elif harness_err.startswith("not_json:"):
                    message = f"main() must return JSON-serializable data: {harness_err[9:]}"
                else:
                    message = harness_err
            return jsonify(error={"type":"ExecutionError","message":message,"details":_truncate(stderr, STDOUT_MAX_CHARS)}, stdout=user_stdout), 400

        if result_json is None:
            return jsonify(error={"type":"ExecutionError","message":"no result emitted (missing RESULT token)"}, stdout=user_stdout), 400

        try:
            result = json.loads(result_json)
        except Exception as e:
            return jsonify(error={"type":"SerializationError","message":f"invalid result json: {e}"}, stdout=user_stdout), 400

        return jsonify(result=result, stdout=user_stdout)

@app.get("/healthz")
def health():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","8080")))
