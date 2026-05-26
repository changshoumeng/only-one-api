# only-one-api

only-one-api 是一个面向个人和小范围自用场景的 LLM 网关与管理后台。它保留了 one-api 最核心的使用体验：用 OpenAI 兼容接口统一调用多个模型供应商；同时主动收窄了多租户、商业化计费、多机部署和复杂渠道生态，把工程重心放在“一个人能快速启动、管理自己的模型 Key、看清每次请求发生了什么”。

从架构视角看，本项目不是 one-api 的功能复刻，而是一个轻量化、可审计、可二次开发的个人 LLM Gateway。

## 与 one-api 的定位差异

one-api 是平台型大模型 API 网关，适合“运营方管理多用户、多令牌、多渠道、额度和分组”的 API 分发/转售/共享场景。它的核心模型是：平台管理员维护共享渠道，用户通过自己的 Token 调用，系统按用户、Token、Group 和渠道做鉴权、配额、计费、日志和负载均衡。

only-one-api 则是个人型网关。它默认只有一个后台用户，一个简单的网关 Key 池，一组自己维护的模型供应商配置。它解决的是个人使用多个供应商时的几个实际问题：

- 本地统一 OpenAI 兼容入口，减少客户端反复切换 base URL 和 Key。
- 在一个后台里维护供应商、模型、价格和默认参数。
- 记录请求、消息、工具调用、错误状态和 Token/费用估算，便于排查模型调用问题。
- 前端构建后由后端直接托管，部署和长期运行成本低。

### 能力对比

| 维度 | one-api | only-one-api |
| --- | --- | --- |
| 目标场景 | 多用户 API 分发平台、共享网关、转售/运营场景 | 个人/小范围自用、本机或局域网网关 |
| 后端技术栈 | Go + Gin + GORM | Python + FastAPI + aiosqlite/aiomysql |
| 前端技术栈 | React SPA，多主题 | Vue 3 + Vite + Pinia |
| 部署形态 | Docker、Docker Compose、手动部署、多机主从 | 直接运行 `python main.py`，前端 build 后由后端托管 |
| 数据库 | SQLite / MySQL / PostgreSQL，支持独立日志库 | SQLite / MySQL |
| 用户体系 | Root/Admin/Common 多角色，注册、OAuth、邮箱、邀请 | 单后台用户，首次登录重置密码 |
| API 调用凭证 | 用户 Token，支持过期、额度、模型白名单、IP 网段 | 网关 API Key，支持启停、备注、删除 |
| 多租户 | 以 User 为租户边界，Token 为子凭证，Group 控制资源池 | 不做租户隔离，面向单人/可信小圈子 |
| 渠道模型 | Channel + Ability + Group，渠道分组、优先级、模型映射 | Provider + Model，按 `model_name` / `model_id` 聚合候选供应商 |
| 负载均衡/故障转移 | 分组内渠道选择，优先级/随机，失败重试和自动禁用渠道 | 同名模型候选供应商轮询，非流式失败尝试下一个候选；流式未输出前可切换 |
| 计费模型 | 用户额度、Token 额度、兑换码、充值、模型倍率、分组倍率 | 请求级 Token/费用统计，按模型配置单价估算，不扣减余额 |
| 管理能力 | 用户、渠道、令牌、兑换码、日志、系统选项、公告等 | 登录、使用量、供应商/模型、模型测试、Key、对话历史 |
| OpenAI 兼容接口 | Chat、Completions、Embeddings、Images、Audio、Moderations 等 | Chat、Models、Images generations/edits |
| 供应商生态 | 30+ 供应商/55+ 渠道类型，适配器体系完整 | 当前聚焦 DeepSeek、火山/豆包、阿里 DashScope、OpenRouter、Aihubmix、通用 OpenAI-compatible 等 |
| 审计粒度 | 消费日志、用户/Token/渠道维度统计 | 请求历史、消息明细、工具调用、请求事件、失败状态 |
| 可观测性 | 基础日志、渠道健康监控，架构文档建议补强 metrics/tracing | loguru 文件日志、`/health`、请求审计表；尚无 Prometheus/tracing |

## 本项目实现了什么

### OpenAI 兼容网关

- `POST /v1/chat/completions`
- `POST /chat/completions`
- `GET /v1/models`
- `GET /models`
- `POST /v1/images/generations`
- `POST /v1/images/edits`
- `GET /health`

Chat 接口支持流式与非流式返回。后端会把请求中的逻辑模型名映射到后台配置的真实供应商模型，并在响应头返回 `X-Request-ID`。OpenAI 路径上的错误会转换成 OpenAI 风格的 `error` 响应体。

### 个人模型与供应商管理

后台可维护：

- 供应商名称、英文标识、API Key、base URL。
- 模型名称、真实 model id、计费单位、输入/输出单价、默认参数。
- 模型启停、删除、连通性测试。
- 同一个 `model_name` 或 `model_id` 下的多个供应商候选。

后端启动时会从数据库加载启用的模型；后台变更供应商或模型后会重新初始化模型缓存。

### 请求审计与使用量统计

本项目比普通“反向代理”多做了一层请求审计：

- `llm_chat_history`：请求级历史、模型、供应商、Token、费用、状态、错误信息。
- `llm_chat_message`：逐条消息明细，支持多模态内容和 assistant/tool 消息。
- `llm_tool_call`：工具调用请求与工具结果。
- `llm_request_event`：请求开始、完成、失败等事件。

管理后台提供使用量图表和对话历史页面，用于定位上游错误、Token 统计缺失、工具调用异常和流式中断。

### 前后端一体化运行

当前有效工程边界是：

- `only-one-backend/`：FastAPI 后端，提供网关 API、后台 API、数据库初始化、session、日志和前端静态资源托管。
- `only-one-frontend/`：Vue 3 管理后台，提供登录、使用量、接口管理、Key 管理和对话历史。

前端构建产物固定输出到 `only-one-backend/html/dist`。构建后只需要启动后端，即可访问管理后台和 API。

## 本项目没有实现什么

与 one-api 相比，以下能力不是当前项目目标：

- 没有多用户注册、Root/Admin/Common 多角色、OAuth、邮箱验证、邀请奖励。
- 没有面向 API 转售的用户余额、令牌余额、兑换码、充值、模型倍率/分组倍率扣费体系。
- 没有 Group/Ability 这类多租户资源池隔离，也没有按用户分组选择渠道。
- 没有完整 one-api 供应商适配器生态；当前是少量供应商定制类 + 通用 OpenAI-compatible 调用。
- 没有 Embeddings、Audio、Moderations、Files、Fine-tuning、Assistants/Threads 等完整 OpenAI API 面。
- 没有 Docker Compose、多机主从、Redis 缓存、PostgreSQL、独立日志库。
- 没有渠道自动禁用、余额批量刷新、全局管理 API、系统公告、主题市场。
- 没有生产级 metrics/tracing/告警体系。

这些不是简单的“缺功能”，而是架构取舍：only-one-api 选择牺牲平台运营能力，换取更低的理解成本、部署成本和个人可控性。

## 目录结构

```text
.
├── only-one-backend/
│   ├── backend/          # 后台管理接口：登录、用量、模型、Key、对话历史
│   ├── db/               # SQLite/MySQL 初始化脚本和默认 SQLite 数据库
│   ├── html/dist/        # 前端构建输出目录，由 FastAPI 托管
│   ├── service/          # 各模型供应商调用适配
│   ├── static/           # 后端运行时静态资源
│   ├── tests/            # 后端 pytest 测试
│   ├── utils/            # 数据库、鉴权、请求校验、OpenAI 契约等工具
│   ├── app_config.yaml   # 后端默认配置
│   ├── config.py         # 配置加载和路径解析
│   └── main.py           # 后端入口，监听 0.0.0.0:2321
├── only-one-frontend/
│   ├── src/              # Vue 3 前端源码
│   ├── tests/            # Vitest 测试
│   ├── package.json
│   └── vite.config.ts    # dev 代理和 build 输出配置
├── docs/                 # 架构、运维、变更和待办文档
└── study/llmgw/          # LLM gateway 学习/演进参考工程
```

## 快速开始

### 1. 启动后端

```bash
conda create -n oneapi python=3.13
conda activate oneapi 

cd only-one-backend
pip install -r requirements.txt
python main.py
```

后端默认监听：

- 管理后台/后端托管入口：`http://127.0.0.1:2321/`
- 登录页：`http://127.0.0.1:2321/login`
- 健康检查：`http://127.0.0.1:2321/health`

默认初始化账号：

```text
用户名: stark
密码: admin@123
```

首次登录后需要重置密码。

### 2. 启动前端开发服务

```bash
cd only-one-frontend
pnpm install
pnpm run dev
```

访问：

- 前端开发入口：`http://127.0.0.1:5173/login`

`vite.config.ts` 已经把开发环境的 `/backend` 和 `/static` 代理到 `http://127.0.0.1:2321`，所以开发时需要同时启动后端。

如果不用 pnpm，也可以使用 npm：

```bash
cd only-one-frontend
npm install
npm run dev
```

### 3. 构建前端并交给后端托管

```bash
cd only-one-frontend
pnpm run build
```

构建输出目录由 `vite.config.ts` 指定为：

```text
only-one-backend/html/dist
```

构建完成后，只需要启动后端：

```bash
cd only-one-backend
python main.py
```

然后访问 `http://127.0.0.1:2321/`。后端会托管 `/assets`、`/images` 和 SPA fallback 路由。

## 管理后台页面

- `/login`：登录
- `/reset-password`：首次登录重置密码
- `/usage`：请求量、Token 和费用统计
- `/api-manage`：供应商、模型、价格、默认参数、模型测试
- `/key-manage`：网关调用 Key 管理
- `/chat-history`：请求历史、消息明细、工具调用和异常状态查看

未登录访问受保护页面时会跳转到 `/login`。

## 后端配置

默认配置文件是 `only-one-backend/app_config.yaml`。常用配置项：

| 配置 | 说明 |
| --- | --- |
| `database.use_db` | `sqlite` 或 `mysql`，默认 `sqlite` |
| `database.sqlite.db_path` | SQLite 数据库路径，默认 `./db/llm.db` |
| `database.mysql.*` | MySQL 连接参数 |
| `proxy.type` | `none`、`system` 或 `manual` |
| `proxy.url` | `manual` 代理地址 |
| `free_model.*` | 免费模型的 base URL、API Key 和模型名 |
| `aihubmix_discount_code` | Aihubmix 推理时代优惠码 |

常用环境变量：

| 环境变量 | 说明 |
| --- | --- |
| `PLLM_CONFIG_PATH` | 指定后端配置文件路径 |
| `PLLM_STATIC_PATH` | 覆盖后端 `/static` 目录 |
| `PLLM_FRONTEND_DIST_PATH` | 覆盖前端构建产物目录 |
| `PLLM_SESSION_SECRET` | 指定 session 签名密钥 |
| `PLLM_SESSION_HTTPS_ONLY` | 设置为 `true` 时 session cookie 仅走 HTTPS |
| `PLLM_FREE_MODEL_BASE_URL` | 覆盖免费模型 base URL |
| `PLLM_FREE_MODEL_API_KEY` | 覆盖免费模型 API Key |
| `PLLM_FREE_MODEL_MODEL` | 覆盖免费模型名 |

本机使用默认 SQLite 即可。切换 MySQL 时，先修改 `app_config.yaml` 的数据库配置，再启动后端，服务会按 `db/init_mysql.sql` 初始化表结构。

## 网关调用示例

先在管理后台的 Key 管理页面创建或启用一个 `sk-` 开头的调用 Key，再请求 OpenAI 兼容接口：

```bash
curl -s http://127.0.0.1:2321/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-v3.2",
    "messages": [
      {"role": "user", "content": "hi"}
    ],
    "temperature": 0.7,
    "max_tokens": 1024
  }'
```

模型名需要与后台模型管理中的 `model_name` 或 `model_id` 匹配。更多 curl 示例和 Windows 命令行注意事项见 `docs/ops/curlcmd.md`。

## 常用命令

后端：

```bash
cd only-one-backend
python main.py
pytest
```

前端：

```bash
cd only-one-frontend
pnpm run dev
pnpm run build
pnpm run typecheck
pnpm run lint
pnpm test
```

## 架构取舍

### 为什么不是直接使用 one-api

如果目标是对外提供服务、管理大量用户、做额度售卖或统一运营多个渠道，one-api 更合适。它已经具备成熟的用户/Token/渠道/配额/兑换码/分组能力。

如果目标是个人自用，one-api 的多租户和计费能力会带来额外心智成本。本项目更适合以下情况：

- 自己维护多个上游模型 Key。
- 想要一个本地 OpenAI-compatible API Base 给各类客户端复用。
- 更关心每次请求的完整审计，而不是用户余额和充值。
- 希望前后端代码结构简单，方便按个人习惯二次开发。

### 当前主要风险

- 默认配置和初始化数据中存在示例 Key，应在真实使用前替换或迁移到私有配置。
- 后端 CORS 当前允许 `*`，对外暴露前需要收紧。
- API Key 以数据库字段保存，未实现密钥托管或加密存储。
- SQLite 适合个人低并发，本项目没有 one-api 的 Redis、多机和批量写入优化。
- 目前没有完整 OpenAPI 文档和管理 API 文档。

