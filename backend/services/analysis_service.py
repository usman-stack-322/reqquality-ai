from analyzers.hybrid_analyzer import analyze_hybrid
from app import REQUIREMENT_TYPES, PRIORITIES, analyze_hybrid
from services.responses import response_payload

def analyze_requirement_endpoint(payload):
    data = payload
    if not isinstance(data, dict):
        return (response_payload(error='Send a JSON object with requirement details.'), 400)
    title = data.get('title')
    description = data.get('description')
    requirement_type = data.get('requirement_type')
    priority = data.get('priority')
    if not isinstance(title, str) or not title.strip():
        return (response_payload(error='Please enter a requirement title.'), 400)
    if not isinstance(description, str) or not description.strip():
        return (response_payload(error='Please enter a requirement description.'), 400)
    if not isinstance(requirement_type, str) or requirement_type not in REQUIREMENT_TYPES:
        return (response_payload(error='Choose a valid requirement type.'), 400)
    if not isinstance(priority, str) or priority not in PRIORITIES:
        return (response_payload(error='Choose a valid priority.'), 400)
    return response_payload(analyze_hybrid(title, description, requirement_type, priority))
