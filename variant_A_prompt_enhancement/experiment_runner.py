#!/usr/bin/env python3
"""
变体A：Prompt增强实验运行器

使用方法:
    python experiment_runner.py --model claude --category radical_semantic_inference
    python experiment_runner.py --model gpt4 --all
"""

import json
import argparse
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExperimentResult:
    """单次实验结果"""
    test_id: str
    character: str
    prompt_type: str  # baseline, pinyin_only, radical_only, full_enhanced
    question: str
    model_response: str
    expected_answer: str
    timestamp: str

    def to_dict(self):
        return {
            "test_id": self.test_id,
            "character": self.character,
            "prompt_type": self.prompt_type,
            "question": self.question,
            "model_response": self.model_response,
            "expected_answer": self.expected_answer,
            "timestamp": self.timestamp
        }


class DictionaryEnhancedPromptExperiment:
    """字典增强Prompt实验框架"""

    def __init__(self, test_cases_path: str):
        with open(test_cases_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.templates = self.data["prompt_templates"]
        self.results: List[ExperimentResult] = []

    def build_prompt(self, case: Dict, template_type: str) -> str:
        """构建不同类型的prompt"""
        template = self.templates.get(template_type, self.templates["baseline"])

        # 部首提示映射
        radical_hints = {
            "氵": "水、液体、河流",
            "火": "火、燃烧、热",
            "木": "树木、植物、木材",
            "犭": "动物、狗、兽类",
            "石": "石头、岩石、矿物",
            "讠": "语言、说话、文字",
            "忄": "心情、情感、心理",
            "扌": "手、动作、操作",
            "艹": "植物、草本、蔬菜"
        }

        # 基础格式化
        prompt = template.format(
            character=case.get("character", ""),
            question=case.get("question", ""),
            pinyin=case.get("pinyin", ""),
            radical=case.get("radical", ""),
            phonetic=case.get("phonetic", ""),
            radical_hint=radical_hints.get(case.get("radical", ""), "某个类别"),
            phonetic_pinyin=case.get("pinyin", ""),
            radical_meaning=radical_hints.get(case.get("radical", ""), "某个事物")
        )

        return prompt

    def manual_test(self, category: str, template_type: str = "baseline"):
        """
        手动测试模式 - 打印prompt供你复制到Claude/GPT-4测试

        Args:
            category: 测试类别，如 "radical_semantic_inference"
            template_type: prompt模板类型
        """
        category_data = self.data["test_categories"].get(category)
        if not category_data:
            print(f"错误：未知类别 {category}")
            print(f"可用类别: {list(self.data['test_categories'].keys())}")
            return

        print(f"\n{'='*80}")
        print(f"类别: {category_data['description']}")
        print(f"Prompt类型: {template_type}")
        print(f"{'='*80}\n")

        for case in category_data["cases"]:
            prompt = self.build_prompt(case, template_type)

            print(f"\n{'-'*60}")
            print(f"测试用例: {case['id']} | 目标字: {case['character']}")
            print(f"期望答案: {case.get('expected_answer', case.get('correct_answer', 'N/A'))}")
            print(f"{'-'*60}")
            print(f"\n【PROMPT】\n{prompt}\n")
            print("【请复制以上prompt到你的模型测试】\n")

    def compare_prompts(self, case_id: str):
        """
        对比同一测试用例在不同prompt下的差异
        """
        # 找到测试用例
        target_case = None
        category_name = None

        for cat_name, cat_data in self.data["test_categories"].items():
            for case in cat_data["cases"]:
                if case["id"] == case_id:
                    target_case = case
                    category_name = cat_name
                    break
            if target_case:
                break

        if not target_case:
            print(f"错误：未找到测试用例 {case_id}")
            return

        print(f"\n{'='*80}")
        print(f"对比测试: {case_id} ({target_case['character']})")
        print(f"{'='*80}\n")

        prompt_types = ["baseline", "pinyin_only", "radical_only", "full_enhanced", "expert_mode"]

        for pt in prompt_types:
            prompt = self.build_prompt(target_case, pt)
            print(f"\n{'='*60}")
            print(f"Prompt类型: {pt}")
            print(f"{'='*60}\n{prompt}\n")

    def variant_d_prompts(self, case_id: str):
        """
        生成变体D（对比破坏型）的4组 prompt
        """
        cases = self.data.get("variant_D_cases", {}).get("cases", [])
        target = next((c for c in cases if c["id"] == case_id), None)
        if not target:
            print(f"错误：未找到变体D用例 {case_id}")
            available = [c["id"] for c in cases]
            print(f"可用ID: {available}")
            return

        char = target["character"]
        question = target.get("question", "请根据以下信息推断这个汉字的意思和读音")

        print(f"\n{'='*80}")
        print(f"变体D对比测试：{case_id} ({char})")
        print(f"核心目的：改变部首/声旁，观察推断方向是否相应偏转")
        print(f"{'='*80}")

        groups = {
            "A（对照：正确部首+正确声旁）": {
                "radical": target.get("correct_radical", ""),
                "phonetic": target.get("correct_phonetic", ""),
                "expected": target.get("result_A", "")
            },
            "B（错误部首+正确声旁）→ 测语义干扰": {
                "radical": target.get("wrong_radical_for_B", ""),
                "phonetic": target.get("correct_phonetic", ""),
                "expected": target.get("result_B", "")
            },
            "C（正确部首+错误声旁）→ 测读音干扰": {
                "radical": target.get("correct_radical", ""),
                "phonetic": target.get("wrong_phonetic_for_C", ""),
                "expected": target.get("result_C", "")
            },
            "D（只有部首，无声旁）": {
                "radical": target.get("correct_radical", ""),
                "phonetic": None,
                "expected": "语义正确，读音未知（诚实）"
            },
        }

        for group_name, info in groups.items():
            print(f"\n{'─'*60}")
            print(f"【{group_name}】")
            if info["expected"]:
                print(f"预期结果：{info['expected']}")
            print(f"{'─'*60}")
            if info["phonetic"]:
                prompt = (
                    f"{question}：\n\n"
                    f"目标字：{char}（部首：{info['radical']}，声旁：{info['phonetic']}）\n\n"
                    f"提示：这是一个形声字，形旁表意，声旁表音。"
                )
            else:
                prompt = (
                    f"{question}：\n\n"
                    f"目标字：{char}（部首：{info['radical']}，无声旁信息）\n\n"
                    f"提示：只根据部首信息推断语义，读音无法从字形推断。"
                )
            print(f"\n{prompt}\n")

    def list_test_cases(self):
        """列出所有可用的测试用例"""
        print("\n可用测试类别:")
        for cat_name, cat_data in self.data["test_categories"].items():
            print(f"\n  {cat_name}:")
            print(f"    描述: {cat_data['description']}")
            print(f"    用例数: {len(cat_data['cases'])}")
            for case in cat_data["cases"]:
                char = case.get('character', case.get('options', ['N/A'])[0] if 'options' in case else '填空')
                print(f"      - {case['id']}: {char} ({case.get('question', '填空')[:30]}...)")

        vd = self.data.get("variant_D_cases", {})
        if vd:
            print(f"\n  变体D（对比破坏型）:")
            print(f"    描述: {vd.get('description', '')}")
            for c in vd.get("cases", []):
                print(f"      - {c['id']}: {c['character']} | 正确读音:{c.get('correct_pinyin','')} | 错误部首:{c.get('wrong_radical_for_B','')} 错误声旁:{c.get('wrong_phonetic_for_C','')}")


def main():
    parser = argparse.ArgumentParser(description='字典增强Prompt实验')
    parser.add_argument('--list', action='store_true', help='列出所有测试用例')
    parser.add_argument('--category', type=str, help='测试类别')
    parser.add_argument('--case', type=str, help='特定测试用例ID')
    parser.add_argument('--prompt-type', type=str, default='baseline',
                       choices=['baseline', 'pinyin_only', 'radical_only', 'full_enhanced', 'expert_mode'],
                       help='Prompt模板类型')
    parser.add_argument('--compare', action='store_true', help='对比同一用例的所有prompt类型')
    parser.add_argument('--variant-d', action='store_true', help='生成变体D（对比破坏型）的4组prompt')

    args = parser.parse_args()

    # 初始化实验
    experiment = DictionaryEnhancedPromptExperiment('test_cases.json')

    if args.list:
        experiment.list_test_cases()

    elif args.variant_d and args.case:
        experiment.variant_d_prompts(args.case)

    elif args.compare and args.case:
        experiment.compare_prompts(args.case)

    elif args.category:
        experiment.manual_test(args.category, args.prompt_type)

    elif args.case:
        # 找到并测试特定用例
        for cat_name, cat_data in experiment.data["test_categories"].items():
            for case in cat_data["cases"]:
                if case["id"] == args.case:
                    experiment.manual_test(cat_name, args.prompt_type)
                    return
        print(f"未找到用例: {args.case}")

    else:
        # 默认：列出所有信息
        print("字典增强Prompt实验 - 变体A")
        print("\n使用方式:")
        print("  1. 查看所有测试用例: python experiment_runner.py --list")
        print("  2. 运行特定类别: python experiment_runner.py --category radical_semantic_inference")
        print("  3. 对比不同prompt: python experiment_runner.py --case R1 --compare")
        print("  4. 使用增强prompt: python experiment_runner.py --category radical_semantic_inference --prompt-type full_enhanced")
        print("  5. 生成变体D破坏测试: python experiment_runner.py --case D_FU --variant-d")


if __name__ == "__main__":
    main()
