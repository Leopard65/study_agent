# 考研学习助手 — 安卓原生版

> 纯原生 Android 应用，数据保存在手机本地，无需电脑后端。AI 功能通过直连 OpenAI-compatible API 实现。

## 简介

考研学习助手的安卓原生版本，基于 Kotlin + Jetpack Compose 构建。覆盖错题本、间隔复习、学习计划、资料管理、AI 问答等核心功能，数据存储在手机本地 Room 数据库中。

## 与桌面 Web 版的关系

| | 桌面 Web 版 (`main` 分支) | 安卓原生版 (`mobile` 分支) |
|---|---|---|
| 语言 | Python + TypeScript | Kotlin |
| UI | React + Tailwind CSS | Jetpack Compose + Material 3 |
| 数据库 | SQLAlchemy + SQLite | Room + SQLite |
| 运行方式 | 电脑启动 Python + Vite | 安装 APK |
| 后端依赖 | 需要 Python 后端 | 无需后端 |
| AI 调用 | 后端代理 OpenAI SDK | OkHttp 直连 API |

两端数据库 schema 设计一致（11 张表），支持相同的学习闭环。

## 技术栈

| 层级 | 技术 |
|---|---|
| 语言 | Kotlin 2.0, Java 11 target |
| UI | Jetpack Compose (BOM 2024.09), Material 3 |
| 导航 | Navigation Compose 2.7 |
| 数据库 | Room 2.6.1 (KSP annotation processing) |
| 网络 | OkHttp 4.12 |
| 安全 | AndroidX Security Crypto (AES256_GCM EncryptedSharedPreferences) |
| 异步 | Kotlin Coroutines 1.8.1 |
| 构建 | AGP 8.11.2, KSP 2.0.21 |
| 最低版本 | Android 8.0 (API 26) |
| 目标版本 | Android 16 (API 36) |

## 架构

```
MVVM + 手动依赖注入

data/
├── ai/              # AI 集成（OpenAI-compatible API）
│   ├── OpenAiApi.kt         # OkHttp HTTP 客户端
│   └── AiRepository.kt      # AI 调用逻辑 + 错误处理
├── backup/          # JSON 备份/恢复
│   └── BackupService.kt     # 全量 DB 导出导入
├── local/           # 本地存储
│   ├── MathAgentDatabase.kt # Room 数据库（11 张表，v4）
│   ├── SecureSettingsStore.kt # EncryptedSharedPreferences
│   ├── LegacyApiKeyMigrator.kt # API Key 迁移（Room → 加密存储）
│   ├── dao/         # 11 个 DAO
│   └── entity/      # 11 个 Entity
├── material/        # 资料导入
│   └── MaterialImportService.kt # 文本文件导入 + 分块
└── repository/      # 10 个 Repository

domain/
└── model/Models.kt  # 领域模型（type alias → Entity）

ui/
├── navigation/      # 导航图 + 路由定义
├── screens/         # 7 个 Compose 页面
└── viewmodel/       # 10 个 ViewModel + Factory
```

## 页面

| 页面 | 路由 | 功能 |
|---|---|---|
| 工作台 | `dashboard` | 学习概览、快速入口 |
| 错题本 | `errors` | 错题列表、筛选、统计 |
| 错题详情 | `error_detail/{id}` | 编辑错题、查看复习记录 |
| 今日复习 | `review` | SM-2 间隔复习队列 |
| 学习计划 | `plans` | 计划管理、按日分组 |
| 资料 | `materials` | 文本资料导入、分块检索 |
| 搜索 | `search` | 跨模块搜索 |
| 设置 | `settings` | API Key 配置、复习间隔、备份 |

底部导航 5 个 Tab：工作台、错题本、今日复习、学习计划、资料

## 数据库（11 张表）

| 表 | 用途 |
|---|---|
| `materials` | 资料元数据（标题、科目、文件信息） |
| `material_chunks` | 资料分块（FK → materials, CASCADE） |
| `error_entries` | 错题 |
| `review_records` | 复习调度（SM-2 算法，FK → error_entries, CASCADE） |
| `study_plans` | 学习计划 |
| `chat_messages` | AI 对话历史 |
| `problem_records` | 题目解析记录 |
| `exam_questions` | 真题题库 |
| `exam_attempts` | 答题记录 |
| `app_settings` | 应用配置（key-value） |
| `backup_logs` | 备份操作日志 |

当前 schema 版本：v4，包含 3 次自动迁移。

## 核心功能

### SM-2 间隔复习

```
easeFactor = 2.5（最低 1.3）
rep 0 → 1 天后复习
rep 1 → 6 天后复习
rep 2+ → interval × easeFactor
```

### AI 集成

- 直连 OpenAI-compatible API（`/chat/completions`）
- 默认模型：`gpt-4o-mini`
- API Key 存储在 `EncryptedSharedPreferences`（AES256_GCM）
- 备份导出时显式排除 API Key
- 错误信息自动脱敏，防止 Key 泄露

### 资料导入

- 支持：txt, json, csv, md, xml, html, yaml, log, code 等文本格式
- 不支持：PDF, Word, 图片等二进制格式
- 按 ~1000 字自动分块（段落/句子/单词边界）

### 备份恢复

- JSON 全量导出/导入
- 包含所有学习记录和配置（不含 API Key）
- `BackupLog` 记录每次操作

## 测试

| 类型 | 文件数 | 覆盖范围 |
|---|---|---|
| Instrumented (androidTest) | 12 | DAO、ViewModel、Repository、Migration、Compose UI、Settings |
| Unit (test) | 6 | AI Repository、API Client、Backup UI、Review Repository、Search ViewModel |

使用 MockWebServer 测试 HTTP 调用，Room in-memory 数据库测试 DAO。

## 开发状态

- [x] 数据库层（Room 11 张表 + 4 次迁移）
- [x] 全部 Repository（10 个）
- [x] AI 集成（OkHttp + OpenAI API）
- [x] 加密存储（API Key → EncryptedSharedPreferences）
- [x] SM-2 间隔复习
- [x] 资料导入 + 分块
- [x] JSON 备份/恢复
- [x] 7 个 Compose 页面 + 底部导航
- [x] 18 个测试（12 instrumented + 6 unit）
- [ ] PDF/Word 资料支持
- [ ] OCR 图片识别
- [ ] RAG 检索增强（embedding 向量搜索）
- [ ] 真题练习功能完善
- [ ] Release 签名 + ProGuard 混淆

## License

MIT
