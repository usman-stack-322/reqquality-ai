from services.responses import response_payload

def health():
    return response_payload(status='ok', message='ReqQuality AI API is running')
