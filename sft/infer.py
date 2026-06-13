"""
推理脚本 — 加载训练好的模型，交互式问答
用法:
  python sft/infer.py                          # 默认加载 models/v1.0/final
  python sft/infer.py --model models/v1.0/final
  python sft/infer.py --benchmark              # 跑 benchmark 评测
"""
import argparse, json, sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


SYSTEM_PROMPT = "你是一个专业的中学学科答疑助手，请用简洁准确的语言回答问题。"

def load_model(model_path: str):
    """加载训练好的模型"""
    print(f"Loading model from {model_path}...")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    # Qwen2.5 自带 chat_template，无需覆盖

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        trust_remote_code=True,
        dtype=torch.float32,
    )
    model.eval()
    print(f"  Model loaded. Device: {'CUDA' if torch.cuda.is_available() else 'CPU'}")
    return model, tokenizer


def generate(model, tokenizer, question: str, max_new_tokens: int = 256) -> str:
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

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,        # 低温度 = 更确定性的回答
            top_p=0.95,
            do_sample=True,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    # 只取新生成的部分
    response = tokenizer.decode(outputs[0][len(inputs.input_ids[0]):], skip_special_tokens=True)
    return response.strip()


def interactive(model, tokenizer):
    """交互式问答"""
    print("\n" + "=" * 60)
    print("Interactive mode. Type 'quit' to exit.")
    print("=" * 60)

    while True:
        try:
            q = input("\n[Q] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in ("quit", "exit", "q"):
            break
        if not q:
            continue

        answer = generate(model, tokenizer, q)
        print(f"[A] {answer}")


def benchmark(model, tokenizer, val_path: str = "data/v1.0/val.json"):
    """在验证集上跑推理"""
    with open(val_path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"\nBenchmark on {len(data)} validation samples...")
    correct = 0
    total = len(data)

    for i, item in enumerate(data):
        question = item["question"]
        true_answer = item["answer"].strip()
        pred = generate(model, tokenizer, question, max_new_tokens=128).strip()

        # 简单匹配：预测中是否包含正确答案
        is_correct = true_answer.lower() in pred.lower() or pred.lower() in true_answer.lower()

        if i < 3:  # 打印前3个样例
            print(f"\n--- Sample {i+1} ---")
            print(f"  Q: {question[:100]}...")
            print(f"  True: {true_answer[:80]}")
            print(f"  Pred: {pred[:80]}")
            print(f"  {'OK' if is_correct else 'WRONG'}")

        if is_correct:
            correct += 1

    acc = correct / total * 100
    print(f"\n{'='*40}")
    print(f"Accuracy: {correct}/{total} = {acc:.1f}%")
    return acc


def main():
    parser = argparse.ArgumentParser(description="模型推理")
    parser.add_argument("--model", default="models/v1.0/final", help="模型路径")
    parser.add_argument("--benchmark", action="store_true", help="跑验证集评测")
    parser.add_argument("--question", type=str, help="单次问答")
    args = parser.parse_args()

    model, tokenizer = load_model(args.model)

    if args.question:
        answer = generate(model, tokenizer, args.question)
        print(f"\nQ: {args.question}")
        print(f"A: {answer}")
    elif args.benchmark:
        benchmark(model, tokenizer)
    else:
        interactive(model, tokenizer)


if __name__ == "__main__":
    main()
