# 变体A：Prompt增强实验

## 实验目的

验证一个简单的假设：**在prompt中给出生僻字的部首/拼音信息，能否帮助模型更好地理解和推理汉字？**

这模拟了人类查字典的行为——遇到不认识的字，先看部首（推断意思）和拼音（知道读音）。

---

## 核心假设

| 假设 | 内容 | 验证方式 |
|------|------|----------|
| **H1** | 部首信息能帮助推断语义类别 | 给"汸(氵)"，看是否能说出"与水有关" |
| **H2** | 声旁信息能帮助推断读音 | 给"汸(方)"，看是否能联想读音 |
| **H3** | 部首+声旁联合 > 单独信息 | 对比四种prompt条件的效果 |
| **H4** | 常见字加注释可能干扰 | 测试"的"加不加拼音部首的区别 |

---

## 实验设计

### Prompt类型对比

针对同一个问题，我们使用5种不同的prompt方式：

| 类型 | 说明 | 示例 |
|------|------|------|
| **baseline** | 不给任何额外信息 | "汸是什么意思？" |
| **pinyin_only** | 只给拼音 | "汸(读音fāng)是什么意思？" |
| **radical_only** | 只给部首 | "汸(部首：氵)是什么意思？" |
| **full_enhanced** | 部首+声旁+拼音 | "汸(部首氵，声旁方，读音fāng)是什么意思？" |
| **expert_mode** | 专家角色+详细分析 | "你是汉字学专家，汸的部首氵表示..." |

### 测试类别

1. **部首语义推断** (radical_semantic_inference)
   - 给生僻字+部首，推断意思类别
   - 例：汸(氵) → 应该推断出"与水有关"

2. **声旁读音推断** (phonetic_pronunciation_inference)
   - 给生僻字+声旁，推断读音
   - 例：汸(方) → 应该推断出读音接近"fang"

3. **联合推断** (combined_inference)
   - 同时利用部首和声旁
   - 例：淦(氵+金) → 与水有关，读音接近"jin"

4. **同音字辨析** (homophone_discrimination)
   - 利用部首区分同音字
   - 例：秘(禾) vs 密(宀)

5. **常见字干扰** (common_character_interference)
   - 测试常用字加注释是否造成信息过载

---

## 快速开始

### 1. 查看所有测试用例

```bash
python experiment_runner.py --list
```

### 2. 运行一组对比测试

```bash
# 查看"部首语义推断"类别的 baseline prompt
python experiment_runner.py --category radical_semantic_inference --prompt-type baseline

# 查看同一类别，但使用 full_enhanced prompt
python experiment_runner.py --category radical_semantic_inference --prompt-type full_enhanced
```

### 3. 对比一个用例的所有prompt变体

```bash
python experiment_runner.py --case R1 --compare
```

这会输出同一个测试用例（R1: 汸）在5种prompt下的完整文本，方便你直接复制测试。

---

## 手工测试步骤

### 第一步：选择测试用例

打开 `test_cases.json`，选择一个感兴趣的用例。

推荐从 **R1 (汸)** 开始——这是一个经典的水部生僻字。

### 第二步：准备对比

用 `experiment_runner.py --case R1 --compare` 生成5种prompt。

### 第三步：实际测试

复制每个prompt到 Claude/GPT-4/文心一言等模型，记录回答。

### 第四步：评估结果

根据以下维度打分：

| 维度 | 标准 | 分值 |
|------|------|------|
| 准确性 | 回答是否与期望答案匹配 | 0-2分 |
| 推理过程 | 是否提到了部首/声旁的作用 | 0-2分 |
| 信心度 | 回答是否自信、逻辑清晰 | 0-1分 |

**总分 0-5分**

### 第五步：对比分析

将5种prompt的得分填入表格：

| Prompt类型 | R1得分 | R2得分 | ... | 平均分 |
|------------|--------|--------|-----|--------|
| baseline | | | | |
| pinyin_only | | | | |
| radical_only | | | | |
| full_enhanced | | | | |
| expert_mode | | | | |

---

## 预期发现

### 情景1：Full_enhanced明显优于baseline
- 说明：字典信息确实有帮助
- 下一步：深入优化信息呈现方式

### 情景2：Radical_only > Pinyin_only
- 说明：部首的语义提示比声旁的读音提示更有用
- 可能原因：部首与意思的关联更直接

### 情景3：常见字加注释反而降低效果
- 说明：信息过载确实存在
- 启示：只在生僻字上加注释可能更好

### 情景4：所有方式效果差不多
- 说明：模型可能已经"记住"了这些信息
- 或者：当前模型对汉字结构的利用能力有限

---

## 数据文件说明

### test_cases.json 结构

```json
{
  "test_categories": {
    "category_name": {
      "description": "类别描述",
      "cases": [
        {
          "id": "R1",
          "character": "汸",
          "pinyin": "fāng",
          "radical": "氵",
          "phonetic": "方",
          "question": "...",
          "expected_answer": "..."
        }
      ]
    }
  },
  "prompt_templates": {
    "baseline": "...",
    "full_enhanced": "..."
  }
}
```

---

## 扩展建议

1. **增加测试用例**：在 `test_cases.json` 中添加更多生僻字
2. **自定义prompt模板**：修改 `prompt_templates` 尝试不同表述
3. **自动化评估**：可以接入API自动运行并记录结果
4. **加入更多模型**：对比Claude、GPT-4、文心、通义等的差异

---

## 实验记录

请在下方记录你的实验结果：

### 2026-04-XX 第一次测试

**测试者**: 
**使用模型**: 

| 用例ID | Prompt类型 | 模型回答摘要 | 得分 | 备注 |
|--------|------------|--------------|------|------|
| R1 | baseline | | | |
| R1 | full_enhanced | | | |
| ... | ... | | | |

**初步结论**: 

---

## 快速开始（自动化测试）

如果你希望直接运行自动化测试而非手工复制：

### 1. 安装依赖

```bash
pip install anthropic  # 或 openai
```

### 2. 设置API Key

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

### 3. 运行测试

```bash
# 测试所有类别
python auto_tester.py --provider anthropic

# 只测试特定类别
python auto_tester.py --provider anthropic --category radical_semantic_inference
```

### 4. 查看结果

测试完成后会生成两个文件：
- `results_anthropic_YYYYMMDD_HHMMSS.json` - 原始结果数据
- `report_anthropic_YYYYMMDD_HHMMSS.md` - 可读性报告

---

*Happy Experimenting!*
