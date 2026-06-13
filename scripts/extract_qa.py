"""
从试卷 markdown 文件中提取问答对，用于 SFT 训练。
只处理「解析卷/真题及答案」文件（包含【答案】标记）。
"""
import json
import re
import random
from pathlib import Path

EXAM_DIR = Path("d:/SZZKLLM/exam-papers")
OUTPUT_DIR = Path("d:/SZZKLLM/data/v1.0")

# 学科映射
SUBJECT_MAP = {
    "语文": "chinese", "数学": "math", "英语": "english",
    "物理": "physics", "化学": "chemistry", "道法": "politics", "历史": "history"
}

def clean_text(text: str) -> str:
    """清洗文本：去除 markdown 格式、多余空白"""
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)  # 移除图片
    text = re.sub(r'\*\*', '', text)              # 移除加粗
    text = re.sub(r'<div[^>]*>.*?</div>', '', text, flags=re.DOTALL)
    text = re.sub(r'<sup>.*?</sup>', '', text)
    text = re.sub(r'<u>', '', text)
    text = re.sub(r'</u>', '', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\*', '', text)
    text = re.sub(r'_{2,}', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{3,}', '  ', text)
    return text.strip()

def extract_from_file(filepath: Path) -> list[dict]:
    """从单个 markdown 文件提取所有问答对"""
    # 只处理有答案的文件（解析卷 或 真题及答案）
    fname = filepath.name
    if not (("解析" in fname or "真题及答案" in fname) and filepath.suffix == ".md"):
        return []

    # 判断学科
    subject = "unknown"
    for cn, en in SUBJECT_MAP.items():
        if cn in filepath.parent.name:
            subject = en
            break

    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    questions = []
    current_q_lines = []
    current_answer_lines = []
    in_answer = False
    question_started = False
    q_start_line = -1

    # 正则：以数字开头的问题行（1.  或 1． 或 1、 等）
    q_pattern = re.compile(r'^(\d{1,3})[\.\．\)、]\s*(.*)')
    # 避免把年份、分数等当问题
    skip_pattern = re.compile(r'^(答题前|全卷|作答|考试|说明|本大题)')

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 检测答案标记
        if stripped.startswith('【答案】'):
            in_answer = True
            answer_text = stripped[4:].strip()
            if answer_text:
                current_answer_lines.append(answer_text)
            continue

        # 检测解析标记 → 结束当前QA
        if stripped.startswith('【解析】') or stripped.startswith('【分析】'):
            if question_started and current_q_lines:
                q_text = clean_text(''.join(current_q_lines))
                a_text = clean_text(' '.join(current_answer_lines))
                if len(q_text) > 10 and len(a_text) > 0:
                    questions.append({
                        "question": q_text,
                        "answer": a_text,
                        "subject": subject,
                        "source": f"{filepath.parent.name}/{filepath.name}"
                    })
            current_q_lines = []
            current_answer_lines = []
            in_answer = False
            question_started = False
            continue

        # 检测新问题开始
        m = q_pattern.match(stripped)
        if m and not skip_pattern.match(stripped):
            q_num = int(m.group(1))
            # 保存上一个问题
            if question_started and current_q_lines:
                q_text = clean_text(''.join(current_q_lines))
                a_text = clean_text(' '.join(current_answer_lines))
                if len(q_text) > 10 and len(a_text) > 0:
                    questions.append({
                        "question": q_text,
                        "answer": a_text,
                        "subject": subject,
                        "source": f"{filepath.parent.name}/{filepath.name}"
                    })

            # 开始新问题
            current_q_lines = [line]
            current_answer_lines = []
            in_answer = False
            question_started = True
            q_start_line = i
            continue

        # 累积当前问题的行
        if question_started:
            if not in_answer:
                current_q_lines.append(line)
            else:
                current_answer_lines.append(line)

    # 处理最后一个问题
    if question_started and current_q_lines:
        q_text = clean_text(''.join(current_q_lines))
        a_text = clean_text(' '.join(current_answer_lines))
        if len(q_text) > 10 and len(a_text) > 0:
            questions.append({
                "question": q_text,
                "answer": a_text,
                "subject": subject,
                "source": f"{filepath.parent.name}/{filepath.name}"
            })

    return questions

def has_too_many_images(q: dict) -> bool:
    """过滤图片过多的问题（数学几何题等）"""
    # 问题中全是空白选项且无实质文本
    text = q["question"]
    # 去除选项标记后的纯文本
    pure = re.sub(r'[A-D][\.\．\、\)]\s*', '', text)
    pure = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]', '', pure)
    pure = pure.strip()
    # 纯文本太短(<30字)，说明问题主要靠图片
    if len(pure) < 30:
        return True
    return False

def main():
    all_questions = []
    stats = {}

    for md_file in sorted(EXAM_DIR.rglob("*.md")):
        qs = extract_from_file(md_file)
        for q in qs:
            if not has_too_many_images(q):
                # 截断过长的答案
                if len(q["answer"]) > 500:
                    q["answer"] = q["answer"][:500] + "..."
                all_questions.append(q)

        if qs:
            subj = qs[0]["subject"] if qs else "unknown"
            stats[subj] = stats.get(subj, 0) + len(qs)

    print(f"=== 提取统计 ===")
    for subj, count in sorted(stats.items()):
        print(f"  {subj}: {count} 题")

    # 过滤后
    after_filter = len(all_questions)
    print(f"\n过滤图片题后: {after_filter} 题")

    # 随机抽取2000题
    if len(all_questions) < 2000:
        print(f"\n⚠ 总题数不足2000，使用全部 {len(all_questions)} 题")
        sampled = all_questions
    else:
        random.seed(42)
        sampled = random.sample(all_questions, 2000)

    # 按学科分布
    subj_dist = {}
    for q in sampled:
        s = q["subject"]
        subj_dist[s] = subj_dist.get(s, 0) + 1
    print(f"\n=== 抽样分布 ===")
    for s, c in sorted(subj_dist.items()):
        print(f"  {s}: {c} 题")

    # 划分训练/验证集 (9:1)
    random.seed(42)
    random.shuffle(sampled)
    split_idx = int(len(sampled) * 0.9)
    train = sampled[:split_idx]
    val = sampled[split_idx:]

    # 移除 source 字段，保留核心字段
    for q in train:
        del q["source"]
    for q in val:
        del q["source"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_DIR / "train.json", "w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_DIR / "val.json", "w", encoding="utf-8") as f:
        json.dump(val, f, ensure_ascii=False, indent=2)

    print(f"\n=== 输出 ===")
    print(f"  训练集: {len(train)} 题 → data/v1.0/train.json")
    print(f"  验证集: {len(val)} 题 → data/v1.0/val.json")

if __name__ == "__main__":
    main()
