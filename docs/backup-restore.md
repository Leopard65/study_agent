# 数据备份与迁移

## 数据存储位置

| 数据 | 位置 | 说明 |
|---|---|---|
| 数据库 | `backend/data/app.db` | SQLite 文件，包含所有学习记录 |
| 上传资料 | `backend/uploads/` | 上传的 PDF/Word/TXT/MD 原文件 |
| OCR 语言包 | `backend/tessdata/` | Tesseract 语言包（需单独安装） |
| 配置 | `backend/.env` | API Key 和应用配置 |

## 备份方式

### 方式一：完整备份 ZIP（推荐）

点击侧边栏底部「完整 ZIP」按钮，会下载一个 ZIP 文件：

- 文件名：`math_agent_backup_YYYY-MM-DD.zip`
- 包含：`backup.json`（学习记录 + 应用设置 + 学习会话）+ `manifest.json`（元信息）+ `uploads/`（上传的原文件）
- **用途**：整机迁移、灾难恢复，无需手动复制 uploads 目录
- **完整覆盖**：资料文件、错题、计划、真题、聊天记录、自定义复习间隔、学习会话记录

ZIP 内部结构：
```
math_agent_backup_YYYY-MM-DD.zip
├── manifest.json       # 备份元信息（版本、文件清单）
├── backup.json         # 学习记录（与 JSON 导出格式相同）
└── uploads/            # 上传的原文件
    ├── a1b2c3d4.pdf
    └── e5f6g7h8.txt
```

### 方式二：仅数据 JSON

点击侧边栏底部「数据 JSON」按钮，会下载一个 JSON 文件：

- 文件名：`math_agent_backup_YYYY-MM-DD.json`
- 包含：错题本、学习计划、真题题库、答题记录、聊天历史、题目解析历史、资料元数据、应用设置（复习间隔等）、学习会话记录
- **不包含**：上传的原文件（PDF/Word 等）和解析后的全文内容
- **用途**：轻量备份，仅保留学习记录和配置
- **JSON 导入时**：资料冲突的 overwrite 策略不会清空已有资料的文件和内容（因为 JSON 不含原文件）

## 导入恢复

### 导入完整备份 ZIP

点击侧边栏底部「导入 ZIP」，选择 ZIP 文件：

1. 预检：显示各模块数据量、文件数量、冲突检测
2. 选择冲突策略：跳过（保留现有）/ 覆盖 / 保留两份
3. 确认导入

导入过程：
- 恢复 `uploads/` 下的所有文件到 `backend/uploads/`
- 创建或更新资料记录，并自动触发后台解析（重建全文索引）
- 恢复错题、计划、真题等学习记录
- 路径安全校验：拒绝绝对路径、`..`、反斜杠逃逸，所有文件只能落到 `uploads/` 内

### 导入仅数据 JSON

点击侧边栏底部「导入 JSON」，选择 JSON 文件：

1. 预检：显示各模块数据量和冲突检测
2. 选择冲突策略：跳过（保留现有）/ 覆盖 / 保留两份
3. 确认导入

导入采用追加策略，不会清空现有数据。重复数据按规则跳过。

> **注意**：JSON 导入只恢复学习记录，不恢复上传文件。导入后资料详情预览和分块检索将不可用，除非原文件已存在于 `backend/uploads/`。

## 换电脑迁移

### 推荐方式：完整备份 ZIP

1. 旧电脑：点击「完整 ZIP」下载备份
2. 新电脑：安装应用，点击「导入 ZIP」选择备份文件
3. 完成！资料文件、学习记录全部恢复，后台自动重建索引

### 手动方式（高级用户）

如果需要更精细的控制：

#### 1. 导出 JSON + 复制 uploads

```bash
# 旧电脑
# 通过界面导出 JSON
cp -r backend/uploads/ /外部存储/uploads/

# 新电脑
# 通过界面导入 JSON
cp -r /外部存储/uploads/ backend/uploads/
```

#### 2. 直接复制 SQLite 数据库（可选）

如果希望完整保留所有数据（包括分块索引、FTS 全文索引等），可以直接复制数据库文件：

```bash
cp backend/data/app.db /外部存储/app.db
# 新电脑
cp /外部存储/app.db backend/data/app.db
```

> 数据库和 JSON 导出二选一即可。直接复制数据库更完整，但要求新电脑的软件版本兼容。

#### 3. OCR 语言包（如需 OCR 功能）

Tesseract OCR 语言包不包含在导出中。新电脑需要：

1. 安装 Tesseract OCR
2. 下载 `chi_sim.traineddata` 和 `eng.traineddata` 放入 `backend/tessdata/`
3. 在 `.env` 中配置 `TESSERACT_CMD` 路径

#### 4. .env 配置

新电脑需要重新创建 `backend/.env` 并填入 API Key。API Key 不会出现在任何导出中。

## 安全说明

- **API Key 保护**：导出备份（JSON 和 ZIP）均不包含 API Key
- **路径安全**：ZIP 导入时严格校验文件路径，防止路径穿越攻击
- **文件类型**：只允许恢复已知的文档类型（PDF/Word/TXT/MD）
- **不删除数据**：导入采用追加策略，不会清空现有数据

## 数据维护中心

侧边栏点击「数据维护」或访问 `/maintenance`，可以：

### 健康检查

查看数据健康摘要：
- 资料记录数、分块索引数、上传文件数
- 孤儿文件数（uploads 目录中未被任何资料引用的文件）
- 缺失文件数（资料引用但文件不在 uploads 目录）
- 解析失败的资料数
- 数据库大小、uploads 目录大小

### 安全清理

1. 点击「预览清理」查看可清理项（不实际删除）
2. 确认后点击「确认清理」执行

清理内容：
- **孤儿文件**：uploads 目录中未被 `materials.stored_filename` 引用的文件
- **无效解析任务**：关联的资料记录已不存在的解析任务
- **孤儿分块**：关联的资料记录已不存在的文本分块（同时清理对应的全文搜索索引）

安全保证：
- 不删除被任何资料引用的文件
- 不删除 `.env`、数据库、日志、脚本
- 不删除 uploads 目录外的任何文件
- 只删除允许的文件扩展名（PDF/Word/TXT/MD）

### 操作日志

查看最近的备份/导入/清理操作记录，包括操作类型、时间、结果摘要。不记录 API Key 或敏感内容。

## 建议维护流程

1. **定期备份**：每周或每月导出一次完整 ZIP 备份
2. **备份后检查**：导入备份后访问数据维护页面，确认数据健康
3. **清理孤儿文件**：长期使用后，删除/重试失败的资料可能留下孤儿文件，可安全清理
4. **恢复后验证**：从备份恢复后，检查「缺失文件」是否为 0，确认所有资料文件已恢复

## 学习会话导入策略

导入学习会话（study_sessions）时，系统会进行严格的数据校验：

- **duration_minutes**：只接受 plain int ≥ 0。`true`/`false`、浮点数、字符串（含 `"60"`）、负数、`None`/缺失 → 均按实际时长（ended_at − started_at）重算并返回 warning。`0` 也按实际时长重算。超过实际时长的 int 会被截断。
- **started_at**：缺失或无法解析 → 跳过，计入 `sessions_invalid`。
- **ended_at < started_at** → 跳过，计入 `sessions_invalid`。
- **活跃会话**（ended_at 为空）→ 导入时强制结束（以当前时间作为 ended_at）。如果 started_at 在未来导致 ended_at < started_at，也跳过。
- **subject**：非字符串转为空字符串，超长截断（上限 100 字符，与创建接口一致）。
- **note**：非字符串转为空字符串，超长截断（上限 500 字符，与创建接口一致）。
- **重复检测**：相同 started_at + subject + note 视为重复。

导入结果中区分：
- `sessions_imported`：成功导入数
- `sessions_skipped`：重复跳过数
- `sessions_invalid`：数据无效跳过数
- `sessions_warnings`：详细警告信息列表

## 复习间隔设置导入策略

- 只允许导入 `review_intervals` 键，其他设置键被忽略。
- 值必须为合法 JSON 数组，且通过 `validate_review_intervals` 校验（严格递增、1-365 范围、最多 10 项）。
- 含布尔值（如 `[true, 2]`）的数组会被拒绝。
- 无效设置计入 `settings_invalid`，不写入数据库。

## 注意事项

- ZIP 导入可选择是否覆盖复习间隔配置（overwrite 策略会覆盖，skip 策略保留现有）
- 真题答题记录的 question_id 会在导入时自动映射到新 ID
- ZIP 导入后，恢复的资料会自动触发后台解析，重建全文索引
- `keep_both` 策略下，资料文件名会添加"(副本)"后缀
- JSON 备份不含上传原文件，导入后资料预览不可用（除非原文件已在 uploads 目录）
- ZIP 备份含上传原文件，导入后自动恢复文件并触发后台解析
