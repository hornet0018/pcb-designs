# YM2151 シールド ESP32-S3 → MCP23S17T-E/SS 改版検討書

## 1. 概要

本書は、YM2151 シールドを ESP32-S3（ESP32-S3-DevKitC-1 等）で動作させる際の**GPIO エクスパンダ方式**を検討したものです。

従来案（SN74LVC8T245 + 2N7002 レベルシフタ）では ESP32-S3 から 13 本の GPIO（D0-D7、/CS、/RD、/WR、A0、/IC）を個別に制御していましたが、本書では **MCP23S17T-E/SS（SPI 16bit GPIO エクスパンダ）** を介して YM2151 と通信する方式に改版します。これにより ESP32-S3 側は SPI 4 本（SCK、MOSI、MISO、CS）のみで済み、GPIO の節約と配線の簡素化を図ります。

YM2151 / YM3012 / PC900 は引き続き 5V 動作です。ESP32-S3 は 3.3V ロジックのため、**電圧レベル変換が必須** です。本書では MCP23S17T-E/SS を **5V 駆動** とし、ESP32-S3 との SPI 線には 2N7002 ベースの MOSFET レベルシフタを使用します。

---

## 2. 現状の接続と改版の狙い

### 2.1 旧方式（個別 GPIO 制御）の課題

| 信号 | 旧 Arduino ピン | 旧 ESP32-S3 GPIO | 用途 |
|:----:|:---------------:|:----------------:|:-----|
| YM2151 D0 | D2 | GPIO7 | データバス |
| YM2151 D1 | D3 | GPIO8 | データバス |
| YM2151 D2 | D4 | GPIO9 | データバス |
| YM2151 D3 | D5 | GPIO10 | データバス |
| YM2151 D4 | D6 | GPIO15 | データバス |
| YM2151 D5 | D7 | GPIO16 | データバス |
| YM2151 D6 | D8 | GPIO17 | データバス |
| YM2151 D7 | D9 | GPIO18 | データバス |
| YM2151 /CS | D10 | GPIO38 | チップセレクト |
| YM2151 /RD | D11 | GPIO39 | リードストローブ |
| YM2151 /WR | D12 | GPIO41 | ライトストローブ |
| YM2151 /IC | D13 | GPIO42 | リセット |
| YM2151 A0 | A0 | GPIO1 | アドレス/データ選択 |

旧方式では YM2151 制御に 13 本の GPIO を消費していました。ESP32-S3 でも動作しますが、他の周辺（UART、I2S、SPI 等）を使う際に GPIO が逼迫する可能性があります。

### 2.2 新方式（MCP23S17T-E/SS 経由）の利点

- **ESP32-S3 GPIO の節約**: SPI 4 本（SCK、MOSI、MISO、CS）で YM2151 を制御可能
- **配線の簡素化**: データバス・制御線を MCP23S17 内部で一元管理
- **読み出し対応**: SPI 経由で YM2151 のステータス（busy フラグ等）を読み出し可能
- **拡張性**: 3 本の予備 GPIO（GPB5-GPB7）を将来用途に確保

---

## 3. MCP23S17T-E/SS 改版の検討ポイント

### 3.1 電圧レベルの違い（最重要）

| 項目 | ESP32-S3 | MCP23S17T-E/SS | YM2151 / YM3012 |
|:----:|:--------:|:--------------:|:---------------:|
| ロジック電圧 | 3.3V | **5V（本設計）** | 5V |
| GPIO 5V 耐性 | なし | — | — |

- MCP23S17T-E/SS を 5V 駆動することで、YM2151 の 5V TTL 入力を確実に駆動します。
- ESP32-S3 からの SPI 信号（3.3V）を MCP23S17 の 5V 入力にそのまま入れると、VIH（0.7×VDD = 3.5V）を下回る可能性があり、動作が不安定になります。
- したがって **ESP32-S3 ↔ MCP23S17 間の SPI 線にはレベルシフタを挟みます**。

### 3.2 推奨レベル変換回路

SPI 線 4 本（SCK、MOSI、MISO、CS）を NXP AN97055 方式の **2N7002 MOSFET レベルシフタ** で変換します。従来案と同じ部品を流用でき、BOM 管理が容易です。

```text
      3.3V                    5V
        │                      │
      [4.7kΩ]               [4.7kΩ]
        │                      │
ESP32-S3 GPIO ──┬── S ┌────────┐ D ── MCP23S17 ピン
                │     │ 2N7002 │
                └─────┤        │
                  G ── └────────┘
                 （G は 3.3V に接続）
```

- **ゲート**: 3.3V に接続
- **ソース**: 3.3V 側（ESP32-S3 GPIO）、4.7kΩ で 3.3V にプルアップ
- **ドレイン**: 5V 側（MCP23S17 ピン）、4.7kΩ で 5V にプルアップ
- 対象信号（全 4 本）: SCK、MOSI、MISO、CS
- MISO は双方向回路ですが、実際の方向は MCP23S17 → ESP32-S3 となります

#### 部品表（レベル変換部のみ）

| 部品 | LCSC 品番 | パッケージ | 数量 | 用途 |
|:-----|:---------:|:----------:|:----:|:-----|
| MCP23S17T-E/SS | **C128577** | SSOP-28 | 1 | SPI 16bit GPIO エクスパンダ |
| 2N7002 Nch MOSFET | **C8545** | SOT-23 | 4 | SPI 線レベルシフタ |
| 4.7kΩ 抵抗 ±1% | **C23162** | 0603 | 8 | MOSFET シフタの両側プルアップ |
| 100nF 50V X7R セラミック | **C1591** | 0603 | 1 | MCP23S17 VDD デカップリング |

- MCP23S17T-E/SS（C128577）は 2026-08 時点で LCSC に在庫ありであることを確認済みです。

### 3.3 MCP23S17T-E/SS のピンアサイン

MCP23S17T-E/SS の 16 本 GPIO を以下のように割り当てます。

#### Port A（GPA0-GPA7）→ YM2151 データバス

| MCP23S17 ピン | ピン名 | 接続先 | 用途 |
|:-------------:|:------:|:------:|:-----|
| 21 | GPA0 | YM2151 D0 | データバス bit0 |
| 22 | GPA1 | YM2151 D1 | データバス bit1 |
| 23 | GPA2 | YM2151 D2 | データバス bit2 |
| 24 | GPA3 | YM2151 D3 | データバス bit3 |
| 25 | GPA4 | YM2151 D4 | データバス bit4 |
| 26 | GPA5 | YM2151 D5 | データバス bit5 |
| 27 | GPA6 | YM2151 D6 | データバス bit6 |
| 28 | GPA7 | YM2151 D7 | データバス bit7 |

#### Port B（GPB0-GPB7）→ YM2151 制御線

| MCP23S17 ピン | ピン名 | 接続先 | 用途 |
|:-------------:|:------:|:------:|:-----|
| 1 | GPB0 | YM2151 /CS | チップセレクト |
| 2 | GPB1 | YM2151 /RD | リードストローブ |
| 3 | GPB2 | YM2151 /WR | ライトストローブ |
| 4 | GPB3 | YM2151 A0 | アドレス/データ選択 |
| 5 | GPB4 | YM2151 /IC | リセット |
| 6-8 | GPB5-GPB7 | 未接続（予備） | 将来拡張用 |

- **YM2151 /CS はシールド側でプルアップされています**。MCP23S17 の GPIO がハイインピーダンス状態（電源投入直後やリセット時）でも /CS は High（インアクティブ）に保たれるため、誤書き込みが防止されます。
- **GPB0 → YM2151 /CS は直接配線** してください。GPB0 と /CS の間に特別な部品は不要です。/CS 側のプルアップ抵抗はシールド側に既にあるため、本基板側では追加のプルアップは不要です。GPB0 は能動的に Low を駆動して /CS をアクティブ（Low）にし、High インピーダンスまたは High 出力時はシールド側のプルアップで /CS は High（インアクティブ）に保たれます。
- プルアップ抵抗が 4.7kΩ や 10kΩ であれば、MCP23S17 の出力が十分に Low を駆動できます（ sink 電流は数 mA 以下）。通常の TTL 入力として動作する YM2151 では問題ありません。

#### SPI・制御ピン

| MCP23S17 ピン | ピン名 | 接続先 | 備考 |
|:-------------:|:------:|:------:|:-----|
| 9 | VDD | +5V | 5V 駆動 |
| 10 | VSS | GND | グランド |
| 11 | CS# | レベルシフタ経由 → ESP32-S3 GPIO10 | SPI チップセレクト |
| 12 | SCK | レベルシフタ経由 → ESP32-S3 GPIO7 | SPI クロック |
| 13 | SI | レベルシフタ経由 → ESP32-S3 GPIO8 | SPI MOSI |
| 14 | SO | レベルシフタ経由 → ESP32-S3 GPIO9 | SPI MISO |
| 15 | A0 | GND | デバイスアドレス bit0 = 0 |
| 16 | A1 | GND | デバイスアドレス bit1 = 0 |
| 17 | A2 | GND | デバイスアドレス bit2 = 0 |
| 18 | RESET# | +5V（プルアップ） | 通常動作時は High |
| 19 | INTB | 未接続 | 割り込み出力 B |
| 20 | INTA | 未接続 | 割り込み出力 A |

- **アドレス**: A0=A1=A2=GND により、SPI コマンドバイトは `0x40`（書き込み）、`0x41`（読み出し）となります。
- **RESET#**: 5V プルアップ（10kΩ 推奨）で常時 High とし、電源投入時のリセットを確実にします。ソフトウェアリセットが必要な場合は ESP32-S3 の GPIO 経由で制御可能ですが、その場合もレベルシフタを介するか、5V  tolerant な回路が必要です。
- **VDD 近傍に 100nF デカップリングコンデンサ** を配置してください。

### 3.4 電源

- シールドの 5V → MCP23S17T-E/SS の VDD、MOSFET シフタの 5V 側プルアップ抵抗
- ESP32-S3 ボードの 5V または VIN → シールド 5V
- ESP32-S3 ボード内蔵の 3.3V レギュレータで 3.3V を生成
- ESP32-S3 の 3.3V → 2N7002 のゲート、3.3V 側プルアップ抵抗
- YM2151 / YM3012 / PC900 はシールドの 5V をそのまま使用

### 3.5 クロック

- シールド上の **4MHz 発振子が YM2151 CLK に供給** されています。
- ESP32-S3 側で CLK を生成する必要はありません。

### 3.6 /IC ピン（リセット）

- MCP23S17 の GPB4 を YM2151 /IC に接続します。
- 電源投入後、GPB4 を一定期間 Low にして YM2151 の内部レジスタを初期化してください。

---

## 4. ESP32-S3 ピンアサイン案

### 4.1 推奨 GPIO 割り当て

| 信号 | MCP23S17 ピン | ESP32-S3 GPIO | コネクタピン | 備考 |
|:----:|:-------------:|:-------------:|:------------:|:-----|
| SCK | 12 | **GPIO7** | J2-8 | SPI クロック（レベルシフタ経由） |
| MOSI (SI) | 13 | **GPIO8** | J2-11 | SPI マスター出力（レベルシフタ経由） |
| MISO (SO) | 14 | **GPIO9** | J2-16 | SPI マスター入力（レベルシフタ経由） |
| CS | 11 | **GPIO10** | J2-15 | SPI チップセレクト（レベルシフタ経由） |

- 上記割り当ては J2 コネクタにまとまっており、配線が交差しにくい配置です。
- SPI ピンは ESP32-S3 の SPI ペリフェラルにマッピング可能です。ソフトウェア SPI でも動作します。

### 4.2 ピン選択の注意点

- **使用しないピン（コネクタに出ているが未割り当て）**:
  - **GPIO15, GPIO16, GPIO17, GPIO18**: 旧方式でデータバスに使用されていましたが、新方式では未使用。
  - **GPIO2, GPIO4, GPIO5, GPIO6**: A1 ~ A4 のアナログ入力は不要のため未使用。
  - **GPIO43 (TXD0), GPIO44 (RXD0)**: UART0。**使用しません**。
  - **GPIO0, GPIO3, GPIO45**: Strapping ピン。起動モードに影響しないよう、信号は割り当てません。
  - **GPIO35, GPIO36, GPIO37**: PSRAM 搭載モジュールでは占有されるため使用しません。
  - **GPIO46, GPIO48**: 未使用。

---

## 5. ハードウェア実装例

### 5.1 ブロック図

```text
[ESP32-S3]                    [MCP23S17T-E/SS]              [YM2151 シールド]
  GPIO7  ──SCK──┐                SCK ──┐
  GPIO8  ──MOSI─┼→[2N7002×4]→── SI   │
  GPIO9  ──MISO─┘                SO   │
  GPIO10 ──CS───┘                CS#  │
                                  │    │
                               GPA0-GPA7 ── D0-D7
                               GPB0 ────── /CS
                               GPB1 ────── /RD
                               GPB2 ────── /WR
                               GPB3 ────── A0
                               GPB4 ────── /IC
                                  │
                                 VDD ── +5V
                                 VSS ── GND
```

### 5.2 電源配線

- シールドの 5V → MCP23S17 VDD、MOSFET シフタの 5V 側プルアップ抵抗
- シールドの GND → MCP23S17 VSS、ESP32-S3 GND
- ESP32-S3 の 3.3V → 2N7002 のゲート、3.3V 側プルアップ抵抗
- MCP23S17 VDD 近傍に 100nF のデカップリングコンデンサを配置

---

## 6. ソフトウェア変更点

### 6.1 開発環境

- **Arduino IDE**: ボードマネージャで `esp32 by Espressif Systems` を追加し、ボードを **ESP32S3 Dev Module** に設定します。
- **PlatformIO**: `platform = espressif32`、`board = esp32-s3-devkitc-1` 等を使用します。

### 6.2 MCP23S17 レジスタ定義

```cpp
#define MCP23S17_ADDR  0x40  // A0=A1=A2=GND

// MCP23S17 レジスタアドレス
#define MCP_IODIRA     0x00
#define MCP_IODIRB     0x01
#define MCP_GPIOA      0x12
#define MCP_GPIOB      0x13
#define MCP_OLATA      0x14
#define MCP_OLATB      0x15
```

### 6.3 ピン定義

```cpp
#define YM_SCK   7
#define YM_MOSI  8
#define YM_MISO  9
#define YM_CS    10
```

### 6.4 初期化

```cpp
void mcp23s17_write(uint8_t reg, uint8_t data) {
  digitalWrite(YM_CS, LOW);
  SPI.transfer(MCP23S17_ADDR);  // 書き込みコマンド
  SPI.transfer(reg);
  SPI.transfer(data);
  digitalWrite(YM_CS, HIGH);
}

uint8_t mcp23s17_read(uint8_t reg) {
  digitalWrite(YM_CS, LOW);
  SPI.transfer(MCP23S17_ADDR | 0x01);  // 読み出しコマンド
  SPI.transfer(reg);
  uint8_t data = SPI.transfer(0x00);
  digitalWrite(YM_CS, HIGH);
  return data;
}

void ym2151_init() {
  SPI.begin(YM_SCK, YM_MISO, YM_MOSI, YM_CS);
  pinMode(YM_CS, OUTPUT);
  digitalWrite(YM_CS, HIGH);

  // Port A, B をすべて出力に設定
  mcp23s17_write(MCP_IODIRA, 0x00);
  mcp23s17_write(MCP_IODIRB, 0x00);

  // 初期状態: /CS=/RD=/WR=A0=/IC=High
  mcp23s17_write(MCP_GPIOA, 0x00);  // D0-D7 = 0
  mcp23s17_write(MCP_GPIOB, 0x1F);  // GPB0=/CS=1, GPB1=/RD=1, GPB2=/WR=1, GPB3=A0=1, GPB4=/IC=1

  // YM2151 /IC リセットパルス
  mcp23s17_write(MCP_GPIOB, 0x0F);  // /IC = Low（GPB4=0）
  delay(10);
  mcp23s17_write(MCP_GPIOB, 0x1F);  // /IC = High
}
```

### 6.5 YM2151 書き込みシーケンス

```cpp
void ym2151_write(uint8_t addr, uint8_t data) {
  // GPB0=/CS, GPB1=/RD, GPB2=/WR, GPB3=A0, GPB4=/IC

  // アドレス書き込み（A0=High）
  mcp23s17_write(MCP_GPIOA, addr);      // D0-D7 = address
  mcp23s17_write(MCP_GPIOB, 0x1E);      // /CS=0, /RD=1, /WR=1, A0=1, /IC=1
  mcp23s17_write(MCP_GPIOB, 0x1A);      // /WR=0
  mcp23s17_write(MCP_GPIOB, 0x1E);      // /WR=1
  mcp23s17_write(MCP_GPIOB, 0x1F);      // /CS=1

  // データ書き込み（A0=Low）
  mcp23s17_write(MCP_GPIOA, data);      // D0-D7 = data
  mcp23s17_write(MCP_GPIOB, 0x16);      // /CS=0, /RD=1, /WR=1, A0=0, /IC=1
  mcp23s17_write(MCP_GPIOB, 0x12);      // /WR=0
  mcp23s17_write(MCP_GPIOB, 0x16);      // /WR=1
  mcp23s17_write(MCP_GPIOB, 0x1F);      // /CS=1
}
```

### 6.6 busy フラグ読み出し

必要に応じて、MCP23S17 の Port A を入力に切り替えて /RD ストローブを発生させ、YM2151 のステータスを読み出します。

```cpp
uint8_t ym2151_read_status() {
  // GPB0=/CS, GPB1=/RD, GPB2=/WR, GPB3=A0, GPB4=/IC

  mcp23s17_write(MCP_IODIRA, 0xFF);     // Port A = input
  mcp23s17_write(MCP_GPIOB, 0x16);      // /CS=0, /RD=1, /WR=1, A0=0, /IC=1
  mcp23s17_write(MCP_GPIOB, 0x14);      // /RD=0
  uint8_t status = mcp23s17_read(MCP_GPIOA);
  mcp23s17_write(MCP_GPIOB, 0x16);      // /RD=1
  mcp23s17_write(MCP_GPIOB, 0x1F);      // /CS=1
  mcp23s17_write(MCP_IODIRA, 0x00);     // Port A = output
  return status;
}
```

### 6.7 タイミング調整

- MCP23S17 への SPI 通信は 10MHz 程度まで可能ですが、YM2151 の /WR パルス幅を確保するため、各ストローブ間に十分な遅延を入れてください。
- MOSFET レベルシフタの立ち上がりは 4.7kΩ × 配線容量の時定数で決まります。配線を短く保ち、必要に応じて待ち時間を調整してください。
- YM2151 のデータシート記載のセットアップ/ホールド時間を満たすよう、必要に応じて `delayMicroseconds()` 等で調整してください。

---

## 7. リスクと対策

| リスク | 内容 | 対策 |
|:-------|:-----|:-----|
| 5V 電圧が ESP32-S3 GPIO に印加 | GPIO 破損 | SPI 線に 2N7002 レベルシフタを挿入し、ESP32-S3 側を 3.3V に制限 |
| 3.3V SPI 信号が MCP23S17 に認識されない | VIH マージン不足 | 2N7002 シフタで 5V 振幅に変換 |
| MCP23S17 起動時の GPIO 浮動 | 誤バスサイクル | YM2151 /CS はシールド側でプルアップされているため自然に High（インアクティブ）。電源投入直後はソフトウェアで即座に初期化 |
| タイミング遅延不足 | YM2151 のセットアップ/ホールド違反 | ソフトウェアで適切な待ち時間を確保 |

---

## 8. まとめ

| 項目 | 結論 |
|:-----|:-----|
| 改版可否 | **可能** |
| 必須ハード変更 | **MCP23S17T-E/SS（5V 駆動）+ SPI 線用 2N7002 レベルシフタ × 4** |
| 必須ソフト変更 | SPI 初期化、MCP23S17 レジスタ設定、YM2151 書き込みシーケンスの変更 |
| ESP32-S3 GPIO 削減 | 13 本 → 4 本（SCK、MOSI、MISO、CS） |
| 推奨ボード | ESP32-S3-DevKitC-1 または互換ボード |

MCP23S17T-E/SS による GPIO エクスパンダ方式は、ESP32-S3 の GPIO を大幅に節約しながら YM2151 の全機能（書き込み・読み出し）を制御できます。電圧レベル変換を正しく行えば、安定した動作が期待できます。
