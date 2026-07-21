# 跨境支付 FAQ 问答系统

基于 RAG 架构的跨境支付问答系统，集成 LangChain、ChromaDB 向量数据库和 Deepseek 大语言模型。

## 🚀 功能特性

- **智能文档切片**: 语义单元切片策略，支持 FAQ/API/错误码等文档类型自动识别
- **多格式支持**: PDF、DOC/DOCX、Excel、TXT、Markdown
- **向量检索**: ChromaDB 向量存储，高效相似度检索
- **Agent 工具**: 支持自定义工具扩展
- **简洁界面**: Streamlit 聊天界面

## ⚙️ 技术栈

- **后端**: FastAPI, LangChain, ChromaDB
- **前端**: Streamlit
- **LLM**: Deepseek
- **嵌入模型**: HuggingFace sentence-transformers

## 📂 项目结构

```
.
├── app/
│   ├── agents/           # Agent 和工具
│   ├── api/              # API 端点
│   ├── core/             # 配置
│   ├── models/           # 数据模型
│   ├── services/         # 业务服务
│   └── main.py           # 应用入口
├── data/uploads/RAG/     # 文档存储
├── frontend/             # Streamlit UI
└── scripts/              # 工具脚本
```

## 🛠️ 快速开始

### 1. 环境配置

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量（可选）
cp .env.example .env
# 编辑 .env 设置 COLLECTION_NAME=RAG
```

### 2. 启动 ChromaDB

```bash
# 使用 Docker
docker run -d -p 8000:8000 chromadb/chroma

# 或本地安装
pip install chromadb
chroma run --path ./chroma_data
```

### 3. 文档摄取

```bash
# 将文档放入 data/uploads/RAG/ 目录
# 运行摄取脚本
python scripts/reingest_documents.py
```

### 4. 启动服务

```bash
# 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 启动前端（新终端）
streamlit run frontend/chat_ui.py
```

访问 http://localhost:8501

## 🐳 Docker 部署

```bash
# 构建并启动
docker-compose up --build

# 后台运行
docker-compose up -d
```

## 📖 API 使用

### 聊天接口
```bash
curl -X POST http://localhost:8000/api/v1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"question": "支持哪些国家的卡"}'
```

### Agent 接口
```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "商户名是什么"}'
```

### 批量摄取
```bash
curl -X POST http://localhost:8000/api/v1/files/batch-ingest \
  -F "collection_name=RAG"
```

## 🆕 随时补充知识库 + 关键词飞书告警

### 1. 随时补充知识库
无需准备文件，直接追加一条问答/文本，立即写入向量库：
```bash
curl -X POST http://localhost:8000/api/v1/files/add-knowledge \
  -H "Content-Type: application/json" \
  -d '{"title": "如何申请退款", "content": "在商户后台-交易管理中发起退款……", "collection_name": "RAG"}'
```
内容会以 `## 标题 + 正文` 的小节格式落盘到 `data/uploads/RAG/`，既进入检索，也保留原文便于后续统一 reingest。

### 2. 咨询命中关键词 → 自动飞书推送
当用户走 `/api/v1/chat` 咨询、问题命中配置的关键词时，系统会**异步**：
1. 向飞书群推送一条告警消息（可 `@` 指定人员）；
2. 在飞书多维表格中新增一条记录（问题 / 回答 / 命中关键词 / 时间）。

推送与写表在后台执行，**不阻塞、不影响**本次问答返回；飞书侧任何异常都会被捕获记录。

关键词管理（预置见 `.env` 的 `FAQ_ALERT_KEYWORDS`，也可运行时增删并持久化）：
```bash
# 查看当前关键词与配置就绪状态
curl http://localhost:8000/api/v1/faq-alert/keywords

# 新增关键词（可批量）
curl -X POST http://localhost:8000/api/v1/faq-alert/keywords \
  -H "Content-Type: application/json" -d '{"keywords": ["投诉", "人工", "退款"]}'

# 删除一个运行时关键词（环境变量预置的无法删除）
curl -X DELETE http://localhost:8000/api/v1/faq-alert/keywords \
  -H "Content-Type: application/json" -d '{"keyword": "投诉"}'

# 手动测试推送（联调飞书配置用）
curl -X POST http://localhost:8000/api/v1/faq-alert/test \
  -H "Content-Type: application/json" -d '{"question": "我要投诉", "answer": "抱歉"}'
```

> 告警所需的飞书凭证、目标群、多维表格若未单独配置（`FAQ_ALERT_*`），会自动回退复用通用的 `FEISHU_*` 配置，做到近乎零额外配置即可启用。完整变量见 `.env.example`。

## 🔧 配置说明

环境变量（.env）:
- `COLLECTION_NAME`: 向量库集合名（默认 RAG）
- `CHROMA_HOST`: ChromaDB 地址（默认 localhost）
- `CHROMA_PORT`: ChromaDB 端口（默认 8000）
- `EMBEDDING_MODEL_NAME`: 嵌入模型名称

## 📝 文档切片策略

- **chunk_size**: 600 字符
- **chunk_overlap**: 120 字符
- **分隔符优先级**: 标题 > Q&A > 段落 > 句子
- **元数据增强**: 自动识别文档类型、分类、关键词
