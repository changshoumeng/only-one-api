import json
import time
import copy

import httpx
from fastapi.exceptions import HTTPException
from utils.util import snowflake, get_current_timestamp, save_base64_image
from utils.db_client import db_client
from utils.logger import Logger
from config import settings
from service.chat_audit import insert_assistant_message, insert_request_event, insert_request_messages, update_history_status
from service.chat_audit_snapshot import (
    build_stream_chunk_summary,
    insert_initial_snapshot,
    parse_error_body,
    record_provider_exchange,
    safe_response_headers,
)

# 供应商模型接口基类
class LLMService(object):

    def __init__(self, id, base_url, model_id, api_key, provider_english_name, model_name, input_unit_price, output_unit_price, default_params):
        self.id = id
        self.base_url_response = base_url + '/responses' if base_url[-1] != '/' else base_url + 'responses'
        self.chat_url = base_url + '/chat/completions' if base_url[-1] != '/' else base_url + 'chat/completions'
        self.base_url = base_url if base_url[-1] != '/' else base_url[:-1]
        self.model_id = model_id
        self.model_name = model_name
        self.key = api_key
        self.provider_english_name = provider_english_name
        self.input_unit_price = input_unit_price
        self.output_unit_price = output_unit_price
        self.default_params = json.loads(default_params) if default_params else {}

        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.key
        }

        self.stream_headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.key,
            "Accept": "text/event-stream",  # 表明客户端接受事件流
            "Cache-Control": "no-cache",  # 禁用缓存
            "Connection": "keep-alive"  # 保持长连接
        }

        if 'midea.com' in base_url.lower():
            self.headers['AIGC-USER'] = 'zhangtao442'
            self.stream_headers['AIGC-USER'] = 'zhangtao442'

    async def create_history(self, params):

        if self.key == 'test':
            raise HTTPException(status_code=403, detail=f'请在后台设置{self.provider_english_name}的API Key')

        history = {}
        history['id'] = snowflake.next_id()
        audit_snapshot = params.pop('_audit_snapshot', None)
        context = await self.construct_db_context(params)
        history['context'] = json.dumps(context, ensure_ascii=False)
        history['request_id'] = params.pop('request_id', None)
        history['finish_status'] = 'running'
        history['usage_source'] = 'unknown'

        if isinstance(params['messages'][-1]['content'], list):
            prompt = [item['text'] for item in params['messages'][-1]['content'] if item['type'] == 'text']
            prompt = '\n'.join(prompt)
        else:
            prompt = params['messages'][-1]['content']
        history['prompt'] = prompt
        history['provider_name'] = self.provider_english_name
        history['model_name'] = self.model_name
        history['model_id'] = self.model_id
        history['api_key_id'] = params['api_key_id']
        del params['api_key_id']

        current_timestamp = get_current_timestamp()
        history['create_time'] = current_timestamp[0:-4]
        history['create_day'] = current_timestamp[0:10]
        history['create_month'] = current_timestamp[0:7]
        history['create_year'] = current_timestamp[0:4]

        await db_client.insert('llm_chat_history', history)
        await insert_request_messages(history['id'], context, received_at=history['create_time'])
        await insert_request_event(history['id'], 'request_started', self.provider_english_name, {
            'model_id': self.model_id,
            'model_name': self.model_name,
            'request_id': history.get('request_id'),
        })
        await insert_initial_snapshot(history['id'], history.get('request_id'), audit_snapshot)
        return history

    def get_usage_source(self, response):
        if response.get('usage_source'):
            return response['usage_source']
        return 'provider' if response.get('usage') else 'unknown'

    async def update_tokens(self, history, response):
        # 更新tokens
        reasoning_content = response['choices'][0]['message'].get('reasoning_content', '')
        if reasoning_content:
            reasoning_content = f'<think>\n{reasoning_content}\n</think>\n'
        else:
            reasoning_content = ''

        update_data = {}
        usage_source = self.get_usage_source(response)
        if response['usage']:
            update_data['completion_tokens'] = response['usage']['completion_tokens']
            update_data['prompt_tokens'] = response['usage']['prompt_tokens']
            update_data['input_price'] = self.input_unit_price * (response['usage']['prompt_tokens'] / 1000)
            update_data['output_price'] = self.output_unit_price * (response['usage']['completion_tokens'] / 1000)
        else:
            update_data['completion_tokens'] = 0
            update_data['prompt_tokens'] = 0
            update_data['input_price'] = 0
            update_data['output_price'] = 0

        if not response['choices'][0]['message']['content']:
            response['choices'][0]['message']['content'] = ''
        update_data['answer'] = reasoning_content + response['choices'][0]['message']['content']
        # tool calls
        if 'tool_calls' in response['choices'][0]['message']:
            update_data['answer'] += json.dumps(response['choices'][0]['message']['tool_calls'], ensure_ascii=False, indent=4)
        current_timestamp = get_current_timestamp()
        update_data['update_time'] = current_timestamp[0:-4]
        update_data['finish_status'] = 'completed'
        update_data['usage_source'] = usage_source

        await db_client.update('llm_chat_history', update_data, 'id = ?', [history['id']])
        assistant_message = response['choices'][0]['message']
        if reasoning_content and assistant_message.get('content'):
            assistant_message = dict(assistant_message)
            assistant_message['content'] = reasoning_content + assistant_message['content']
        await insert_assistant_message(
            history['id'],
            assistant_message,
            len(json.loads(history.get('context') or '[]')),
            update_data['completion_tokens'],
            usage_source,
            received_at=update_data['update_time'],
        )
        await insert_request_event(history['id'], 'request_completed', self.provider_english_name, {
            'usage': response.get('usage'),
            'usage_source': usage_source,
        })


    async def chat(self, params):
        id = params.get('id', '')
        if id:
            del params['id']
        else:
            id = snowflake.next_id()

        history = await self.create_history(params)
        logger = Logger(self.model_name, id)
        logger.info(f"chat start")

        try:
            # httpx异步请求
            params['model'] = self.model_id
            # 根据不同的供应商参数进行个性化处理
            await self.handle_params(params)
            if self.default_params: # 合并默认参数
                for key, value in self.default_params.items():
                    if key not in params:
                        params[key] = value
            await record_provider_exchange(
                history['id'],
                provider_outbound=copy.deepcopy(params),
                snapshot_status='captured',
            )

            async with httpx.AsyncClient(**settings.HTTPX_PARAMS) as client:
                response = await client.post(self.chat_url, json=params, headers=self.headers, timeout=600)
                if response.status_code != 200:
                    # 先读取响应内容
                    error_content = await response.aread()
                    await record_provider_exchange(
                        history['id'],
                        provider_response={
                            'http_status': response.status_code,
                            'body': parse_error_body(error_content.decode()),
                        },
                        response_headers=safe_response_headers(response.headers),
                        snapshot_status='partial',
                    )
                    raise HTTPException(status_code=response.status_code, detail=error_content.decode())

            response_headers = safe_response_headers(response.headers)
            response = response.json()
            await record_provider_exchange(
                history['id'],
                provider_response=copy.deepcopy(response),
                response_headers=response_headers,
                snapshot_status='captured',
            )

            # 拿到结果
            answer = response['choices'][0]['message']['content']
            reasoning_content = response['choices'][0]['message'].get('reasoning_content', '')

            # usage
            if not response.get('usage', {}):
                usage = await self.get_usage(response, params, f'{reasoning_content}\n{answer}')
                response['usage'] = usage
                response['usage_source'] = 'estimated' if usage and usage.get('total_tokens', 0) > 0 else 'unknown'
            else:
                response['usage_source'] = 'provider'

            await self.update_tokens(history, response)

            logger.info(f"chat end")
            return response
        except Exception as e:
            await update_history_status(history['id'], finish_status='failed', error_message=str(e))
            await insert_request_event(history['id'], 'request_failed', self.provider_english_name, {'error': str(e)})
            raise


    async def chat_stream(self, params):
        id = params.get('id', '')
        if id:
            del params['id']
        else:
            id = snowflake.next_id()

        history = await self.create_history(params)
        logger = Logger(self.model_name, id)
        logger.info(f"chat start")

        sent_any_chunk = False
        stream_chunks = []
        try:
            # httpx异步请求
            usage = None
            usage_source = 'unknown'
            content = []
            reasoning_content = []
            params['model'] = self.model_id
            # 根据不同的供应商参数进行个性化处理
            await self.handle_params(params)
            if self.default_params: # 合并默认参数
                for key, value in self.default_params.items():
                    if key not in params:
                        params[key] = value
            await record_provider_exchange(
                history['id'],
                provider_outbound=copy.deepcopy(params),
                snapshot_status='captured',
            )

            async with httpx.AsyncClient(**settings.HTTPX_PARAMS) as client:
                async with client.stream("POST", self.chat_url, json=params, headers=self.stream_headers) as response:

                    if response.status_code != 200:
                        # 先读取响应内容
                        error_content = await response.aread()
                        await record_provider_exchange(
                            history['id'],
                            provider_response={
                                'http_status': response.status_code,
                                'body': parse_error_body(error_content.decode()),
                            },
                            response_headers=safe_response_headers(response.headers),
                            snapshot_status='partial',
                        )
                        raise HTTPException(status_code=response.status_code, detail=error_content.decode())

                    async for line in response.aiter_lines():
                        chunk = line.strip()
                        # logger.info(f"chunk: {chunk}")
                        if not chunk:
                            continue  # 跳过空行
                        chunk = chunk[6:]
                        if chunk == '[DONE]':
                            continue  # 跳过空行

                        try:
                            chunk = json.loads(chunk)
                            if 'choices' not in chunk:
                                print(chunk)
                                continue
                        except Exception as e:
                            continue

                        if 'usage' not in chunk:
                            chunk['usage'] = None
                        stream_chunks.append(copy.deepcopy(chunk))
                        if chunk['usage']:
                            usage = chunk['usage']
                            usage_source = 'provider'

                        if chunk['choices']:
                            if 'content' not in chunk['choices'][0]['delta']:
                                chunk['choices'][0]['delta']['content'] = ''
                            if chunk['choices'][0]['delta']['content']:
                                content.append(chunk['choices'][0]['delta']['content'])
                            if chunk['choices'][0]['delta'].get('reasoning_content', ''):
                                reasoning_content.append(chunk['choices'][0]['delta']['reasoning_content'])
                            if chunk['choices'][0]['delta'].get('reasoning', ''):
                                reasoning_content.append(chunk['choices'][0]['delta']['reasoning'])

                            # 输出图片base64保存
                            for image in chunk['choices'][0]['delta'].get('images', []):
                                if image['type'] == 'image_url':
                                    img_path = save_base64_image(image['image_url']['url'].split(',')[1])
                                    content.append(f'\n\n![image]({img_path})')

                            if chunk['choices'][0].get('finish_reason', '') == 'stop':
                                chunk['choices'][0]['finish_reason'] = None

                                if chunk['choices'][0].get('id', ''):
                                    params['id'] = chunk['choices'][0]['id']

                        sent_any_chunk = True
                        yield chunk


            usage = await self.get_usage({'usage': usage}, params, f"{''.join(reasoning_content)}\n{''.join(content)}")
            if usage_source == 'unknown':
                usage_source = 'estimated' if usage and usage.get('total_tokens', 0) > 0 else 'unknown'

            # finishe
            templace = {"choices": [{"delta": {"content": "", "role": "assistant"}, "index": 0, "finish_reason": 'stop'}],
                        "created": int(time.time()), "id": str(history['id']), "model": self.model_id,
                        "service_tier": "default", "object": "chat.completion.chunk", "usage": usage}

            yield templace
            stream_chunks.append(copy.deepcopy(templace))
            await record_provider_exchange(
                history['id'],
                stream_chunks=build_stream_chunk_summary(stream_chunks),
                snapshot_status='captured',
            )

            # 记录数据
            response = {'id': history['id'],
                        'choices': [{'message': {
                            "role": "assistant",
                            'content': ''.join(content)
                        }}],
                        'usage': usage,
                        "created": int(time.time()), "model": self.model_id, "object": "chat.completion"
                        }
            if reasoning_content:
                response['choices'][0]['message']['reasoning_content'] = ''.join(reasoning_content)
            response['usage_source'] = usage_source

            await self.update_tokens(history, response)
            logger.info(f"chat end")
        except Exception as e:
            status = 'interrupted' if sent_any_chunk else 'failed'
            if stream_chunks:
                await record_provider_exchange(
                    history['id'],
                    stream_chunks=build_stream_chunk_summary(stream_chunks),
                    snapshot_status='partial',
                )
            await update_history_status(history['id'], finish_status=status, error_message=str(e))
            await insert_request_event(history['id'], f'request_{status}', self.provider_english_name, {'error': str(e)})
            raise


    # response LLM接口
    async def chat_stream_response(self, params):
        id = params.get('id', '')
        if id:
            del params['id']

        history = await self.create_history(params)
        logger = Logger(self.model_name, id)
        logger.info(f"chat start")

        sent_any_chunk = False
        stream_chunks = []
        try:
            # 处理messages参数
            params['model'] = self.model_id
            input_params = params.copy()
            input_params['input'] = input_params['messages']
            del input_params['messages']
            if 'stream_options' in input_params:
                del input_params['stream_options']

            # 根据不同的供应商参数进行个性化处理
            await self.handle_params(input_params)
            if self.default_params: # 合并默认参数
                for key, value in self.default_params.items():
                    if key not in input_params:
                        input_params[key] = value
            await record_provider_exchange(
                history['id'],
                provider_outbound=copy.deepcopy(input_params),
                snapshot_status='captured',
            )

            # httpx异步请求
            usage = None
            usage_source = 'unknown'
            content = []
            reasoning_content = []
            templace = {"choices": [{"delta": {"content": "", "role": "assistant"}, "index": 0}], "created": int(time.time()), "id": str(history['id']), "model": self.model_id, "service_tier": "default", "object": "chat.completion.chunk", "usage": None}
            async with httpx.AsyncClient(**settings.HTTPX_PARAMS) as client:
                async with client.stream("POST", self.base_url_response, json=input_params, headers=self.stream_headers) as response:

                    if response.status_code != 200:
                        # 先读取响应内容
                        error_content = await response.aread()
                        await record_provider_exchange(
                            history['id'],
                            provider_response={
                                'http_status': response.status_code,
                                'body': parse_error_body(error_content.decode()),
                            },
                            response_headers=safe_response_headers(response.headers),
                            snapshot_status='partial',
                        )
                        raise HTTPException(status_code=response.status_code, detail=error_content.decode())

                    async for line in response.aiter_lines():
                        chunk = line.strip()
                        # logger.info(chunk)
                        if not chunk:
                            continue  # 跳过空行
                        chunk = chunk[6:]
                        if chunk[-1] != '}':
                            continue  # 跳过空行

                        chunk = json.loads(chunk)

                        if chunk.get('response', {}) and chunk['response'].get('usage', {}):
                            usage = chunk['response']['usage']
                            usage_source = 'provider'

                        if not chunk.get('delta', ''):
                            continue

                        if chunk['type'] == 'response.output_text.delta':
                            if 'reasoning_content' in templace['choices'][0]['delta']:
                                del templace['choices'][0]['delta']['reasoning_content']
                            templace['choices'][0]['delta']['content'] = chunk['delta']
                            content.append(chunk['delta'])
                        elif chunk['type'] == 'response.reasoning_summary_text.delta':
                            templace['choices'][0]['delta']['reasoning_content'] = chunk['delta']
                            reasoning_content.append(chunk['delta'])

                        stream_chunks.append(copy.deepcopy(templace))
                        sent_any_chunk = True
                        yield templace

            if not usage:
                usage = await self.get_usage({'usage': usage}, params, f"{''.join(reasoning_content)}\n{''.join(content)}")
                usage_source = 'estimated' if usage and usage.get('total_tokens', 0) > 0 else 'unknown'
            else:
                usage = {'completion_tokens': usage['output_tokens'], 'prompt_tokens': usage['input_tokens'], 'total_tokens': usage['total_tokens']}

            # finishe
            templace = {"choices": [{"delta": {"content": "", "role": "assistant"}, "index": 0, "finish_reason": 'stop'}],
                        "created": int(time.time()), "id": str(history['id']), "model": self.model_id,
                        "service_tier": "default", "object": "chat.completion.chunk", "usage": usage}

            yield templace
            stream_chunks.append(copy.deepcopy(templace))
            await record_provider_exchange(
                history['id'],
                stream_chunks=build_stream_chunk_summary(stream_chunks),
                snapshot_status='captured',
            )

            # 记录数据
            response = {'id': history['id'],
                        'choices': [{'message': {
                            "role": "assistant",
                            'content': ''.join(content)
                        }}],
                        'usage': usage,
                        "created": int(time.time()), "model": self.model_id, "object": "chat.completion"
                        }
            if reasoning_content:
                response['choices'][0]['message']['reasoning_content'] = ''.join(reasoning_content)
            response['usage_source'] = usage_source

            await self.update_tokens(history, response)
            logger.info(f"chat end")
        except Exception as e:
            status = 'interrupted' if sent_any_chunk else 'failed'
            if stream_chunks:
                await record_provider_exchange(
                    history['id'],
                    stream_chunks=build_stream_chunk_summary(stream_chunks),
                    snapshot_status='partial',
                )
            await update_history_status(history['id'], finish_status=status, error_message=str(e))
            await insert_request_event(history['id'], f'request_{status}', self.provider_english_name, {'error': str(e)})
            raise


    # 获取usage
    async def get_usage(self, response, params, answer):
        if response['usage']:
            return {'completion_tokens': response['usage']['completion_tokens'], 'prompt_tokens': response['usage']['prompt_tokens'], 'total_tokens': response['usage']['total_tokens']}
        else:
            return {'completion_tokens': 0, 'prompt_tokens': 0, 'total_tokens': 0}

    # 根据不同的供应商参数进行个性化处理
    async def handle_params(self, params):
        pass

    # 构建数据库当中的context字段
    async def construct_db_context(self, params):
        messages = copy.deepcopy(params['messages'])

        for item in messages:
            if isinstance(item['content'], list):
                for content_item in item['content']:
                    if 'image_url' in content_item:
                        if content_item['image_url']['url'].startswith('data:image'):
                            # 保存图片
                            image_url = content_item['image_url']['url']
                            content_item['image_url']['url'] = save_base64_image(image_url.split(',')[1])

        tools = []
        for tool in params.get('tools', []):
            if tool['type'] != 'web_search':
                tools.append(tool)

        context = messages + tools if tools else messages
        return context
