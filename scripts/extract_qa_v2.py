"""
V2: 多策略QA提取。处理三种格式：
  A. 【答案】逐题标记 (解析卷，数理化语文历史道法)
  B. ## **参考答案** 汇总格式 (英语)
  C. 参考答案表格格式 (旧版真题及答案)
"""
import json, re, random, sys
from pathlib import Path
from collections import defaultdict

EXAM_DIR = Path("d:/SZZKLLM/exam-papers")
OUTPUT_DIR = Path("d:/SZZKLLM/data/v1.0")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 工具函数
# ============================================================
def clean(text: str) -> str:
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'<div[^>]*>.*?</div>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\*', '', text)
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'[\t ]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

SUBJECT_MAP = {"语文":"chinese","数学":"math","英语":"english",
    "物理":"physics","化学":"chemistry","道法":"politics","历史":"history"}

def get_subject(filepath: Path) -> str:
    for cn, en in SUBJECT_MAP.items():
        if cn in filepath.parent.name: return en
    return "unknown"

def is_valid_qa(q: str, a: str) -> bool:
    """过滤无效QA对"""
    if len(q) < 12 or len(a) < 1: return False
    # 跳过纯图片题（问题基本是空白选项）
    pure = re.sub(r'[A-D][\.\．\、\)]\s*', '', q)
    pure = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]', '', pure)
    pure = re.sub(r'\s+', '', pure)
    if len(pure) < 15: return False
    # 跳过全是表格/图片的问题
    if pure.count('|') > len(pure) * 0.3: return False
    return True

# ============================================================
# 策略 A: 【答案】逐题标记
# ============================================================
def extract_strategy_a(filepath: Path) -> list[dict]:
    """处理有【答案】标记的文件"""
    with open(filepath, encoding="utf-8") as f:
        text = f.read()
    lines = text.split('\n')

    subject = get_subject(filepath)
    questions = []
    buf_q, buf_a = [], []
    in_answer = False
    active = False

    q_pat = re.compile(r'^(\d{1,3})[\.\．\)、]\s*')
    skip_pat = re.compile(r'^(答题前|全卷|作答|考试|说明|本大题|要求|条理|信中|4-|60-|要求)')

    for i, line in enumerate(lines):
        s = line.strip()

        if s.startswith('【答案】'):
            # 保存上一题
            if active and buf_q:
                q_text = clean(''.join(buf_q))
                a_text = clean(' '.join(buf_a))
                if is_valid_qa(q_text, a_text):
                    questions.append({"question": q_text, "answer": a_text, "subject": subject})
            buf_a = [s[4:].strip()] if s[4:].strip() else []
            in_answer = True; active = True
            continue

        if s.startswith('【解析】') or s.startswith('【分析】') or s.startswith('【点评】') or s.startswith('【详解】'):
            if active and buf_q:
                q_text = clean(''.join(buf_q))
                a_text = clean(' '.join(buf_a))
                if is_valid_qa(q_text, a_text):
                    questions.append({"question": q_text, "answer": a_text, "subject": subject})
            buf_q, buf_a = [], []
            in_answer = False; active = False
            continue

        m = q_pat.match(s)
        if m and not skip_pat.match(s):
            if active and buf_q:
                q_text = clean(''.join(buf_q))
                a_text = clean(' '.join(buf_a))
                if is_valid_qa(q_text, a_text):
                    questions.append({"question": q_text, "answer": a_text, "subject": subject})
            buf_q = [line]; buf_a = []
            in_answer = False; active = True
            continue

        if active:
            if in_answer: buf_a.append(line)
            else: buf_q.append(line)

    # 最后一题
    if active and buf_q:
        q_text = clean(''.join(buf_q))
        a_text = clean(' '.join(buf_a))
        if is_valid_qa(q_text, a_text):
            questions.append({"question": q_text, "answer": a_text, "subject": subject})

    return questions

# ============================================================
# 策略 B: ## **参考答案** 汇总 (英语)
# ============================================================
def extract_strategy_b(filepath: Path) -> list[dict]:
    """处理英语试卷：问题在上半部分，## **参考答案** 下半部分列出答案"""
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    if '参考答案' not in text and '参考答案与试题解析' not in text:
        return []

    subject = get_subject(filepath)
    lines = text.split('\n')

    # 找到参考答案分界线
    split_idx = None
    for i, line in enumerate(lines):
        if re.match(r'^##\s*\*?\*?参考答', line.strip()):
            split_idx = i
            break

    if split_idx is None:
        return []

    question_lines = lines[:split_idx]
    answer_lines = lines[split_idx:]

    # 解析答案部分 — 提取答案映射 {题号: 答案}
    answer_map = {}
    # 模式: "数字.答案" 或 "数字．答案" 或 "数字 答案"
    for line in answer_lines[1:]:  # 跳过标题行
        s = line.strip()
        # 匹配 "1.D" "1. D" "1  D" 等
        ms = re.findall(r'(\d{1,3})\s*[\.\．\、]?\s*([A-Da-d][\.\．\、\)\s]|[一-鿿]+[^\d]*)', s)
        for m in ms:
            num, ans = int(m[0]), m[1].strip().rstrip('.')
            ans = re.sub(r'\s+', ' ', ans)
            answer_map[num] = ans

    # 从问题部分，找独立的问题行
    # 英语题格式: "1. ---What is ...?" 或 "1. Which ...?"
    q_pat = re.compile(r'^(\d{1,3})[\.\．\)、]\s*(.*)')
    all_q_nums = []
    all_q_texts = {}

    # 找所有带编号的行
    for i, line in enumerate(question_lines):
        s = line.strip()
        m = q_pat.match(s)
        if not m: continue
        num = int(m.group(1))
        rest = m.group(2).strip()
        # 跳过明显的非问题行
        if re.match(r'^(答题|全卷|作答|考试|说明|要求|条理|信中|注意|参考)', rest):
            continue
        if re.match(r'^(A[\.\．\、\)]|B[\.\．\、\)])', rest):
            continue
        all_q_nums.append(num)
        # 收集问题文本（包含后续行直到下一个题号或空行过多）
        q_lines = [line]
        j = i + 1
        while j < len(question_lines):
            nxt = question_lines[j].strip()
            if q_pat.match(nxt): break
            if nxt.startswith('##') or nxt.startswith('---'): break
            if nxt.startswith('【'): break
            q_lines.append(question_lines[j])
            j += 1
        all_q_texts[num] = clean(''.join(q_lines))

    # 配对
    questions = []
    for num in all_q_nums:
        q = all_q_texts.get(num, '')
        a = answer_map.get(num, '')
        if is_valid_qa(q, a):
            questions.append({"question": q, "answer": a, "subject": subject})

    return questions

# ============================================================
# 策略 C: 参考答案表格 (旧版数理化)
# ============================================================
def extract_strategy_c(filepath: Path) -> list[dict]:
    """处理旧版真题及答案：参考答案在尾部表格中"""
    with open(filepath, encoding="utf-8") as f:
        text = f.read()

    if '参考答案' not in text:
        return []

    subject = get_subject(filepath)
    lines = text.split('\n')

    # 找答案分界线
    ref_idx = None
    for i, line in enumerate(lines):
        if '参考答案' in line:
            ref_idx = i
            break

    if ref_idx is None:
        return []

    # 从参考答案区域提取答案map
    answer_map = {}
    # 匹配表格行中的答案: "| ... | ... | A | B | C | ..."
    table_lines = []
    for i in range(ref_idx, min(ref_idx + 30, len(lines))):
        s = lines[i].strip()
        if s.startswith('|'):
            table_lines.append(s)

    answers_in_order = []
    for tl in table_lines:
        cells = [c.strip() for c in tl.split('|') if c.strip()]
        for cell in cells:
            cell = re.sub(r'\*\*', '', cell).strip()
            if re.match(r'^[A-Da-d]$', cell):
                answers_in_order.append(cell.upper())
            elif re.match(r'^[\d]+$', cell) and len(cell) <= 2:
                answers_in_order.append(cell)

    # 从问题部分提取问题文本
    q_lines = lines[:ref_idx]
    q_pat = re.compile(r'^(\d{1,3})[\.\．\)、]\s*')
    questions = []
    question_texts = {}

    in_table = False
    for i, line in enumerate(q_lines):
        s = line.strip()
        if s.startswith('|'): in_table = True; continue
        if not s: in_table = False; continue
        if in_table: continue

        m = q_pat.match(s)
        if not m: continue
        num = int(m.group(1))
        rest = s[m.end():].strip()
        if re.match(r'^(答题|全卷|作答|考试|说明|要求|条理|信中|注意|参考)', rest):
            continue
        if re.match(r'^(A[\.\．\、\)]|B[\.\．\、\)])', rest):
            continue

        # 收集问题文本
        q_text_lines = [line]
        j = i + 1
        while j < len(q_lines):
            nxt = q_lines[j].strip()
            if q_pat.match(nxt): break
            if nxt.startswith('##') or nxt.startswith('---'): break
            if nxt.startswith('【'): break
            q_text_lines.append(q_lines[j])
            j += 1
        question_texts[num] = clean(''.join(q_text_lines))

    # 配对: 选择题答案按顺序
    for idx, (num, q) in enumerate(sorted(question_texts.items())):
        a = answers_in_order[idx] if idx < len(answers_in_order) else ""
        if is_valid_qa(q, a):
            questions.append({"question": q, "answer": a, "subject": subject})

    return questions


# ============================================================
# 主流程
# ============================================================
def main():
    all_qa = []
    stats_by_subj = defaultdict(int)
    stats_by_strategy = defaultdict(int)

    files = list(EXAM_DIR.rglob("*.md"))
    # 只看有答案的文件
    answer_files = [f for f in files if '解析' in f.name or '真题及答案' in f.name]

    for fp in sorted(answer_files):
        qs = []
        # 检查文件中有哪种答案标记
        with open(fp, encoding="utf-8") as f:
            content = f.read()

        has_per_q_answer = '【答案】' in content
        has_ref_answer = '参考答案' in content

        if has_per_q_answer:
            qs = extract_strategy_a(fp)
            if qs: stats_by_strategy['A(逐题答案)'] += 1
        elif has_ref_answer:
            # 先试策略B(英语格式), 如果结果少则试策略C
            qs_b = extract_strategy_b(fp)
            qs_c = extract_strategy_c(fp)
            qs = qs_b if len(qs_b) >= len(qs_c) else qs_c
            if qs: stats_by_strategy['B/C(参考答案)'] += 1

        for q in qs:
            all_qa.append(q)
            stats_by_subj[q["subject"]] += 1

    print(f"=== 提取结果 ===")
    print(f"处理文件: {stats_by_strategy}")
    print(f"总题数: {len(all_qa)}")
    for s, c in sorted(stats_by_subj.items()):
        print(f"  {s}: {c}")

    if len(all_qa) == 0:
        print("错误：未提取到任何问答对！")
        return

    # 去重
    seen = set()
    unique = []
    for q in all_qa:
        key = q["question"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(q)
    print(f"\n去重后: {len(unique)} 题")

    # 随机抽样
    random.seed(42)
    target = min(2000, len(unique))
    sampled = random.sample(unique, target) if len(unique) > target else unique

    # 9:1 划分
    random.shuffle(sampled)
    split = int(len(sampled) * 0.9)
    train, val = sampled[:split], sampled[split:]

    # 精简：只保留 question, answer, subject
    for item in train + val:
        item.pop("source", None)

    with open(OUTPUT_DIR / "train.json", "w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False, indent=2)
    with open(OUTPUT_DIR / "val.json", "w", encoding="utf-8") as f:
        json.dump(val, f, ensure_ascii=False, indent=2)

    print(f"\n=== 输出 ===")
    print(f"训练集: {len(train)} 题 → data/v1.0/train.json")
    print(f"验证集: {len(val)} 题 → data/v1.0/val.json")

    # 学科分布
    dist = defaultdict(int)
    for q in train: dist[q["subject"]] += 1
    print(f"\n训练集学科分布:")
    for s, c in sorted(dist.items()): print(f"  {s}: {c}")

if __name__ == "__main__":
    main()
