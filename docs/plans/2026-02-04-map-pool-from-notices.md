# 瓦罗兰特竞技模式图池 API 设计（基于变量更新）

日期：2026-02-04

## 背景与目标
- 目标：提供一个可在 GitHub Actions 上自动生成并发布的“图池 API”。当新赛季变动地图时，只需修改三个变量（回归/新增/轮出），即可更新完整图池和输出 JSON。
- 初始化基线来自 `地图轮换.xlsx`（仅首次使用），后续更新不再依赖 Excel。
- 输出中英文地图名。

## 关键约束
- 当前图池**不超过 7 张**，允许减少到 6 张（如地图 bug 临时下架）。
- 变量里使用**中文地图名**。
- 输出同时提供中文名与英文名。

## 总体架构
- 运行方式：GitHub Actions 定时任务（每日一次），同时支持手动触发。
- 发布方式：GitHub Pages 托管静态 JSON。
- 基准来源：首次从 Excel 取最后一条“当前图池”，写入 `config/current_pool.json`，后续以该文件为滚动基线。
- 地图名映射：`config/map-name-map.json`（中文 → 英文）。

## 数据流与组件
### 1) 输入
- `config/current_pool.json`：当前基准图池（中文名列表）。
- GitHub Actions 变量：
  - `RETURNING`：回归地图（中文名，支持中文顿号/逗号/换行分隔）
  - `ADDING`：新增地图
  - `ROTATED_OUT`：轮出地图
- `config/map-name-map.json`：中英文映射。

### 2) 处理规则
- 统一分隔符并去空格、去重。
- 计算逻辑：
  - `当前图池 = (基准图池 - 轮出) ∪ 回归 ∪ 新增`
- 地图状态：
  - `in_pool`：当前图池内，但非回归/新增
  - `returning`：本赛季回归
  - `add`：本赛季新增
  - `rotated_out`：被轮出（仅在 meta 中记录）

### 3) 输出
- `dist/maps.json`：地图列表及状态（中英文）
- `dist/meta.json`：元数据（版本、基准池、输入变量、变更摘要、生成时间）

示例结构（简化）：
```json
// dist/maps.json
{
  "maps": [
    {"name_zh": "盐海矿镇", "name_en": "Corrode", "status": "in_pool"},
    {"name_zh": "隐世修所", "name_en": "Haven", "status": "returning"}
  ]
}
```

```json
// dist/meta.json
{
  "source": "rolling",
  "generated_at": "2026-02-04T09:00:00Z",
  "inputs": {
    "returning": "隐世修所",
    "adding": "",
    "rotated_out": "霓虹町"
  },
  "previous_pool": ["盐海矿镇", "源工重镇", "微风岛屿", "隐世修所", "幽邃地窟", "深海明珠", "霓虹町"],
  "current_pool": ["盐海矿镇", "源工重镇", "微风岛屿", "隐世修所", "幽邃地窟", "深海明珠"],
  "rotated_out": ["霓虹町"],
  "warnings": []
}
```

## 初始化（仅首次）
- 从 `地图轮换.xlsx` 的 `Sheet1` 取最后一条有效记录的“当前图池”。
- 目前 v12.00 基线：
  - `盐海矿镇、源工重镇、微风岛屿、隐世修所、幽邃地窟、深海明珠、霓虹町`
- 初始化后写入 `config/current_pool.json`，后续不再读取 Excel。

## 校验与错误处理
- **映射缺失**：变量中的中文名不在 `map-name-map.json`，失败并列出缺失项。
- **冲突检测**：同一地图同时出现在回归/新增/轮出中则失败。
- **数量限制**：更新后图池数量必须 `1..7`，超过 7 直接失败。
- **空图池**：禁止生成空图池。
- 失败时不中断 Pages 部署，避免发布错误 JSON。

## 测试策略
- 轻量单元测试（或脚本自检）：
  - 分隔符解析
  - 冲突检测
  - 映射缺失
  - 图池数量上限
  - 轮出/回归/新增逻辑正确性

## 运维与发布
- Actions 定时每日运行；支持 `workflow_dispatch` 立即发布。
- 成功生成后自动覆盖 `config/current_pool.json` 为最新基线。
- Pages 站点路径：`/maps.json` 与 `/meta.json`。

## 地图中英文映射（当前维护）
- Ascent — 亚海悬城
- Abyss — 幽邃地窟
- Split — 霓虹町
- Fracture — 裂变峡谷
- Bind — 源工重镇
- Breeze — 微风岛屿
- Lotus — 莲华古城
- Sunset — 日落之城
- Pearl — 深海明珠
- Icebox — 森寒冬港
- Corrode — 盐海矿镇
- Haven — 隐世修所

## 需要你确认的默认值
- `RETURNING` / `ADDING` / `ROTATED_OUT` 变量默认空字符串。
- 初始 `config/current_pool.json` 写入 v12.00 基线。
