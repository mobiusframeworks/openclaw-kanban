#!/usr/bin/env python3
"""
Hermes Bridge - Interface between OpenClaw Kanban and Hermes Agent.

Routes simple tasks to Hermes/Ollama before they hit Claude,
reducing API rate limit pressure.

Architecture:
    Task → HermesBridge → Hermes CLI/Ollama → Result
                       ↘ (fallback) Claude

Usage:
    from hermes_bridge import HermesBridge
    bridge = HermesBridge()
    result = bridge.execute("Summarize this text: ...")
"""

import os
import sys
import json
import subprocess
import time
import requests
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime


@dataclass
class HermesResult:
    """Result from Hermes execution."""
    success: bool
    content: str
    model: str
    provider: str  # "hermes", "ollama", "fallback"
    latency_ms: int
    skill_used: Optional[str] = None
    error: Optional[str] = None


class HermesBridge:
    """
    Bridge to Hermes Agent for task routing.

    Provides multiple execution paths:
    1. Hermes CLI with skills (research, obsidian, etc.)
    2. Direct Ollama API (for simple queries)
    3. Fallback signal for Claude routing
    """

    # Hermes installation paths
    HERMES_HOME = Path.home() / ".hermes"
    HERMES_AGENT = HERMES_HOME / "hermes-agent"
    HERMES_VENV_PYTHON = HERMES_AGENT / "venv" / "bin" / "python"
    HERMES_CLI = HERMES_AGENT / "cli.py"

    # Task type to Hermes skill mapping
    SKILL_MAP = {
        "research": "deep-research",
        "web_search": "web",
        "summarization": None,  # Use Ollama directly
        "classification": None,
        "note_taking": "obsidian",
        "code_review": "code-review",
        "documentation": None,
        "data_processing": None,
        "creative_writing": None,
        "analysis": "deep-research",
    }

    # Keywords that suggest specific skills
    SKILL_KEYWORDS = {
        "research": ["research", "investigate", "find out", "look up", "study"],
        "web_search": ["search the web", "google", "find online", "web search"],
        "note_taking": ["note", "obsidian", "vault", "journal", "document this"],
        "code_review": ["review code", "code review", "check this code", "audit code"],
    }

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        default_model: str = "qwen2.5:7b",
        timeout: int = 120
    ):
        self.ollama_url = ollama_url
        self.default_model = default_model
        self.timeout = timeout
        self._hermes_available = None
        self._ollama_available = None

    def check_hermes_available(self) -> bool:
        """Check if Hermes CLI is available and functional."""
        if self._hermes_available is not None:
            return self._hermes_available

        try:
            if not self.HERMES_VENV_PYTHON.exists():
                self._hermes_available = False
                return False

            # Quick test of Hermes CLI
            result = subprocess.run(
                [str(self.HERMES_VENV_PYTHON), str(self.HERMES_CLI), "--help"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self.HERMES_AGENT)
            )
            self._hermes_available = result.returncode == 0
        except Exception:
            self._hermes_available = False

        return self._hermes_available

    def check_ollama_available(self) -> bool:
        """Check if Ollama is running and responsive."""
        if self._ollama_available is not None:
            return self._ollama_available

        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            self._ollama_available = response.status_code == 200
        except Exception:
            self._ollama_available = False

        return self._ollama_available

    def _detect_skill(self, task_text: str) -> Optional[str]:
        """Detect which Hermes skill might be appropriate for a task."""
        task_lower = task_text.lower()

        for skill_type, keywords in self.SKILL_KEYWORDS.items():
            if any(kw in task_lower for kw in keywords):
                return self.SKILL_MAP.get(skill_type)

        return None

    def _classify_task_type(self, task_text: str) -> str:
        """Classify task into a type."""
        task_lower = task_text.lower()

        if any(kw in task_lower for kw in ["research", "investigate", "study"]):
            return "research"
        if any(kw in task_lower for kw in ["summarize", "summary", "brief"]):
            return "summarization"
        if any(kw in task_lower for kw in ["classify", "categorize", "sort"]):
            return "classification"
        if any(kw in task_lower for kw in ["note", "obsidian", "vault"]):
            return "note_taking"
        if any(kw in task_lower for kw in ["review code", "code review"]):
            return "code_review"
        if any(kw in task_lower for kw in ["analyze", "compare", "evaluate"]):
            return "analysis"

        return "general"

    def execute_hermes_cli(
        self,
        query: str,
        skill: Optional[str] = None,
        model: Optional[str] = None
    ) -> HermesResult:
        """
        Execute a task using Hermes CLI.

        Args:
            query: The task/query to execute
            skill: Optional specific skill to use
            model: Optional model override

        Returns:
            HermesResult with execution details
        """
        if not self.check_hermes_available():
            return HermesResult(
                success=False,
                content="",
                model="",
                provider="hermes",
                latency_ms=0,
                error="Hermes CLI not available"
            )

        start_time = time.time()

        try:
            cmd = [
                str(self.HERMES_VENV_PYTHON),
                str(self.HERMES_CLI),
                "-q", query,
                "--non-interactive"
            ]

            if skill:
                cmd.extend(["--skills", skill])

            if model:
                cmd.extend(["--model", model])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.HERMES_AGENT),
                env={**os.environ, "HERMES_QUIET": "1"}
            )

            latency_ms = int((time.time() - start_time) * 1000)

            if result.returncode == 0:
                # Parse output - Hermes outputs the response directly
                content = result.stdout.strip()
                # Remove any ANSI escape codes
                import re
                content = re.sub(r'\x1b\[[0-9;]*m', '', content)

                return HermesResult(
                    success=True,
                    content=content,
                    model=model or "hermes-default",
                    provider="hermes",
                    latency_ms=latency_ms,
                    skill_used=skill
                )
            else:
                return HermesResult(
                    success=False,
                    content="",
                    model="",
                    provider="hermes",
                    latency_ms=latency_ms,
                    error=f"Hermes CLI error: {result.stderr[:500]}"
                )

        except subprocess.TimeoutExpired:
            return HermesResult(
                success=False,
                content="",
                model="",
                provider="hermes",
                latency_ms=self.timeout * 1000,
                error=f"Hermes CLI timeout after {self.timeout}s"
            )
        except Exception as e:
            return HermesResult(
                success=False,
                content="",
                model="",
                provider="hermes",
                latency_ms=int((time.time() - start_time) * 1000),
                error=f"Hermes execution error: {str(e)}"
            )

    def execute_ollama(
        self,
        query: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> HermesResult:
        """
        Execute a task directly via Ollama API.

        Faster than Hermes CLI for simple queries that don't need skills.

        Args:
            query: The task/query to execute
            model: Model to use (defaults to self.default_model)
            system_prompt: Optional system prompt

        Returns:
            HermesResult with execution details
        """
        if not self.check_ollama_available():
            return HermesResult(
                success=False,
                content="",
                model="",
                provider="ollama",
                latency_ms=0,
                error="Ollama not available"
            )

        model = model or self.default_model
        start_time = time.time()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": query})

            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False
                },
                timeout=self.timeout
            )
            response.raise_for_status()

            result = response.json()
            latency_ms = int((time.time() - start_time) * 1000)

            content = result.get("message", {}).get("content", "")

            return HermesResult(
                success=True,
                content=content,
                model=model,
                provider="ollama",
                latency_ms=latency_ms
            )

        except requests.Timeout:
            return HermesResult(
                success=False,
                content="",
                model=model,
                provider="ollama",
                latency_ms=self.timeout * 1000,
                error=f"Ollama timeout after {self.timeout}s"
            )
        except Exception as e:
            return HermesResult(
                success=False,
                content="",
                model=model,
                provider="ollama",
                latency_ms=int((time.time() - start_time) * 1000),
                error=f"Ollama error: {str(e)}"
            )

    def execute(
        self,
        task_text: str,
        prefer_hermes: bool = False,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None
    ) -> HermesResult:
        """
        Execute a task using the best available method.

        Routing logic:
        1. If task needs a skill and Hermes is available → Hermes CLI
        2. If Ollama is available → Direct Ollama
        3. Otherwise → Return fallback signal for Claude

        Args:
            task_text: The task to execute
            prefer_hermes: If True, try Hermes CLI first even without skill match
            model: Optional model override
            system_prompt: Optional system prompt for Ollama

        Returns:
            HermesResult with execution details
        """
        # Detect if we need a Hermes skill
        skill = self._detect_skill(task_text)

        # If skill detected and Hermes available, use Hermes CLI
        if skill and self.check_hermes_available():
            result = self.execute_hermes_cli(task_text, skill=skill, model=model)
            if result.success:
                return result

        # If prefer_hermes, try Hermes CLI without skill
        if prefer_hermes and self.check_hermes_available():
            result = self.execute_hermes_cli(task_text, model=model)
            if result.success:
                return result

        # Try direct Ollama
        if self.check_ollama_available():
            return self.execute_ollama(task_text, model=model, system_prompt=system_prompt)

        # Signal that Claude should handle this
        return HermesResult(
            success=False,
            content="",
            model="",
            provider="fallback",
            latency_ms=0,
            error="No local execution path available - escalate to Claude"
        )

    def get_status(self) -> Dict[str, Any]:
        """Get status of all execution paths."""
        return {
            "hermes_available": self.check_hermes_available(),
            "ollama_available": self.check_ollama_available(),
            "hermes_path": str(self.HERMES_CLI) if self.HERMES_CLI.exists() else None,
            "ollama_url": self.ollama_url,
            "default_model": self.default_model,
            "available_skills": list(set(s for s in self.SKILL_MAP.values() if s))
        }


# Convenience function for quick execution
def execute_local(task_text: str, **kwargs) -> HermesResult:
    """Quick execution via Hermes bridge."""
    bridge = HermesBridge()
    return bridge.execute(task_text, **kwargs)


if __name__ == "__main__":
    bridge = HermesBridge()

    print("=" * 60)
    print("Hermes Bridge Status")
    print("=" * 60)

    status = bridge.get_status()
    print(f"\nHermes CLI: {'OK' if status['hermes_available'] else 'NOT AVAILABLE'}")
    print(f"Ollama: {'OK' if status['ollama_available'] else 'NOT AVAILABLE'}")
    print(f"Default Model: {status['default_model']}")
    print(f"Available Skills: {', '.join(status['available_skills'])}")

    if status['ollama_available']:
        print("\n--- Test Execution ---")
        result = bridge.execute("What is 2 + 2?")
        print(f"Provider: {result.provider}")
        print(f"Model: {result.model}")
        print(f"Latency: {result.latency_ms}ms")
        print(f"Success: {result.success}")
        if result.success:
            print(f"Response: {result.content[:200]}...")
        else:
            print(f"Error: {result.error}")
