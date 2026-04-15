# DHGripperWithRealManRobot

RealMan RM65 の RS485 に接続した DH Robotics AG95 系グリッパーを、コマンドラインから操作するための補助スクリプト群です。

## 構成（主要ファイル）

| ファイル | 役割 |
| -------- | ---- |
| `dhag95gripper.py` | AG95 の Modbus レジスタ操作と、`Robotic_Arm`（RM_API2）経由の制御クラス `DHAG95Gripper` |
| `dhag95gripper_rclpy_cli.py` | **rclpy 版 CLI** — ROS2 の `rm_driver` トピック経由で制御（`rclpy` ノードとして動作） |
| `dhag95gripper_python_cli.py` | **Python 版 CLI** — `dhag95gripper.py` の `DHAG95Gripper` を直接使い、アームへ TCP 接続（ROS2 不要） |

## 依存パッケージ（pip と ROS2）

- **RM API2**: RealMan が提供する Python バインディングで、実体は pip で入る **`Robotic_Arm`** パッケージです（PyPI 上の名前やインストール手順はメーカーの SDK 記載に従ってください。例: `pip install Robotic_Arm`）。コードでは `Robotic_Arm.rm_robot_interface` を import します。
- **Python 版**（`dhag95gripper_python_cli.py`）: ROS2 は不要ですが、**上記 RM API2（pip の `Robotic_Arm`）は必須**です。
- **rclpy 版**（`dhag95gripper_rclpy_cli.py`）: ROS2 環境で **`rclpy`** や **`rm_ros_interfaces`** などを `source` して使えることに加え、**RM API2（pip の `Robotic_Arm`）も必要です**。`dhag95gripper.py` が RM API2 を参照するため、ROS 側の依存とは別に pip インストールが要ります。

---

## 共通点

- **対象ハード**: RM65 のツール末端 RS485 に AG95 を接続する想定（ボーレート 115200、スレーブ ID は既定で 1）。
- **操作イメージ**: `on` で RS485／Modbus まわりを有効化してから `open` / `close` を送る流れ（先に初期化が必要な点は両方とも同様）。
- **サブコマンドの対応**: どちらも `on` / `off` / `open` / `close` を持ちます（Python 版のみ追加で `status` があります）。
- **実装上の位置づけ**: Python 版は `dhag95gripper.py` をそのまま利用します。rclpy 版は同じ AG95 を ROS トピック経由で扱うための CLI で、**アームとの接続経路が RM_API2 直結ではなく `rm_driver` になります**（依存パッケージと起動手順が異なります）。

---

## 前提の違い（rclpy 版 vs Python 版）

| 項目 | `dhag95gripper_rclpy_cli.py`（rclpy） | `dhag95gripper_python_cli.py`（Python / RM_API2） |
| ---- | ------------------------------------- | ------------------------------------------------ |
| **ROS2** | 必須（`rclpy`、RM の ROS2 ワークスペース、`rm_ros_interfaces` など） | 不要 |
| **rm_driver** | **起動済みであること**（下記トピックが存在すること） | 不要 |
| **アームとの通信** | ROS トピック経由（IP は rm_driver 側の設定に依存） | TCP（既定 `192.168.1.18:8080`）。`--ip` / `--port` で変更 |
| **RS485 ポート** | スクリプト／ドライバ側の前提に依存（末端ツール想定） | `--rs485-port` で `0`=筐体 RS485、`1`=末端 RS485（既定は 1） |
| **追加の主な機能** | `on` に `--extra-wait` など | `status` 読み取り、`on` に `--force` / `--speed` / `--full-init`、接続系のグローバル引数 |

**rclpy 版が購読／発行のために使うトピック（名前はコード内固定）**

- `/rm_driver/set_controller_rs485_mode_cmd`
- `/rm_driver/write_modbus_rtu_registers_cmd`
- `/rm_driver/close_controller_rtu_modbus_cmd`

（pip / `rclpy` の整理は上記「依存パッケージ（pip と ROS2）」を参照してください。）

---

## コマンド実行方法

作業ディレクトリを本リポジトリのルート（`dhag95gripper.py` と同じ場所）に置いて実行する想定です。

### rclpy 版（`dhag95gripper_rclpy_cli.py`）

1. ROS2 と RM のワークスペースを `source` する。  
2. RM65 用の launch で `rm_driver` が動いていることを確認する（`ros2 topic list` など）。  
3. 例:

```bash
python3 dhag95gripper_rclpy_cli.py on
python3 dhag95gripper_rclpy_cli.py open --width 800
python3 dhag95gripper_rclpy_cli.py close
python3 dhag95gripper_rclpy_cli.py off
```

- `open` の既定 `--width` は **200**（`close` / `open` は内部で `initialize` しません。先に `on` を実行してください）。
- `on` のオプション例: `--rs485-wait`、`--extra-wait`、`--close-after-on`（初期化のあと通信を切りたいとき）。

### Python 版（`dhag95gripper_python_cli.py`）

ROS を立ち上げず、PC からアームの API ポートへ直接つなぎます。

```bash
python dhag95gripper_python_cli.py --ip 192.168.1.18 on
python dhag95gripper_python_cli.py open
python dhag95gripper_python_cli.py open --width 500
python dhag95gripper_python_cli.py close
python dhag95gripper_python_cli.py off
python dhag95gripper_python_cli.py status
```

- すべてのサブコマンドの前に、共通で `--ip`、`--port`、`--rs485-port`、`--slave`、`-q`（安静時ログ）を付けられます。
- `open` の既定 `--width` は **1000**（rclpy 版の既定 200 とは異なるので注意）。
- `on` 例: `--close-after-on`、`--full-init`、把持力・速度 `--force` / `--speed` など。

---

## 安全上の注意

- グリッパー駆動は実機が動きます。実行前に周囲の安全を確認してください。
- 連続でコマンドを打つ場合は、動作が終わるまで待つか、`--wait`（既定 2.0 秒など）を目安に間隔を空けてください。
