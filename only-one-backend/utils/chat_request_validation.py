from fastapi.exceptions import HTTPException


def validate_chat_request_params(params: dict, model_exists):
    """Validate OpenAI-compatible chat/image params without mutating model routing state."""
    if 'model' not in params:
        raise HTTPException(status_code=400, detail='model params error!')
    if not model_exists(params['model']):
        raise HTTPException(status_code=500, detail='model params error!')

    if 'messages' not in params:
        raise HTTPException(status_code=400, detail='messages params error!')
    if not params['messages']:
        raise HTTPException(status_code=400, detail='messages params error!')
    if params.get('stream') is True and 'stream_options' not in params:
        params['stream_options'] = {'include_usage': True}

    if str(params.get('web_search', 'false')).lower() == 'true':
        params['tools'] = params.get('tools', []) + [{'type': 'web_search'}]
        del params['web_search']

    return params
