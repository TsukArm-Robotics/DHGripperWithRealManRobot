#!/usr/bin/env python3
"""
dhag95gripper_cli.py  — ROS2-free version using RM_API2

目的
  - RM65 の RS485 に接続された DH Robotics AG95 グリッパーを、
    コマンドラインから「開く / 閉じる / ON / OFF」するツール。
  - ROS2・rm_driver 不要。WSL2 を含む任意の Python 環境で動作します。

前提条件
  1. pip install Robotic_Arm
  2. RM65 コントローラと同じネットワーク上に PC があること
     (デフォルト: 192.168.1.18:8080)
  3. dhag95gripper.py が同じディレクトリに置かれていること

RS485 ポート設定 (ARM_RS485_PORT):
  port = 0 : コントローラ筐体の RS485
  port = 1 : アーム末端の RS485  ← AG95 はここに接続 (デフォルト)

使い方
  python dhag95gripper_cli.py on                # Modbus初期化 + グリッパー初期化
  python dhag95gripper_cli.py open              # 完全開き
  python dhag95gripper_cli.py open --width 500  # 半開き (0-1000)
  python dhag95gripper_cli.py close             # 閉じる
  python dhag95gripper_cli.py off               # Modbus RTU モード解除
  python dhag95gripper_cli.py status            # 現在状態の読み取り

  python dhag95gripper_cli.py on --close-after-on  # 初期化後すぐ off する
  python dhag95gripper_cli.py on --full-init        # 再初期化 (0xA5)
"""

from __future__ import annotations

import argparse
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from Robotic_Arm.rm_robot_interface import *
from dhag95gripper import DHAG95Gripper


# ── 設定 ──────────────────────────────────────────────────────────────────────
ARM_IP        = "192.168.1.18"
ARM_PORT      = 8080
ARM_RS485_PORT = 1          # 0=コントローラ RS485, 1=ツール末端 RS485
GRIPPER_SLAVE = 1           # AG95 スレーブアドレス
GRIPPER_BAUD  = 115200


# ── パーサー ──────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="DHAG95 グリッパー CLI (RM_API2 / ROS2 不要)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # 接続設定の共通オーバーライド
    p.add_argument("--ip",   default=ARM_IP,   help=f"アーム IP アドレス (default: {ARM_IP})")
    p.add_argument("--port", type=int, default=ARM_PORT, help=f"アーム ポート (default: {ARM_PORT})")
    p.add_argument("--rs485-port", type=int, default=ARM_RS485_PORT,
                   help=f"RS485 ポート番号 0=コントローラ 1=ツール末端 (default: {ARM_RS485_PORT})")
    p.add_argument("--slave", type=int, default=GRIPPER_SLAVE,
                   help=f"AG95 Modbus スレーブ ID (default: {GRIPPER_SLAVE})")
    p.add_argument("-q", "--quiet", action="store_true", help="詳細ログを抑制")

    sub = p.add_subparsers(dest="action", required=True)

    # on
    s_on = sub.add_parser("on", help="Modbus 有効化 + グリッパー初期化")
    s_on.add_argument("--rs485-wait",  type=float, default=2.0, help="初期化後の待機秒 (default: 2.0)")
    s_on.add_argument("--force",       type=int,   default=50,  help="初期把持力 20-100%% (default: 50)")
    s_on.add_argument("--speed",       type=int,   default=50,  help="初期速度  1-100%%  (default: 50)")
    s_on.add_argument("--full-init",   action="store_true",     help="フル再初期化 (0xA5) を使う")
    s_on.add_argument("--close-after-on", action="store_true",  help="初期化後に Modbus を off する")

    # off
    sub.add_parser("off", help="Modbus RTU モード解除")

    # open
    s_open = sub.add_parser("open", help="グリッパーを開く")
    s_open.add_argument("--width", type=int, default=1000,
                        help="目標位置 0-1000 (default: 1000=完全開き)")
    s_open.add_argument("--wait",  type=float, default=2.0, help="待機秒 (default: 2.0)")

    # close
    s_close = sub.add_parser("close", help="グリッパーを閉じる")
    s_close.add_argument("--wait", type=float, default=2.0, help="待機秒 (default: 2.0)")

    # status
    sub.add_parser("status", help="現在のグリッパー状態を読み取る")

    return p


# ── メイン ────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    verbose = not args.quiet

    # ── アーム接続 ────────────────────────────────────────────────────────────
    print(f"[CLI] RM65 に接続中 {args.ip}:{args.port} ...")
    robot  = RoboticArm(rm_thread_mode_e.RM_TRIPLE_MODE_E)
    handle = robot.rm_create_robot_arm(args.ip, args.port)

    if handle.id == -1:
        print(f"[ERROR] 接続失敗 ({args.ip}:{args.port})")
        sys.exit(1)
    print(f"[CLI] 接続成功 (handle.id={handle.id})")

    gripper = DHAG95Gripper(
        robot    = robot,
        port     = args.rs485_port,
        slave_id = args.slave,
        baudrate = GRIPPER_BAUD,
        verbose  = verbose,
    )

    exit_code = 0

    try:
        if args.action == "on":
            gripper.initialize(
                force      = args.force,
                speed      = args.speed,
                wait       = args.rs485_wait,
                full_init  = args.full_init,
            )
            if args.close_after_on:
                gripper.close_modbus()
            print("[CLI] 完了: on")

        elif args.action == "off":
            gripper.close_modbus()
            print("[CLI] 完了: off")

        elif args.action == "open":
            gripper.open(width=args.width, wait=args.wait)
            print("[CLI] 完了: open")

        elif args.action == "close":
            gripper.close(wait=args.wait)
            print("[CLI] 完了: close")

        elif args.action == "status":
            st = gripper.get_status()
            INIT_LABELS = {0: "未初期化", 1: "初期化済"}
            GRIP_LABELS = {0: "動作中", 1: "位置到達", 2: "把持", 3: "脱落"}
            print("──── AG95 現在状態 ────────────────────────")
            print(f"  初期化状態 : {INIT_LABELS.get(st['init_state'], st['init_state'])}")
            print(f"  グリッパー : {GRIP_LABELS.get(st['grip_state'], st['grip_state'])}")
            print(f"  現在位置   : {st['position']} / 1000")
            print("──────────────────────────────────────────")

        else:
            print(f"[ERROR] 不明なアクション: {args.action!r}")
            exit_code = 1

    except KeyboardInterrupt:
        print("\n[CLI] Ctrl+C で中断しました。")
        exit_code = 130

    except Exception as e:
        print(f"[ERROR] 実行に失敗しました: {e!r}")
        exit_code = 1

    finally:
        print("[CLI] アーム接続を切断します ...")
        robot.rm_delete_robot_arm()
        print("[CLI] 終了")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
