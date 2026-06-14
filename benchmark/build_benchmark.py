# -*- coding: utf-8 -*-
"""
Day 8: 200道客观题题库建设
用法: python benchmark/build_benchmark.py
输出: benchmark/test_set_v0.1.json
"""
import json, re, random, os, sys
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

random.seed(42)

# ═══════════════════════════════════════════════════════
# 1. 从训练数据提取选择题
# ═══════════════════════════════════════════════════════
def extract_options_from_question(text: str) -> list[str] | None:
    """从题目文本中提取选项。支持多种格式：
    A. xxx B. xxx C. xxx D. xxx
    A、xxx B、xxx
    （A）xxx （B）xxx
    A．xxx B．xxx
    """
    # 尝试多种选项分隔模式
    patterns = [
        r'([A-D])[.\s、．）)]([^A-D]*?)(?=[A-D][.\s、．）)]|$)',
        r'[（(]([A-D])[）)]([^(（]*?)(?=[（(][A-D][）)]|$)',
    ]

    for pat in patterns:
        matches = re.findall(pat, text)
        if len(matches) >= 2:  # 至少2个选项才算选择题
            options = []
            for letter, content in matches:
                content = content.strip().rstrip('.').strip()
                if content:  # 非空选项
                    options.append(f"{letter}. {content}")
            if len(options) >= 2:
                return options
    return None


def extract_single_answer(answer_text: str, question: str) -> str | None:
    """提取单选题答案（单个字母 A/B/C/D）"""
    # 如果答案已经是一个字母
    ans = answer_text.strip().upper()
    if len(ans) <= 2 and ans and ans[0] in 'ABCD':
        return ans[0]

    # 尝试从长答案中提取: "选C" "故选A" "答案：B"
    m = re.search(r'(?:选|故选|答案为?|答案[：:])[^A-D]*([A-D])', answer_text)
    if m:
        return m.group(1)
    m = re.search(r'(?:^|[（(])\s*([A-D])\s*(?:[）).]|$)', answer_text)
    if m:
        return m.group(1)

    # 对于有选项的题目，在答案中查找出现的选项字母
    if extract_options_from_question(question):
        for ch in ans:
            if ch in 'ABCD':
                return ch

    return None


def is_clean_question(q: dict) -> bool:
    """检查题目是否适合作为benchmark"""
    text = q["question"]
    # 太短/太长都不行
    if len(text) < 15 or len(text) > 800:
        return False
    # 必须有选项
    if not extract_options_from_question(text):
        return False
    # 答案必须可解析
    if not extract_single_answer(q["answer"], text):
        return False
    return True


# ═══════════════════════════════════════════════════════
# 2. 补充题目（数据不足的学科手动补充高质量中考题）
# ═══════════════════════════════════════════════════════
SUPPLEMENT = {
    "chemistry": [
        {"question": "下列物质中，属于纯净物的是（ ）A. 空气 B. 海水 C. 蒸馏水 D. 石灰水",
         "answer": "C", "options": ["A. 空气", "B. 海水", "C. 蒸馏水", "D. 石灰水"]},
        {"question": "下列变化中，属于化学变化的是（ ）A. 冰雪融化 B. 木材燃烧 C. 玻璃破碎 D. 铁丝弯曲",
         "answer": "B", "options": ["A. 冰雪融化", "B. 木材燃烧", "C. 玻璃破碎", "D. 铁丝弯曲"]},
        {"question": "下列物质在氧气中燃烧，产生大量白烟的是（ ）A. 木炭 B. 铁丝 C. 红磷 D. 硫粉",
         "answer": "C", "options": ["A. 木炭", "B. 铁丝", "C. 红磷", "D. 硫粉"]},
        {"question": "下列金属中，活动性最强的是（ ）A. 铁 B. 铜 C. 锌 D. 银",
         "answer": "C", "options": ["A. 铁", "B. 铜", "C. 锌", "D. 银"]},
        {"question": "下列物质溶于水，溶液温度降低的是（ ）A. 浓硫酸 B. 氢氧化钠 C. 氯化钠 D. 硝酸铵",
         "answer": "D", "options": ["A. 浓硫酸", "B. 氢氧化钠", "C. 氯化钠", "D. 硝酸铵"]},
        {"question": "下列实验操作正确的是（ ）A. 用嘴吹灭酒精灯 B. 用手直接取用固体药品 C. 稀释浓硫酸时将水倒入浓硫酸 D. 读取量筒读数时视线与凹液面最低处相平",
         "answer": "D", "options": ["A. 用嘴吹灭酒精灯", "B. 用手直接取用固体药品", "C. 稀释浓硫酸时将水倒入浓硫酸", "D. 读取量筒读数时视线与凹液面最低处相平"]},
        {"question": "下列物质中，属于有机合成材料的是（ ）A. 羊毛 B. 棉花 C. 塑料 D. 蚕丝",
         "answer": "C", "options": ["A. 羊毛", "B. 棉花", "C. 塑料", "D. 蚕丝"]},
        {"question": "铁生锈的条件是（ ）A. 只与水接触 B. 只与氧气接触 C. 与水和氧气同时接触 D. 与二氧化碳接触",
         "answer": "C", "options": ["A. 只与水接触", "B. 只与氧气接触", "C. 与水和氧气同时接触", "D. 与二氧化碳接触"]},
        {"question": "下列物质中，pH小于7的是（ ）A. 食盐水 B. 石灰水 C. 食醋 D. 纯碱溶液",
         "answer": "C", "options": ["A. 食盐水", "B. 石灰水", "C. 食醋", "D. 纯碱溶液"]},
        {"question": "化学反应前后，一定不变的是（ ）A. 分子种类 B. 分子数目 C. 原子种类 D. 物质种类",
         "answer": "C", "options": ["A. 分子种类", "B. 分子数目", "C. 原子种类", "D. 物质种类"]},
        {"question": "下列气体中，有刺激性气味的是（ ）A. 氮气 B. 氧气 C. 二氧化硫 D. 二氧化碳",
         "answer": "C", "options": ["A. 氮气", "B. 氧气", "C. 二氧化硫", "D. 二氧化碳"]},
        {"question": "下列物质中，属于氧化物的是（ ）A. O₂ B. H₂O C. KClO₃ D. NaOH",
         "answer": "B", "options": ["A. O₂", "B. H₂O", "C. KClO₃", "D. NaOH"]},
        {"question": "下列金属中，不能与稀盐酸反应生成氢气的是（ ）A. 镁 B. 锌 C. 铁 D. 铜",
         "answer": "D", "options": ["A. 镁", "B. 锌", "C. 铁", "D. 铜"]},
        {"question": "过滤操作中，不需要用到的仪器是（ ）A. 烧杯 B. 漏斗 C. 玻璃棒 D. 酒精灯",
         "answer": "D", "options": ["A. 烧杯", "B. 漏斗", "C. 玻璃棒", "D. 酒精灯"]},
        {"question": "下列物质中，属于复合肥料的是（ ）A. 尿素 B. 硝酸钾 C. 过磷酸钙 D. 氯化钾",
         "answer": "B", "options": ["A. 尿素", "B. 硝酸钾", "C. 过磷酸钙", "D. 氯化钾"]},
        {"question": "下列气体中，能使带火星的木条复燃的是（ ）A. 氮气 B. 氧气 C. 二氧化碳 D. 氢气",
         "answer": "B", "options": ["A. 氮气", "B. 氧气", "C. 二氧化碳", "D. 氢气"]},
        {"question": "下列物质中，属于碱的是（ ）A. NaCl B. NaOH C. HCl D. H₂O",
         "answer": " B", "options": ["A. NaCl", "B. NaOH", "C. HCl", "D. H₂O"]},
        {"question": "原子中，决定元素种类的是（ ）A. 质子数 B. 中子数 C. 电子数 D. 相对原子质量",
         "answer": "A", "options": ["A. 质子数", "B. 中子数", "C. 电子数", "D. 相对原子质量"]},
        {"question": "下列反应中，属于置换反应的是（ ）A. 2H₂+O₂→2H₂O B. Zn+H₂SO₄→ZnSO₄+H₂↑ C. CaCO₃→CaO+CO₂↑ D. NaOH+HCl→NaCl+H₂O",
         "answer": "B", "options": ["A. 2H₂+O₂→2H₂O", "B. Zn+H₂SO₄→ZnSO₄+H₂↑", "C. CaCO₃→CaO+CO₂↑", "D. NaOH+HCl→NaCl+H₂O"]},
        {"question": "下列物质敞口放置，质量会增加且变质的是（ ）A. 浓盐酸 B. 浓硫酸 C. 氢氧化钠固体 D. 食盐",
         "answer": "C", "options": ["A. 浓盐酸", "B. 浓硫酸", "C. 氢氧化钠固体", "D. 食盐"]},
        {"question": "下列各组物质中，能用酚酞试液鉴别的是（ ）A. 食盐水和蒸馏水 B. 稀盐酸和稀硫酸 C. 石灰水和氢氧化钠溶液 D. 稀盐酸和石灰水",
         "answer": "D", "options": ["A. 食盐水和蒸馏水", "B. 稀盐酸和稀硫酸", "C. 石灰水和氢氧化钠溶液", "D. 稀盐酸和石灰水"]},
        {"question": "下列实验现象描述正确的是（ ）A. 硫在氧气中燃烧发出淡蓝色火焰 B. 铁丝在氧气中燃烧生成四氧化三铁 C. 镁条在空气中燃烧发出耀眼白光 D. 木炭在空气中燃烧生成黑色固体",
         "answer": "C", "options": ["A. 硫在氧气中燃烧发出淡蓝色火焰", "B. 铁丝在氧气中燃烧生成四氧化三铁", "C. 镁条在空气中燃烧发出耀眼白光", "D. 木炭在空气中燃烧生成黑色固体"]},
    ],
    "math": [
        {"question": "－3的绝对值是（ ）A. 3 B. -3 C. 1/3 D. -1/3",
         "answer": "A", "options": ["A. 3", "B. -3", "C. 1/3", "D. -1/3"]},
        {"question": "下列图形中，是轴对称图形的是（ ）A. 平行四边形 B. 直角三角形 C. 圆 D. 梯形",
         "answer": "C", "options": ["A. 平行四边形", "B. 直角三角形", "C. 圆", "D. 梯形"]},
        {"question": "不等式 x-2>0 的解集是（ ）A. x<2 B. x>2 C. x<-2 D. x>-2",
         "answer": "B", "options": ["A. x<2", "B. x>2", "C. x<-2", "D. x>-2"]},
        {"question": "计算 (-2a²)³ 的结果是（ ）A. -8a⁶ B. -6a⁶ C. 8a⁶ D. -8a⁵",
         "answer": "A", "options": ["A. -8a⁶", "B. -6a⁶", "C. 8a⁶", "D. -8a⁵"]},
        {"question": "已知等腰三角形的一个底角为50°，则其顶角为（ ）A. 50° B. 80° C. 100° D. 130°",
         "answer": "B", "options": ["A. 50°", "B. 80°", "C. 100°", "D. 130°"]},
        {"question": "若点P(2, -3)关于x轴对称，则对称点的坐标为（ ）A. (2, 3) B. (-2, -3) C. (-2, 3) D. (2, -3)",
         "answer": "A", "options": ["A. (2, 3)", "B. (-2, -3)", "C. (-2, 3)", "D. (2, -3)"]},
        {"question": "下列方程中，是一元二次方程的是（ ）A. x+2=0 B. x²+2x+1=0 C. 2x+y=5 D. 1/x=2",
         "answer": "B", "options": ["A. x+2=0", "B. x²+2x+1=0", "C. 2x+y=5", "D. 1/x=2"]},
        {"question": "一组数据：3, 5, 7, 7, 9, 7，其中众数是（ ）A. 5 B. 6 C. 7 D. 9",
         "answer": "C", "options": ["A. 5", "B. 6", "C. 7", "D. 9"]},
        {"question": "在Rt△ABC中，∠C=90°，AC=3，BC=4，则AB=（ ）A. 5 B. 6 C. 7 D. 8",
         "answer": "A", "options": ["A. 5", "B. 6", "C. 7", "D. 8"]},
        {"question": "分解因式 x²-4 的结果是（ ）A. x(x-4) B. (x+2)(x-2) C. (x-2)² D. (x+2)²",
         "answer": "B", "options": ["A. x(x-4)", "B. (x+2)(x-2)", "C. (x-2)²", "D. (x+2)²"]},
        {"question": "已知圆的半径为5cm，则其周长为（ ）A. 5π cm B. 10π cm C. 25π cm D. 50π cm",
         "answer": "B", "options": ["A. 5π cm", "B. 10π cm", "C. 25π cm", "D. 50π cm"]},
        {"question": "若一次函数 y=kx+b 中，k<0，b>0，则其图像经过（ ）A. 一二三象限 B. 一三四象限 C. 一二四象限 D. 二三四象限",
         "answer": "C", "options": ["A. 一二三象限", "B. 一三四象限", "C. 一二四象限", "D. 二三四象限"]},
        {"question": "抛掷一枚质地均匀的硬币，正面朝上的概率是（ ）A. 0 B. 1/4 C. 1/2 D. 1",
         "answer": "C", "options": ["A. 0", "B. 1/4", "C. 1/2", "D. 1"]},
        {"question": "下列运算正确的是（ ）A. a²·a³=a⁶ B. (a²)³=a⁵ C. a⁶÷a²=a³ D. (ab)²=a²b²",
         "answer": "D", "options": ["A. a²·a³=a⁶", "B. (a²)³=a⁵", "C. a⁶÷a²=a³", "D. (ab)²=a²b²"]},
        {"question": "一个多边形的内角和为720°，则这个多边形是（ ）A. 四边形 B. 五边形 C. 六边形 D. 七边形",
         "answer": "C", "options": ["A. 四边形", "B. 五边形", "C. 六边形", "D. 七边形"]},
        {"question": "函数 y=√(x-1) 中，自变量x的取值范围是（ ）A. x>1 B. x≥1 C. x<1 D. x≤1",
         "answer": "B", "options": ["A. x>1", "B. x≥1", "C. x<1", "D. x≤1"]},
        {"question": "已知x=1是方程2x²+kx-1=0的一个根，则k=（ ）A. -1 B. 0 C. 1 D. 2",
         "answer": "A", "options": ["A. -1", "B. 0", "C. 1", "D. 2"]},
        {"question": "如图，在平行四边形ABCD中，对角线AC与BD相交于点O，则下列结论不正确的是（ ）A. AB=CD B. AO=CO C. AC=BD D. BO=DO",
         "answer": "C", "options": ["A. AB=CD", "B. AO=CO", "C. AC=BD", "D. BO=DO"]},
        {"question": "将抛物线 y=x² 向右平移2个单位，再向下平移3个单位，得到的抛物线解析式为（ ）A. y=(x+2)²-3 B. y=(x-2)²-3 C. y=(x+2)²+3 D. y=(x-2)²+3",
         "answer": "B", "options": ["A. y=(x+2)²-3", "B. y=(x-2)²-3", "C. y=(x+2)²+3", "D. y=(x-2)²+3"]},
        {"question": "若分式 (x-1)/(x+2) 的值为0，则x=（ ）A. 1 B. -1 C. 2 D. -2",
         "answer": "A", "options": ["A. 1", "B. -1", "C. 2", "D. -2"]},
    ],
    "chinese": [
        {"question": "下列词语中，加点字的读音全部正确的一项是（ ）A. 倔强(jué) 迸溅(bèng) 称职(chèn) 忍俊不禁(jīn) B. 贮蓄(chǔ) 怂恿(sǒng) 蜷伏(quán) 随声附和(hé) C. 酬和(hé) 追溯(sù) 稽首(qǐ) 铢两悉称(chēng) D. 粗犷(kuàng) 挫(chuō) 愧怍(zuò) 鲜为人知(xiǎn)",
         "answer": "A", "options": ["A. 倔强(jué) 迸溅(bèng) 称职(chèn) 忍俊不禁(jīn)", "B. 贮蓄(chǔ) 怂恿(sǒng) 蜷伏(quán) 随声附和(hé)", "C. 酬和(hé) 追溯(sù) 稽首(qǐ) 铢两悉称(chēng)", "D. 粗犷(kuàng) 挫(chuō) 愧怍(zuò) 鲜为人知(xiǎn)"]},
        {"question": "下列句子中，没有语病的一项是（ ）A. 能否保护好水资源，是关系到人类可持续发展的大事 B. 深圳地铁的快速发展，极大地缓解了市民的出行问题 C. 经过老师的反复讲解，终于使我明白了这道题的解法 D. 为了避免交通拥堵，交警部门建议市民错峰出行",
         "answer": "D", "options": ["A. 能否保护好水资源，是关系到人类可持续发展的大事", "B. 深圳地铁的快速发展，极大地缓解了市民的出行问题", "C. 经过老师的反复讲解，终于使我明白了这道题的解法", "D. 为了避免交通拥堵，交警部门建议市民错峰出行"]},
        {"question": "下列文学常识搭配正确的一项是（ ）A. 《岳阳楼记》—范仲淹—南宋 B. 《醉翁亭记》—欧阳修—北宋 C. 《出师表》—诸葛亮—西晋 D. 《桃花源记》—陶渊明—东汉",
         "answer": "B", "options": ["A. 《岳阳楼记》—范仲淹—南宋", "B. 《醉翁亭记》—欧阳修—北宋", "C. 《出师表》—诸葛亮—西晋", "D. 《桃花源记》—陶渊明—东汉"]},
        {"question": "下列对诗句的理解，不正确的一项是（ ）A. '会当凌绝顶，一览众山小'表达诗人登高望远的豪情 B. '海内存知己，天涯若比邻'表达诗人与友人分别时的悲伤 C. '长风破浪会有时，直挂云帆济沧海'表达诗人对未来的信心 D. '但愿人长久，千里共婵娟'表达对亲人的思念和美好祝愿",
         "answer": "B", "options": ["A. '会当凌绝顶，一览众山小'表达诗人登高望远的豪情", "B. '海内存知己，天涯若比邻'表达诗人与友人分别时的悲伤", "C. '长风破浪会有时，直挂云帆济沧海'表达诗人对未来的信心", "D. '但愿人长久，千里共婵娟'表达对亲人的思念和美好祝愿"]},
        {"question": "下列各组句子中，加点词意义相同的一项是（ ）A. 以其境过清/可以为师矣 B. 温故而知新/故虽有名马 C. 学而时习之/时过境迁 D. 择其善者而从之/从善如流",
         "answer": "D", "options": ["A. 以其境过清/可以为师矣", "B. 温故而知新/故虽有名马", "C. 学而时习之/时过境迁", "D. 择其善者而从之/从善如流"]},
    ],
    "english": [
        {"question": "I don't have enough money to buy a car means I can't _____ a car. A. rent B. borrow C. afford",
         "answer": "C", "options": ["A. rent", "B. borrow", "C. afford"]},
        {"question": "—Hi, Bob! What's going on over there?—Oh, Tom and Dick are playing chess. The phrase 'going on' means _____. A. appearing B. happening C. working",
         "answer": "B", "options": ["A. appearing", "B. happening", "C. working"]},
        {"question": "In Shenzhen the city center will be _____ to all the districts by metro in several years. A. closed to B. joined to C. added to",
         "answer": "B", "options": ["A. closed to", "B. joined to", "C. added to"]},
        {"question": "—Would you like _____ the Wutong Mountain tomorrow?—If my mother _____, I will go with you. A. climbing; will allow B. climbing; allows C. to climb; allows D. to climb; will allow",
         "answer": "C", "options": ["A. climbing; will allow", "B. climbing; allows", "C. to climb; allows", "D. to climb; will allow"]},
        {"question": "The dress looks so nice on you! It must be very expensive. —_____, it is only 100 yuan. A. In fact B. In addition C. In need",
         "answer": "A", "options": ["A. In fact", "B. In addition", "C. In need"]},
        {"question": "—We are going to hold a party to raise money for our club.—Sounds great! I will help you if I am _____. A. busy B. free C. pleased",
         "answer": "B", "options": ["A. busy", "B. free", "C. pleased"]},
        {"question": "—It sounds _____ that a truck hit two cars.—Luckily, _____ of three drivers was hurt. A. terribly; none B. terrible; none C. terrible; neither D. terribly; neither",
         "answer": "B", "options": ["A. terribly; none", "B. terrible; none", "C. terrible; neither", "D. terribly; neither"]},
        {"question": "—Have you heard from Sarah recently?—No. I lost touch with her two years ago. 'Heard from' means _____. A. written to B. got a letter from C. heard about",
         "answer": "B", "options": ["A. written to", "B. got a letter from", "C. heard about"]},
        {"question": "—I have difficulty in learning Chinese. Could you give me some help?—Sure. _____ you read, _____ you will be. A. The more; the better B. More; better C. The most; the best",
         "answer": "A", "options": ["A. The more; the better", "B. More; better", "C. The most; the best"]},
        {"question": "Most Chinese customers prefer to pay by Alipay or WeChat pay nowadays. —That's true. Life becomes more convenient. The word 'convenient' means _____. A. difficult B. easy C. boring",
         "answer": "B", "options": ["A. difficult", "B. easy", "C. boring"]},
        {"question": "—To lose weight, I have to be on a diet.—You'd better not _____, you should take exercise. A. give up B. put up C. take up",
         "answer": "A", "options": ["A. give up", "B. put up", "C. take up"]},
        {"question": "—I feel bad about all the mess.—_____! I will clean it up later. A. Don't worry B. Hurry up C. You're welcome",
         "answer": "A", "options": ["A. Don't worry", "B. Hurry up", "C. You're welcome"]},
        {"question": "—Can you guess _____?—I've no idea about it. A. why was he late B. when shall we have the sports meeting C. where was she born D. how much he paid for the camera",
         "answer": "D", "options": ["A. why was he late", "B. when shall we have the sports meeting", "C. where was she born", "D. how much he paid for the camera"]},
        {"question": "—Anne, the information you gave me is really _____. Thank you very much.—Not at all. I am happy I can help. A. useless B. helpful C. harmful",
         "answer": "B", "options": ["A. useless", "B. helpful", "C. harmful"]},
    ],
    "chinese": [
        {"question": "下列词语中，没有错别字的一项是（ ）A. 迫不及待 B. 走头无路 C. 一诺千斤 D. 谈笑风声",
         "answer": "A", "options": ["A. 迫不及待", "B. 走头无路", "C. 一诺千斤", "D. 谈笑风声"]},
        {"question": "下列句子中，加点成语使用正确的一项是（ ）A. 他平时学习不认真，考试时却胸有成竹 B. 这两篇文章虽然题材相同，但风格大相径庭 C. 看到有人落水，他袖手旁观 D. 他在演讲比赛中夸夸其谈，获得了一等奖",
         "answer": "B", "options": ["A. 他平时学习不认真，考试时却胸有成竹", "B. 这两篇文章虽然题材相同，但风格大相径庭", "C. 看到有人落水，他袖手旁观", "D. 他在演讲比赛中夸夸其谈，获得了一等奖"]},
        {"question": "下列句子中没有语病的一项是（ ）A. 通过这次活动，使我们开阔了眼界 B. 深圳的夏天是一个美丽的城市 C. 能否刻苦学习是取得好成绩的关键 D. 我们要养成认真检查作业的习惯",
         "answer": "D", "options": ["A. 通过这次活动，使我们开阔了眼界", "B. 深圳的夏天是一个美丽的城市", "C. 能否刻苦学习是取得好成绩的关键", "D. 我们要养成认真检查作业的习惯"]},
        {"question": "下列句子排序最恰当的一项是：①所以，古人通过观测天象来判断季节②二十四节气是我国古代劳动人民智慧的结晶③这是中国古代订立的一种用来指导农事的补充历法④它反映了季节的变化，指导农事活动 A. ②④①③ B. ②③④① C. ①③②④ D. ④①②③",
         "answer": "B", "options": ["A. ②④①③", "B. ②③④①", "C. ①③②④", "D. ④①②③"]},
        {"question": "下列关于文学常识的表述，不正确的一项是（ ）A. 《诗经》是我国最早的一部诗歌总集 B. 《史记》是西汉司马迁所著 C. 《战国策》的作者是西汉刘向 D. 李白被称为'诗圣'",
         "answer": "D", "options": ["A. 《诗经》是我国最早的一部诗歌总集", "B. 《史记》是西汉司马迁所著", "C. 《战国策》的作者是西汉刘向", "D. 李白被称为'诗圣'"]},
        {"question": "下列句子中，修辞手法判断正确的一项是（ ）A. 月亮像一个大圆盘挂在天上——拟人 B. 鸟儿在枝头唱着欢快的歌——比喻 C. 飞流直下三千尺，疑是银河落九天——夸张 D. 教室里静得连一根针掉在地上都听得见——排比",
         "answer": "C", "options": ["A. 月亮像一个大圆盘挂在天上——拟人", "B. 鸟儿在枝头唱着欢快的歌——比喻", "C. 飞流直下三千尺，疑是银河落九天——夸张", "D. 教室里静得连一根针掉在地上都听得见——排比"]},
        {"question": "下列对文章的理解和分析，不正确的一项是（ ）A. 议论文的三要素是论点、论据、论证 B. 说明文的语言要求准确、严谨 C. 小说的情节一般包括开端、发展、高潮、结局 D. 散文必须要有完整的故事线索",
         "answer": "D", "options": ["A. 议论文的三要素是论点、论据、论证", "B. 说明文的语言要求准确、严谨", "C. 小说的情节一般包括开端、发展、高潮、结局", "D. 散文必须要有完整的故事线索"]},
        {"question": "下列诗句中，表达思乡之情的是（ ）A. 会当凌绝顶，一览众山小 B. 举头望明月，低头思故乡 C. 大漠孤烟直，长河落日圆 D. 春风得意马蹄疾，一日看尽长安花",
         "answer": "B", "options": ["A. 会当凌绝顶，一览众山小", "B. 举头望明月，低头思故乡", "C. 大漠孤烟直，长河落日圆", "D. 春风得意马蹄疾，一日看尽长安花"]},
        {"question": "下列关于名著阅读的表述，不正确的一项是（ ）A. 《西游记》中孙悟空大闹天宫体现反抗精神 B. 《水浒传》中宋江被称为'及时雨' C. 《骆驼祥子》的作者是老舍 D. 《红星照耀中国》是虚构小说",
         "answer": "D", "options": ["A. 《西游记》中孙悟空大闹天宫体现反抗精神", "B. 《水浒传》中宋江被称为'及时雨'", "C. 《骆驼祥子》的作者是老舍", "D. 《红星照耀中国》是虚构小说"]},
    ],
    "politics": [
        {"question": "2022年度全国最美家庭莫益娟夫妇，10年如一日照顾着没有血亲关系的孤寡老人，用实际行动教育孩子。他们的行为体现了（ ）A. 诚实守信 B. 勤俭节约 C. 乐于助人 D. 勇于创新",
         "answer": "C", "options": ["A. 诚实守信", "B. 勤俭节约", "C. 乐于助人", "D. 勇于创新"]},
        {"question": "青春如诗，岁月如歌。初中生活是丰富多彩的，三年的点点滴滴见证了我们的成长。因此，我们应该（ ）A. 激发潜能，不断超越自我 B. 顺其自然，得过且过 C. 只关注学习，不参加活动 D. 逃避困难，选择安逸",
         "answer": "A", "options": ["A. 激发潜能，不断超越自我", "B. 顺其自然，得过且过", "C. 只关注学习，不参加活动", "D. 逃避困难，选择安逸"]},
        {"question": "维护国家粮食安全是国家安全的重要内容。节约粮食是公民应尽的义务，从道德角度看，这是因为（ ）A. 法律要求节约粮食 B. 节约粮食是中华民族的传统美德 C. 不节约会被罚款 D. 节约粮食能增加农民收入",
         "answer": "B", "options": ["A. 法律要求节约粮食", "B. 节约粮食是中华民族的传统美德", "C. 不节约会被罚款", "D. 节约粮食能增加农民收入"]},
        {"question": "下列行为中，属于履行公民基本义务的是（ ）A. 依法纳税 B. 参加志愿者活动 C. 向灾区捐款 D. 参加学校社团",
         "answer": "A", "options": ["A. 依法纳税", "B. 参加志愿者活动", "C. 向灾区捐款", "D. 参加学校社团"]},
        {"question": "我国宪法规定，中华人民共和国的一切权力属于（ ）A. 公民 B. 人民 C. 政府 D. 全国人大",
         "answer": "B", "options": ["A. 公民", "B. 人民", "C. 政府", "D. 全国人大"]},
        {"question": "2021年全国成年国民阅读形式调查结果显示，随着网络的发展，人们的阅读方式选择不断丰富。这说明（ ）A. 纸质图书将被完全取代 B. 网络丰富生活，为文化传播搭建新平台 C. 网络阅读优于纸质阅读 D. 传统阅读已经没有价值",
         "answer": "B", "options": ["A. 纸质图书将被完全取代", "B. 网络丰富生活，为文化传播搭建新平台", "C. 网络阅读优于纸质阅读", "D. 传统阅读已经没有价值"]},
        {"question": "下列做法中，体现绿色发展理念的是（ ）A. 大量使用一次性餐具 B. 垃圾分类回收利用 C. 随意排放工业废水 D. 过度开发自然资源",
         "answer": "B", "options": ["A. 大量使用一次性餐具", "B. 垃圾分类回收利用", "C. 随意排放工业废水", "D. 过度开发自然资源"]},
        {"question": "我国根本政治制度是（ ）A. 民族区域自治制度 B. 基层群众自治制度 C. 人民代表大会制度 D. 多党合作制度",
         "answer": "C", "options": ["A. 民族区域自治制度", "B. 基层群众自治制度", "C. 人民代表大会制度", "D. 多党合作制度"]},
    ],
}


def main():
    # ── 1. 加载所有数据 ──
    train = json.load(open("data/v1.0/train.json", encoding="utf-8"))
    val = json.load(open("data/v1.0/val.json", encoding="utf-8"))
    all_data = train + val
    print(f"总数据: {len(all_data)} 条")

    # ── 2. 提取干净选择题 ──
    extracted = defaultdict(list)
    for q in all_data:
        if not is_clean_question(q):
            continue
        options = extract_options_from_question(q["question"])
        answer = extract_single_answer(q["answer"], q["question"])
        if options and answer:
            extracted[q["subject"]].append({
                "question": q["question"],
                "options": options,
                "answer": answer,
                "subject": q["subject"],
            })

    print("\n从训练数据提取:")
    for s in sorted(extracted):
        print(f"  {s}: {len(extracted[s])}")

    # ── 3. 去重 ──
    for s in extracted:
        seen = set()
        unique = []
        for item in extracted[s]:
            key = item["question"][:80]
            if key not in seen:
                seen.add(key)
                unique.append(item)
        extracted[s] = unique
        print(f"  {s} 去重后: {len(unique)}")

    # ── 4. 目标分配 ──
    TARGETS = {
        "math": 35, "physics": 30, "history": 30,
        "english": 30, "chinese": 30, "chemistry": 25,
        "politics": 20,
    }
    # 调整使总数=200
    total_target = sum(TARGETS.values())
    print(f"\n目标: {total_target} 题")

    # ── 5. 采样 ──
    benchmark = []
    qid = 1

    for subject in ["math", "physics", "history", "english", "chinese", "chemistry", "politics"]:
        target = TARGETS.get(subject, 20)
        pool = extracted.get(subject, [])

        if len(pool) < target:
            # 从补充题库中补充
            supplement = SUPPLEMENT.get(subject, [])
            needed = target - len(pool)
            supplement_sample = supplement[:needed]
            print(f"  {subject}: 提取{len(pool)} + 补充{len(supplement_sample)} = {len(pool)+len(supplement_sample)}")
            pool = pool + supplement_sample
        else:
            pool = random.sample(pool, target)
            print(f"  {subject}: 采样{len(pool)} (可用{len(extracted.get(subject, []))})")

        for item in pool:
            benchmark.append({
                "id": qid,
                "subject": subject,
                "question": item["question"],
                "options": item.get("options", extract_options_from_question(item["question"]) or []),
                "answer": item["answer"].strip().upper()[0] if item["answer"] else "?",
            })
            qid += 1

    # ── 6. 验证和过滤 ──
    valid = []
    issues = []
    for b in benchmark:
        ok = True
        if not b["answer"] or b["answer"] not in "ABCD":
            issues.append(f"  #{b['id']} [{b['subject']}] 答案格式异常: {b['answer']} — 已排除")
            ok = False
        if not b["options"] or len(b["options"]) < 2:
            issues.append(f"  #{b['id']} [{b['subject']}] 选项不足 — 已排除")
            ok = False
        option_letters = [o[0] for o in b["options"]]
        if b["answer"] not in option_letters:
            issues.append(f"  #{b['id']} [{b['subject']}] 答案{b['answer']}不在选项中{option_letters} — 已排除")
            ok = False
        if ok:
            valid.append(b)
    benchmark = valid

    # 重新编号
    for i, b in enumerate(benchmark):
        b["id"] = i + 1

    print(f"\n总计: {len(benchmark)} 题 (排除{len(issues)}个无效)")
    if issues:
        for issue in issues[:10]:
            print(issue)
    else:
        print("✅ 全部验证通过")

    # ── 7. 保存 ──
    os.makedirs("benchmark", exist_ok=True)
    output_path = "benchmark/test_set_v0.1.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(benchmark, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 已保存: {output_path} ({len(benchmark)} 题)")

    # 学科分布饼图数据
    print("\n学科分布:")
    for s in sorted(TARGETS):
        count = sum(1 for b in benchmark if b["subject"] == s)
        bar = "█" * (count // 2)
        print(f"  {s:10s} {count:3d} {bar}")


if __name__ == "__main__":
    main()
