#!/usr/bin/env python3
"""
变体A：自动化测试脚本
支持通过API调用模型进行批量测试
"""

import json
import os
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import argparse

# 尝试导入anthropic SDK
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("警告: anthropic SDK 未安装，尝试运行: pip install anthropic")

# 尝试导入OpenAI SDK
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


@dataclass
class TestResult:
    """单次测试结果"""
    test_id: str
    character: str
    category: str
    prompt_type: str
    prompt_text: str
    model_name: str
    response: str
    latency_ms: float
    timestamp: str
    expected_answer: str

    def to_dict(self):
        return asdict(self)


class ModelAPI:
    """统一的模型API接口"""

    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        self.client = None

        if provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic SDK 未安装")
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("未设置 ANTHROPIC_API_KEY 环境变量")
            self.client = Anthropic(api_key=api_key)
            self.model = "claude-opus-4-7"

        elif provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("openai SDK 未安装")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("未设置 OPENAI_API_KEY 环境变量")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self.model = "gpt-4o-mini"

    def generate(self, prompt: str, max_tokens: int = 500) -> tuple[str, float]:
        """生成回答，返回(回答内容, 延迟ms)"""
        start_time = time.time()

        if self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text

        elif self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content

        latency = (time.time() - start_time) * 1000
        return content, latency


class AutomatedPromptExperiment:
    """自动化Prompt实验"""

    def __init__(self, test_cases_path: str, model_provider: str = "anthropic"):
        with open(test_cases_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.templates = self.data["prompt_templates"]
        self.model = ModelAPI(model_provider)
        self.results: List[TestResult] = []

    def build_prompt(self, case: Dict, template_type: str) -> str:
        """构建prompt"""
        template = self.templates.get(template_type, self.templates["baseline"])

        radical_hints = {
            "氵": "水、液体、河流",
            "火": "火、燃烧、热",
            "木": "树木、植物、木材",
            "犭": "动物、狗、兽类",
            "石": "石头、岩石、矿物",
            "讠": "语言、说话、文字",
            "忄": "心情、情感、心理",
            "扌": "手、动作、操作",
            "艹": "植物、草本、蔬菜",
            "禾": "禾苗、庄稼、谷物"
        }

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

    def run_single_test(self, case: Dict, category: str, prompt_type: str) -> TestResult:
        """运行单个测试"""
        prompt = self.build_prompt(case, prompt_type)

        print(f"  测试 {case['id']} - {prompt_type} ... ", end="", flush=True)

        try:
            response, latency = self.model.generate(prompt)
            print(f"✓ ({latency:.0f}ms)")

            return TestResult(
                test_id=case['id'],
                character=case.get('character', ''),
                category=category,
                prompt_type=prompt_type,
                prompt_text=prompt,
                model_name=self.model.model,
                response=response,
                latency_ms=latency,
                timestamp=datetime.now().isoformat(),
                expected_answer=case.get('expected_answer', case.get('correct_answer', ''))
            )
        except Exception as e:
            print(f"✗ 错误: {e}")
            return TestResult(
                test_id=case['id'],
                character=case.get('character', ''),
                category=category,
                prompt_type=prompt_type,
                prompt_text=prompt,
                model_name=self.model.model,
                response=f"ERROR: {e}",
                latency_ms=0,
                timestamp=datetime.now().isoformat(),
                expected_answer=case.get('expected_answer', case.get('correct_answer', ''))
            )

    def run_category(self, category: str, prompt_types: Optional[List[str]] = None):
        """运行一个类别的所有测试"""
        if prompt_types is None:
            prompt_types = ["baseline", "pinyin_only", "radical_only", "full_enhanced"]

        category_data = self.data["test_categories"].get(category)
        if not category_data:
            print(f"错误: 未知类别 {category}")
            return

        print(f"\n{'='*60}")
        print(f"类别: {category_data['description']}")
        print(f"用例数: {len(category_data['cases'])}")
        print(f"Prompt类型: {', '.join(prompt_types)}")
        print(f"{'='*60}\n")

        for case in category_data["cases"]:
            print(f"测试用例: {case['id']} ({case.get('character', '')})")
            for pt in prompt_types:
                result = self.run_single_test(case, category, pt)
                self.results.append(result)
                time.sleep(0.5)  # 避免请求过快

    def run_all(self, prompt_types: Optional[List[str]] = None):
        """运行所有类别的测试"""
        for category in self.data["test_categories"].keys():
            self.run_category(category, prompt_types)

    def save_results(self, output_path: str):
        """保存结果到JSON"""
        results_dict = {
            "metadata": {
                "model": self.model.model,
                "provider": self.model.provider,
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(self.results)
            },
            "results": [r.to_dict() for r in self.results]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到: {output_path}")

    def generate_report(self, output_path: str):
        """生成Markdown格式的实验报告"""
        lines = [
            "# 变体A实验报告：Prompt增强效果测试",
            "",
            f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**测试模型**: {self.model.model}",
            f"**总测试数**: {len(self.results)}",
            "",
            "## 测试设计",
            "",
            "本实验测试在不同prompt增强条件下，模型对生僻字的理解和推理能力。",
            "",
            "### Prompt类型",
            "",
            "| 类型 | 说明 |",
            "|------|------|",
            "| baseline | 无额外信息 |",
            "| pinyin_only | 只提供拼音 |",
            "| radical_only | 只提供部首 |",
            "| full_enhanced | 部首+声旁+拼音 |",
            "",
            "## 测试结果",
            ""
        ]

        # 按类别分组
        by_category = {}
        for r in self.results:
            cat = r.category
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(r)

        for cat_name, cat_results in by_category.items():
            cat_desc = self.data["test_categories"][cat_name]["description"]
            lines.extend([
                f"### {cat_desc}",
                ""
            ])

            # 按测试用例分组
            by_case = {}
            for r in cat_results:
                if r.test_id not in by_case:
                    by_case[r.test_id] = {}
                by_case[r.test_id][r.prompt_type] = r

            for case_id, case_results in by_case.items():
                char = case_results.get('baseline', case_results.get(list(case_results.keys())[0])).character
                lines.extend([
                    f"#### 用例 {case_id}: {char}",
                    "",
                    "| Prompt类型 | 模型回答 | 期望答案 |",
                    "|------------|----------|----------|"
                ])

                for pt in ["baseline", "pinyin_only", "radical_only", "full_enhanced", "expert_mode"]:
                    if pt in case_results:
                        r = case_results[pt]
                        # 截断长回答
                        response = r.response.replace('\n', ' ')[:100]
                        if len(r.response) > 100:
                            response += "..."
                        expected = r.expected_answer[:50] if r.expected_answer else "N/A"
                        lines.append(f"| {pt} | {response} | {expected} |")

                lines.append("")

        lines.extend([
            "## 观察与结论",
            "",
            "_待分析..._",
            "",
            "## 原始数据",
            "",
            "完整结果见: `results.json`",
            ""
        ])

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"报告已生成: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='自动化Prompt实验')
    parser.add_argument('--provider', type=str, default='anthropic',
                       choices=['anthropic', 'openai'],
                       help='模型提供商')
    parser.add_argument('--category', type=str,
                       help='只测试特定类别')
    parser.add_argument('--hard', action='store_true',
                       help='测试高难度用例（hard_cases）')
    parser.add_argument('--output-dir', type=str, default='results',
                       help='输出目录')

    args = parser.parse_args()

    # 检查环境变量
    if args.provider == 'anthropic' and not os.getenv('ANTHROPIC_API_KEY'):
        print("错误: 未设置 ANTHROPIC_API_KEY 环境变量")
        print("请运行: export ANTHROPIC_API_KEY='your-api-key'")
        return

    if args.provider == 'openai' and not os.getenv('OPENAI_API_KEY'):
        print("错误: 未设置 OPENAI_API_KEY 环境变量")
        return

    # 初始化实验
    try:
        experiment = AutomatedPromptExperiment('test_cases.json', args.provider)
    except Exception as e:
        print(f"初始化失败: {e}")
        return

    # 运行测试
    os.makedirs(args.output_dir, exist_ok=True)
    if args.category:
        experiment.run_category(args.category)
    elif args.hard:
        print("运行高难度用例（hard_cases）...")
        for sub in ['stacked_character_pronunciation', 'obscure_phonetic_compounds', 'phonetic_obsolescence']:
            experiment.run_category(sub)
    else:
        # 默认：核心类别
        print("运行核心测试类别...")
        experiment.run_category('radical_semantic_inference')
        experiment.run_category('phonetic_pronunciation_inference')
        experiment.run_category('combined_inference')

    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    results_path = os.path.join(args.output_dir, f'results_{args.provider}_{timestamp}.json')
    experiment.save_results(results_path)

    report_path = os.path.join(args.output_dir, f'report_{args.provider}_{timestamp}.md')
    experiment.generate_report(report_path)

    print(f"\n实验完成!")
    print(f"  结果: {results_path}")
    print(f"  报告: {report_path}")


if __name__ == "__main__":
    main()
