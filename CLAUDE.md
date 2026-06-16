# bme280_sensor_to_hub

Raspberry Pi に接続した BME280 センサー（温度・湿度・気圧）を定期的に読み取り、
`raspi-esp32-status-panel`（ハブ）が監視する JSON ファイルとして書き出すサービス。

## システム構成

- ハブ（`raspi-esp32-status-panel`、別リポジトリ・別プロセス）は `hub/data/*.json` を
  監視し、HTTP 経由で ESP32 の OLED に配信する既存システム。
- 本リポジトリはそのハブに対する「各サービス」の一つ。ハブのコードは参照しない。
- 本サービスの責務は BME280 から値を取得し、契約に従った JSON ファイルを
  指定ディレクトリに書き出すことのみ。

## 技術スタック

- 言語: Python 3
- センサー接続: I2C（smbus2 を直接使用し、BME280 のレジスタ読み出し・補正計算は自前実装）
- 依存管理: venv + requirements.txt
- 常駐方式: systemd サービス（自動起動・自動再起動）

## JSON 出力契約

書き込み先: `<configured_dir>/bme280.json`（ディレクトリは環境ごとに異なるため設定可能。
`BME280_HUB_DATA_DIR` 環境変数で指定）

```json
{
  "updated_at": "2024-01-01T12:34:56",
  "lines": ["BME280 12:34", "Temp: 23.4C", "Humid: 45.6%", "Press: 1013hPa"]
}
```

- `lines` は必ず 4 要素。値がない場合は `""`（空文字）。
- `updated_at` は ISO 8601・ローカル時刻（タイムゾーン情報なし、`datetime.now().isoformat()` 相当）。
- 書き込みは一時ファイルへ書いてから `os.replace` でリネームするアトミック write。
  読み取り側に不完全な JSON を見せないこと。

### lines の内容（固定フォーマット）

1. `BME280 hh:mm` — 最終更新時刻（時:分のみ、日付は OLED が小さく入らないため含めない）
2. `Temp: <値>C`
3. `Humid: <値>%`
4. `Press: <値>hPa`

## 設定（環境変数）

- `BME280_HUB_DATA_DIR`: JSON 書き込み先ディレクトリ（必須、デフォルトなし）
- `BME280_POLL_INTERVAL_SEC`: センサー取得・JSON 書き込み間隔（デフォルト 60 秒）
- `BME280_I2C_BUS`: I2C バス番号（デフォルト 1）
- `BME280_I2C_ADDRESS`: I2C アドレス（デフォルト 0x76、配線により 0x77 の場合あり）

## エラーハンドリング方針

- I2C 読み出しに失敗した場合、JSON ファイルは更新しない（古い値を上書きしない）。
- 失敗時は標準エラー出力 / journald にログを残す。
- `lines[0]`（`BME280 hh:mm`）は直近の成功した更新時刻を表すため、表示が更新されていない
  ことで読み取り側が鮮度の劣化に気づける。

## systemd

- サービスユニットはリポジトリ内に同梱し、`systemctl enable --now` で自動起動できるようにする。
- 異常終了時は自動再起動（`Restart=on-failure`）。
- 環境変数は systemd の `Environment=` または `EnvironmentFile=` で注入する。

## ディレクトリ構成

```
bme280_sensor_to_hub/
  CLAUDE.md
  README.md
  requirements.txt
  .env.example          # .env のテンプレート（値なし、コミット対象）
  .gitignore
  src/
    bme280_sensor_to_hub/
      __init__.py
      __main__.py        # エントリポイント（python -m bme280_sensor_to_hub）
      config.py           # 環境変数の読み込み・検証
      driver.py           # I2C 経由の BME280 レジスタ読み出し・補正計算
      writer.py           # JSON のアトミック write
      service.py          # ポーリングループ本体
  systemd/
    bme280-sensor-to-hub.service
  tests/
    test_driver.py
    test_writer.py
```

## 秘密情報の扱い

- このプロジェクトに API キー等の秘密情報は想定していないが、`.env`（実際の設定値）は
  `.gitignore` 済みでコミットしない。リポジトリには値の入っていない `.env.example` のみ置く。
- `systemd/*.service` 内に実際のパスや値を直接書き込まない。環境ごとの値は
  デプロイ先の `.env`（`EnvironmentFile=`）側で注入する。
- コミット前に `git status` / `git diff` で `.env` や認証情報らしきファイルが
  紛れ込んでいないか必ず確認する。

## 開発時の注意

- ハブ側のコードベースは別リポジトリのため、このリポジトリからは参照・編集しない。
  ハブとの整合性に疑問があれば実装を進める前に確認する。
- センサー値の補正計算（温度・湿度・気圧）は BME280 データシートの補正式に従う。
  外部ライブラリのソースを参考にしてよいが、依存としては追加しない。
