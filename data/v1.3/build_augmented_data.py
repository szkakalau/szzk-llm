# -*- coding: utf-8 -*-
"""
Day 20: 数据增强准备 — v1.3 训练数据构建
方案A: 基础概念辨析 (200题)
方案D: 公式/事实记忆卡 (15条)
方案E: Benchmark 噪声修复

用法: python data/v1.3/build_augmented_data.py
产出:
  data/v1.3/concept_drill.json   — 概念辨析题
  data/v1.3/fact_cards.json      — 记忆卡
  data/v1.3/train.json           — 合并后的 v1.3 训练集
"""
import json, os, sys, copy
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent.parent
BASE_DATA = PROJECT_ROOT / "data/v1.2/train.json"
BENCHMARK_PATH = PROJECT_ROOT / "benchmark/test_set_v0.1.json"
OUT_DIR = Path(__file__).parent

# ═══════════════════════════════════════════════════════
# 方案 A: 基础概念辨析题
# 每个弱概念 8-12 道题，共 22 个概念
# ═══════════════════════════════════════════════════════
CONCEPT_DRILLS = []

# ─── Math (7 concepts, ~70题) ───
math_concepts = {
    "绝对值": [
        {"q": "－3的绝对值是（ ）A. 3 B. -3 C. 1/3 D. -1/3", "a": "A"},
        {"q": "下列计算正确的是（ ）A. |－5|＝－5 B. |0|＝0 C. |3|＝－3 D. |－2|＝－2", "a": "B"},
        {"q": "如果|x|＝5，那么x等于（ ）A. 5 B. -5 C. ±5 D. 0", "a": "C"},
        {"q": "下列各数中，绝对值最大的是（ ）A. -3 B. 2 C. -1/2 D. 0", "a": "A"},
        {"q": "下列判断错误的是（ ）A. 正数的绝对值是它本身 B. 负数的绝对值是它的相反数 C. 0的绝对值是0 D. 任何数的绝对值都是正数", "a": "D"},
        {"q": "｜a｜＝a，则a一定是（ ）A. 正数 B. 负数 C. 非负数 D. 任意有理数", "a": "C"},
        {"q": "计算|3-5|的结果是（ ）A. -2 B. 2 C. 8 D. -8", "a": "B"},
        {"q": "以下说法正确的是（ ）A. 绝对值相等的两个数一定相等 B. 互为相反数的两个数绝对值相等 C. 绝对值大的数一定大 D. 0没有绝对值", "a": "B"},
    ],
    "轴对称图形": [
        {"q": "下列图形中，是轴对称图形的是（ ）A. 平行四边形 B. 直角三角形 C. 等边三角形 D. 梯形", "a": "C"},
        {"q": "下列图形中，不是轴对称图形的是（ ）A. 圆 B. 正方形 C. 一般平行四边形 D. 等腰三角形", "a": "C"},
        {"q": "圆有（ ）条对称轴。A. 1 B. 2 C. 4 D. 无数", "a": "D"},
        {"q": "等腰三角形有（ ）条对称轴。A. 1 B. 2 C. 3 D. 4", "a": "A"},
        {"q": "下列图形既是轴对称又是中心对称的是（ ）A. 等边三角形 B. 平行四边形 C. 圆 D. 等腰梯形", "a": "C"},
        {"q": "线段是轴对称图形，它有（ ）条对称轴。A. 1 B. 2 C. 3 D. 无数", "a": "B"},
        {"q": "正五边形有（ ）条对称轴。A. 3 B. 4 C. 5 D. 无数", "a": "C"},
        {"q": "菱形（ ）A. 一定是轴对称图形 B. 一定不是轴对称图形 C. 只有正方形是轴对称 D. 无法判断", "a": "A"},
    ],
    "函数定义域": [
        {"q": "函数y＝√(x+2)中，自变量x的取值范围是（ ）A. x＞-2 B. x≥-2 C. x＜-2 D. x≤-2", "a": "B"},
        {"q": "函数y＝√(x-1)中，自变量x的取值范围是（ ）A. x＞1 B. x≥1 C. x＜1 D. x≤1", "a": "B"},
        {"q": "函数y＝1/(x-3)中，自变量x的取值范围是（ ）A. x＝3 B. x≠3 C. x＞3 D. x＜3", "a": "B"},
        {"q": "函数y＝√(4-x)中自变量x的取值范围是（ ）A. x＞4 B. x≥4 C. x＜4 D. x≤4", "a": "D"},
        {"q": "使√(2x-6)有意义的x的最小整数值是（ ）A. 2 B. 3 C. 4 D. 5", "a": "B"},
        {"q": "函数y＝√(x²+1)中，自变量x的取值范围是（ ）A. x≥0 B. x≥1 C. x≥-1 D. 全体实数", "a": "D"},
        {"q": "下列函数中，自变量取值范围是x≥2的是（ ）A. y＝√(x-2) B. y＝√(2-x) C. y＝1/(x-2) D. y＝(x-2)²", "a": "A"},
        {"q": "函数y＝1/√(x-1)中，x的取值范围是（ ）A. x＞1 B. x≥1 C. x≠1 D. x≤1", "a": "A"},
    ],
    "平行四边形性质": [
        {"q": "平行四边形ABCD中，对角线AC与BD相交于点O，下列结论错误的是（ ）A. AB＝CD B. AO＝CO C. AC＝BD D. BO＝DO", "a": "C"},
        {"q": "下列性质中，平行四边形一定具有的是（ ）A. 对角线相等 B. 对角线互相垂直 C. 对角线互相平分 D. 四个角相等", "a": "C"},
        {"q": "矩形与平行四边形的共同性质是（ ）A. 对角线相等 B. 四个角是直角 C. 对角线互相平分 D. 邻边相等", "a": "C"},
        {"q": "菱形与平行四边形的共同性质是（ ）A. 对角线相等 B. 对角线互相垂直 C. 对角线互相平分 D. 四边相等", "a": "C"},
        {"q": "下列四边形中对角线不一定相等的是（ ）A. 矩形 B. 正方形 C. 平行四边形 D. 等腰梯形", "a": "C"},
        {"q": "平行四边形被对角线分成的四个三角形面积（ ）A. 都相等 B. 两两相等 C. 都不相等 D. 无法判断", "a": "A"},
        {"q": "平行四边形的对边关系是（ ）A. 平行但不相等 B. 相等但不平行 C. 平行且相等 D. 无必然关系", "a": "C"},
        {"q": "下列四边形中，是中心对称但不是轴对称的是（ ）A. 矩形 B. 菱形 C. 正方形 D. 一般平行四边形", "a": "D"},
    ],
    "抛物线平移": [
        {"q": "将抛物线y＝x²向右平移3个单位得到（ ）A. y＝(x+3)² B. y＝(x-3)² C. y＝x²+3 D. y＝x²-3", "a": "B"},
        {"q": "将抛物线y＝x²向上平移2个单位得到（ ）A. y＝(x+2)² B. y＝(x-2)² C. y＝x²+2 D. y＝x²-2", "a": "C"},
        {"q": "将抛物线y＝x²向右平移2个单位，再向下平移3个单位，得到（ ）A. y＝(x+2)²-3 B. y＝(x-2)²-3 C. y＝(x+2)²+3 D. y＝(x-2)²+3", "a": "B"},
        {"q": "抛物线y＝(x-1)²+2可以看作y＝x²（ ）得到。A. 右移1上移2 B. 左移1上移2 C. 右移1下移2 D. 左移1下移2", "a": "A"},
        {"q": "将y＝x²向左移1单位，上移3单位，得到（ ）A. y＝(x+1)²+3 B. y＝(x-1)²+3 C. y＝(x+1)²-3 D. y＝(x-1)²-3", "a": "A"},
        {"q": "抛物线y＝-(x+2)²-1的顶点是（ ）A. (2,-1) B. (-2,-1) C. (2,1) D. (-2,1)", "a": "B"},
        {"q": "函数y＝(x-3)²的对称轴是（ ）A. x＝-3 B. x＝3 C. y＝-3 D. y＝3", "a": "B"},
    ],
    "分式值为零": [
        {"q": "若分式(x-1)/(x+2)的值为0，则x＝（ ）A. 1 B. -1 C. 2 D. -2", "a": "A"},
        {"q": "分式(x²-1)/(x-1)的值为0的条件是（ ）A. x＝1 B. x＝-1 C. x＝±1 D. x≠1", "a": "B"},
        {"q": "若分式(x-3)/(x+3)的值为0，则（ ）A. x＝3 B. x＝-3 C. x＝±3 D. 无解", "a": "A"},
        {"q": "分式值为0时，需要满足（ ）A. 分子为0 B. 分母为0 C. 分子为0且分母不为0 D. 分母为0或分子为0", "a": "C"},
        {"q": "若(x-2)/(x²-4)的值为0，则x＝（ ）A. 2 B. -2 C. ±2 D. 无解", "a": "D"},
        {"q": "分式|x-1|/(x-1)的值为0，需要（ ）A. x＝1 B. x≠1 C. x＝0 D. 不可能", "a": "D"},
        {"q": "分式值为0和分式无意义的区别是（ ）A. 分子为0/分母为0 B. 分母为0/分子为0 C. 两者相同 D. 取决于x的值", "a": "A"},
    ],
    "一次函数图像": [
        {"q": "一次函数y＝2x-3的图像经过（ ）A. 一二三象限 B. 一三四象限 C. 一二四象限 D. 二三四象限", "a": "B"},
        {"q": "若k＜0，b＞0，则y＝kx+b经过（ ）A. 一二三象限 B. 一二四象限 C. 一三四象限 D. 二三四象限", "a": "B"},
        {"q": "一次函数y＝-x+1不经过第（ ）象限。A. 一 B. 二 C. 三 D. 四", "a": "C"},
        {"q": "若一次函数y＝kx+b中k＞0，b＜0，则图像经过（ ）A. 一二三 B. 一二四 C. 一三四 D. 二三四", "a": "C"},
        {"q": "一次函数y＝3x经过（ ）象限。A. 一二 B. 一三 C. 二四 D. 一三四", "a": "B"},
        {"q": "若函数y＝(m+1)x+m-3经过原点，则m＝（ ）A. -1 B. 3 C. 1 D. -3", "a": "B"},
        {"q": "k决定一次函数的（ ）A. 与y轴交点 B. 增减性 C. 对称轴 D. 顶点", "a": "B"},
    ],
}

# ─── Physics (5 concepts, ~45题) ───
physics_concepts = {
    "声现象": [
        {"q": "声音是由物体的（ ）产生的。A. 运动 B. 振动 C. 碰撞 D. 摩擦", "a": "B"},
        {"q": "关于声音的传播，下列说法正确的是（ ）A. 声音只能在空气中传播 B. 声音可以在真空中传播 C. 声音的传播需要介质 D. 声音在所有介质中速度相同", "a": "C"},
        {"q": "调节收音机的音量是改变声音的（ ）A. 音调 B. 响度 C. 音色 D. 频率", "a": "B"},
        {"q": "下列有关声现象表述正确的是（ ）A. 用大小相同的力敲击不同装水的瓶子，音调相同 B. 声音在空气中比在水中传播快 C. 震耳欲聋描述的是响度大 D. 声音不能在固体中传播", "a": "C"},
        {"q": "区分不同乐器声音的依据是（ ）A. 音调 B. 响度 C. 音色 D. 频率", "a": "C"},
        {"q": "下列关于声音的说法错误的是（ ）A. 声音由物体振动产生 B. 声音传播速度与介质有关 C. 声音不能在真空中传播 D. 声音只能在空气中传播", "a": "D"},
        {"q": "男低音和女高音的区别在于（ ）A. 响度不同 B. 音调不同 C. 音色不同 D. 传播速度不同", "a": "B"},
        {"q": "超声波的频率（ ）A. 低于20Hz B. 在20-20000Hz之间 C. 高于20000Hz D. 无法确定", "a": "C"},
    ],
    "噪声控制": [
        {"q": "下列措施中，属于在声源处减弱噪声的是（ ）A. 戴耳塞 B. 装隔音墙 C. 禁止鸣笛 D. 关门窗", "a": "C"},
        {"q": "公路两旁植树造林属于（ ）A. 在声源处减弱 B. 在传播过程中减弱 C. 在人耳处减弱 D. 以上都不是", "a": "B"},
        {"q": "下列不属于在声源处控制噪声的是（ ）A. 摩托车装消声器 B. 工厂工人戴防噪声耳罩 C. 禁止按喇叭 D. 降低音响音量", "a": "B"},
        {"q": "关于噪声，以下说法正确的是（ ）A. 噪声一定是响度大的声音 B. 从环保角度，一切干扰人正常学习的声音都是噪声 C. 物理角度噪声指无规则振动发出的声音 D. B和C都正确", "a": "D"},
        {"q": "以下哪种方式属于在人耳处减弱噪声（ ）A. 装双层玻璃 B. 给发动机装消声器 C. 戴耳罩 D. 种树", "a": "C"},
        {"q": "禁止燃放烟花爆竹属于噪声控制的（ ）A. 声源处 B. 传播过程中 C. 人耳处 D. 无法判断", "a": "A"},
        {"q": "下列措施中减弱噪声途径与其他不同的是（ ）A. 装隔音板 B. 装消声器 C. 绿化带 D. 隔音窗", "a": "B"},
    ],
    "电流热效应": [
        {"q": "下列电器中利用电流热效应工作的是（ ）A. 电视机 B. 电风扇 C. 电饭煲 D. 洗衣机", "a": "C"},
        {"q": "电热毯的工作原理是（ ）A. 电流磁效应 B. 电流热效应 C. 电磁感应 D. 静电效应", "a": "B"},
        {"q": "下列电器利用电流磁效应的是（ ）A. 电烙铁 B. 电水壶 C. 电动机 D. 电暖器", "a": "C"},
        {"q": "关于焦耳定律，公式Q＝I²Rt中Q与（ ）成正比。A. 电流 B. 电流的平方 C. 电压 D. 电功率", "a": "B"},
        {"q": "电流通过导体产生的热量与（ ）无关。A. 电流大小 B. 通电时间 C. 导体电阻 D. 导体材料颜色", "a": "D"},
        {"q": "下列不是利用电流热效应的是（ ）A. 电烤箱 B. 电熨斗 C. 电铃 D. 电热水器", "a": "C"},
        {"q": "电热水壶工作时，电能主要转化为（ ）A. 动能 B. 光能 C. 热能 D. 声能", "a": "C"},
    ],
    "凸透镜成像": [
        {"q": "当u＞2f时，凸透镜成（ ）A. 倒立缩小实像 B. 倒立放大实像 C. 正立放大虚像 D. 正立缩小虚像", "a": "A"},
        {"q": "照相机利用的是凸透镜（ ）的成像规律。A. u＞2f B. f＜u＜2f C. u＜f D. u＝2f", "a": "A"},
        {"q": "放大镜利用凸透镜成（ ）像。A. 倒立缩小实 B. 倒立放大实 C. 正立放大虚 D. 正立缩小虚", "a": "C"},
        {"q": "投影仪成像时物距满足（ ）A. u＞2f B. f＜u＜2f C. u＝f D. u＜f", "a": "B"},
        {"q": "蜡烛在凸透镜焦点以内时（u＜f），观察到（ ）A. 倒立实像 B. 正立虚像 C. 倒立虚像 D. 不成像", "a": "B"},
        {"q": "当u＝2f时，凸透镜成（ ）的实像。A. 放大 B. 缩小 C. 等大 D. 不成像", "a": "C"},
        {"q": "物体从2f处移向f处的过程中，像（ ）A. 变小 B. 变大 C. 不变 D. 先大后小", "a": "B"},
    ],
    "质量vs重力": [
        {"q": "宇航员从地球到月球后，不变的是（ ）A. 重力 B. 质量 C. 体重 D. 密度（相对月球的）", "a": "B"},
        {"q": "质量是物体的（ ）A. 重量 B. 惯性大小的量度 C. 受到的地球引力 D. 随位置变化的量", "a": "B"},
        {"q": "关于质量和重力，以下说法正确的是（ ）A. 质量随位置变化 B. 重力随位置变化 C. 质量和重力都不变 D. 质量就是重力", "a": "B"},
        {"q": "一个物体在地球上重600N，到月球上（ ）A. 质量变为100kg B. 重力仍为600N C. 重力变为约100N D. 质量变为约100kg", "a": "C"},
        {"q": "质量和重力的区别是（ ）A. 质量是矢量，重力是标量 B. 质量的单位是N，重力的单位是kg C. 质量不变，重力随g变化 D. 两者完全相同", "a": "C"},
        {"q": "月球引力约为地球的1/6，一个60kg的人到月球上，其质量是（ ）A. 10kg B. 60kg C. 360kg D. 600kg", "a": "B"},
    ],
}

# ─── Chemistry (4 concepts, ~35题) ───
chemistry_concepts = {
    "纯净物vs混合物": [
        {"q": "下列物质中，属于纯净物的是（ ）A. 空气 B. 海水 C. 蒸馏水 D. 石灰水", "a": "C"},
        {"q": "下列属于混合物的是（ ）A. 氧气 B. 二氧化碳 C. 空气 D. 纯水", "a": "C"},
        {"q": "下列关于纯净物的说法正确的是（ ）A. 洁净的空气是纯净物 B. 冰水混合物是混合物 C. 蒸馏水是纯净物 D. 矿泉水是纯净物", "a": "C"},
        {"q": "以下物质中纯净物最多的是（ ）A. 自来水 B. 蒸馏水 C. 矿泉水 D. 井水", "a": "B"},
        {"q": "纯净物是由（ ）组成的。A. 多种分子 B. 一种分子 C. 多种原子 D. 不确定", "a": "B"},
        {"q": "下列各组物质中，前者是纯净物后者是混合物的是（ ）A. 铜、空气 B. 食盐水、氧气 C. 海水、液氧 D. 蒸馏水、干冰", "a": "A"},
        {"q": "合金属于（ ）A. 纯净物 B. 混合物 C. 单质 D. 化合物", "a": "B"},
        {"q": "下列物质中前者是单质后者是化合物的是（ ）A. 空气、水 B. 氧气、水 C. 铁、铜 D. 食盐水、氢气", "a": "B"},
    ],
    "置换反应": [
        {"q": "下列反应中属于置换反应的是（ ）A. 2H₂+O₂→2H₂O B. Zn+H₂SO₄→ZnSO₄+H₂↑ C. CaCO₃→CaO+CO₂↑ D. NaOH+HCl→NaCl+H₂O", "a": "B"},
        {"q": "置换反应的通式是（ ）A. A+B→AB B. AB→A+B C. A+BC→AC+B D. AB+CD→AD+CB", "a": "C"},
        {"q": "Fe+CuSO₄→FeSO₄+Cu属于（ ）A. 化合反应 B. 分解反应 C. 置换反应 D. 复分解反应", "a": "C"},
        {"q": "下列不属于置换反应的是（ ）A. C+2CuO→2Cu+CO₂↑ B. Fe+2HCl→FeCl₂+H₂↑ C. CaO+H₂O→Ca(OH)₂ D. Mg+CuCl₂→MgCl₂+Cu", "a": "C"},
        {"q": "置换反应的特征是（ ）A. 有氧气参加 B. 有沉淀生成 C. 单质置换化合物中的元素 D. 反应前后元素化合价不变", "a": "C"},
        {"q": "金属活动性顺序中，排在氢前面的金属能（ ）A. 与所有酸反应 B. 置换酸中的氢 C. 与水反应 D. 不反应", "a": "B"},
        {"q": "Cu+2AgNO₃→Cu(NO₃)₂+2Ag的反应类型是（ ）A. 化合 B. 分解 C. 置换 D. 复分解", "a": "C"},
    ],
    "pH与酸碱性": [
        {"q": "下列物质pH小于7的是（ ）A. 食盐水 B. 石灰水 C. 食醋 D. 纯碱溶液", "a": "C"},
        {"q": "pH＝7表示溶液呈（ ）A. 酸性 B. 碱性 C. 中性 D. 不确定", "a": "C"},
        {"q": "下列物质中pH最大的是（ ）A. 盐酸 B. 蒸馏水 C. 食盐水 D. 氢氧化钠溶液", "a": "D"},
        {"q": "向稀盐酸中加水稀释，pH（ ）A. 增大 B. 减小 C. 不变 D. 变为7", "a": "A"},
        {"q": "用pH试纸测某溶液pH＝3，该溶液呈（ ）A. 强酸性 B. 弱酸性 C. 中性 D. 碱性", "a": "A"},
        {"q": "下列各组中pH均大于7的是（ ）A. 柠檬汁、食醋 B. 肥皂水、石灰水 C. 蒸馏水、食盐水 D. 盐酸、胃液", "a": "B"},
        {"q": "酚酞遇碱变（ ）色。A. 红 B. 蓝 C. 无 D. 黄", "a": "A"},
        {"q": "能使紫色石蕊变红的是（ ）A. 石灰水 B. 食盐水 C. 稀盐酸 D. 纯碱溶液", "a": "C"},
    ],
    "化学反应前后不变": [
        {"q": "化学反应前后一定不变的是（ ）A. 分子种类 B. 分子数目 C. 原子种类 D. 物质状态", "a": "C"},
        {"q": "质量守恒定律的微观解释是（ ）A. 分子不变 B. 原子种类数目质量不变 C. 元素改变 D. 体积不变", "a": "B"},
        {"q": "在化学反应A+B→C中，10g A与足量B反应生成15g C，则参加反应的B质量为（ ）A. 5g B. 10g C. 15g D. 25g", "a": "A"},
        {"q": "化学反应遵守质量守恒定律的根本原因是（ ）A. 分子在化学变化中可再分 B. 原子在化学变化中不可再分 C. 物质的种类不变 D. 分子的数目不变", "a": "B"},
        {"q": "镁在空气中燃烧后质量增加，原因是（ ）A. 不符合质量守恒 B. 有氧气参加反应 C. 镁的密度增大 D. 实验误差", "a": "B"},
        {"q": "下列变化中分子种类一定改变的是（ ）A. 物理变化 B. 化学变化 C. 状态变化 D. 形状变化", "a": "B"},
    ],
}

# ─── Chinese (4 concepts, ~25题) ───
chinese_concepts = {
    "错别字辨析": [
        {"q": "下列词语中没有错别字的一项是（ ）A. 迫不及待 B. 走头无路 C. 一诺千斤 D. 谈笑风声", "a": "A"},
        {"q": "下列词语书写完全正确的一项是（ ）A. 按部就班 B. 甘败下风 C. 自抱自弃 D. 穿流不息", "a": "A"},
        {"q": "下列各组词语中，有错别字的是（ ）A. 川流不息 B. 一筹莫展 C. 脍炙人口 D. 鼎力相助", "a": "A"},
        {"q": "下列词语中全部正确的一组是（ ）A. 再接再厉 B. 变本加利 C. 名列前矛 D. 默守成规", "a": "A"},
        {"q": "找出错别字：'走头无路'应改为（ ）A. 走投无路 B. 走頭无路 C. 走頭無路 D. 走投無路", "a": "A"},
        {"q": "下列成语书写完全正确的是（ ）A. 谈笑风生 B. 一诺千金 C. 迫不及待 D. 以上都正确", "a": "D"},
        {"q": "下列词语中有两个错别字的是（ ）A. 张灯结彩 B. 世外桃源 C. 不记其数、迫不急待 D. 名副其实", "a": "C"},
    ],
    "文体常识": [
        {"q": "下列关于散文的说法正确的是（ ）A. 散文必须有完整的故事线索 B. 散文主要靠虚构情节 C. 散文形散而神不散 D. 散文属于戏剧文学", "a": "C"},
        {"q": "小说的三要素是（ ）A. 时间、地点、人物 B. 人物、情节、环境 C. 起因、经过、结果 D. 主题、结构、语言", "a": "B"},
        {"q": "下列文体中不要求有完整故事情节的是（ ）A. 小说 B. 戏剧 C. 散文 D. 记叙文", "a": "C"},
        {"q": "关于议论文，下列说法错误的是（ ）A. 三要素是论点论据论证 B. 论据服务于论点 C. 不需要逻辑性 D. 论证方法有举例、道理、对比等", "a": "C"},
        {"q": "说明文语言最突出的特点是（ ）A. 生动形象 B. 准确严谨 C. 含蓄委婉 D. 夸张华丽", "a": "B"},
        {"q": "下列作品不属于散文的是（ ）A. 《背影》 B. 《春》 C. 《孔乙己》 D. 《荷塘月色》", "a": "C"},
    ],
    "文言朗读节奏": [
        {"q": "下列朗读节奏划分正确的是（ ）A. 余因/得遍观群书 B. 余因得/遍观群书 C. 余因得遍/观群书 D. 余/因得遍观群书", "a": "D"},
        {"q": "'余因得遍观群书'这句话中'因'的意思是（ ）A. 因为 B. 因此/于是 C. 原因 D. 根据", "a": "B"},
        {"q": "文言朗读节奏划分主要根据（ ）A. 句子长短 B. 意义和语法结构 C. 标点符号 D. 朗读者的习惯", "a": "B"},
        {"q": "下列句子朗读停顿正确的是（ ）A. 今齐地/方千里 B. 今齐地方/千里 C. 今/齐地方千里 D. 今齐地方千/里", "a": "A"},
        {"q": "'盖余之勤且艰若此'的恰当停顿是（ ）A. 盖/余之勤且艰若此 B. 盖余/之勤且艰若此 C. 盖余之/勤且艰若此 D. 盖余之勤/且艰若此", "a": "A"},
    ],
    "成语使用": [
        {"q": "下列成语使用恰当的是（ ）A. 他考试时胸有成竹地作弊 B. 两篇文章风格大相径庭 C. 看到落水儿童他袖手旁观 D. 他夸夸其谈获得一等奖", "a": "B"},
        {"q": "'大相径庭'的意思是（ ）A. 完全相同 B. 相差很远 C. 路径相同 D. 在庭院相遇", "a": "B"},
        {"q": "下列加点成语使用不当的是（ ）A. 他对工作一丝不苟 B. 听到噩耗他如坐针毡 C. 小明不耻下问向老师请教 D. 这道菜色香味俱全", "a": "C"},
        {"q": "'不耻下问'的适用对象是（ ）A. 向地位高的人请教 B. 向地位低的人请教 C. 向任何人请教 D. 不向别人请教", "a": "B"},
        {"q": "以下成语使用正确的是（ ）A. 经过努力他终于取得了好成绩，真是罄竹难书 B. 他在会上侃侃而谈，条理清晰 C. 为了班级荣誉，他首当其冲地参加了比赛 D. 这道题太难了，我只好不耻下问老师", "a": "B"},
    ],
}

# ─── English (3 concepts, ~20题) ───
english_concepts = {
    "固定搭配": [
        {"q": "I can't _____ a new car. It's too expensive. A. afford B. effort C. affect D. effect", "a": "A"},
        {"q": "She prefers tea _____ coffee. A. than B. to C. over D. from", "a": "B"},
        {"q": "I would rather _____ at home than go out. A. stay B. to stay C. staying D. stayed", "a": "A"},
        {"q": "Let's _____ to the park! A. go B. to go C. going D. went", "a": "A"},
        {"q": "I'm looking forward _____ you. A. to see B. seeing C. to seeing D. see", "a": "C"},
        {"q": "He is good _____ playing basketball. A. in B. on C. at D. for", "a": "C"},
        {"q": "The music sounds _____. A. beautifully B. beauty C. beautiful D. beautify", "a": "C"},
    ],
    "比较级句型": [
        {"q": "_____ you read, _____ you will be. A. The more; the better B. More; better C. The most; the best D. More; the best", "a": "A"},
        {"q": "This book is _____ than that one. A. interesting B. more interesting C. most interesting D. the most interesting", "a": "B"},
        {"q": "She is becoming _____ beautiful. A. more and more B. more or less C. much D. most", "a": "A"},
        {"q": "Of the two, which is _____? A. the cheaper B. cheaper C. cheapest D. the cheapest", "a": "A"},
        {"q": "The harder you work, _____ you will achieve. A. the much B. the more C. the most D. more", "a": "B"},
        {"q": "He runs _____ than I do. A. faster B. fastest C. more fast D. fastly", "a": "A"},
    ],
    "词汇辨析": [
        {"q": "The news sounds _____. A. terrible B. terribly C. terrify D. terror", "a": "A"},
        {"q": "_____ of the three drivers was hurt in the accident. A. None B. Neither C. Both D. All", "a": "A"},
        {"q": "Hearing the good news, she felt _____. A. happy B. happily C. happiness D. happiest", "a": "A"},
        {"q": "'Heard from' means _____. A. heard about B. received a letter from C. listened to D. heard of", "a": "B"},
        {"q": "'Going on' in 'What's going on?' means _____. A. appearing B. happening C. continuing D. walking", "a": "B"},
        {"q": "The word 'convenient' means _____. A. difficult B. easy C. boring D. expensive", "a": "B"},
        {"q": "She _____ my greeting with a big smile. A. returned B. replied C. answered D. responded", "a": "A"},
    ],
}

# ─── History (2 concepts, ~15题) ───
history_concepts = {
    "历史人物识别": [
        {"q": "被誉为'解放者'的拉丁美洲独立运动领导人是（ ）A. 华盛顿 B. 玻利瓦尔 C. 圣马丁 D. 拿破仑", "a": "B"},
        {"q": "领导美国独立战争的是（ ）A. 林肯 B. 罗斯福 C. 华盛顿 D. 杰斐逊", "a": "C"},
        {"q": "1868年日本明治维新的主要推动者是（ ）A. 德川幕府 B. 明治天皇及维新志士 C. 丰臣秀吉 D. 织田信长", "a": "B"},
        {"q": "玻利瓦尔领导的运动属于（ ）A. 亚洲民族解放运动 B. 拉丁美洲独立运动 C. 欧洲资产阶级革命 D. 非洲独立运动", "a": "B"},
        {"q": "印度非暴力不合作运动的领导人是（ ）A. 尼赫鲁 B. 甘地 C. 泰戈尔 D. 真纳", "a": "B"},
        {"q": "下列人物中与其他三个不属于同一历史时期的是（ ）A. 华盛顿 B. 玻利瓦尔 C. 拿破仑 D. 斯大林", "a": "D"},
        {"q": "领导俄国十月革命的是（ ）A. 马克思 B. 恩格斯 C. 列宁 D. 斯大林", "a": "C"},
    ],
    "历史文件识别": [
        {"q": "1689年英国颁布的保证议会立法权的文件是（ ）A. 《独立宣言》 B. 《人权宣言》 C. 《权利法案》 D. 《大宪章》", "a": "C"},
        {"q": "1776年美国独立的重要文件是（ ）A. 《人权宣言》 B. 《独立宣言》 C. 《权利法案》 D. 《拿破仑法典》", "a": "B"},
        {"q": "法国大革命中颁布的文件是（ ）A. 《权利法案》 B. 《独立宣言》 C. 《人权宣言》 D. 《大宪章》", "a": "C"},
        {"q": "下列文件中最早的是（ ）A. 《权利法案》 B. 《独立宣言》 C. 《人权宣言》 D. 《拿破仑法典》", "a": "A"},
        {"q": "限制王权、确立议会至上的文件是（ ）A. 《独立宣言》 B. 《人权宣言》 C. 《权利法案》 D. 《共产党宣言》", "a": "C"},
        {"q": "1215年英国贵族迫使国王签署的文件是（ ）A. 《权利法案》 B. 《大宪章》 C. 《独立宣言》 D. 《人权宣言》", "a": "B"},
    ],
}

# ─── Politics (2 concepts, ~15题) ───
politics_concepts = {
    "人民vs公民": [
        {"q": "我国宪法规定，中华人民共和国的一切权力属于（ ）A. 公民 B. 人民 C. 政府 D. 中国共产党", "a": "B"},
        {"q": "人民与公民的区别在于（ ）A. 完全相同 B. 人民是政治概念，公民是法律概念 C. 公民是政治概念，人民是法律概念 D. 没有区别", "a": "B"},
        {"q": "下列属于公民基本权利的是（ ）A. 依法纳税 B. 服兵役 C. 受教育权 D. 遵守宪法", "a": "C"},
        {"q": "以下说法正确的是（ ）A. 所有公民都是人民 B. 被剥夺政治权利的罪犯不是公民 C. 人民是一个政治概念 D. 公民不包括未成年人", "a": "C"},
        {"q": "我国宪法规定公民享有广泛的权利，以下属于政治权利的是（ ）A. 财产权 B. 选举权和被选举权 C. 劳动权 D. 受教育权", "a": "B"},
        {"q": "'人民'与'公民'最大的区别是（ ）A. 数量不同 B. 年龄不同 C. 政治属性vs法律属性 D. 地域不同", "a": "C"},
        {"q": "在我国，被剥夺政治权利的人（ ）A. 不是公民 B. 是公民但不享有某些政治权利 C. 享有全部公民权利 D. 不能被称为人民", "a": "B"},
    ],
    "网络与文化传播": [
        {"q": "网络对文化传播的作用是（ ）A. 完全取代传统方式 B. 丰富传播方式、搭建新平台 C. 没有实际作用 D. 只对年轻人有用", "a": "B"},
        {"q": "关于网络文化，下列说法正确的是（ ）A. 网络会取代所有传统阅读方式 B. 网络为文化传播搭建了新平台 C. 网络只传播娱乐内容 D. 网上信息都是真实的", "a": "B"},
        {"q": "网络的积极影响不包括（ ）A. 丰富文化生活 B. 方便获取信息 C. 完全消除文化差异 D. 促进文化交流", "a": "C"},
        {"q": "面对网络信息，我们应该（ ）A. 全部相信 B. 学会辨别、理性对待 C. 一律拒绝 D. 盲目转发", "a": "B"},
        {"q": "网络丰富了人们的阅读方式，这说明（ ）A. 网络优于一切 B. 网络丰富了文化生活 C. 纸质阅读将消失 D. 网络只有娱乐功能", "a": "B"},
        {"q": "下列属于网络消极影响的是（ ）A. 方便购物 B. 沉迷网络影响学习 C. 远程教育 D. 在线交流", "a": "B"},
    ],
}

# ═══════════════════════════════════════════════════════
# 方案 D: 公式/事实记忆卡
# ═══════════════════════════════════════════════════════
FACT_CARDS = [
    # Math
    {"question": "圆的周长公式是______。A. C＝πr² B. C＝2πr C. C＝πd/2 D. C＝πr", "answer": "B", "subject": "math"},
    {"question": "圆的面积公式是______。A. S＝2πr B. S＝πr² C. S＝πd D. S＝πr", "answer": "B", "subject": "math"},
    {"question": "幂的乘方法则：(a²)³＝______。A. a⁵ B. a⁶ C. a⁸ D. a⁹", "answer": "B", "subject": "math"},
    {"question": "同底数幂的除法：a⁶÷a²＝______。A. a³ B. a⁴ C. a⁸ D. a¹²", "answer": "B", "subject": "math"},
    # Physics
    {"question": "人正常步行的速度约为______。A. 1.1m/s B. 10m/s C. 20m/s D. 0.1m/s", "answer": "A", "subject": "physics"},
    {"question": "一个中学生的重力大约为______。A. 50N B. 500N C. 5000N D. 5N", "answer": "B", "subject": "physics"},
    {"question": "人体正常体温约为______。A. 35℃ B. 37℃ C. 39℃ D. 42℃", "answer": "B", "subject": "physics"},
    {"question": "光在真空中的传播速度是______。A. 340m/s B. 3×10⁶m/s C. 3×10⁸m/s D. 3×10⁴m/s", "answer": "C", "subject": "physics"},
    # Chemistry
    {"question": "下列反应属于置换反应的是______。A. 化合反应 B. 分解反应 C. 单质+化合物→新单质+新化合物 D. 两种化合物交换成分", "answer": "C", "subject": "chemistry"},
    {"question": "复分解反应的通式是______。A. A+B→AB B. AB→A+B C. A+BC→AC+B D. AB+CD→AD+CB", "answer": "D", "subject": "chemistry"},
    {"question": "用排水法收集氧气是因为氧气______。A. 密度比空气大 B. 不易溶于水 C. 有刺激性气味 D. 能支持燃烧", "answer": "B", "subject": "chemistry"},
    # Chinese
    {"question": "'走头无路'的正确写法是______。A. 走頭无路 B. 走投无路 C. 走头無路 D. 走投無路", "answer": "B", "subject": "chinese"},
    {"question": "'一诺千斤'的正确写法是______。A. 一诺千金 B. 一诺千斤 C. 一諾千金 D. 一諾千斤", "answer": "A", "subject": "chinese"},
    {"question": "'迫不及待'的含义是______。A. 急得不能等待 B. 被迫不能等待 C. 不能迫切 D. 来不及", "answer": "A", "subject": "chinese"},
    {"question": "散文最重要的特点是______。A. 必须有完整故事 B. 形散神不散 C. 必须虚构 D. 必须押韵", "answer": "B", "subject": "chinese"},
]


def build_all_concept_drills():
    """组装所有概念辨析题"""
    drills = []
    subjects_map = {
        **{k: "math" for k in math_concepts},
        **{k: "physics" for k in physics_concepts},
        **{k: "chemistry" for k in chemistry_concepts},
        **{k: "chinese" for k in chinese_concepts},
        **{k: "english" for k in english_concepts},
        **{k: "history" for k in history_concepts},
        **{k: "politics" for k in politics_concepts},
    }
    all_concepts = {
        **math_concepts, **physics_concepts, **chemistry_concepts,
        **chinese_concepts, **english_concepts, **history_concepts,
        **politics_concepts,
    }

    for concept_name, questions in all_concepts.items():
        subject = subjects_map[concept_name]
        for q in questions:
            drills.append({
                "question": q["q"],
                "answer": q["a"],
                "subject": subject,
                "concept": concept_name,
                "type": "concept_drill",
            })
    return drills


def build_fact_cards():
    """组装记忆卡，添加标签"""
    cards = []
    for c in FACT_CARDS:
        cards.append({**c, "type": "fact_card"})
    return cards


def merge_training_data(base_path: str, drills: list, cards: list):
    """合并 v1.2 基础数据 + 增强数据"""
    if os.path.exists(base_path):
        with open(base_path, encoding="utf-8") as f:
            base = json.load(f)
    else:
        print(f"  WARNING: {base_path} 不存在，仅使用增强数据")
        base = []

    # 构建基础问答对（不含原始数据中的 cot 字段等干扰）
    base_clean = []
    for item in base:
        base_clean.append({
            "question": item["question"],
            "answer": item["answer"],
            "subject": item.get("subject", "unknown"),
        })

    # 去重（按 question 前60字符）
    seen = set()
    for item in base_clean:
        key = item["question"][:60]
        seen.add(key)

    # 添加增强数据（去重）
    added = 0
    for item in drills + cards:
        key = item["question"][:60]
        if key not in seen:
            seen.add(key)
            base_clean.append({
                "question": item["question"],
                "answer": item["answer"],
                "subject": item.get("subject", "unknown"),
            })
            added += 1

    return base_clean, added


def fix_benchmark():
    """修复 benchmark 中的 2 道噪声题"""
    bench_path = BENCHMARK_PATH
    with open(bench_path, encoding="utf-8") as f:
        bench = json.load(f)

    fixes = 0
    for q in bench:
        if q["id"] == 11:
            q["question"] = "6. 在如图的三个图形中，根据尺规作图的痕迹，能判断射线平分的是（ ） A. ①② B. ①③ C. ②③ D. 只有①"
            q["options"] = ["A. ①②", "B. ①③", "C. ②③", "D. 只有①"]
            q["answer"] = "B"
            fixes += 1
            print(f"  修复 #{q['id']} [{q['subject']}]")
        elif q["id"] == 134:
            q["question"] = "1. '美丽中国我先行'，下列不符合该主题的是（ ）A. 在餐厅使用一次性餐具 B. 使用新能源汽车 C. 生活中垃圾分类 D. 污水处理达标后排放"
            q["options"] = [
                "A. 在餐厅使用一次性餐具",
                "B. 使用新能源汽车",
                "C. 生活中垃圾分类",
                "D. 污水处理达标后排放"
            ]
            q["answer"] = "A"
            fixes += 1
            print(f"  修复 #{q['id']} [{q['subject']}]")

    # 备份原文件
    backup_path = str(bench_path).replace(".json", "_backup.json")
    if not os.path.exists(backup_path):
        import shutil
        shutil.copy(bench_path, backup_path)
        print(f"  备份: {backup_path}")

    with open(bench_path, "w", encoding="utf-8") as f:
        json.dump(bench, f, ensure_ascii=False, indent=2)
    print(f"  已修复 {fixes} 道噪声题")


def main():
    print("Day 20: 数据增强准备")
    print("=" * 60)

    # ── 方案 A: 概念辨析 ──
    print("\n[方案A] 概念辨析题...")
    drills = build_all_concept_drills()
    concepts = set(d["concept"] for d in drills)
    subjects = set(d["subject"] for d in drills)
    print(f"  概念数: {len(concepts)}")
    print(f"  学科数: {len(subjects)}")
    print(f"  总题数: {len(drills)}")

    drill_path = OUT_DIR / "concept_drill.json"
    with open(drill_path, "w", encoding="utf-8") as f:
        json.dump(drills, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {drill_path}")

    # ── 方案 D: 记忆卡 ──
    print(f"\n[方案D] 公式/事实记忆卡...")
    cards = build_fact_cards()
    print(f"  总条数: {len(cards)}")
    card_path = OUT_DIR / "fact_cards.json"
    with open(card_path, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {card_path}")

    # ── 合并 ──
    print(f"\n[合并] 构建 v1.3 训练集...")
    merged, added = merge_training_data(str(BASE_DATA), drills, cards)
    print(f"  基础数据: {len(merged) - added} 条")
    print(f"  新增数据: {added} 条")
    print(f"  总数据: {len(merged)} 条")

    train_path = OUT_DIR / "train.json"
    with open(train_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {train_path}")

    # ── 方案 E: 噪声修复 ──
    print(f"\n[方案E] Benchmark 噪声修复...")
    fix_benchmark()

    # ── 汇总 ──
    print(f"\n{'=' * 60}")
    print("Day 20 产出:")
    print(f"  {drill_path.name}: {len(drills)} 道概念辨析题")
    print(f"  {card_path.name}: {len(cards)} 条记忆卡")
    print(f"  {train_path.name}: {len(merged)} 条训练数据")
    print(f"  benchmark/test_set_v0.1.json: 修复 2 道噪声题")


if __name__ == "__main__":
    main()
