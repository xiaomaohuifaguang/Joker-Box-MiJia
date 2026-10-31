"""不访问真实米家账号的 FastAPI 接口测试。"""

import pytest
from fastapi.testclient import TestClient
from mijiaAPI.errors import DeviceNotFoundError

from app.mijia_service import (
    DeviceOperationError,
    MijiaAuthenticationError,
    MijiaLoginSessionError,
    MijiaService,
    MijiaServiceError,
    get_mijia_service,
    summarize_devices,
)
from main import app

HOMES = [{"id": "home-1", "name": "测试家庭"}]
ROOMS = [
    {
        "id": "room-1",
        "name": "卧室",
        "home_id": "home-1",
        "device_ids": ["ir.test"],
    }
]
DEVICES = [
    {
        "did": "ir.test",
        "name": "空调",
        "display_name": "卧室空调",
        "model": "miir.aircondition.ir02",
        "online": True,
        "home_id": "home-1",
        "home_name": "测试家庭",
        "room_id": "room-1",
        "room_name": "卧室",
    }
]
DEVICE_DETAIL = {
    "device": {
        "did": "ir.test",
        "name": "空调",
        "display_name": "卧室空调",
        "model": "miir.aircondition.ir02",
    },
    "properties": [
        {
            "name": "ir-temperature",
            "description": "Temperature for IR",
            "type": "float",
            "access": "w",
            "range": [16, 30, 1],
            "choices": None,
            "siid": 2,
            "piid": 2,
        }
    ],
    "actions": [
        {"name": "turn-on", "description": "Turn On", "siid": 2, "aiid": 6}
    ],
}


class FakeService:
    def __init__(self):
        self.home_id = None
        self.commands = []

    def list_homes(self):
        return HOMES

    def get_auth_status(self):
        return {"authenticated": True}

    def start_qr_login(self):
        return {"status": "waiting_for_scan", "qr_url": "https://example.test/qr"}

    def complete_qr_login(self):
        return {"status": "authenticated", "qr_url": None}

    def list_rooms(self, home_id):
        assert home_id == "home-1"
        return ROOMS

    def list_devices(self, home_id=None):
        self.home_id = home_id
        return DEVICES

    def get_device_detail(self, did):
        assert did == "ir.test"
        return DEVICE_DETAIL

    def set_property(self, did, property_name, value):
        self.commands.append(("set", did, property_name, value))
        return {
            "status": "sent",
            "did": did,
            "property_name": property_name,
            "value": value,
        }

    def run_action(self, did, action_name, values=None):
        self.commands.append(("action", did, action_name, values))
        return {"status": "sent", "did": did, "action_name": action_name}

    def logout(self):
        return {"status": "logged_out"}


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def override_service(service):
    app.dependency_overrides[get_mijia_service] = lambda: service


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_auth_status_and_qr_login(client):
    override_service(FakeService())

    status_response = client.get("/api/auth/status")
    start_response = client.post("/api/auth/qr-login")
    complete_response = client.post("/api/auth/qr-login/complete")

    assert status_response.json() == {"authenticated": True}
    assert start_response.json() == {
        "status": "waiting_for_scan",
        "qr_url": "https://example.test/qr",
    }
    assert complete_response.json() == {"status": "authenticated", "qr_url": None}


def test_qr_login_requires_a_pending_session(client):
    class NoLoginService(FakeService):
        def complete_qr_login(self):
            raise MijiaLoginSessionError("没有等待中的扫码登录")

    override_service(NoLoginService())
    response = client.post("/api/auth/qr-login/complete")
    assert response.status_code == 409
    assert response.json() == {"detail": "没有等待中的扫码登录"}


def test_logout(client):
    override_service(FakeService())
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"status": "logged_out"}


def test_web_index_and_assets(client):
    index_response = client.get("/")
    script_response = client.get("/static/app.js")
    style_response = client.get("/static/styles.css")

    assert index_response.status_code == 200
    assert 'id="device-list"' in index_response.text
    assert script_response.status_code == 200
    assert "initialize();" in script_response.text
    assert style_response.status_code == 200


def test_homes_rooms_and_devices(client):
    service = FakeService()
    override_service(service)

    homes_response = client.get("/api/homes")
    rooms_response = client.get("/api/homes/home-1/rooms")
    devices_response = client.get("/api/devices", params={"home_id": "home-1"})

    assert homes_response.status_code == 200
    assert homes_response.json() == HOMES
    assert rooms_response.status_code == 200
    assert rooms_response.json() == ROOMS
    assert devices_response.status_code == 200
    assert devices_response.json() == DEVICES
    assert service.home_id == "home-1"


def test_device_detail(client):
    override_service(FakeService())
    response = client.get("/api/devices/ir.test")

    assert response.status_code == 200
    body = response.json()
    assert body["device"]["model"] == "miir.aircondition.ir02"
    assert body["device"]["display_name"] == "卧室空调"
    assert body["properties"][0]["access"] == "w"
    assert body["actions"][0]["name"] == "turn-on"


def test_set_device_property(client):
    service = FakeService()
    override_service(service)

    response = client.put(
        "/api/devices/ir.test/properties/ir-temperature", json={"value": 26}
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "sent",
        "did": "ir.test",
        "property_name": "ir-temperature",
        "value": 26,
    }
    assert service.commands == [("set", "ir.test", "ir-temperature", 26)]


def test_run_device_action_without_body(client):
    service = FakeService()
    override_service(service)

    response = client.post("/api/devices/ir.test/actions/turn-on")

    assert response.status_code == 200
    assert response.json() == {
        "status": "sent",
        "did": "ir.test",
        "action_name": "turn-on",
    }
    assert service.commands == [("action", "ir.test", "turn-on", None)]


def test_run_device_action_with_values(client):
    service = FakeService()
    override_service(service)

    response = client.post(
        "/api/devices/ir.test/actions/test-action", json={"values": [1, 26]}
    )

    assert response.status_code == 200
    assert service.commands == [("action", "ir.test", "test-action", [1, 26])]


def test_invalid_device_operation(client):
    class InvalidOperationService(FakeService):
        def run_action(self, did, action_name, values=None):
            raise DeviceOperationError("不支持的动作")

    override_service(InvalidOperationService())
    response = client.post("/api/devices/ir.test/actions/invalid")
    assert response.status_code == 400
    assert response.json() == {"detail": "不支持的动作"}


def test_device_not_found(client):
    class NotFoundService(FakeService):
        def get_device_detail(self, did):
            raise DeviceNotFoundError(did)

    override_service(NotFoundService())
    response = client.get("/api/devices/missing")
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (MijiaAuthenticationError("请重新登录"), 503),
        (MijiaServiceError("上游请求失败"), 502),
    ],
)
def test_service_errors(client, error, expected_status):
    class ErrorService(FakeService):
        def list_devices(self, home_id=None):
            raise error

    override_service(ErrorService())
    response = client.get("/api/devices")
    assert response.status_code == expected_status
    assert response.json()["detail"] == str(error)


def test_missing_auth_file_does_not_call_sdk(tmp_path):
    service = MijiaService(tmp_path / "missing.json")
    with pytest.raises(MijiaAuthenticationError):
        service.list_homes()


def test_room_membership_and_display_alias():
    homes = [
        {
            "id": "home-1",
            "name": "我的家庭",
            "roomlist": [
                {
                    "id": "room-1",
                    "name": "卧室",
                    "parentid": "home-1",
                    "dids": ["device-1"],
                }
            ],
        }
    ]
    devices = [
        {
            "did": "device-1",
            "name": "English Product Name",
            "model": "test.model",
            "home_id": "home-1",
            "room_id": None,
        }
    ]

    result = summarize_devices(devices, homes, {"device-1": "中文设备名"})[0]

    assert result["name"] == "English Product Name"
    assert result["display_name"] == "中文设备名"
    assert result["room_id"] == "room-1"
    assert result["room_name"] == "卧室"
