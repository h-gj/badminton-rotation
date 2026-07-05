# 羽转 — 生产部署与启动指南

本文档说明如何在本机（Windows）通过 **Cloudflare Tunnel** 将 Django 应用暴露到公网域名。

## 架构概览

```
浏览器 / 手机
    │  HTTPS
    ▼
Cloudflare（DNS + CDN + TLS）
    │
    ▼
cloudflared（本机 Tunnel 客户端）
    │  HTTP
    ▼
Waitress（127.0.0.1:8000）
    │
    ▼
Django + SQLite + media/ 用户上传
```

- **静态文件**（CSS/JS）：WhiteNoise 打包到 `staticfiles/`，由 Django 直接提供。
- **用户上传**（头像等）：保存在项目 `media/` 目录，生产模式下由 Django 路由提供（见 `config/urls.py`）。
- **数据库**：SQLite 文件 `db.sqlite3`，需定期备份。

> 本方案要求运行 Django 和 Tunnel 的电脑**保持开机并联网**。Tunnel 进程退出后，外网将无法访问。

---

## 前置要求

| 项目 | 说明 |
|------|------|
| 操作系统 | Windows 10/11 |
| Python | 3.10+，已创建虚拟环境 `venv/` |
| 域名 | 已接入 Cloudflare（NS 指向 Cloudflare） |
| cloudflared | `winget install Cloudflare.cloudflared` |
| 项目路径 | 例：`C:\Users\69063\Projects\badminton-rotation` |

---

## 一、首次部署

### 1. 创建虚拟环境并安装依赖

```powershell
cd C:\Users\69063\Projects\badminton-rotation
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

### 2. 配置 `.env`

复制模板并按实际域名修改：

```powershell
copy .env.example .env
```

**生产环境必填项**（`DEBUG=0` 时缺一不可）：

```env
DEBUG=0
SECRET_KEY=请替换为随机长字符串
ALLOWED_HOSTS=goodminton.hgjhub.com
CSRF_TRUSTED_ORIGINS=https://goodminton.hgjhub.com
```

| 变量 | 说明 |
|------|------|
| `DEBUG` | 开发用 `1`，生产用 `0` |
| `SECRET_KEY` | Django 密钥，生产环境务必使用随机长字符串 |
| `ALLOWED_HOSTS` | 允许访问的域名，多个用英文逗号分隔 |
| `CSRF_TRUSTED_ORIGINS` | 必须带 `https://` 前缀，与域名一致 |

其余 `WECHAT_IMPORT_VISION_*` 为微信群截图导入功能的视觉 API 配置，按需填写。

> **注意**：修改 `.env` 后必须**保存文件**并**重启 Django**，配置才会生效。`.env` 中的值会覆盖系统环境变量。

### 3. 初始化数据库

```powershell
.\venv\Scripts\python manage.py migrate
.\venv\Scripts\python manage.py createsuperuser
```

### 4. 配置 Cloudflare Tunnel

#### 4.1 登录并创建 Tunnel

在 PowerShell 中依次执行：

```powershell
cloudflared tunnel login
cloudflared tunnel create badminton-rotation
cloudflared tunnel route dns badminton-rotation goodminton.hgjhub.com
```

- `tunnel login` 会在浏览器中授权，并在 `%USERPROFILE%\.cloudflared\` 生成 `cert.pem`。
- `tunnel create` 会输出 **Tunnel UUID**，并生成对应的 `{UUID}.json` 凭证文件。
- `route dns` 会在 Cloudflare 自动创建 CNAME 记录，将子域名指向该 Tunnel。

#### 4.2 编写 `config.yml`

将 `deploy/cloudflared-config.example.yml` 复制到：

```
%USERPROFILE%\.cloudflared\config.yml
```

> **文件名必须是 `config.yml`**，不要写成 `config.yml.yml`。

示例内容（替换为你的 UUID 和域名）：

```yaml
tunnel: eb796505-a489-4061-9c7a-7e9df5626660
credentials-file: C:\Users\69063\.cloudflared\eb796505-a489-4061-9c7a-7e9df5626660.json

ingress:
  - hostname: goodminton.hgjhub.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

最后一行 `http_status:404` 是 catch-all 规则，**不可省略**。

---

## 二、日常启动

需要**同时运行两个进程**，顺序不限，但 Django 必须先于外网访问就绪。

### 方式 A：双击启动（推荐）

| 文件 | 作用 |
|------|------|
| `start-django.bat` | 新开窗口，启动 Django 生产服务 |
| `start-tunnel.bat` | 新开窗口，启动 Cloudflare Tunnel |

### 方式 B：命令行启动

```powershell
# 窗口 1 — Django
scripts\run-production.cmd

# 窗口 2 — Tunnel
scripts\run-tunnel.cmd
```

### 启动后 Django 窗口应显示

```
[1/4] pip install...
[2/4] migrate...
[3/4] collectstatic...
[4/4] starting waitress on http://127.0.0.1:8000
```

### 启动后 Tunnel 窗口应显示

```
Starting tunnel... Press Ctrl+C to stop
```

### 验证

1. 本机：http://127.0.0.1:8000
2. 外网：https://goodminton.hgjhub.com
3. 登录、上传头像等功能正常

### 停止服务

在两个窗口分别按 `Ctrl+C`，或关闭窗口。

### 方式 C：一键启动两个服务

双击 **`start-all.bat`**：先启动 Django，等待约 15 秒后再启动 Tunnel（适合开机自启）。

### 方式 D：开机自动启动

1. 双击 **`scripts\install-startup.cmd`**
2. 会在「启动」文件夹创建快捷方式，指向 `start-all.bat`
3. **下次登录 Windows** 时会自动打开两个服务窗口

取消自启：双击 **`scripts\uninstall-startup.cmd`**

快捷方式位置：

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Yuzhuan Badminton.lnk
```

> 登录后需等 Django 完成 migrate / collectstatic（约 10–30 秒），外网才能稳定访问。若电脑刚开机网络未就绪，Tunnel 窗口可能短暂报错，一般会自动恢复；不行就手动再双击 `start-tunnel.bat`。

---

## 三、启动脚本说明

```
badminton-rotation/
├── start-django.bat          # 双击入口 → 调用 run-production.cmd
├── start-tunnel.bat          # 双击入口 → 调用 run-tunnel.cmd
├── start-all.bat             # 一键启动 Django + Tunnel（含间隔等待）
├── scripts/
│   ├── run-production.cmd    # pip install → migrate → collectstatic → waitress
│   ├── run-production.ps1    # PowerShell 版（同上）
│   ├── run-tunnel.cmd        # cloudflared tunnel run
│   ├── install-startup.cmd   # 安装登录自启快捷方式
│   └── uninstall-startup.cmd # 移除登录自启
├── deploy/
│   └── cloudflared-config.example.yml
└── .env                      # 环境变量（勿提交到 Git）
```

### `run-production.cmd` 做了什么

1. 激活 `venv`
2. `pip install -r requirements.txt`
3. `python manage.py migrate --noinput`
4. `python manage.py collectstatic --noinput`
5. 用 **Waitress** 监听 `127.0.0.1:8000`

> Windows 不支持 Gunicorn（缺少 `fcntl` 模块），因此生产脚本使用 Waitress。

### `run-tunnel.cmd` 做了什么

1. 检查 `cloudflared` 是否已安装
2. 检查 `%USERPROFILE%\.cloudflared\config.yml` 是否存在
3. 执行 `cloudflared tunnel run badminton-rotation`

---

## 四、生产环境 Django 配置要点

相关代码在 `config/settings.py`：

| 配置 | 生产行为（`DEBUG=0`） |
|------|----------------------|
| `ALLOWED_HOSTS` | 仅允许 `.env` 中配置的域名 |
| `CSRF_TRUSTED_ORIGINS` | 必须包含 `https://你的域名` |
| `SECURE_PROXY_SSL_HEADER` | 识别 Cloudflare 转发的 HTTPS |
| `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` | Cookie 仅通过 HTTPS 传输 |
| WhiteNoise | 提供 `staticfiles/` 静态资源 |
| `config/urls.py` | 生产模式下通过 Django 提供 `media/` 用户上传 |

---

## 五、备份

定期备份以下文件/目录：

| 路径 | 内容 |
|------|------|
| `db.sqlite3` | 全部业务数据 |
| `media/` | 用户头像等上传文件 |
| `.env` | 环境配置（含 API Key，注意安全） |

Cloudflare Tunnel 凭证 `%USERPROFILE%\.cloudflared\` 也建议备份，避免重装后需重新授权。

---

## 六、常见问题

### 双击 `.bat` / `.cmd` 窗口闪退

- 请双击根目录的 **`start-django.bat`** / **`start-tunnel.bat`**（内部用 `cmd /k` 保持窗口）。
- 若仍闪退，查看窗口中的 `[ERROR]` 或 `[FAILED]` 提示。

### Tunnel 报 `missing config.yml`

- 确认文件路径为 `%USERPROFILE%\.cloudflared\config.yml`。
- 常见误操作：复制时文件名变成 `config.yml.yml`。

### 登录报 CSRF / Origin checking failed

- 确认 `.env` 已保存且包含：
  ```env
  CSRF_TRUSTED_ORIGINS=https://goodminton.hgjhub.com
  ```
- 域名必须与浏览器地址栏完全一致（含 `https://`）。
- 修改后**重启 Django**。

### 头像 / media 文件 404

- 上传成功但访问 `/media/...` 返回 404：生产环境需 Django 提供 media（已在 `config/urls.py` 配置）。
- 确认 `media/avatars/` 下文件存在，并重启 Django。

### `cloudflared tunnel create` 失败

- 需先执行 `cloudflared tunnel login` 生成 `cert.pem`。

### 外网能打开但本机 127.0.0.1:8000 不行

- 检查 Django 窗口是否在运行、是否有报错。
- Tunnel 依赖本机 8000 端口，Django 必须先启动。

### 修改代码或 `.env` 后未生效

- 必须重启 `start-django.bat` 窗口；Tunnel 一般无需重启。

---

## 七、开发模式 vs 生产模式

| | 开发 | 生产 |
|---|------|------|
| 启动 | `python manage.py runserver` | `start-django.bat` |
| `DEBUG` | `1`（默认） | `0` |
| WSGI 服务器 | Django runserver | Waitress |
| 外网访问 | 不需要 Tunnel | 需要 `start-tunnel.bat` |
| `.env` 生产变量 | 可不填 | 必填 |

本地开发时 `.env` 可不设置 `DEBUG=0`；部署到公网前务必切换为生产配置。
