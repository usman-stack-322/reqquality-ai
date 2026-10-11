"""Compare HEAD and working tree sequentially with the same synthetic benchmark.

Only tracked Python source is copied; no credentials, live data or migrations.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
python = root / 'backend' / '.venv' / 'Scripts' / 'python.exe'
env = {**os.environ, 'DATABASE_URL': '', 'GEMINI_API_KEY': ''}
with tempfile.TemporaryDirectory(prefix='.audit-baseline-', dir=root) as directory:
    target = Path(directory).resolve()
    assert target.is_relative_to(root.resolve())
    sources = subprocess.check_output(['git', 'ls-files', 'backend/*.py', 'backend/**/*.py'], cwd=root, text=True).splitlines()
    for source in sources:
        destination = target / source
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(subprocess.check_output(['git', 'show', 'HEAD:' + source], cwd=root))
    (target / 'backend' / 'benchmark_audit.py').write_bytes((root / 'backend' / 'benchmark_audit.py').read_bytes())
    for label, folder in [('before', target / 'backend'), ('after', root / 'backend')]:
        for benchmark in ['benchmark_audit.py', 'benchmark_login.py']:
            result = subprocess.run([str(python), benchmark], cwd=folder, env=env, capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                print(json.dumps({'revision': label, 'benchmark': benchmark, **json.loads(line)}))
