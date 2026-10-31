"""从原始 MIoT 规格中恢复动作输入参数定义。"""

import json
from pathlib import Path

import requests


class ActionSpecError(Exception):
    """动作规格获取或解析失败。"""


def spec_item_name(item: dict) -> str:
    parts = item.get("type", "").split(":")
    return parts[3] if len(parts) > 3 else item.get("type", "未知参数")


def spec_description(item: dict) -> str:
    return " / ".join(
        part for part in [item.get("description"), item.get("comment")] if part
    )


def spec_property_type(prop: dict) -> str | None:
    prop_format = prop.get("format", "")
    if prop_format.startswith("int"):
        return "int"
    if prop_format.startswith("uint"):
        return "uint"
    if prop_format in {"bool", "float", "string"}:
        return prop_format
    return None


def parse_action_parameters(spec: dict) -> dict[str, list[dict] | None]:
    """以 siid:aiid 为键返回有序参数；无法完整解析时返回 None。"""
    result = {}
    for service in spec.get("services", []):
        properties = {prop.get("iid"): prop for prop in service.get("properties", [])}
        for action in service.get("actions", []):
            parameters = []
            supported = True
            for piid in action.get("in", []):
                prop = properties.get(piid)
                prop_type = spec_property_type(prop) if prop else None
                if not prop or not prop_type:
                    supported = False
                    break
                parameters.append(
                    {
                        "piid": piid,
                        "name": spec_item_name(prop),
                        "description": spec_description(prop) or spec_item_name(prop),
                        "type": prop_type,
                        "range": prop.get("value-range"),
                        "choices": [
                            {
                                "value": choice.get("value"),
                                "description": spec_description(choice)
                                or str(choice.get("value")),
                            }
                            for choice in prop.get("value-list") or []
                        ]
                        or None,
                    }
                )
            key = f"{service.get('iid')}:{action.get('iid')}"
            result[key] = parameters if supported else None
    return result


class ActionSpecRepository:
    """按 spec_type 缓存原始规格，避免每次设备详情都请求公网。"""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self._parsed_specs: dict[str, dict[str, list[dict] | None]] = {}

    def _cache_file(self, spec_type: str) -> Path:
        return self.cache_dir / f"{spec_type.replace(':', '_')}.json"

    def get(self, spec_type: str) -> dict[str, list[dict] | None]:
        if spec_type in self._parsed_specs:
            return self._parsed_specs[spec_type]

        cache_file = self._cache_file(spec_type)
        spec = None
        if cache_file.is_file():
            try:
                with cache_file.open(encoding="utf-8") as file:
                    spec = json.load(file)
            except (OSError, json.JSONDecodeError):
                spec = None

        if spec is None:
            try:
                response = requests.get(
                    "https://miot-spec.org/miot-spec-v2/instance",
                    params={"type": spec_type},
                    headers={"User-Agent": "Joker-Box-MiJia/0.1"},
                    timeout=(3.05, 10),
                )
                response.raise_for_status()
                spec = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise ActionSpecError(f"获取动作规格失败: {exc}") from exc
            if not isinstance(spec, dict) or not isinstance(spec.get("services"), list):
                raise ActionSpecError("动作规格格式无效")
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                temporary_file = cache_file.with_suffix(".tmp")
                with temporary_file.open("w", encoding="utf-8") as file:
                    json.dump(spec, file, ensure_ascii=False)
                temporary_file.replace(cache_file)
            except OSError:
                # 缓存不可写不影响本次规格解析。
                pass

        try:
            parsed = parse_action_parameters(spec)
        except (AttributeError, TypeError) as exc:
            raise ActionSpecError(f"解析动作规格失败: {exc}") from exc
        self._parsed_specs[spec_type] = parsed
        return parsed
