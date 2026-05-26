
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Request

from utils.util import require_auth, PaginationParams, get_page_params
from utils.db_client import db_client

router = APIRouter(prefix="/backend/chat", tags=["chat"])
_JSON_DEFAULT = object()

def _format_datetime(value):
    if not value:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return str(value)[:19]


def _format_price(value):
    number = float(value or 0)
    return f"{number:.6g}"


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value)[:19], '%Y-%m-%d %H:%M:%S')
    except Exception:
        return None


def _duration_seconds(start, end):
    start_time = _parse_datetime(start)
    end_time = _parse_datetime(end)
    if not start_time or not end_time:
        return None
    return int((end_time - start_time).total_seconds())


def _safe_json_loads(value, default=_JSON_DEFAULT):
    if default is _JSON_DEFAULT:
        default = {}
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _jsonable(value):
    return _safe_json_loads(json.dumps(value, ensure_ascii=False, default=str), value)


def _as_id(value):
    return str(value) if value is not None else None


def _safe_int(value):
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _prompt_preview(prompt, limit=60):
    text = str(prompt or '')
    return text if len(text) <= limit else f'{text[:limit]}...'


def _content_for_display(context_item):
    if 'content' in context_item and context_item['content']:
        if isinstance(context_item['content'], str) and '<think>' in context_item['content']:
            context_item['content'] = context_item['content'].replace('<think>', '\n## <think>\n').replace('</think>', '\n## </think>\n')

        # 处理多模态
        if isinstance(context_item['content'], list):
            context_list = []
            for obj in context_item['content']:
                if 'text' in obj:
                    context_list.append(obj['text'])
                elif 'image_url' in obj:
                    context_list.append(f'![image]({obj["image_url"]["url"]})')
            context_item['content'] = '\n\n\n'.join(context_list)

    elif 'tool_calls' in context_item:
        context_item['content'] = json.dumps(context_item['tool_calls'], ensure_ascii=False, indent=4)
    elif 'function' in context_item:
        context_item['role'] = 'function'
        context_item['content'] = json.dumps(context_item['function'], ensure_ascii=False, indent=4)

    return context_item


def _is_tool_definition(raw):
    return (
        isinstance(raw, dict)
        and raw.get('type') == 'function'
        and isinstance(raw.get('function'), dict)
        and not raw.get('role')
    )


def _message_type(raw, fallback='unknown_text'):
    role = raw.get('role') if isinstance(raw, dict) else None
    content = raw.get('content') if isinstance(raw, dict) else None
    if isinstance(raw, dict) and raw.get('tool_calls'):
        return 'assistant_tool_call'
    if role == 'tool':
        return 'tool_result'
    if isinstance(content, list):
        return f'{role or "unknown"}_multimodal'
    if role:
        return f'{role}_text'
    return fallback


def _content_text(raw, fallback=''):
    if fallback:
        return fallback
    if not isinstance(raw, dict):
        return ''
    content = raw.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and 'text' in item:
                parts.append(str(item['text']))
            elif isinstance(item, dict) and 'image_url' in item:
                parts.append(json.dumps({'image_url': item['image_url']}, ensure_ascii=False))
            else:
                parts.append(str(item))
        return '\n\n'.join(parts)
    if content is None:
        return ''
    return str(content)


def _history_summary(history, row_id=None, include_prompt_full=False):
    history_id = _as_id(history.get('id')) or ''
    input_price = _safe_float(history.get('input_price'))
    output_price = _safe_float(history.get('output_price'))
    total_price = input_price + output_price
    duration_seconds = _duration_seconds(history.get('create_time'), history.get('update_time'))
    prompt_full = str(history.get('prompt') or '')

    summary = {
        'history_id': history_id,
        'id': history_id,
        'row_id': row_id,
        'request_id': history.get('request_id'),
        'model_name': history.get('model_name'),
        'provider_name': history.get('provider_name'),
        'model_id': history.get('model_id'),
        'prompt_preview': _prompt_preview(prompt_full),
        'prompt': _prompt_preview(prompt_full),
        'finish_status': history.get('finish_status') or 'unknown',
        'usage_source': history.get('usage_source') or 'unknown',
        'prompt_tokens': _safe_int(history.get('prompt_tokens')),
        'completion_tokens': _safe_int(history.get('completion_tokens')),
        'input_price': input_price,
        'output_price': output_price,
        'total_price': total_price,
        'input_price_display': _format_price(input_price),
        'output_price_display': _format_price(output_price),
        'total_price_display': f'{_format_price(total_price)} 元',
        'duration_seconds': duration_seconds,
        'duration': f'{duration_seconds} s' if duration_seconds is not None else '未完成',
        'create_time': _format_datetime(history.get('create_time')),
        'update_time': _format_datetime(history.get('update_time')),
        'error_message': history.get('error_message'),
    }
    if include_prompt_full:
        summary['prompt_full'] = prompt_full
    return summary


def _raw_record(kind, label, source_table, source_id, seq, created_at, raw_json):
    record_id = f'{kind}:{source_id if source_id is not None else seq if seq is not None else label}'
    return {
        'id': record_id,
        'kind': kind,
        'label': label,
        'source_table': source_table,
        'source_id': _as_id(source_id),
        'seq': seq,
        'created_at': _format_datetime(created_at),
        'raw_json': _jsonable(raw_json),
    }


def _tool_definition_from_raw(raw, *, history_id, row=None, seq=None, received_at=None, source='llm_chat_message'):
    function = raw.get('function') or {}
    parameters = function.get('parameters')
    source_id = row.get('id') if row else None
    source_table = 'llm_chat_message' if source == 'llm_chat_message' else 'llm_chat_history.context'
    return {
        'id': _as_id(source_id),
        'history_id': _as_id(history_id) or '',
        'seq': row.get('seq') if row else seq,
        'tool_type': raw.get('type') or 'function',
        'tool_name': function.get('name'),
        'description': function.get('description') or '',
        'parameters_json': _jsonable(parameters),
        'raw_json': _jsonable(raw),
        'received_at': _format_datetime((row or {}).get('received_at') or received_at),
        'source': source,
        'raw_record_id': f'tool_definition:{source_id if source_id is not None else seq}',
        'source_table': source_table,
    }


def _message_from_row(message):
    raw = _safe_json_loads(message.get('raw_json'), {})
    if _is_tool_definition(raw):
        return None

    role = message.get('role') or (raw.get('role') if isinstance(raw, dict) else None) or 'unknown'
    message_type = message.get('message_type') or _message_type(raw)
    if message_type == 'unknown_text':
        message_type = _message_type(raw, message_type)

    item = {
        'id': _as_id(message.get('id')),
        'history_id': _as_id(message.get('history_id')) or '',
        'seq': message.get('seq'),
        'role': role,
        'message_type': message_type,
        'content': _content_text(raw, message.get('content_text') or ''),
        'content_json': _safe_json_loads(message.get('content_json'), None),
        'received_at': _format_datetime(message.get('received_at')),
        'token_count': message.get('token_count'),
        'token_source': message.get('token_source') or 'unknown',
        'tool_call_id': raw.get('tool_call_id') if isinstance(raw, dict) else None,
        'tool_name': raw.get('name') if isinstance(raw, dict) else None,
        'raw_record_id': f'message:{message.get("id")}',
    }
    if isinstance(raw, dict) and raw.get('tool_calls'):
        item['tool_calls'] = _jsonable(raw['tool_calls'])
    if isinstance(item.get('content'), str) and '<think>' in item['content']:
        item['content'] = item['content'].replace('<think>', '\n## <think>\n').replace('</think>', '\n## </think>\n')
    return item


def _message_from_legacy(raw, history, seq):
    item = {
        'id': None,
        'history_id': _as_id(history.get('id')) or '',
        'seq': seq,
        'role': raw.get('role') or 'unknown',
        'message_type': raw.get('message_type') or _message_type(raw),
        'content': _content_text(raw, raw.get('content') if isinstance(raw.get('content'), str) else ''),
        'content_json': _jsonable(raw.get('content')) if 'content' in raw else None,
        'received_at': _format_datetime(history.get('create_time')),
        'token_count': None,
        'token_source': 'legacy_unknown',
        'tool_call_id': raw.get('tool_call_id'),
        'tool_name': raw.get('name'),
        'raw_record_id': f'legacy_context:{seq}',
    }
    if raw.get('tool_calls'):
        item['tool_calls'] = _jsonable(raw['tool_calls'])
    return item


def _assistant_message_from_history(history, seq):
    content = history.get('answer') or '请求未完成或异常中断，暂无回复。'
    return {
        'id': None,
        'history_id': _as_id(history.get('id')) or '',
        'seq': seq,
        'role': 'assistant',
        'message_type': 'assistant_text',
        'content': content,
        'content_json': content,
        'received_at': _format_datetime(history.get('update_time')) or _format_datetime(history.get('create_time')),
        'token_count': history.get('completion_tokens'),
        'token_source': 'legacy_total_completion',
        'tool_call_id': None,
        'tool_name': None,
        'raw_record_id': 'legacy_answer:answer',
    }


async def _load_messages_and_tool_definitions(history):
    sql = """
        SELECT *
        FROM llm_chat_message
        WHERE history_id = ?
        ORDER BY seq ASC, id ASC
    """
    messages = await db_client.select(sql, [history['id']])

    message_views = []
    tool_definitions = []
    raw_records = []
    for message in messages:
        raw = _safe_json_loads(message.get('raw_json'), {})
        if _is_tool_definition(raw):
            tool_definitions.append(
                _tool_definition_from_raw(
                    raw,
                    history_id=history['id'],
                    row=message,
                    source='llm_chat_message',
                )
            )
            raw_records.append(
                _raw_record(
                    'tool_definition',
                    f'tool definition: {(raw.get("function") or {}).get("name") or "unknown"}',
                    'llm_chat_message',
                    message.get('id'),
                    message.get('seq'),
                    message.get('received_at'),
                    raw,
                )
            )
            continue

        view = _message_from_row(message)
        if view:
            message_views.append(view)
            raw_records.append(
                _raw_record(
                    'message',
                    f'message: {view["role"]}/{view["message_type"]}',
                    'llm_chat_message',
                    message.get('id'),
                    message.get('seq'),
                    message.get('received_at'),
                    raw,
                )
            )

    return message_views, tool_definitions, raw_records


async def _load_structured_messages(history):
    messages, _, _ = await _load_messages_and_tool_definitions(history)
    return messages


def _legacy_context(history):
    context = json.loads(history.get('context') or '[]')
    for context_item in context:
        context_item.setdefault('received_at', _format_datetime(history.get('create_time')))
        context_item.setdefault('token_count', None)
        context_item.setdefault('token_source', 'legacy_unknown')
        context_item.setdefault('message_type', context_item.get('role', 'unknown'))
        _content_for_display(context_item)

    assistant_item = {
        'role': 'assistant',
        'content': history.get('answer') or '请求未完成或异常中断，暂无回复。',
        'received_at': _format_datetime(history.get('update_time')) or _format_datetime(history.get('create_time')),
        'token_count': history.get('completion_tokens'),
        'token_source': 'legacy_total_completion',
        'message_type': 'assistant_text',
    }
    context.append(_content_for_display(assistant_item))
    return context


def _legacy_detail_parts(history):
    legacy_context = _safe_json_loads(history.get('context'), [])
    if not isinstance(legacy_context, list):
        legacy_context = []

    messages = []
    tool_definitions = []
    raw_records = []
    for seq, raw in enumerate(legacy_context):
        if not isinstance(raw, dict):
            raw = {'content': str(raw)}
        if _is_tool_definition(raw):
            tool_definitions.append(
                _tool_definition_from_raw(
                    raw,
                    history_id=history.get('id'),
                    seq=seq,
                    received_at=history.get('create_time'),
                    source='legacy_context',
                )
            )
        else:
            messages.append(_message_from_legacy(raw, history, seq))
        raw_records.append(
            _raw_record(
                'legacy_context',
                f'legacy context #{seq}',
                'llm_chat_history.context',
                history.get('id'),
                seq,
                history.get('create_time'),
                raw,
            )
        )

    assistant = _assistant_message_from_history(history, len(legacy_context))
    messages.append(assistant)
    raw_records.append(
        _raw_record(
            'legacy_answer',
            'legacy assistant answer',
            'llm_chat_history.answer',
            history.get('id'),
            assistant['seq'],
            history.get('update_time') or history.get('create_time'),
            {'role': 'assistant', 'content': assistant['content']},
        )
    )
    return messages, tool_definitions, raw_records


async def _load_tool_calls(history_id):
    sql = """
        SELECT *
        FROM llm_tool_call
        WHERE history_id = ?
        ORDER BY created_at ASC, id ASC
    """
    rows = await db_client.select(sql, [history_id])
    tool_calls = []
    raw_records = []
    for row in rows:
        view = {
            'id': _as_id(row.get('id')) or '',
            'history_id': _as_id(row.get('history_id')) or '',
            'message_id': _as_id(row.get('message_id')),
            'tool_call_id': row.get('tool_call_id'),
            'tool_name': row.get('tool_name'),
            'arguments_json': _safe_json_loads(row.get('arguments_json'), row.get('arguments_json')),
            'result_json': _safe_json_loads(row.get('result_json'), row.get('result_json')),
            'status': row.get('status') or 'unknown',
            'created_at': _format_datetime(row.get('created_at')),
            'completed_at': _format_datetime(row.get('completed_at')),
            'raw_record_id': f'tool_call:{row.get("id")}',
        }
        tool_calls.append(view)
        raw_records.append(
            _raw_record(
                'tool_call',
                f'tool call: {row.get("tool_name") or row.get("tool_call_id") or "unknown"}',
                'llm_tool_call',
                row.get('id'),
                None,
                row.get('created_at'),
                row,
            )
        )
    return tool_calls, raw_records


async def _load_events(history_id):
    sql = """
        SELECT *
        FROM llm_request_event
        WHERE history_id = ?
        ORDER BY created_at ASC, id ASC
    """
    rows = await db_client.select(sql, [history_id])
    events = []
    raw_records = []
    for row in rows:
        view = {
            'id': _as_id(row.get('id')) or '',
            'history_id': _as_id(row.get('history_id')) or '',
            'event_type': row.get('event_type') or 'unknown',
            'provider_name': row.get('provider_name'),
            'payload_json': _safe_json_loads(row.get('payload_json'), {}),
            'created_at': _format_datetime(row.get('created_at')),
            'raw_record_id': f'event:{row.get("id")}',
        }
        events.append(view)
        raw_records.append(
            _raw_record(
                'event',
                f'event: {view["event_type"]}',
                'llm_request_event',
                row.get('id'),
                None,
                row.get('created_at'),
                row,
            )
        )
    return events, raw_records


def _raw_availability():
    return {
        'persisted_records': True,
        'inbound_request': False,
        'normalized_request': False,
        'provider_outbound': False,
        'provider_response': False,
        'stream_chunks': False,
    }


def _snapshot_available(snapshot, key):
    return bool(snapshot and snapshot.get(key))


def _snapshot_availability(snapshot, persisted_records):
    return {
        'persisted_records': bool(persisted_records),
        'inbound_request': _snapshot_available(snapshot, 'inbound_json'),
        'normalized_request': _snapshot_available(snapshot, 'normalized_json'),
        'provider_outbound': _snapshot_available(snapshot, 'provider_outbound_json'),
        'provider_response': _snapshot_available(snapshot, 'provider_response_json'),
        'stream_chunks': _snapshot_available(snapshot, 'stream_chunks_json'),
    }


def _snapshot_redaction(snapshot):
    truncated_fields = _safe_json_loads((snapshot or {}).get('truncated_fields_json'), [])
    if not isinstance(truncated_fields, list):
        truncated_fields = []
    notes = []
    if not snapshot:
        notes.append('raw exchange was not captured for this history')
    return {
        'redaction_version': (snapshot or {}).get('redaction_version') or 'v1',
        'payload_bytes': _safe_int((snapshot or {}).get('payload_bytes')),
        'truncated': bool(truncated_fields) or (snapshot or {}).get('snapshot_status') == 'truncated',
        'truncated_fields': truncated_fields,
        'notes': notes,
    }


def _snapshot_meta(snapshot):
    if not snapshot:
        return []
    return [
        {
            'id': _as_id(snapshot.get('id')) or '',
            'history_id': _as_id(snapshot.get('history_id')) or '',
            'request_id': snapshot.get('request_id'),
            'snapshot_status': snapshot.get('snapshot_status') or 'captured',
            'redaction_version': snapshot.get('redaction_version') or 'v1',
            'created_at': _format_datetime(snapshot.get('created_at')),
            'updated_at': _format_datetime(snapshot.get('updated_at')),
        }
    ]


def _request_stage(snapshot):
    if _snapshot_available(snapshot, 'provider_outbound_json'):
        return 'provider_outbound'
    if _snapshot_available(snapshot, 'normalized_json'):
        return 'normalized'
    if _snapshot_available(snapshot, 'inbound_json'):
        return 'inbound'
    return 'unavailable'


def _response_stage(snapshot):
    if _snapshot_available(snapshot, 'provider_response_json'):
        response = _safe_json_loads(snapshot.get('provider_response_json'), {})
        if isinstance(response, dict) and response.get('http_status') and response.get('body'):
            return 'provider_error'
        return 'provider_response'
    if _snapshot_available(snapshot, 'stream_chunks_json'):
        return 'stream_summary'
    return 'unavailable'


def _request_json(snapshot):
    for key in ('provider_outbound_json', 'normalized_json', 'inbound_json'):
        if _snapshot_available(snapshot, key):
            return _safe_json_loads(snapshot.get(key), None)
    return None


def _response_json(snapshot):
    if _snapshot_available(snapshot, 'provider_response_json'):
        return _safe_json_loads(snapshot.get('provider_response_json'), None)
    if _snapshot_available(snapshot, 'stream_chunks_json'):
        return _safe_json_loads(snapshot.get('stream_chunks_json'), None)
    return None


async def _load_latest_snapshot(history_id):
    rows = await db_client.select(
        """
        SELECT *
        FROM llm_request_snapshot
        WHERE history_id = ?
        ORDER BY updated_at DESC, created_at DESC, id DESC
        LIMIT 1
        """,
        [history_id],
    )
    return rows[0] if rows else None


async def _load_persisted_raw_records(history):
    messages, tool_definitions, raw_records = await _load_messages_and_tool_definitions(history)
    raw_records.insert(
        0,
        _raw_record(
            'history',
            'history summary',
            'llm_chat_history',
            history.get('id'),
            None,
            history.get('create_time'),
            history,
        ),
    )
    if not messages and not tool_definitions:
        _, _, legacy_raw_records = _legacy_detail_parts(history)
        raw_records.extend(legacy_raw_records)
    tool_calls, tool_call_raw_records = await _load_tool_calls(history['id'])
    events, event_raw_records = await _load_events(history['id'])
    raw_records.extend(tool_call_raw_records)
    raw_records.extend(event_raw_records)
    return raw_records


@router.get("/chat-history")
@require_auth
async def chat_history(request: Request, params: PaginationParams = Depends(get_page_params)):
    sql = "SELECT * FROM llm_chat_history ORDER BY id DESC LIMIT ?,?"
    data_list = await db_client.select(sql, [(params.page - 1) * params.perPage, params.perPage])

    res = []
    for index, item in enumerate(data_list):
        row_id = index + 1 + (params.page - 1) * params.perPage
        res.append(_history_summary(item, row_id=row_id, include_prompt_full=False))

    sql = 'select count(1) as cou from llm_chat_history'
    total = await db_client.select(sql)
    total = total[0]['cou']

    data = {'status':0, 'msg':'', 'data':{'count':total, 'rows':res}}
    return data


@router.get("/chat-history/{history_id}/raw")
@require_auth
async def chat_history_raw(request: Request, history_id: str):
    history_rows = await db_client.select(
        "SELECT * FROM llm_chat_history WHERE id = ?",
        [history_id],
    )
    if not history_rows:
        return {'status': 1, 'msg': '对话不存在', 'data': {}}

    history = history_rows[0]
    snapshot = await _load_latest_snapshot(history['id'])
    persisted_records = await _load_persisted_raw_records(history)
    availability = _snapshot_availability(snapshot, persisted_records)
    data = {
        'history_id': _as_id(history.get('id')) or '',
        'request_id': (snapshot or {}).get('request_id') or history.get('request_id'),
        'request_stage': _request_stage(snapshot),
        'response_stage': _response_stage(snapshot),
        'request_json': _request_json(snapshot),
        'response_json': _response_json(snapshot),
        'availability': availability,
        'redaction': _snapshot_redaction(snapshot),
        'snapshots': _snapshot_meta(snapshot),
        'persisted_records': persisted_records,
    }
    return {'status': 0, 'msg': '', 'data': data}


@router.get("/chat-history/{history_id}")
@require_auth
async def chat_history_detail(request: Request, history_id: str):
    history_rows = await db_client.select(
        "SELECT * FROM llm_chat_history WHERE id = ?",
        [history_id],
    )
    if not history_rows:
        return {'status': 1, 'msg': '对话不存在', 'data': {}}

    history = history_rows[0]
    summary = _history_summary(history, include_prompt_full=True)
    messages, tool_definitions, raw_records = await _load_messages_and_tool_definitions(history)

    raw_records.insert(
        0,
        _raw_record(
            'history',
            'history summary',
            'llm_chat_history',
            history.get('id'),
            None,
            history.get('create_time'),
            history,
        ),
    )

    if not messages and not tool_definitions:
        messages, tool_definitions, legacy_raw_records = _legacy_detail_parts(history)
        raw_records.extend(legacy_raw_records)

    tool_calls, tool_call_raw_records = await _load_tool_calls(history['id'])
    events, event_raw_records = await _load_events(history['id'])
    raw_records.extend(tool_call_raw_records)
    raw_records.extend(event_raw_records)

    data = {
        'summary': summary,
        'messages': messages,
        'tool_definitions': tool_definitions,
        'tool_calls': tool_calls,
        'events': events,
        'raw_records': raw_records,
        'raw_available': _raw_availability(),
    }
    return {'status': 0, 'msg': '', 'data': data}
