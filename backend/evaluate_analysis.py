"""Opt-in real Gemini evaluation on reviewed synthetic inputs. No application DB.

This records model outputs for human rubric review; it is not a heuristic quality score.
"""
import argparse
import json
from pathlib import Path
from time import perf_counter
from analyzers.llm_analyzer import analyze_with_llm, generation_configuration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    cases = json.loads((Path(__file__).parent / 'evaluation/requirement_cases.json').read_text())
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', encoding='utf-8') as stream:
        for case in cases:
            inputs = {key:case[key] for key in ('title','description','requirement_type','project_context')}
            inputs.update(priority='Medium', clarifications='')
            started = perf_counter()
            result = analyze_with_llm(inputs)
            row = dict(case=case['id'], input=inputs, configuration=generation_configuration(),
                       elapsed_ms=round((perf_counter()-started)*1000, 1), **result)
            stream.write(json.dumps(row, ensure_ascii=True)+'\n')
            stream.flush()
            print(json.dumps({key:row[key] for key in ('case','elapsed_ms','status')}), flush=True)
            if result['status'] in ('quota_exceeded','authentication_error','missing_api_key','missing_model','model_unavailable'):
                break


if __name__ == '__main__':
    main()
