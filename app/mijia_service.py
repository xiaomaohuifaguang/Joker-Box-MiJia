"""米家 SDK 的服务层封装。"""

import json
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from mijiaAPI import mijiaAPI, mijiaDevice
from mijiaAPI.errors import DeviceNotFoundError

from app.action_specs import ActionSpecError, ActionSpecRepository
from app.config import (
    resolve_action_aliases_path,
    resolve_auth_data_path,
    resolve_device_aliases_path,
)


class MijiaServiceError(Exception):
    """米家服务调用失败。"""


class MijiaAuthenticationError(MijiaServiceError):
    """米家认证文件缺失或 Token 无效。"""


class MijiaLoginSessionError(MijiaServiceError):
    """没有可继续完成的扫码登录会话。"""


class HomeNotFoundError(MijiaServiceError):
    """指定的家庭不存在。"""


class DeviceOperationError(MijiaServiceError):
    """设备不支持该操作，或操作参数不符合设备规格。"""


@dataclass
class QrLoginSession:
    api: mijiaAPI
    data: dict
    qr_url: str
    completing: bool = False
    done: threading.Event = field(default_factory=threading.Event)
    error: str | None = None


def load_name_aliases(path: Path, label: str) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        with path.open(encoding="utf-8") as file:
            aliases = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise MijiaServiceError(f"读取{label}配置失败: {exc}") from exc
    if not isinstance(aliases, dict) or not all(
        isinstance(key, str)
        and isinstance(value, str)
        and bool(value.strip())
        for key, value in aliases.items()
    ):
        raise MijiaServiceError(f"{label}配置必须是名称到非空别名的 JSON 对象")
    return {key: value.strip() for key, value in aliases.items()}


def summarize_homes(homes: list[dict]) -> list[dict]:
    return [{"id": home.get("id"), "name": home.get("name")} for home in homes]


def summarize_rooms(home: dict) -> list[dict]:
    return [
        {
            "id": room.get("id"),
            "name": room.get("name"),
            "home_id": room.get("parentid") or home.get("id"),
            "device_ids": [str(did) for did in room.get("dids") or []],
        }
        for room in home.get("roomlist") or []
    ]


def summarize_devices(
    devices: list[dict], homes: list[dict], aliases: dict[str, str] | None = None
) -> list[dict]:
    aliases = aliases or {}
    home_names = {str(home.get("id")): home.get("name") for home in homes}
    rooms_by_id = {}
    room_by_did = {}
    for home in homes:
        for room in home.get("roomlist") or []:
            rooms_by_id[str(room.get("id"))] = room
            for did in room.get("dids") or []:
                room_by_did[str(did)] = room

    result = []
    for device in devices:
        did = device.get("did")
        raw_room_id = device.get("room_id")
        room = room_by_did.get(str(did)) or rooms_by_id.get(str(raw_room_id))
        room_id = raw_room_id if raw_room_id is not None else room and room.get("id")
        name = device.get("name")
        result.append(
            {
                "did": did,
                "name": name,
                "display_name": aliases.get(str(did)) or name,
                "model": device.get("model"),
                "online": device.get("isOnline"),
                "home_id": device.get("home_id"),
                "home_name": home_names.get(str(device.get("home_id"))),
                "room_id": room_id,
                "room_name": room and room.get("name"),
            }
        )
    return result


def unique_named_objects(items: dict) -> list:
    """去除 SDK 为带连字符名称添加的访问别名。"""
    return list({item.name: item for item in items.values()}.values())


def describe_property(prop) -> dict:
    return {
        "name": prop.name,
        "description": prop.desc,
        "type": prop.type,
        "access": prop.rw,
        "range": prop.range,
        "choices": prop.value_list,
        "siid": prop.method.get("siid"),
        "piid": prop.method.get("piid"),
    }


def describe_action(action, aliases: dict[str, str] | None = None) -> dict:
    return {
        "name": action.name,
        "description": action.desc,
        "display_name": (aliases or {}).get(action.name) or action.desc,
        "siid": action.method.get("siid"),
        "aiid": action.method.get("aiid"),
    }


def inspect_device(
    device: mijiaDevice, action_aliases: dict[str, str] | None = None
) -> dict:
    """批量读取设备规格和可读属性，不执行任何写操作。"""
    properties = []
    readable_items = []
    for prop in unique_named_objects(device.prop_list):
        item = describe_property(prop)
        properties.append(item)
        if "r" in prop.rw:
            readable_items.append((item, prop))

    if readable_items:
        queries = []
        for _, prop in readable_items:
            method = prop.method.copy()
            method["did"] = device.did
            queries.append(method)
        try:
            values = device.api.get_devices_prop(queries)
        except Exception as exc:
            for item, _ in readable_items:
                item["read_error"] = str(exc)
        else:
            values_by_id = {
                (value.get("siid"), value.get("piid")): value for value in values
            }
            for item, prop in readable_items:
                key = (prop.method.get("siid"), prop.method.get("piid"))
                value = values_by_id.get(key)
                if value is None:
                    item["read_error"] = "米家未返回该属性"
                elif value.get("code") == 0:
                    item["value"] = value.get("value")
                else:
                    item["read_error"] = f"米家返回错误码 {value.get('code')}"

    return {
        "device": {
            "did": device.did,
            "name": device.name,
            "model": device.model,
        },
        "properties": properties,
        "actions": [
            describe_action(action, action_aliases)
            for action in unique_named_objects(device.action_list)
        ],
    }


class MijiaService:
    """串行访问一个 mijiaAPI 实例，避免并发读写认证状态。"""

    def __init__(
        self,
        auth_data_path: Path,
        device_aliases_path: Path | None = None,
        action_aliases_path: Path | None = None,
    ):
        self.auth_data_path = auth_data_path
        self.device_aliases_path = device_aliases_path or resolve_device_aliases_path()
        self.action_aliases_path = action_aliases_path or resolve_action_aliases_path()
        self._api: mijiaAPI | None = None
        self._login_session: QrLoginSession | None = None
        self._lock = threading.RLock()
        self._spec_types: dict[str, str] = {}
        self._action_specs = ActionSpecRepository(
            auth_data_path.parent / "action-specs"
        )

    def _remember_spec_types(self, devices: list[dict]) -> None:
        for device in devices:
            if device.get("did") and device.get("spec_type"):
                self._spec_types[str(device["did"])] = device["spec_type"]

    def _get_api(self) -> mijiaAPI:
        if not self.auth_data_path.is_file():
            raise MijiaAuthenticationError("米家认证文件不存在，请先完成登录")
        if self._api is None:
            self._api = mijiaAPI(auth_data_path=str(self.auth_data_path))
        if not self._api.available:
            raise MijiaAuthenticationError("米家 Token 无效或已过期，请重新登录")
        return self._api

    def get_auth_status(self) -> dict:
        """只返回认证状态，不向 Web 暴露认证文件内容。"""
        with self._lock:
            if not self.auth_data_path.is_file():
                return {"authenticated": False}
            try:
                self._get_api()
            except (MijiaAuthenticationError, json.JSONDecodeError, OSError):
                self._api = None
                return {"authenticated": False}
            return {"authenticated": True}

    def start_qr_login(self) -> dict:
        """获取二维码后立即返回；刷新页面时复用未结束的会话。"""
        with self._lock:
            if self._login_session is not None:
                return {
                    "status": "waiting_for_scan",
                    "qr_url": self._login_session.qr_url,
                }
            self._api = None
            try:
                api = mijiaAPI(auth_data_path=str(self.auth_data_path))
                # SDK 5.0 将终端 QRlogin 拆成获取数据和长轮询两个步骤。
                login_data = api._get_qr_login_data()
                if login_data.get("refreshed"):
                    self._api = api
                    return {"status": "authenticated", "qr_url": None}
                qr_url = login_data.get("qr")
                if not qr_url or not login_data.get("lp"):
                    raise ValueError("米家未返回有效的二维码登录数据")
                self._login_session = QrLoginSession(api, login_data, qr_url)
                return {"status": "waiting_for_scan", "qr_url": qr_url}
            except MijiaServiceError:
                raise
            except Exception as exc:
                raise MijiaServiceError(f"获取登录二维码失败: {exc}") from exc

    def complete_qr_login(self) -> dict:
        """等待扫码时不持有全局锁，避免阻塞状态检查和退出登录。"""
        with self._lock:
            session = self._login_session
            if session is None:
                raise MijiaLoginSessionError("没有等待中的扫码登录，请先获取二维码")
            owner = not session.completing
            session.completing = True

        if not owner:
            # 另一个页面已在等待同一个二维码，只等待其结果，不重复调用 SDK。
            session.done.wait()
            with self._lock:
                if self._api is session.api and self.auth_data_path.is_file():
                    return {"status": "authenticated", "qr_url": None}
                raise MijiaServiceError(
                    session.error or "扫码登录会话已结束，请重新获取二维码"
                )

        error = None
        try:
            session.api._complete_qr_login(session.data)
            if not self.auth_data_path.is_file():
                raise OSError("登录完成后未找到认证文件")
        except Exception as exc:
            error = f"扫码登录未完成: {exc}"

        with self._lock:
            if error is None and not self.auth_data_path.is_file():
                error = "扫码登录未完成: 认证文件已清除"
            if self._login_session is session:
                if error is None:
                    self._api = session.api
                    self._spec_types.clear()
                self._login_session = None
            session.error = error
            session.done.set()

        if error is not None:
            raise MijiaServiceError(error)
        return {"status": "authenticated", "qr_url": None}

    def list_homes(self) -> list[dict]:
        with self._lock:
            try:
                return summarize_homes(self._get_api().get_homes_list())
            except MijiaServiceError:
                raise
            except Exception as exc:
                raise MijiaServiceError(f"获取家庭列表失败: {exc}") from exc

    def list_rooms(self, home_id: str) -> list[dict]:
        with self._lock:
            try:
                homes = self._get_api().get_homes_list()
                home = next(
                    (home for home in homes if str(home.get("id")) == home_id), None
                )
                if home is None:
                    raise HomeNotFoundError(f"未找到家庭: {home_id}")
                return summarize_rooms(home)
            except MijiaServiceError:
                raise
            except Exception as exc:
                raise MijiaServiceError(f"获取房间列表失败: {exc}") from exc

    def list_devices(self, home_id: str | None = None) -> list[dict]:
        with self._lock:
            try:
                api = self._get_api()
                homes = api.get_homes_list()
                devices = api.get_devices_list(home_id=home_id)
                self._remember_spec_types(devices)
                aliases = load_name_aliases(self.device_aliases_path, "设备别名")
                return summarize_devices(devices, homes, aliases)
            except MijiaServiceError:
                raise
            except Exception as exc:
                raise MijiaServiceError(f"获取设备列表失败: {exc}") from exc

    def get_device_detail(self, did: str) -> dict:
        with self._lock:
            try:
                api = self._get_api()
                device = mijiaDevice(api, did=did)
                spec_type = self._spec_types.get(did)
                if spec_type is None:
                    self._remember_spec_types(api.get_devices_list())
                    spec_type = self._spec_types.get(did)
                result = inspect_device(
                    device, load_name_aliases(self.action_aliases_path, "动作别名")
                )
                if spec_type:
                    try:
                        action_specs = self._action_specs.get(spec_type)
                    except ActionSpecError:
                        # 公网规格不可用时不影响设备详情和动作执行。
                        pass
                    else:
                        for action in result["actions"]:
                            key = f"{action['siid']}:{action['aiid']}"
                            action["parameters"] = action_specs.get(key, [])
                aliases = load_name_aliases(self.device_aliases_path, "设备别名")
                result["device"]["display_name"] = aliases.get(did) or device.name
                return result
            except (MijiaServiceError, DeviceNotFoundError):
                raise
            except Exception as exc:
                raise MijiaServiceError(f"读取设备失败: {exc}") from exc
    def logout(self) -> dict:
        """删除本地认证信息；其他设备上的米家登录不受影响。"""
        with self._lock:
            self._api = None
            if self._login_session is not None and not self._login_session.completing:
                self._login_session = None
            self._spec_types.clear()
            try:
                self.auth_data_path.unlink(missing_ok=True)
            except OSError as exc:
                raise MijiaServiceError(f"删除本地认证文件失败: {exc}") from exc
            return {"status": "logged_out"}

    def set_property(
        self, did: str, property_name: str, value: bool | int | float | str
    ) -> dict:
        with self._lock:
            try:
                device = mijiaDevice(self._get_api(), did=did)
                try:
                    device.set(property_name, value)
                except ValueError as exc:
                    raise DeviceOperationError(str(exc)) from exc
                return {
                    "status": "sent",
                    "did": did,
                    "property_name": property_name,
                    "value": value,
                }
            except (MijiaServiceError, DeviceNotFoundError):
                raise
            except Exception as exc:
                raise MijiaServiceError(f"设置设备属性失败: {exc}") from exc

    def run_action(
        self,
        did: str,
        action_name: str,
        values: list[bool | int | float | str] | None = None,
    ) -> dict:
        with self._lock:
            try:
                device = mijiaDevice(self._get_api(), did=did)
                try:
                    if values is None:
                        device.run_action(action_name)
                    else:
                        # 米家动作接口使用 in；SDK 的 _in 会透传为该字段。
                        device.run_action(action_name, _in=values)
                except ValueError as exc:
                    raise DeviceOperationError(str(exc)) from exc
                return {"status": "sent", "did": did, "action_name": action_name}
            except (MijiaServiceError, DeviceNotFoundError):
                raise
            except Exception as exc:
                raise MijiaServiceError(f"执行设备动作失败: {exc}") from exc


@lru_cache
def get_mijia_service() -> MijiaService:
    return MijiaService(
        auth_data_path=resolve_auth_data_path(),
        device_aliases_path=resolve_device_aliases_path(),
        action_aliases_path=resolve_action_aliases_path(),
    )
