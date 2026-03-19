# DHGripperWithRealManRobot
DHGripper with RealManRobot

## dhag95gripper_cli.py

### 目的
  - RM65 の末端 RS485 に接続された DH Robotics AG160-95 グリッパーを、
    コマンドラインから「開く / 閉じる」および「ON / OFF（通信制御の有効化・解除）」できるツールです。

### 前提条件（重要）
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

### 依存パッケージ
  - Python: `rclpy` / `std_msgs` / `rm_ros_interfaces` 等が必要です。
  - もし import エラーが出る場合は、ROS2 パッケージ（rm_ros_interfaces など）がビルド/インストール済みか確認してください。

### 使い方（例）
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

## 安全上の注意
  - グリッパー駆動は物理的な動作です。必ず周囲の安全を確認してください。
  - 連続実行する場合は、機械が動き切るまで待つことを推奨します（`--wait` やデフォルトの 2.0 を目安にしてください）。
