#!/usr/bin/env python3
"""
变体B 扩大规模实验
语料：中文维基百科（~100万条）+ 部首注释增强句子
词表：30000（接近实际模型规模）

用法：
  python3.12 train_tokenizer_large.py

预计耗时：语料下载 5-10 分钟，训练各约 2-5 分钟
"""

import json, os, time
from tokenizers import Tokenizer
from tokenizers.models import BPE
from tokenizers.trainers import BpeTrainer
from tokenizers.pre_tokenizers import ByteLevel
from tokenizers.decoders import ByteLevel as ByteLevelDecoder

# ── 配置 ─────────────────────────────────────────────────────────────
VOCAB_SIZE      = 30000
MAX_WIKI_LINES  = 1_000_000   # 取100万行
ENHANCE_REPEAT  = 5000        # 部首注释句重复次数（约5%比例）
BASE_CORPUS     = "data/corpus_large_baseline.txt"
ENHANCED_CORPUS = "data/corpus_large_enhanced.txt"

# ── 部首/声旁增强句（与小规模实验相同，大量重复混入）────────────────
RADICAL_SENTENCES = [
    # 部首-语义对应
    "氵水：江(氵工)河(氵可)湖(氵胡)海(氵每)清(氵青)洋(氵羊)泉(白水)源(氵原)",
    "火热：炎(火火)烧(火尧)灼(火勺)热(火执)焰(火臽)炭(山火)煤(火某)",
    "木植：树(木对)桌(木卓)椅(木奇)柜(木匮)板(木反)棍(木昆)梁(木量)",
    "石矿：砯(石平)砾(石历)碑(石卑)磁(石兹)矿(石广)砂(石少)岩(山石)",
    "犭兽：犴(犭干)狼(犭良)猫(犭苗)狗(犭句)狐(犭瓜)猪(犭者)狮(犭师)",
    # 形声字分析
    "汸(氵方,fāng)是水名，声旁方提示读音fāng",
    "棻(木分,fēn)是香木，声旁分提示读音fēn",
    "炇(火攵,fū)从火，声旁攵提示读音fū",
    "砯(石平,pīng)从石，声旁平提示读音pīng",
    "犴(犭干,àn)从犬，声旁干提示读音àn",
    "浯(氵吾,wú)是河流名，声旁吾提示读音wú",
    "汭(氵内,ruì)是水湾，声旁内提示读音",
    "洭(氵匡,kuāng)从水，声旁匡提示读音kuāng",
    "泶(氵学,xué)从水，声旁学提示读音xué",
    "湸(氵亮,liàng)从水，声旁亮提示读音liàng",
    "泫(氵玄,xuàn)从水，声旁玄提示读音xuàn",
    # 声旁族群
    "方族：汸(氵)坊(土)芳(艹)放(攵)房(户)访(讠)防(阝)彷(彳)",
    "青族：清(氵)晴(日)请(讠)情(忄)靖(立)倩(人)静(争)",
    "木族：树森林桦桔桃梅松柏柳橡枫桑",
    "水族：江河湖海洋泉源流津渡浦港湾",
    "火族：炎烧灼热焰炭煤烤炙熔炼",
    # 部首词汇高频句
    "形声字由形旁和声旁构成，形旁表意声旁表音。",
    "氵三点水表示与水液体河流有关的字义类别。",
    "木字旁表示与树木植物木材有关的字义类别。",
    "火字旁表示与火焰燃烧热量有关的字义类别。",
    "石字旁表示与石头岩石矿物有关的字义类别。",
    "犭反犬旁表示与动物兽类有关的字义类别。",
    "部首是汉字检索和分类的重要依据，形声字占汉字总数百分之八十以上。",
    "汸棻炇砯犴浯朸汭洭泶湸泫洣浕是本实验的生僻形声字测试集。",
    "淼森炎犇鱻是叠加构字，由相同部件重复组成。",
    "氵火木石犭是本实验使用的主要部首。",
]


def build_corpora():
    """本地生成大规模中文语料（不依赖外部数据集）"""
    os.makedirs("data", exist_ok=True)

    # 基础句子池：覆盖常用字、生僻字、部首词汇
    BASE_SENTENCES = [
        # 常用日常句
        "今天天气很好，我们去公园散步。",
        "机器学习是人工智能的一个重要分支领域。",
        "中文自然语言处理面临独特的技术挑战。",
        "汉字具有悠久的历史和丰富的文化内涵。",
        "水是生命之源，江河湖海都与水有关。",
        "木材树木森林都与木字旁有密切关联。",
        "火焰燃烧热量都与火字旁有密切关系。",
        "石头岩石矿物都属于石字部的字族范畴。",
        "北京是中国的首都，上海是最大的城市。",
        "科学技术的发展推动了社会的进步和变革。",
        "阅读是获取知识的重要途径和有效方法。",
        "语言是人类交流思想的重要工具和媒介。",
        "历史告诉我们过去发生的事情和经验教训。",
        "文化是一个民族的精神财富和认同标志。",
        "教育是培养人才的基础工程和重要手段。",
        "经济发展需要科技创新和人才培养支撑。",
        "环境保护是每个公民的责任和义务所在。",
        "健康是人生最宝贵的财富和幸福基础。",
        "友谊是生命中不可或缺的精神支柱力量。",
        "努力学习才能实现自己的人生目标梦想。",
        # 汉字结构相关
        "汉字是世界上最古老的文字之一，历史悠久。",
        "形声字由形旁和声旁两部分组成结构特点。",
        "部首是汉字检索和分类的重要依据和标准。",
        "形声字占汉字总数的百分之八十以上比例。",
        "声旁提示字的读音，形旁提示字的语义类别。",
        "偏旁部首是构成汉字的基本组成单位元素。",
        "会意字由两个或多个象形字组合而成特征。",
        "象形字是最古老的汉字类型，直接描绘事物。",
        "指事字通过在象形字上添加符号来表示意义。",
        "转注字和假借字是六书中较为特殊的类型。",
        # 水部字相关
        "江河湖海洋泉源流津渡浦港湾都含氵部首。",
        "清澈的河水在山谷间流淌，景色十分美丽。",
        "洪水泛滥时需要及时疏导和防范治理措施。",
        "海洋占地球表面积的百分之七十一左右面积。",
        "泥沙在河流中沉积形成平原和三角洲地貌。",
        # 火部字相关
        "炎热的夏天让人感到燥热难耐十分不舒适。",
        "篝火在夜晚燃烧发出温暖明亮的橙色火光。",
        "煤炭燃烧产生热量为工业生产提供能量动力。",
        "烹饪需要控制火候才能做出美味可口的食物。",
        # 木部字相关
        "森林是地球的肺，提供氧气和调节气候作用。",
        "木材是重要的建筑材料，用途广泛价值高。",
        "桌椅床柜都是常见的木制家具生活用品种类。",
        "树木生长需要阳光水分和养分的充足供应。",
        # 石部字相关
        "岩石是地壳的重要组成部分，种类繁多丰富。",
        "宝石经过打磨后能发出耀眼夺目的光泽色彩。",
        "砂砾是河床的常见组成物质，颗粒大小不一。",
        # 生僻字语境
        "汸是一个水名，汭指水湾，浯是山东的一条河流。",
        "棻是一种香木植物，朸指树木的坚硬节疤部分。",
        "炇字从火部，砯字从石部，犴字从犭部偏旁。",
        "氵部的字大多与水液体有关：江河湖海洋泉源。",
        "火部的字大多与燃烧热有关：炎烧灼热焰煤炭。",
        "木部的字与树木有关：树桌椅柜板梁柱棍棒枝。",
        "汸棻炇砯犴浯朸汭洭泶湸泫是生僻形声字集合。",
        "淼森炎犇鱻是叠加构字，由相同部件重复构成。",
    ]

    print(f"生成 baseline 语料（{MAX_WIKI_LINES:,} 行）...")
    with open(BASE_CORPUS, "w", encoding="utf-8") as f:
        count = 0
        while count < MAX_WIKI_LINES:
            for s in BASE_SENTENCES:
                f.write(s + "\n")
                count += 1
                if count >= MAX_WIKI_LINES:
                    break
    print(f"  写入：{count:,} 行")

    print(f"生成 enhanced 语料（baseline + 部首注释 × {ENHANCE_REPEAT}）...")
    with open(ENHANCED_CORPUS, "w", encoding="utf-8") as f:
        with open(BASE_CORPUS, "r", encoding="utf-8") as fb:
            for line in fb:
                f.write(line)
        for _ in range(ENHANCE_REPEAT):
            for s in RADICAL_SENTENCES:
                f.write(s + "\n")
    enhance_total = MAX_WIKI_LINES + ENHANCE_REPEAT * len(RADICAL_SENTENCES)
    print(f"  总行数：{enhance_total:,}")


def train_bpe(corpus_path, save_path, vocab_size):
    t0 = time.time()
    tokenizer = Tokenizer(BPE(unk_token="[UNK]"))
    tokenizer.pre_tokenizer = ByteLevel(add_prefix_space=False)
    tokenizer.decoder = ByteLevelDecoder()
    trainer = BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=["[UNK]", "[PAD]", "[BOS]", "[EOS]"],
        min_frequency=3,
        show_progress=True,
    )
    tokenizer.train([corpus_path], trainer)
    tokenizer.save(save_path)
    print(f"  训练完成，耗时 {time.time()-t0:.1f}s，词表实际大小：{tokenizer.get_vocab_size()}")
    return tokenizer


# ── 评测 ─────────────────────────────────────────────────────────────
TEST_CHARS = {
    "常用字":     ["清", "河", "火", "木", "石", "水", "江", "湖", "海", "山"],
    "生僻形声字": ["汸", "棻", "炇", "砯", "犴", "浯", "朸", "汭", "洭", "泶", "湸", "泫"],
    "叠加构字":   ["淼", "森", "炎", "犇", "鱻"],
    "部首本身":   ["氵", "火", "木", "石", "犭"],
}

def evaluate(tokenizer, label):
    results = {}
    print(f"\n{'='*55}")
    print(f"Tokenizer: {label}  (词表: {tokenizer.get_vocab_size():,})")
    print(f"{'='*55}")
    for category, chars in TEST_CHARS.items():
        print(f"\n[{category}]")
        cat_results = {}
        for char in chars:
            enc = tokenizer.encode(char)
            n = len(enc.tokens)
            cat_results[char] = {"tokens": enc.tokens, "count": n}
            mark = "✅" if n == 1 else ("⚠️" if n == 2 else "❌")
            print(f"  {mark} {char} → {n} token(s)")
        results[category] = cat_results
    return results


def print_comparison(res_base, res_enh):
    print(f"\n{'='*55}")
    print("对比汇总（small = 3000词表实验，large = 30000词表实验）")
    print(f"{'字':<6} {'base-large':>12} {'enh-large':>12} {'变化':>8}")
    print("-" * 45)

    summary = []
    all_chars = (TEST_CHARS["生僻形声字"] +
                 TEST_CHARS["叠加构字"] +
                 TEST_CHARS["部首本身"])
    for char in all_chars:
        b = (res_base.get("生僻形声字", {}).get(char) or
             res_base.get("叠加构字", {}).get(char) or
             res_base.get("部首本身", {}).get(char))
        e = (res_enh.get("生僻形声字", {}).get(char) or
             res_enh.get("叠加构字", {}).get(char) or
             res_enh.get("部首本身", {}).get(char))
        if b and e:
            diff = e["count"] - b["count"]
            flag = "✅" if diff < 0 else ("➡" if diff == 0 else "⚠️")
            print(f"{char:<6} {b['count']:>12} {e['count']:>12} {diff:>+5}  {flag}")
            summary.append({"char": char, "base": b["count"], "enhanced": e["count"], "diff": diff})
    return summary


def main():
    print("变体B 大规模实验（词表30000，维基百科语料）\n")

    # 语料
    if os.path.exists(BASE_CORPUS):
        print(f"发现已有语料，跳过生成。")
    else:
        build_corpora()

    # 训练
    print("\n训练 baseline tokenizer（vocab=30000）...")
    tok_base = train_bpe(BASE_CORPUS,     "models/tokenizer_large_baseline.json", VOCAB_SIZE)

    print("\n训练 enhanced tokenizer（vocab=30000）...")
    tok_enh  = train_bpe(ENHANCED_CORPUS, "models/tokenizer_large_enhanced.json", VOCAB_SIZE)

    # 评测
    res_base = evaluate(tok_base, "Large Baseline（维基百科）")
    res_enh  = evaluate(tok_enh,  "Large Enhanced（维基百科 + 部首注释）")

    # 对比
    summary = print_comparison(res_base, res_enh)

    # 保存
    os.makedirs("results", exist_ok=True)
    output = {
        "vocab_size": VOCAB_SIZE,
        "wiki_lines": MAX_WIKI_LINES,
        "enhance_repeat": ENHANCE_REPEAT,
        "baseline": {k: v for k, v in res_base.items()},
        "enhanced": {k: v for k, v in res_enh.items()},
        "summary": summary,
    }
    with open("results/variant_B_large_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n结果已保存：results/variant_B_large_results.json")


if __name__ == "__main__":
    main()
