from controllers.responses import respond
from services import reports_service as service

def export_requirement_pdf(requirement_id):
    return respond(service.export_requirement_pdf(requirement_id))

def export_project_pdf():
    return respond(service.export_project_pdf())

def export_requirements_csv():
    return respond(service.export_requirements_csv())
