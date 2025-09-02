# harness.py
import json, types, sys, traceback
SCRIPT =  "user_script.py"
RESULT = "result.json"


def fail(msg: str, exc: BaseException | None = None) -> None:
    if exc:
        print(msg, file=sys.stderr)
        traceback.print_exc()
    else:
        print(msg, file=sys.stderr)
    sys.exit(1)

try:
    with open(SCRIPT, encoding="utf-8") as f:
        code = f.read()

except Exception as e:
    fail(f"Failed to read user_script.py: {e}", e)

# Execute user code in an isolated module namespace
mod = types.ModuleType("user_script")
try:
    compiled = compile(code, str(SCRIPT), "exec")
    exec(compiled, mod.__dict__)
except Exception as e:
    fail("Failed to import/exec user script", e)

main = getattr(mod, "main", None)
if not callable(main):
    fail("main() is missing or not callable")

try:
    ret = main()
except Exception as e:
    fail("Exception while running main()", e)

# Validate JSON-serializable and persist to result.json
try:
    payload = json.dumps(ret)
except Exception as e:
    fail(f"main() must return JSON-serializable data: {e}", e)

try:
    with open(RESULT, "w", encoding="utf-8") as f:
        f.write(payload)
except Exception as e:
    fail(f"Failed to write result.json: {e}", e)
