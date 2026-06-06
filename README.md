# 考研长期陪跑学习助手

> **当前版本：MVP v0.7** — Web 端本地单用户学习工具，数据全部保存在你的电脑上，不上传到任何服务器。安卓端在独立仓库开发。

基于 AI 问答 + 资料库 RAG 的考研学习辅助工具，支持数学公式 LaTeX 渲染。覆盖「资料上传 → AI 问答/题目解析 → 加入错题本 → 今日复习 → 学习计划/工作台」的完整学习闭环。

## 这是什么工具？

- **单用户个人工具**：没有登录、注册、多用户或云端账号，你一个人用
- **数据在你电脑上**：学习记录存在本地 SQLite 数据库，上传的资料存在本地 `uploads/` 目录
- **API Key 你自己保管**：只保存在本地 `.env` 文件中，不上传到作者服务器
- **可选 AI 功能**：配置第三方 API Key 后解锁 AI 问答、题目解析、计划生成等；不配置也能用错题本、复习队列、资料管理等核心功能
- **支持 PWA**：可安装到桌面，获得类 App 体验

## 功能与 AI 依赖

| 功能 | 无需 AI Key | 需要 AI Key |
|---|:---:|:---:|
| 上传资料（PDF/Word/TXT/MD） | ✅ | |
| 资料库管理（搜索/阅读/删除/批量） | ✅ | |
| 错题本（录入/筛选/统计/复习间隔） | ✅ | |
| 今日复习队列（优先级排序/标记掌握） | ✅ | |
| 学习计划（手动添加/勾选完成） | ✅ | |
| 真题练习（手动录入/提交答案/加入错题本） | ✅ | |
| 学习工作台（任务/打卡/趋势/计时） | ✅ | |
| 全局搜索（跨模块检索） | ✅ | |
| 数据导出/导入备份（JSON + 完整 ZIP） | ✅ | |
| 数据维护中心（健康检查/清理/操作日志） | ✅ | |
| 扫描版 PDF OCR（识别图片中的文字） | ✅（需安装 Tesseract） | |
| AI 问答（自动检索资料库回答） | | ✅ |
| 题目解析（AI 返回解题步骤） | | ✅ |
| AI 生成学习计划 | | ✅ |
| AI 生成练习题 | | ✅ |

## 快速开始

### 前提条件

你需要安装 Python 和 Node.js：

- **Python 3.10+**：[python.org](https://www.python.org/downloads/) 下载安装，安装时勾选「Add to PATH」
- **Node.js 18+**：[nodejs.org](https://nodejs.org/) 下载 LTS 版本安装

### 方式一：Windows 一键启动（推荐）

下载或克隆项目后，在项目根目录打开 PowerShell，运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-windows.ps1
```

脚本会自动：检查 Python/Node 版本 → 创建虚拟环境 → 安装依赖 → 检查 `.env` → 启动后端和前端 → 打开浏览器。

**最简流程（无需 AI）**：直接运行脚本，错题本、复习队列、资料管理等核心功能即可使用。

**启用 AI 功能**：
1. 编辑 `backend\.env`，填入 `OPENAI_API_KEY=你的真实Key`
2. 重新运行启动脚本（API Key 在启动时读取，运行中修改不会生效）

**停止服务**：在启动窗口按任意键自动停止所有服务（含子进程），或另开终端运行 `scripts\stop-windows.ps1`。

> 出错时可查看日志：`scripts\backend.log`（后端 stdout+stderr）、`scripts\frontend.log`（前端）。
>
> 启动脚本支持参数：`-NoOpenBrowser`（不打开浏览器）、`-AutoStopAfterSeconds N`（N 秒后自动停止，用于测试）。

### 方式二：手动启动（所有平台）

**第一步：安装依赖**

```bash
# 下载项目
git clone <repo-url>
cd math_agent

# 后端
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
```

**第二步：配置 API Key（可选，不填也能用）**

```bash
cd ../backend
# Windows: copy .env.example .env
# Linux/Mac: cp .env.example .env
```

编辑 `backend/.env`，如需 AI 功能填入 `OPENAI_API_KEY`。支持任何 OpenAI-compatible API：

> **注意**：API Key 在后端启动时读取，修改 `.env` 后需要重启后端才能生效。

| 服务商 | OPENAI_BASE_URL | 说明 |
|---|---|---|
| DeepSeek | `https://api.deepseek.com` | 国内访问快，性价比高（默认） |
| OpenAI | `https://api.openai.com` | GPT 系列模型 |
| 本地 Ollama | `http://localhost:11434/v1` | 完全离线运行 |

> **不填 API Key 也能正常使用**：错题本、复习队列、资料管理、学习计划、真题练习、数据备份等核心功能都不需要 AI。侧边栏会显示「运行正常」或「⚠️ 需配置 API Key」（表示 AI 功能不可用但核心功能正常）。

**第三步：启动**

```bash
# 终端 1 — 后端
cd backend
.venv\Scripts\activate    # Linux/Mac: source .venv/bin/activate
python -m uvicorn app.main:app --reload --reload-dir app --port 8000

# 终端 2 — 前端
cd frontend
npm run dev
```

浏览器打开 **http://localhost:5173**

### 方式三：生产/类 App 单服务启动（Windows）

只启动 FastAPI 一个服务，FastAPI 直接托管前端静态资源，无需 Vite：

```powershell
# 先构建前端（首次需要）
cd frontend && npm run build && cd ..

# 启动单服务
powershell -ExecutionPolicy Bypass -File scripts\start-app-windows.ps1
```

浏览器打开 **http://127.0.0.1:8000**

> 与开发模式的区别：只有一个 Python 进程，前端静态文件由 FastAPI 直接托管。适合日常使用或部署到内网。
>
> - 首次运行会自动创建 `.venv` 并安装后端依赖（同开发启动脚本逻辑）。
> - `frontend/dist` 不存在时会自动 `npm run build`。
> - `/api/*` 路由不被前端 fallback 吃掉：未匹配的 API 路径返回 404 JSON，而非 `index.html`。
>
> 支持参数：`-NoOpenBrowser`、`-AutoStopAfterSeconds N`。

### 开始使用

1. **上传资料**：进入「资料库」页面，上传你的 PDF/Word/TXT/MD 学习资料
2. **手动录入错题**：进入「错题本」页面，录入做错的题目
3. **今日复习**：工作台会显示今日待复习的错题数量，点击进入复习队列
4. **导入备份**：如果之前有备份，点击侧边栏「导入 ZIP」或「导入 JSON」恢复数据

## 扫描版 PDF OCR（可选）

如果你的 PDF 是扫描版（图片型），需要安装 Tesseract OCR 才能识别其中的文字：

**安装 Tesseract：**

- **Windows**：下载 [UB-Mannheim 构建](https://github.com/UB-Mannheim/tesseract/wiki)，安装后在 `.env` 中配置 `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe`
- **Linux**：`sudo apt install tesseract-ocr tesseract-ocr-chi-sim`
- **Mac**：`brew install tesseract tesseract-lang`

**下载中文语言包：**

从 [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) 下载 `chi_sim.traineddata` 和 `eng.traineddata`，放入 `backend/tessdata/` 目录。

在 `.env` 中配置：

```env
OCR_ENABLED=true
OCR_LANG=chi_sim+eng
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSDATA_DIR=./tessdata
```

> 未安装 Tesseract 时，普通 PDF（文字型）和 TXT/MD 文件上传不受影响。

## 数据备份与迁移

详见 [docs/backup-restore.md](docs/backup-restore.md)。

**要点：**
- 侧边栏「完整 ZIP」→ 完整备份（学习记录 + 上传原文件 + 复习间隔 + 学习会话），推荐用于整机迁移
- 侧边栏「数据 JSON」→ 仅学习记录和配置（轻量备份，不含上传原文件）
- 侧边栏「导入 ZIP」→ 从完整备份恢复（自动恢复文件 + 重建索引 + 恢复设置）
- 侧边栏「导入 JSON」→ 从 JSON 恢复学习记录（资料 overwrite 不会清空已有文件内容）
- API Key 不包含在任何导出中，新电脑需重新配置
- 备份格式 v0.3 兼容导入 v0.2 格式的旧备份

## 数据安全

- **API Key**：只保存在本地 `backend/.env` 文件，不出现在导出备份中
- **学习数据**：存在本地 `backend/data/app.db`（SQLite），不上传到任何服务器
- **上传资料**：存在本地 `backend/uploads/`，以 UUID 重命名，不上传到任何服务器
- **AI 调用**：使用 AI 功能时，题目内容会发送到你配置的 API 服务商（如 DeepSeek），这是唯一的网络请求
- **无遥测**：本工具不收集任何使用数据

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `OPENAI_API_KEY` | — | API Key（AI 功能必填；留空可使用核心本地功能） |
| `OPENAI_MODEL` | `deepseek-v4-flash` | 模型名称 |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 前端访问地址 |
| `APP_TIMEZONE` | `Asia/Shanghai` | 时区 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/app.db` | 数据库路径 |
| `UPLOAD_DIR` | `./uploads` | 上传文件存储路径 |
| `MAX_UPLOAD_MB` | `50` | 单文件上传大小限制（MB） |
| `MATERIAL_PREVIEW_CHARS` | `5000` | 资料详情预览字符数 |
| `MATERIAL_PARSE_CONCURRENCY` | `1` | 后台解析并发数 |
| `OCR_ENABLED` | `true` | 是否启用 OCR |
| `OCR_LANG` | `chi_sim+eng` | OCR 识别语言 |
| `TESSERACT_CMD` | — | Tesseract 可执行文件路径 |
| `TESSDATA_DIR` | — | Tesseract 语言包目录 |
| `OCR_MIN_TEXT_CHARS` | `80` | 低于此字数触发 OCR |
| `OCR_MAX_PAGES` | `30` | OCR 最大页数 |

## 功能一览

| 页面 | 路径 | 功能 |
|---|---|---|
| 学习工作台 | `/` | 今日任务、连续打卡、今日复习数、学习时长、未掌握错题、专注计时、7/30 天趋势图 |
| AI 问答 | `/qa` | 对话式问答，自动检索资料库（RAG），LaTeX 渲染，参考资料可跳转 |
| 资料库 | `/materials` | 上传/解析/搜索/阅读/批量管理，后台异步解析，失败可重试 |
| 题目解析 | `/problems` | 输入题目，AI 返回解题步骤，可一键加入错题本 |
| 错题本 | `/errors` | 录入/筛选/统计，可配置复习间隔，LaTeX 渲染，统计图表 |
| 学习计划 | `/plan` | 手动添加 + AI 生成，按日分组，勾选完成 |
| 真题练习 | `/exam` | 题库管理，AI 出题，提交答案，一键加入错题本 |
| 今日复习 | `/review` | 优先级排序复习队列，展开解析，标记掌握/仍需复习/明日再来/跳过 |
| 全局搜索 | `/search` | 跨模块搜索，类型筛选，点击跳转定位 |
| 数据维护 | `/maintenance` | 数据健康摘要、孤儿文件清理、操作日志 |
| 命令面板 | Ctrl+K | 快速搜索页面和动作 |
| 侧边栏 | — | 折叠/展开，主题切换（浅色/深色/跟随系统） |

## 核心学习闭环

```
资料上传 → RAG 检索 → AI 问答/题目解析 → 加入错题本 → 今日复习队列 → 标记掌握
                                                    ↑                    ↑
                                          学习计划（手动/AI 生成）        真题练习 → 一键加入错题本
                                                    ↓                    │
                                          工作台勾选完成                   │
                                                    ↑                    │
                                          Dashboard 薄弱知识点 ←──────────┘
```

## 项目结构

```
math_agent/
├── backend/
│   ├── app/
│   │   ├── routers/          # API 路由
│   │   ├── services/         # 文档解析、LLM、OCR、搜索
│   │   ├── utils/            # 日期 helper
│   │   ├── config.py         # 环境变量读取
│   │   ├── database.py       # SQLAlchemy 引擎
│   │   ├── models.py         # 数据库表定义
│   │   ├── schemas.py        # Pydantic 模型
│   │   └── main.py           # FastAPI 入口
│   ├── data/app.db           # SQLite 数据库（自动生成）
│   ├── uploads/              # 上传文件存储
│   ├── tessdata/             # OCR 语言包（需手动下载）
│   ├── scripts/smoke_test.py # 冒烟测试
│   ├── .env                  # 配置（从 .env.example 复制）
│   ├── .env.example          # 配置模板
│   └── requirements.txt
├── frontend/
│   ├── src/                  # React 源码
│   ├── e2e/smoke.spec.ts     # E2E 测试
│   ├── vite.config.ts
│   └── package.json
└── docs/
    └── backup-restore.md     # 备份迁移指南
```

## 数据库表

| 表 | 用途 |
|---|---|
| `materials` | 资料元数据（文件名、类型、全文内容） |
| `material_chunks` | 资料分块（每 800-1200 字一个 chunk） |
| `chunks_fts` | FTS5 虚拟表（chunk 全文索引） |
| `chat_history` | AI 问答记录 |
| `error_book` | 错题本 |
| `study_plans` | 学习计划 |
| `problems` | 题目解析记录 |
| `exam_questions` | 真题题库 |
| `exam_attempts` | 真题作答记录 |
| `app_settings` | 应用配置（复习间隔等） |
| `study_sessions` | 学习会话记录 |

## API 端点

<details>
<summary>点击展开完整 API 列表</summary>

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | AI 问答（自动 RAG） |
| GET | `/api/chat/history` | 问答历史 |
| POST | `/api/materials/upload` | 上传资料 |
| GET | `/api/materials` | 资料列表（分页） |
| GET | `/api/materials/{id}` | 资料详情 |
| POST | `/api/materials/search` | 关键词检索 |
| DELETE | `/api/materials/{id}` | 删除资料 |
| POST | `/api/materials/bulk-delete` | 批量删除 |
| POST | `/api/materials/export-selected` | 导出选中资料元数据 |
| POST | `/api/problems/solve` | 题目解析 |
| GET | `/api/problems/history` | 解析历史 |
| POST | `/api/errors` | 添加错题 |
| GET | `/api/errors` | 错题列表 |
| GET | `/api/errors/stats` | 错题统计 |
| PATCH | `/api/errors/{id}` | 更新错题 |
| DELETE | `/api/errors/{id}` | 删除错题 |
| POST | `/api/plan` | 添加计划 |
| GET | `/api/plan` | 计划列表 |
| PATCH | `/api/plan/{id}` | 更新计划 |
| DELETE | `/api/plan/{id}` | 删除计划 |
| POST | `/api/plan/generate` | AI 生成计划 |
| GET | `/api/dashboard` | 工作台统计 |
| GET | `/api/dashboard/trends` | 学习趋势 |
| POST | `/api/sessions/start` | 开始学习会话 |
| POST | `/api/sessions/{id}/stop` | 结束学习会话 |
| GET | `/api/sessions/active` | 当前活跃会话 |
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/search` | 全局搜索 |
| GET | `/api/exam/questions` | 真题列表 |
| POST | `/api/exam/questions` | 添加真题 |
| POST | `/api/exam/generate` | AI 生成练习题 |
| GET | `/api/exam/questions/{id}` | 真题详情 |
| POST | `/api/exam/questions/{id}/attempt` | 提交答案 |
| POST | `/api/exam/questions/{id}/add-to-errors` | 加入错题本 |
| DELETE | `/api/exam/questions/{id}` | 删除真题 |
| GET | `/api/export/json` | 导出数据 JSON |
| GET | `/api/export/zip` | 导出完整备份 ZIP |
| POST | `/api/import/preview` | JSON 导入预检 |
| POST | `/api/import/json` | JSON 导入 |
| POST | `/api/import/zip/preview` | ZIP 导入预检 |
| POST | `/api/import/zip` | ZIP 导入 |
| GET | `/api/settings/review` | 获取复习间隔 |
| PUT | `/api/settings/review` | 更新复习间隔 |
| GET | `/api/review/queue` | 今日复习队列 |
| POST | `/api/review/{id}/action` | 复习动作 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/maintenance/health` | 数据维护健康摘要 |
| POST | `/api/maintenance/cleanup/preview` | 清理预览 |
| POST | `/api/maintenance/cleanup` | 执行清理 |
| GET | `/api/maintenance/logs` | 操作日志 |

</details>

## 开发验证

```bash
cd backend
.venv\Scripts\python.exe -m compileall app
.venv\Scripts\python.exe scripts\smoke_test.py

cd ../frontend
npm run lint
npm run build

# 首次运行 Playwright 前需要安装浏览器
npx playwright install chromium
npm run e2e
```

**Windows 启动脚本验证**（需要后端依赖已安装）：

```powershell
# 开发模式：自动启动 → 验证 → 停止，不打开浏览器
powershell -ExecutionPolicy Bypass -File scripts\test-windows-start.ps1

# 生产模式：单服务启动 → 验证 → 停止
powershell -ExecutionPolicy Bypass -File scripts\test-start-app-windows.ps1

# 手动测试启动脚本参数
powershell -ExecutionPolicy Bypass -File scripts\start-windows.ps1 -NoOpenBrowser -AutoStopAfterSeconds 3

# 测试停止脚本
powershell -ExecutionPolicy Bypass -File scripts\stop-windows.ps1
```

截至当前版本，后端冒烟测试 **1080 passed, 0 failed**，前端 E2E 测试 **21 passed**。

## License

MIT
