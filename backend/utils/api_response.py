from flask import jsonify


def success_response(data=None, message='OK', status_code=200):
    return jsonify({
        'success': True,
        'message': message,
        'data': data
    }), status_code


def error_response(message, status_code=400, details=None, code=None):
    payload = {'error': message}

    if details is not None:
        payload['details'] = details
    if code is not None:
        payload['code'] = code

    return jsonify(payload), status_code
