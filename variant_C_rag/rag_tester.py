#!/usr/bin/env python3
"""
变体C：RAG检索增强实验
核心问题：自动检索字典信息能否替代手工注入，复现变体A的效果？

对比三个条件：
  baseline     - 无任何字典信息
  manual       - 手工注入（变体A方式，直接写入prompt）
  rag          - 自动检索字典后注入（变体C）

期望结论：manual ≈ rag >> baseline
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional
import argparse

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

DICT_PATH = os.path.join(os.path.dirname(__file__), "char_dict.json")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def load_char_dict() -> dict:
    with open(DICT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["chars"]


def retrieve(char: str, char_dict: dict) -> Optional[dict]:
    """检索单个字的字典信息，未收录返回None（模拟检索失败）"""
    return char_dict.get(char)


def build_prompt(char: str, condition: str, char_dict: dict) -> str:
    """
    condition:
      baseline - 只给字，不给任何字典信息
      manual   - 手工方式直接写入所有信息（模拟变体A）
      rag      - 先检索再注入（变体C核心）
    """
    base_question = f"汉字「{char}」：\n1. 可能与什么含义/领域有关？\n2. 读音可能是什么？\n请分别回答，并说明你的推断依据。"

    if condition == "baseline":
        return base_question

    if condition == "manual":
        info = char_dict.get(char)
        if not info:
            return base_question
        return _build_enhanced_prompt(char, info, source="手工注入", base_question=base_question)

    if condition == "rag":
        info = retrieve(char, char_dict)
        if not info:
            return f"[检索结果：字典中未收录「{char}」]\n\n{base_question}"
        return _build_enhanced_prompt(char, info, source="字典检索", base_question=base_question)

    raise ValueError(f"未知condition: {condition}")


def _build_enhanced_prompt(char: str, info: dict, source: str, base_question: str) -> str:
    parts = [f"[{source}]"]
    if info.get("radical"):
        parts.append(f"部首：{info['radical']}")
    if info.get("phonetic"):
        parts.append(f"声旁：{info['phonetic']}")
    if info.get("pinyin"):
        parts.append(f"拼音：{info['pinyin']}")
    if info.get("meaning"):
        parts.append(f"释义参考：{info['meaning']}")
    header = "  |  ".join(parts)
    return f"{header}\n\n{base_question}"


@dataclass
class TestResult:
    char: str
    condition: str
    prompt: str
    response: str
    model: str
    latency_ms: float
    timestamp: str

    def to_dict(self):
        return asdict(self)


class ModelAPI:
    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        if provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("pip install anthropic")
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("未设置 ANTHROPIC_API_KEY")
            self.client = Anthropic(api_key=api_key)
            self.model = "claude-opus-4-7"
        elif provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("pip install openai")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("未设置 OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.model = "gpt-4o-mini"

    def generate(self, prompt: str) -> tuple[str, float]:
        start = time.time()
        if self.provider == "anthropic":
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            text = resp.content[0].text
        else:
            resp = self.client.chat.completions.create(
                model=self.model,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            text = resp.choices[0].message.content
        latency = (time.time() - start) * 1000
        return text, latency


# 变体C专属测试字集：覆盖形声字（有部首+声旁）和会意字（无声旁），对应变体A核心用例
TEST_CHARS = [
    "汸",   # 形声字，氵+方，罕见
    "炇",   # 形声字，火+攵，罕见
    "杻",   # 形声字，木+丑，罕见
    "犴",   # 形声字，犭+干，罕见
    "砯",   # 形声字，石+平，罕见
    "浯",   # 形声字，氵+吾，罕见（变体D核心字）
    "棻",   # 形声字，木+分，罕见
    "汭",   # 形声字，氵+内，罕见（H5声旁失效字）
    "虪",   # 会意字，三虎，无声旁
    "龘",   # 会意字，三龙，无声旁
]

CONDITIONS = ["baseline", "manual", "rag"]


def run_experiment(provider: str, chars: list = None, dry_run: bool = False):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    char_dict = load_char_dict()
    test_chars = chars or TEST_CHARS

    if dry_run:
        print("=== DRY RUN：只打印prompt，不调用API ===\n")
        for char in test_chars:
            for cond in CONDITIONS:
                prompt = build_prompt(char, cond, char_dict)
                print(f"[{char}] [{cond}]")
                print(prompt)
                print("-" * 50)
        return

    api = ModelAPI(provider)
    results = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    total = len(test_chars) * len(CONDITIONS)
    done = 0

    for char in test_chars:
        for cond in CONDITIONS:
            prompt = build_prompt(char, cond, char_dict)
            print(f"[{done+1}/{total}] 「{char}」 {cond} ...", end=" ", flush=True)
            try:
                response, latency = api.generate(prompt)
                result = TestResult(
                    char=char,
                    condition=cond,
                    prompt=prompt,
                    response=response,
                    model=api.model,
                    latency_ms=round(latency, 1),
                    timestamp=datetime.now().isoformat(),
                )
                results.append(result)
                print(f"✓ ({latency:.0f}ms)")
            except Exception as e:
                print(f"✗ 错误: {e}")
            done += 1
            time.sleep(0.5)

    out_path = os.path.join(RESULTS_DIR, f"results_variant_C_{provider}_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in results], f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存：{out_path}")
    print(f"共 {len(results)} 条，覆盖 {len(test_chars)} 个字 × {len(CONDITIONS)} 个条件")
    return out_path, results


def main():
    parser = argparse.ArgumentParser(description="变体C RAG实验")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic")
    parser.add_argument("--dry-run", action="store_true", help="只打印prompt，不调用API")
    parser.add_argument("--chars", nargs="+", help="指定测试字，默认使用预设字集")
    args = parser.parse_args()

    run_experiment(args.provider, chars=args.chars, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
