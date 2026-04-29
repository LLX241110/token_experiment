# Token Experiment：用查字典的方式处理中文输入

> 核心问题：如果用拼音/部首等「字典信息」辅助大模型处理中文，会有什么效果？

## 研究背景

现代大模型使用 BPE（Byte-Pair Encoding）处理中文——它是「盲目的」，不知道「木」和「林」有关系，也不知道「青」在「清/晴/睛」中表音。

本项目探索：**将汉字字典结构（部首、声旁、拼音）显式注入 prompt，能否帮助模型更好地理解和推理汉字？**

## 实验设计概览

```
token_experiment/
├── docs/                          # 实验设计文档
│   └── variant_A_experiment.md    # 变体A详细设计
├── variant_A_prompt_enhancement/  # 变体A：Prompt增强
│   ├── test_cases.json            # 测试数据集（含基础+高难度+变体D用例）
│   ├── experiment_runner.py       # 手动测试工具
│   ├── auto_tester.py             # 自动化测试脚本（需 API Key）
│   ├── MANUAL_TEST_GUIDE.md       # 无需 API Key 的手动测试指南
│   └── results/                   # 实验结果（已完成）
│       ├── results_gpt_manual_2026-04-24.md
│       ├── results_claude_manual_2026-04-29.md
│       ├── results_claude_advanced_2026-04-29.md
│       └── results_variant_D_2026-04-29.md
├── discussion_log_2026-04-24.md   # 完整研究讨论记录
└── FINDINGS.md                    # 核心发现汇总（快速阅读版）
```

## 实验变体规划

| 变体 | 方法 | 状态 | 难度 |
|------|------|------|------|
| **A** | Prompt 增强（不改模型） | ✅ 完成 | 低 |
| **B** | Tokenizer 重训练 | 📋 待做 | 中 |
| **C** | 检索增强（RAG思路） | 📋 待做 | 中 |
| **D** | 对比破坏型 | ✅ 完成 | 低 |
| **E** | 跨语言迁移 | 📋 待做 | 高 |
| **F** | 教育场景模拟 | 📋 待做 | 高 |

## 快速开始

### 无 API Key（推荐入门）

```bash
cd variant_A_prompt_enhancement

# 查看所有测试用例
python3 experiment_runner.py --list

# 生成对比 prompt（复制到 Claude/GPT-4 手动测试）
python3 experiment_runner.py --case R1 --compare

# 生成变体D对比破坏测试 prompt
python3 experiment_runner.py --case D_FU --variant-d
```

详细步骤见 [MANUAL_TEST_GUIDE.md](variant_A_prompt_enhancement/MANUAL_TEST_GUIDE.md)

### 有 API Key（自动化）

```bash
cd variant_A_prompt_enhancement
pip install anthropic   # 或 openai

export ANTHROPIC_API_KEY="sk-ant-..."
python3 auto_tester.py --provider anthropic

# 或 GPT-4
export OPENAI_API_KEY="sk-..."
python3 auto_tester.py --provider openai
```

## 核心发现（速览）

完整内容见 [FINDINGS.md](FINDINGS.md)

1. **部首→语义 / 声旁→读音，两条通道完全独立**：通过变体D对比破坏实验（对生僻字提供错误部首/声旁）验证了因果关系——改错哪条，只干扰对应维度
2. **模型在真正推理，不只是查字典**：对不认识的字，错误信息能完全导向错误推断
3. **常见字加注释有害无益**：H4 实验验证，对熟练读者是信息过载；最优策略是按需注释（只标生僻字）
4. **Claude vs GPT-4 差异显著**：Claude baseline 均分 9.2/10，GPT 约 6/10——对 Claude 增强 prompt 的价值主要在「读音补充」而非「纠错」
5. **声旁失效时模型忠实地犯错**：模型掌握共时形声字规律，不具备历时演变（古音→今音）知识

## 待验证假设

| 假设 | 描述 | 状态 |
|------|------|------|
| H5 | 模型对形声字的掌握是共时的（非历时） | 🔍 部分验证，待系统化 |
| H6 | 先验置信度越低，错误信息干扰越大 | 📋 待设计梯度实验 |

## 技术栈

- Python 3.12+
- anthropic SDK (`pip install anthropic`)
- openai SDK（可选，`pip install openai`）

## 贡献 / 继续实验

如需继续实验，建议从以下方向入手：

1. **H6 梯度实验**：设计置信度从高到低的字集，量化干扰效果
2. **变体D跨模型复刻**：在 GPT-4 上重做相同生僻字实验，比较推理机制差异
3. **变体B**：基于本次发现设计包含部首声旁标注的 tokenizer 训练数据
