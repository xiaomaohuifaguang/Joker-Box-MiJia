# Joker Box MiJia

基于 [mijiaapi](https://mijia-api.do1e.com/) 和 FastAPI 的米家设备管理工具。提供浏览器管理页面和 HTTP API，使用 uv 管理依赖。

## 功能

- 米家二维码登录、Token 有效性检查和认证文件复用
- Web 无认证时自动展示二维码，扫码成功后自动加载设备
- 自定义认证文件、设备别名和动作别名路径
- 家庭、房间和设备列表
- 按房间及在线/离线状态筛选设备
- 读取设备规格、批量读取设备属性
- 设置可写属性、执行设备动作
- 根据原始 MIoT 规格生成动作参数表单
- 中文设备别名和动作别名
- Swagger API 文档

## 环境要求

- Python 3.12 或更高版本
- [uv](https://docs.astral.sh/uv/)
- 可登录米家 App 的账号

## 安装

```bash
git clone https://github.com/xiaomaohuifaguang/Joker-Box-MiJia.git
cd Joker-Box-MiJia
uv sync
```

复制 `.env.example` 为 `.env`，按实际情况修改路径：

```dotenv
MIJIA_AUTH_DATA_PATH=data/auth.json
MIJIA_DEVICE_ALIASES_PATH=data/device_aliases.json
MIJIA_ACTION_ALIASES_PATH=data/action_aliases.json
```

相对路径以项目目录为基准。`.env`、认证文件和设备别名不会提交到 Git；通用动作别名 `data/action_aliases.json` 可以纳入版本管理。

## 登录米家

启动服务后打开 http://127.0.0.1:8000/ 。没有认证文件或 Token 失效时，页面会自动显示二维码；使用米家 App 扫码并确认后，页面会自动加载设备。浏览器只接收二维码地址和登录状态，认证文件内容由 SDK 直接保存在本机。

也可以在终端扫码登录：

```bash
uv run --env-file .env python -m cli.auth login
```

终端会显示二维码，使用米家 App 扫码并确认。已有有效 Token 时会自动跳过扫码。

检查认证状态：

```bash
uv run --env-file .env python -m cli.auth status
```

退出登录并删除本地认证文件：

```bash
uv run --env-file .env python -m cli.auth logout
```

退出登录只清除本机认证，不会注销其他手机或设备上的米家登录。也可以在 Web 页面右上角点击“退出登录”，或调用 `POST /api/auth/logout`。

也可以不使用 `.env`，直接指定认证文件：

```bash
uv run python -m cli.auth --auth-data-path "C:/path/to/mijia/auth.json" login
```

命令行 `--auth-data-path` 的优先级高于 `MIJIA_AUTH_DATA_PATH` 环境变量。

## 启动

```bash
uv run --env-file .env uvicorn main:app --host 127.0.0.1 --port 8000
```

- Web 管理页面：http://127.0.0.1:8000/
- Swagger：http://127.0.0.1:8000/docs
- OpenAPI：http://127.0.0.1:8000/openapi.json

当前接口没有访问认证，默认仅监听本机。不要直接通过 `0.0.0.0` 或公网暴露控制接口。

## 命令行验证工具

列出家庭和设备：

```bash
uv run --env-file .env python -m cli.devices
```

只读查看设备规格和属性：

```bash
uv run --env-file .env python -m cli.device_info --did "设备DID"
```

执行一次开机或关机：

```bash
uv run --env-file .env python -m cli.control --did "设备DID" --action turn-on
uv run --env-file .env python -m cli.control --did "设备DID" --action turn-off
```

控制命令会操作真实设备，请确认 DID 后再执行。

## HTTP API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| GET | `/api/auth/status` | 检查本机认证状态 |
| POST | `/api/auth/qr-login` | 获取扫码登录二维码 |
| POST | `/api/auth/qr-login/complete` | 等待扫码确认并完成登录 |
| POST | `/api/auth/logout` | 删除本地认证文件并退出登录 |
| GET | `/api/homes` | 家庭列表 |
| GET | `/api/homes/{home_id}/rooms` | 指定家庭的房间列表 |
| GET | `/api/devices` | 全部设备 |
| GET | `/api/devices?home_id={home_id}` | 指定家庭的设备 |
| GET | `/api/devices/{did}` | 设备规格、属性和动作参数 |
| PUT | `/api/devices/{did}/properties/{property_name}` | 设置可写属性 |
| POST | `/api/devices/{did}/actions/{action_name}` | 执行设备动作 |

### 查询设备

```bash
curl "http://127.0.0.1:8000/api/devices?home_id=家庭ID"
curl "http://127.0.0.1:8000/api/devices/设备DID"
```

设备详情中的 `properties` 包含属性读写权限、范围、枚举值和当前值；`actions[].parameters` 按顺序描述动作输入参数。`parameters: null` 表示规格不可用，可在 Web 中使用该动作的 JSON 备用输入。

### 设置属性

```bash
curl -X PUT "http://127.0.0.1:8000/api/devices/设备DID/properties/ir-temperature" \
  -H "Content-Type: application/json" \
  -d '{"value": 26}'
```

### 执行无参数动作

```bash
curl -X POST "http://127.0.0.1:8000/api/devices/设备DID/actions/turn-on"
```

### 执行带参数动作

```bash
curl -X POST "http://127.0.0.1:8000/api/devices/设备DID/actions/play-text" \
  -H "Content-Type: application/json" \
  -d '{"values": ["你好"]}'
```

`values` 的顺序必须与设备详情中的 `actions[].parameters` 一致。支持布尔、整数、浮点数和字符串参数。

成功响应中的 `status: "sent"` 仅表示指令已发送，不代表设备状态已回读确认。特别是红外设备通常只有写权限，无法查询实际开关、模式或温度。

常见错误：无效参数或不支持的操作返回 `400`，没有等待中的扫码会话返回 `409`，设备或家庭不存在返回 `404`，米家认证失效返回 `503`，上游调用失败返回 `502`。

### 通过 API 扫码登录

先调用 `POST /api/auth/qr-login`，使用返回的 `qr_url` 展示二维码，再调用 `POST /api/auth/qr-login/complete` 等待手机确认。第二个请求是长轮询，最长等待时间由 mijiaapi 控制；二维码过期或等待超时后重新执行上述两步。不要重复调用完成接口来轮询状态。

## 别名配置

设备别名保存于 `data/device_aliases.json`，键为 DID：

```json
{
  "ir.example-device-id": "客厅空调"
}
```

动作别名保存于 `data/action_aliases.json`，键为 SDK 原始动作名：

```json
{
  "turn-on": "开机",
  "turn-off": "关机",
  "play-text": "朗读文本"
}
```

别名文件会在请求时重新读取，无需重启。未配置的设备或动作使用原始名称。两个配置文件都是可选的。设备别名包含 DID，仅保存在本机；动作别名不包含账号或设备标识，默认文件可由 Git 跟踪，团队可共同补充翻译。

## 房间和状态说明

部分米家设备记录中的 `room_id` 为 `null`，本项目会通过家庭 `roomlist[*].dids` 反向关联房间。在线筛选只包含明确在线的设备；状态未知的设备可在“全部”中查看。

## 测试

```bash
uv sync
uv run pytest
node --check web/app.js
```

Python 测试使用模拟设备，不访问真实米家账号，也不会执行真实控制。`node --check` 仅在没有前端构建流程的情况下检查 JavaScript 语法，需要本机安装 Node.js。

## 项目结构

```text
main.py                 # FastAPI 入口
app/
  config.py             # 认证和别名文件路径配置
  action_specs.py       # 原始 MIoT 动作参数解析与缓存
  mijia_service.py      # 米家 SDK、认证和设备控制服务层
  schemas.py            # API 模型
cli/
  auth.py               # 登录、Token 检查和退出登录
  devices.py            # 家庭与设备列表
  device_info.py        # 只读设备详情
  control.py            # 开关验证命令
web/                    # 原生 HTML/CSS/JavaScript 管理页面
tests/                  # 不访问真实设备的自动化测试
```

CLI 使用模块方式运行，例如 `uv run python -m cli.auth status`；需要从项目根目录执行，以便 Python 找到 `app` 和 `cli` 包。
