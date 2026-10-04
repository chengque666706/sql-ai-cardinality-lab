# 成员D 交付物说明

课题：SQL 与 AI 协同优化——基于机器学习的查询优化（本学期 PostgreSQL 实证分析）
成员D：执行计划影响与典型案例分析负责人

## 内容清单

| 文件 | 说明 | 仓库内位置 |
| --- | --- | --- |
| `成员D_执行计划影响分析.md` | 案例分析文字（主交付物）：T09/S20 两个典型案例 + S16/T11 两个对照案例，含节点级指标表、估计式复现、Cost 传导推算、"未发生计划切换"的如实分析与 PPT 使用建议 | `reports/成员D_执行计划影响分析.md` |
| `figures/D01_plan_tree_T09.png/.svg` | 案例一 T09 执行计划树（估计/实际行数、Q-error、代价、耗时逐节点标注） | `figures/` |
| `figures/D02_plan_tree_S20.png/.svg` | 案例二 S20 执行计划树 + 扩展统计三阶段对照 | `figures/` |
| `figures/D03_influence_chain.png/.svg` | 影响链路图（统计假设→基数→代价→计划→性能，四案例并列） | `figures/` |
| `results/D_典型案例节点级指标表.csv` | 四个案例 27 条节点级原始记录（自 `node_runs.csv` 筛选，字段口径一致） | `results/` |
| `scripts/make_figures_D.py` | 三张图的生成脚本；数字改动后重跑即可再生成 PNG+SVG | `scripts/` |

## 数字口径

- 所有实测数字来自仓库保存的原始结果：`results/plans/`、`results/node_runs.csv`、`results/query_summary.csv`、`results/stats_baseline.json`。
- 节点级数字取基线阶段正式测量 r1（与 `query_summary.csv` 的 `representative_plan` 一致）；查询级耗时用三次正式测量的中位数，与 B/C 报告的 Execution Time 口径一致。
- 文中标注"（推算）"的内容是基于 PostgreSQL 代价模型的透明算术推演，非实测，共 5 处，已在正文和附录逐一列明。
- Q-error = max(估计/实际, 实际/估计)；`Actual Rows` 为每循环口径。

## 使用方式

1. 成员A制作 PPT 时，按分析文档第 6.2 节的三页方案插图（D01/D02/D03 均为白底、微软雅黑、与 B/C 系列图同风格）。
2. 成员E的衔接点见分析文档第 6.3 节。
3. 并入仓库时按上表第二列复制到对应目录即可；`make_figures_D.py` 不依赖仓库路径，可独立运行。
