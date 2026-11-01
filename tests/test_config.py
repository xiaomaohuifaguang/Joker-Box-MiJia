"""服务监听地址和端口的环境变量解析测试。"""

import pytest

from app.config import (
    DEFAULT_SERVER_HOST,
    DEFAULT_SERVER_PORT,
    resolve_server_host,
    resolve_server_port,
)


def test_host_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("MIJIA_HOST", raising=False)
    assert resolve_server_host() == DEFAULT_SERVER_HOST == "127.0.0.1"


def test_host_reads_env(monkeypatch):
    monkeypatch.setenv("MIJIA_HOST", "192.168.1.10")
    assert resolve_server_host() == "192.168.1.10"


def test_port_defaults(monkeypatch):
    monkeypatch.delenv("MIJIA_PORT", raising=False)
    assert resolve_server_port() == DEFAULT_SERVER_PORT == 10253


def test_port_reads_env(monkeypatch):
    monkeypatch.setenv("MIJIA_PORT", "9000")
    assert resolve_server_port() == 9000


@pytest.mark.parametrize("value", ["abc", "0", "65536", "-1"])
def test_port_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("MIJIA_PORT", value)
    with pytest.raises(ValueError):
        resolve_server_port()
