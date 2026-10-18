"""Verify account model availability; optional synthetic analysis smoke test."""
import argparse,json,os
from time import perf_counter
from analyzers.llm_analyzer import _error_status


def main():
    from google import genai
    from google.genai import types
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true',help='Generate a synthetic analysis (uses provider quota).')
    args=parser.parse_args()
    key,model=os.getenv('GEMINI_API_KEY','').strip(),os.getenv('GEMINI_MODEL','').strip()
    if not key or not model:
        print(json.dumps({'status':'configuration_missing'}));return 1
    try:
        with genai.Client(api_key=key,http_options=types.HttpOptions(timeout=15000,retry_options=types.HttpRetryOptions(attempts=1))) as client:
            available=any(m.name.removeprefix('models/')==model.removeprefix('models/') and 'generateContent' in (m.supported_actions or []) for m in client.models.list())
        print(json.dumps({'configured_model':model,'available_for_generate_content':available}))
        if not available:return 1
        if args.smoke:
            from analyzers.ai_analyzer import analyze_ai
            start=perf_counter()
            result=analyze_ai('Sign in','Registered users can sign in using valid credentials. Invalid credentials display a generic error.','Functional','Medium')
            print(json.dumps({'status':result.get('status'),'code':result.get('code'),'ms':round((perf_counter()-start)*1000,1),'criteria':len(result.get('acceptance_criteria',[])),'scenarios':len(result.get('test_scenarios',[]))}))
            return 0 if result.get('status')=='completed' else 1
        return 0
    except Exception as e:
        print(json.dumps({'status':_error_status(e),'exception_type':type(e).__name__}));return 1

if __name__=='__main__':raise SystemExit(main())
