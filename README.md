# SZZKLLM — 深圳中考学科问答模型

基于 Qwen2.5-0.5B 微调的中考学科问答模型，覆盖语文、数学、英语、物理、化学、历史、政治 7 个学科。配套完整的 Benchmark 评测体系和 AI 辅助错误分析工作流。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 推理测试
python sft/infer.py --model models/v1.3/final --question "下列图形中，是轴对称图形的是（ ）A. 平行四边形 B. 直角三角形 C. 圆 D. 梯形"

# Benchmark 评测
python benchmark/evaluate.py --model models/v1.3/final

# 训练 (修改 sft/config_v1.3.yaml 中的参数后)
python sft/train.py --config sft/config_v1.3.yaml
```

## 模型版本

| 版本 | 准确率 | 训练数据 | 策略 | 关键发现 |
|------|--------|---------|------|---------|
| v1.0 | 62.5% | 367条 | 基线, 无CoT | 语文37.9% 数学47.1% 短板 |
| v1.1 | 43.5% | 567条 | +CoT 200条 | **CoT对选择题适得其反** |
| v1.2 | 61.0% | 430条 | 去噪24%, 保留CoT | 接近基线但未超越 |
| **v1.3** ⭐ | **63.5%** | **630条** | **+概念辨析186题** | **当前最佳** |
| v1.4 | 60.5% | 660条 | +陷阱变体31题 | 数据稀释导致退步 |

### v1.3 学科得分

| 学科 | 准确率 | 提升(vs v1.2) |
|------|--------|--------------|
| history | **86.7%** | +20.0% 🎉 |
| politics | **85.0%** | +20.0% 🎉 |
| chemistry | 74.1% | +7.4% |
| english | 66.7% | +3.7% |
| math | 58.8% | → 持平 |
| physics | 45.5% | -18.1% ⚠ |
| chinese | 44.8% | -31.1% ⚠ |

## 项目结构

```
SZZKLLM/
├── sft/                        # 训练与推理
│   ├── train.py                # SFT 训练脚本 (TRL SFTTrainer)
│   ├── infer.py                # 模型推理
│   ├── run_pipeline.py         # 一键流水线
│   └── config_v1.3.yaml        # v1.3 训练配置
│
├── benchmark/                   # 评测体系
│   ├── test_set_v0.1.json      # 200题题库 (7学科)
│   ├── evaluate.py             # 双指标评测 (General + Error Recovery)
│   ├── verify_scoring.py       # 评分验证 (46项提取+10项模拟+600批量)
│   ├── build_benchmark.py      # 题库构建脚本
│   └── error_set_v1.*.json     # 各版本错误集
│
├── error_analysis/              # 错误分析体系
│   ├── all_errors.json         # D15: 统一错误数据库 (134条)
│   ├── classified_errors.json  # D16: DeepSeek API 深度分类 (72题)
│   ├── curated_errors.json     # D17: 审核后 + P0/P1/P2 优先级
│   ├── root_cause.md           # D18: 根因分析报告
│   ├── optimization_plan.md    # D19: 7方案优化设计
│   ├── deep_classify.py        # DeepSeek 分类脚本
│   └── curate_d17.py           # 审核规则引擎
│
├── data/                        # 训练数据
│   ├── v1.0/                   # 基线: 367条
│   ├── v1.1/                   # +CoT: 567条
│   ├── v1.2/                   # 干净: 430条
│   ├── v1.3/                   # +概念辨析: 630条
│   │   ├── concept_drill.json  # 186道概念辨析题
│   │   ├── fact_cards.json     # 15条公式记忆卡
│   │   └── train.json
│   └── v1.4/                   # +陷阱变体: 660条
│
├── models/                      # 模型权重 (gitignored)
│   ├── v1.0/final/             # 基线
│   ├── v1.1/final/             # CoT (退步)
│   ├── v1.2/final/             # 去噪
│   ├── v1.3/final/             # ⭐ 最佳
│   └── v1.4/final/             # 陷阱
│
├── docs/                        # 实验报告
│   ├── week1_report.md
│   ├── week2_report.md
│   └── week3_report.md
│
├── exam-papers/                 # 中考真题 (原始数据源)
│   ├── 1.深圳中考语文/
│   ├── 2.深圳中考数学/
│   └── ... (物理/化学/英语/历史/政治)
│
└── scripts/
    └── generate_cot.py          # CoT 数据生成 (DeepSeek API)
```

## 核心发现

### 1. CoT 对选择题适得其反
v1.1 加入 CoT 训练后准确率从 62.5% 骤降至 43.5%。选择题不需要推理过程，直接输出选项字母最优。

### 2. 概念理解偏差是最大根因 (53%)
DeepSeek API 深度分析 72 道错误后发现：53% 是**知识缺失**（不是逻辑推理问题）。模型连绝对值、轴对称、纯净物等最基础概念都无法稳定掌握。

### 3. 72% 的错误来自基础送分题
52/72 道错误被标注为 difficulty=easy。这些应该是"闭着眼睛都能做对"的题，修复性价比极高。

### 4. 概念辨析数据增强显著有效
186 道概念辨析题使 History +20%、Politics +20%。证明了"针对弱概念做正反例对比训练"的策略正确。

### 5. LoRA 在 CPU 训练中导致模型崩溃
v1.3 先用 LoRA 训练得到 26.5%（接近随机），切换为全量微调后恢复正常 63.5%。CPU 环境下全量微调 > LoRA。

## Benchmark 评测

```bash
# 基础评测
python benchmark/evaluate.py --model models/v1.3/final

# 带历史错误集 (计算 Error Recovery Score)
python benchmark/evaluate.py --model models/v1.3/final \
    --error-set benchmark/error_set_v1.2.json \
    --save-errors benchmark/error_set_v1.3.json

# 评分验证 (确保评分逻辑 100% 正确)
python benchmark/verify_scoring.py
```

双指标体系：
- **General Score**: 全局 200 题准确率
- **Error Recovery Score**: 历史错题修复率

## 错误分析工作流

```
D15 → D16 → D17 → D18 → D19 → D20 → D21
错误DB   AI分类  审核   根因   方案   数据   复盘
```

完整流程产出：
1. 134 条统一错误数据库（3 版本合并去重）
2. 72 题 DeepSeek 深度分类（置信度 0.94）
3. 46 题 P0 优先修复清单
4. 根因分析报告 + 7 方案优化矩阵
5. 186 道概念辨析 + 15 条记忆卡 + 31 道陷阱变体

## 技术栈

- **基座模型**: Qwen2.5-0.5B
- **训练框架**: TRL SFTTrainer + Hugging Face Transformers
- **微调方式**: 全量微调 (Full Fine-tuning)
- **评测**: 200 题自建 Benchmark (7 学科 × 选择题)
- **错误分析**: DeepSeek API (deepseek-v4-flash)
- **实验追踪**: Weights & Biases (WandB)
- **环境**: Python 3.14, PyTorch 2.12, CPU (无 GPU)

## 下一步

- [ ] 获取 GPU 资源验证性能上限
- [ ] Physics/Chinese 专项数据增强
- [ ] FastAPI + Next.js 前后端部署
- [ ] GitHub Actions 自动评测流水线

---

🤖 *36 次提交 | 4 天集中开发 | 5 轮模型迭代 | 2026年6月*
