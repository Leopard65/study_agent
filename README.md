# 考研长期陪跑学习助手

> **当前状态：MVP v0.1** — 基础学习闭环已打通，资料库支持扫描版 PDF OCR，真题练习仍在规划中。

基于 AI 问答 + 资料库 RAG 的考研学习辅助工具，支持数学公式 LaTeX 渲染。

当前版本已经覆盖「资料上传 → RAG 问答/题目解析 → 加入错题本 → 今日复习 → 学习计划/工作台」的完整闭环，适合作为个人本地学习助手继续迭代。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 19 + TypeScript + Vite + TailwindCSS 4 |
| 后端 | Python FastAPI + SQLAlchemy (async) |
| 数据库 | SQLite + FTS5 全文索引 |
| AI 接口 | OpenAI-compatible SDK（默认对接 DeepSeek） |
| 文档解析 | PyPDF2 + python-docx + chardet + PyMuPDF + Tesseract OCR |
| 公式渲染 | KaTeX + react-markdown + remark-math |

## 功能一览

| 页面 | 路径 | 功能 |
|---|---|---|
| 学习工作台 | `/` | 今日任务（可直接勾选）、连续打卡、今日复习数、未掌握错题统计、复习入口 |
| AI 问答 | `/qa` | 对话式问答，自动检索资料库（RAG），LaTeX 公式渲染 |
| 资料库 | `/materials` | 上传 PDF/Word/TXT/MD，分块索引，中文关键词检索，可查看资料详情和解析文本预览，删除时同步清理文件和索引 |
| 题目解析 | `/problems` | 输入题目，AI 返回完整解题步骤，可一键加入错题本 |
| 错题本 | `/errors` | 科目/章节/知识点/错误类型/标签/复习时间，掌握状态筛选，今日复习筛选，LaTeX 渲染 |
| 学习计划 | `/plan` | 手动添加 + AI 一键生成（JSON 解析，失败可查看原始返回），按日分组，勾选完成 |
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

# 可选：扫描版 PDF OCR
OCR_ENABLED=true
OCR_LANG=chi_sim+eng
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSDATA_DIR=./tessdata
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
python -m uvicorn app.main:app --reload --reload-dir app --port 8000
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
│   │   │   ├── ocr.py            # Tesseract OCR 配置和语言包检测
│   │   │   └── search.py         # 分块索引 + FTS5 + 中文 LIKE fallback
│   │   ├── config.py             # 环境变量读取
│   │   ├── database.py           # 异步 SQLAlchemy 引擎
│   │   ├── models.py             # 数据库表定义
│   │   ├── schemas.py            # Pydantic 请求/响应模型
│   │   └── main.py               # FastAPI 入口
│   ├── uploads/                  # 上传文件存储
│   ├── tessdata/                  # 本地 Tesseract 语言包（不入 git）
│   ├── scripts/smoke_test.py      # 非 AI 主链路冒烟测试
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
    │   ├── utils/date.ts          # 本地日期格式化
    │   ├── App.tsx
    │   ├── main.tsx
    │   └── index.css
    ├── vite.config.ts
    └── package.json
```

## 数据库表

| 表 | 用途 |
|---|---|
| `materials` | 资料元数据（文件名、类型、全文内容、stored_filename） |
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

## 核心学习闭环

```
资料上传 → RAG 检索 → AI 问答/题目解析 → 加入错题本 → 今日复习 → 标记掌握
                                                    ↑
                                          学习计划（手动/AI 生成）→ 工作台勾选完成
```

- **题目解析 → 错题本**：解析页面可一键将题目保存到错题本，自动设置复习日期
- **今日复习**：错题本支持"今日复习"筛选，工作台显示待复习数量并提供入口
- **学习计划**：支持手动添加和 AI 生成，按日期分组，工作台可直接勾选完成
- **健康检查**：侧边栏底部实时显示服务状态（正常/未配置 AI/异常）

## 前端体验

- **服务状态**：侧边栏底部调用 `GET /api/health`，显示"服务正常"/"未配置 AI"/"服务异常"
- **错误提示**：资料库、错题本、学习计划页面均有操作失败的红色提示块
- **防重复点击**：资料删除、错题标记/删除、计划添加/切换/删除均有 loading 状态，防止重复提交
- **LaTeX 渲染**：错题本、AI 问答、题目解析均支持数学公式渲染
- **资料列表分页**：资料库采用"加载更多"模式，每页 20 条，避免一次性拉取过多数据
- **资料库搜索**：搜索结果支持空状态提示和一键清空搜索
- **资料详情**：点击"查看"可弹窗展示资料元信息和解析文本预览，方便确认 PDF/OCR 是否成功

## 资料文件管理

- 上传文件以 UUID 重命名保存到 `backend/uploads/`，数据库记录 `stored_filename`
- 删除资料时同步清理：数据库记录 → 分块索引 → FTS5 条目 → 上传文件
- 文件路径经过 `os.path.commonpath` 校验，防止路径穿越

## 扫描版 PDF OCR

- 上传 PDF 时，先用 PyPDF2 提取文本
- 如果提取文字少于 `OCR_MIN_TEXT_CHARS`（默认 80 字）且 `OCR_ENABLED=true`，自动触发 OCR fallback
- OCR 使用 PyMuPDF 渲染页面（200 DPI），pytesseract 识别文字
- 默认识别语言 `chi_sim+eng`（简体中文 + 英文），可通过 `OCR_LANG` 配置
- 大 PDF 只处理前 `OCR_MAX_PAGES`（默认 30）页，避免卡死
- OCR 失败不会导致上传崩溃，回退到 PyPDF2 已提取的文本

### 安装 Tesseract OCR

OCR 功能需要本机安装 Tesseract：

- **Windows**：下载 [UB-Mannheim 构建](https://github.com/UB-Mannheim/tesseract/wiki)，安装后在 `.env` 中配置 `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`
- **Linux**：`sudo apt install tesseract-ocr tesseract-ocr-chi-sim`
- **Mac**：`brew install tesseract tesseract-lang`

中文识别需要安装 `chi_sim` 语言包。未安装 Tesseract 时，健康检查 `ocr_available` 为 `false`，普通 PDF/文本上传不受影响。

当前本地开发环境采用项目内语言包目录：

```env
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSDATA_DIR=./tessdata
OCR_LANG=chi_sim+eng
```

`backend/tessdata/*.traineddata` 不提交到 Git。新机器上需要自行放入 `chi_sim.traineddata` 和 `eng.traineddata`，或改用系统默认的 Tesseract `tessdata` 目录。

## 上传限制说明

- 单文件默认最大 50MB（前端 + 后端双重校验）
- 可通过环境变量 `MAX_UPLOAD_MB` 调整，例如 `MAX_UPLOAD_MB=100`
- 扫描版 PDF 仍建议 20MB / 30 页以内
- 资料数量目前没有硬限制，数据保存在本地 SQLite 和 `backend/uploads/`
- OCR 页数：扫描版 PDF 默认只 OCR 前 `OCR_MAX_PAGES=30` 页

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | AI 问答（自动 RAG） |
| GET | `/api/chat/history` | 问答历史 |
| POST | `/api/materials/upload` | 上传资料 |
| GET | `/api/materials` | 资料列表（支持 `limit`/`offset` 分页） |
| GET | `/api/materials/{id}` | 资料详情（含解析文本预览） |
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
| GET | `/api/health` | 健康检查（返回 database/upload_dir/ai_configured/model/status/ocr_available） |

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible API 地址 |
| `OPENAI_API_KEY` | — | API Key（必填） |
| `OPENAI_MODEL` | `deepseek-v4-flash` | 模型名称 |
| `OCR_ENABLED` | `true` | 是否启用扫描版 PDF OCR fallback |
| `OCR_LANG` | `chi_sim+eng` | Tesseract 识别语言 |
| `TESSERACT_CMD` | — | Tesseract 可执行文件路径（Windows 通常需要配置） |
| `TESSDATA_DIR` | — | Tesseract 语言包目录；可设为 `./tessdata` 使用项目本地语言包 |
| `OCR_MIN_TEXT_CHARS` | `80` | PyPDF2 提取文字少于此阈值时触发 OCR |
| `OCR_MAX_PAGES` | `30` | OCR 最多处理的 PDF 页数 |
| `MAX_UPLOAD_MB` | `50` | 单个上传文件最大大小，单位 MB |
| `MATERIAL_PREVIEW_CHARS` | `5000` | 资料详情接口返回的文本预览最大字符数 |

## 验证

```bash
cd backend
.venv\Scripts\python.exe -m compileall app
.venv\Scripts\python.exe scripts\smoke_test.py

cd ../frontend
npm run build
```

截至当前版本，本地冒烟测试覆盖 health、资料上传/检索/删除、资料列表分页、超大文件拒绝（413）、学习计划 CRUD、错题本 CRUD、工作台统计，结果为 `74 passed, 0 failed`。

## License

MIT
