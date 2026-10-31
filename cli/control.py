"""向指定米家设备发送一次开机或关机动作。"""

import argparse
import sys

from mijiaAPI import mijiaAPI, mijiaDevice

from app.config import resolve_auth_data_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--did", required=True, help="要控制的设备 ID")
    parser.add_argument(
        "--action",
        required=True,
        choices=["turn-on", "turn-off"],
        help="turn-on 开机；turn-off 关机",
    )
    parser.add_argument(
        "--auth-data-path",
        help="认证文件路径；也可通过 MIJIA_AUTH_DATA_PATH 环境变量指定",
    )
    return parser.parse_args()


def run_device_action(device: mijiaDevice, action: str) -> None:
    if action not in device.action_list:
        available = ", ".join(device.action_list) or "无"
        raise ValueError(f"设备不支持动作 {action}；可用动作: {available}")
    device.run_action(action)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    auth_data_path = resolve_auth_data_path(args.auth_data_path)

    if not auth_data_path.is_file():
        print(f"认证文件不存在: {auth_data_path}", file=sys.stderr)
        print("请先使用 python -m cli.auth 完成登录。", file=sys.stderr)
        return 1

    try:
        api = mijiaAPI(auth_data_path=str(auth_data_path))
        if not api.available:
            print("Token 无效或已过期，请重新登录。", file=sys.stderr)
            return 1

        device = mijiaDevice(api, did=args.did)
        print(f"设备: {device.name} ({device.model})")
        print(f"发送动作: {args.action}", flush=True)
        run_device_action(device, args.action)
    except KeyboardInterrupt:
        print("\n操作已取消。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"设备控制失败: {exc}", file=sys.stderr)
        return 1

    print("控制指令已发送。红外设备无法回读状态，请观察设备是否实际响应。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
