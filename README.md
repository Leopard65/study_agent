# 考研长期陪跑学习助手

基于 AI 问答 + 资料库 RAG 的考研学习辅助工具，支持数学公式 LaTeX 渲染。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 19 + TypeScript + Vite + TailwindCSS 4 |
| 后端 | Python FastAPI + SQLAlchemy (async) |
| 数据库 | SQLite + FTS5 全文索引 |
| AI 接口 | OpenAI-compatible SDK（默认对接 DeepSeek） |
| 文档解析 | PyPDF2 + python-docx + chardet |
| 公式渲染 | KaTeX + react-markdown + remark-math |

## 功能一览

| 页面 | 路径 | 功能 |
|---|---|---|
| 学习工作台 | `/` | 今日任务、连续打卡、资料数、未掌握错题统计 |
| AI 问答 | `/qa` | 对话式问答，自动检索资料库（RAG），LaTeX 公式渲染 |
| 资料库 | `/materials` | 上传 PDF/Word/TXT/MD，分块索引，中文关键词检索 |
| 题目解析 | `/problems` | 输入题目，AI 返回完整解题步骤 |
| 错题本 | `/errors` | 科目/章节/知识点/错误类型/标签/复习时间，掌握状态筛选 |
| 学习计划 | `/plan` | 手动添加 + AI 一键生成（JSON 解析，失败可查看原始返回） |
| 真题练习 | `/exam` | 占位页面（规划中） |

## 快速开始

### 1. 环境要求

- Python 3.10+
- Node.js 18+

### 2. 克隆项目

```bash
git clone <repo-url>
cd math_agent
```

### 3. 后端配置

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
```

编辑 `backend/.env`，填入你的 API Key：

```env
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=sk-你的key
OPENAI_MODEL=deepseek-v4-flash
```

> 如需更强推理能力，可改为 `OPENAI_MODEL=deepseek-v4-pro`。
> 不要使用 `deepseek-chat` 或 `deepseek-reasoner`，它们将于 2026-07-24 弃用。

### 4. 前端安装

```bash
cd frontend
npm install
```

### 5. 启动

**终端 1 — 后端：**

```bash
cd backend
.venv\Scripts\activate
python -m uvicorn app.main:app --reload --port 8000
```

**终端 2 — 前端：**

```bash
cd frontend
npm run dev
```

访问 `http://localhost:5173`

## 项目结构

```
math_agent/
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   │   ├── chat.py           # AI 问答 + RAG
│   │   │   ├── dashboard.py      # 工作台统计
│   │   │   ├── errors.py         # 错题本 CRUD
│   │   │   ├── materials.py      # 资料上传/检索/删除
│   │   │   ├── plan.py           # 学习计划 CRUD + AI 生成
│   │   │   └── problems.py       # 题目解析
│   │   ├── services/
│   │   │   ├── doc_parser.py     # PDF/Word/TXT/MD 文本提取
│   │   │   ├── llm.py            # OpenAI SDK 调用封装
│   │   │   └── search.py         # 分块索引 + FTS5 + 中文 LIKE fallback
│   │   ├── config.py             # 环境变量读取
│   │   ├── database.py           # 异步 SQLAlchemy 引擎
│   │   ├── models.py             # 数据库表定义
│   │   ├── schemas.py            # Pydantic 请求/响应模型
│   │   └── main.py               # FastAPI 入口
│   ├── uploads/                  # 上传文件存储
│   ├── data/app.db               # SQLite 数据库（自动生成）
│   ├── .env                      # 环境变量（不入 git）
│   ├── .env.example              # 环境变量示例
│   └── requirements.txt
│
└── frontend/
    ├── src/
    │   ├── api/client.ts         # axios 请求封装
    │   ├── components/
    │   │   ├── ChatMessage.tsx    # 对话消息气泡
    │   │   ├── FileUpload.tsx     # 文件上传组件
    │   │   ├── LatexRenderer.tsx  # KaTeX + Markdown 渲染
    │   │   └── Sidebar.tsx        # 侧边导航
    │   ├── pages/
    │   │   ├── Dashboard.tsx      # 学习工作台
    │   │   ├── QA.tsx             # AI 问答
    │   │   ├── Materials.tsx      # 资料库
    │   │   ├── ProblemSolver.tsx  # 题目解析
    │   │   ├── ErrorBook.tsx      # 错题本
    │   │   ├── StudyPlan.tsx      # 学习计划
    │   │   └── ExamPractice.tsx   # 真题练习（占位）
    │   ├── App.tsx
    │   ├── main.tsx
    │   └── index.css
    ├── vite.config.ts
    └── package.json
```

## 数据库表

| 表 | 用途 |
|---|---|
| `materials` | 资料元数据（文件名、类型、全文内容） |
| `material_chunks` | 资料分块（每 800-1200 字一个 chunk） |
| `chunks_fts` | FTS5 虚拟表（chunk 全文索引） |
| `chat_history` | AI 问答记录 |
| `error_book` | 错题本（13 个字段） |
| `study_plans` | 学习计划 |
| `problems` | 题目解析记录 |

## RAG 检索策略

资料库检索采用两层策略：

1. **英文/ASCII 查询**：优先使用 SQLite FTS5 全文检索
2. **中文查询**：提取关键词后 fallback 到 LIKE 搜索
   - 去停用词（60+ 个常见中文停用词）
   - 优先匹配领域专业词（70+ 个，如卷积、傅里叶、拉普拉斯、矩阵等）
   - 多关键词分别搜索，合并去重

AI 问答时自动检索资料库，将相关 chunk 作为 context 发给模型，回答中引用资料来源。

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | AI 问答（自动 RAG） |
| GET | `/api/chat/history` | 问答历史 |
| POST | `/api/materials/upload` | 上传资料 |
| GET | `/api/materials` | 资料列表 |
| POST | `/api/materials/search` | 关键词检索 |
| DELETE | `/api/materials/{id}` | 删除资料 |
| POST | `/api/problems/solve` | 题目解析 |
| GET | `/api/problems/history` | 解析历史 |
| POST | `/api/errors` | 添加错题 |
| GET | `/api/errors` | 错题列表（支持 mastered/subject 筛选） |
| PATCH | `/api/errors/{id}` | 更新错题状态 |
| DELETE | `/api/errors/{id}` | 删除错题 |
| POST | `/api/plan` | 添加计划 |
| GET | `/api/plan` | 计划列表（支持 date 筛选） |
| PATCH | `/api/plan/{id}` | 更新计划状态 |
| DELETE | `/api/plan/{id}` | 删除计划 |
| POST | `/api/plan/generate` | AI 生成学习计划 |
| GET | `/api/dashboard` | 工作台统计数据 |
| GET | `/api/health` | 健康检查 |

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible API 地址 |
| `OPENAI_API_KEY` | — | API Key（必填） |
| `OPENAI_MODEL` | `deepseek-v4-flash` | 模型名称 |

## License

MIT
