"""Joker Box MiJia FastAPI 入口。"""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mijiaAPI.errors import DeviceNotFoundError

from app.mijia_service import (
    DeviceOperationError,
    HomeNotFoundError,
    MijiaAuthenticationError,
    MijiaLoginSessionError,
    MijiaService,
    MijiaServiceError,
    get_mijia_service,
)
from app.schemas import (
    ActionRequest,
    ActionResponse,
    AuthStatusResponse,
    DeviceDetail,
    DeviceSummary,
    HealthResponse,
    Home,
    LogoutResponse,
    PropertySetRequest,
    PropertySetResponse,
    QrLoginResponse,
    Room,
)

app = FastAPI(
    title="Joker Box MiJia",
    description="基于 mijiaapi 的米家设备管理接口",
    version="0.1.0",
)

ServiceDependency = Annotated[MijiaService, Depends(get_mijia_service)]
WEB_DIR = Path(__file__).resolve().parent / "web"
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def web_index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.exception_handler(MijiaAuthenticationError)
async def handle_authentication_error(
    request: Request, exc: MijiaAuthenticationError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(MijiaLoginSessionError)
async def handle_login_session_error(
    request: Request, exc: MijiaLoginSessionError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DeviceNotFoundError)
async def handle_device_not_found(
    request: Request, exc: DeviceNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(HomeNotFoundError)
async def handle_home_not_found(
    request: Request, exc: HomeNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DeviceOperationError)
async def handle_device_operation_error(
    request: Request, exc: DeviceOperationError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(MijiaServiceError)
async def handle_service_error(request: Request, exc: MijiaServiceError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/auth/status", response_model=AuthStatusResponse, tags=["auth"])
def auth_status(service: ServiceDependency) -> dict:
    return service.get_auth_status()


@app.post("/api/auth/qr-login", response_model=QrLoginResponse, tags=["auth"])
def start_qr_login(service: ServiceDependency) -> dict:
    return service.start_qr_login()


@app.post(
    "/api/auth/qr-login/complete", response_model=QrLoginResponse, tags=["auth"]
)
def complete_qr_login(service: ServiceDependency) -> dict:
    """长轮询等待扫码确认，最长等待时间由 mijiaapi 控制。"""
    return service.complete_qr_login()


@app.post("/api/auth/logout", response_model=LogoutResponse, tags=["auth"])
def logout(service: ServiceDependency) -> dict:
    return service.logout()


@app.get("/api/homes", response_model=list[Home], tags=["devices"])
def list_homes(service: ServiceDependency) -> list[dict]:
    return service.list_homes()


@app.get("/api/homes/{home_id}/rooms", response_model=list[Room], tags=["devices"])
def list_rooms(home_id: str, service: ServiceDependency) -> list[dict]:
    return service.list_rooms(home_id)


@app.get("/api/devices", response_model=list[DeviceSummary], tags=["devices"])
def list_devices(
    service: ServiceDependency, home_id: str | None = None
) -> list[dict]:
    return service.list_devices(home_id=home_id)


@app.get("/api/devices/{did}", response_model=DeviceDetail, tags=["devices"])
def get_device(did: str, service: ServiceDependency) -> dict:
    return service.get_device_detail(did)


@app.put(
    "/api/devices/{did}/properties/{property_name}",
    response_model=PropertySetResponse,
    tags=["controls"],
)
def set_device_property(
    did: str,
    property_name: str,
    payload: PropertySetRequest,
    service: ServiceDependency,
) -> dict:
    return service.set_property(did, property_name, payload.value)


@app.post(
    "/api/devices/{did}/actions/{action_name}",
    response_model=ActionResponse,
    tags=["controls"],
)
def run_device_action(
    did: str,
    action_name: str,
    service: ServiceDependency,
    payload: ActionRequest | None = None,
) -> dict:
    values = payload.values if payload is not None else None
    return service.run_action(did, action_name, values)
