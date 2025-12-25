# Changelog

所有重要变更将记录在此文件中。

## [Unreleased]

### Added
- Google OAuth 登录支持
- 用户头像显示 (从 Google 账号获取)
- Admin 模式 (管理员可管理所有图片)
- 密码强度提示 (注册时)
- 启动时配置警告 (SECRET_KEY / GOOGLE_CLIENT_ID)

### Changed
- 优化数据库迁移逻辑 (SQLite UNIQUE 列兼容)
- 更新 `.env.example` 添加新配置项

### Fixed
- 修复 `google_id` 列迁移在旧数据库上失败的问题

---

## [1.0.0] - 2024-xx-xx

### Added
- 初始版本
- 图片上传、历史管理
- MinIO 存储集成
- 私有/共享模式
