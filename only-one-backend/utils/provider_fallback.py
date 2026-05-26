import json


def clone_request_params(params: dict) -> dict:
    return json.loads(json.dumps(params, ensure_ascii=False))


async def run_with_fallback(models, params, call_model):
    last_error = None
    for model in models:
        try:
            return await call_model(model, clone_request_params(params))
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError('no provider candidates available')


async def stream_with_fallback(models, params, stream_model, logger=None):
    last_error = None
    for index, model in enumerate(models):
        yielded_any = False
        try:
            async for chunk in stream_model(model, clone_request_params(params)):
                yielded_any = True
                yield chunk
            return
        except Exception as exc:
            last_error = exc
            if logger:
                logger.error(f"stream provider attempt {index + 1} failed: {exc}")
            if yielded_any or index == len(models) - 1:
                raise
            continue
    if last_error:
        raise last_error
