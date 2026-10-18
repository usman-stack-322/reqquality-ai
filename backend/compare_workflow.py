"""Read-only HEAD source comparison; no credentials or real DB copied."""
import os,sys,json,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
python=root/'backend/.venv/Scripts/python.exe'
env={**os.environ,'DATABASE_URL':'','GEMINI_API_KEY':''}
with tempfile.TemporaryDirectory(prefix='.workflow-baseline-',dir=root) as directory:
    target=Path(directory)
    sources=subprocess.check_output(['git','ls-files','backend/*.py','backend/**/*.py'],cwd=root,text=True).splitlines()
    for source in sources:
        p=target/source;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(subprocess.check_output(['git','show','HEAD:'+source],cwd=root))
    (target/'backend/benchmark_workflow.py').write_bytes((root/'backend/benchmark_workflow.py').read_bytes())
    for label,folder in [('before',target/'backend'),('after',root/'backend')]:
        # Separate interpreter imports, no request or DB access.
        imports=[]
        for _ in range(3):
            r=subprocess.run([str(python),'-c','import time; s=time.perf_counter(); import app; print(round((time.perf_counter()-s)*1000,2))'],cwd=folder,env=env,capture_output=True,text=True,check=True)
            imports.append(float(r.stdout.strip()))
        print(json.dumps({'revision':label,'operation':'process_import','samples_ms':imports}),flush=True)
        r=subprocess.run([str(python),'benchmark_workflow.py'],cwd=folder,env=env,capture_output=True,text=True,check=True)
        for line in r.stdout.splitlines(): print(json.dumps({'revision':label,**json.loads(line)}),flush=True)
