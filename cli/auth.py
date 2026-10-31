"""米家二维码登录与认证状态验证。"""

import argparse
import sys

from mijiaAPI import mijiaAPI

from app.config import resolve_auth_data_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--auth-data-path",
        help="认证文件路径；也可通过 MIJIA_AUTH_DATA_PATH 环境变量指定",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("login", help="二维码登录；已有有效 Token 时自动跳过")
    subparsers.add_parser("status", help="检查已有认证文件及 Token 是否有效")
    subparsers.add_parser("logout", help="删除本地认证文件，不影响其他设备")
    return parser.parse_args()


def main() -> int:
    # Windows 的默认控制台编码可能导致中文和二维码边框乱码。
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    auth_data_path = resolve_auth_data_path(args.auth_data_path)
    print(f"认证文件路径: {auth_data_path}")

    if args.command == "logout":
        try:
            auth_data_path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"退出登录失败: {exc}", file=sys.stderr)
            return 1
        print("已退出登录，本地认证文件已删除。")
        return 0

    if args.command == "status" and not auth_data_path.is_file():
        print("认证文件不存在，请先执行 login 命令。", file=sys.stderr)
        return 1

    try:
        if args.command == "login":
            auth_data_path.parent.mkdir(parents=True, exist_ok=True)

        api = mijiaAPI(auth_data_path=str(auth_data_path))
        if args.command == "login":
            api.login()

        if not api.available:
            print("Token 无效或已过期，请重新执行 login 命令。", file=sys.stderr)
            return 1
    except KeyboardInterrupt:
        print("\n操作已取消。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"认证操作失败: {exc}", file=sys.stderr)
        return 1

    if args.command == "login" and not auth_data_path.is_file():
        print("登录后未找到认证文件，请检查上述路径。", file=sys.stderr)
        return 1

    print("Token 有效。")
    if args.command == "login":
        print("认证信息已保存；再次执行 login 时将复用有效 Token。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
