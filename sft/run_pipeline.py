# -*- coding: utf-8 -*-
"""
SZZKLLM 一键训练流水线
用法:
  python sft/run_pipeline.py                        # 完整流水线: 训练→推理→对比
  python sft/run_pipeline.py --skip-train            # 跳过训练，仅推理+对比
  python sft/run_pipeline.py --config sft/config.yaml  # 自定义配置
  python sft/run_pipeline.py --test                  # 测试模式 (少量数据验证)
"""
import argparse, subprocess, sys, os, time, json
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent


def run_step(name: str, cmd: list, timeout: int = 7200) -> bool:
    """运行单个步骤"""
    print(f"\n{'=' * 60}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {name}")
    print(f"  CMD: {' '.join(cmd)}")
    print(f"{'=' * 60}")
    t0 = time.time()
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    elapsed = time.time() - t0
    if result.returncode == 0:
        print(f"\n  {name} 完成 ✅ ({elapsed:.0f}s)")
        return True
    else:
        print(f"\n  {name} 失败 ❌ (exit {result.returncode}, {elapsed:.0f}s)")
        return False


def main():
    parser = argparse.ArgumentParser(description="SZZKLLM 一键训练流水线")
    parser.add_argument("--config", default="sft/config.yaml", help="训练配置文件")
    parser.add_argument("--test", action="store_true", help="测试模式")
    parser.add_argument("--skip-train", action="store_true", help="跳过训练")
    parser.add_argument("--skip-compare", action="store_true", help="跳过对比评测")
    parser.add_argument("--python", default=sys.executable, help="Python解释器")
    args = parser.parse_args()

    python = args.python
    test_flag = ["--test"] if args.test else []

    # 从config提取output_dir
    import yaml
    config_path = PROJECT_ROOT / args.config
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        output_dir = config.get("output_dir", "models/v1.1")
    else:
        output_dir = "models/v1.1"

    results = {}
    t_start = time.time()

    # ── Step 1: 训练 ──
    if not args.skip_train:
        train_cmd = [python, "sft/train.py", "--config", args.config] + test_flag
        results["train"] = run_step("Step 1/3: 训练模型", train_cmd)
        if not results["train"]:
            print("\n训练失败，流水线终止")
            return
    else:
        print("\n[跳过] 训练步骤")

    # ── Step 2: Benchmark评测 ──
    infer_cmd = [
        python, "sft/infer.py",
        "--model", f"{output_dir}/final",
        "--benchmark",
    ]
    results["benchmark"] = run_step("Step 2/3: Benchmark评测", infer_cmd, timeout=600)

    # ── Step 3: 模型对比 ──
    if not args.skip_compare:
        compare_cmd = [python, "sft/compare_models.py"]
        results["compare"] = run_step("Step 3/3: 模型对比", compare_cmd, timeout=600)

    # ── 总结 ──
    total_time = time.time() - t_start
    print(f"\n{'=' * 60}")
    print(f"流水线完成 ({total_time:.0f}s)")
    print(f"{'=' * 60}")
    for step, ok in results.items():
        status = "✅" if ok else "❌"
        print(f"  {status} {step}")
    print(f"\n模型路径: {output_dir}/final")
    print(f"推理测试: python sft/infer.py --model {output_dir}/final")
    print(f"模型对比: python sft/compare_models.py")


if __name__ == "__main__":
    main()
