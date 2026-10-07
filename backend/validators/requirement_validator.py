from app import PRIORITIES, RISK_LEVELS, SCENARIO_CATEGORIES, CONTENT_SOURCES

def _validate_analysis_payload(analysis):
    if analysis is None:
        return None
    if not isinstance(analysis, dict):
        return 'Analysis must be an object.'
    risk_score = analysis.get('risk_score')
    if risk_score is not None and (isinstance(risk_score, bool) or not isinstance(risk_score, int) or (not 0 <= risk_score <= 100)):
        return 'Risk score must be an integer from 0 to 100.'
    suggested_priority = analysis.get('suggested_priority')
    if suggested_priority is not None and suggested_priority not in PRIORITIES:
        return 'Analysis contains an invalid suggested priority.'
    risk_level = analysis.get('risk_level')
    if risk_level is not None and risk_level not in RISK_LEVELS:
        return 'Analysis contains an invalid risk level.'
    criteria = analysis.get('acceptance_criteria', [])
    if not isinstance(criteria, list) or any((not isinstance(value, str) for value in criteria)):
        return 'Acceptance criteria must be a list of strings.'
    scenarios = analysis.get('test_scenarios', [])
    if not isinstance(scenarios, list):
        return 'Test scenarios must be a list.'
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            return 'Each test scenario must be an object.'
        if scenario.get('category') not in SCENARIO_CATEGORIES:
            return 'A test scenario has an invalid category.'
        if not isinstance(scenario.get('title'), str) or not scenario['title'].strip():
            return 'Each test scenario must have a title.'
        if not isinstance(scenario.get('expected_result'), str):
            return 'Each test scenario must have an expected result.'
        for field in ('preconditions', 'test_steps'):
            values = scenario.get(field, [])
            if not isinstance(values, list) or any((not isinstance(value, str) for value in values)):
                return f"Scenario {field.replace('_', ' ')} must be a list of strings."
        if scenario.get('source') is not None and scenario['source'] not in CONTENT_SOURCES:
            return 'A test scenario has an invalid source.'
        if scenario.get('needs_confirmation') is not None and (not isinstance(scenario['needs_confirmation'], bool)):
            return 'Scenario needs_confirmation must be true or false.'
        for field in ('introduced_values', 'assumption_reasons'):
            values = scenario.get(field, [])
            if not isinstance(values, list) or any((not isinstance(value, str) for value in values)):
                return f"Scenario {field.replace('_', ' ')} must be a list of strings."
    labeled_analysis = analysis.get('labeled_analysis', {})
    if not isinstance(labeled_analysis, dict):
        return 'Labeled analysis must be an object.'
    for field in ('acceptance_criteria', 'assumptions'):
        items = labeled_analysis.get(field, [])
        if not isinstance(items, list):
            return f"Labeled {field.replace('_', ' ')} must be a list."
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get('text'), str):
                return f"Each labeled {field.replace('_', ' ')} item must include text."
            if item.get('source') not in CONTENT_SOURCES:
                return f"A labeled {field.replace('_', ' ')} item has an invalid source."
            if not isinstance(item.get('needs_confirmation'), bool):
                return f"A labeled {field.replace('_', ' ')} item needs a confirmation flag."
            values = item.get('introduced_values', [])
            if not isinstance(values, list) or any((not isinstance(value, str) for value in values)):
                return 'Introduced values must be a list of strings.'
    return None
