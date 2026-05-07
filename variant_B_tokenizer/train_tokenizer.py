#!/usr/bin/env python3
"""
变体B：Tokenizer 重训练实验
对比两个 BPE tokenizer：
  - baseline：标准中文语料训练
  - enhanced：相同语料 + 部首/声旁注释增强

评测指标：
  - 生僻字的 token 数（越少越好，说明切分更合理）
  - 已知常用字的 token 数（不应变差）
  - 部首/声旁是否被单独保留为独立 token
"""

import json
from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.trainers import BpeTrainer
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.decoders import ByteLevel as ByteLevelDecoder

# ── 1. 构造训练语料 ──────────────────────────────────────────────────

# 基础中文语料（覆盖常用字、生僻字、部首词汇）
BASE_CORPUS = [
    # 常用句子
    "今天天气很好，我们去公园散步。",
    "机器学习是人工智能的一个重要分支。",
    "中文自然语言处理面临独特的挑战。",
    "汉字具有悠久的历史和丰富的文化内涵。",
    "水是生命之源，江河湖海都与氵有关。",
    "木材、树木、森林都与木字旁有关联。",
    "火焰、燃烧、热量都与火有密切关系。",
    "石头、岩石、矿物都属于石部的字族。",
    # 生僻字语境
    "汸是一个水名，汭指水湾，浯是山东的一条河。",
    "棻是一种香木，朸指木节，杻是树木的名称。",
    "炇字从火，砯字从石，犴字从犬。",
    "氵部的字大多与水有关：江河湖海洋泉源流。",
    "火部的字大多与燃烧有关：炎烧灼热焰煤炭。",
    "木部的字与树木有关：树桌椅柜板梁柱棍棒。",
    # 部首词汇
    "部首是汉字的重要组成部分，形声字由形旁和声旁构成。",
    "氵三点水表示与水液体河流有关的字义。",
    "形声字占汉字总数的百分之八十以上。",
    "声旁提示读音，形旁提示语义类别。",
    "清晴情请青都含有青这个声旁，读音相近。",
    "江河湖海洋都含氵，都与水有关。",
    "林森木材树枝都含木，都与植物有关。",
] * 50  # 重复50次增加语料量

# 增强语料：在原语料基础上加入部首/声旁注释
ENHANCED_CORPUS = BASE_CORPUS + [
    # 显式的部首-语义对应
    "氵水：江(氵工)河(氵可)湖(氵胡)海(氵每)清(氵青)洋(氵羊)",
    "火热：炎(火火)烧(火尧)灼(火勺)热(火执)焰(火臽)",
    "木植：树(木对)桌(木卓)椅(木奇)柜(木匮)板(木反)",
    "石矿：砯(石平)砾(石历)碑(石卑)磁(石兹)矿(石广)",
    "犭兽：犴(犭干)狼(犭良)猫(犭苗)狗(犭句)狐(犭瓜)",
    # 形声字分析
    "汸(氵方,fāng)是水名，声旁方提示读音",
    "棻(木分,fēn)是香木，声旁分提示读音",
    "炇(火攵,fū)从火，声旁攵提示读音",
    "砯(石平,pīng)从石，声旁平提示读音",
    "犴(犭干,àn)从犬，声旁干提示读音",
    "浯(氵吾,wú)是河流名，声旁吾提示读音",
    "棻朸杻炇砯犴氵木火石犭",
    "形旁声旁部首偏旁声调读音语义",
    # 声旁族群
    "方族：汸(氵)坊(土)芳(艹)放(攵)房(户)访(讠)防(阝)",
    "青族：清(氵)晴(日)请(讠)情(忄)靖(立)倩(人)",
    "木族：树森林桦桔桃梅松柏柳橡",
    "水族：江河湖海洋泉源流津渡",
] * 30


def build_corpus_file(sentences, path):
    with open(path, "w", encoding="utf-8") as f:
        for s in sentences:
            f.write(s + "\n")


def train_bpe(corpus_path, save_path, vocab_size=3000):
    tokenizer = Tokenizer(BPE(unk_token="[UNK]"))
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False)
    tokenizer.decoder = ByteLevelDecoder()

    trainer = BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=["[UNK]", "[PAD]", "[BOS]", "[EOS]"],
        min_frequency=2,
        show_progress=False,
    )
    tokenizer.train([corpus_path], trainer)
    tokenizer.save(save_path)
    return tokenizer


# ── 2. 评测函数 ──────────────────────────────────────────────────────

TEST_CHARS = {
    "常用字": ["清", "河", "火", "木", "石", "水", "江", "湖"],
    "生僻形声字": ["汸", "棻", "炇", "砯", "犴", "浯", "朸", "汭"],
    "叠加构字": ["淼", "森", "炎", "犇", "鱻"],
    "部首本身": ["氵", "火", "木", "石", "犭"],
}

def evaluate(tokenizer, label):
    results = {}
    print(f"\n{'='*50}")
    print(f"Tokenizer: {label}")
    print(f"{'='*50}")

    for category, chars in TEST_CHARS.items():
        print(f"\n[{category}]")
        cat_results = {}
        for char in chars:
            encoding = tokenizer.encode(char)
            tokens = encoding.tokens
            n = len(tokens)
            cat_results[char] = {"tokens": tokens, "count": n}
            print(f"  {char} → {tokens} ({n} token{'s' if n > 1 else ''})")
        results[category] = cat_results

    return results


# ── 3. 主流程 ────────────────────────────────────────────────────────

def main():
    print("变体B：Tokenizer 重训练实验")
    print("构建语料...")

    build_corpus_file(BASE_CORPUS,     "data/corpus_baseline.txt")
    build_corpus_file(ENHANCED_CORPUS, "data/corpus_enhanced.txt")
    print(f"  baseline 语料：{len(BASE_CORPUS)} 行")
    print(f"  enhanced 语料：{len(ENHANCED_CORPUS)} 行")

    print("\n训练 baseline tokenizer...")
    tok_base = train_bpe("data/corpus_baseline.txt", "models/tokenizer_baseline.json")

    print("训练 enhanced tokenizer...")
    tok_enh  = train_bpe("data/corpus_enhanced.txt", "models/tokenizer_enhanced.json")

    # 评测
    res_base = evaluate(tok_base, "Baseline（无部首注释）")
    res_enh  = evaluate(tok_enh,  "Enhanced（含部首注释）")

    # 对比汇总
    print(f"\n{'='*50}")
    print("对比汇总：生僻字 token 数变化")
    print(f"{'='*50}")
    print(f"{'字':<6} {'baseline':>10} {'enhanced':>10} {'变化':>8}")
    print("-" * 40)

    summary = []
    for char in TEST_CHARS["生僻形声字"] + TEST_CHARS["叠加构字"] + TEST_CHARS["部首本身"]:
        b = res_base.get("生僻形声字", {}).get(char) or \
            res_base.get("叠加构字", {}).get(char) or \
            res_base.get("部首本身", {}).get(char)
        e = res_enh.get("生僻形声字", {}).get(char) or \
            res_enh.get("叠加构字", {}).get(char) or \
            res_enh.get("部首本身", {}).get(char)
        if b and e:
            diff = e["count"] - b["count"]
            flag = "✅ 改善" if diff < 0 else ("➡ 持平" if diff == 0 else "⚠ 增加")
            print(f"{char:<6} {b['count']:>10} {e['count']:>10} {diff:>+5}  {flag}")
            summary.append({"char": char, "baseline": b["count"], "enhanced": e["count"], "diff": diff})

    # 保存
    output = {
        "baseline": {k: {c: v for c, v in cat.items()} for k, cat in res_base.items()},
        "enhanced": {k: {c: v for c, v in cat.items()} for k, cat in res_enh.items()},
        "summary": summary,
    }
    with open("results/variant_B_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n结果已保存：results/variant_B_results.json")
    print("模型已保存：models/tokenizer_baseline.json")
    print("        models/tokenizer_enhanced.json")


if __name__ == "__main__":
    main()
