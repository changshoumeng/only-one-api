def is_openai_path(path: str) -> bool:
    return path in {
        '/v1/chat/completions',
        '/chat/completions',
        '/v1/images/edits',
        '/v1/images/generations',
        '/v1/models',
        '/models',
    }


def error_type_for_status(status_code: int) -> str:
    if status_code == 401:
        return 'authentication_error'
    if status_code == 403:
        return 'permission_error'
    if status_code == 404:
        return 'not_found_error'
    if 400 <= status_code < 500:
        return 'invalid_request_error'
    return 'server_error'


def openai_error_body(detail, status_code: int, code: str = None):
    message = detail
    if isinstance(detail, bytes):
        message = detail.decode('utf-8', errors='replace')
    elif not isinstance(detail, str):
        message = str(detail)

    return {
        'error': {
            'message': message,
            'type': error_type_for_status(status_code),
            'param': None,
            'code': code or status_code,
        }
    }


def build_models_payload(models_dict):
    seen = set()
    data = []
    for model_name, services in models_dict.items():
        if model_name in seen or not services:
            continue
        seen.add(model_name)
        data.append({
            'id': model_name,
            'object': 'model',
            'created': 0,
            'owned_by': getattr(services[0], 'provider_english_name', 'unknown'),
        })

    return {'object': 'list', 'data': data}
