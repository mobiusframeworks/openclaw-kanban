#!/usr/bin/env python3
"""
Routing Benchmark - Test speed, coordination, and accuracy across providers.

Tests:
1. Speed - Latency comparison across providers
2. Coordination - Routing decision consistency
3. Accuracy - Response quality for different task types

Usage:
    python routing_benchmark.py
    python routing_benchmark.py --quick    # Abbreviated test
    python routing_benchmark.py --provider ollama  # Test single provider
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from task_router import KanbanRouter
from hermes_bridge import HermesBridge


@dataclass
class BenchmarkResult:
    """Result of a single benchmark test."""
    provider: str
    model: str
    task_type: str
    prompt: str
    latency_ms: int
    success: bool
    response_length: int
    response_preview: str
    error: str = ""


@dataclass
class AccuracyTest:
    """Test with expected answer for accuracy checking."""
    prompt: str
    task_type: str
    expected_contains: List[str]  # Response should contain these
    complexity: str  # "simple", "medium", "complex"


class RoutingBenchmark:
    """Benchmark routing systems for speed, coordination, and accuracy."""

    # Test prompts by task type
    SPEED_TESTS = [
        ("What is 2 + 2?", "math", "simple"),
        ("Summarize: The quick brown fox jumps over the lazy dog.", "summarization", "simple"),
        ("Classify this as positive or negative: I love this product!", "classification", "simple"),
        ("List 3 benefits of exercise.", "general", "simple"),
        ("What is the capital of France?", "factual", "simple"),
    ]

    ACCURACY_TESTS = [
        AccuracyTest(
            prompt="What is 15 * 7?",
            task_type="math",
            expected_contains=["105"],
            complexity="simple"
        ),
        AccuracyTest(
            prompt="Is this sentiment positive or negative: 'This is the worst day ever'",
            task_type="classification",
            expected_contains=["negative"],
            complexity="simple"
        ),
        AccuracyTest(
            prompt="What programming language is known for its use in data science and has libraries like pandas and numpy?",
            task_type="factual",
            expected_contains=["python", "Python"],
            complexity="simple"
        ),
        AccuracyTest(
            prompt="Summarize in one sentence: Bitcoin is a decentralized digital currency that operates without a central bank or single administrator.",
            task_type="summarization",
            expected_contains=["bitcoin", "Bitcoin", "decentralized", "digital", "currency"],
            complexity="medium"
        ),
        AccuracyTest(
            prompt="What are 3 key differences between Python and JavaScript?",
            task_type="comparison",
            expected_contains=["type", "syntax", "browser", "server", "indent", "semicolon"],
            complexity="medium"
        ),
    ]

    # Coordination tests - should route consistently
    COORDINATION_TESTS = [
        "Summarize this meeting notes",
        "Research the latest trends in AI",
        "Implement a new feature for the dashboard",
        "Fix the bug in the login page",
        "Classify these emails by priority",
        "git commit and push changes",
        "Analyze the sales data for Q1",
    ]

    def __init__(self):
        self.router = KanbanRouter()
        self.bridge = HermesBridge()
        self.results: List[BenchmarkResult] = []

    def _test_ollama(self, prompt: str, model: str = "qwen2.5:7b") -> BenchmarkResult:
        """Test Ollama provider."""
        start = time.time()
        result = self.bridge.execute_ollama(prompt, model=model)
        latency = int((time.time() - start) * 1000)

        return BenchmarkResult(
            provider="ollama",
            model=model,
            task_type="",
            prompt=prompt[:50],
            latency_ms=latency,
            success=result.success,
            response_length=len(result.content),
            response_preview=result.content[:100] if result.content else "",
            error=result.error or ""
        )

    def _test_hermes(self, prompt: str, skill: str = None) -> BenchmarkResult:
        """Test Hermes provider."""
        start = time.time()
        if skill:
            result = self.bridge.execute_hermes_cli(prompt, skill=skill)
        else:
            result = self.bridge.execute(prompt, prefer_hermes=True)
        latency = int((time.time() - start) * 1000)

        return BenchmarkResult(
            provider="hermes",
            model=f"hermes:{skill}" if skill else "hermes",
            task_type="",
            prompt=prompt[:50],
            latency_ms=latency,
            success=result.success,
            response_length=len(result.content),
            response_preview=result.content[:100] if result.content else "",
            error=result.error or ""
        )

    def _test_openrouter(self, prompt: str, model: str = "nvidia/nemotron-3-nano-30b-a3b:free") -> BenchmarkResult:
        """Test OpenRouter provider."""
        start = time.time()
        result = self.router.execute_openrouter(prompt, model=model)
        latency = int((time.time() - start) * 1000)

        return BenchmarkResult(
            provider="openrouter",
            model=model.split("/")[-1][:30],
            task_type="",
            prompt=prompt[:50],
            latency_ms=latency,
            success=result.get("success", False),
            response_length=len(result.get("content", "")),
            response_preview=result.get("content", "")[:100],
            error=result.get("error", "")
        )

    def run_speed_tests(self, providers: List[str] = None) -> Dict[str, Any]:
        """Run speed benchmark across providers."""
        if providers is None:
            providers = ["ollama", "openrouter"]

        print("\n" + "=" * 70)
        print("  SPEED BENCHMARK")
        print("=" * 70)

        results_by_provider = {p: [] for p in providers}

        for prompt, task_type, complexity in self.SPEED_TESTS:
            print(f"\n  Testing: {prompt[:40]}...")

            for provider in providers:
                try:
                    if provider == "ollama":
                        result = self._test_ollama(prompt)
                    elif provider == "hermes":
                        result = self._test_hermes(prompt)
                    elif provider == "openrouter":
                        result = self._test_openrouter(prompt)
                    else:
                        continue

                    result.task_type = task_type
                    results_by_provider[provider].append(result)
                    self.results.append(result)

                    status = "OK" if result.success else "FAIL"
                    print(f"    {provider:12} {result.latency_ms:5}ms [{status}]")

                except Exception as e:
                    print(f"    {provider:12} ERROR: {str(e)[:40]}")

        # Calculate averages
        summary = {}
        for provider, results in results_by_provider.items():
            if results:
                successful = [r for r in results if r.success]
                summary[provider] = {
                    "total_tests": len(results),
                    "successful": len(successful),
                    "avg_latency_ms": sum(r.latency_ms for r in successful) / len(successful) if successful else 0,
                    "min_latency_ms": min(r.latency_ms for r in successful) if successful else 0,
                    "max_latency_ms": max(r.latency_ms for r in successful) if successful else 0,
                }

        return summary

    def run_accuracy_tests(self, providers: List[str] = None) -> Dict[str, Any]:
        """Run accuracy benchmark."""
        if providers is None:
            providers = ["ollama", "openrouter"]

        print("\n" + "=" * 70)
        print("  ACCURACY BENCHMARK")
        print("=" * 70)

        results_by_provider = {p: {"correct": 0, "total": 0, "details": []} for p in providers}

        for test in self.ACCURACY_TESTS:
            print(f"\n  Testing: {test.prompt[:40]}...")
            print(f"  Expected: contains one of {test.expected_contains[:3]}")

            for provider in providers:
                try:
                    if provider == "ollama":
                        result = self._test_ollama(test.prompt)
                    elif provider == "hermes":
                        result = self._test_hermes(test.prompt)
                    elif provider == "openrouter":
                        result = self._test_openrouter(test.prompt)
                    else:
                        continue

                    # Check accuracy
                    response_lower = result.response_preview.lower()
                    is_correct = any(exp.lower() in response_lower for exp in test.expected_contains)

                    results_by_provider[provider]["total"] += 1
                    if is_correct:
                        results_by_provider[provider]["correct"] += 1

                    results_by_provider[provider]["details"].append({
                        "prompt": test.prompt[:30],
                        "correct": is_correct,
                        "response": result.response_preview[:50]
                    })

                    status = "CORRECT" if is_correct else "WRONG"
                    print(f"    {provider:12} [{status:7}] {result.response_preview[:40]}...")

                except Exception as e:
                    print(f"    {provider:12} ERROR: {str(e)[:40]}")
                    results_by_provider[provider]["total"] += 1

        # Calculate accuracy percentages
        summary = {}
        for provider, data in results_by_provider.items():
            total = data["total"] or 1
            summary[provider] = {
                "correct": data["correct"],
                "total": data["total"],
                "accuracy_pct": (data["correct"] / total) * 100
            }

        return summary

    def run_coordination_tests(self) -> Dict[str, Any]:
        """Test routing decision consistency."""
        print("\n" + "=" * 70)
        print("  COORDINATION BENCHMARK (Routing Decisions)")
        print("=" * 70)

        decisions = []

        for prompt in self.COORDINATION_TESTS:
            routing = self.router.should_use_local(prompt)
            decisions.append({
                "prompt": prompt[:40],
                "provider": routing.provider,
                "model": routing.model[:25],
                "complexity": routing.complexity,
                "task_type": routing.task_type,
                "use_local": routing.use_local
            })

            tier_emoji = {"hermes": "🔧", "ollama": "🏠", "openrouter": "☁️", "claude": "🤖"}.get(routing.provider, "?")
            print(f"  {tier_emoji} [{routing.provider:10}] {routing.model:25} | {prompt[:35]}...")

        # Analyze consistency
        local_count = sum(1 for d in decisions if d["use_local"])
        cloud_count = len(decisions) - local_count

        return {
            "total_tasks": len(decisions),
            "local_routed": local_count,
            "cloud_routed": cloud_count,
            "local_percentage": (local_count / len(decisions)) * 100,
            "decisions": decisions
        }

    def run_full_benchmark(self, quick: bool = False) -> Dict[str, Any]:
        """Run all benchmarks."""
        print("\n" + "=" * 70)
        print("  HERMES + OPENCLAW ROUTING BENCHMARK")
        print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("=" * 70)

        # Check provider availability
        print("\n  Provider Status:")
        providers_available = []

        if self.bridge.check_ollama_available():
            print("    Ollama:     OK")
            providers_available.append("ollama")
        else:
            print("    Ollama:     UNAVAILABLE")

        if self.router.openrouter_api_key:
            print("    OpenRouter: OK")
            providers_available.append("openrouter")
        else:
            print("    OpenRouter: NO API KEY")

        if self.bridge.check_hermes_available():
            print("    Hermes:     OK")
            # Don't add hermes to speed tests by default (slower due to CLI overhead)
        else:
            print("    Hermes:     UNAVAILABLE")

        if not providers_available:
            print("\n  ERROR: No providers available for testing!")
            return {}

        # Run benchmarks
        results = {
            "timestamp": datetime.now().isoformat(),
            "providers_tested": providers_available
        }

        # Speed tests
        results["speed"] = self.run_speed_tests(providers_available)

        # Accuracy tests (skip some if quick mode)
        if quick:
            self.ACCURACY_TESTS = self.ACCURACY_TESTS[:2]
        results["accuracy"] = self.run_accuracy_tests(providers_available)

        # Coordination tests
        results["coordination"] = self.run_coordination_tests()

        # Print summary
        self._print_summary(results)

        return results

    def _print_summary(self, results: Dict[str, Any]):
        """Print benchmark summary."""
        print("\n" + "=" * 70)
        print("  BENCHMARK SUMMARY")
        print("=" * 70)

        # Speed summary
        print("\n  SPEED (Average Latency):")
        for provider, data in results.get("speed", {}).items():
            print(f"    {provider:12} {data['avg_latency_ms']:6.0f}ms  "
                  f"(min: {data['min_latency_ms']}ms, max: {data['max_latency_ms']}ms)")

        # Accuracy summary
        print("\n  ACCURACY:")
        for provider, data in results.get("accuracy", {}).items():
            print(f"    {provider:12} {data['accuracy_pct']:5.1f}%  "
                  f"({data['correct']}/{data['total']} correct)")

        # Coordination summary
        coord = results.get("coordination", {})
        print(f"\n  COORDINATION:")
        print(f"    Local routing:  {coord.get('local_percentage', 0):.1f}%")
        print(f"    Cloud routing:  {100 - coord.get('local_percentage', 0):.1f}%")

        # Winner determination
        print("\n  RECOMMENDATIONS:")
        speed_data = results.get("speed", {})
        if speed_data:
            fastest = min(speed_data.items(), key=lambda x: x[1].get("avg_latency_ms", 9999))
            print(f"    Fastest:     {fastest[0]} ({fastest[1]['avg_latency_ms']:.0f}ms avg)")

        accuracy_data = results.get("accuracy", {})
        if accuracy_data:
            most_accurate = max(accuracy_data.items(), key=lambda x: x[1].get("accuracy_pct", 0))
            print(f"    Most Accurate: {most_accurate[0]} ({most_accurate[1]['accuracy_pct']:.1f}%)")

        print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Routing Benchmark")
    parser.add_argument("--quick", action="store_true", help="Run abbreviated tests")
    parser.add_argument("--provider", type=str, help="Test single provider")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    benchmark = RoutingBenchmark()

    if args.provider:
        # Test single provider
        print(f"\nTesting single provider: {args.provider}")
        if args.provider == "ollama":
            result = benchmark._test_ollama("What is 2+2?")
        elif args.provider == "hermes":
            result = benchmark._test_hermes("What is 2+2?")
        elif args.provider == "openrouter":
            result = benchmark._test_openrouter("What is 2+2?")
        else:
            print(f"Unknown provider: {args.provider}")
            return

        print(f"Success: {result.success}")
        print(f"Latency: {result.latency_ms}ms")
        print(f"Response: {result.response_preview}")
        return

    results = benchmark.run_full_benchmark(quick=args.quick)

    if args.json:
        print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
