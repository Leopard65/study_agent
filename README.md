# 考研长期陪跑学习助手

> **当前状态：MVP v0.2** — 基础学习闭环已打通，资料库支持扫描版 PDF OCR，真题练习已实现 MVP。

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
| 学习工作台 | `/` | 今日任务（可直接勾选）、连续打卡、今日复习数、今日学习时长、未掌握错题统计、复习入口、专注计时、7/30 天学习趋势图表 |
| AI 问答 | `/qa` | 对话式问答，自动检索资料库（RAG），LaTeX 公式渲染 |
| 资料库 | `/materials` | 上传 PDF/Word/TXT/MD，分块索引，中文关键词检索，可查看资料详情和解析文本预览，删除时同步清理文件和索引 |
| 题目解析 | `/problems` | 输入题目，AI 返回完整解题步骤，可一键加入错题本 |
| 错题本 | `/errors` | 科目/章节/知识点/错误类型/标签/复习时间，掌握状态筛选，今日复习筛选，可配置复习间隔（默认 1/3/7/14 天），LaTeX 渲染，统计分析（科目/错误类型/知识点分布、30 天趋势） |
| 学习计划 | `/plan` | 手动添加 + AI 一键生成（JSON 解析，失败可查看原始返回），按日分组，勾选完成 |
| 真题练习 | `/exam` | 真题题库（按科目/年份/标签筛选），AI 生成练习题草稿（检索资料库辅助出题），逐题预览确认后保存，提交答案，查看参考答案与解析，一键加入错题本，LaTeX 渲染 |
| 全局搜索 | `/search` | 跨模块搜索资料/错题/计划/真题/问答/解析，支持类型筛选，点击跳转并定位到具体数据 |
| 命令面板 | Ctrl+K | 快速搜索页面和常用动作，键盘导航，支持专注计时和数据导出快捷入口 |
| 侧边栏 | — | 可折叠（仅显示图标），主题切换（浅色/深色/跟随系统），偏好保存在 localStorage |

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
│   │   │   ├── exam.py           # 真题练习 CRUD + 答题 + 加入错题本 + AI 生成
│   │   │   ├── export.py         # 数据导出 JSON
│   │   │   ├── import_data.py    # 数据导入恢复
│   │   │   ├── materials.py      # 资料上传/检索/详情/删除
│   │   │   ├── settings.py       # 复习策略配置
│   │   │   ├── plan.py           # 学习计划 CRUD + AI 生成
│   │   │   ├── problems.py       # 题目解析
│   │   │   ├── search.py         # 全局搜索
│   │   │   ├── sessions.py       # 学习会话/专注计时
│   │   ├── services/
│   │   │   ├── doc_parser.py     # PDF/Word/TXT/MD 文本提取
│   │   │   ├── llm.py            # OpenAI SDK 调用封装
│   │   │   ├── ocr.py            # Tesseract OCR 配置和语言包检测
│   │   │   └── search.py         # 分块索引 + FTS5 + 中文 LIKE fallback
│   │   ├── utils/
│   │   │   └── date.py           # 时区统一 helper（local_today/local_date_obj）
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
    │   │   ├── CommandPalette.tsx # 命令面板（Ctrl+K）
    │   │   ├── FileUpload.tsx     # 文件上传组件
    │   │   ├── LatexRenderer.tsx  # KaTeX + Markdown 渲染
    │   │   └── Sidebar.tsx        # 侧边导航（支持折叠/主题切换）
    │   ├── hooks/
    │   │   └── usePreferences.tsx # 界面偏好 context（侧边栏折叠/主题模式）
    │   ├── pages/
    │   │   ├── Dashboard.tsx      # 学习工作台
    │   │   ├── QA.tsx             # AI 问答
    │   │   ├── Materials.tsx      # 资料库
    │   │   ├── ProblemSolver.tsx  # 题目解析
    │   │   ├── ErrorBook.tsx      # 错题本
    │   │   ├── StudyPlan.tsx      # 学习计划
    │   │   ├── ExamPractice.tsx   # 真题练习
    │   │   └── SearchPage.tsx     # 全局搜索
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
| `error_book` | 错题本（含 review_count 复习次数） |
| `study_plans` | 学习计划 |
| `problems` | 题目解析记录 |
| `exam_questions` | 真题题库（标题、科目、年份、题目、答案、解析、标签） |
| `exam_attempts` | 真题作答记录（关联 question_id，含 user_answer 和 is_correct） |
| `app_settings` | 应用配置键值表（key/value/updated_at，当前存复习间隔） |
| `study_sessions` | 学习会话记录（subject/note/started_at/ended_at/duration_minutes） |

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
                                                    ↑              ↑
                                          学习计划（手动/AI 生成）  真题练习 → 一键加入错题本
                                                    ↓
                                          工作台勾选完成
```

- **题目解析 → 错题本**：解析页面可一键将题目保存到错题本，自动设置复习日期
- **真题练习 → 错题本**：真题页面可一键将题目加入错题本，打通真题练习与复习闭环
- **AI 生成练习题**：输入知识点主题，可选检索资料库辅助出题，生成草稿后逐题预览确认再保存到题库
- **今日复习**：错题本支持"今日复习"筛选，工作台显示待复习数量并提供入口
- **自动复习节奏**：标记掌握后自动推进下次复习日期，间隔 1→3→7→14 天；改回未掌握则重新进入今日复习
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

## 数据导出/导入/备份

- 侧边栏底部"导出数据备份"按钮，一键导出全部学习数据为 JSON 文件
- 导出内容：资料元数据（不含原文和上传文件）、错题本、学习计划、真题题库、答题记录、聊天历史、题目解析历史
- 文件名格式：`math_agent_backup_YYYY-MM-DD.json`
- 支持导入恢复：选择备份文件 → 预检摘要 → 确认导入
- 导入采用追加/跳过重复策略（错题按 question+error_type，计划按 date+subject+task，真题按 title+question），不清空现有数据
- 真题答题记录的 question_id 自动映射到导入后的新 ID
- 资料只导入元数据，不导入内容和上传文件
- 不覆盖复习策略配置

## 学习趋势洞察

- Dashboard 底部展示最近 7/30 天学习趋势
- 三组条形图：计划完成（已完成/总数）、真题练习（正确/总次数）、错题动态（新增/待复习）
- `errors_review_due` 口径：`next_review_date == 当日` 且 `mastered=false`
- 纯 CSS 实现，无图表库依赖，移动端不溢出

## 错题统计分析

- 错题本页面可展开"错题统计分析"面板
- 概览卡片：总错题、已掌握、未掌握、今日待复习
- 科目分布、错误类型分布、知识点 Top 10 条形图
- 最近 30 天新增错题趋势图
- 空值字段归为"未分类"，分布取前 10
- `due_today` 口径与 Dashboard 今日复习一致（`next_review_date <= today` 且 `mastered=false`）
- 纯 CSS 条形图实现，无图表库依赖，支持深色模式

## 全局搜索

- 统一搜索入口 `/search`，同时检索资料、错题、学习计划、真题、聊天历史、题目解析
- 支持按类型筛选（materials/errors/plans/exam/chat/problems）
- 资料搜索复用现有 FTS5 + LIKE 检索，其他表用 LIKE 搜索关键字段
- snippet 为纯文本截断，不含 HTML 标签
- 点击结果跳转到对应页面并定位到具体数据（资料自动打开详情弹窗，错题自动展开+蓝色高亮，计划自动滚动+高亮，真题自动展开）

## 学习会话/专注计时

- Dashboard 专注计时组件：输入科目和备注，开始/结束学习会话
- 进行中显示实时计时（前端每秒刷新），页面刷新后自动恢复 active 状态
- 结束后计算 `duration_minutes`，同一时间只允许一个 active 会话
- Dashboard 卡片新增"今日学习"分钟数
- 学习趋势图新增每日学习分钟数条形图
- 时间使用 APP_TIMEZONE 对应时区

## 命令面板

- 按 Ctrl+K（Mac: Cmd+K）或点击侧边栏"命令面板"按钮打开
- 支持关键词搜索所有页面和常用动作
- 键盘上下选择、Enter 执行、Esc 关闭
- 包含 10 个内置命令：打开各页面、开始专注计时、导出数据备份
- 纯 CSS 实现，无 UI 库依赖，支持无障碍属性（role=dialog/combobox/listbox/option）

## 界面偏好设置

- 侧边栏可折叠：折叠后只显示图标，保留 tooltip 和快捷操作
- 主题模式：浅色 / 深色 / 跟随系统（`prefers-color-scheme`）
- 设置保存在 `localStorage`（key: `math_agent_preferences`），无需后端
- 深色模式覆盖：Dashboard、错题本、学习计划、真题练习、全局搜索、命令面板等主要页面
- Sidebar 底部提供折叠按钮和主题切换控件

## 复习策略配置

- 复习间隔可自定义，默认 `[1, 3, 7, 14]` 天
- 通过 `GET /api/settings/review` 查看、`PUT /api/settings/review` 修改
- 校验规则：1-10 个正整数，每个 1-365，严格递增
- 超过配置长度时使用最后一个间隔（如默认配置下第 5 次掌握仍为 +14 天）
- 错题本页面提供轻量设置入口，编辑为逗号分隔数字即可

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/chat` | AI 问答（自动 RAG，sources 含 material_id/filename/snippet） |
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
| GET | `/api/errors/stats` | 错题统计分析（总数/掌握/待复习、科目/错误类型/知识点分布、30 天新增趋势） |
| PATCH | `/api/errors/{id}` | 更新错题状态 |
| DELETE | `/api/errors/{id}` | 删除错题 |
| POST | `/api/plan` | 添加计划 |
| GET | `/api/plan` | 计划列表（支持 date 筛选） |
| PATCH | `/api/plan/{id}` | 更新计划状态 |
| DELETE | `/api/plan/{id}` | 删除计划 |
| POST | `/api/plan/generate` | AI 生成学习计划 |
| GET | `/api/dashboard` | 工作台统计数据（含 today_review_errors） |
| GET | `/api/dashboard/trends` | 最近 7/30 天学习趋势（计划完成、错题、真题、学习时长） |
| POST | `/api/sessions/start` | 开始学习会话 |
| POST | `/api/sessions/{id}/stop` | 结束学习会话 |
| GET | `/api/sessions/active` | 获取当前进行中的会话 |
| GET | `/api/sessions` | 学习会话列表 |
| GET | `/api/search` | 全局搜索（资料/错题/计划/真题/问答/解析，支持类型过滤） |
| GET | `/api/exam/questions` | 真题列表（支持 subject/year/tag 筛选） |
| POST | `/api/exam/questions` | 添加真题 |
| POST | `/api/exam/generate` | AI 生成练习题草稿（不写入数据库） |
| GET | `/api/exam/questions/{id}` | 真题详情 |
| POST | `/api/exam/questions/{id}/attempt` | 提交答案 |
| POST | `/api/exam/questions/{id}/add-to-errors` | 一键加入错题本 |
| DELETE | `/api/exam/questions/{id}` | 删除真题（级联删除作答记录） |
| GET | `/api/export/json` | 导出全部学习数据为 JSON（不含资料原文和上传文件） |
| POST | `/api/import/preview` | 预检导入备份文件，返回可导入数量摘要（不写入数据库） |
| POST | `/api/import/json` | 导入备份数据（追加/跳过重复，返回 inserted/skipped 摘要） |
| GET | `/api/settings/review` | 获取复习间隔配置（默认 [1,3,7,14]） |
| PUT | `/api/settings/review` | 更新复习间隔配置 |
| GET | `/api/health` | 健康检查（返回 database/upload_dir/ai_configured/model/status/ocr_available） |

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | OpenAI-compatible API 地址 |
| `OPENAI_API_KEY` | — | API Key（必填） |
| `OPENAI_MODEL` | `deepseek-v4-flash` | 模型名称 |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | CORS 允许来源（逗号分隔） |
| `APP_TIMEZONE` | `Asia/Shanghai` | 应用时区（用于工作台统计和复习日期计算） |
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
npm run lint
npm run build
```

截至当前版本，本地冒烟测试覆盖 health、资料上传/检索/详情/删除、资料列表分页、详情截断预览、搜索 limit 边界、超大文件拒绝（413）、OCR fallback 图片型 PDF 识别（含内容断言）、学习计划 CRUD、错题本 CRUD、自动复习节奏（使用统一时区 helper）、工作台统计（含 today_review_errors 时区一致性、未来日期不计入复习数）、输入校验（空值/格式/范围 422，含 chat 和 plan/generate 边界值及纯空白科目拒绝）、搜索片段安全、真题练习 CRUD（创建/列表/筛选/详情/提交答案/加入错题本/删除级联）、真题输入校验（空标题/空题目/错误年份格式/不存在 ID 404）、真题加入错题本去重（重复添加返回 409）、AI 生成练习题草稿（count 越界/空 topic 422、无 API key 503、JSON 解析失败返回 parse_error、mock 成功不写入数据库）、数据导出 JSON（endpoint 200、关键字段存在、materials 不含完整 content、exam_attempts 结构完整、数据条数一致）、复习策略配置（默认值、PUT 校验、非递增/空/越界 422、自定义间隔影响错题复习日期、超出长度使用最后间隔）、数据导入恢复（预检不写 DB、导入后数量增加、二次导入跳过重复、exam_attempts question_id 映射、缺少字段 422、materials 不导入 content）、学习趋势洞察（days=7/30、非法 days 422、插入测试数据后统计正确）、全局搜索（空 q/limit 越界 422、类型过滤、插入各类数据后搜到对应类型、snippet 不含 HTML、搜索结果 ID 为实体 ID 非 chunk ID）、学习会话/专注计时（start/stop/active/list、重复 start 409、double stop 409、duration_minutes 计算、dashboard today_study_minutes、trends study_minutes）、错题统计分析（空数据结构校验、插入多科目/错误类型/知识点后统计正确、掌握/未掌握/待复习计数、分布列表 Top 10、30 天趋势序列长度和今日计数），结果为 `377 passed, 0 failed`。

## License

MIT
