# ◈ CunDrop

基于 **Cloudflare Workers + R2 + D1** 的个人网盘 / 图床。无服务器，推送到 GitHub 即自动部署。

## 功能

- 📁 文件库：上传、搜索、删除、存储统计
- ⬆ 上传：浏览器经**预签名 URL 直传 R2**，不经过 Worker 中转，单文件最大 5GB，带实时进度
- 🔗 分享链接 `/f/xxxx`：可设有效期、访问密码、最大查看次数
- 🎬 视频在线播放（支持拖进度，Range 分片）、图片 / 音频预览、一键下载
- 🔒 单密码登录（无注册），HMAC 会话 Cookie
- 🌙 深色高级感 UI

## 架构

```
浏览器 ──静态页面──▶ Worker (src/worker.js)
   │                      ├─ D1 (元数据: 文件/分享记录)
   │                      └─ R2 绑定 (删除/读取/Range 流)
   └─PUT 文件(预签名URL)─▶ R2 (直传, 不经过 Worker)
```

## 部署准备（一次性）

### 1. 创建 R2 存储桶

Cloudflare 后台 → **R2 对象存储** → 创建存储桶，取名 `cundrop`。

**配置 CORS**（部署拿到 Worker 域名后再配，见下方“自动部署”）：在存储桶 → 设置 → CORS 策略，填入：

```json
[
  {
    "AllowedOrigins": ["https://你的Worker域名"],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

> Worker 域名形如 `https://cundrop.你的子域名.workers.dev`，部署后可见；也可以绑定自己的域名。
> CORS 配好之前，上传功能会报跨域错误，其他功能不受影响。

### 2. 创建 R2 API Token

R2 页面 → **管理 R2 API 令牌** → 创建令牌：权限选 **对象读写**，指定存储桶 `cundrop`。
记下 **Access Key ID** 和 **Secret Access Key**（只显示一次）。

### 3. 创建 D1 数据库

```bash
npx wrangler d1 create cundrop
# 把输出的 database_id 填到 wrangler.toml
```

表结构会在 Worker 收到首次请求时自动创建，无需手动执行 SQL。

### 4. 填 wrangler.toml

- `database_id`：上一步 D1 的 ID（这是资源 ID 不是密钥，公开仓库中保留是常规做法）

### 5. 设置 Secrets

在 Worker 的 **设置 → 变量和机密** 里添加（或用 `npx wrangler secret put <名字>`）：

| Secret | 说明 |
|---|---|
| `ADMIN_PASSWORD` | 登录密码 |
| `SESSION_SECRET` | 任意随机长字符串（会话签名用） |
| `R2_ACCOUNT_ID` | R2 页面右侧的 Account ID |
| `R2_ACCESS_KEY_ID` | 第 2 步的 Key ID |
| `R2_SECRET_ACCESS_KEY` | 第 2 步的 Secret |

## 自动部署（推荐）

Cloudflare 后台 → **Workers 和 Pages** → **创建** → **连接到 Git**：

1. 选择本仓库 `cundrop`
2. 生产分支：`main`
3. 构建命令：`npm install`
4. 部署命令：`npx wrangler deploy`

之后每次 `git push` 到 main，Cloudflare 自动构建部署，无需任何手动操作。

> 注意：D1 的 `database_id` 和 Secrets 只需配置一次，自动部署不会覆盖它们。

### 手动部署

```bash
npm install
npx wrangler deploy
```

### 本地开发

```bash
cp .dev.vars.example .dev.vars   # 填入真实值
npm install
npx wrangler dev                 # 需先 wrangler login
```

## 分享链接说明

- 链接形如 `https://你的域名/f/aB3xYz9QwK2p`
- 可选：有效期（1/7/30 天或永久）、访问密码、最大查看次数
- 有密码的分享：访客输入密码后获得访问凭证才能读取文件流
- 删除文件会连带删除其所有分享链接

## 费用

Cloudflare 免费额度内完全够用：Workers 每天 10 万次请求、R2 10GB 存储、D1 5GB 存储。

## License

MIT
