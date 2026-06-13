"""
V3: 简化通用提取。核心思路：
- 以【答案】或「答案：」为锚点，向前找问题文本，向后取答案文本
- 不再区分学科和试卷格式
"""
import json, re, random
from pathlib import Path
from collections import defaultdict

EXAM_DIR = Path("d:/SZZKLLM/exam-papers")
OUTPUT_DIR = Path("d:/SZZKLLM/data/v1.0")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SUBJECT_MAP = {"语文":"chinese","数学":"math","英语":"english",
    "物理":"physics","化学":"chemistry","道法":"politics","历史":"history"}

def clean(text: str) -> str:
    text = re.sub(r'!\[.*?\]\(.*?\)', ' ', text)
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'<div[^>]*>.*?</div>', ' ', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'[\t ]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def is_good(q: str, a: str) -> bool:
    """宽松过滤 — 只跳过明显无效的"""
    if len(q) < 5 or len(a) < 1:
        return False
    # 去除选项标记后看纯文本长度
    pure = re.sub(r'[A-D][\.\．\、\)]\s*', '', q)
    pure = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]', '', pure)
    pure = re.sub(r'\s+', '', pure)
    pure = re.sub(r'[_\-\|]+', '', pure)
    if len(pure) < 6:
        return False
    return True

def extract_all(filepath: Path) -> list[dict]:
    """通用提取：找所有答案标记，向前回溯找问题"""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    lines = content.split('\n')

    # 判断学科
    subject = "unknown"
    for cn, en in SUBJECT_MAP.items():
        if cn in filepath.parent.name:
            subject = en
            break

    # 找所有答案行: 【答案】, 答案：, 【解答】, etc.
    ans_pattern = re.compile(r'(?:【答案】|【解答】|答案[：:])')
    ans_indices = [i for i, line in enumerate(lines) if ans_pattern.search(line)]

    if not ans_indices:
        return []

    questions = []
    q_num_pat = re.compile(r'^(\d{1,3})[\.\．\)、]\s*')

    for ans_idx in ans_indices:
        ans_line = lines[ans_idx].strip()
        # 提取答案文本
        ans_text = ans_pattern.sub('', ans_line).strip()

        # 收集答案后续行（直到下一个答案标记或解析标记）
        ans_extra = []
        j = ans_idx + 1
        while j < len(lines) and j < ans_idx + 8:
            s = lines[j].strip()
            if ans_pattern.search(s): break
            if s.startswith('【解析】') or s.startswith('【分析】') or s.startswith('【点评】'):
                break
            if q_num_pat.match(s): break
            if s: ans_extra.append(s)
            j += 1
        if ans_extra:
            ans_text = ans_text + ' ' + ' '.join(ans_extra)
        ans_text = clean(ans_text)
        if len(ans_text) > 400:
            ans_text = ans_text[:400]

        # 向前回溯找问题文本
        q_lines = []
        i = ans_idx - 1
        # 往上找到问题开始
        found_q_start = False
        while i >= 0 and i >= ans_idx - 30:
            s = lines[i].strip()
            # 检查是否遇到上一个答案或解析
            if ans_pattern.search(s) or s.startswith('【解析】') or s.startswith('【分析】'):
                break
            # 检查是否是问题编号开头
            if q_num_pat.match(s):
                q_lines.insert(0, s)
                found_q_start = True
                # 继续往上收集看是否有更多上下文
                i -= 1
                while i >= 0 and i >= ans_idx - 35:
                    ps = lines[i].strip()
                    if q_num_pat.match(ps) or ans_pattern.search(ps):
                        break
                    if ps.startswith('【'): break
                    if ps.startswith('##') or ps.startswith('---'): break
                    q_lines.insert(0, ps)
                    i -= 1
                break
            # 收集非空行
            if s and not s.startswith('##') and not s.startswith('---') \
               and not s.startswith('<div') and not s.startswith('|'):
                q_lines.insert(0, s)
            i -= 1

        if not found_q_start:
            continue

        q_text = clean(''.join(q_lines))
        if is_good(q_text, ans_text):
            questions.append({
                "question": q_text,
                "answer": ans_text,
                "subject": subject
            })

    return questions


def main():
    all_qa = []
    stats = defaultdict(int)

    # 处理所有有答案标记的文件
    answer_files = []
    for fp in sorted(EXAM_DIR.rglob("*.md")):
        fname = fp.name
        if "解析" in fname or "真题及答案" in fname:
            answer_files.append(fp)

    for fp in answer_files:
        # 检查是否有可提取的答案标记
        with open(fp, encoding="utf-8") as f:
            content = f.read()
        if '答案' not in content:
            continue

        qs = extract_all(fp)
        for q in qs:
            all_qa.append(q)
            stats[q["subject"]] += 1

    print(f"=== 提取结果 ===")
    print(f"总题数: {len(all_qa)}")
    for s, c in sorted(stats.items()):
        print(f"  {s}: {c}")

    if not all_qa:
        print("未提取到任何数据！")
        return

    # 去重
    seen = set()
    unique = []
    for q in all_qa:
        key = q["question"][:80]
        if key not in seen:
            seen.add(key)
            unique.append(q)
    print(f"\n去重后: {len(unique)}")

    # 随机抽样
    random.seed(42)
    target = min(2000, len(unique))
    sampled = random.sample(unique, target) if len(unique) > target else unique

    # 9:1 划分
    random.shuffle(sampled)
    split = int(len(sampled) * 0.9)
    train, val = sampled[:split], sampled[split:]

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
