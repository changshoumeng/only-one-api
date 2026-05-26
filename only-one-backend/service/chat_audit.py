import json
from typing import Any, Optional

from utils.db_client import db_client
from utils.util import get_current_timestamp, snowflake


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _message_content_text(message: dict) -> str:
    content = message.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if 'text' in item:
                    parts.append(str(item['text']))
                elif 'image_url' in item:
                    parts.append(_json_dumps({'image_url': item['image_url']}))
            else:
                parts.append(str(item))
        return '\n\n'.join(parts)
    if content is None:
        return ''
    return str(content)


def _message_type(message: dict) -> str:
    role = message.get('role') or 'unknown'
    if message.get('tool_calls'):
        return 'assistant_tool_call'
    if role == 'tool':
        return 'tool_result'
    if isinstance(message.get('content'), list):
        return f'{role}_multimodal'
    return f'{role}_text'


async def insert_chat_message(
    history_id: int,
    seq: int,
    message: dict,
    *,
    token_count: Optional[int] = None,
    token_source: str = 'unknown',
    received_at: Optional[str] = None,
) -> int:
    message_id = snowflake.next_id()
    received_at = received_at or get_current_timestamp()[0:-4]
    data = {
        'id': message_id,
        'history_id': history_id,
        'seq': seq,
        'role': message.get('role'),
        'message_type': _message_type(message),
        'content_text': _message_content_text(message),
        'content_json': _json_dumps(message.get('content')) if 'content' in message else None,
        'token_count': token_count,
        'token_source': token_source,
        'received_at': received_at,
        'raw_json': _json_dumps(message),
        'create_time': received_at,
    }
    await db_client.insert('llm_chat_message', data)
    await insert_tool_calls(history_id, message_id, message, received_at=received_at)
    return message_id


async def insert_request_messages(history_id: int, messages: list, received_at: Optional[str] = None):
    for seq, message in enumerate(messages):
        await insert_chat_message(
            history_id,
            seq,
            message,
            token_source='legacy_unknown',
            received_at=received_at,
        )


async def insert_assistant_message(
    history_id: int,
    message: dict,
    seq: int,
    token_count: Optional[int],
    token_source: str,
    received_at: Optional[str] = None,
):
    await insert_chat_message(
        history_id,
        seq,
        message,
        token_count=token_count,
        token_source=token_source,
        received_at=received_at,
    )


async def insert_tool_calls(history_id: int, message_id: Optional[int], message: dict, received_at: Optional[str] = None):
    received_at = received_at or get_current_timestamp()[0:-4]
    for tool_call in message.get('tool_calls') or []:
        function = tool_call.get('function') or {}
        data = {
            'id': snowflake.next_id(),
            'history_id': history_id,
            'message_id': message_id,
            'tool_call_id': tool_call.get('id'),
            'tool_name': function.get('name'),
            'arguments_json': function.get('arguments'),
            'result_json': None,
            'status': 'requested',
            'created_at': received_at,
            'completed_at': None,
        }
        await db_client.insert('llm_tool_call', data)

    if message.get('role') == 'tool':
        data = {
            'id': snowflake.next_id(),
            'history_id': history_id,
            'message_id': message_id,
            'tool_call_id': message.get('tool_call_id'),
            'tool_name': message.get('name'),
            'arguments_json': None,
            'result_json': _json_dumps(message.get('content')),
            'status': 'completed',
            'created_at': received_at,
            'completed_at': received_at,
        }
        await db_client.insert('llm_tool_call', data)


async def insert_request_event(history_id: int, event_type: str, provider_name: str, payload: Optional[dict] = None):
    await db_client.insert('llm_request_event', {
        'id': snowflake.next_id(),
        'history_id': history_id,
        'event_type': event_type,
        'provider_name': provider_name,
        'payload_json': _json_dumps(payload or {}),
        'created_at': get_current_timestamp()[0:-4],
    })


async def update_history_status(
    history_id: int,
    *,
    finish_status: str,
    usage_source: Optional[str] = None,
    error_message: Optional[str] = None,
):
    data = {
        'finish_status': finish_status,
        'update_time': get_current_timestamp()[0:-4],
    }
    if usage_source is not None:
        data['usage_source'] = usage_source
    if error_message is not None:
        data['error_message'] = error_message
    await db_client.update('llm_chat_history', data, 'id = ?', [history_id])
