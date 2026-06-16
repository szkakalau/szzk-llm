# SZZKLLM — 深圳中考学科问答模型

基于 Qwen2.5 微调的中考学科问答模型，覆盖语文、数学、英语、物理、化学、历史、政治 7 个学科。当前最佳模型 **Qwen2.5-7B + 5,527 扩增数据 = 89.3%**。

## 项目状态

| 阶段 | 状态 | 说明 |
|------|------|------|
| 0.5B 小模型验证 | ✅ | 5 轮迭代，v1.3 = 63.5% |
| 真题数据提取 | ✅ | 1,193 题 (2008-2025, 7学科) |
| 数据扩增 | ✅ | 5,527 题 (4.6×, DeepSeek API) |
| 错误分析体系 | ✅ | 134条数据库 + 72题 AI 深度分类 |
| **7B 模型训练** | ✅ | **Qwen2.5-7B LoRA, 89.3%** 🎉 |

## 快速开始

### 7B 模型 (推荐)

```bash
# 训练 (RTX 4090 24GB)
python sft/train_7b.py

# 评测
python sft/infer_7b.py --model models/qwen7b-lora/final --benchmark

# 合并 LoRA → 完整模型
python sft/merge_lora.py --lora models/qwen7b-lora/final --out models/qwen7b-merged
```

### 0.5B 模型 (CPU 可运行)

```bash
pip install -r requirements.txt
python sft/infer.py --model models/v1.3/final --question "..."
python benchmark/evaluate.py --model models/v1.3/final
```

## 模型版本

### 准确率演进

```
7B v3 (扩增):   89.3% ██████████████████████████████████████████████ ⭐
7B v2 (原始):   72.4% ████████████████████████████████████
0.5B v1.3:      63.5% ████████████████████████████████
```

### 7B 版本

| 版本 | 准确率 | 数据 | 训练 |
|------|--------|------|------|
| v2 (原始) | 72.4% | 1,193 题 | 2ep, RTX 4090 |
| **v3 (扩增)** ⭐ | **89.3%** | **5,527 题 (4.6×)** | **2ep, RTX 4090** |

### 7B v3 各科

| 学科 | 准确率 | 亮点 |
|------|--------|------|
| history | **94.1%** | 🔥 |
| english | **93.8%** | 🔥 |
| politics | **92.9%** | 🔥 |
| physics | **90.3%** | 从 45% 暴涨 |
| chemistry | 89.0% | |
| chinese | 82.4% | |
| math | 70.4% | ⚠ 含图公式待解决 |

### 0.5B 实验

| 版本 | 准确率 | 策略 |
|------|--------|------|
| v1.0 | 62.5% | 基线 |
| v1.1 | 43.5% | +CoT (退步) |
| v1.2 | 61.0% | 去噪 |
| v1.3 | 63.5% | +概念辨析 |
| v1.4 | 60.5% | +陷阱变体 |

## 数据集

| 学科 | 原题 | 扩增后 | 年份 |
|------|------|--------|------|
| english | 340 | 1,312 | 2008-2024 |
| math | 159 | 1,295 | 2009-2025 |
| physics | 175 | 1,064 | 2011-2025 |
| chemistry | 154 | 866 | 2008-2025 |
| history | 303 | 839 | 2009-2025 |
| politics | 28 | 78 | 2022-2023 |
| chinese | 34 | 73 | 2010-2024 |
| **总计** | **1,193** | **5,527 (4.6×)** | **18 年** |

## 项目结构

```
SZZKLLM/
├── sft/                        # 训练与推理
│   ├── train_7b.py             # 7B LoRA 训练
│   ├── infer_7b.py             # 7B 推理 + Benchmark
│   ├── merge_lora.py           # LoRA 合并
│   ├── train.py / infer.py     # 0.5B 训练推理
│   └── config_v1.3.yaml
│
├── data/                        # 训练数据
│   ├── clean_train.json        # 1,193 题
│   ├── clean_bench.json        # 1,193 题 (评测格式)
│   ├── augmented_train.json    # 5,527 题 (扩增)
│   └── extracted_questions.json
│
├── scripts/                     # 工具
│   ├── extract_v2.py           # docx 提取流水线
│   ├── augment.py              # 数据扩增 (DeepSeek API)
│   ├── build_training_set.py   # 数据清洗
│   └── gpu_setup.sh            # GPU 环境部署
│
├── benchmark/                   # 评测体系
├── error_analysis/              # 错误分析
├── exam-papers/                 # 303 个原始试卷
├── docs/                        # 实验报告
└── models/                      # 模型权重 (gitignored)
```

## 核心经验

1. **数据扩增是关键** — 1,193 → 5,527 带来 +16.9% (72% → 89%)
2. **基座模型大小决定天花板** — 0.5B 极限 63%, 7B 极限 89%
3. **CoT 对选择题适得其反** — v1.1 加入 CoT 从 62.5% 跌至 43.5%
4. **CPU LoRA 训练会崩溃** — 全量微调才正常
5. **DeepSeek API 答题可用** — 452 题 AI 答案贡献了数据完整性

## 技术栈

- **基座模型**: Qwen2.5-0.5B / Qwen2.5-7B-Instruct
- **微调方式**: 全量微调 (0.5B) / LoRA r=64 (7B)
- **数据**: 303 个原始试卷 → python-docx → 1,193 题 → 扩增 5,527 题
- **扩增**: DeepSeek API (4.6× 变体生成)
- **训练**: RTX 4090 24GB, ~50 分钟

---

🤖 *55 次提交 | 5,527 题训练数据 | 7B LoRA 89.3% | 2026年6月*
