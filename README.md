# Valorant Map Pool API

通过 GitHub Actions 变量更新瓦罗兰特竞技模式图池，生成静态 JSON 并发布到 GitHub Pages。

## 输出
- `dist/maps.json`（包含当前图池地图，且追加 `rotated_out`）
- `dist/meta.json`
- `dist/<version>/maps.json`（版本快照）
- `dist/<version>/meta.json`（版本快照）

## 变量（Actions / 本地环境变量）
- `VERSION`：版本号，例如 `v8.07a`
- `VERSION_DATE`：版本日期，例如 `2024-03-18` 或 `2024/3/18`
- `RETURNING`：回归地图（中文名，支持中文顿号/逗号/空格分隔，不支持换行）
- `ADDING`：新增地图（中文名，支持中文顿号/逗号/空格分隔，不支持换行）
- `ROTATED_OUT`：轮出地图（中文名，支持中文顿号/逗号/空格分隔，不支持换行）

## 本地运行
运行（有 warning 或缺少版本信息会报错并终止）：
```bash
VERSION="v8.07a" VERSION_DATE="2024/3/18" \
RETURNING="" ADDING="" ROTATED_OUT="霓虹町 亚海悬城" \
python3 scripts/build_map_pool.py
```

## 初始化（仅首次）
从 `地图轮换.xlsx` 读取基线：
```bash
python3 scripts/build_map_pool.py --bootstrap
```

## 历史记录
- 文件：`history/versions.json`
- 记录字段：`version` / `version_date` / `current_pool`
- 同版本号会覆盖旧记录

## 构建失败锁
- 如果上一次构建失败，必须先重跑同版本并成功
- 其它版本会被直接拒绝且不会写入仓库

## GitHub Pages
生成的 JSON 发布后，访问路径为：
- `/maps.json`
- `/meta.json`
