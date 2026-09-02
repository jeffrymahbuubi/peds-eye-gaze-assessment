# GazePoint 整合與測試交接文件

> 對象：接手 `peds-eye-gaze-assessment` 的助理／RA
> 目標：把已經打通的 GazePoint GP3HD 接進這個 prototype，並驗證資料正確
> 版本：對應 repo v0.1（commit `4e7e592`）

---

## 0. 現況一句話

程式的 **OpenGaze TCP client 已經寫好、單元測試也過**（29 個測試全綠），
但 **從來沒有接過真機**。整段 pipeline 目前都是靠 `.jsonl` 重播檔在跑。
你們的工作是把「真機」這一段補上，並確認真機資料和重播資料走的是同一條路。

---

## 1. 環境建置

### 1.1 需求

| 項目 | 版本／說明 |
|---|---|
| OS | Windows 10/11（GUI 目標平台；macOS/Linux 可跑 headless 與測試） |
| Python | **>= 3.11**（`pyproject.toml` 有擋，3.9/3.10 會裝不起來） |
| Gazepoint Control | GazePoint 官方 Windows 程式，**必須在背景執行** |
| 硬體 | GP3HD |

### 1.2 安裝

```bash
git clone https://github.com/elfj/peds-eye-gaze-assessment.git
cd peds-eye-gaze-assessment

# 只跑 headless pipeline 與測試（不需要 Qt）
pip install -e ".[dev]"

# 完整 GUI（Windows 實機用這個）
pip install -e ".[gui,dev]"
```

若系統 Python 太舊，建議用 uv 建虛擬環境：

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[gui,dev]"
```

---

## 2. GazePoint 端設定

1. 開啟 **Gazepoint Control**。它會在 `127.0.0.1:4242` 開一個 TCP server。
2. 在 Gazepoint Control 內完成 **使用者校正（calibration）**，記下校正誤差。
   - 本程式目前**不會**幫你跑完整校正 UI（見 §6 缺口 A），請先在原廠程式校好。
3. 確認 Gazepoint Control 的視窗不要蓋住受測畫面，或設定成最小化。
4. 螢幕解析度、坐姿距離固定後就不要再改 —— 座標是正規化的，但 px 換算會受影響（見 §6 缺口 B）。

**協定重點**（完整版見 [`gazepoint_api_cheatsheet.md`](gazepoint_api_cheatsheet.md)）：

- line-based XML over TCP，每則訊息以 `\r\n` 結尾。
- 先送 `<SET ID="ENABLE_SEND_*" STATE="1" />` 訂閱欄位。
- 之後 server 持續推 `<REC ... />`，一筆一個 gaze sample。
- 本程式訂閱：`TIME`、`POG_FIX`、`POG_BEST`、`PUPIL_LEFT`、`PUPIL_RIGHT`、`CURSOR`。

---

## 3. 程式怎麼跟 GazePoint 溝通

### 3.1 資料流

```
Gazepoint Control (TCP 4242)
        │  <REC .../>
        ▼
GazepointClient._run_socket()        背景 thread，只負責讀 socket
        │  parse_rec() → rec_to_sample()
        ▼
GazepointClient.latest() -> GazeSample   （0–1 正規化座標，加鎖）
        │
        ▼
EyeInput.poll(t_ns) -> Pointer       主執行緒，60 Hz QTimer 取樣
        │
        ▼
BaseTask.update(t_ns, pointer)       命中測試 + DwellSelector + trial 狀態機
        │
        ▼
SessionRecorder                       sessions/<id>/{trials.csv, gaze_stream.csv, ...}
```

### 3.2 你只需要看懂這幾個檔案

| 檔案 | 責任 | 你會不會改 |
|---|---|---|
| `src/inputs/gazepoint_client.py` | OpenGaze 連線、解析、重播 | **會**（§6 A/C） |
| `src/engine/calibration.py` | 校正指令與誤差回收 | **會**（§6 A） |
| `src/app.py` | GUI 接線、60 Hz 主迴圈 | **會**（§6 B/C） |
| `src/inputs/eye_input.py` | dwell 累積邏輯 | 通常不用 |
| `src/tasks/base_task.py` | 命中測試、trial 狀態機 | 通常不用 |
| `configs/default.yaml` | 治療師可調參數 | 會（調參） |

### 3.3 兩個一定要記住的約定

1. **座標一律正規化 0–1，原點左上。** `GazepointClient` 輸出的就是 0–1，
   換成像素是 canvas / task 的責任（`norm_to_px()`）。新增任何 tracker 時
   請維持這個約定。
2. **時間一律 `time.time_ns()` 奈秒。** 真機模式用 wall clock；重播模式用
   虛擬時鐘（frame × 1/fps），所以重播完全可重現、沒有 thread。

### 3.4 換掉 tracker 的介面

任何暴露 `latest() -> GazeSample | None` 的物件都可以取代 `GazepointClient`，
引擎不用改。這是刻意設計的擴充點（見 `ARCHITECTURE.md` 的 Extending 一節）。

---

## 4. 第一次接真機的步驟

**照順序做，不要跳。** 每一步都能獨立判斷失敗點。

### Step 1 — 純 socket smoke test（不碰本專案的引擎）

先確認「Gazepoint Control 有在推資料」。把下面存成 `smoke.py` 執行：

```python
import socket, time

sock = socket.create_connection(("127.0.0.1", 4242), timeout=5)
for rid in ("ENABLE_SEND_TIME", "ENABLE_SEND_POG_FIX", "ENABLE_SEND_POG_BEST"):
    sock.sendall(f'<SET ID="{rid}" STATE="1" />\r\n'.encode("ascii"))

sock.settimeout(1.0)
end = time.time() + 5
while time.time() < end:
    try:
        print(sock.recv(4096).decode("ascii", "ignore"), end="")
    except TimeoutError:
        pass
sock.close()
```

**預期**：畫面持續刷出 `<REC TIME="..." FPOGX="..." .../>`。
沒有 → 問題在 Gazepoint Control 或防火牆，不是這個 repo。

### Step 2 — 用專案的 client 讀真機

```python
from src.inputs.gazepoint_client import GazepointClient
import time

c = GazepointClient()
c.connect()            # 預設 127.0.0.1:4242
c.start_streaming()
for _ in range(20):
    print(c.latest())
    time.sleep(0.2)
c.stop()
```

**預期**：印出 `GazeSample(t_ns=..., x=0.xx, y=0.xx, valid=True, ...)`，
且你把視線移到螢幕四角時 x/y 會接近 0/1。
`valid=False` 一直出現 → 校正沒做好或受測者不在追蹤範圍。

### Step 3 — 錄一段真機 fixture（重要！）

把真機資料存成 `.jsonl`，之後所有回歸測試就能離線重跑：

```python
import json, time
from src.inputs.gazepoint_client import GazepointClient

c = GazepointClient(); c.connect(); c.start_streaming()
with open("tests/fixtures/gaze_real_p001.jsonl", "w", encoding="utf-8") as f:
    end = time.time() + 30
    seen = None
    while time.time() < end:
        s = c.latest()
        if s is not None and s.t_ns != seen:
            seen = s.t_ns
            f.write(json.dumps({
                "t_ns": s.t_ns, "x": s.x, "y": s.y, "valid": s.valid,
                "fixation_id": s.fixation_id, "fix_duration_s": s.fix_duration_s,
                "pupil_left": s.pupil_left, "pupil_right": s.pupil_right,
            }) + "\n")
        time.sleep(1 / 60)
c.stop()
```

錄製時請受測者**依序注視四角與中心各 3 秒**，方便之後檢查座標對不對。

> ⚠️ 真人資料屬個資。`.gitignore` 已排除 `sessions/`，但 `tests/fixtures/`
> **沒有**被排除 —— 只 commit 匿名／志願者（例如你自己）的 fixture，
> 不要把個案資料推上去。

### Step 4 — GUI + 真機

```bash
python -m src.main --task click_static --gui
```

**預期**：全螢幕出現目標，紅點（gaze cursor）跟著你的視線走，
停留 800 ms 後 progress ring 跑滿並觸發選取 + 粒子效果。
按 `Esc` 結束，會寫出 session 資料夾。

---

## 5. 測試怎麼做

分五層，由便宜到昂貴。**每次改 code 都要至少跑 L0 + L1。**

### L0 — 單元測試（無硬體、無 GUI，< 1 秒）

```bash
pytest
ruff check .
```

預期：`29 passed`、`All checks passed!`。
GazePoint 相關的測試在 `tests/test_gazepoint_client.py`（REC 解析、
BPOG/FPOG 回退、valid 判定、enable 指令格式、replay 時間索引）。

**你新增任何解析邏輯，就要在這裡補測試。** 這是唯一能在沒有硬體時
擋住回歸的東西。

### L1 — Headless 重播（無硬體、無 GUI）

```bash
python -m src.main --task click_static --replay tests/fixtures/gaze_replay.jsonl
```

預期輸出：

```
[click_static] trials=32 hits=24 timeouts=8
Session written to: sessions/replay_click_static_REPLAY
```

四個任務都要能跑：`--task click_grid|follow_moving|scanning`。
**這個結果是決定性的** —— 同樣的 fixture + seed 應該永遠得到同樣的數字。
數字變了就是有東西壞了。

Step 3 錄好真機 fixture 之後，改用它再跑一次：

```bash
python -m src.main --task click_static --replay tests/fixtures/gaze_real_p001.jsonl
```

### L2 — GUI + 假重播（無硬體，要 Qt）

```bash
python -m src.main --task click_static --gui --replay tests/fixtures/gaze_replay.jsonl
```

檢查：畫面全螢幕、cursor 有動、progress ring 會轉、operator panel 的
FPS 顯示接近 60、pause/skip/dwell slider 都有反應。

### L3 — GUI + 真機

見 §4 Step 4。額外檢查清單：

- [ ] 注視螢幕**四角**時，紅點確實落在四角（不是縮在中間或跑出畫面）
- [ ] 眨眼時紅點不會亂飛（`valid=False` 有被吃掉）
- [ ] dwell 800 ms 觸發的時機和體感一致
- [ ] operator panel 的 FPS ≥ 55
- [ ] 按 `Esc` 能正常結束並寫出檔案

### L4 — 資料驗證（真機收完一筆之後）

```bash
python analysis/analyze_session.py sessions/<session_id>
```

會印出 RT 摘要與 gaze heatmap（有裝 matplotlib 就出圖，沒有就出文字圖）。

逐檔檢查 `sessions/<id>/`：

| 檔案 | 要檢查什麼 |
|---|---|
| `metadata.json` | `schema_version`、`input_mode`、`calibration_error_px` |
| `trials.csv` | 每個 trial 有 `t_target_shown_ns`、`t_click_ns`、`is_hit`；RT 落在合理範圍（0.5–5 s） |
| `gaze_stream.csv` | 取樣率接近 tracker 標稱值；`valid=1` 的比例 > 80% |
| `events.jsonl` | 事件順序合理，沒有缺漏 |

資料欄位定義見 [`DATA_SCHEMA.md`](DATA_SCHEMA.md)。

---

## 6. 已知缺口（這就是你們要做的事）

依重要性排序。每一項都標了確切位置。

### A. 校正結果沒有真的收回來 —— `src/engine/calibration.py`

`Calibration.run()` 送出 `CALIBRATE_CLEAR / SHOW / START` 之後
**立刻回傳**，`mean_error_px` 永遠是 `None`。程式碼註解也寫了
「Real error parsing is added when hardware is on-site (Phase 1)」——
就是現在。

要做：
1. 送 `<GET ID="CALIBRATE_RESULT_SUMMARY" />`（常數已經定義好了，只是沒被用）。
2. 解析回應，填入 `CalibrationResult.mean_error_px`。
3. 等校正真的做完再回傳（現在是 non-blocking，會和主視窗搶畫面）。
4. 結束時記得送 `<SET ID="CALIBRATE_SHOW" STATE="0" />`。

⚠️ 注意：`GazepointClient` 的背景 reader thread 會把 socket 上所有東西
讀走，而 `parse_rec()` 只認 `<REC`，其他一律丟掉 —— 所以校正的回應
**現在會被那條 thread 吃掉**。正確做法是在 `start_streaming()` **之前**
做校正，或在 client 內加一個「非 REC 訊息」的佇列。
目前 `src/app.py:94` 的校正是在 `start_streaming()`（`app.py:59`）**之後**
才呼叫的，這個順序要改。

### B. 命中測試的螢幕尺寸寫死 1920×1080 —— `src/engine/task_runner.py:53`

`build_task()` 一律用 `configs/default.yaml` 的 `app.screen_width_px`
（預設 1920×1080）把正規化座標換成像素做命中測試，但 canvas 畫圖用的是
**實際 widget 尺寸**。在非 1080p 螢幕上，畫出來的目標大小和實際 hitbox
會對不上，`jitter_tolerance_px` 也會被縮放。

要做：短期 —— 在 `configs/default.yaml` 把 `screen_width_px` /
`screen_height_px` 改成**實際使用的螢幕解析度**（最省事，先這樣）。
長期 —— GUI 模式改成從 `canvas.width()/height()` 取值傳進 `build_task()`。

### C. YAML 的 `gazepoint` 設定沒有被使用 —— `src/app.py:57`

```python
gp_cfg = self.config.get("gazepoint", {})
self.client = GazepointClient(replay_path=replay_path)   # ← enable 沒傳進去
self.client.connect(host=gp_cfg.get("host", ...), port=...)
```

`default.yaml` 的 `gazepoint.enable.*` 完全沒有生效（剛好預設值也是全開，
所以現在看不出問題）。改成 `GazepointClient(enable=gp_cfg.get("enable"), replay_path=...)`。

### D. 沒有斷線重連

`_run_socket()` 一旦 `recv` 收到空 chunk 或 `OSError` 就 `break`，
thread 直接結束，`latest()` 之後永遠回傳最後一筆舊資料 —— **畫面上看起來
像是視線卡住，而不是斷線**。實測時 Gazepoint Control 若被關掉就會發生。

要做：加重連迴圈，並在 `GazeSample` 過期時把 `valid` 設成 `False`
（例如超過 200 ms 沒有新樣本）。

### E. README 的測試數字過期

README 寫「26 tests」，實際是 29。順手改掉。

### F. 沒有實機的 latency 量測

計畫需要知道「注視 → 畫面回饋」的延遲。目前完全沒量。
建議：在 `_tick()` 記錄 `sample.t_ns` 與 `time.time_ns()` 的差，
寫進 `events.jsonl`，收案前先量一輪。

---

## 7. 驗收標準

做完可以說「GazePoint 整合完成」的條件：

- [ ] `pytest` 全綠，且新增了真機解析／重連的測試
- [ ] 四個任務都能用 `--replay` 跑完並輸出 session
- [ ] 有一份真機錄的 `.jsonl` fixture 進 repo（志願者，非個案）
- [ ] GUI 接真機能完成一整個 `click_static` session
- [ ] `metadata.json` 裡的 `calibration_error_px` 有真實數值（缺口 A 完成）
- [ ] 螢幕四角命中測試正確（缺口 B 完成）
- [ ] 拔掉 tracker 後程式能顯示「訊號中斷」而不是靜止不動（缺口 D 完成）
- [ ] 量到端到端 latency 並記錄（缺口 F 完成）

---

## 8. 排查表

| 症狀 | 可能原因 | 怎麼確認 |
|---|---|---|
| `ConnectionRefusedError` | Gazepoint Control 沒開 | 跑 §4 Step 1 |
| 連上但沒有 `<REC` | 沒送 `ENABLE_SEND_*` | Step 1 的 raw 輸出裡找 `<ACK` |
| `latest()` 一直 `None` | 忘記 `start_streaming()` | 加 print 確認 thread 有起來 |
| `valid` 一直 `False` | 未校正／受測者超出範圍 | 回 Gazepoint Control 重校 |
| 紅點卡住不動 | socket 斷了，thread 已死（缺口 D） | 檢查 `client._thread.is_alive()` |
| 紅點位置偏移 | 螢幕尺寸設定錯（缺口 B） | 對照 `default.yaml` 的 `screen_*_px` |
| GUI 起不來 | 沒裝 gui extra | `pip install -e ".[gui]"` |
| 裝不起來 | Python < 3.11 | `python -V` |

---

## 9. 有問題找誰

- 程式架構：`docs/ARCHITECTURE.md`
- 資料欄位：`docs/DATA_SCHEMA.md`
- OpenGaze 協定：`docs/gazepoint_api_cheatsheet.md`（權威來源仍是 GazePoint 原廠 PDF）
- 完整設計計畫：`303bfbea-eye_gaze_assessment_v1_plan.md`（在 repo 外，向 PI 索取）
