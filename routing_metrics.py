#!/usr/bin/env python3
"""
Routing Metrics Dashboard - Track and visualize task routing efficiency.

Monitors:
- Tasks per tier (hermes/ollama/openrouter/claude)
- Estimated cost savings
- Escalation frequency
- Latency comparisons

Usage:
    python routing_metrics.py              # Show summary
    python routing_metrics.py --dashboard  # Live dashboard (refreshes)
    python routing_metrics.py --export     # Export to CSV
    python routing_metrics.py --reset      # Reset metrics
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict


class RoutingMetrics:
    """
    Track and analyze routing metrics for the Hermes/OpenClaw integration.

    Metrics tracked:
    - Task counts per provider (hermes, ollama, openrouter, claude)
    - Execution latency
    - Success/failure rates
    - Estimated cost savings
    """

    METRICS_PATH = Path(__file__).parent / "routing_metrics.json"
    LOG_PATH = Path("/tmp/routing-metrics.log")

    # Estimated costs per 1K tokens (USD)
    COST_ESTIMATES = {
        "hermes": 0.0,       # Free (local)
        "ollama": 0.0,       # Free (local)
        "openrouter": 0.0,   # Free tier models
        "claude": 0.003,     # ~$3/1M tokens (Claude 3.5 Sonnet)
    }

    # Average tokens per task (rough estimate)
    AVG_TOKENS_PER_TASK = 1500  # input + output

    def __init__(self):
        self.metrics = self._load_metrics()

    def _load_metrics(self) -> Dict[str, Any]:
        """Load existing metrics from file."""
        if self.METRICS_PATH.exists():
            try:
                with open(self.METRICS_PATH) as f:
                    return json.load(f)
            except Exception:
                pass

        return {
            "total_filtered": 0,
            "hermes_executed": 0,
            "local_executed": 0,
            "openrouter_executed": 0,
            "claude_passed": 0,
            "total_latency_ms": 0,
            "decisions": [],
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }

    def _save_metrics(self):
        """Save metrics to file."""
        self.metrics["last_updated"] = datetime.now().isoformat()

        # Keep only last 1000 decisions
        if len(self.metrics.get("decisions", [])) > 1000:
            self.metrics["decisions"] = self.metrics["decisions"][-1000:]

        with open(self.METRICS_PATH, "w") as f:
            json.dump(self.metrics, f, indent=2)

    def record_decision(
        self,
        task_id: str,
        tier: str,
        provider: str,
        model: str,
        complexity: float,
        executed: bool,
        latency_ms: int = 0,
        success: bool = True
    ):
        """Record a routing decision."""
        decision = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "tier": tier,
            "provider": provider,
            "model": model,
            "complexity": complexity,
            "executed": executed,
            "latency_ms": latency_ms,
            "success": success
        }

        self.metrics["decisions"].append(decision)
        self.metrics["total_filtered"] += 1

        if executed:
            if provider == "hermes":
                self.metrics["hermes_executed"] = self.metrics.get("hermes_executed", 0) + 1
            elif provider == "ollama":
                self.metrics["local_executed"] = self.metrics.get("local_executed", 0) + 1
            elif provider == "openrouter":
                self.metrics["openrouter_executed"] = self.metrics.get("openrouter_executed", 0) + 1
            self.metrics["total_latency_ms"] = self.metrics.get("total_latency_ms", 0) + latency_ms
        else:
            self.metrics["claude_passed"] = self.metrics.get("claude_passed", 0) + 1

        self._save_metrics()

        # Also log to file
        with open(self.LOG_PATH, "a") as f:
            f.write(f"[{decision['timestamp']}] {tier:10} {provider:12} {model:30} latency={latency_ms}ms\n")

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        total = self.metrics.get("total_filtered", 0) or 1
        hermes = self.metrics.get("hermes_executed", 0)
        local = self.metrics.get("local_executed", 0)
        openrouter = self.metrics.get("openrouter_executed", 0)
        claude = self.metrics.get("claude_passed", 0)

        # Calculate estimated savings
        local_total = hermes + local + openrouter
        estimated_claude_cost = total * self.AVG_TOKENS_PER_TASK / 1000 * self.COST_ESTIMATES["claude"]
        actual_claude_cost = claude * self.AVG_TOKENS_PER_TASK / 1000 * self.COST_ESTIMATES["claude"]
        savings = estimated_claude_cost - actual_claude_cost

        # Calculate average latencies
        decisions = self.metrics.get("decisions", [])
        latency_by_provider = defaultdict(list)
        for d in decisions:
            if d.get("latency_ms", 0) > 0:
                latency_by_provider[d.get("provider", "unknown")].append(d["latency_ms"])

        avg_latencies = {}
        for provider, latencies in latency_by_provider.items():
            avg_latencies[provider] = sum(latencies) / len(latencies) if latencies else 0

        return {
            "total_tasks": total,
            "hermes_tasks": hermes,
            "ollama_tasks": local,
            "openrouter_tasks": openrouter,
            "claude_tasks": claude,
            "hermes_percentage": (hermes / total) * 100,
            "ollama_percentage": (local / total) * 100,
            "openrouter_percentage": (openrouter / total) * 100,
            "claude_percentage": (claude / total) * 100,
            "local_total_percentage": (local_total / total) * 100,
            "estimated_savings_usd": round(savings, 4),
            "avg_latencies_ms": avg_latencies,
            "created_at": self.metrics.get("created_at", ""),
            "last_updated": self.metrics.get("last_updated", "")
        }

    def get_hourly_breakdown(self, hours: int = 24) -> Dict[str, Any]:
        """Get hourly breakdown of routing decisions."""
        cutoff = datetime.now() - timedelta(hours=hours)
        decisions = self.metrics.get("decisions", [])

        hourly = defaultdict(lambda: {"hermes": 0, "ollama": 0, "openrouter": 0, "claude": 0})

        for d in decisions:
            try:
                ts = datetime.fromisoformat(d["timestamp"])
                if ts > cutoff:
                    hour_key = ts.strftime("%Y-%m-%d %H:00")
                    provider = d.get("provider", "unknown")
                    if provider in hourly[hour_key]:
                        hourly[hour_key][provider] += 1
            except Exception:
                continue

        return dict(hourly)

    def get_tier_efficiency(self) -> Dict[str, Any]:
        """Calculate efficiency metrics per tier."""
        decisions = self.metrics.get("decisions", [])

        tier_stats = defaultdict(lambda: {
            "total": 0,
            "success": 0,
            "total_latency": 0,
            "complexities": []
        })

        for d in decisions:
            tier = d.get("tier", "unknown")
            tier_stats[tier]["total"] += 1
            if d.get("success", True):
                tier_stats[tier]["success"] += 1
            tier_stats[tier]["total_latency"] += d.get("latency_ms", 0)
            tier_stats[tier]["complexities"].append(d.get("complexity", 0))

        result = {}
        for tier, stats in tier_stats.items():
            total = stats["total"] or 1
            result[tier] = {
                "total_tasks": stats["total"],
                "success_rate": (stats["success"] / total) * 100,
                "avg_latency_ms": stats["total_latency"] / total,
                "avg_complexity": sum(stats["complexities"]) / len(stats["complexities"]) if stats["complexities"] else 0
            }

        return result

    def reset(self):
        """Reset all metrics."""
        self.metrics = {
            "total_filtered": 0,
            "hermes_executed": 0,
            "local_executed": 0,
            "openrouter_executed": 0,
            "claude_passed": 0,
            "total_latency_ms": 0,
            "decisions": [],
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        self._save_metrics()

    def export_csv(self, output_path: str = None) -> str:
        """Export decisions to CSV."""
        if not output_path:
            output_path = str(Path(__file__).parent / "routing_metrics_export.csv")

        decisions = self.metrics.get("decisions", [])

        with open(output_path, "w") as f:
            # Header
            f.write("timestamp,task_id,tier,provider,model,complexity,executed,latency_ms,success\n")

            # Data
            for d in decisions:
                f.write(f"{d.get('timestamp','')},{d.get('task_id','')},{d.get('tier','')},")
                f.write(f"{d.get('provider','')},{d.get('model','')},{d.get('complexity',0)},")
                f.write(f"{d.get('executed',False)},{d.get('latency_ms',0)},{d.get('success',True)}\n")

        return output_path


def print_dashboard(metrics: RoutingMetrics, clear: bool = True):
    """Print a terminal dashboard."""
    if clear:
        os.system('clear' if os.name == 'posix' else 'cls')

    summary = metrics.get_summary()
    efficiency = metrics.get_tier_efficiency()

    print("=" * 70)
    print("  HERMES + OPENCLAW ROUTING METRICS DASHBOARD")
    print("=" * 70)
    print(f"  Last Updated: {summary.get('last_updated', 'N/A')}")
    print()

    # Overview
    print("  OVERVIEW")
    print("  " + "-" * 40)
    print(f"  Total Tasks Processed: {summary['total_tasks']}")
    print(f"  Estimated API Savings: ${summary['estimated_savings_usd']:.4f}")
    print()

    # Tier breakdown with bar chart
    print("  ROUTING BREAKDOWN")
    print("  " + "-" * 40)

    tiers = [
        ("Hermes (Skills)", summary['hermes_percentage'], "hermes"),
        ("Ollama (Local)", summary['ollama_percentage'], "ollama"),
        ("OpenRouter (Free)", summary['openrouter_percentage'], "openrouter"),
        ("Claude (API)", summary['claude_percentage'], "claude"),
    ]

    for name, pct, tier in tiers:
        bar_len = int(pct / 2)  # Scale to 50 chars max
        bar = "#" * bar_len
        count = summary.get(f"{tier}_tasks", 0)
        print(f"  {name:20} [{bar:50}] {pct:5.1f}% ({count})")

    print()
    print(f"  Local Total (non-Claude): {summary['local_total_percentage']:.1f}%")
    print()

    # Latencies
    print("  AVERAGE LATENCIES")
    print("  " + "-" * 40)
    avg_lat = summary.get('avg_latencies_ms', {})
    for provider, latency in sorted(avg_lat.items()):
        print(f"  {provider:15} {latency:8.0f}ms")

    print()

    # Tier efficiency
    print("  TIER EFFICIENCY")
    print("  " + "-" * 40)
    for tier, stats in sorted(efficiency.items()):
        print(f"  {tier:15} Success: {stats['success_rate']:5.1f}%  "
              f"Avg Complexity: {stats['avg_complexity']:.2f}")

    print()
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Routing Metrics Dashboard")
    parser.add_argument("--dashboard", action="store_true", help="Show live dashboard")
    parser.add_argument("--refresh", type=int, default=10, help="Dashboard refresh interval (seconds)")
    parser.add_argument("--export", action="store_true", help="Export to CSV")
    parser.add_argument("--reset", action="store_true", help="Reset all metrics")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    metrics = RoutingMetrics()

    if args.reset:
        metrics.reset()
        print("Metrics reset successfully")
        return

    if args.export:
        path = metrics.export_csv()
        print(f"Exported to: {path}")
        return

    if args.json:
        print(json.dumps(metrics.get_summary(), indent=2))
        return

    if args.dashboard:
        try:
            while True:
                print_dashboard(metrics)
                print(f"\n  Refreshing in {args.refresh}s... (Ctrl+C to exit)")
                time.sleep(args.refresh)
                metrics = RoutingMetrics()  # Reload
        except KeyboardInterrupt:
            print("\nExiting dashboard...")
            return
    else:
        print_dashboard(metrics, clear=False)


if __name__ == "__main__":
    main()
