#!/usr/bin/env python3
"""
Task Pre-Filter - Intercepts kanban tasks before they hit Claude.

Scans the kanban board for tasks that can be handled locally via
Hermes/Ollama, reducing Claude API rate limit pressure.

Architecture:
    Kanban Board → Pre-Filter → Route Decision
                        │
    ┌───────────────────┼───────────────────┐
    ▼                   ▼                   ▼
TIER 1: LOCAL      TIER 2: FREE        TIER 3: CLAUDE
Hermes + Ollama    OpenRouter          Cline/Claude Max
(complexity < 0.5) (complexity < 0.75) (complexity >= 0.75)

Usage:
    # Scan and process tasks
    python task_prefilter.py --scan

    # Dry run (show routing decisions only)
    python task_prefilter.py --dry-run

    # Filter a single task
    python task_prefilter.py --task "summarize the daily metrics"
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from task_router import KanbanRouter, RoutingResult
from hermes_bridge import HermesBridge, HermesResult
from telegram_notify import notify_task_complete


@dataclass
class PrefilterDecision:
    """Decision made by the pre-filter."""
    task_id: str
    task_prompt: str
    should_intercept: bool
    tier: str  # "local", "openrouter", "claude"
    provider: str  # "ollama", "hermes", "openrouter", "claude"
    model: str
    reason: str
    complexity: float
    task_type: str
    executed: bool = False
    result: Optional[str] = None
    latency_ms: int = 0


class TaskPrefilter:
    """
    Pre-filters kanban tasks to reduce Claude API usage.

    Workflow:
    1. Load config to check if pre-filtering is enabled
    2. Scan kanban board for pending/in_progress tasks
    3. Score each task's complexity
    4. Route simple tasks to Hermes/Ollama
    5. Pass complex tasks through to Cline/Claude
    """

    # Paths
    CONFIG_PATH = Path(__file__).parent / "routing_config.json"
    KANBAN_PATH = Path.home() / ".cline" / "kanban" / "workspaces" / "openclaw" / "board.json"
    SESSIONS_PATH = Path.home() / ".cline" / "kanban" / "workspaces" / "openclaw" / "sessions.json"
    METRICS_PATH = Path(__file__).parent / "routing_metrics.json"

    # Complexity thresholds for routing tiers
    TIER_THRESHOLDS = {
        "local": 0.5,       # Below this → Ollama/Hermes
        "openrouter": 0.75, # Below this but above local → OpenRouter free
        # Above openrouter threshold → Claude
    }

    def __init__(self):
        self.config = self._load_config()
        self.router = KanbanRouter()
        self.bridge = HermesBridge()
        self.metrics = self._load_metrics()

    def _load_config(self) -> Dict[str, Any]:
        """Load routing configuration."""
        if self.CONFIG_PATH.exists():
            try:
                with open(self.CONFIG_PATH) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "prefilter_enabled": True,
            "hermes_enabled": True,
            "prefer_local": True,
            "dry_run": False
        }

    def _load_metrics(self) -> Dict[str, Any]:
        """Load existing metrics."""
        if self.METRICS_PATH.exists():
            try:
                with open(self.METRICS_PATH) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "total_filtered": 0,
            "local_executed": 0,
            "openrouter_executed": 0,
            "claude_passed": 0,
            "decisions": []
        }

    def _save_metrics(self):
        """Save metrics to file."""
        # Keep only last 1000 decisions
        if len(self.metrics["decisions"]) > 1000:
            self.metrics["decisions"] = self.metrics["decisions"][-1000:]

        with open(self.METRICS_PATH, "w") as f:
            json.dump(self.metrics, f, indent=2)

    def _load_kanban_board(self) -> Dict[str, Any]:
        """Load the Cline kanban board."""
        if not self.KANBAN_PATH.exists():
            return {"columns": []}

        try:
            with open(self.KANBAN_PATH) as f:
                return json.load(f)
        except Exception as e:
            print(f"[PreFilter] Error loading kanban: {e}")
            return {"columns": []}

    def _load_sessions(self) -> Dict[str, Any]:
        """Load task sessions."""
        if not self.SESSIONS_PATH.exists():
            return {}

        try:
            with open(self.SESSIONS_PATH) as f:
                return json.load(f)
        except Exception:
            return {}

    def _get_filterable_tasks(self) -> List[Dict[str, Any]]:
        """
        Get tasks that can potentially be pre-filtered.

        Returns tasks that are:
        - In backlog or in_progress columns
        - Not currently being executed by Cline
        - Have a prompt/description
        """
        board = self._load_kanban_board()
        sessions = self._load_sessions()

        tasks = []

        for column in board.get("columns", []):
            # Only look at backlog and in_progress
            if column.get("id") not in ("backlog", "in_progress"):
                continue

            for card in column.get("cards", []):
                task_id = card.get("id", "")
                prompt = card.get("prompt", "")

                if not prompt:
                    continue

                # Skip if actively being executed by Cline
                session = sessions.get(task_id, {})
                if session.get("state") in ("running", "awaiting_review"):
                    continue

                tasks.append({
                    "id": task_id,
                    "prompt": prompt,
                    "column": column.get("id"),
                    "created_at": card.get("createdAt"),
                    "updated_at": card.get("updatedAt")
                })

        return tasks

    def analyze_task(self, task_prompt: str, task_id: str = "") -> PrefilterDecision:
        """
        Analyze a single task and decide how to route it.

        Args:
            task_prompt: The task description/prompt
            task_id: Optional task ID for tracking

        Returns:
            PrefilterDecision with routing recommendation
        """
        # Get routing decision from KanbanRouter
        routing = self.router.should_use_local(task_prompt)

        # Determine tier based on provider
        if routing.provider == "hermes":
            tier = "local"
            should_intercept = True
        elif routing.provider == "ollama":
            tier = "local"
            should_intercept = True
        elif routing.provider == "openrouter":
            tier = "openrouter"
            should_intercept = True
        else:
            tier = "claude"
            should_intercept = False

        # Check if Hermes skill might be better than raw Ollama
        # (only if router didn't already pick Hermes)
        if routing.provider == "ollama":
            hermes_skill = self.bridge._detect_skill(task_prompt)
            if hermes_skill and self.config.get("hermes_enabled", True):
                # Hermes with skill is preferred for research-type tasks
                if self.bridge.check_hermes_available():
                    return PrefilterDecision(
                        task_id=task_id,
                        task_prompt=task_prompt,
                        should_intercept=True,
                        tier="local",
                        provider="hermes",
                        model=f"hermes:{hermes_skill}",
                        reason=f"Hermes skill '{hermes_skill}' matches task",
                        complexity=routing.complexity,
                        task_type=routing.task_type
                    )

        return PrefilterDecision(
            task_id=task_id,
            task_prompt=task_prompt,
            should_intercept=should_intercept,
            tier=tier,
            provider=routing.provider,
            model=routing.model,
            reason=routing.reason,
            complexity=routing.complexity,
            task_type=routing.task_type
        )

    def execute_filtered_task(self, decision: PrefilterDecision) -> PrefilterDecision:
        """
        Execute a task that was filtered for local/openrouter execution.

        Args:
            decision: The prefilter decision for this task

        Returns:
            Updated decision with execution result
        """
        if not decision.should_intercept:
            return decision

        start_time = time.time()
        success = False

        if decision.provider == "hermes":
            # Use Hermes CLI with skill
            skill = decision.model.replace("hermes:", "") if ":" in decision.model else None
            result = self.bridge.execute_hermes_cli(decision.task_prompt, skill=skill)

            decision.executed = True
            decision.latency_ms = result.latency_ms

            if result.success:
                decision.result = result.content
                self.metrics["hermes_executed"] = self.metrics.get("hermes_executed", 0) + 1
                success = True
            else:
                decision.result = f"Error: {result.error}"

        elif decision.provider == "ollama":
            # Use direct Ollama
            result = self.bridge.execute_ollama(decision.task_prompt, model=decision.model)

            decision.executed = True
            decision.latency_ms = result.latency_ms

            if result.success:
                decision.result = result.content
                self.metrics["local_executed"] = self.metrics.get("local_executed", 0) + 1
                success = True
            else:
                decision.result = f"Error: {result.error}"

        elif decision.provider == "openrouter":
            # Use OpenRouter via KanbanRouter
            routing_result = RoutingResult(
                use_local=True,
                model=decision.model,
                provider="openrouter",
                reason=decision.reason,
                task_type=decision.task_type,
                complexity=decision.complexity
            )
            result = self.router.execute(decision.task_prompt, routing_result)

            decision.executed = True
            decision.latency_ms = result.get("latency_ms", 0)

            if result.get("success"):
                decision.result = result.get("content", "")
                self.metrics["openrouter_executed"] = self.metrics.get("openrouter_executed", 0) + 1
                success = True
            else:
                decision.result = f"Error: {result.get('error', 'Unknown error')}"

        # If execution succeeded, update kanban, save result, and notify
        if success and decision.task_id:
            self._save_task_result(decision)
            self._move_task_to_review(decision.task_id)

            # Send Telegram notification
            if self.config.get("telegram_notifications", True):
                try:
                    notify_task_complete(
                        task_id=decision.task_id,
                        prompt=decision.task_prompt,
                        result=decision.result or "",
                        provider=decision.provider,
                        model=decision.model,
                        latency_ms=decision.latency_ms,
                        success=True
                    )
                except Exception as e:
                    print(f"  [Telegram notification failed: {e}]")

        return decision

    def _save_task_result(self, decision: PrefilterDecision):
        """Save task execution result to file."""
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)

        result_file = results_dir / f"{decision.task_id[:20]}.json"
        result_data = {
            "task_id": decision.task_id,
            "prompt": decision.task_prompt,
            "provider": decision.provider,
            "model": decision.model,
            "complexity": decision.complexity,
            "latency_ms": decision.latency_ms,
            "result": decision.result,
            "executed_at": datetime.now().isoformat()
        }

        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2)

        print(f"  [Saved result to {result_file.name}]")

    def _move_task_to_review(self, task_id: str):
        """Move a completed task to the review column in kanban."""
        if not self.KANBAN_PATH.exists():
            return

        try:
            with open(self.KANBAN_PATH) as f:
                board = json.load(f)

            # Find and remove task from current column
            task_card = None
            for column in board.get("columns", []):
                for i, card in enumerate(column.get("cards", [])):
                    if card.get("id") == task_id:
                        task_card = column["cards"].pop(i)
                        break
                if task_card:
                    break

            if not task_card:
                return

            # Add to review column
            for column in board.get("columns", []):
                if column.get("id") == "review":
                    # Add metadata about local execution
                    task_card["localExecuted"] = True
                    task_card["localExecutedAt"] = datetime.now().isoformat()
                    task_card["updatedAt"] = int(time.time() * 1000)
                    column["cards"].insert(0, task_card)
                    break

            # Save updated board
            with open(self.KANBAN_PATH, "w") as f:
                json.dump(board, f, indent=2)

            print(f"  [Moved task to review column]")

        except Exception as e:
            print(f"  [Error moving task: {e}]")

    def scan_and_filter(self, dry_run: bool = False, execute: bool = False) -> List[PrefilterDecision]:
        """
        Scan kanban board and filter tasks.

        Args:
            dry_run: If True, only analyze without executing
            execute: If True, execute filtered tasks

        Returns:
            List of PrefilterDecision for all analyzed tasks
        """
        if not self.config.get("prefilter_enabled", True):
            print("[PreFilter] Pre-filtering disabled in config")
            return []

        tasks = self._get_filterable_tasks()
        decisions = []
        max_exec = self.config.get("max_tasks_per_cycle", 3)
        executed_count = 0

        print(f"[PreFilter] Analyzing {len(tasks)} tasks (max {max_exec} executions)...")

        for task in tasks:
            decision = self.analyze_task(task["prompt"], task["id"])
            decisions.append(decision)

            # Execute if requested, interceptable, and under limit
            if execute and not dry_run and decision.should_intercept:
                if executed_count < max_exec:
                    print(f"\n  >>> EXECUTING locally ({executed_count + 1}/{max_exec})...")
                    decision = self.execute_filtered_task(decision)
                    if decision.executed:
                        executed_count += 1
                else:
                    print(f"  [Skipped - max executions ({max_exec}) reached]")

            # Track metrics
            self.metrics["total_filtered"] += 1
            if not decision.should_intercept:
                self.metrics["claude_passed"] += 1

            # Log decision
            tier_emoji = {"local": "🏠", "openrouter": "☁️", "claude": "🤖"}.get(decision.tier, "?")
            exec_status = " [DONE]" if decision.executed else ""
            print(f"  {tier_emoji} [{decision.tier:10}] {decision.model:30} | {decision.task_prompt[:40]}...{exec_status}")

            # Store decision summary in metrics
            self.metrics["decisions"].append({
                "timestamp": datetime.now().isoformat(),
                "task_id": decision.task_id,
                "tier": decision.tier,
                "provider": decision.provider,
                "model": decision.model,
                "complexity": decision.complexity,
                "executed": decision.executed
            })

        # Save metrics
        self._save_metrics()

        return decisions

    def filter_single(self, task_prompt: str, execute: bool = False) -> PrefilterDecision:
        """
        Analyze and optionally execute a single task.

        Args:
            task_prompt: The task description
            execute: If True, execute if interceptable

        Returns:
            PrefilterDecision
        """
        decision = self.analyze_task(task_prompt)

        if execute and decision.should_intercept:
            decision = self.execute_filtered_task(decision)

        return decision

    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        total = self.metrics.get("total_filtered", 0) or 1  # Avoid div by zero

        return {
            "total_tasks": self.metrics.get("total_filtered", 0),
            "local_executed": self.metrics.get("local_executed", 0),
            "openrouter_executed": self.metrics.get("openrouter_executed", 0),
            "claude_passed": self.metrics.get("claude_passed", 0),
            "local_percentage": (self.metrics.get("local_executed", 0) / total) * 100,
            "openrouter_percentage": (self.metrics.get("openrouter_executed", 0) / total) * 100,
            "claude_percentage": (self.metrics.get("claude_passed", 0) / total) * 100,
            "estimated_api_savings": f"{((self.metrics.get('local_executed', 0) + self.metrics.get('openrouter_executed', 0)) / total) * 100:.1f}%"
        }


def main():
    parser = argparse.ArgumentParser(description="Task Pre-Filter for Hermes/OpenClaw integration")
    parser.add_argument("--scan", action="store_true", help="Scan kanban and filter tasks")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't execute")
    parser.add_argument("--execute", action="store_true", help="Execute filtered tasks")
    parser.add_argument("--task", type=str, help="Filter a single task by prompt")
    parser.add_argument("--stats", action="store_true", help="Show routing statistics")

    args = parser.parse_args()

    prefilter = TaskPrefilter()

    if args.stats:
        print("=" * 60)
        print("Routing Statistics")
        print("=" * 60)
        stats = prefilter.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        return

    if args.task:
        print("=" * 60)
        print(f"Single Task Analysis")
        print("=" * 60)
        decision = prefilter.filter_single(args.task, execute=args.execute)
        print(f"\nTask: {decision.task_prompt[:80]}...")
        print(f"Tier: {decision.tier}")
        print(f"Provider: {decision.provider}")
        print(f"Model: {decision.model}")
        print(f"Complexity: {decision.complexity:.2f}")
        print(f"Type: {decision.task_type}")
        print(f"Should Intercept: {decision.should_intercept}")
        print(f"Reason: {decision.reason}")

        if decision.executed:
            print(f"\nExecution Result:")
            print(f"  Latency: {decision.latency_ms}ms")
            print(f"  Result: {decision.result[:500] if decision.result else 'None'}...")
        return

    if args.scan:
        print("=" * 60)
        print("Kanban Pre-Filter Scan")
        print("=" * 60)
        decisions = prefilter.scan_and_filter(dry_run=args.dry_run, execute=args.execute)

        print(f"\n--- Summary ---")
        local = sum(1 for d in decisions if d.tier == "local")
        openrouter = sum(1 for d in decisions if d.tier == "openrouter")
        claude = sum(1 for d in decisions if d.tier == "claude")

        print(f"Local (Hermes/Ollama): {local}")
        print(f"OpenRouter (Free): {openrouter}")
        print(f"Claude: {claude}")
        print(f"Potential API savings: {((local + openrouter) / max(len(decisions), 1)) * 100:.1f}%")
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
