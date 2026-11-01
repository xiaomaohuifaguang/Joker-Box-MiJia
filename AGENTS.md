# AGENTS.md

This file provides shared project guidance for coding assistants working in this repository.

## 项目概述

基于 [mijiaapi](https://github.com/Do1e/mijia-api)（米家 SDK）和 FastAPI 的米家设备管理工具，提供浏览器管理页面和 HTTP API。界面与文档为中文。

## 常用命令

依赖管理使用 [uv](https://docs.astral.sh/uv/)，需要 Python 3.12+：

```bash
uv sync                                                  # 安装依赖
uv run --env-file .env python main.py                          # 启动服务（MIJIA_HOST/MIJIA_PORT，默认 127.0.0.1:10253；MIJIA_RELOAD=true 热重载）
uv run pytest                                            # 运行全部测试
uv run pytest tests/test_api.py::test_health             # 运行单个测试
node --check web/app.js                                  # 前端语法检查（无构建流程，需本机 Node.js）
```

CLI 以模块方式运行，必须从项目根目录执行（Python 需要找到 `app` 和 `cli` 包）：

```bash
uv run --env-file .env python -m cli.auth login|status|logout
uv run --env-file .env python -m cli.devices
uv run --env-file .env python -m cli.device_info --did "设备DID"
uv run --env-file .env python -m cli.control --did "设备DID" --action turn-on
```

`cli.control` 会操作真实设备；测试全部使用模拟设备，不访问真实米家账号。

## 架构

### 分层

- `main.py` — 纯 FastAPI 路由层：定义端点、挂载 `web/` 静态资源，并通过 `@app.exception_handler` 把服务层异常映射为 HTTP 状态码（认证失效 503、无扫码会话 409、设备/家庭不存在 404、参数或操作不支持 400、上游失败 502）。路由本身不含业务逻辑。
- `app/mijia_service.py` — 核心服务层 `MijiaService`，封装 `mijiaAPI` SDK。通过 `@lru_cache` 的 `get_mijia_service()` 以 FastAPI `Depends` 注入为全局单例；`tests/test_api.py` 用 `app.dependency_overrides[get_mijia_service]` 替换为 `FakeService` 进行测试。
- `app/action_specs.py` — 从 miot-spec.org 拉取原始 MIoT 规格，解析出动作的有序输入参数（以 `siid:aiid` 为键），并缓存到 `data/action-specs/` 目录（先写 `.tmp` 再原子替换）。规格不可用时动作仍可执行，只是无参数表单。
- `app/config.py` — 认证文件与别名文件路径解析，优先级：CLI 参数 > 环境变量（`MIJIA_*_PATH`）> 默认值 `data/` 下，相对路径以启动时工作目录为基准。
- `cli/` — 独立的 argparse 命令行工具，直接复用 `app/` 的代码。
- `web/` — 无构建流程的原生 HTML/CSS/JS 管理页面，由 FastAPI 直接伺服。

### 关键设计约束

- **并发模型**：`MijiaService` 用 `threading.RLock` 串行化所有 SDK 调用，避免并发读写认证状态。唯一的例外是 `complete_qr_login`：等待扫码确认时故意不持锁（否则状态检查和退出登录会被阻塞），通过 `QrLoginSession.done` 事件让并发请求共享同一次 SDK 长轮询。
- **扫码登录两步拆分**：mijiaapi 5.0 把 QR 登录拆成获取数据（`_get_qr_login_data`）和长轮询完成（`_complete_qr_login`）两步。本服务有意调用 SDK 的这两个私有方法来实现"一个二维码、多页面共享"的会话复用。升级 mijiaapi 时需检查这两个私有 API 是否仍然存在。
- **设备与动作别名**：`data/device_aliases.json`（键为 DID，含设备标识，不入 Git）和 `data/action_aliases.json`（键为 SDK 原始动作名，可入 Git）。每次请求时重新读取，改完无需重启。
- **房间反查**：部分设备的 `room_id` 为 `null`，`summarize_devices` 会遍历各家庭的 `roomlist[*].dids` 反向关联房间。

### 安全注意

所有 HTTP 接口**没有访问认证**，README 明确要求只绑定 `127.0.0.1`。不要为了让服务对外可访问而改为 `0.0.0.0` 或公网暴露；认证文件内容（`data/auth.json`）绝不出现在 API 响应中，`get_auth_status` 只返回布尔状态。
