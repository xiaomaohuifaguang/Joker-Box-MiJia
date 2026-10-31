"""项目路径配置；相对路径以启动命令的工作目录为基准。"""

import os
from pathlib import Path

DEFAULT_AUTH_DATA_PATH = Path("data/auth.json")
DEFAULT_DEVICE_ALIASES_PATH = Path("data/device_aliases.json")
DEFAULT_ACTION_ALIASES_PATH = Path("data/action_aliases.json")


def resolve_auth_data_path(cli_path: str | None = None) -> Path:
    """按命令行参数、环境变量、默认值的顺序确定认证文件路径。"""
    configured_path = cli_path or os.getenv("MIJIA_AUTH_DATA_PATH")
    path = Path(configured_path) if configured_path else DEFAULT_AUTH_DATA_PATH
    return path.expanduser().resolve()


def resolve_device_aliases_path() -> Path:
    configured_path = os.getenv("MIJIA_DEVICE_ALIASES_PATH")
    path = Path(configured_path) if configured_path else DEFAULT_DEVICE_ALIASES_PATH
    return path.expanduser().resolve()


def resolve_action_aliases_path() -> Path:
    configured_path = os.getenv("MIJIA_ACTION_ALIASES_PATH")
    path = Path(configured_path) if configured_path else DEFAULT_ACTION_ALIASES_PATH
    return path.expanduser().resolve()
