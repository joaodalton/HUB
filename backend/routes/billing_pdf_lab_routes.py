"""Laboratório documental exclusivo de platform admin; sem gravação operacional."""
import hashlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import BoundedSemaphore
from time import perf_counter

from flask import Blueprint, current_app, g, request
from werkzeug.utils import secure_filename

from services.billing_pdf_lab_service import analyze_pdf
from services.fatura_concessionaria_upload_service import InvoiceUploadError, _validate_pdf
from utils.api_response import error_response, success_response


billing_pdf_lab_routes = Blueprint('billing_pdf_lab_routes', __name__,
    url_prefix='/api/v1/platform/billing-diagnostics')
_workers = ThreadPoolExecutor(max_workers=2, thread_name_prefix='billing-pdf-lab')
_capacity = BoundedSemaphore(2)


@billing_pdf_lab_routes.before_request
def _require_platform_admin():
    if request.method == 'OPTIONS':
        return None
    user = getattr(g, 'current_user', None)
    if user is None:
        return error_response('Autenticação obrigatória.', 401)
    if not user.is_platform_admin:
        return error_response('Acesso restrito a administradores da plataforma.', 403)


@billing_pdf_lab_routes.post('/pdf')
def diagnose_pdf():
    uploaded = request.files.get('arquivo')
    if uploaded is None:
        return error_response('Envie um PDF no campo arquivo.', 400, code='PDF_REQUIRED')
    upload_started = perf_counter()
    filename = secure_filename(uploaded.filename or 'fatura.pdf') or 'fatura.pdf'
    try:
        document = _validate_pdf(uploaded)
    except InvoiceUploadError as exc:
        return error_response(str(exc), exc.status_code, code=exc.code)
    except Exception:
        return error_response('Falha técnica na validação do PDF.', 500,
                              code='PDF_VALIDATION_FAILED')
    finally:
        uploaded.close()
    upload_duration_ms = f'{(perf_counter() - upload_started) * 1000:.3f}'

    if not _capacity.acquire(blocking=False):
        return error_response('Laboratório ocupado; tente novamente.', 503, code='PDF_DIAGNOSTIC_BUSY')
    try:
        job = _workers.submit(analyze_pdf, document,
            sha256=hashlib.sha256(document).hexdigest(),
            filename=filename, size=len(document), upload_duration_ms=upload_duration_ms)
        job.add_done_callback(lambda unused: _capacity.release())
    except Exception:
        _capacity.release()
        return error_response('Falha técnica no diagnóstico do PDF.', 500,
                              code='PDF_DIAGNOSTIC_FAILED')
    try:
        result = job.result(timeout=current_app.config['BILLING_DIAGNOSTIC_TIMEOUT_SECONDS'])
    except TimeoutError:
        job.cancel()
        return error_response('Tempo limite do diagnóstico excedido.', 504,
                              code='PDF_DIAGNOSTIC_TIMEOUT')
    except Exception:
        return error_response('Falha técnica no diagnóstico do PDF.', 500,
                              code='PDF_DIAGNOSTIC_FAILED')
    return success_response(result, 'Diagnóstico concluído.')
