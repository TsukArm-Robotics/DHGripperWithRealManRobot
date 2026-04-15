#!/usr/bin/env python3
"""
dhag95gripper.py  — ROS2-free version using RM_API2

RM65 の RS485 に接続された DH Robotics AG95 グリッパーを
RM_API2 (Robotic_Arm) 経由で制御するライブラリです。

依存:
    pip install Robotic_Arm

RS485 ポート番号について (rm_set_modbus_mode の port 引数):
    port = 0 : コントローラ RS485 (コントローラ筐体側)
    port = 1 : ツール端末 RS485  (アーム末端側)  ← AG95 はここに接続

AG95 Modbus レジスタマップ (Function Code 06: Write Single Register):
    0x0100 (256) : 初期化  — 0x01=初期化, 0xA5=再初期化(フル)
    0x0101 (257) : 力      — 20-100 (%)
    0x0102 (258) : 速度    — 1-100  (%)
    0x0103 (259) : 位置    — 0-1000 (‰)  0=完全閉じ, 1000=完全開き
    0x0200 (512) : 初期化状態  [読取専用] 0=未初期化, 1=初期化済
    0x0201 (513) : グリッパー状態 [読取専用] 0=動作中, 1=到達, 2=把持, 3=脱落
    0x0202 (514) : 現在位置 [読取専用]

Slave address (AG95 デフォルト): 1
Baudrate: 115200
"""

from __future__ import annotations
import time
from Robotic_Arm.rm_robot_interface import *


# ── AG95 レジスタ定数 ─────────────────────────────────────────────────────────
REG_INIT     = 0x0100   # 初期化
REG_FORCE    = 0x0101   # 力 (20-100%)
REG_SPEED    = 0x0102   # 速度 (1-100%)
REG_POSITION = 0x0103   # 目標位置 (0-1000)
REG_STATE_INIT = 0x0200 # 初期化状態
REG_STATE_GRIP = 0x0201 # グリッパー状態
REG_POS_CURRENT = 0x0202 # 現在位置

VAL_INIT_NORMAL = 0x01  # 通常初期化
VAL_INIT_FULL   = 0xA5  # 再初期化（フル）

POSITION_OPEN  = 1000   # 完全開き
POSITION_CLOSE = 0      # 完全閉じ

DEFAULT_FORCE  = 50     # デフォルト力 (%)
DEFAULT_SPEED  = 50     # デフォルト速度 (%)
DEFAULT_SLAVE  = 1      # AG95 スレーブアドレス
DEFAULT_BAUD   = 115200
DEFAULT_PORT   = 1      # ツール端末 RS485
MODBUS_TIMEOUT = 2      # タイムアウト (×100ms 単位 → 200ms)


class DHAG95Gripper:
    """
    RM_API2 経由で AG95 グリッパーを制御するクラス。

    Parameters
    ----------
    robot    : RoboticArm インスタンス (接続済み)
    port     : RS485 ポート番号 (0=コントローラ, 1=ツール端末)
    slave_id : Modbus スレーブアドレス (デフォルト: 1)
    baudrate : RS485 ボーレート (デフォルト: 115200)
    verbose  : デバッグ出力の有無
    """

    def __init__(
        self,
        robot: RoboticArm,
        port: int = DEFAULT_PORT,
        slave_id: int = DEFAULT_SLAVE,
        baudrate: int = DEFAULT_BAUD,
        verbose: bool = True,
    ):
        self._robot    = robot
        self._port     = port
        self._slave    = slave_id
        self._baudrate = baudrate
        self._verbose  = verbose
        self._modbus_open = False

    # ── 内部ユーティリティ ─────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(f"[DHAG95] {msg}")

    def _make_params(self, address: int) -> object:
        """rm_peripheral_read_write_params_t を生成して返す。"""
        params = rm_peripheral_read_write_params_t()
        params.port    = self._port
        params.address = address
        params.device  = self._slave
        params.num     = 1
        return params

    def _write_reg(self, address: int, value: int) -> int:
        """単一レジスタへの書き込み。戻り値 0 = 成功。"""
        params = self._make_params(address)
        ret = self._robot.rm_write_single_register(params, value)
        if ret != 0:
            self._log(f"  [WARN] write_single_register addr=0x{address:04X} val={value} ret={ret}")
        return ret

    def _read_reg(self, address: int) -> tuple[int, int]:
        """単一レジスタ読み取り。(ret_code, value) を返す。"""
        params = self._make_params(address)
        result = self._robot.rm_read_holding_registers(params)
        # result は (ret_code, value) または (ret_code, [values,...]) の場合あり
        if isinstance(result, (list, tuple)) and len(result) >= 2:
            return int(result[0]), int(result[1]) if not isinstance(result[1], (list, tuple)) else int(result[1][0])
        return -1, 0

    # ── 公開 API ───────────────────────────────────────────────────────────────

    def open_modbus(self) -> None:
        """
        RS485 ポートを Modbus RTU モードで開く。
        on()/initialize() の中から自動的に呼ばれます。
        """
        self._log(f"Modbus RTU を開きます (port={self._port}, baud={self._baudrate}) ...")
        ret = self._robot.rm_set_modbus_mode(self._port, self._baudrate, MODBUS_TIMEOUT)
        if ret != 0:
            raise RuntimeError(f"rm_set_modbus_mode failed: ret={ret}")
        self._modbus_open = True
        self._log("  Modbus RTU モード ON")

    def close_modbus(self) -> None:
        """RS485 ポートの Modbus RTU モードを閉じる (= off 操作)。"""
        self._log(f"Modbus RTU を閉じます (port={self._port}) ...")
        ret = self._robot.rm_close_modbus_mode(self._port)
        if ret != 0:
            self._log(f"  [WARN] rm_close_modbus_mode ret={ret}")
        else:
            self._log("  Modbus RTU モード OFF")
        self._modbus_open = False

    def initialize(
        self,
        force: int = DEFAULT_FORCE,
        speed: int = DEFAULT_SPEED,
        wait: float = 2.0,
        full_init: bool = False,
    ) -> None:
        """
        グリッパーを初期化します。
        1. Modbus RTU モードを開く
        2. 力・速度を設定
        3. 初期化コマンドを送信
        4. wait 秒だけ待機

        Parameters
        ----------
        force     : 把持力 20-100 (%)
        speed     : 動作速度 1-100 (%)
        wait      : 初期化後の待機秒
        full_init : True のとき 0xA5 (再初期化) を送る
        """
        if not self._modbus_open:
            self.open_modbus()

        self._log(f"初期化: force={force}% speed={speed}%")
        self._write_reg(REG_FORCE, max(20, min(100, force)))
        self._write_reg(REG_SPEED, max(1,  min(100, speed)))

        init_val = VAL_INIT_FULL if full_init else VAL_INIT_NORMAL
        self._write_reg(REG_INIT, init_val)

        if wait > 0:
            self._log(f"  {wait:.1f} 秒 待機 ...")
            time.sleep(wait)

        self._log("初期化 完了")

    def open(self, width: int = POSITION_OPEN, wait: float = 2.0) -> None:
        """
        グリッパーを開く。

        Parameters
        ----------
        width : 目標位置 0-1000 (0=完全閉じ, 1000=完全開き)
        wait  : コマンド後の待機秒
        """
        pos = max(0, min(1000, width))
        self._log(f"OPEN: position={pos}")
        self._write_reg(REG_POSITION, pos)
        if wait > 0:
            time.sleep(wait)

    def close(self, wait: float = 2.0) -> None:
        """
        グリッパーを閉じる。

        Parameters
        ----------
        wait : コマンド後の待機秒
        """
        self._log(f"CLOSE: position={POSITION_CLOSE}")
        self._write_reg(REG_POSITION, POSITION_CLOSE)
        if wait > 0:
            time.sleep(wait)

    def set_force(self, force: int) -> None:
        """把持力を設定 (20-100%)。"""
        val = max(20, min(100, force))
        self._log(f"SET FORCE: {val}%")
        self._write_reg(REG_FORCE, val)

    def set_speed(self, speed: int) -> None:
        """動作速度を設定 (1-100%)。"""
        val = max(1, min(100, speed))
        self._log(f"SET SPEED: {val}%")
        self._write_reg(REG_SPEED, val)

    def get_status(self) -> dict:
        """
        グリッパーの現在状態を読み取って辞書で返す。

        Returns
        -------
        dict with keys:
            init_state  : 0=未初期化, 1=初期化済
            grip_state  : 0=動作中, 1=到達, 2=把持, 3=脱落
            position    : 現在位置 0-1000
        """
        _, init  = self._read_reg(REG_STATE_INIT)
        _, grip  = self._read_reg(REG_STATE_GRIP)
        _, pos   = self._read_reg(REG_POS_CURRENT)
        return {"init_state": init, "grip_state": grip, "position": pos}
