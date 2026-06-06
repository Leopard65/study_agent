# 考研学习助手 — 安卓离线版

> **当前版本：Phase 1 骨架** — 不依赖电脑后端，数据保存在手机本地。

## 简介

这是考研学习助手的安卓离线版本，基于 Capacitor + React 构建。数据存储在手机本地 SQLite，AI 功能通过直连第三方 API 实现（需配置 API Key）。

## 技术栈

- **框架**: Capacitor 8 + React 19 + TypeScript
- **构建**: Vite 8 + Tailwind CSS v4
- **数据库**: @capacitor-community/sqlite（本地 SQLite）
- **AI**: 直连 OpenAI-compatible API（无需后端代理）

## 与桌面版的关系

| | 桌面 Web 版 | 安卓离线版（本分支） |
|---|---|---|
| 分支 | `main` | `mobile` |
| 运行方式 | 电脑启动 Python + Vite | 安装 APK |
| 数据位置 | 电脑本地 SQLite | 手机本地 SQLite |
| 资料格式 | PDF/Word/TXT/MD + OCR | Phase 1: TXT/MD |
| 后端依赖 | 需要 Python 后端 | 无需后端，直连 API |

## 开发状态

- [x] 数据库层（schema + CRUD）
- [x] LLM 客户端
- [x] 错题本服务
- [x] 学习计划服务
- [x] 学习会话计时
- [x] 资料导入/搜索
- [x] Dashboard 统计
- [x] 页面骨架（6 个页面 + 底部导航）
- [ ] 完善 UI 交互
- [ ] Android 原生构建
- [ ] 数据备份/恢复

## License

MIT
