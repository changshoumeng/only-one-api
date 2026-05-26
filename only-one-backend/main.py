import os
import asyncio
import json
import traceback
import base64
import uuid
from contextlib import asynccontextmanager

from loguru import logger
current_file_path = os.path.abspath(__file__)
log_file = os.path.join(os.path.dirname(current_file_path), 'logs', 'personal_llm_{time:YYYY-MM-DD}.log')
logger.add(
    log_file,  # 按日期命名的日志文件
    rotation="00:00",              # 每天午夜轮转
    retention="10 days",           # 保留10天的日志
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}",
    level="INFO"
)


# 导入FastAPI
import uvicorn
from fastapi import FastAPI, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.exception_handlers import http_exception_handler as fastapi_http_exception_handler
from fastapi.responses import JSONResponse
from pydantic_core import ValidationError

from init import MODELS_OBJ, init_db, init_models, get_model, get_model_candidates, has_model
from config import settings
from utils.db_client import db_client
from utils.chat_request_validation import validate_chat_request_params
from utils.openai_contract import build_models_payload, is_openai_path, openai_error_body
from utils.provider_fallback import run_with_fallback, stream_with_fallback
from service.chat_audit_snapshot import build_request_audit_snapshot
from backend.backend_api import backend_router
from backend.llm_usage import router as llm_usage_router
from backend.api_manage import router as api_router
from backend.chat import router as chat_router


async def init_app():
    # 初始化数据库
    await init_db()
    # 初始化模型
    await init_models()


@asynccontextmanager
async def lifespan(app):
    await init_app()
    yield



# 创建FastAPI应用实例
app = FastAPI(
    docs_url=None,      # 禁用 Swagger UI
    redoc_url=None,     # 禁用 ReDoc
    openapi_url=None,   # 禁用 OpenAPI JSON
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境不要用 *
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    # 可选参数
    session_cookie="session",
    max_age=60*60*24,  # 1小时
    same_site="lax",
    https_only=settings.SESSION_HTTPS_ONLY
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=settings.STATIC_PATH), name="static1")
if os.path.isdir(os.path.join(settings.FRONTEND_DIST_PATH, 'assets')):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(settings.FRONTEND_DIST_PATH, 'assets')),
        name="frontend-assets",
    )
if os.path.isdir(os.path.join(settings.FRONTEND_DIST_PATH, 'images')):
    app.mount(
        "/images",
        StaticFiles(directory=os.path.join(settings.FRONTEND_DIST_PATH, 'images')),
        name="frontend-images",
    )

# 挂载后端路由
app.include_router(backend_router)
app.include_router(llm_usage_router)
app.include_router(api_router)
app.include_router(chat_router)



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """自定义验证错误处理器"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error['loc']),
            "message": str(error['ctx']['error']) if 'ctx' in error else '',
            "type": error['type']
        })

    return JSONResponse(
        status_code=200,
        content={"status": 1, "msg": errors[0]['message']}
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler2(request, exc):
    """自定义验证错误处理器"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error['loc']),
            "message": str(error['ctx']['error']) if 'ctx' in error else '',
            "type": error['type']
        })

    return JSONResponse(
        status_code=200,
        content={"status": 1, "msg": errors[0]['message']}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if is_openai_path(request.url.path):
        return JSONResponse(
            status_code=exc.status_code,
            content=openai_error_body(exc.detail, exc.status_code),
        )

    return await fastapi_http_exception_handler(request, exc)


async def chat_stream(model, params):
    # 判断是否使用response接口
    is_use_response_interface = False
    for item in params.get('tools', []):
        if item['type'] == 'web_search':
            is_use_response_interface = True
            break

    if is_use_response_interface:
        async for chunk in model.chat_stream_response(params):
            ## sse返回数据
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    else:
        async for chunk in model.chat_stream(params):
            ## sse返回数据
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

    # 完成
    yield "data: [DONE]\n\n"


async def chat_stream_with_fallback(models, params):
    async for chunk in stream_with_fallback(models, params, chat_stream, logger):
        yield chunk


async def chat_with_fallback(models, params):
    return await run_with_fallback(models, params, lambda model, attempt_req: model.chat(attempt_req))


# 校验api key是否存在
async def check_api_key(api_key: str):
    """校验api key是否存在"""
    if not api_key:
        raise HTTPException(status_code=401, detail='api key error!')

    api_key = api_key.replace('Bearer ', '')
    if not api_key or not api_key.startswith('sk-'):
        raise HTTPException(status_code=401, detail='api key error!')

    sql = "SELECT api_key_id FROM llm_api_keys WHERE api_key = ? and is_use = 1 and is_delete = 0"
    result = await db_client.select(sql, [api_key])
    if not result:
        raise HTTPException(status_code=401, detail='api key error!')

    return result[0]['api_key_id']

# 参数校验
def validate_chat_params(params: dict):
    """校验chat参数"""
    return validate_chat_request_params(params, has_model)


# 定义路由和视图函数
@app.post('/v1/chat/completions')
@app.post('/chat/completions')
async def chat_completions(request: Request):
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    # 校验key
    api_key = request.headers.get('Authorization')
    api_key_id = await check_api_key(api_key)

    # 接收请求体
    req = await request.json()
    inbound_req = json.loads(json.dumps(req, ensure_ascii=False))
    # 校验参数
    req = validate_chat_params(req)
    req['api_key_id'] = api_key_id
    req['request_id'] = request_id
    req['_audit_snapshot'] = build_request_audit_snapshot(inbound_req, req)

    # 1. 获取模型
    models = get_model_candidates(req['model'])
    del req['model']

    # 2. 判断是否是流式
    if req.get('stream', False):
        # 流式
        return StreamingResponse(chat_stream_with_fallback(models, req), media_type="text/event-stream", headers={'X-Request-ID': request_id})
    else:
        # 非流式
        try:
            answer = await chat_with_fallback(models, req)
        except Exception as e:
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
        if isinstance(answer, dict):
            answer.setdefault('request_id', request_id)
        return JSONResponse(content=answer, headers={'X-Request-ID': request_id})


@app.get('/v1/models')
@app.get('/models')
async def list_models(request: Request):
    api_key = request.headers.get('Authorization')
    await check_api_key(api_key)

    return build_models_payload(MODELS_OBJ['models_dict'])


@app.get('/health')
async def health():
    db_ok = True
    db_error = ''
    try:
        await db_client.select('SELECT 1')
    except Exception as e:
        db_ok = False
        db_error = str(e)

    models_count = len(MODELS_OBJ.get('models_dict', {}))
    status = 'ok' if db_ok and models_count > 0 else 'degraded'
    return {
        'status': status,
        'database': {'ok': db_ok, 'error': db_error},
        'models': {'count': models_count},
    }


async def img_params_process(img_params: list):
    """处理图片参数"""
    params = {}
    content = []
    images = []
    for item in img_params:
        if item[0] == 'prompt':
            content.append({'type': 'text', 'text': item[1]})
        elif 'image' in item[0]:
            if isinstance(item[1], list) or isinstance(item[1], str):
                if isinstance(item[1], str):
                    item[1] = [item[1]]
                for img in item[1]:
                    images.append({'type': 'image_url', 'image_url': {'url': img}})
            else:
                contents = await item[1].read()
        
                # 2. 将二进制数据转换为 Base64 编码的 bytes
                base64_bytes = base64.b64encode(contents)
                
                # 3. 将 bytes 转换为 utf-8 字符串
                base64_string = base64_bytes.decode("utf-8")
                
                # (可选) 构造 Data URI 格式，方便前端直接展示
                # 格式为：data:<mime_type>;base64,<data>
                mime_type = item[1].content_type
                full_base64_str = f"data:{mime_type};base64,{base64_string}"
                images.append({'type': 'image_url', 'image_url': {'url': full_base64_str}})
        else:
            params[item[0]] = item[1]
    
    content.extend(images)
    params['messages'] = [{'role': 'user', 'content': content}]

    return params

# 图片编辑和生成
@app.post('/v1/images/edits')
@app.post('/v1/images/generations')
async def chat_completions(request: Request):
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    # 校验key
    api_key = request.headers.get('Authorization')
    api_key_id = await check_api_key(api_key)

    content_type = request.headers.get('Content-Type', '')

    # 接收请求体
    if 'multipart/form-data' in content_type:
        # 多部分表单数据
        img_params = await request.form()
        req = await img_params_process(img_params._list)
    else:
        img_params = await request.json()
        req = await img_params_process([(k, v) for k, v in img_params.items()])

    # 校验参数
    req = validate_chat_params(req)
    req['api_key_id'] = api_key_id
    req['request_id'] = request_id

    # 1. 获取模型
    models = get_model_candidates(req['model'])
    del req['model']

    # 2. 判断是否是流式
    if req.get('stream', False):
        # 流式
        return StreamingResponse(chat_stream_with_fallback(models, req), media_type="text/event-stream", headers={'X-Request-ID': request_id})
    else:
        # 非流式
        try:
            answer = await chat_with_fallback(models, req)
        except Exception as e:
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))
        if isinstance(answer, dict):
            answer.setdefault('request_id', request_id)
        return JSONResponse(content=answer, headers={'X-Request-ID': request_id})


def frontend_index_response():
    index_path = os.path.join(settings.FRONTEND_DIST_PATH, 'index.html')
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=503, detail='Frontend dist is not built')
    return FileResponse(index_path)


def frontend_dist_file_response(path: str):
    dist_root = os.path.abspath(settings.FRONTEND_DIST_PATH)
    file_path = os.path.abspath(os.path.join(dist_root, path))
    if not file_path.startswith(dist_root + os.sep):
        return None
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return None


@app.get('/')
async def frontend_root():
    return frontend_index_response()


@app.get('/{path:path}')
async def frontend_spa(path: str):
    reserved_prefixes = ('backend/', 'v1/', 'static/', 'assets/', 'images/')
    reserved_paths = {'health', 'models', 'chat/completions'}
    if path in reserved_paths or path.startswith(reserved_prefixes):
        raise HTTPException(status_code=404, detail='Not Found')
    static_response = frontend_dist_file_response(path)
    if static_response:
        return static_response
    return frontend_index_response()



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2321)
