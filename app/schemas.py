"""API 响应模型。"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class LogoutResponse(BaseModel):
    status: str


class AuthStatusResponse(BaseModel):
    authenticated: bool


class QrLoginResponse(BaseModel):
    status: str
    qr_url: str | None = None


class Home(BaseModel):
    id: str | int | None = None
    name: str | None = None


class Room(BaseModel):
    id: str | int | None = None
    name: str | None = None
    home_id: str | int | None = None
    device_ids: list[str]


class DeviceIdentity(BaseModel):
    did: str
    name: str | None = None
    display_name: str | None = None
    model: str | None = None


class DeviceSummary(DeviceIdentity):
    online: bool | None = None
    home_id: str | int | None = None
    home_name: str | None = None
    room_id: str | int | None = None
    room_name: str | None = None


class PropertyChoice(BaseModel):
    value: bool | int | float | str
    description: str


class PropertyInfo(BaseModel):
    name: str
    description: str
    type: str
    access: str
    range: list[int | float] | None = None
    choices: list[PropertyChoice] | None = None
    siid: int | None = None
    piid: int | None = None
    value: bool | int | float | str | None = None
    read_error: str | None = None


class ActionParameter(BaseModel):
    piid: int
    name: str
    description: str
    type: str
    range: list[int | float] | None = None
    choices: list[PropertyChoice] | None = None


class ActionInfo(BaseModel):
    name: str
    description: str
    display_name: str | None = None
    siid: int | None = None
    aiid: int | None = None
    parameters: list[ActionParameter] | None = None


class DeviceDetail(BaseModel):
    device: DeviceIdentity
    properties: list[PropertyInfo]
    actions: list[ActionInfo]


class PropertySetRequest(BaseModel):
    value: bool | int | float | str


class PropertySetResponse(BaseModel):
    status: str
    did: str
    property_name: str
    value: bool | int | float | str


class ActionRequest(BaseModel):
    values: list[bool | int | float | str] | None = None


class ActionResponse(BaseModel):
    status: str
    did: str
    action_name: str
