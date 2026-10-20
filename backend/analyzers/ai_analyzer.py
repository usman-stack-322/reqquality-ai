"""One semantic Gemini call, with no generated fallback content."""
import os
from time import perf_counter
from analyzers.llm_analyzer import analyze_with_llm, LIST_FIELDS, ANALYSIS_VERSION
from analyzers.value_safety import find_introduced_values
from middlewares.observability import record_timing


def analyze_ai(title, description, requirement_type, priority, clarifications='', **scope):
    start = perf_counter()
    try:
        result = analyze_with_llm(dict(title=title, description=description,
                                       requirement_type=requirement_type, priority=priority, clarifications=clarifications, **scope))
    except Exception:
        result = {'status': 'api_error', 'analysis': None}
    finally:
        record_timing('ai', (perf_counter() - start) * 1000)
    if not isinstance(result, dict):
        result = {'status': 'api_error', 'analysis': None}
    if result.get('status') != 'success' or not result.get('analysis'):
        category = result.get('status', 'api_error')
        reason = {'quota_exceeded': 'Gemini quota or rate limit reached.', 'network_error': 'Gemini timed out or could not be reached.', 'malformed_json': 'Gemini returned invalid or incomplete analysis.', 'model_unavailable': 'The configured Gemini model is unavailable.', 'missing_api_key': 'Gemini is not configured.', 'missing_model': 'A Gemini model is not configured.'}.get(category, 'Gemini analysis failed.')
        if category == 'service_unavailable':
            reason = 'Gemini is temporarily unavailable.'
        return {'status': 'failed', 'code': result.get('status', 'api_error'),
                'retryable': True, 'error': reason + ' Your input is preserved. Please retry.'}
    analysis = result['analysis']
    original = f'{title}\n{description}\n{clarifications}\n{scope.get("project_context", "")}'
    def label(text, source='ai_suggestion'):
        return dict(text=text, source=source, needs_confirmation=True,
                    introduced_values=find_introduced_values(text, original))
    analysis['labeled_analysis'] = {
        field: [label(text, 'ai_assumption' if field == 'assumptions' else 'ai_suggestion')
                for text in analysis[field]] for field in LIST_FIELDS
    }
    analysis['labeled_analysis']['improved_requirement'] = label(analysis['improved_requirement'])
    for index, scenario in enumerate(analysis['test_scenarios'], 1):
        scenario.update(id=f'SC-{index:03d}', source='ai_suggestion', needs_confirmation=True,
                        introduced_values=find_introduced_values(str(scenario), original),
                        assumption_reasons=[], linked_requirement=title)
    analysis.update(status='completed', analysis_mode='ai_only', analysis_version=ANALYSIS_VERSION,
                    model=os.getenv('GEMINI_MODEL', ''), llm_status='success',
                    risk_score=None, test_scenario_source='gemini')
    return analysis
