from flask import request

def register_response_headers(app):

    @app.after_request
    def reset_privacy(response):
        if request.path.startswith('/api/auth/'):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
        return response
