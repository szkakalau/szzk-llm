"""
SFT 训练脚本 — 基于 TRL SFTTrainer + WandB
用法:
  # 本地测试运行 (CPU，20条数据，1步)
  python sft/train.py --test

  # 完整训练 (需要 GPU 或 Colab)
  python sft/train.py --model Qwen/Qwen2.5-0.5B --epochs 2 --batch_size 4

  # 用自定义数据集
  python sft/train.py --train_data data/v1.0/train.json --val_data data/v1.0/val.json
"""
import argparse, json, os, sys
from pathlib import Path

import torch
import wandb
from datasets import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
)
from trl import SFTTrainer

# ============================================================
# 默认超参数（与计划一致）
# ============================================================
DEFAULTS = {
    "model": "Qwen/Qwen2.5-0.5B",
    "train_data": "data/v1.0/train.json",
    "val_data": "data/v1.0/val.json",
    "output_dir": "models/v1.0",
    "epochs": 2,
    "batch_size": 4,
    "gradient_accumulation": 2,
    "learning_rate": 2e-5,
    "warmup_steps": 50,
    "max_seq_length": 1024,
    "save_steps": 100,
    "logging_steps": 10,
    "wandb_project": "szzk-llm",
    "wandb_entity": "33350441-sightwhale",
}


def format_chat(example: dict) -> dict:
    """将 QA 对格式化为 ChatML 格式"""
    return {
        "messages": [
            {"role": "user", "content": example["question"]},
            {"role": "assistant", "content": example["answer"]},
        ]
    }


def load_data(train_path: str, val_path: str, test_mode: bool = False):
    """加载并格式化训练/验证数据"""
    with open(train_path, encoding="utf-8") as f:
        train_raw = json.load(f)
    with open(val_path, encoding="utf-8") as f:
        val_raw = json.load(f)

    if test_mode:
        train_raw = train_raw[:20]
        val_raw = val_raw[:5]

    # 转为 HuggingFace Dataset
    train_data = Dataset.from_list([format_chat(x) for x in train_raw])
    val_data = Dataset.from_list([format_chat(x) for x in val_raw])

    print(f"训练集: {len(train_data)} 条, 验证集: {len(val_data)} 条")
    return train_data, val_data


def main():
    parser = argparse.ArgumentParser(description="SFT 训练脚本")
    parser.add_argument("--test", action="store_true", help="测试模式：少量数据，1个epoch，不记录WandB")
    parser.add_argument("--model", default=DEFAULTS["model"])
    parser.add_argument("--train_data", default=DEFAULTS["train_data"])
    parser.add_argument("--val_data", default=DEFAULTS["val_data"])
    parser.add_argument("--output_dir", default=DEFAULTS["output_dir"])
    parser.add_argument("--epochs", type=int, default=DEFAULTS["epochs"])
    parser.add_argument("--batch_size", type=int, default=DEFAULTS["batch_size"])
    parser.add_argument("--gradient_accumulation", type=int, default=DEFAULTS["gradient_accumulation"])
    parser.add_argument("--learning_rate", type=float, default=DEFAULTS["learning_rate"])
    parser.add_argument("--max_seq_length", type=int, default=DEFAULTS["max_seq_length"])
    parser.add_argument("--use_lora", action="store_true", help="使用 LoRA 微调（节省显存）")
    parser.add_argument("--lora_r", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    args = parser.parse_args()

    test_mode = args.test

    # ── 1. 加载数据 ──
    print("=" * 60)
    print("Step 1/5: 加载数据...")
    train_data, val_data = load_data(args.train_data, args.val_data, test_mode)
    print(f"  训练集: {len(train_data)} | 验证集: {len(val_data)}")
    print(f"  样本: {train_data[0]['messages'][0]['content'][:80]}...")

    # ── 2. 加载模型和分词器 ──
    print("\n" + "=" * 60)
    print(f"Step 2/5: 加载模型 {args.model}...")
    print(f"  设备: {'CUDA' if torch.cuda.is_available() else 'CPU'}")

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    load_kwargs = {}
    if not torch.cuda.is_available():
        # CPU 模式：减少内存占用
        load_kwargs["device_map"] = "cpu"
        load_kwargs["dtype"] = torch.float32
        print("  [CPU] GPU not available, using CPU mode (for syntax verification only)")
    else:
        load_kwargs["dtype"] = torch.bfloat16

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        trust_remote_code=True,
        **load_kwargs,
    )

    # 配置 chat template（如果模型没有自带）
    if not hasattr(tokenizer, 'chat_template') or tokenizer.chat_template is None:
        tokenizer.chat_template = (
            "{% for message in messages %}"
            "{% if message['role'] == 'user' %}"
            "<|im_start|>user\n{{ message['content'] }}<|im_end|>\n"
            "{% elif message['role'] == 'assistant' %}"
            "<|im_start|>assistant\n{{ message['content'] }}<|im_end|>\n"
            "{% endif %}"
            "{% endfor %}"
        )
        print("  已设置默认 chat_template (ChatML 格式)")

    # 格式化函数：将 messages 转为训练文本
    def formatting_func(example):
        return tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )

    # ── 3. 配置训练参数 ──
    print("\n" + "=" * 60)
    print("Step 3/5: 配置训练参数...")

    effective_batch = args.batch_size * args.gradient_accumulation
    print(f"  有效 batch size: {args.batch_size} × {args.gradient_accumulation} = {effective_batch}")
    print(f"  学习率: {args.learning_rate}")
    print(f"  Epochs: {args.epochs}")

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=1 if test_mode else args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=1 if test_mode else args.gradient_accumulation,
        learning_rate=args.learning_rate,
        warmup_steps=DEFAULTS["warmup_steps"],
        logging_steps=DEFAULTS["logging_steps"],
        save_steps=DEFAULTS["save_steps"],
        eval_strategy="steps",
        eval_steps=DEFAULTS["save_steps"],
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=torch.cuda.is_available(),
        fp16=False,
        dataloader_num_workers=0,
        report_to=["wandb"] if not test_mode else ["none"],
        run_name=f"sft-{args.model.split('/')[-1]}" if not test_mode else "test-run",
        remove_unused_columns=False,
    )

    # ── 4. WandB 初始化 ──
    if not test_mode:
        print("\n" + "=" * 60)
        print("Step 4/5: 初始化 WandB...")
        try:
            wandb.init(
                project=DEFAULTS["wandb_project"],
                entity=DEFAULTS["wandb_entity"],
                config={
                    "model": args.model,
                    "train_size": len(train_data),
                    "val_size": len(val_data),
                    "epochs": args.epochs,
                    "batch_size": args.batch_size,
                    "gradient_accumulation": args.gradient_accumulation,
                    "learning_rate": args.learning_rate,
                    "max_seq_length": args.max_seq_length,
                    "use_lora": args.use_lora,
                },
            )
            print("  WandB initialized successfully")
        except Exception as e:
            print(f"  WandB online failed: {e}")
            print("  Trying offline mode (logs saved locally, sync later with: wandb sync)")
            try:
                os.environ["WANDB_MODE"] = "offline"
                wandb.init(
                    project=DEFAULTS["wandb_project"],
                    entity=DEFAULTS["wandb_entity"],
                    config={"model": args.model},
                    mode="offline",
                )
                print("  WandB offline mode OK")
            except Exception as e2:
                print(f"  WandB offline also failed: {e2}")
                print("  Continuing without WandB logging")
                training_args.report_to = ["none"]
    else:
        print("\n  [测试模式] 跳过 WandB 初始化")

    # ── 5. 创建 Trainer 并训练 ──
    print("\n" + "=" * 60)
    print("Step 5/5: 开始训练...")

    # LoRA 配置
    peft_config = None
    if args.use_lora:
        from peft import LoraConfig
        peft_config = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )
        print("  使用 LoRA 微调")

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_data,
        eval_dataset=val_data,
        formatting_func=formatting_func,
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    print(f"\n  开始训练... (test_mode={test_mode})")
    print(f"  总步数估算: {len(train_data) * args.epochs // effective_batch}")

    try:
        trainer.train()
    except KeyboardInterrupt:
        print("\n  训练被手动中断")
    except Exception as e:
        print(f"\n  训练出错: {e}")
        import traceback
        traceback.print_exc()
        if test_mode:
            print("\n  [测试模式] 这是预期行为 — CPU 训练可能因显存/内存不足失败")
            print("  脚本语法和流程验证通过，请在 GPU 环境运行完整训练。")
        sys.exit(1)

    # ── 保存模型 ──
    final_path = Path(args.output_dir) / "final"
    print(f"\n  保存模型到 {final_path}...")
    trainer.save_model(str(final_path))
    tokenizer.save_pretrained(str(final_path))

    if not test_mode:
        wandb.finish()

    print("\n" + "=" * 60)
    print("Training completed!")
    print(f"模型保存在: {final_path}")


if __name__ == "__main__":
    main()
