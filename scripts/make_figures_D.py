# -*- coding: utf-8 -*-
"""
成员D 交付图生成脚本
D01 T09 执行计划树（基线 r1）
D02 S20 执行计划树 + 三阶段对照（基线 r1）
D03 基数估计误差影响链路图

所有数字来自仓库保存的原始结果（成员B/C采集）：
  results/plans/baseline/T09_r1.json, T11_r1.json, S20_r1.json, S16_r1.json
  results/plans/reanalyze_control/, extended/ 下同名文件
  results/node_runs.csv, results/query_summary.csv, results/stats_baseline.json
生成：PNG(200dpi) 与 SVG 双格式，风格与 B/C 系列图保持一致（微软雅黑）。
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.font_manager as fm
import os

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "figures")

C_BLUE = "#1F77B4"    # 正常
C_GREEN = "#1B9E77"   # 估计准确/已修正
C_RED = "#D95F02"     # 误差/警示
C_GRAY = "#5A5A5A"
C_LIGHT = "#F5F6F8"
C_AMBER = "#E8A33D"

def fmt(n):
    return f"{n:,}"

def new_ax(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax

def box(ax, cx, cy, w, h, lines, edge=C_BLUE, face="white", lw=2.0, fs=10,
        title_fs=None, title_color=None, radius=1.2):
    """lines: [(text, style)] style in {'title','dim','err','ok','plain','small'}"""
    p = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                       boxstyle=f"round,pad=0.3,rounding_size={radius}",
                       fc=face, ec=edge, lw=lw, zorder=3)
    ax.add_patch(p)
    n = len(lines)
    title_fs = title_fs or fs
    for i, (t, st) in enumerate(lines):
        y = cy + h/2 - (i + 0.5) * h / n
        if st == "title":
            ax.text(cx, y, t, ha="center", va="center", fontsize=title_fs,
                    fontweight="bold", color=title_color or "#222222", zorder=4)
        elif st == "dim":
            ax.text(cx, y, t, ha="center", va="center", fontsize=fs-1.2,
                    color=C_GRAY, zorder=4)
        elif st == "err":
            ax.text(cx, y, t, ha="center", va="center", fontsize=fs,
                    color=C_RED, fontweight="bold", zorder=4)
        elif st == "ok":
            ax.text(cx, y, t, ha="center", va="center", fontsize=fs,
                    color=C_GREEN, zorder=4)
        else:
            ax.text(cx, y, t, ha="center", va="center", fontsize=fs,
                    color="#222222", zorder=4)

def arrow(ax, x1, y1, x2, y2, color=C_GRAY, lw=1.6, style="-|>"):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                        mutation_scale=14, color=color, lw=lw, zorder=2,
                        shrinkA=2, shrinkB=2)
    ax.add_patch(a)

def panel(ax, x, y, w, h, title, body_lines, fs=9.5, edge=C_GRAY):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0",
                       fc=C_LIGHT, ec=edge, lw=1.0, zorder=1)
    ax.add_patch(p)
    ax.text(x + 1.2, y + h - 2.0, title, ha="left", va="top",
            fontsize=fs + 1.5, fontweight="bold", color="#222222", zorder=4)
    ax.text(x + 1.2, y + h - 5.2, "\n".join(body_lines), ha="left", va="top",
            fontsize=fs, color="#333333", zorder=4, linespacing=1.55)

def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=200, bbox_inches="tight",
                facecolor="white")
    fig.savefig(os.path.join(OUT, name + ".svg"), bbox_inches="tight",
                facecolor="white")
    plt.close(fig)
    print("saved", name)

# =====================================================================
# D01  T09 执行计划树
# =====================================================================
fig, ax = new_ax(16.2, 9.6)
ax.text(50, 99, "案例一 T09（三表连接）执行计划树：基数误差在最上层连接处新生",
        ha="center", va="top", fontsize=16, fontweight="bold")
ax.text(50, 95.2, "TPC-H SF=1 · PostgreSQL 17.6 · 基线阶段正式测量 r1 · 计划文件 results/plans/baseline/T09_r1.json",
        ha="center", va="top", fontsize=10, color=C_GRAY)

# 根节点
box(ax, 33, 85, 40, 13, [
    ("Hash Join   连接条件 l_orderkey = o_orderkey", "title"),
    ("估计 315,018 行   |   实际 30,519 行", "err"),
    ("Q-error = 10.32（高估 10.3 倍）", "err"),
    ("估计代价 256,034.79   ·   实际 2,831.6 ms", "plain"),
], edge=C_RED, lw=2.6, fs=10.5, title_color=C_RED)

# 左子树 lineitem
box(ax, 14, 63, 24, 12.5, [
    ("Seq Scan  lineitem (600万行)", "title"),
    ("过滤 l_shipdate > 1995-03-15", "dim"),
    ("估计 3,236,751 / 实际 3,241,776", "plain"),
    ("Q-error 1.00 √   代价 185,611.70（72.5%）", "ok"),
    ("实际 1,284.2 ms（占总耗时 45%）", "plain"),
], edge=C_GREEN, fs=9.3)

# 右子树 hash
box(ax, 54, 63, 13, 7.5, [
    ("Hash 构建", "title"),
    ("估计 145,988 / 实际 147,126", "plain"),
], edge=C_GREEN, fs=9.0)

# 内连接
box(ax, 54, 46.5, 26, 12, [
    ("Hash Join   o_custkey = c_custkey", "title"),
    ("估计 145,988 / 实际 147,126", "plain"),
    ("Q-error 1.01 √", "ok"),
    ("代价 53,310.25   ·   实际 801.3 ms", "plain"),
], edge=C_GREEN, fs=9.3)

box(ax, 40, 24, 22, 11.5, [
    ("Seq Scan  orders (150万行)", "title"),
    ("过滤 o_orderdate < 1995-03-15", "dim"),
    ("估计 734,716 / 实际 727,305", "plain"),
    ("Q-error 1.01 √   代价 45,462.00", "ok"),
], edge=C_GREEN, fs=9.0)

box(ax, 63.5, 24, 10.5, 7, [
    ("Hash 构建", "title"),
    ("29,805 / 30,142", "plain"),
], edge=C_GREEN, fs=9.0)

box(ax, 63.5, 8.5, 21, 9, [
    ("Seq Scan  customer", "title"),
    ("过滤 c_mktsegment = 'BUILDING'", "dim"),
    ("估计 29,805 / 实际 30,142（Q 1.01 √）", "ok"),
], edge=C_GREEN, fs=9.0)

# 树边
arrow(ax, 27, 78.4, 15.5, 69.4)        # root -> lineitem
arrow(ax, 41, 78.4, 53, 66.8)          # root -> hash
arrow(ax, 54, 59.2, 54, 52.5)          # hash -> inner HJ
arrow(ax, 46, 40.5, 41.5, 29.8)        # inner HJ -> orders
arrow(ax, 62, 40.5, 63.4, 27.6)        # inner HJ -> hash2
arrow(ax, 63.5, 20.5, 63.5, 13.2)      # hash2 -> customer

# 右侧结论面板
panel(ax, 71, 8, 28.5, 84, "因果分析链（本案例）", [
    "① 底层全部准确：单表过滤与",
    "   外键连接的 Q-error 均 ≤ 1.01",
    "   ——误差不是从底层累积来的",
    "",
    "② 误差在顶层连接“新生”：",
    "   估计式 3,236,751 × 145,988",
    "   ÷ 1,500,000 ≈ 315,018，",
    "   即假设两输入的行在连接键上",
    "   均匀独立分布（选择率取订单",
    "   侧主键的不同值数 1/150万）",
    "",
    "③ 失效原因：o_orderdate < d 与",
    "   l_shipdate > d 经由连接键和",
    "   业务规则（发货日期≥订单日",
    "   期+1天）强负相关，独立性",
    "   假设在连接后失效",
    "",
    "④ 向 Cost 传导被稀释（推算）：",
    "   输出行数代价项偏差 ≈ 2,845，",
    "   仅占总代价约 1.1%",
    "",
    "⑤ 计划未切换的原因（推算）：",
    "   无论按 315,018 还是 30,519",
    "   估计，324万行×14.7万行的",
    "   连接中 Hash Join 都明显优于",
    "   需要百万次索引探测的 Nested",
    "   Loop，候选代价差距很大",
], fs=8.8)

# 底部条
ax.text(1, 0.6, "该 10.3 倍误差未改变计划与时间（时间花在估计准确的扫描上）；但若该节点不是根节点、还要参与上层连接或聚合，"
                "315,018 与 30,519 的差距将直接误导后续决策。",
        ha="left", va="bottom", fontsize=9.5, color=C_RED, fontweight="bold")
save(fig, "D01_plan_tree_T09")

# =====================================================================
# D02  S20 执行计划树 + 三阶段对照
# =====================================================================
fig, ax = new_ax(16.2, 9.0)
ax.text(50, 99, "案例二 S20（跨表相关）执行计划树：扩展统计修正不了跨表联合分布",
        ha="center", va="top", fontsize=16, fontweight="bold")
ax.text(50, 95.2, "合成数据 · 1万客户 × 30万订单 · 订单邮编与客户城市编码跨表绑定 · 计划文件 results/plans/baseline/S20_r1.json",
        ha="center", va="top", fontsize=10, color=C_GRAY)

box(ax, 26, 80, 42, 13, [
    ("Hash Join   连接条件 customer_id = id", "title"),
    ("估计 30 行   |   实际 3,000 行", "err"),
    ("Q-error = 100（低估 100 倍）", "err"),
    ("估计代价 5,551.12   ·   实际 44.2 ms（Execution Time 中位）", "plain"),
], edge=C_RED, lw=2.6, fs=10.5, title_color=C_RED)

box(ax, 13, 55, 22, 12, [
    ("Seq Scan  cross_orders (30万行)", "title"),
    ("过滤 zipcode = 'Z00'", "dim"),
    ("估计 3,000 / 实际 3,000", "ok"),
    ("Q-error 1.00 √   代价 5,372.00（96.8%）", "ok"),
    ("实际 49.1 ms", "plain"),
], edge=C_GREEN, fs=9.0)

box(ax, 41, 55, 12, 7.5, [
    ("Hash 构建", "title"),
    ("估计 100 / 实际 100", "plain"),
], edge=C_GREEN, fs=9.0)

box(ax, 41, 36, 21.5, 10, [
    ("Seq Scan  cross_customers", "title"),
    ("过滤 city = 'C00'", "dim"),
    ("估计 100 / 实际 100（Q 1.00 √）", "ok"),
    ("代价 170.00", "plain"),
], edge=C_GREEN, fs=9.0)

# 案例背景小框
box(ax, 26, 14, 50, 13.5, [
    ("案例背景：相关性被人为构造在两张表之间", "title"),
    ("cross_customers(id 主键, city)，cross_orders(id 主键, customer_id 外键, zipcode)", "dim"),
    ("每客户固定 30 笔订单；订单的 zipcode 编码与其客户的 city 编码一致", "dim"),
    ("两张表各自的 city / zipcode 单列分布完全均匀（各 100 种取值）", "dim"),
    ("=> 单列统计对两个过滤都给出准确估计，但都无法描述“跨表的 city→zipcode”", "dim"),
], edge=C_GRAY, face=C_LIGHT, fs=9.0)

arrow(ax, 19, 73.4, 13.8, 61.4)
arrow(ax, 34, 73.4, 40.3, 58.8)
arrow(ax, 41, 51.2, 41, 41.2)

panel(ax, 56, 6, 43, 86, "机制与三阶段对照", [
    "① 两个单表过滤都估计得很准（MCV 频率准确），",
    "   误差只出现在连接节点：",
    "   估计式 3,000 × 100 ÷ 10,000 = 30，即假设",
    "   3,000 笔 Z00 订单均匀分布在 10,000 名客户",
    "   上（每客户 0.3 笔 × 100 家 C00 客户）",
    "   实际：每笔订单的邮编由其客户的城市决定，",
    "   3,000 笔 Z00 订单全部属于 100 家 C00 客户",
    "   ——这是“跨表的函数依赖”，任何单表统计",
    "   （包括扩展统计）都无法表达",
    "",
    "② 三阶段对照（数据、SQL、索引、参数完全相同）：",
    "  ────────────────────────────────────────",
    "   阶段              估计  Q-error  代价      计划",
    "   基线              30    100    5,551.12  Hash Join",
    "   仅重新 ANALYZE    30    100    5,551.12  Hash Join",
    "   扩展统计          30    100    5,551.12  Hash Join",
    "  ────────────────────────────────────────",
    "   对照组 S16（同表相关）：扩展统计后 Q 100→1",
    "   对照组 S19（倾斜稀有）：扩展统计后 Q 189→1",
    "",
    "③ 时间影响：三阶段中位耗时 44.2 / 45.0 / 42.2 ms",
    "   （Execution Time；含插桩开销）三阶段差异属测量波动，100 倍误差未造成可声称的加速或劣化；代价 96.8%",
    "   花在与选择率无关的 30 万行顺序扫描上",
], fs=8.8)

ax.text(1, 0.6, "结论：扩展统计（同表多列依赖/MCV/ndistinct）修正了 S16/S19，却对 S20 无能为力——"
                "跨表联合分布是原生统计机制的结构性盲区，这正是学习型跨表基数估计（DeepDB、NeuroCard 等）的研究动机。",
        ha="left", va="bottom", fontsize=9.5, color=C_RED, fontweight="bold")
save(fig, "D02_plan_tree_S20")

# =====================================================================
# D03  影响链路图
# =====================================================================
fig, ax = new_ax(16.8, 10.2)
ax.text(50, 99, "基数估计误差的影响链路：从统计假设到执行性能",
        ha="center", va="top", fontsize=16.5, fontweight="bold")
ax.text(50, 95.4, "四个实测案例在链路各环节的表现（数据均来自本组实验，标注“推算”的为基于代价模型的透明计算，非实测）",
        ha="center", va="top", fontsize=10, color=C_GRAY)

# 顶层链路
stages = [
    ("① 统计信息与假设", "单列 MCV / 直方图\n采样估计 n_distinct\n多列独立性假设"),
    ("② 基数估计", "Plan Rows\n（每节点估计行数）\n用 Q-error 度量"),
    ("③ 代价估计", "Total Cost\n由子节点行数与\n访问路径代价累加"),
    ("④ 计划选择", "Join 算法 / Join Order\n访问路径 / 构建侧\n在候选计划中择优"),
    ("⑤ 执行性能", "Actual Rows\nActual Total Time\n中间结果真实规模"),
]
sx = [11, 30.5, 50, 69.5, 89]
sw, sh, sy = 16.5, 12.5, 84
for (t, b), x in zip(stages, sx):
    box(ax, x, sy, sw, sh, [(t, "title"), ("", "plain"), (b.split("\n")[0], "dim"),
                            (b.split("\n")[1], "dim"), (b.split("\n")[2], "dim")],
        edge="#37474F", face="#ECEFF1", fs=8.6, title_fs=10)
for i in range(4):
    arrow(ax, sx[i] + sw/2 + 0.4, sy, sx[i+1] - sw/2 - 0.4, sy, color="#37474F", lw=2.2)

# 四条案例泳道
lanes = [
    dict(y=66, name="T09 三表连接\n（TPC-H）", color=C_RED,
         cells={
             1: ("Q-error 10.32\n误差在顶层连接“新生”\n（底层全部 ≤1.02）", C_RED),
             2: ("代价偏差 ≈1.1%（推算）\nHash Join 代价对输出\n行数不敏感 → 稀释", C_AMBER),
             3: ("计划未变：仍选\nHash Join（3.2M×147K\n时 Hash 明显占优）", C_GREEN),
             4: ("实际 2,688 ms（中位）\n时间由扫描决定\n与误差基本无关", C_GREEN),
         }),
    dict(y=47.5, name="S20 跨表相关\n（合成数据）", color=C_RED,
         cells={
             1: ("Q-error 100\n单表估计全准\n误差源于跨表联合分布", C_RED),
             2: ("代价偏差 ≈0.5%（推算）\n扩展统计前后\n代价 5,551.12 不变", C_AMBER),
             3: ("计划未变：三阶段\n均 Hash Join；扩展统计\n无法表达跨表依赖", C_GREEN),
             4: ("实际约 44 ms（中位）\n风险：若作为上层连接\n内侧 → 100×工作量误判", C_AMBER),
         }),
    dict(y=29, name="S16 同表强相关\n（对照案例）", color=C_GREEN,
         cells={
             1: ("基线 Q-error 100\n扩展统计后 → 1\n（同表依赖可修正）", C_AMBER),
             2: ("代价完全不变\n6,122.00（实测）\nSeq Scan 代价与选择率无关", C_GREEN),
             3: ("计划自由度为零：\n无 city/zipcode 索引\n只有 Seq Scan 可选", C_GREEN),
             4: ("中位 58.5→52.2→30.8 ms\n随阶段下降属顺序效应\n误差大 ≠ 有性能后果", C_GREEN),
         }),
    dict(y=10.5, name="T11 五表连接\n（对照案例）", color=C_BLUE,
         cells={
             1: ("n_distinct 低估 3.9 倍\n(38.4万 vs 实际150万)\n每循环估计 16 行 / 实际 4 行", C_AMBER),
             2: ("内侧累计工作量\n高估 ≈4.1 倍（推算）\n顶层输出估计仍准（Q 1.01）", C_AMBER),
             3: ("计划未变：NL+索引\n每循环代价 1.1 很小\n候选差距大 → 稳健", C_GREEN),
             4: ("实际 1,585 ms（中位）\n同一连接条件存在\n两套估计口径并存", C_BLUE),
         }),
]
for ln in lanes:
    y = ln["y"]
    box(ax, 6.5, y, 10.5, 12, [(t, "title") for t in ln["name"].split("\n")],
        edge=ln["color"], face="white", lw=2.0, fs=9.2, title_color=ln["color"])
    for i in range(1, 5):
        t, c = ln["cells"][i]
        box(ax, sx[i], y, sw, 12, [(x, "plain") for x in t.split("\n")],
            edge=c, face="white", lw=1.6, fs=8.2)
    for i in range(0, 4):
        arrow(ax, sx[i] + sw/2 + 0.4, y, sx[i+1] - sw/2 - 0.4, y,
              color="#B0BEC5", lw=1.3)

ax.text(50, 1.2,
        "核心规律：误差的危害 ≈ 误差大小 × 误差位置（是否被下游决策引用）× 下游决策自由度。"
        "本实验如实呈现：未观察到 Join 算法或 Join Order 切换——所有显著误差要么出现在无下游可误导的根节点，要么处于零自由度位置。",
        ha="center", va="bottom", fontsize=10.5, fontweight="bold", color="#222222")
save(fig, "D03_influence_chain")

print("ALL DONE")
