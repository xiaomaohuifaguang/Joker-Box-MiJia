"""扫码登录流程测试，不访问真实米家账号。"""

import threading
from unittest.mock import Mock, patch

import pytest

from app.mijia_service import MijiaLoginSessionError, MijiaService, QrLoginSession


def test_qr_login_returns_only_qr_url_then_uses_saved_auth(tmp_path):
    auth_path = tmp_path / "auth.json"
    service = MijiaService(auth_path)
    api = Mock()
    api._get_qr_login_data.return_value = {
        "qr": "https://example.test/qr.png",
        "lp": "https://example.test/wait",
        "serviceToken": "must-not-be-returned",
    }
    api._complete_qr_login.side_effect = lambda _: auth_path.write_text(
        "test-only-auth", encoding="utf-8"
    )

    with patch("app.mijia_service.mijiaAPI", return_value=api) as api_class:
        expected_start = {
            "status": "waiting_for_scan",
            "qr_url": "https://example.test/qr.png",
        }
        assert service.start_qr_login() == expected_start
        assert service.start_qr_login() == expected_start
        assert service.complete_qr_login() == {
            "status": "authenticated",
            "qr_url": None,
        }

    api_class.assert_called_once_with(auth_data_path=str(auth_path))
    api._complete_qr_login.assert_called_once()
    assert service._api is api
    assert service._login_session is None


def test_qr_login_reuses_refreshed_token(tmp_path):
    service = MijiaService(tmp_path / "auth.json")
    api = Mock()
    api._get_qr_login_data.return_value = {"refreshed": True}

    with patch("app.mijia_service.mijiaAPI", return_value=api):
        assert service.start_qr_login() == {
            "status": "authenticated",
            "qr_url": None,
        }

    assert service._api is api
    with pytest.raises(MijiaLoginSessionError):
        service.complete_qr_login()


def test_auth_status_does_not_require_an_sdk_call_without_a_file(tmp_path):
    service = MijiaService(tmp_path / "missing.json")
    service._get_api = Mock()

    assert service.get_auth_status() == {"authenticated": False}
    service._get_api.assert_not_called()


def test_logout_clears_pending_qr_login(tmp_path):
    service = MijiaService(tmp_path / "auth.json")
    service._login_session = Mock(completing=False)

    service.logout()

    assert service._login_session is None


def test_auth_status_is_not_blocked_by_waiting_for_a_scan(tmp_path):
    auth_path = tmp_path / "auth.json"
    service = MijiaService(auth_path)
    api = Mock()
    session = QrLoginSession(api, {"lp": "test-only"}, "https://example.test/qr")
    service._login_session = session
    sdk_waiting = threading.Event()
    finish_login = threading.Event()

    def complete_login(_):
        sdk_waiting.set()
        assert finish_login.wait(2)
        auth_path.write_text("test-only-auth", encoding="utf-8")

    api._complete_qr_login.side_effect = complete_login
    login_thread = threading.Thread(target=service.complete_qr_login, daemon=True)
    login_thread.start()
    assert sdk_waiting.wait(1)

    status_results = []
    status_thread = threading.Thread(
        target=lambda: status_results.append(service.get_auth_status()), daemon=True
    )
    status_thread.start()
    status_thread.join(0.5)
    try:
        assert not status_thread.is_alive(), "状态检查被扫码长轮询阻塞"
        assert status_results == [{"authenticated": False}]
    finally:
        finish_login.set()
        login_thread.join(1)

    assert not login_thread.is_alive()
