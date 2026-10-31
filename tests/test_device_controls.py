"""设备动作参数传递测试，不访问真实设备。"""

from unittest.mock import Mock, patch

from app.mijia_service import MijiaService


def make_service(tmp_path):
    service = MijiaService(tmp_path / "auth.json")
    service._get_api = Mock(return_value=object())
    return service


def test_action_values_are_sent_as_miot_in_field(tmp_path):
    service = make_service(tmp_path)
    device = Mock()

    with patch("app.mijia_service.mijiaDevice", return_value=device):
        result = service.run_action("speaker-1", "play-text", ["你好"])

    device.run_action.assert_called_once_with("play-text", _in=["你好"])
    assert result == {
        "status": "sent",
        "did": "speaker-1",
        "action_name": "play-text",
    }


def test_action_without_values_omits_input_field(tmp_path):
    service = make_service(tmp_path)
    device = Mock()

    with patch("app.mijia_service.mijiaDevice", return_value=device):
        service.run_action("aircon-1", "turn-on")

    device.run_action.assert_called_once_with("turn-on")


def test_logout_deletes_only_local_auth_and_clears_sdk_state(tmp_path):
    auth_path = tmp_path / "auth.json"
    auth_path.write_text("test-only-secret", encoding="utf-8")
    service = MijiaService(auth_path)
    service._api = Mock()
    service._spec_types["device-1"] = "spec-1"

    assert service.logout() == {"status": "logged_out"}
    assert service.logout() == {"status": "logged_out"}
    assert not auth_path.exists()
    assert service._api is None
    assert service._spec_types == {}
