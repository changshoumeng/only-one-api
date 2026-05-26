import json
import copy
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from utils.db_client import db_client
from utils.util import get_current_timestamp, snowflake


REDACTION_VERSION = 'v1'
REDACTED = '[REDACTED]'
DEFAULT_MAX_FIELD_CHARS = 64 * 1024
DEFAULT_MAX_TOTAL_CHARS = 2 * 1024 * 1024
SAFE_RESPONSE_HEADERS = {
    'content-type',
    'x-request-id',
    'x-ratelimit-limit-requests',
    'x-ratelimit-remaining-requests',
    'x-ratelimit-reset-requests',
    'retry-after',
}

_SECRET_KEY_PATTERN = re.compile(
    r'(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|cookie|session)',
    re.IGNORECASE,
)
_BEARER_PATTERN = re.compile(r'\bbearer\s+[A-Za-z0-9._~+/=-]+', re.IGNORECASE)
_API_KEY_VALUE_PATTERN = re.compile(r'\bsk-[A-Za-z0-9._-]{8,}\b')
_DATA_URI_PATTERN = re.compile(
    r'^data:(?P<mime>[-\w.+/]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$',
    re.IGNORECASE,
)


@dataclass
class SanitizedSnapshot:
    value: Any
    json_text: str
    redaction_version: str = REDACTION_VERSION
    payload_bytes: int = 0
    truncated_fields: list[str] = field(default_factory=list)
    truncated: bool = False
    redacted: bool = False


def _json_path(parent: str, key: str | int) -> str:
    if isinstance(key, int):
        return f'{parent}[{key}]'
    if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key):
        return f'{parent}.{key}'
    return f'{parent}[{json.dumps(key, ensure_ascii=False)}]'


def _base64_summary(value: str) -> str | None:
    match = _DATA_URI_PATTERN.match(value.strip())
    if not match:
        return None
    raw_data = re.sub(r'\s+', '', match.group('data'))
    approx_bytes = int(len(raw_data) * 3 / 4)
    return f'[BASE64_DATA {match.group("mime")} {approx_bytes} bytes]'


def _safe_non_json_summary(value: Any) -> dict[str, str]:
    return {'non_json_value': type(value).__name__}


def _sanitize_value(
    value: Any,
    *,
    key: str = '',
    path: str = '$',
    max_field_chars: int,
    truncated_fields: list[str],
) -> Any:
    if key and _SECRET_KEY_PATTERN.search(key):
        return REDACTED

    if isinstance(value, str):
        base64_summary = _base64_summary(value)
        if base64_summary:
            return base64_summary

        redacted = _BEARER_PATTERN.sub(REDACTED, value)
        redacted = _API_KEY_VALUE_PATTERN.sub(REDACTED, redacted)
        if len(redacted) > max_field_chars:
            truncated_fields.append(path)
            omitted = len(redacted) - max_field_chars
            return f'{redacted[:max_field_chars]}\n[TRUNCATED {omitted} chars]'
        return redacted

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    if isinstance(value, list):
        return [
            _sanitize_value(
                item,
                path=_json_path(path, index),
                max_field_chars=max_field_chars,
                truncated_fields=truncated_fields,
            )
            for index, item in enumerate(value)
        ]

    if isinstance(value, tuple):
        return [
            _sanitize_value(
                item,
                path=_json_path(path, index),
                max_field_chars=max_field_chars,
                truncated_fields=truncated_fields,
            )
            for index, item in enumerate(value)
        ]

    if isinstance(value, dict):
        safe = {}
        for entry_key, entry_value in value.items():
            safe_key = str(entry_key)
            safe[safe_key] = _sanitize_value(
                entry_value,
                key=safe_key,
                path=_json_path(path, safe_key),
                max_field_chars=max_field_chars,
                truncated_fields=truncated_fields,
            )
        return safe

    return _safe_non_json_summary(value)


def _truncate_total_payload(json_text: str, max_total_chars: int, truncated_fields: list[str]) -> tuple[str, bool]:
    if len(json_text) <= max_total_chars:
        return json_text, False
    truncated_fields.append('$')
    omitted = len(json_text) - max_total_chars
    return f'{json_text[:max_total_chars]}\n[TRUNCATED_PAYLOAD {omitted} chars]', True


def sanitize_snapshot_payload(
    payload: Any,
    *,
    max_field_chars: int = DEFAULT_MAX_FIELD_CHARS,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> SanitizedSnapshot:
    truncated_fields: list[str] = []
    safe_value = _sanitize_value(
        payload,
        path='$',
        max_field_chars=max_field_chars,
        truncated_fields=truncated_fields,
    )
    json_text = json.dumps(safe_value, ensure_ascii=False, default=str)
    json_text, total_truncated = _truncate_total_payload(
        json_text,
        max_total_chars,
        truncated_fields,
    )
    payload_bytes = len(json_text.encode('utf-8'))
    return SanitizedSnapshot(
        value=safe_value,
        json_text=json_text,
        payload_bytes=payload_bytes,
        truncated_fields=truncated_fields,
        truncated=bool(truncated_fields) or total_truncated,
        redacted=REDACTED in json_text,
    )


def build_request_audit_snapshot(inbound_json: Any, normalized_json: Any) -> dict[str, Any]:
    return {
        'inbound_json': copy.deepcopy(inbound_json),
        'normalized_json': copy.deepcopy(normalized_json),
    }


def _snapshot_status(snapshots: list[SanitizedSnapshot]) -> str:
    if any(snapshot.truncated for snapshot in snapshots):
        return 'truncated'
    if any(snapshot.redacted for snapshot in snapshots):
        return 'redacted'
    return 'captured'


async def insert_initial_snapshot(history_id: int, request_id: str | None, audit_snapshot: dict[str, Any] | None):
    if not audit_snapshot:
        return None

    inbound = sanitize_snapshot_payload(audit_snapshot.get('inbound_json'))
    normalized = sanitize_snapshot_payload(audit_snapshot.get('normalized_json'))
    snapshots = [inbound, normalized]
    now = get_current_timestamp()[0:-4]
    row = {
        'id': snowflake.next_id(),
        'history_id': history_id,
        'request_id': request_id,
        'inbound_json': inbound.json_text,
        'normalized_json': normalized.json_text,
        'provider_outbound_json': None,
        'provider_response_json': None,
        'response_headers_json': None,
        'stream_chunks_json': None,
        'snapshot_status': _snapshot_status(snapshots),
        'redaction_version': REDACTION_VERSION,
        'payload_bytes': sum(snapshot.payload_bytes for snapshot in snapshots),
        'truncated_fields_json': json.dumps(
            [field for snapshot in snapshots for field in snapshot.truncated_fields],
            ensure_ascii=False,
        ),
        'created_at': now,
        'updated_at': now,
    }
    try:
        await db_client.insert('llm_request_snapshot', row)
    except Exception as exc:
        logger.warning(f'failed to insert initial chat audit snapshot: {exc}')
        return None
    return row['id']


def safe_response_headers(headers: Any) -> dict[str, str]:
    if not headers:
        return {}
    return {
        str(key).lower(): str(value)
        for key, value in dict(headers).items()
        if str(key).lower() in SAFE_RESPONSE_HEADERS
    }


def parse_error_body(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return text


def _chunk_finish_reason(chunk: Any) -> Any:
    if not isinstance(chunk, dict):
        return None
    choices = chunk.get('choices')
    if isinstance(choices, list) and choices:
        return choices[0].get('finish_reason')
    return chunk.get('finish_reason')


def build_stream_chunk_summary(
    chunks: list[Any],
    *,
    max_chunks: int = 80,
    max_sample_chars: int = 1000,
) -> dict[str, Any]:
    summary_chunks = []
    for index, chunk in enumerate(chunks[:max_chunks], start=1):
        sample_text = json.dumps(chunk, ensure_ascii=False, default=str)
        if len(sample_text) > max_sample_chars:
            sample_text = f'{sample_text[:max_sample_chars]}\n[TRUNCATED {len(sample_text) - max_sample_chars} chars]'
        summary_chunks.append({
            'seq': index,
            'received_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'size': len(json.dumps(chunk, ensure_ascii=False, default=str).encode('utf-8')),
            'has_usage': bool(isinstance(chunk, dict) and chunk.get('usage')),
            'finish_reason': _chunk_finish_reason(chunk),
            'sample': parse_error_body(sample_text),
        })
    return {
        'stream': True,
        'chunk_count': len(chunks),
        'truncated': len(chunks) > max_chunks,
        'chunks': summary_chunks,
    }


async def record_provider_exchange(
    history_id: int,
    *,
    provider_outbound: Any = None,
    provider_response: Any = None,
    response_headers: Any = None,
    stream_chunks: Any = None,
    snapshot_status: str | None = None,
):
    data: dict[str, Any] = {
        'updated_at': get_current_timestamp()[0:-4],
    }
    sanitized_values = []
    if provider_outbound is not None:
        outbound = sanitize_snapshot_payload(provider_outbound)
        data['provider_outbound_json'] = outbound.json_text
        sanitized_values.append(outbound)
    if provider_response is not None:
        response = sanitize_snapshot_payload(provider_response)
        data['provider_response_json'] = response.json_text
        sanitized_values.append(response)
    if response_headers is not None:
        headers = sanitize_snapshot_payload(safe_response_headers(response_headers))
        data['response_headers_json'] = headers.json_text
        sanitized_values.append(headers)
    if stream_chunks is not None:
        chunks = sanitize_snapshot_payload(stream_chunks)
        data['stream_chunks_json'] = chunks.json_text
        sanitized_values.append(chunks)

    if sanitized_values:
        data['payload_bytes'] = sum(item.payload_bytes for item in sanitized_values)
        data['truncated_fields_json'] = json.dumps(
            [field for item in sanitized_values for field in item.truncated_fields],
            ensure_ascii=False,
        )
    data['snapshot_status'] = snapshot_status or _snapshot_status(sanitized_values)

    try:
        await db_client.update('llm_request_snapshot', data, 'history_id = ?', [history_id])
    except Exception as exc:
        logger.warning(f'failed to update chat audit snapshot: {exc}')
