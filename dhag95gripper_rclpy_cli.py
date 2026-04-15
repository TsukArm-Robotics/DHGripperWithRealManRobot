#!/usr/bin/env python3
"""
dhag95gripper_cli.py

目的
  - RM65 の末端 RS485 に接続された DH Robotics AG160-95 グリッパーを、
    コマンドラインから「開く / 閉じる」および「ON / OFF（通信制御の有効化・解除）」できるツールです。

前提条件（重要）
  1. ROS2 環境が有効になっていること
     - 例: 実行するROS2のワークスペースを読み込む(RM65のROS2ワークスペースの場合)
       - `source /opt/ros/<ros-distro>/setup.bash`
       - `source ~/ros2_ws/install/setup.bash`
     - 実行前に `ros2 topic list` や `ros2 node list` ができる状態を想定しています。

  2. rm_driver が起動していること
     - dhag95gripper_cli.py が呼んでいるトピックは以下です（ハードコードされています）
       - `/rm_driver/set_controller_rs485_mode_cmd`
       - `/rm_driver/write_modbus_rtu_registers_cmd`
       - `/rm_driver/close_controller_rtu_modbus_cmd`
     - これらはRM65のROS2 launchを実行すると「rm_driver」配下のノードとして現れます が無いと書き込みが飛ばない」構造です。

  3. ハードウェア配線・設定
     - AG95 は RM65 の「ツール端末（末端）」RS485 に接続されていること
     - AG95 の Modbus スレーブアドレス: 1
     - RS485 ボーレート: 115200
     - （dhag95gripper_cli.py 内で上記が固定値です）

依存パッケージ
  - Python: `rclpy` / `std_msgs` / `rm_ros_interfaces` 等が必要です。
  - もし import エラーが出る場合は、ROS2 パッケージ（rm_ros_interfaces など）がビルド/インストール済みか確認してください。

使い方（例）
  - 開く（width=200 は joy_vel_teleop と同じデフォルト）
      python3 dhag95gripper_cli.py open --width 800

  - 閉じる
      python3 dhag95gripper_cli.py close

  - ON（RS485/AG95初期化だけ実行。以後 open/close が有効化前提で動きます）
    - デフォルトでは `close_connection()` を呼ばず、通信制御を「有効化したまま」終了します。
      python3 dhag95gripper_cli.py on

  - OFF（通信制御の解除）
      python3 dhag95gripper_cli.py off

  - ON の直後に OFF もしたい場合（初期化だけしたくない運用）
      python3 dhag95gripper_cli.py on --close-after-on

安全上の注意
  - グリッパー駆動は物理的な動作です。必ず周囲の安全を確認してください。
  - 連続実行する場合は、機械が動き切るまで待つことを推奨します（`--wait` やデフォルトの 2.0 を目安にしてください）。
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import NoReturn


# ros2_ws 直下に dhag95gripper.py がある場合のインポートパス
_WS = os.path.dirname(os.path.abspath(__file__))
if _WS not in sys.path:
    sys.path.insert(0, _WS)

import rclpy
from rclpy.node import Node

from dhag95gripper import DHAG95Gripper


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DHAG95 グリッパーをコマンドラインで開閉/ONOFFするツール",
    )

    sub = parser.add_subparsers(dest="action", required=True)

    # open
    p_open = sub.add_parser(
        "open",
        help="グリッパーを指定幅で開く（initialize/close_connection は行いません。まず on を実行してください）",
    )
    p_open.add_argument("--width", type=int, default=200, help="開き幅 0〜1000（デフォルト: 200）")
    p_open.add_argument("--wait", type=float, default=2.0, help="開コマンド後の待機秒（デフォルト: 2.0）")

    # close
    p_close = sub.add_parser(
        "close",
        help="グリッパーを閉じる（initialize/close_connection は行いません。まず on を実行してください）",
    )
    p_close.add_argument("--wait", type=float, default=2.0, help="閉コマンド後の待機秒（デフォルト: 2.0）")

    # on
    p_on = sub.add_parser(
        "on",
        help="RS485/AG95の初期化（initialize のみ）。デフォルトでは close_connection() を呼ばず終了します。",
    )
    p_on.add_argument(
        "--rs485-wait",
        type=float,
        default=2.0,
        help="initialize 時の RS485 設定後待機秒（デフォルト: 2.0）",
    )
    p_on.add_argument(
        "--extra-wait",
        type=float,
        default=0.0,
        help="initialize 後に追加で待つ秒（デフォルト: 0.0）",
    )
    p_on.add_argument(
        "--close-after-on",
        action="store_true",
        help="initialize 後に OFF（close_connection）も実行して、状態を元に戻します。",
    )

    # off
    p_off = sub.add_parser("off", help="通信制御の解除（close_connection を実行）")

    return parser


def _die(node: Node, msg: str, code: int = 1) -> NoReturn:
    node.get_logger().error(msg)
    raise SystemExit(code)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # ROS2初期化
    rclpy.init()
    node = Node("dhag95_gripper_cli")
    gripper = DHAG95Gripper(node=node)

    try:
        if args.action == "open":
            node.get_logger().warn("open: on（初期化）を先に実行してください。ここでは open コマンドのみ送信します。")
            gripper.open(width=args.width, wait=args.wait)
            node.get_logger().info("完了: open")

        elif args.action == "close":
            node.get_logger().warn("close: on（初期化）を先に実行してください。ここでは close コマンドのみ送信します。")
            gripper.close(wait=args.wait)
            node.get_logger().info("完了: close")

        elif args.action == "on":
            node.get_logger().info("initialize を実行します（デフォルト: close_connection しません）...")
            gripper.initialize(wait_after_rs485=args.rs485_wait)
            if args.extra_wait > 0.0:
                node.get_logger().info(f"extra_wait: {args.extra_wait} 秒 待機します...")
                rclpy.spin_once(node, timeout_sec=args.extra_wait)
                # spin_once で待つのが目的です（publishのみでも動きますが、挙動を安定させる意図）

            if args.close_after_on:
                node.get_logger().info("close-after-on 指定: OFF（close_connection）も実行します...")
                gripper.close_connection(destroy_node=False)
            node.get_logger().info("完了: on（必要なら off を別途実行してください）")

        elif args.action == "off":
            node.get_logger().info("OFF（close_connection）を実行します...")
            gripper.close_connection(destroy_node=False)
            node.get_logger().info("完了: off")

        else:
            _die(node, f"不明な action: {args.action!r}")

    except KeyboardInterrupt:
        node.get_logger().warn("Ctrl+C で中断しました。")
        # 物理動作中の安全確保は利用者側でお願いします。
        raise
    except Exception as e:
        _die(node, f"実行に失敗しました: {e!r}")
    finally:
        # ここでは close_connection を呼ばない（actionごとの意図を優先）。
        # node破棄 + shutdown で、ROS2側のリソースを閉じます。
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

