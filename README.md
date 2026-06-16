# bme280_sensor_to_hub

Raspberry Pi に接続した BME280 センサー(温度・湿度・気圧)を定期的に読み取り、
`raspi-esp32-status-panel` ハブが監視する JSON ファイルとして書き出すサービスです。
詳細な設計・契約は [CLAUDE.md](./CLAUDE.md) を参照してください。

## セットアップ

### 1. 配線

BME280 を I2C で Raspberry Pi に接続します(SDA/SCL/VCC/GND の4本)。
`raspi-config` で I2C を有効化しておいてください。

```bash
sudo raspi-config  # Interface Options -> I2C -> Enable
```

接続確認:

```bash
sudo apt install -y i2c-tools
i2cdetect -y 1
```

`0x76` または `0x77` にデバイスが見えていれば接続成功です。

### 2. venv と依存パッケージ

```bash
cd bme280_sensor_to_hub
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

開発時(テストを実行する場合)は `requirements-dev.txt` を使います。

```bash
.venv/bin/pip install -r requirements-dev.txt
```

### 3. 設定

`.env.example` をコピーして `.env` を作り、環境に合わせて値を編集します。

```bash
cp .env.example .env
```

| 環境変数 | 必須 | デフォルト | 説明 |
|---|---|---|---|
| `BME280_HUB_DATA_DIR` | ✅ | なし | `bme280.json` の書き込み先ディレクトリ(ハブの `hub/data`) |
| `BME280_POLL_INTERVAL_SEC` | - | `60` | センサー取得・JSON書き込みの間隔(秒) |
| `BME280_I2C_BUS` | - | `1` | I2Cバス番号 |
| `BME280_I2C_ADDRESS` | - | `0x76` | I2Cアドレス(配線により `0x77` の場合あり) |

`.env` はコミットしないでください(`.gitignore` 済み)。

## 実行(動作確認)

```bash
cd bme280_sensor_to_hub
set -a; source .env; set +a
PYTHONPATH=src .venv/bin/python -m bme280_sensor_to_hub
```

`$BME280_HUB_DATA_DIR/bme280.json` が更新されていくことを確認してください。

## テスト

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/
```

## systemd への登録

```bash
sudo cp systemd/bme280-sensor-to-hub.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bme280-sensor-to-hub.service
```

ユニットファイル中の `WorkingDirectory` / `EnvironmentFile` / `ExecStart` のパスは、
実際にデプロイした場所に合わせて書き換えてください(デフォルトは `/opt/bme280_sensor_to_hub`)。

状態確認・ログ:

```bash
sudo systemctl status bme280-sensor-to-hub.service
journalctl -u bme280-sensor-to-hub.service -f
```
