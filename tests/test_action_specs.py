"""MIoT 动作参数规格解析测试。"""

import json

from app.action_specs import ActionSpecRepository, parse_action_parameters


SPEC = {
    "services": [
        {
            "iid": 7,
            "properties": [
                {
                    "iid": 1,
                    "type": "urn:miot-spec-v2:property:text-content:00000001",
                    "description": "Text Content",
                    "comment": "文本内容",
                    "format": "string",
                },
                {
                    "iid": 2,
                    "type": "urn:miot-spec-v2:property:silent-execution:00000002",
                    "description": "Silent Execution",
                    "format": "bool",
                },
                {
                    "iid": 3,
                    "type": "urn:miot-spec-v2:property:level:00000003",
                    "description": "Level",
                    "format": "uint8",
                    "value-range": [1, 10, 1],
                    "value-list": [{"value": 1, "description": "Low"}],
                },
            ],
            "actions": [
                {"iid": 4, "in": [1, 2]},
                {"iid": 5, "in": []},
                {"iid": 6, "in": [99]},
            ],
        }
    ]
}


def test_parse_action_parameters_preserves_order_and_types():
    result = parse_action_parameters(SPEC)

    parameters = result["7:4"]
    assert [parameter["piid"] for parameter in parameters] == [1, 2]
    assert [parameter["type"] for parameter in parameters] == ["string", "bool"]
    assert parameters[0]["name"] == "text-content"
    assert parameters[0]["description"] == "Text Content / 文本内容"
    assert result["7:5"] == []
    assert result["7:6"] is None


def test_repository_reads_cached_spec_without_network(tmp_path):
    spec_type = "urn:test:speaker:1"
    cache_file = tmp_path / f"{spec_type.replace(':', '_')}.json"
    cache_file.write_text(json.dumps(SPEC), encoding="utf-8")
    repository = ActionSpecRepository(tmp_path)

    first = repository.get(spec_type)
    second = repository.get(spec_type)

    assert first["7:4"][0]["type"] == "string"
    assert second is first
