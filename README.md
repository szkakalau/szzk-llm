# SZZKLLM — 深圳中考学科问答模型

基于 Qwen2.5 微调的中考学科问答模型，覆盖语文、数学、英语、物理、化学、历史、政治 7 个学科。配套完整的 **真题提取流水线**、**Benchmark 评测体系** 和 **AI 辅助错误分析工作流**。

## 项目状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| 0.5B 小模型验证 | ✅ 完成 | 5 轮迭代，最佳 v1.3 = 63.5% |
| 真题数据提取 | ✅ 完成 | 1,193 道高质量选择题 (2008-2025) |
| 错误分析体系 | ✅ 完成 | 134条数据库 + 72题 AI 深度分类 |
| **7B 模型训练** | 🔜 **待 GPU** | 脚本就绪，租 RTX 4090 即可 |

## 快速开始

### 0.5B 模型 (CPU 可运行)

```bash
pip install -r requirements.txt

# 推理测试
python sft/infer.py --model models/v1.3/final --question "下列图形中，是轴对称图形的是（ ）A. 平行四边形 B. 直角三角形 C. 圆 D. 梯形"

# Benchmark 评测
python benchmark/evaluate.py --model models/v1.3/final
```

### 7B 模型 (需要 GPU ≥24GB)

```bash
# 部署环境
bash scripts/gpu_setup.sh

# 训练
python sft/train_7b.py              # LoRA, RTX 4090 24GB
python sft/train_7b.py --qlora      # QLoRA, 更低显存

# 评测
python sft/infer_7b.py --model models/qwen7b-lora/final --benchmark

# 合并导出
python sft/merge_lora.py --lora models/qwen7b-lora/final --out models/qwen7b-merged
```

## 数据集

### 真题提取流水线

从 178 个 `.docx` 原始试卷文件中提取选择题：

```
scripts/extract_v2.py          ← docx → 选择题 (题目+选项+答案匹配)
scripts/build_training_set.py  ← 清洗 + 训练格式输出
scripts/answer_with_deepseek.py ← DeepSeek API 批量答题 (452题)
```

### 数据统计

| 学科 | 数量 | 年份 | 来源 |
|------|------|------|------|
| english | 340 | 2008-2024 | 真题提取 + DeepSeek 答题 |
| history | 303 | 2009-2025 | 真题提取 + DeepSeek 答题 |
| physics | 175 | 2011-2025 | 真题提取 |
| math | 159 | 2009-2025 | 真题提取 |
| chemistry | 154 | 2008-2025 | 真题提取 |
| chinese | 34 | 2010-2024 | 真题提取 |
| politics | 28 | 2022-2023 | 真题提取 |
| **总计** | **1,193** | **18 年** | |

### 数据格式

```json
// data/clean_train.json — 训练格式
{"question": "－3的绝对值是（ ）A. 3 B. -3 C. 1/3 D. -1/3", "answer": "A", "subject": "math"}

// data/clean_bench.json — 评测格式  
{"id": 1, "question": "－3的绝对值是（ ）", "options": ["A. 3", "B. -3", "C. 1/3", "D. -1/3"], "answer": "A", "subject": "math"}
```

## 0.5B 模型版本

| 版本 | 准确率 | 训练数据 | 策略 | 关键发现 |
|------|--------|---------|------|---------|
| v1.0 | 62.5% | 367条 | 基线, 无CoT | 语文37.9% 数学47.1% 短板 |
| v1.1 | 43.5% | 567条 | +CoT 200条 | **CoT对选择题适得其反** |
| v1.2 | 61.0% | 430条 | 去噪24%, 保留CoT | 接近基线但未超越 |
| **v1.3** ⭐ | **63.5%** | **630条** | **+概念辨析186题** | **0.5B 最佳** |
| v1.4 | 60.5% | 660条 | +陷阱变体31题 | 数据稀释导致退步 |

## 项目结构

```
SZZKLLM/
├── sft/                        # 训练与推理
│   ├── train.py                # 0.5B 训练 (TRL SFTTrainer)
│   ├── infer.py                # 0.5B 推理
│   ├── train_7b.py             # 7B LoRA 训练 ← GPU
│   ├── infer_7b.py             # 7B 推理 + Benchmark
│   └── merge_lora.py           # LoRA 权重合并
│
├── benchmark/                   # 评测体系
│   ├── test_set_v0.1.json      # 200题题库 (旧)
│   ├── evaluate.py             # 双指标评测
│   └── verify_scoring.py       # 评分验证
│
├── error_analysis/              # 错误分析体系
│   ├── all_errors.json         # 统一错误数据库 (134条)
│   ├── classified_errors.json  # DeepSeek 深度分类 (72题)
│   ├── root_cause.md           # 根因分析报告
│   └── optimization_plan.md    # 7方案优化设计
│
├── data/                        # 训练数据
│   ├── clean_train.json        # 1,193条 训练集
│   ├── clean_bench.json        # 1,193条 评测集
│   ├── extracted_questions.json # 原始提取 (1,239条)
│   └── v1.0~v1.4/             # 各版训练数据
│
├── scripts/                     # 数据工具
│   ├── extract_v2.py           # docx 提取流水线
│   ├── build_training_set.py   # 数据清洗
│   ├── answer_with_deepseek.py # DeepSeek 答题
│   ├── gpu_setup.sh            # GPU 环境部署
│   └── run_all.sh              # 训练+评测一键脚本
│
├── docs/                        # 实验报告
│   ├── week1_report.md ~ week4_report.md
│   └── benchmark_v0.1_guide.md
│
├── exam-papers/                 # 中考真题 (303个 .doc/.docx)
└── models/                      # 模型权重 (gitignored)
```

## 核心发现

### 1. 概念辨析数据增强最有效
186 道概念辨析题使 v1.3 达 63.5%，History +20%, Politics +20%。针对弱概念做正反例对比的策略被证实有效。

### 2. CoT 对选择题适得其反
v1.1 加入 CoT 后从 62.5% 跌至 43.5%。选择题不需要推理过程，直接输出选项字母最优。

### 3. 数据量是天花板
0.5B 模型在 630 条数据上达到 63.5% 的极限。1,193 条真题 + 7B 模型预计可突破 85%。

### 4. LoRA 在 CPU 训练中崩溃
CPU LoRA 导致模型输出垃圾文本 (26.5%)，全量微调恢复正常 (63.5%)。GPU 上 LoRA 无此问题。

### 5. 真题 .docx 提取可行
303 个原始试卷文件 → 1,239 题提取 → 1,193 题清洗可用。纯文本提取覆盖 97%，仅 ~25 道含图公式题需多模态处理。

## 技术栈

- **基座模型**: Qwen2.5-0.5B / Qwen2.5-7B-Instruct
- **训练框架**: TRL SFTTrainer + Hugging Face Transformers + PEFT
- **微调方式**: 全量微调 (0.5B) / LoRA (7B)
- **数据**: 303 个原始试卷 → python-docx 提取 → 1,193 题
- **答题**: DeepSeek API (452 题自动作答)
- **错误分析**: DeepSeek API (72 题深度分类, 置信度 0.94)
- **预计 7B 配置**: RTX 4090 24GB, LoRA r=64, ~40-60 min

## 下一步

- [ ] 租 RTX 4090 GPU → 训练 Qwen2.5-7B
- [ ] 预估准确率: **85%+**
- [ ] Physics/Chinese 专项数据增强
- [ ] FastAPI + Next.js 部署

---

🤖 *54 次提交 | 1,193 题训练数据 | 5 轮 0.5B 迭代 | 2026年6月*
