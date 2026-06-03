# 数据备份与迁移

## 数据存储位置

| 数据 | 位置 | 说明 |
|---|---|---|
| 数据库 | `backend/data/app.db` | SQLite 文件，包含所有学习记录 |
| 上传资料 | `backend/uploads/` | 上传的 PDF/Word/TXT/MD 原文件 |
| OCR 语言包 | `backend/tessdata/` | Tesseract 语言包（需单独安装） |
| 配置 | `backend/.env` | API Key 和应用配置 |

## 导出备份

点击侧边栏底部「导出数据备份」按钮，会下载一个 JSON 文件：

- 文件名：`math_agent_backup_YYYY-MM-DD.json`
- 包含：错题本、学习计划、真题题库、答题记录、聊天历史、题目解析历史、资料元数据
- **不包含**：上传的原文件（PDF/Word 等）和解析后的全文内容

## 导入恢复

点击侧边栏底部「导入备份」，选择 JSON 文件：

1. 预检：显示各模块数据量和冲突检测
2. 选择冲突策略：跳过（保留现有）/ 覆盖 / 保留两份
3. 确认导入

导入采用追加策略，不会清空现有数据。重复数据按规则跳过。

## 换电脑迁移

如果要在新电脑上完整迁移数据，需要复制以下内容：

### 1. 导出 JSON（学习记录）

通过界面「导出数据备份」按钮导出，在新电脑上「导入备份」恢复。

### 2. 复制 uploads 目录（上传的资料文件）

```bash
# 旧电脑
cp -r backend/uploads/ /外部存储/uploads/

# 新电脑
cp -r /外部存储/uploads/ backend/uploads/
```

> 导出的 JSON 只包含资料元数据（文件名、类型等），不含原文件。
> 如果不复制 uploads 目录，导入后资料的详情预览和分块检索将不可用。

### 3. 复制 SQLite 数据库（可选）

如果希望完整保留所有数据（包括分块索引、FTS 全文索引等），可以直接复制数据库文件：

```bash
cp backend/data/app.db /外部存储/app.db
# 新电脑
cp /外部存储/app.db backend/data/app.db
```

> 数据库和 JSON 导出二选一即可。直接复制数据库更完整，但要求新电脑的软件版本兼容。

### 4. OCR 语言包（如需 OCR 功能）

Tesseract OCR 语言包不包含在导出中。新电脑需要：

1. 安装 Tesseract OCR
2. 下载 `chi_sim.traineddata` 和 `eng.traineddata` 放入 `backend/tessdata/`
3. 在 `.env` 中配置 `TESSERACT_CMD` 路径

### 5. .env 配置

新电脑需要重新创建 `backend/.env` 并填入 API Key。API Key 不会出现在导出的 JSON 中。

## 注意事项

- API Key 只保存在本地 `.env` 文件中，导出备份不包含 API Key
- 导入不会覆盖复习策略配置（复习间隔）
- 真题答题记录的 question_id 会在导入时自动映射到新 ID
