"""列出米家家庭和设备，用于验证账号下的设备发现结果。"""

import argparse
import json
import sys

from mijiaAPI import mijiaAPI

from app.config import resolve_auth_data_path
from app.mijia_service import summarize_devices, summarize_homes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--auth-data-path",
        help="认证文件路径；也可通过 MIJIA_AUTH_DATA_PATH 环境变量指定",
    )
    parser.add_argument("--home-id", help="只获取指定家庭的设备；默认获取所有家庭")
    return parser.parse_args()


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

        homes = api.get_homes_list()
        devices = api.get_devices_list(home_id=args.home_id)
    except KeyboardInterrupt:
        print("\n操作已取消。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"获取设备失败: {exc}", file=sys.stderr)
        return 1

    result = {
        "homes": summarize_homes(homes),
        "device_count": len(devices),
        "devices": summarize_devices(devices, homes),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
