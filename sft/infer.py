"""
推理脚本 — 加载训练好的模型，交互式问答 / Benchmark 评测
用法:
  python sft/infer.py                          # 默认加载 models/v1.0/final，交互模式
  python sft/infer.py --model models/v1.0/final
  python sft/infer.py --benchmark              # 跑验证集评测
  python sft/infer.py --question "你的问题"    # 单次问答
"""
import argparse, json, re, sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


SYSTEM_PROMPT = "你是一个专业的中学学科答疑助手，请用简洁准确的语言回答问题。"


def load_model(model_path: str):
    """加载训练好的模型，自动检测 GPU/CPU"""
    print(f"Loading model from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  Device: {device}")

    load_kwargs = {"trust_remote_code": True}
    if device == "cuda":
        load_kwargs["torch_dtype"] = torch.bfloat16
        load_kwargs["device_map"] = "auto"
    else:
        # CPU: 必须用 float32（bf16 在 CPU 上不收敛或报错）
        load_kwargs["dtype"] = torch.float32
        load_kwargs["device_map"] = "cpu"

    model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
    model.eval()
    print(f"  Model loaded on {device}")
    return model, tokenizer, device


def generate(
    model, tokenizer, question: str,
    max_new_tokens: int = 256,
    do_sample: bool = False,
    temperature: float = 0.1,
    device: str = "cpu"
) -> str:
    """单次推理"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt")

    # 确保 inputs 在正确的设备上
    if device == "cuda":
        inputs = {k: v.to("cuda") for k, v in inputs.items()}

    # <|im_end|> token ID = 151645 (Qwen2.5), eos = 151643 = <|endoftext|>
    stop_ids = [tokenizer.eos_token_id, 151645]

    gen_kwargs = {
        "max_new_tokens": max_new_tokens,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": stop_ids,
        "do_sample": do_sample,
    }
    if do_sample:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["top_p"] = 0.95

    with torch.no_grad():
        outputs = model.generate(**inputs, **gen_kwargs)

    # 只取新生成的部分
    response = tokenizer.decode(
        outputs[0][len(inputs["input_ids"][0]):],
        skip_special_tokens=True,
    )
    return response.strip()


def interactive(model, tokenizer, device: str):
    """交互式问答"""
    print("\n" + "=" * 60)
    print("Interactive mode — Type 'quit' to exit, 'sample' to toggle sampling")
    print(f"Device: {device}")
    print("=" * 60)

    use_sampling = True
    while True:
        try:
            q = input("\n[Q] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("quit", "exit", "q"):
            break
        if q.lower() == "sample":
            use_sampling = not use_sampling
            print(f"  Sampling {'ON' if use_sampling else 'OFF'} (greedy)")
            continue
        if not q:
            continue

        answer = generate(model, tokenizer, q, do_sample=use_sampling, device=device)
        print(f"[A] {answer}")


def is_choice_question(question: str) -> bool:
    """判断是否为选择题（含 A/B/C/D 选项）"""
    return bool(re.search(r"[（(]\s*[A-D]\s*[）)]", question))


def extract_choice_answer(pred: str) -> str | None:
    """从模型输出中提取选项字母"""
    # 匹配常见模式：A、选A、(A)、A.
    match = re.search(r"(?:选|答案|选择)?[（(]?\s*([A-D])\s*[）).]?", pred, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    # 如果输出只是单个大写字母
    if len(pred.strip()) <= 2 and pred.strip().upper() in "ABCD":
        return pred.strip().upper()
    return None


def match_answer(pred: str, true_answer: str, question: str = "") -> bool:
    """判断预测是否正确。

    规则：
    1. 选择题：优先按选项字母匹配；不匹配时回退到包含匹配
    2. 其他题：核心关键词包含匹配（忽略标点和空格）
    """
    pred_clean = pred.strip()
    true_clean = true_answer.strip()

    # 选择题：精确匹配选项字母
    if is_choice_question(question):
        pred_option = extract_choice_answer(pred_clean)
        true_option = extract_choice_answer(true_clean)
        if pred_option and true_option:
            return pred_option == true_option

    # 简答题/填空题：关键词包含（双向）或选项字母匹配
    pred_option = extract_choice_answer(pred_clean)
    true_option = extract_choice_answer(true_clean)
    if pred_option and true_option:
        return pred_option == true_option

    # 标准化后双向包含
    def norm(s: str) -> str:
        return re.sub(r"\s+", "", s).lower()
    p = norm(pred_clean)
    t = norm(true_clean)
    return t in p or p in t


def benchmark(model, tokenizer, val_path: str = "data/v1.0/val.json", device: str = "cpu"):
    """在验证集上跑推理评测"""
    with open(val_path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"\nBenchmark on {len(data)} validation samples...")
    print(f"Device: {device}, decoding: greedy (do_sample=False)")
    correct = 0
    total = len(data)

    for i, item in enumerate(data):
        question = item["question"]
        true_answer = item["answer"].strip()

        # Benchmark 用贪婪解码确保结果稳定
        pred = generate(
            model, tokenizer, question,
            max_new_tokens=128,
            do_sample=False,
            device=device,
        ).strip()

        is_correct = match_answer(pred, true_answer, question)

        if i < 5:  # 打印前 5 个样例
            print(f"\n--- Sample {i+1}/{total} ---")
            print(f"  Q: {question[:120]}...")
            print(f"  True: {true_answer[:80]}")
            print(f"  Pred: {pred[:80]}")
            print(f"  {'OK' if is_correct else 'WRONG'}")

        if is_correct:
            correct += 1

    acc = correct / total * 100
    print(f"\n{'='*50}")
    print(f"Benchmark Result: {correct}/{total} = {acc:.1f}%")
    return acc


def main():
    parser = argparse.ArgumentParser(description="模型推理脚本")
    parser.add_argument("--model", default="models/v1.0/final", help="模型路径")
    parser.add_argument("--benchmark", action="store_true", help="跑验证集评测")
    parser.add_argument("--question", type=str, help="单次问答")
    parser.add_argument("--val_data", default="data/v1.0/val.json", help="验证集路径")
    args = parser.parse_args()

    model, tokenizer, device = load_model(args.model)

    if args.question:
        answer = generate(model, tokenizer, args.question, do_sample=False, device=device)
        print(f"\nQ: {args.question}")
        print(f"A: {answer}")
    elif args.benchmark:
        benchmark(model, tokenizer, val_path=args.val_data, device=device)
    else:
        interactive(model, tokenizer, device=device)


if __name__ == "__main__":
    main()
