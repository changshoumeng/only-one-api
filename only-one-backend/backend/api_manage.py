import json
import shlex
import time
import string
import secrets
import uuid
from typing import Optional, Union

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator

from utils.util import snowflake, get_current_timestamp, require_auth, PaginationParams, get_page_params
from utils.db_client import db_client
from init import init_models

router = APIRouter(prefix="/backend/api-manage", tags=["api-manage"])


def parse_positive_int(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None

class ProviderBase(BaseModel):
    provider_name: str
    provider_english_name: str
    api_key: str
    base_url: str

    @field_validator('base_url')
    def validate_base_url(cls, value):
        if not value.startswith('http') and not value.startswith('https'):
            raise ValueError('base-url 必须是网址')
        return value

# 创建提供商
@router.post("/provider/create")
@require_auth
async def provider_create(request: Request, params: ProviderBase):

    # 判断提供商名称是否存在
    sql = 'select * from llm_provider where provider_name = ?'
    result = await db_client.select(sql, [params.provider_name])
    if result:
        return {"status": 1, "msg": "提供商名称已存在", "data": {}}

    data = {}
    data['id'] = snowflake.next_id()
    data['provider_name'] = params.provider_name
    data['provider_english_name'] = params.provider_english_name
    data['api_key'] = params.api_key
    data['base_url'] = params.base_url
    current_timestamp = get_current_timestamp()
    data['create_time'] = current_timestamp[:-4]
    data['update_time'] = current_timestamp[:-4]
    
    await db_client.insert('llm_provider', [data])
    await init_models()
    return {"status": 0, "msg": "创建成功", "data": {}}

# 获取提供商列表
@router.get("/provider/list")
@require_auth
async def provider_list(request: Request, params: PaginationParams = Depends(get_page_params)):

    sql = 'select * from llm_provider where is_delete=0 order by id desc limit ?,?'
    result = await db_client.select(sql, [(params.page - 1) * params.perPage, params.perPage])
    for i, item in enumerate(result):
        item['row_id'] = i + 1 + (params.page - 1) * params.perPage
        item['id'] = str(item['id'])
        item['create_time'] = item['create_time'].strftime('%Y-%m-%d %H:%M:%S')

    sql = 'select count(*) as cou from llm_provider where is_delete=0'
    total = await db_client.select(sql)
    total = total[0]['cou']

    data = {'status':0, 'msg':'', 'data':{'count':total, 'rows':result}}
    return data

@router.get("/provider/select")
@require_auth
async def provider_select(request: Request):

    sql = 'select provider_english_name from llm_provider where is_delete=0 order by id asc'
    result = await db_client.select(sql)
    options = []
    for item in result:
        options.append({'label':item['provider_english_name'], 'value':item['provider_english_name']})

    data = {'status':0, 'msg':'', 'data':options}
    return data

@router.get("/provider/delete")
@require_auth
async def provider_delete(request: Request):
    # 获取参数
    request_data = request.query_params._dict
    provider_id = parse_positive_int(request_data.get('id'))
    if not provider_id:
        return {"status": 1, "msg": "错误！", "data": {}}

    # 更新is_delete
    current_timestamp = get_current_timestamp()[:-4]
    sql = "update llm_provider set is_delete=1, update_time=? where id=?"
    await db_client.execute(sql, [current_timestamp, provider_id])

    sql = "update llm_model set is_delete=1, update_time=? where provider_english_name=(select provider_english_name from llm_provider where id=?)"
    await db_client.execute(sql, [current_timestamp, provider_id])

    await init_models()
    return {"status": 0, "msg": "删除成功", "data": {}}

# 更新提供商
@router.post("/provider/update")
@require_auth
async def provider_update(request: Request, params: ProviderBase):

    # 获取参数
    request_data = await request.json()
    provider_id = parse_positive_int(request_data.get('id'))
    if not provider_id:
        return {"status": 1, "msg": "错误！", "data": {}}
    
    current_timestamp = get_current_timestamp()[:-4]

    sql = (
        'update llm_provider set provider_name=?, provider_english_name=?, '
        'api_key=?, base_url=?, update_time=? where id=?'
    )
    await db_client.execute(sql, [
        params.provider_name,
        params.provider_english_name,
        params.api_key,
        params.base_url,
        current_timestamp,
        provider_id,
    ])
    await init_models()
    return {"status": 0, "msg": "更新成功", "data": {}}



class ModelBase(BaseModel):
    provider_english_name: str
    model_name: str
    model_id: str
    billing_unit: str
    input_unit_price: Union[str, int, float]
    output_unit_price: Union[str, int, float]
    default_params: Optional[str] = None

    @field_validator('input_unit_price')
    def validate_input_unit_price(cls, value):
        if isinstance(value, int) or isinstance(value, float):
            value = str(value)

        if not value:
            raise ValueError('输入单价不能为空')
        try:
            float(value)
        except:
            raise ValueError('输入单价必须为数字')
        return float(value)

    @field_validator('output_unit_price')
    def validate_output_unit_price(cls, value):
        if isinstance(value, int) or isinstance(value, float):
            value = str(value)

        if not value:
            raise ValueError('输出单价不能为空')
        try:
            float(value)
        except:
            raise ValueError('输出单价必须为数字')
        return float(value)

    @field_validator('default_params')
    def validate_default_params(cls, value):
        if value:
            value = value.strip()
            if not value:
                return None

            try:
                json.loads(value)
                return value
            except:
                raise ValueError('默认参数必须为JSON字符串')
        return None


class ModelTestRequest(BaseModel):
    id: int
    prompt: str = 'hi,你是谁,是什么模型？'
    temperature: float = 0.7
    max_tokens: int = 256

    @field_validator('id')
    def validate_id(cls, value):
        if int(value) <= 0:
            raise ValueError('模型ID必须大于0')
        return int(value)

    @field_validator('prompt')
    def validate_prompt(cls, value):
        if not value or not value.strip():
            raise ValueError('测试提示词不能为空')
        return value.strip()

    @field_validator('max_tokens')
    def validate_max_tokens(cls, value):
        if int(value) <= 0:
            raise ValueError('max_tokens必须大于0')
        return int(value)

    @field_validator('temperature')
    def validate_temperature(cls, value):
        return float(value)


MODEL_TEST_CHAT_PATH = '/v1/chat/completions'
MODEL_TEST_TIMEOUT = 30.0
MODEL_TEST_DEFAULT_STAGE = 'gateway_request'


def _mask_api_key(api_key: str) -> str:
    if not api_key:
        return ''
    if api_key.startswith('sk-') and len(api_key) > 10:
        return f"sk-****{api_key[-4:]}"
    if len(api_key) <= 8:
        return '*' * len(api_key)
    return f"{api_key[:4]}****{api_key[-4:]}"


def _build_model_test_url(request: Request) -> str:
    forwarded_proto = request.headers.get('x-forwarded-proto')
    forwarded_host = request.headers.get('x-forwarded-host')
    host = forwarded_host or request.headers.get('host')
    if forwarded_proto and host:
        return f'{forwarded_proto}://{host}{MODEL_TEST_CHAT_PATH}'
    return f"{str(request.base_url).rstrip('/')}{MODEL_TEST_CHAT_PATH}"


def _build_model_test_body(model_row, params: ModelTestRequest) -> dict:
    return {
        'model': model_row['model_id'],
        'messages': [
            {
                'role': 'user',
                'content': params.prompt,
            }
        ],
        'temperature': params.temperature,
        'max_tokens': params.max_tokens,
    }


def _build_curl_command(url: str, api_key: str, request_id: str, body: dict) -> str:
    payload = json.dumps(body, ensure_ascii=False, separators=(',', ':'))
    return ' \\\n  '.join(
        [
            f"curl -sS {shlex.quote(url)}",
            '-X POST',
            f"-H {shlex.quote(f'Authorization: Bearer {api_key}')}",
            f"-H {shlex.quote('Content-Type: application/json')}",
            f"-H {shlex.quote(f'X-Request-ID: {request_id}')}",
            f"--data-raw {shlex.quote(payload)}",
        ]
    )


def _build_model_test_request_payload(url: str, api_key: str, request_id: str, body: dict) -> dict:
    return {
        'url': url,
        'method': 'POST',
        'body': body,
        'curl': _build_curl_command(url, api_key, request_id, body),
        'curl_display': _build_curl_command(url, _mask_api_key(api_key), request_id, body),
    }


def _normalize_response_body(response: httpx.Response):
    try:
        return response.json()
    except Exception:
        return None


def _build_model_test_response(response: httpx.Response, started_at: float, request_id: str):
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    payload = _normalize_response_body(response)
    response_body = {
        'http_status': response.status_code,
        'request_id': response.headers.get('X-Request-ID') or request_id,
        'duration_ms': elapsed_ms,
        'content': '',
        'raw': payload if payload is not None else response.text,
    }

    if response.status_code in (401, 403):
        return {
            'test_status': 'auth_failed',
            'available': False,
            'stage': 'gateway_auth',
            'response': response_body,
            'error': {
                'code': 'AUTH_FAILED',
                'message': '网关密钥不可用，请到密钥管理确认 API Key 是否启用。',
            },
        }

    if response.status_code == 404:
        return {
            'test_status': 'model_not_found',
            'available': False,
            'stage': 'gateway_lookup',
            'response': response_body,
            'error': {
                'code': 'MODEL_NOT_FOUND',
                'message': '模型不存在或已删除。',
            },
        }

    if response.status_code >= 400:
        return {
            'test_status': 'upstream_failed',
            'available': False,
            'stage': 'provider_request',
            'response': response_body,
            'error': {
                'code': 'UPSTREAM_FAILED',
                'message': '上游模型调用失败，请检查 provider api-key、base-url 与模型 ID。',
            },
        }

    if not isinstance(payload, dict):
        return {
            'test_status': 'invalid_response',
            'available': False,
            'stage': 'response_parse',
            'response': response_body,
            'error': {
                'code': 'INVALID_RESPONSE',
                'message': '返回格式异常，未识别到 OpenAI 兼容响应。',
            },
        }

    choices = payload.get('choices')
    if not isinstance(choices, list) or not choices:
        return {
            'test_status': 'invalid_response',
            'available': False,
            'stage': 'response_parse',
            'response': response_body,
            'error': {
                'code': 'INVALID_RESPONSE',
                'message': '返回格式异常，未识别到 choices。',
            },
        }

    message = choices[0].get('message') if isinstance(choices[0], dict) else None
    if not isinstance(message, dict):
        return {
            'test_status': 'invalid_response',
            'available': False,
            'stage': 'response_parse',
            'response': response_body,
            'error': {
                'code': 'INVALID_RESPONSE',
                'message': '返回格式异常，未识别到 message。',
            },
        }

    content = message.get('content')
    if not isinstance(content, str) or not content.strip():
        response_body['raw'] = payload
        return {
            'test_status': 'invalid_response',
            'available': False,
            'stage': 'response_parse',
            'response': response_body,
            'error': {
                'code': 'INVALID_RESPONSE',
                'message': '模型返回成功，但未包含可展示的文本回复。',
            },
        }

    response_body['content'] = content
    response_body['raw'] = payload
    return {
        'test_status': 'success',
        'available': True,
        'stage': 'chat_completions',
        'response': response_body,
        'error': None,
    }


async def _get_model_test_key():
    sql = (
        'select api_key from llm_api_keys '
        'where is_use=1 and is_delete=0 '
        'order by api_key_id asc limit 1'
    )
    result = await db_client.select(sql)
    if not result:
        return None
    return result[0].get('api_key')


async def _call_model_test_gateway(url: str, api_key: str, request_id: str, body: dict):
    started_at = time.perf_counter()
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'X-Request-ID': request_id,
    }

    try:
        async with httpx.AsyncClient(timeout=MODEL_TEST_TIMEOUT) as client:
            response = await client.post(url, json=body, headers=headers)
    except httpx.TimeoutException:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            'test_status': 'timeout',
            'available': False,
            'stage': MODEL_TEST_DEFAULT_STAGE,
            'response': {
                'http_status': None,
                'request_id': request_id,
                'duration_ms': elapsed_ms,
                'content': '',
                'raw': None,
            },
            'error': {
                'code': 'TIMEOUT',
                'message': '测试超时，请检查 provider 网络、base-url 与模型响应时间。',
            },
        }
    except httpx.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            'test_status': 'upstream_failed',
            'available': False,
            'stage': MODEL_TEST_DEFAULT_STAGE,
            'response': {
                'http_status': None,
                'request_id': request_id,
                'duration_ms': elapsed_ms,
                'content': '',
                'raw': str(exc),
            },
            'error': {
                'code': 'UPSTREAM_FAILED',
                'message': '上游模型调用失败，请检查 provider api-key、base-url 与模型 ID。',
            },
        }

    return _build_model_test_response(response, started_at, request_id)


@router.post("/model/test")
@require_auth
async def model_test(request: Request, params: ModelTestRequest):
    request_id = str(uuid.uuid4())
    model_sql = (
        'select * from llm_model '
        'where id=? and is_delete=0'
    )
    result = await db_client.select(model_sql, [params.id])
    if not result:
        return {
            "status": 0,
            "msg": "",
            "data": {
                "test_status": "model_not_found",
                "available": False,
                "stage": "model_lookup",
                "model": {
                    "id": str(params.id),
                },
                "request": {
                    "url": _build_model_test_url(request),
                    "method": "POST",
                    "body": {
                        "model": "",
                        "messages": [{"role": "user", "content": params.prompt}],
                        "temperature": params.temperature,
                        "max_tokens": params.max_tokens,
                    },
                    "curl": "",
                    "curl_display": "",
                },
                "response": {
                    "http_status": None,
                    "request_id": request_id,
                    "duration_ms": 0,
                    "content": "",
                    "raw": None,
                },
                "error": {
                    "code": "MODEL_NOT_FOUND",
                    "message": "模型不存在或已删除。",
                },
                "tested_at": get_current_timestamp()[:-4],
            },
        }

    model_row = result[0]
    url = _build_model_test_url(request)
    body = _build_model_test_body(model_row, params)
    api_key = await _get_model_test_key()
    request_payload = _build_model_test_request_payload(url, api_key or '', request_id, body)

    if model_row.get('status') != 1:
        return {
            "status": 0,
            "msg": "",
            "data": {
                "test_status": "model_disabled",
                "available": False,
                "stage": "model_state",
                "model": {
                    "id": str(model_row.get('id')),
                    "provider_english_name": model_row.get('provider_english_name'),
                    "model_name": model_row.get('model_name'),
                    "model_id": model_row.get('model_id'),
                },
                "request": request_payload,
                "response": {
                    "http_status": None,
                    "request_id": request_id,
                    "duration_ms": 0,
                    "content": "",
                    "raw": None,
                },
                "error": {
                    "code": "MODEL_DISABLED",
                    "message": "模型已停用，请先启用后再测试。",
                },
                "tested_at": get_current_timestamp()[:-4],
            },
        }

    if not api_key:
        return {
            "status": 0,
            "msg": "",
            "data": {
                "test_status": "auth_failed",
                "available": False,
                "stage": "auth",
                "model": {
                    "id": str(model_row.get('id')),
                    "provider_english_name": model_row.get('provider_english_name'),
                    "model_name": model_row.get('model_name'),
                    "model_id": model_row.get('model_id'),
                },
                "request": _build_model_test_request_payload(url, '', request_id, body),
                "response": {
                    "http_status": None,
                    "request_id": request_id,
                    "duration_ms": 0,
                    "content": "",
                    "raw": None,
                },
                "error": {
                    "code": "AUTH_FAILED",
                    "message": "网关密钥不可用，请到密钥管理创建或启用 API Key。",
                },
                "tested_at": get_current_timestamp()[:-4],
            },
        }

    test_result = await _call_model_test_gateway(url, api_key, request_id, body)
    return {
        "status": 0,
        "msg": "",
        "data": {
            **test_result,
            "model": {
                "id": str(model_row.get('id')),
                "provider_english_name": model_row.get('provider_english_name'),
                "model_name": model_row.get('model_name'),
                "model_id": model_row.get('model_id'),
            },
            "request": request_payload,
            "tested_at": get_current_timestamp()[:-4],
        },
    }

@router.post("/model/create")
@require_auth
async def model_create(request: Request, params: ModelBase):

    data = {}
    data['id'] = snowflake.next_id()
    data['provider_english_name'] = params.provider_english_name
    data['model_name'] = params.model_name
    data['model_id'] = params.model_id
    data['billing_unit'] = params.billing_unit
    data['input_unit_price'] = params.input_unit_price
    data['output_unit_price'] = params.output_unit_price
    # 统一到千token
    if data['billing_unit'] == 'per_million_tokens':
        data['input_unit_price'] /= 1000
        data['output_unit_price'] /= 1000

    data['default_params'] = params.default_params
    data['status'] = 1
    current_timestamp = get_current_timestamp()
    data['create_time'] = current_timestamp[:-4]
    data['update_time'] = current_timestamp[:-4]
    
    await db_client.insert('llm_model', data)
    await init_models()
    return {"status": 0, "msg": "创建成功", "data": {}}


@router.get("/model/list")
@require_auth
async def model_list(request: Request, params: PaginationParams = Depends(get_page_params)):

    sql = 'select * from llm_model where is_delete=0 order by id desc limit ?,?'
    result = await db_client.select(sql, [(params.page - 1) * params.perPage, params.perPage])
    for i, item in enumerate(result):
        item['row_id'] = i + 1 + (params.page - 1) * params.perPage
        item['id'] = str(item['id'])
        item['status'] = True if item['status'] == 1 else False
        item['create_time'] = item['create_time'].strftime('%Y-%m-%d %H:%M:%S')
        # 准备百万token的单价 和千token的单价
        item['input_unit_price_thousand'] = item['input_unit_price']
        item['output_unit_price_thousand'] = item['output_unit_price']
        item['input_unit_price_million'] = item['input_unit_price'] * 1000
        item['output_unit_price_million'] = item['output_unit_price'] * 1000
        if item['billing_unit'] == 'per_million_tokens':
            item['input_unit_price'] *= 1000
            item['output_unit_price'] *= 1000

    sql = 'select count(*) as cou from llm_model where is_delete=0'
    total = await db_client.select(sql)
    total = total[0]['cou']

    data = {'status':0, 'msg':'', 'data':{'count':total, 'rows':result}}
    return data


@router.post("/model/update")
@require_auth
async def model_update(request: Request, params: ModelBase):
    # 获取参数
    request_data = await request.json()
    model_id = parse_positive_int(request_data.get('id'))
    if not model_id:
        return {"status": 1, "msg": "错误！", "data": {}}

    status = 0 if not request_data.get('status', None) else 1
    current_timestamp = get_current_timestamp()[:-4]

    # 统一到千token
    if params.billing_unit == 'per_million_tokens':
        params.input_unit_price /= 1000
        params.output_unit_price /= 1000

    data = {}
    data['provider_english_name'] = params.provider_english_name
    data['model_name'] = params.model_name
    data['model_id'] = params.model_id
    data['billing_unit'] = params.billing_unit
    data['input_unit_price'] = params.input_unit_price
    data['output_unit_price'] = params.output_unit_price
    data['default_params'] = params.default_params
    data['status'] = status
    data['update_time'] = current_timestamp

    await db_client.update('llm_model', data, 'id = ?', [model_id])
    
    await init_models()
    return {"status": 0, "msg": "修改成功", "data": {}}


@router.get("/model/update-status")
@require_auth
async def model_update_status(request: Request):
    # 获取参数
    request_data = request.query_params._dict
    model_id = parse_positive_int(request_data.get('id'))
    if not model_id:
        return {"status": 1, "msg": "错误！", "data": {}}

    # 查询模型状态
    sql = "select status from llm_model where id=?"
    result = await db_client.select(sql, [model_id])
    if not result:
        return {"status": 1, "msg": "模型不存在！", "data": {}}

    status = 0 if result[0]['status'] == 1 else 1
    current_timestamp = get_current_timestamp()[:-4]

    # 更新模型状态
    sql = "update llm_model set status=?, update_time=? where id=?"
    await db_client.execute(sql, [status, current_timestamp, model_id])

    await init_models()
    return {"status": 0, "msg": "修改成功", "data": {}}

@router.get("/model/delete")
@require_auth
async def model_delete(request: Request):
    # 获取参数
    request_data = request.query_params._dict
    model_id = parse_positive_int(request_data.get('id'))
    if not model_id:
        return {"status": 1, "msg": "错误！", "data": {}}

    # 更新is_delete
    current_timestamp = get_current_timestamp()[:-4]
    sql = "update llm_model set is_delete=1, update_time=? where id=?"
    await db_client.execute(sql, [current_timestamp, model_id])

    await init_models()
    return {"status": 0, "msg": "删除成功", "data": {}}


@router.get("/key/list")
@require_auth
async def key_list(request: Request, params: PaginationParams = Depends(get_page_params)):

    sql = 'select * from llm_api_keys where is_delete=0 order by api_key_id desc limit ?,?'
    result = await db_client.select(sql, [(params.page - 1) * params.perPage, params.perPage])
    for i, item in enumerate(result):
        item['row_id'] = i + 1 + (params.page - 1) * params.perPage
        item['id'] = str(item['api_key_id'])
        item['status'] = True if item['is_use'] == 1 else False
        item['create_time'] = item['create_time'].strftime('%Y-%m-%d %H:%M:%S')

    sql = 'select count(*) as cou from llm_api_keys where is_delete=0'
    total = await db_client.select(sql)
    total = total[0]['cou']

    data = {'status':0, 'msg':'', 'data':{'count':total, 'rows':result}}
    return data

@router.get("/key/create")
@require_auth
async def key_create(request: Request):
    # 定义密钥的字符集，包括字母和数字
    alphabet = string.ascii_letters + string.digits

    # 使用 secrets.choice 从字符集中随机选择字符
    length = 32
    api_key = ''.join(secrets.choice(alphabet) for _ in range(length))
    api_key = f"sk-{api_key}"

    key = {}
    key['api_key'] = api_key

    await db_client.insert('llm_api_keys', key)

    data = {'status':0, 'msg':'', 'data':{}}
    return data


@router.get("/key/update-status")
@require_auth
async def key_update_status(request: Request):
    # 获取参数
    request_data = request.query_params._dict
    api_key_id = parse_positive_int(request_data.get('id'))
    if not api_key_id:
        return {"status": 1, "msg": "错误！", "data": {}}

    # 查询模型状态
    sql = "select is_use from llm_api_keys where api_key_id=?"
    result = await db_client.select(sql, [api_key_id])
    if not result:
        return {"status": 1, "msg": "密钥不存在！", "data": {}}

    status = 0 if result[0]['is_use'] == 1 else 1
    current_timestamp = get_current_timestamp()[:-4]

    # 更新模型状态
    sql = "update llm_api_keys set is_use=?, update_time=? where api_key_id=?"
    await db_client.execute(sql, [status, current_timestamp, api_key_id])

    return {"status": 0, "msg": "修改成功", "data": {}}

@router.post("/key/update-remark")
@require_auth
async def key_update_remark(request: Request):
    # 获取参数
    request_data = await request.json()
    api_key_id = parse_positive_int(request_data.get('id'))
    if not api_key_id:
        return {"status": 1, "msg": "错误！", "data": {}}
    if not request_data.get('remark', None):
        request_data['remark'] = ''


    current_timestamp = get_current_timestamp()[:-4]

    # 更新模型状态
    sql = "update llm_api_keys set remark=?, update_time=? where api_key_id=?"
    await db_client.execute(sql, [request_data['remark'], current_timestamp, api_key_id])

    return {"status": 0, "msg": "修改成功", "data": {}}

@router.get("/key/delete")
@require_auth
async def key_delete(request: Request):
    # 获取参数
    request_data = request.query_params._dict
    api_key_id = parse_positive_int(request_data.get('id'))
    if not api_key_id:
        return {"status": 1, "msg": "错误！", "data": {}}

    # 更新is_delete
    current_timestamp = get_current_timestamp()[:-4]
    sql = "update llm_api_keys set is_delete=1, update_time=? where api_key_id=?"
    await db_client.execute(sql, [current_timestamp, api_key_id])

    return {"status": 0, "msg": "删除成功", "data": {}}
