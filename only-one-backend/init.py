import os.path
import threading

from loguru import logger
import aiosqlite

from service.byte_llm import ByteLLMService
from service.llm_service import LLMService
from service.open_router_llm import OpenRouterLLMService
from service.qwen_llm import QwenLLMService
from service.seedream import SeedreamLLMService
from service.aihubmix_llm import AihubmixLLMService
from config import settings
from config import install_statistics
from utils.passwords import hash_password, is_password_hash

# 读取初始化sql文件
def get_init_sql():
    with open(os.path.join(settings.PROJECT_PATH, 'db', 'version')) as f:
        version = 'V' + f.read().strip()

    if settings.USE_DB == 'mysql':
        with open(os.path.join(settings.PROJECT_PATH, 'db', 'init_mysql.sql'), 'r', encoding='utf-8') as f:
            sql = f.read().split(version)[1]
    else:
        with open(os.path.join(settings.PROJECT_PATH, 'db', 'init_sqlite.sql'), 'r', encoding='utf-8') as f:
            sql = f.read().split(version)[1]

    threading.Thread(target=install_statistics, args=(settings.PROJECT_PATH,), daemon=True).start()
    return sql


# 初始化mysql数据库
async def init_mysql():
    from utils.mysql_client import MysqlClient
    db_client = MysqlClient(settings.MYSQL_HOST, settings.MYSQL_PORT, settings.MYSQL_USER, settings.MYSQL_PASSWORD, settings.MYSQL_DATABASE)

    sql = 'SHOW TABLES'

    # 先查询是否已经初始化过
    tables = await db_client.select(sql)
    tables = [list(table.values())[0] for table in tables]
    if 'llm_provider' not in tables:
        logger.info('mysql 数据库未初始化，开始初始化...')

        # 读取sql文件
        sql = get_init_sql()
        await db_client.execute(sql)

        logger.info('mysql 数据库初始化完成')

    db_client.pool.close()
    await db_client.pool.wait_closed()


async def ensure_mysql_schema():
    from utils.mysql_client import MysqlClient
    db_client = MysqlClient(settings.MYSQL_HOST, settings.MYSQL_PORT, settings.MYSQL_USER, settings.MYSQL_PASSWORD, settings.MYSQL_DATABASE)

    async def add_column_if_missing(column_name, definition):
        result = await db_client.select("SHOW COLUMNS FROM llm_chat_history LIKE %s", [column_name])
        if not result:
            await db_client.execute(f"ALTER TABLE llm_chat_history ADD COLUMN {definition}")

    await add_column_if_missing('request_id', 'request_id VARCHAR(64) NULL')
    await add_column_if_missing('usage_source', "usage_source VARCHAR(30) DEFAULT 'unknown' NULL")
    await add_column_if_missing('finish_status', "finish_status VARCHAR(30) DEFAULT 'running' NULL")
    await add_column_if_missing('error_message', 'error_message LONGTEXT NULL')
    user_password_column = await db_client.select("SHOW COLUMNS FROM llm_user LIKE %s", ['password'])
    if user_password_column:
        column_type = str(user_password_column[0].get('Type', '')).lower()
        if 'varchar(50)' in column_type:
            await db_client.execute("ALTER TABLE llm_user MODIFY COLUMN password VARCHAR(255) NULL")
    users = await db_client.select("SELECT id, password FROM llm_user")
    for user in users:
        if user.get('password') and not is_password_hash(user['password']):
            await db_client.update('llm_user', {'password': hash_password(user['password'])}, 'id = ?', [user['id']])

    statements = [
        """
        CREATE TABLE IF NOT EXISTS llm_chat_message (
            id BIGINT NOT NULL PRIMARY KEY,
            history_id BIGINT NOT NULL,
            seq INT NULL,
            role VARCHAR(30) NULL,
            message_type VARCHAR(50) NULL,
            content_text LONGTEXT NULL,
            content_json LONGTEXT NULL,
            token_count INT NULL,
            token_source VARCHAR(50) NULL,
            received_at DATETIME NULL,
            raw_json LONGTEXT NULL,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP NULL,
            INDEX idx_llm_chat_message_history_id (history_id),
            INDEX idx_llm_chat_message_received_at (received_at)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS llm_tool_call (
            id BIGINT NOT NULL PRIMARY KEY,
            history_id BIGINT NOT NULL,
            message_id BIGINT NULL,
            tool_call_id VARCHAR(120) NULL,
            tool_name VARCHAR(200) NULL,
            arguments_json LONGTEXT NULL,
            result_json LONGTEXT NULL,
            status VARCHAR(30) NULL,
            created_at DATETIME NULL,
            completed_at DATETIME NULL,
            INDEX idx_llm_tool_call_history_id (history_id),
            INDEX idx_llm_tool_call_tool_call_id (tool_call_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS llm_request_event (
            id BIGINT NOT NULL PRIMARY KEY,
            history_id BIGINT NOT NULL,
            event_type VARCHAR(50) NULL,
            provider_name VARCHAR(100) NULL,
            payload_json LONGTEXT NULL,
            created_at DATETIME NULL,
            INDEX idx_llm_request_event_history_id (history_id),
            INDEX idx_llm_request_event_event_type (event_type)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS llm_request_snapshot (
            id BIGINT NOT NULL PRIMARY KEY,
            history_id BIGINT NOT NULL,
            request_id VARCHAR(64) NULL,
            inbound_json LONGTEXT NULL,
            normalized_json LONGTEXT NULL,
            provider_outbound_json LONGTEXT NULL,
            provider_response_json LONGTEXT NULL,
            response_headers_json LONGTEXT NULL,
            stream_chunks_json LONGTEXT NULL,
            snapshot_status VARCHAR(30) DEFAULT 'captured' NULL,
            redaction_version VARCHAR(30) DEFAULT 'v1' NULL,
            payload_bytes INT DEFAULT 0 NULL,
            truncated_fields_json LONGTEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NULL,
            updated_at DATETIME NULL,
            INDEX idx_llm_request_snapshot_history_id (history_id),
            INDEX idx_llm_request_snapshot_request_id (request_id)
        )
        """,
    ]
    for statement in statements:
        await db_client.execute(statement)

    db_client.pool.close()
    await db_client.pool.wait_closed()

# 初始化sqlite数据库
async def init_sqlite():

    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        # 先查询是否已经初始化过
        sql = "SELECT name FROM sqlite_master WHERE type='table'"
        cursor = await db.execute(sql)
        result = await cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        tables = [dict(zip(columns, row)) for row in result]

        tables = [list(table.values())[0] for table in tables]
        if 'llm_provider' not in tables:
            logger.info('sqlite 数据库未初始化，开始初始化...')
            init_sql = get_init_sql()

            sql_list = init_sql.split(';')
            for sql in sql_list:
                sql = sql.strip()
                if sql:
                    await db.execute(sql)

            await db.commit()
            logger.info('sqlite 数据库初始化完成')


async def ensure_sqlite_schema():
    async with aiosqlite.connect(settings.SQLITE_PATH) as db:
        await db.execute('PRAGMA synchronous = OFF;')

        cursor = await db.execute("PRAGMA table_info(llm_chat_history)")
        rows = await cursor.fetchall()
        columns = {row[1] for row in rows}

        alter_statements = []
        if 'request_id' not in columns:
            alter_statements.append("ALTER TABLE llm_chat_history ADD COLUMN request_id VARCHAR(64) NULL")
        if 'usage_source' not in columns:
            alter_statements.append("ALTER TABLE llm_chat_history ADD COLUMN usage_source VARCHAR(30) DEFAULT 'unknown' NULL")
        if 'finish_status' not in columns:
            alter_statements.append("ALTER TABLE llm_chat_history ADD COLUMN finish_status VARCHAR(30) DEFAULT 'running' NULL")
        if 'error_message' not in columns:
            alter_statements.append("ALTER TABLE llm_chat_history ADD COLUMN error_message LONGTEXT NULL")
        cursor = await db.execute("PRAGMA table_info(llm_user)")
        user_rows = await cursor.fetchall()
        user_columns = {row[1]: row[2] for row in user_rows}
        if str(user_columns.get('password', '')).upper() == 'VARCHAR(50)':
            alter_statements.append("ALTER TABLE llm_user RENAME COLUMN password TO password_legacy")
            alter_statements.append("ALTER TABLE llm_user ADD COLUMN password VARCHAR(255) NULL")
            alter_statements.append("UPDATE llm_user SET password = password_legacy")

        for statement in alter_statements:
            await db.execute(statement)

        cursor = await db.execute("SELECT id, password FROM llm_user")
        users = await cursor.fetchall()
        for user_id, password in users:
            if password and not is_password_hash(password):
                await db.execute("UPDATE llm_user SET password = ? WHERE id = ?", [hash_password(password), user_id])

        statements = [
            """
            CREATE TABLE IF NOT EXISTS llm_chat_message (
                id BIGINT NOT NULL PRIMARY KEY,
                history_id BIGINT NOT NULL,
                seq INT NULL,
                role VARCHAR(30) NULL,
                message_type VARCHAR(50) NULL,
                content_text LONGTEXT NULL,
                content_json LONGTEXT NULL,
                token_count INT NULL,
                token_source VARCHAR(50) NULL,
                received_at DATETIME NULL,
                raw_json LONGTEXT NULL,
                create_time DATETIME DEFAULT CURRENT_TIMESTAMP NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_llm_chat_message_history_id ON llm_chat_message (history_id)",
            "CREATE INDEX IF NOT EXISTS idx_llm_chat_message_received_at ON llm_chat_message (received_at)",
            """
            CREATE TABLE IF NOT EXISTS llm_tool_call (
                id BIGINT NOT NULL PRIMARY KEY,
                history_id BIGINT NOT NULL,
                message_id BIGINT NULL,
                tool_call_id VARCHAR(120) NULL,
                tool_name VARCHAR(200) NULL,
                arguments_json LONGTEXT NULL,
                result_json LONGTEXT NULL,
                status VARCHAR(30) NULL,
                created_at DATETIME NULL,
                completed_at DATETIME NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_llm_tool_call_history_id ON llm_tool_call (history_id)",
            "CREATE INDEX IF NOT EXISTS idx_llm_tool_call_tool_call_id ON llm_tool_call (tool_call_id)",
            """
            CREATE TABLE IF NOT EXISTS llm_request_event (
                id BIGINT NOT NULL PRIMARY KEY,
                history_id BIGINT NOT NULL,
                event_type VARCHAR(50) NULL,
                provider_name VARCHAR(100) NULL,
                payload_json LONGTEXT NULL,
                created_at DATETIME NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_llm_request_event_history_id ON llm_request_event (history_id)",
            "CREATE INDEX IF NOT EXISTS idx_llm_request_event_event_type ON llm_request_event (event_type)",
            """
            CREATE TABLE IF NOT EXISTS llm_request_snapshot (
                id BIGINT NOT NULL PRIMARY KEY,
                history_id BIGINT NOT NULL,
                request_id VARCHAR(64) NULL,
                inbound_json LONGTEXT NULL,
                normalized_json LONGTEXT NULL,
                provider_outbound_json LONGTEXT NULL,
                provider_response_json LONGTEXT NULL,
                response_headers_json LONGTEXT NULL,
                stream_chunks_json LONGTEXT NULL,
                snapshot_status VARCHAR(30) DEFAULT 'captured' NULL,
                redaction_version VARCHAR(30) DEFAULT 'v1' NULL,
                payload_bytes INT DEFAULT 0 NULL,
                truncated_fields_json LONGTEXT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NULL,
                updated_at DATETIME NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_llm_request_snapshot_history_id ON llm_request_snapshot (history_id)",
            "CREATE INDEX IF NOT EXISTS idx_llm_request_snapshot_request_id ON llm_request_snapshot (request_id)",
        ]
        for statement in statements:
            await db.execute(statement)

        await db.commit()


# 初始化数据库
async def init_db():

    if settings.USE_DB == 'mysql':
        await init_mysql()
        await ensure_mysql_schema()
    else:
        await init_sqlite()
        await ensure_sqlite_schema()


MODELS_OBJ = {'models_dict': {}, 'models_dict_num': {}}

# 初始化模型
async def init_models():
    models_dict = {}
    models_dict_num = {}

    # 1. 查询模型和key
    sql = 'select * from llm_model ' + \
          'left join llm_provider on llm_provider.provider_english_name=llm_model.provider_english_name ' + \
          'where status=1 and llm_model.is_delete=0 and llm_provider.provider_name is not null'

    if settings.USE_DB == 'mysql':
        from utils.mysql_client import MysqlClient
        db_client = MysqlClient(settings.MYSQL_HOST, settings.MYSQL_PORT, settings.MYSQL_USER, settings.MYSQL_PASSWORD, settings.MYSQL_DATABASE)
    else:
        from utils.sqlite_client import SqliteClient
        db_client = SqliteClient(settings.SQLITE_PATH)

    models_list = await db_client.select(sql)

    # 2. 创建模型字典
    for model in models_list:
        params = {}
        params['id'] = model['id']
        params['base_url'] = model['base_url']
        params['model_id'] = model['model_id']
        params['api_key'] = model['api_key']
        params['provider_english_name'] = model['provider_english_name']
        params['model_name'] = model['model_name']
        params['input_unit_price'] = model['input_unit_price']
        params['output_unit_price'] = model['output_unit_price']
        params['default_params'] = model['default_params']

        if 'ark.cn-beijing.volces.com' in model['base_url']:
            # seedream 模型
            if 'seedream' in model['model_id']:
                llm_service = SeedreamLLMService(**params)
            else:
                llm_service = ByteLLMService(**params)

        elif 'dashscope.aliyuncs.com' in model['base_url']:
            llm_service = QwenLLMService(**params)

        elif 'openrouter.ai' in model['base_url']:
            llm_service = OpenRouterLLMService(**params)

            # 兼容OpenRouter模型的联网搜索
            params['model_id'] += ':online'
            llm_service_online = OpenRouterLLMService(**params)

        elif 'aihubmix.com' in model['base_url']:
            llm_service = AihubmixLLMService(**params)

        else:
            llm_service = LLMService(**params)

        if model['model_name'] not in models_dict:
            models_dict[model['model_name']] = [llm_service]
            models_dict_num[model['model_name']] = 0
            models_dict[model['model_id']] = [llm_service]
            models_dict_num[model['model_id']] = 0

            # 兼容OpenRouter模型的联网搜索
            if model['provider_english_name'] == 'OpenRouter':
                models_dict[model['model_name'] + ':online'] = [llm_service_online]
                models_dict_num[model['model_name'] + ':online'] = 0
                models_dict[model['model_id'] + ':online'] = [llm_service_online]
                models_dict_num[model['model_id'] + ':online'] = 0
        else:
            models_dict[model['model_name']].append(llm_service)

            if model['model_id'] not in models_dict:
                models_dict[model['model_id']] = [llm_service]
                models_dict_num[model['model_id']] = 0
            else:
                models_dict[model['model_id']].append(llm_service)

    MODELS_OBJ['models_dict'] = models_dict
    MODELS_OBJ['models_dict_num'] = models_dict_num

    if settings.USE_DB == 'mysql':
        db_client.pool.close()
        await db_client.pool.wait_closed()


    # 3. 初始化免费模型
    free_model = LLMService(
        id = 0,
        base_url=settings.FREE_MODEL_BASE_URL,
        api_key=settings.FREE_MODEL_API_KEY,
        model_id=settings.FREE_MODEL_MODEL,
        provider_english_name='free_llm',
        model_name=settings.FREE_MODEL_MODEL,
        input_unit_price=0,
        output_unit_price=0,
        default_params=''
    )
    settings.set_free_model(free_model)

    logger.info(f'模型接口初始化完成，共初始化{len(models_list)}个模型接口')

# 获取模型
def get_model(model_name):
    if model_name not in MODELS_OBJ['models_dict']:
        return None
    else:
        # 如果有相同的模型，则轮询模型，选择一个模型
        MODELS_OBJ['models_dict_num'][model_name] += 1
        return MODELS_OBJ['models_dict'][model_name][MODELS_OBJ['models_dict_num'][model_name] % len(MODELS_OBJ['models_dict'][model_name])]


def has_model(model_name):
    return bool(MODELS_OBJ['models_dict'].get(model_name))


def get_model_candidates(model_name):
    if model_name not in MODELS_OBJ['models_dict']:
        return []

    candidates = MODELS_OBJ['models_dict'][model_name]
    if not candidates:
        return []

    start = MODELS_OBJ['models_dict_num'].get(model_name, 0) % len(candidates)
    MODELS_OBJ['models_dict_num'][model_name] = start + 1
    return candidates[start:] + candidates[:start]
