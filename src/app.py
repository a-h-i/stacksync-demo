import json, os, tempfile, subprocess
from flask import Flask, request, jsonify
import shutil

app = Flask(__name__)

MAX_SCRIPT_BYTES = 200_000

def run_in_jail(workdir: str):
    proc = subprocess.run(
        [
         "nsjail", "--config", "/app/nsjail.cfg",
         "--tmpfsmount", "/tmp",
         "--cwd",
         workdir,
         "--",
         "/usr/local/bin/python3",
         f"{workdir}/harness.py"
        ],
        cwd=workdir,
        capture_output=True,
        text=True,
    )
    return proc

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

    with tempfile.TemporaryDirectory(prefix="exec-") as d:
        # Prepare files
        script_file = open(os.path.join(d,"user_script.py"),"w")
        script_file.write(script)
        script_file.close()
        shutil.copy("/app/harness.py", os.path.join(d, "harness.py"))

        try:
            proc = run_in_jail(d)
        except subprocess.TimeoutExpired:
            return jsonify(error={"type":"ExecutionError","message":"time limit exceeded"}), 408

        stdout = proc.stdout
        stderr = proc.stderr

        result_path = os.path.join(d,"result.json")
        if proc.returncode != 0:
            return jsonify(error={"type":"ExecutionError","message":"script crashed","details":stderr.strip()}, stdout=stdout), 400

        if not os.path.exists(result_path):
            return jsonify(error={"type":"ExecutionError","message":"main() did not produce a result"}, stdout=stdout), 400

        try:
            result = json.loads(open(result_path).read())
        except Exception:
            return jsonify(error={"type":"SerializationError","message":"invalid result.json"}, stdout=stdout), 400

        return jsonify(result=result, stdout=stdout)
