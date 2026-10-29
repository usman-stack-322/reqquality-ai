from flask import jsonify, request
from middlewares.auth import login_required, csrf_required
from services import review_assistant_service as service


def register_routes(app):
    @app.post('/api/requirements/<int:rid>/ai-review')
    @login_required
    @csrf_required
    def open_ai_review(rid):
        return jsonify(service.open_conversation(rid,request.get_json(silent=True)))

    @app.post('/api/requirements/<int:rid>/ai-review/<cid>/messages')
    @login_required
    @csrf_required
    def ai_review_message(rid,cid):
        return jsonify(service.generate(rid,cid,request.get_json(silent=True)))

    @app.post('/api/requirements/<int:rid>/ai-review/<cid>/proposals/<tid>')
    @login_required
    @csrf_required
    def decide_ai_review(rid,cid,tid):
        return jsonify(service.decide(rid,cid,tid,request.get_json(silent=True)))
