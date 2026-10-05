# CunDrop ◈

基于 **Cloudflare R2** 的个人网盘 / 图床 / 视频床。自用、不开放注册，一个密码登录，全端深色高级感 UI。

## 功能

- 📤 **拖拽上传**：浏览器直传 R2（预签名 URL），不经过服务器中转，单文件最大 5GB，实时进度条
- 🗂️ **文件库**：搜索、删除、存储统计
- 🔗 **分享链接**：`/f/xxxx` 短链，可设有效期（1 天 / 7 天 / 30 天 / 永久）与访问密码，可查看访问次数
- 🎬 **在线预览**：视频分享页带播放器（支持拖进度），图片/音频直接预览
- 🔒 **单用户鉴权**：无注册，密码登录 + 分享页独立密码
- 🗄️ **SQLite**：零依赖数据库，文件元数据与分享记录本地存储

## 快速开始

### 1. 准备 R2

1. 登录 [Cloudflare 控制台](https://dash.cloudflare.com/) → R2 → 创建 Bucket（例如 `cundrop`）
2. R2 → API → 创建 API 令牌，权限选 **对象读写**，记下 `Access Key ID` / `Secret Access Key` / `Account ID`

### 2. 部署

```bash
git clone https://github.com/<你的用户名>/cundrop.git
cd cundrop
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填入 R2 信息与登录密码
python app.py          # http://localhost:5000
```

生产环境建议用 gunicorn + nginx 反向代理（配好 HTTPS）：

```bash
gunicorn -w 2 -b 127.0.0.1:5000 app:app
```

### GitHub Actions 自动部署

仓库自带 `.github/workflows/deploy.yml`，在 Actions 页点 **Run workflow** 手动触发部署。

**前置工作（服务器上做一次）：**

```bash
sudo mkdir -p /opt/cundrop && sudo chown $USER /opt/cundrop
git clone <你的仓库地址> /opt/cundrop
# 把 deploy/cundrop.service 放到 /etc/systemd/system/（改好路径）
sudo systemctl daemon-reload && sudo systemctl enable --now cundrop
# .env 放到 /opt/cundrop/.env（不要进 Git）
```

**GitHub 仓库 Settings → Secrets and variables → Actions 里添加：**

| Secret | 说明 |
|---|---|
| `SSH_HOST` | 服务器 IP 或域名 |
| `SSH_PORT` | SSH 端口，一般 22 |
| `SSH_USER` | SSH 用户名 |
| `SSH_KEY` | SSH 私钥（对应服务器上已授权的公钥） |
| `DEPLOY_PATH` | 服务器上的部署目录，如 `/opt/cundrop` |

### 3. 环境变量

| 变量 | 说明 |
|---|---|
| `R2_ACCOUNT_ID` | Cloudflare 账号 ID |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | R2 API 令牌 |
| `R2_BUCKET` | Bucket 名 |
| `R2_ENDPOINT` | 可选，默认 `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `APP_PASSWORD` | 登录密码 |
| `SECRET_KEY` | Flask session 密钥，换成随机字符串 |
| `PORT` | 可选，默认 5000 |

## 工作原理

```
浏览器 --预签名PUT--> R2 (直传, 不经服务器)
浏览器 <--预签名GET-- R2 (分享页播放/下载, 支持 Range)
服务器只存: SQLite(文件元数据/分享记录) + 生成签名
```

## 安全建议

- 第一时间修改 `APP_PASSWORD`，生产环境务必走 HTTPS
- R2 API 令牌只给**对象读写**权限，不要给账号级权限
- `.env` 不要提交到 Git（已在 `.gitignore`）

## 开源协议

MIT
