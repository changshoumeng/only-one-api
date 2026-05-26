
-- V1.3--
-- LLM提供商表
create table if not exists llm_provider
(
    id                    BIGINT   not null primary key,
    provider_name         VARCHAR(100) null,
    provider_english_name VARCHAR(50)  null,
    api_key               VARCHAR(100) null,
    base_url              VARCHAR(100) null,
    is_delete             TINYINT default 0 null,
    create_time           DATETIME null,
    update_time           DATETIME null
);

INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (786254914769649665, '深度求索', 'DeepSeek', 'test', 'https://api.deepseek.com', '2025-12-09 23:36:19', '2025-12-10 22:06:27');
INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (786594449739218945, '火山云', 'ByteDance', 'test', 'https://ark.cn-beijing.volces.com/api/v3', '2025-12-10 22:05:31', '2025-12-10 22:05:31');
INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (786608631641538561, '阿里云', 'ALiYun', 'test', 'https://dashscope.aliyuncs.com/compatible-mode/v1', '2025-12-10 23:01:52', '2025-12-10 23:01:52');
INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (786608813334593537, 'OpenRouter', 'OpenRouter', 'test', 'https://openrouter.ai/api/v1', '2025-12-10 23:02:35', '2025-12-10 23:02:35');
INSERT INTO llm_provider (id, provider_name, provider_english_name, api_key, base_url, create_time, update_time) VALUES (787137527113842688, '硅基流动', 'SiliconCloud', 'test', 'https://api.siliconflow.cn', '2025-12-12 10:03:30', '2025-12-12 10:03:30');


-- LLM模型表
create table if not exists llm_model
(
    id                    BIGINT   not null primary key,
    provider_english_name VARCHAR(50)  null,
    model_name            VARCHAR(50)  null,
    model_id              VARCHAR(50)  null,
    billing_unit         VARCHAR(50)  null,
    input_unit_price      FLOAT null,
    output_unit_price     FLOAT null,
    default_params        VARCHAR(500)  null,
    status                TINYINT      null,
    is_delete             TINYINT default 0 null,
    create_time           DATETIME null,
    update_time           DATETIME null
);

create index llm_model_provider_english_name_index
    on llm_model (provider_english_name);

create index llm_model_status_index
    on llm_model (status);

INSERT INTO llm_model (id, provider_english_name, model_name, model_id, billing_unit, input_unit_price, output_unit_price, status, create_time, update_time) VALUES (786255595048009728, 'DeepSeek', 'deepseek-v3.2', 'deepseek-reasoner', 'per_thousand_tokens', 0.002, 0.003, 1, '2025-12-09 23:39:01', '2025-12-09 23:39:01');



-- LLM聊天记录表
create table if not exists llm_chat_history
(
    id                BIGINT                             not null primary key,
    context           LONGTEXT                            null,
    prompt            LONGTEXT                            null,
    answer            LONGTEXT                            null,
    provider_name     VARCHAR(100)                           null,
    model_name        VARCHAR(50)                            null,
    model_id          VARCHAR(50)                            null,
    api_key_id        INT                             null,
    prompt_tokens     INT      default 0                 null,
    completion_tokens INT      default 0                 null,
    request_id        VARCHAR(64)                         null,
    usage_source      VARCHAR(30) default 'unknown'       null,
    finish_status     VARCHAR(30) default 'running'       null,
    error_message     LONGTEXT                            null,
    input_price       FLOAT default 0                 null,
    output_price      FLOAT default 0                 null,
    create_time       DATETIME default CURRENT_TIMESTAMP null,
    create_day        VARCHAR(10)                           null,
    create_month      VARCHAR(7)                            null,
    create_year       VARCHAR(4)                            null,
    update_time       DATETIME                           null
);

create index llm_chat_history_create_time_index
    on llm_chat_history (create_time);

create index llm_chat_history_create_day_index
    on llm_chat_history (create_day);
create index llm_chat_history_create_month_index
    on llm_chat_history (create_month);
create index llm_chat_history_create_year_index
    on llm_chat_history (create_year);


create index llm_chat_history_model_id_index
    on llm_chat_history (model_id);

create index llm_chat_history_model_name_index
    on llm_chat_history (model_name);

create index llm_chat_history_provider_name_index
    on llm_chat_history (provider_name);

create index llm_chat_history_id_index
    on llm_chat_history (id desc);

create index llm_chat_history_api_key_id_index
    on llm_chat_history (api_key_id);

create index llm_chat_history_request_id_index
    on llm_chat_history (request_id);

-- LLM聊天消息明细表
create table if not exists llm_chat_message
(
    id             BIGINT                             not null primary key,
    history_id     BIGINT                             not null,
    seq            INT                                null,
    role           VARCHAR(30)                        null,
    message_type   VARCHAR(50)                        null,
    content_text   LONGTEXT                           null,
    content_json   LONGTEXT                           null,
    token_count    INT                                null,
    token_source   VARCHAR(50)                        null,
    received_at    DATETIME                           null,
    raw_json       LONGTEXT                           null,
    create_time    DATETIME default CURRENT_TIMESTAMP null
);

create index llm_chat_message_history_id_index
    on llm_chat_message (history_id);

create index llm_chat_message_received_at_index
    on llm_chat_message (received_at);

-- LLM工具调用明细表
create table if not exists llm_tool_call
(
    id             BIGINT      not null primary key,
    history_id     BIGINT      not null,
    message_id     BIGINT      null,
    tool_call_id   VARCHAR(120) null,
    tool_name      VARCHAR(200) null,
    arguments_json LONGTEXT    null,
    result_json    LONGTEXT    null,
    status         VARCHAR(30) null,
    created_at     DATETIME    null,
    completed_at   DATETIME    null
);

create index llm_tool_call_history_id_index
    on llm_tool_call (history_id);

create index llm_tool_call_tool_call_id_index
    on llm_tool_call (tool_call_id);

-- LLM请求事件表
create table if not exists llm_request_event
(
    id            BIGINT       not null primary key,
    history_id    BIGINT       not null,
    event_type    VARCHAR(50)  null,
    provider_name VARCHAR(100) null,
    payload_json  LONGTEXT     null,
    created_at    DATETIME     null
);

create index llm_request_event_history_id_index
    on llm_request_event (history_id);

create index llm_request_event_event_type_index
    on llm_request_event (event_type);

-- LLM原始请求响应快照表
create table if not exists llm_request_snapshot
(
    id                     BIGINT                             not null primary key,
    history_id             BIGINT                             not null,
    request_id             VARCHAR(64)                        null,
    inbound_json           LONGTEXT                           null,
    normalized_json        LONGTEXT                           null,
    provider_outbound_json LONGTEXT                           null,
    provider_response_json LONGTEXT                           null,
    response_headers_json  LONGTEXT                           null,
    stream_chunks_json     LONGTEXT                           null,
    snapshot_status        VARCHAR(30) default 'captured'     null,
    redaction_version      VARCHAR(30) default 'v1'           null,
    payload_bytes          INT default 0                      null,
    truncated_fields_json  LONGTEXT                           null,
    created_at             DATETIME default CURRENT_TIMESTAMP null,
    updated_at             DATETIME                           null
);

create index idx_llm_request_snapshot_history_id
    on llm_request_snapshot (history_id);

create index idx_llm_request_snapshot_request_id
    on llm_request_snapshot (request_id);


-- LLM接口密钥表
create table if not exists llm_api_keys
(
    api_key_id  INTEGER primary key AUTOINCREMENT,
    api_key     varchar(100)           null,
    remark      varchar(150)           null,
    is_use      tinyint  default 1     null,
    is_delete   tinyint  default 0     null,
    create_time datetime default (datetime('now','localtime')) null,
    update_time datetime default (datetime('now','localtime')) null
);

create index llm_api_keys_api_key_index
    on llm_api_keys (api_key);

create index llm_api_keys_is_use_index
    on llm_api_keys (is_use);

create index llm_api_keys_is_delete_index
    on llm_api_keys (is_delete);

INSERT INTO llm_api_keys (api_key, remark, is_use, is_delete, create_time, update_time) VALUES ('sk-6krzNJoef72vmQkzCAf97BFiMwevu2cQ', null, 1, 0, '2025-12-10 22:08:40', '2025-12-10 22:08:40');


-- LLM用户表
create table if not exists llm_user
(
    id          BIGINT   not null primary key,
    username    VARCHAR(50)  null,
    password    VARCHAR(255)  null,
    is_first_login TINYINT   null,
    create_time DATETIME default (datetime('now','localtime')) null
);

create index llm_user_username_index
    on llm_user (username);

create index llm_user_password_index
    on llm_user (password);

INSERT INTO llm_user (id, username, password, is_first_login) VALUES (1, 'stark', 'pllm_pbkdf2_sha256$260000$cGVyc29uYWwtbGxtLWFwaS1kZWZhdWx0LXNhbHQ$gPm5XXBiL2rFsxk7TK60Y7K2O3KVswW3gKuojGJkcrQ', 1);

-- V1.3--
