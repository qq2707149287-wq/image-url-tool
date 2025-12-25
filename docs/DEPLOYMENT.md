# Coolify 部署指南

本文档介绍如何将此项目部署到 [Coolify](https://coolify.io/)。

---

## 🚀 快速部署步骤

### 1. 创建新服务
- 在 Coolify 控制面板中，选择 **Add Service > Docker > Dockerfile**
- 连接您的 Git 仓库

### 2. 配置环境变量
在 Coolify 的 **Environment Variables** 中添加以下变量：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `MINIO_ENDPOINT` | MinIO 服务器地址 | `http://minio:9000` 或 `https://your-minio.com` |
| `MINIO_ACCESS_KEY` | MinIO Access Key | `your-access-key` |
| `MINIO_SECRET_KEY` | MinIO Secret Key | `your-secret-key` |
| `MINIO_BUCKET_NAME` | 存储桶名称 | `images` |
| `SECRET_KEY` | JWT 签名密钥 (随机字符串) | `生成一个随机字符串` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID (可选) | `xxx.apps.googleusercontent.com` |

> ⚠️ **重要**: `SECRET_KEY` 必须是一个长随机字符串，用于签署 JWT Token。生产环境绝对不能使用默认值！

### 3. 配置持久化存储 (Volumes)
为了保留数据库和上传文件，需要挂载 Volume：

| 容器路径 | 说明 |
|----------|------|
| `/app/history.db` | SQLite 数据库 |
| `/app/uploads` | 本地上传目录 (如果不使用 MinIO) |

在 Coolify 中配置 **Persistent Storage**，将 `/app/history.db` 映射到一个持久卷。

### 4. 配置域名
1. 在 **Domains** 中添加您的域名，如 `img.yourdomain.com`。
2. Coolify 会自动生成 SSL 证书 (Let's Encrypt)。

### 5. Google OAuth 额外配置
如果启用 Google 登录，需要在 Google Cloud Console 的 OAuth Client 中添加：

- **Authorized JavaScript origins**: `https://img.yourdomain.com`
- **Authorized redirect URIs**: (本项目不使用，可留空)

---

## 🔧 常见问题

### 数据库丢失
确保 `/app/history.db` 已挂载到持久化存储。否则每次部署都会清空数据。

### Google 登录报错 `origin_mismatch`
检查 Google Cloud Console 中的 **Authorized JavaScript origins** 是否包含您的部署域名（包括协议和端口）。

### 图片无法访问 (MinIO 配置)
1. 确保 `MINIO_ENDPOINT` 可以从 Coolify 容器内访问。
2. 如果 MinIO 也部署在 Coolify 上，使用 Docker 网络名 (如 `http://minio:9000`)。

---

## ✅ 部署前检查清单

- [ ] 环境变量已全部配置
- [ ] `history.db` 已挂载持久卷
- [ ] MinIO 服务可从容器内访问
- [ ] (可选) Google OAuth 域名已配置
- [ ] 域名已添加并生成 SSL 证书

部署成功后，访问您的域名即可使用！
