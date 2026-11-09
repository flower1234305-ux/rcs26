# 屋頂＋植物分支

> **rcs26 note (2026-11-10).** This document was written in the old `grid-roof-plants` repository, branch `roof-plants-contribution` (`e910bec`), and moved here with paths and commands rewritten for rcs26: run everything from the repository root, and files are under `projects/roof-plants/`. Sections about branches, merging and commit history describe that old repository, not rcs26. The roof modules in `roof_plants` are a copy of `projects/roof/grid_roof` at `f4c0b44`; see `README.md`.

每個花台依種的植物各自開口，其他步驟都沿用原版。植物的數字目前**全是假設值、沒有文獻來源**，
這個分支證明的是流程：植物條件改了，形體跟著變。

## 怎麼跑

```bash
uv sync --all-packages
uv run jupyter lab projects/roof-plants/plants_walkthrough.ipynb    # 約 1 分鐘，末尾輸出整屋粗略 STL
uv run python -m roof_plants.plant_build --out out                   # 53 塊全做，幾分鐘
uv run python -m pytest projects/roof-plants
uv run python scripts/run_notebooks.py roof-plants
```

要換植物：改 `planter_plants.json`，或改 notebook 第 7 格的 `PLANTER`、`PLANT`。

## 加了什麼

| 新檔 | 用途 | 依賴 |
|---|---|---|
| `roof_plants/plants.py` | 讀植物資料、換算開口、算花台底高度（純函式） | 只有標準函式庫 |
| `roof_plants/plant_voids.py` | 把開口變成 SDF，接到 `design_roof` | compas_vol |
| `roof_plants/plant_checks.py` | 花台的所有檢查 | numpy、compas_vol（經 `design.region`） |
| `roof_plants/plant_figures.py`、`plant_build.py` | 對照圖、53 塊 build | matplotlib、compas_vol |
| `plants.json`、`planter_plants.json` | 植物資料、哪個花台種什麼 | |
| `plants_walkthrough.ipynb` | 老師驗收用的 notebook | |
| `tests/test_design_hooks.py`、`test_plants.py`、`test_plant_voids.py`、`test_plant_checks.py`、`test_plant_outputs.py` | 測試 | |

新模組沒有加進 `roof_plants/__init__.py`，要用就 `from roof_plants.plants import ...`。

## 改了哪一個既有位置

**只有 `roof_plants/design.py` 的 `design_roof`**，多一個只能用名字傳的選填參數 `steps`。

```python
def design_roof(brief, drawing, *, steps=None):
    chosen = {"water": water, "voids": voids}
    unknown = set(steps or ()) - set(chosen)
    if unknown:
        raise ValueError(...)
    chosen.update(steps or {})
    b = beams(brief)
    incision = chosen["water"](brief, drawing, b)
    ...
    v = chosen["voids"](brief, drawing, s)
```

`steps` 不認識植物，其他分支也能用：

- `"water"`：換掉 Step 4，呼叫方式和 `water(brief, drawing, beams)` 相同。
- `"voids"`：換掉 Step 7，呼叫方式和 `voids(brief, drawing, slab)` 相同，回傳 `Voids`。
- 其他名字會報錯。目前只開放這兩步，好讓 `design_roof` 只改兩行；別的分支需要換其他步時，在 `chosen` 加一個名字、改一行。

**不傳 `steps` 時與原版相同，把關範圍如下：**

| 誰把關 | 比什麼 | 沒比什麼 |
|---|---|---|
| `tests/test_design_hooks.py`（每次跑） | 和測試裡寫死的原版步驟順序比：板面陣列、`design.roof`、`drawn`、`keep` 各 10 萬個隨機點差 0.0 mm，53 塊名稱相同 | 測試呼叫的是同一批步驟函式，所以只保護 `design_roof` 的本體。別人改步驟函式時兩邊一起變，測試看不出來；風化後的場和 STL 也沒比 |
| 對 `main` 的交叉比對（2026-11-07 手動跑，不在 CI） | 匯出 `main` 的程式，同樣的量各比 30 萬點，差 0.0 mm | 只代表當時的 `main` |

## 和其他分支的介面

| 問題 | 答案 |
|---|---|
| 讀什麼輸入 | `Brief` 的 `thickness`、`planter_wall`、`planter_depth`、`planter_rim`、`plan_cell`、`outlet`；`Drawing` 的 `planters`、`drains`；`Slab.deck.height_at(x, y)`；`Voids.openings` 的實際形狀。不加也不改 `Brief`、`drawing.json` 的欄位 |
| 花台和植物怎麼對應 | `planter_plants.json` 的 `index`，對應 `drawing.json` 裡 `planters` 的順序。數量不符會報錯；**數量相同但順序改變不會報錯**，植物會默默換到別的花台。到時要改成 id |
| `control` 是什麼 | 代表「這份 Brief 的原版花台」。`plants.json` 寫死的數字只等於預設 `Brief`，換了 `planter_depth` 或 `planter_rim`，或把它的 `depth_datum` 改掉，都會在 `plant_steps` 立刻報錯，並說哪裡不同 |
| `Voids` 怎麼產生 | 先呼叫 `voids()`（或你給的 `base_voids`）拿到開口和出水口，再用 `dataclasses.replace` 只換掉 `pockets`。所以採光分支改 `voids()` 的開口段會直接生效，`Voids` 多了欄位也會保留。**`base_voids` 做的花台形狀會被丟掉**，見下方限制 |
| Step 4 怎麼影響排水 | 花台在 Step 4 是吸水區。這裡把每個花台的輪廓換成「花台底輪廓」（手繪線外擴 `offset`），水路因此改變。對照組的 pocket 與原版相同；**板面只有全部 `offset` 為 0 時才與原版相同** |
| 花台深度怎麼量 | `depth_datum`：`nominal` 從板頂量（對照組）；`local_min` 從頂面輪廓（`offset + rim`）內最低的實際板面量。**所以 Step 4／5 的板面一變，花台底就跟著變**。洩水坡或水道改深之後，原本放得下的花台可能放不下，會在 Step 4 之後立刻報錯，並說 `depth` 最多多少 |

### 換植物會影響別的花台嗎

**機制上會。** 花台的輪廓是 Step 4 的吸水區，換植物可能改變水路；`local_min` 的花台底跟著板面走，所以別的花台可能因此放不下。

**下面的實測只適用於這個範圍：預設 `Brief`、目前的 `drawing.json`、只有現有三種植物（`offset` 0、±300）。不能外推到其他配置。**

| 量什麼（2026-11-07 手動掃描，不在測試裡） | 結果 |
|---|---|
| 4 個花台 × 3 種植物的全部 81 種配置，每種走到實際的放不下檢查 | 36 種放得下（不代表其他檢查都通過），45 種報錯 |
| 報錯的是誰 | 只有 P0 種 `group3_upright`（27 種配置，壁底差 54 mm）和 P2 種 `group3_upright`（27 種配置，差 27 mm），其中 9 種兩個都報 |
| 報錯的花台換過植物嗎 | 全部換過：預設配置裡 P0、P2 都不是 `group3_upright`。沒換植物的花台報錯 0 次 |
| 同一花台、同一植物，其他花台怎麼換 | 12 組的花台底高度變化都是 0.00 mm。P1 種 `group3_upright` 時餘量都是 6.31 mm |
| 沒換植物的花台，頂面輪廓內的板面（與預設配置比） | 81 種都差 0.00 mm |
| 只限預設配置：與原版的板面差 | 全屋 87,001 格有 312 格改變，最大 67.4 mm。其中 33 格在 P2 頂面輪廓內，P0、P1、P3 輪廓內 0 格，其餘 279 格在所有花台的頂面輪廓之外 |

在這個範圍內，放不下只來自花台自己種的植物。**範圍之外沒有測過。** 這些改動都要重跑才知道，尤其 P1 只有 6.3 mm 的餘量，最低板面再低一點就會報錯：

- `Brief` 的 `fall`、`relief`、`relief_seed`、`channel_*`
- 排水點或花台的位置
- 採光口的位置（Step 4 的水會避開採光口）
- `offset` 不是 0、±300 的新植物

### 壁厚 150 是怎麼量的

`planter_wall` = 150 是 `Shell` 的**場值**：花台的場是平面距離減去喇叭口的外擴量，所以這 150 是**水平**量的，不是垂直於壁面的厚度。喇叭口越斜，實際壁厚越薄。

檢查表的 `wall_normal_min` 用公式列出最薄處，**只回報，不影響 `ok`**：`planter_wall / sqrt(1 + (1.5 × rim / (thickness − floor))²)`。1.5 是 smoothstep 的最大斜率。有測試拿這個公式和場的等值線距離比對，誤差 3% 以內。

| 花台 | rim | 垂直壁面的最薄厚度 |
|---|---|---|
| P0、P3 control | 220 | 約 109 mm |
| P1 group3_upright | 80 | 約 145 mm |
| P2 group1_creeping | 400 | **約 73 mm** |

要不要改 P2 的 `rim` 或 `planter_wall` 還沒決定。

### 疊加別的分支的 Step 7 的限制

`voids_by_plant` 會把 `base_voids` 回傳的 `pockets` **逐一換掉**，對方做的花台形狀會消失；開口、出水口和 `Voids` 的其他欄位會保留。對方回傳的 pockets 數量不等於花台數時會報錯，以免多出來的花台被默默丟掉。如果兩個分支都要改花台形狀，要當面合併這段，不能只靠疊加。

## 預期的合併衝突

| 情況 | 會發生什麼 | 怎麼解 |
|---|---|---|
| 別的分支也改 `design_roof` 的 `chosen` 或那兩行呼叫 | 文字衝突，一眼看得懂 | 兩邊的步驟名稱都留下 |
| 別的分支也傳 `steps` | 沒有文字衝突，但同一個名字只能有一個 | 把他們的步驟當 base，照抄下面的組合做法 |
| 別的分支改 `carve` 或 `keep` | 不衝突 | 重跑 `tests/test_plant_checks.py` |
| 排水分支改洩水坡、水道深度 | 不衝突，但花台底會變 | 重跑 notebook；放不下就依錯誤訊息下修 `depth`（是假設值，要在 `source` 寫理由） |
| 別的分支增刪 `drawing.json` 的花台 | 數量不符時 `assign` 報錯；**數量相同但順序改變不會報錯** | 更新 `planter_plants.json`，並檢查每個花台種的是不是原本的植物 |
| 別的分支移動開口或排水點 | 不衝突，檢查可能變不過 | 看 notebook 第 5 格 |

### 和別的分支的步驟組合

```python
from roof_plants.plant_voids import plant_steps

# 他們的步驟，呼叫方式和 water、voids 相同
steps = plant_steps(brief, specs, base_water=their_water, base_voids=their_voids)
built = roof.design_roof(brief, drawing, steps=steps)
```

植物的 water step 會把 `drawing` 的花台換成花台底輪廓，再交給 `their_water`，所以他們看到的是換過的 `drawing`。只有其中一步要疊，另一個參數不寫即可。

### 如果 repo 改成 `origin/studio-layout` 的結構

上游有一條分支把屋頂搬到 `projects/roof/`。試合併（`git merge-tree`）的結果：`design.py` 的掛點會自動跟過去，沒有文字衝突；
`roof_plants/plant*.py`、`plants.py` 會報 file location 衝突，要接受 git 建議的新位置；
`plants.json`、`planter_plants.json`、`plants_walkthrough.ipynb`、`docs/roof-plants.md` 和 `tests/` 裡的新測試留在原地，要手動搬進 `projects/roof/`。這條路徑只試過合併，沒有實際跑過。

共用檔案的順序還沒決定。組內可以討論一種做法：梁 → 排水 → 採光／動線 → 植物，先放的成為後放的禁區。

## 暫定值

| 值 | 目前 | 狀態 |
|---|---|---|
| `plants.json` 的 `offset`、`rim`、`depth` | 見檔案 | 假設值，沒有文獻來源；之後由根系類型、生長方向、根深換算，改 `opening_spec` 即可 |
| `plant_checks.DRAIN_GAP` | 500 mm | 暫定，grid-roof 沒有這條規則；排水分支有數字時請改掉。另有硬下限 `planter_wall + outlet`（230 mm），參數改不掉：`keep` 的花台壁沒有 carve、最後才 union，再靠近時**壁會把出水孔填回去，排水被堵**。230 是直壁的最壞情況，喇叭口會讓壁在板面附近內縮，開始堵的距離更近。手動實測（depth 350、一個花台）：`rim` 0 時，距離 220 堵 2%、100 堵 91%、40 全堵；`rim` 220 時，距離 100 不堵、40 堵 12% |
| `group3_upright` 的 `depth` | 360 mm（原 400） | 改用 `local_min` 後放不下而下修，理由寫在 `source`。**v2 起（2026-11-09）改回 400，放不下，見 v2 第 5 項** |

## 還沒做

Grasshopper 元件、分區運算、自動生成花台位置、根系換算。

## 第二版（v2）

分支 `roof-plants-v2`，從 tag `roof-plants-v1` 開出。2026-11-08：花台排水、載重盤點、連通花台示範、植物資料表格。2026-11-09（Wei 核准四件事）：排水孔接落水管、連通花台改 800 mm 頸、`group3_upright` 土深 400、載重改成情境比較。

> **先看這裡**：2026-11-09 起 `group3_upright` 的 `depth` 是 400 mm，**在目前的圖上哪個花台都放不下**（第 5 項）。`planter_plants.json` 仍寫設計意圖（P1 種 `group3_upright`），所以直接跑會在 P1 停下；notebook、53 塊 build、測試改用 `planter_plants_fallback.json`（P1 **暫代** `control`）。暫代不是設計，要怎麼讓它放得下由 Wei 決定。

### 新增什麼

| 新檔 | 用途 | 依賴 |
|---|---|---|
| `roof_plants/plant_drains.py` | 每個花台底的排水孔，和它的檢查 | numpy、scipy（compas_vol 的 processes 已帶進來）、compas_vol |
| `roof_plants/plant_pipes.py` | 排水孔到最近落水點的板下排水管（只是資料與預覽，不挖進 SDF） | numpy、matplotlib（只在畫圖時） |
| `roof_plants/plant_loads.py` | 載重盤點與情境比較：每個花台、每塊、全屋 | numpy |
| `roof_plants/plant_table.py` | `plants.csv` ↔ `plants.json` | 只有標準函式庫 |
| `plants.csv` | 植物資料的正本，人編輯這份（UTF-8 with BOM，Excel 直接開） | |
| `planter_plants_fallback.json` | 暫代配置：P1 改種 `control`，檔內 `note` 寫明是暫代與原因 | |
| `drawing_connected.json`、`planter_plants_connected.json`、`scripts/make_connected_drawing.py` | 連通花台示範（頸寬 800 mm） | |
| `tests/test_plant_drains.py`、`test_plant_pipes.py`、`test_plant_loads.py`、`test_plant_table.py`、`test_plant_connected.py`、`test_plant_fit.py` | 測試 | |
| `tests/conftest.py` | 共用 fixture `v1_plants`（`group3_upright` 用 v1 的 360，見 `at_v1_depth`） | |

### 動到的既有檔案

| 檔案 | 改了什麼 | 理由 |
|---|---|---|
| `roof_plants/plant_build.py` | `main()` 改用有排水孔的步驟與檢查；多一個 `--planters`（預設 `planter_plants.json`）；`results.json` 多 `drains`、`planting`、`stand_in`、`planting_note`（配置檔 `note` 原文）；`note` 含 STAND-IN 時終端機印警告；放不下（`PlanterFitError`）時印出可改用 `--planters projects/roof-plants/planter_plants_fallback.json`（暫代），exit 1 | 不改的話 build 出來是盲孔；`--planters` 讓暫代配置能 build，且暫代標示要一路帶到輸出。`build_pieces`、`passed` 的簽名沒變 |
| `plants.json` | 由 `plants.csv` 轉出：`group3_upright` 的 `depth` 400、`source`；三種植物的 `mature_weight_kg_m2`、`source_pages` | Wei 2026-11-09 核准 |
| `tests/test_plant_checks.py` | 只改 fixture：改用 `conftest.py` 的 `v1_plants`（`group3_upright` 用 v1 的 `depth` 360） | 這些測試檢查的是機制，用放得下的 v1 配置；400 放不下由 `test_plant_fit.py` 鎖住 |
| `plants_walkthrough.ipynb` | 第 4 格先試設計意圖、放不下改用暫代；第 5 格加排水孔表；新增第 5b 格（排水管）；第 7 格預設改 P2 → `control`；第 8 格改成情境比較；第 9 格改 800 mm 頸 | 示範第二版 |
| `docs/roof-plants.md` | 這一節 | |

`design.py`、`plant_voids.py`、`plant_checks.py`、`plants.py`、`drawing.json`、`planter_plants.json` 都沒改。**不傳 `steps` 時 `design_roof` 與原版相同**，`tests/test_design_hooks.py` 照樣通過。

### 1. 花台排水孔

**問題**：原版的花台是盲孔（`Voids.pockets`），Step 4 卻把花台當吸水區，水導進去出不來。

**做法**：每個花台從底部垂直開一個孔，穿出板底。孔是**花台凹槽的一部分**（`pocket ∪ 圓柱`），不是 `Voids.outlets` 裡的另一個孔。

| 既有規則 | 如果把孔放進 `Voids.outlets` | 現在的做法 |
|---|---|---|
| `keep` 最後才 union 花台壁 `Shell(pocket, 150)` | 壁會把孔填回去（同 `DRAIN_GAP` 那段說的堵塞機制） | 孔在 pocket 裡面，`Shell` 反而沿著孔外圍包一圈 150 mm 的套管一路到板底：孔不會被填回，水也不會從側面滲進泡沫層 |
| 梁保留 500 mm（`beams.core` 也在 `keep` 裡） | 孔若落在梁上會被梁填回，或要切梁 | 孔一律放在梁帶外 |
| 板面、水道（Step 4／5） | — | 孔不改板面：有孔與無孔的 `incision.surface` 完全相同（測試） |

**孔放哪裡**：花台底是平面，但邊緣有約 120 mm 的圓角過渡，所以花台底輪廓（手繪線外擴 `offset`）內**最深處**是凹槽最先到達底面的地方。孔放在這個最深點（同樣深就取最靠近中心的），且孔邊到梁帶的距離要大於 0（`gap_to_beams` > 0；選位置和檢查用同一條規則，正好貼齊梁邊的點不選）。花台底如果分成好幾塊，每一塊各開一個。

**孔多大**：半徑預設等於 `brief.outlet` 80 mm（直徑 160 mm），**假設值（PROVISIONAL，2026-11-08），沒有來源**；`plant_steps_drained(..., radius=...)` 可改。孔從花台底上 50 mm 一路開到板底下 200 mm（`BELOW`）。

```python
from roof_plants.plant_drains import plant_steps_drained, drained_planter_rows, drain_rows, all_ok_drained, drain_table

built = roof.design_roof(brief, drawing, steps=plant_steps_drained(brief, specs))
rows = drained_planter_rows(brief, drawing, specs, built)     # 原本的花台檢查表
drains = drain_rows(brief, drawing, specs, built)             # 排水孔檢查表
ok = all_ok_drained(rows, water_check(built.incision), drains)
```

**檢查** `drain_rows` → `bore_check`：沿孔軸和半徑一半的 8 個點，從花台底上 20 mm 到板底上 5 mm 每 10 mm 取樣，`design.roof`、`design.drawn`、`keep` 三者都 > 0（空）才算通；另檢查 `beam_gap` > 0。`flat` 只回報：孔周圍是否還有 `半徑 + 120 mm` 的平底。

**為什麼要 `drained_planter_rows`**：原本的 `floor_check` 量「花台底下有沒有完整的壁」，孔那一柱本來就沒有壁，直接用 `planter_rows` 會讓 `kept` 變成 0（有測試證明）。所以只在這個檢查裡把孔補回 `keep`；孔本身由 `drain_rows` 用真正的 `keep` 檢查。

**實測**（暫代配置）：4 個花台各 1 孔，`open` 100%，`flat` 全為 True，孔邊到梁 940～1989 mm。刻意違規：拿 v1 的盲孔跑同一個檢查，4 個全部不通過（`open` < 20%）。

### 2. 板下排水管（2026-11-09）

垂直孔不變。每個孔從板底接一條管，吊在板下走到**平面上最近的落水點**，在那裡接上落水點自己的豎管（豎管沒有建模）。

| 項目 | 內容 |
|---|---|
| 起點 | 孔在板底的出口 `(x, y, 0)` |
| 走法 | 先往下一個管半徑（管頂貼齊板底），再沿梁格兩個方向走：先 X 後 Y；穿過東西就改先 Y 後 X；兩種都不行才走直線。全程以 `slope` 下降 |
| 終點 | 落水點正下方，高度 = −(管半徑 + 坡度 × 長度) |
| 坡度 | `SLOPE` = 1 %，**PROVISIONAL（2026-11-09），沒有來源**；`planter_pipes(..., slope=)` 可改 |
| 管徑 | 預設等於孔的半徑 80 mm，**假設值** |
| 檢查（平面投影） | 不能穿過別的花台的排水孔、別的落水點的出水口、採光開口（`Voids.openings` 最寬處），各外擴管半徑。從梁或花台下方經過不算穿過 |
| 落差 | `drop` = 坡度 × 長度，`below_soffit` = 落差 + 管徑：**板下可用空間沒有定義，只回報、不判定** |

落水點是用**平面直線距離**挑最近的；最近那條路被擋住時，不會改試第二近的落水點（只回報穿過什麼）。

管與管之間**不做碰撞判定**，`pipe_overlaps` 只回報兩管在平面上比兩管半徑和更近的長度、最近距離、高差。暫代配置下 P1、P3 都接到 D4：重疊 1500 mm、最近平面距離 0、高差約 11 mm。

管線**不挖進屋頂 SDF**（有測試確認 `design.roof` 不變）；`pipe_rows`／`pipe_table` 是資料，`pipe_mesh` 是可選的預覽管（三角網格），`plot_plan`／`plot_profiles` 讓 notebook 畫平面和縱斷面（第 5b 格）。

```python
from roof_plants.plant_pipes import planter_pipes, pipe_table
pipes = planter_pipes(brief, drawing, specs, built)   # slope=0.01
print(pipe_table(pipes))
```

**實測**（暫代配置，2026-11-09）：

| 花台 | 接到落水點 | 走法 | 長度 mm | 落差 mm | 管底在板底下 mm | 穿過 |
|---|---|---|---|---|---|---|
| P0 | D0 | 先 X 後 Y | 2262 | 23 | 183 | 無 |
| P1 | D4 | 先 X 後 Y | 2567 | 26 | 186 | 無 |
| P2 | D2 | 先 X 後 Y | 3199 | 32 | 192 | 無 |
| P3 | D4 | 先 X 後 Y | 3682 | 37 | 197 | 無 |

**FLL 要求植栽區內的落水頭要設檢查井，本工具沒有建模。**

### 3. 載重盤點與情境比較（不判定結構安全）

**只盤點、只比較，不選、不判定。** 程式和輸出裡沒有任何「安全／不安全」。

| 項目 | 怎麼算 |
|---|---|
| 花台土壤體積 | 凹槽內「花台底以上、板面以下」的格子數 × 格子體積（`soil_step`，預設 25 mm）；排水孔與 `carve` 的 80 mm 圓角不算 |
| 花台載重 | 乾：土 × `soil_dry` + 植物；飽和：土 × `soil_saturated` + 植物 + 積水。植物與積水按花台平面面積（有土的格子） |
| 每塊（53 塊） | `design.roof` 在該塊範圍內的實體（`slab_step`，預設 50 mm）× `slab`，加上落在該塊上的花台載重；kN/m² 用該塊的平面面積 |
| 全屋 | 53 塊加總；kN/m² 用 18 × 12 = 216 m² |

`design.roof` 是風化與接頭之前的設計；風化只會拿掉材料，所以偏多。

**情境**（`SCENARIOS`，2026-11-09 Wei 核准；三者只差飽和土壤和積水，所以比的是飽和載重）：

| 情境 | 飽和土壤 | 積水 | 出處 |
|---|---|---|---|
| `light_medium` 輕介質 | 1,400 kg/m³ | 0 | ZinCo Info Sheet 2026-01 p.1（飽和 1,300–1,500） |
| `mineral_soil` 礦物土 | 1,800 kg/m³ | 0 | FLL 2018 表 24 p.115（密集型土壤／礦物混合 1,600–1,900） |
| `drain_blocked` 排水孔堵塞 | 1,800 kg/m³ | 50 mm | 積水 50 mm：**Wei 未定，PROVISIONAL** |

「飽和」照 FLL 的最大含水量：先飽和、再自由排水（FLL 為滴水 2 小時）後保留的水分；孔隙全滿的水不算，積水另用 `ponding_mm`。

**植物載重**依 id（FLL 2018 表 26 p.117，寫在 `plants.csv` 的 `mature_weight_kg_m2`，由 `plant_weights(plants)` 接到計算）：`group1_creeping` 10 kg/m²、`group3_upright` 20 kg/m²、`control` 0（對照組不對應植物）。

**板密度**：屋頂的材料**沒有任何地方指定**。預設 `slab` 2400 kg/m³，PROVISIONAL：材料未指定；2400 ≈ EN 1991-1-1 表 A.1 一般混凝土 24 kN/m³（×100 簡化）。`SLAB_DENSITIES` 並列比較，只列數字、不選材料：

| kg/m³ | 對應材料 | 出處 |
|---|---|---|
| 2000 | 輕質混凝土 LC2.0 上限 | EN 1991-1-1 表 A.1 p.32 |
| 2100 | 陶土燒成 | EN 1991-1-1 表 A.2 p.33 |
| 2350 | 3D 列印混凝土 | Le et al. 2012, Cement and Concrete Research 42(3):558–566，只讀摘要 |
| 2400 | 現值 | — |
| 2500 | 含配筋混凝土 | EN 1991-1-1 表 A.1 註 1 |

附錄 A 的值是乾燥狀態，板吸水後的濕重沒有計入。×100 是簡化：24 kN/m³ ÷ g = 2447 kg/m³，用 2400 使板重**偏低約 1.9%**（同理，表中每個密度若原本是由 kN/m³ ×100 換來，也一樣偏低約 1.9%）。`soil_dry` 1200 仍是 2026-11-08 的量級參考，沒有查證。

```python
from roof_plants.plant_loads import compare, plant_weights, scenario_table, slab_table
compared = compare(brief, drawing, specs, built, plant_weights=plant_weights(plants))
print(scenario_table(compared)); print(slab_table(compared))
```

`compare()` 的結果記錄實際用到的 `plant_weights`；沒有傳時，`plant_weights_note` 寫明「植物載重未計」（三個預設情境的 `plant_kg_m2` 都是 0）。

**情境比較表**（暫代配置、板 2400；`compare()` 約 2.7 秒）：飽和 kN

| | 輕介質 | 礦物土 | 排水孔堵塞 |
|---|---|---|---|
| P0 control | 6.39 | 8.22 | 9.32 |
| P1 control（暫代） | 8.15 | 10.48 | 11.84 |
| P2 group1_creeping | 13.14 | 16.76 | 19.18 |
| P3 control | 3.79 | 4.87 | 5.53 |
| 花台合計 | 31.47 | 40.33 | 45.86 |
| 全屋（板 + 花台）kN | 2159.73 | 2168.59 | 2174.12 |
| 全屋 kN/m² | 10.00 | 10.04 | 10.07 |

**板密度敏感度**（實體 90.43 m³，50 mm 取樣）：全屋飽和 kN/m²

| kg/m³ | 板 kN | 板 kN/m² | 輕介質 | 礦物土 | 排水孔堵塞 |
|---|---|---|---|---|---|
| 2000 | 1773.55 | 8.21 | 8.36 | 8.40 | 8.42 |
| 2100 | 1862.23 | 8.62 | 8.77 | 8.81 | 8.83 |
| 2350 | 2083.92 | 9.65 | 9.79 | 9.83 | 9.86 |
| 2400 | 2128.26 | 9.85 | 10.00 | 10.04 | 10.07 |
| 2500 | 2216.94 | 10.26 | 10.41 | 10.45 | 10.48 |

解析度：`slab_step` 從 50 改 100 mm，實體少 1.8%；`soil_step` 從 25 改 12.5 mm，各花台乾 kN 差 2% 以內（2026-11-08 測）。`loads()` 單次在已建好的屋頂上約 2.5 秒（2026-11-08 連跑三次 2.50～2.57 秒，20 執行緒 Intel 桌機）。

### 4. 連通花台示範（程式邏輯不改）

`drawing_connected.json`：把 `drawing.json` 的 P1、P3（最近的一對，相距 2.7 m，中間沒有梁）用 **800 mm** 寬的頸部連成啞鈴形，其他不變。花台變成 3 個：P0、啞鈴、P2。`planter_plants_connected.json` 讓啞鈴沿用 P1 的 `group3_upright`。由 `uv run python projects/roof-plants/scripts/make_connected_drawing.py` 產生（腳本預設頸寬已改成 800；其他頸寬預設寫到新檔 `drawing_connected_neck<寬>.json`，不覆寫）。

**結果（2026-11-09，全部有測試鎖住）**

| 情況 | 結果 |
|---|---|
| 800 mm 頸、`group3_upright`、v1 `depth` 360 | **全部檢查通過** |
| 800 mm 頸、`group3_upright`、`depth` 400（現值） | **放不下**：`PlanterFitError`，`depth` 最多 366 mm。啞鈴包含 P1 原本最低的板面，和 P1 單獨時一樣 |
| 800 mm 頸、`control` | 全部檢查通過 |
| 500 mm 頸（回歸測試，在測試內用腳本函式產生，不放檔案） | Step 4 停下：內縮 300 mm 把頸部切成兩圈，`offset_outline` 只接受一圈 |

notebook 第 9 格是這個示範（`RUN_CONNECTED = True` 才跑）。

### 5. `group3_upright` 土深 400 mm（2026-11-09）

`plants.csv` 的 `depth` 改成 400，`source`：依《建築基地綠化設計技術規範》表 1 灌木類屋頂最小覆土 0.4 m，2026-11-09 Wei 核准（`offset`、`rim` 仍是假設值）。

**結果：放不下。** 不只 P1：在目前的圖上，四個花台都放不下 400（其他花台照暫代配置）：

| 花台 | 頂面輪廓內最低板面 mm | `depth` 最多 mm |
|---|---|---|
| P0 | 456.0 | 306 |
| P1 | 516.3 | **366** |
| P2 | 482.7 | 332 |
| P3 | 541.1 | 391 |

`planter_wall`、`depth_datum`、花台位置都**沒有自行調整**（屬於結構或設計決定）。

**處理方式**：`plants.csv` 保留 400；`planter_plants.json` 保留設計意圖（P1 `group3_upright`），直接跑會在 P1 停並印出上面的數字；`planter_plants_fallback.json` 讓 P1 暫代 `control`，notebook（第 4 格先試意圖、失敗才改用並印出「STAND-IN」；第 5、5b、6、8 格都印出 `PLANTING`；預覽 STL、剖面圖、排水管、載重的輸出檔名加 `_standin`）、53 塊 build（`--planters projects/roof-plants/planter_plants_fallback.json`；`results.json` 有 `stand_in: true` 與 note 原文）、排水管、載重都用它。機制測試保留 v1 的 360（`tests/conftest.py` 的 `v1_plants`）。

想試別的配置時，寫到**另一個檔**再用 `--planters` 指定；**不要覆寫 `planter_plants.json`**，它記的是設計意圖（P1 種 `group3_upright`）。

**要讓 P1 種 400 放得下的選項**（A～E 實際跑過（手動，不在測試裡）；F 沒有試。2026-11-09；都沒有採用，交給 Wei）：

| 選項 | 實際數字 | 結果與代價 |
|---|---|---|
| A. `planter_wall` 150 → **116 mm 以下** | `planter_wall` 116 實跑：P1 花台底 116.3 mm，`wall_margin` 0.3；四個花台垂直壁面最薄處 `wall_normal`：P0 84.4、P1 112.6、**P2 56.3**、P3 84.4 mm（壁厚 150 時為 109.1、145（v1 360）、72.8、109.1） | 所有檢查通過；但 `planter_wall` 是全部花台共用，每個花台的壁與底都變薄，P2 喇叭口最斜，只剩 56 mm。`DRAIN_GAP` 的硬下限 `planter_wall + outlet` 也從 230 降到 196 mm（壁越薄，堵住出水孔的距離越近） |
| B. P1 改用 `depth_datum` `nominal` | 花台底 200 mm | 所有檢查通過；但土深從板頂量，實際最淺處 `soil_min` **318 mm**（最深 332），**不滿足 0.4 m 的本意** |
| C. 移動 P1（同形狀平移） | 篩選方法：其他花台照原設計不動，用 P1 在原位時的板面，以 250 mm 間距試所有平移，留下頂面輪廓不碰梁、離採光口與其他花台至少一個壁厚、離落水點至少 500 mm、且最低板面 ≥ 550 mm 的位置，共 27 個；其中驗證 4 個（移動距離最短的 1 個＋估計餘量最大的 3 個），每個都重跑完整流程（P1 移動後板面會變）。結果：(−1300, −1550) mm（中心約 7.0, 7.75 m）餘量 1.7；(−1300, −2050) 餘量 14.6；(−1050, −2300) 餘量 14.4；(−1300, −2300)（中心約 7.0, 7.0 m）餘量 **19.2**、`soil_min` 402 | 四個都全部檢查通過；但位置是設計決定，且餘量都很小（< 20 mm），板面或水路稍變就會再放不下。「梁距 94 mm」是 dx −1300 的三個位置頂面開口到 x = 6000 那根梁的距離；(−1050, −2300) 是 204 mm |
| D. 板厚 `thickness` 600 → **約 634 mm 以上**（內插值：板面隨板厚等量上升，516.3 + Δ ≥ 550 → Δ ≥ 33.7；634 本身沒有實跑） | 640 實測：花台底 156.3、`soil_min` 401.7；630 實測放不下（最多 396） | 所有檢查通過；屬結構決定，整片板加厚 |
| E. P1 改種別的植物 | `control`：通過（即暫代）；`group1_creeping`：跑得完但檢查不過（`drain_gap` 332 < 暫定 500） | 換掉 `group3_upright` 就不是原設計 |
| F. 改 `fall`、`relief` 讓 P1 一帶板面變高 | 沒有試 | 會改全屋的水路，影響其他花台，要重掃 |

**notebook 第 7 格的換植物示範**（暫代為底）：P3 → `group3_upright` 在 v1（360）放得下，現在放不下（最多 391）。預設示範改為 P2 → `control`（全部通過，開口 4.96 → 1.99 m²）。

### 6. 植物資料表格

`plants.csv` 是正本，`plants.json` 由它產生；程式只讀 `plants.json`。

```bash
cd projects/roof-plants
uv run python -m roof_plants.plant_table csv2json plants.csv plants.json   # 改完 csv 後
uv run python -m roof_plants.plant_table json2csv plants.json plants.csv   # 反向
```

| 欄位 | 誰用 |
|---|---|
| `id,name_zh,root_type,growth,offset,rim,depth,depth_datum,source` | 程式（同 `plants.REQUIRED`），必填 |
| `name_sci,name_common,soil_depth_min_mm,soil_depth_rec_mm,root_spread_mm,mature_weight_kg_m2,water_need,drought_tolerance,sun_need,source_pages` | 研究用，可留空；空格不寫進 JSON，不會報錯 |

數字欄整數讀成 int、有小數讀成 float，JSON → CSV → JSON 逐位元組相同（測試）；另有測試確認 `plants.csv` 與 `plants.json` 同步。目前有值的新欄位只有 `mature_weight_kg_m2` 與 `source_pages`（2026-11-09，FLL 2018 表 26 p.117）；其他仍空，等研究員給有文獻來源的數值。`soil_depth_min_mm` 沒有填 400（Wei 只核准了 `depth`）。

### 測試與時間

全部測試 `uv run python -m pytest`：v1 160 個，v2 216 個（2026-11-09 第二輪審查修正後實跑：216 passed，5 分 20 秒），`ruff check .` 無錯誤。

### 已驗證／未驗證

**已驗證**（有測試或實測）

- 不傳 `steps` 時 `design_roof` 與原版相同（`test_design_hooks.py`）
- 排水孔在 `design.roof`、`design.drawn`、`keep` 中都通到板底；盲孔版同一檢查不通過；孔外有 150 mm 套管；孔不在梁帶內，兩個方向的梁 500 mm 範圍仍全是保留實體；加孔不改板面；選孔與檢查的梁距規則一致（邊界測試）
- 排水管：每孔接到平面最近的落水點；全程以坡度下降；落差 = 坡度 × 長度；繞開擋路的孔、出水口、採光口（合成案例）；不改 `design.roof`
- `group3_upright` 400 的放不下數字（306／366／332／391）、意圖配置在 P1 停下、暫代配置全部通過（`test_plant_fit.py`）；第 5 項的選項 A～E 是手動實跑（不在測試裡）
- 載重：方塊、球、方形花台對手算；各塊加總一致；三種情境的土、積水、植物各項對手算；板密度表與情境表一致；輸出不含任何安全判定
- 連通花台四種結果（`test_plant_connected.py`）
- 53 塊完整 build（暫代配置、有排水孔、40 mm voxel）：53 塊全部封閉（watertight），梁最小深度 500.0 mm，所有檢查與排水孔通過，248 秒；`results.json` 的 `stand_in` 為 true、`planting_note` 為暫代說明原文（2026-11-09 審查修正後重跑）
- notebook 從頭到尾執行無錯誤（含 `RUN_CONNECTED = True`），97 秒（2026-11-09 審查修正後重跑）；暫代時輸出檔名帶 `_standin`；提交版不含 outputs

**未驗證／不在範圍**

- 排水孔半徑 80 mm、排水管坡度 1 %、管徑都沒有依據；板下可用空間沒有定義；落水點的豎管、檢查井（FLL 要求）、濾層、排水層、防根層都沒有建模；沒有水量或堵塞計算
- 排水管的碰撞只看平面投影，沒有檢查管與結構、設備的立體關係；管的吊掛沒有建模
- **管與管之間沒有做碰撞判定**：`pipe_overlaps` 只回報數字。暫代配置下 P1、P3 都接到 D4，兩條管在平面上重疊 1500 mm（沿 x = 9600 往 D4 那段），最近處平面距離 0、高差約 11 mm，實際上會相撞或要合流，沒有處理
- 落水點是用平面直線距離挑最近的；最近那條路被擋住時，不會改試第二近的落水點
- 積水 50 mm、`soil_dry` 1200、板 2400 都是假設值；**結構安全完全不在本工具範圍**；板吸水後的濕重、風化與接頭後的實際重量沒有算
- 第 5 項選項 C 只驗證了 4 個位置；選項 F 沒有試；81 種配置的掃描沒有用 400 重做
- `plants.csv` 用 Excel 存檔後的格式沒有實測
- Grasshopper 元件沒有更新
- 有兩個 commit 先於植物資料 commit（`8251ff1`）：`0e3b015`（載重情境）單獨 checkout 時 `test_plant_weights_come_from_the_plant_table` 會失敗，`c536ed2`（800 mm 頸）單獨 checkout 時 `test_at_depth_400_it_does_not_fit_as_p1_does_not` 會失敗；分支最新狀態沒有問題。沒有改寫歷史（不 rebase），操作時請注意：`git bisect` 遇到這兩個 commit 用 `git bisect skip`；`cherry-pick` 這兩個 commit 時要和 `8251ff1` 一起挑
