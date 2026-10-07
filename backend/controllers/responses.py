"""Convert service results to the existing Flask response format."""
from flask import jsonify

def respond(result):
    if isinstance(result, tuple):
        body, *options = result
        if isinstance(body, (dict, list)):
            body = jsonify(body)
        return (body, *options)
    if isinstance(result, (dict, list)):
        return jsonify(result)
    return result
