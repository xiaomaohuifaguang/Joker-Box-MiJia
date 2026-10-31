"""设备详情批量读取测试，不访问真实米家账号。"""

from types import SimpleNamespace

from app.mijia_service import inspect_device


def make_property(name, siid, piid, access="r"):
    return SimpleNamespace(
        name=name,
        desc=name,
        type="uint",
        rw=access,
        range=None,
        value_list=None,
        method={"siid": siid, "piid": piid},
    )


class FakeDevice:
    did = "device-1"
    name = "测试设备"
    model = "test.model"

    def __init__(self, api, properties):
        self.api = api
        self.prop_list = {prop.name: prop for prop in properties}
        self.action_list = {}

    def get(self, name):
        raise AssertionError("详情读取不应再逐个调用 get()")


class FakeApi:
    def __init__(self, values):
        self.values = values
        self.calls = []

    def get_devices_prop(self, queries):
        self.calls.append(queries)
        if isinstance(self.values, Exception):
            raise self.values
        return self.values


def test_readable_properties_are_fetched_in_one_batch():
    api = FakeApi(
        [
            {"did": "device-1", "siid": 2, "piid": 1, "code": 0, "value": 26},
            {"did": "device-1", "siid": 2, "piid": 2, "code": -4004},
        ]
    )
    device = FakeDevice(
        api,
        [
            make_property("temperature", 2, 1),
            make_property("fault", 2, 2),
            make_property("write-only", 3, 1, "w"),
        ],
    )

    result = inspect_device(device)

    assert len(api.calls) == 1
    assert api.calls[0] == [
        {"did": "device-1", "siid": 2, "piid": 1},
        {"did": "device-1", "siid": 2, "piid": 2},
    ]
    assert result["properties"][0]["value"] == 26
    assert result["properties"][1]["read_error"] == "米家返回错误码 -4004"
    assert "value" not in result["properties"][2]
    assert "read_error" not in result["properties"][2]


def test_batch_failure_is_reported_on_readable_properties():
    api = FakeApi(RuntimeError("模拟网络错误"))
    device = FakeDevice(
        api,
        [make_property("temperature", 2, 1), make_property("write-only", 3, 1, "w")],
    )

    result = inspect_device(device)

    assert len(api.calls) == 1
    assert result["properties"][0]["read_error"] == "模拟网络错误"
    assert "read_error" not in result["properties"][1]


def test_action_display_name_uses_alias_and_preserves_original_name():
    device = FakeDevice(FakeApi([]), [])
    device.action_list = {
        "turn-on": SimpleNamespace(
            name="turn-on", desc="Turn On", method={"siid": 2, "aiid": 6}
        )
    }

    result = inspect_device(device, {"turn-on": "开机"})

    assert result["actions"][0]["name"] == "turn-on"
    assert result["actions"][0]["description"] == "Turn On"
    assert result["actions"][0]["display_name"] == "开机"
    assert device.api.calls == []
