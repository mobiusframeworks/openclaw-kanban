#!/usr/bin/env python3
"""
Task Router - Routes kanban tasks to optimal models.

Supports four tiers:
1. Hermes + Local Ollama (skills + fastest, free, privacy-safe)
2. Local Ollama (fastest, free, privacy-safe)
3. OpenRouter Free (cloud, free tier models)
4. Claude (most capable, for complex tasks)

Free OpenRouter Models:
- minimax/minimax-m2.5:free - Fast, 1M context
- glm-4.6:cloud - Good reasoning
- google/gemini-2.0-flash-lite:free - Fast multimodal
- nvidia/nemotron-3-super-120b-a12b:free - 120B reasoning
"""

import os
import sys
import re
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
from enum import Enum

# Add the router module path
ROUTER_PATH = Path.home() / ".openclaw" / "scripts" / "routing"
if ROUTER_PATH.exists():
    sys.path.insert(0, str(ROUTER_PATH))
    try:
        from router import HybridRouter, TaskType, TaskResult
    except ImportError:
        HybridRouter = None
        TaskType = None
        TaskResult = None
else:
    HybridRouter = None
    TaskType = None
    TaskResult = None


@dataclass
class RoutingResult:
    """Result of routing decision."""
    use_local: bool
    model: str
    provider: str  # "hermes", "ollama", "openrouter", "claude"
    reason: str
    task_type: str
    complexity: float
    hermes_skill: str = ""  # Hermes skill if provider is "hermes"


@dataclass
class ModelConfig:
    """Configuration for a model."""
    name: str
    provider: str  # "ollama", "openrouter", "claude"
    capabilities: List[str] = field(default_factory=list)
    max_tokens: int = 4096
    context_window: int = 8192
    speed: str = "medium"  # "fast", "medium", "slow"
    cost: str = "free"  # "free", "cheap", "expensive"


class KanbanRouter:
    """Routes kanban tasks to optimal models across providers."""

    # Hermes skill mapping for task types
    HERMES_SKILLS = {
        "research": "deep-research",
        "web_search": "web",
        "note_taking": "obsidian",
        "code_review": "code-review",
        "analysis": "deep-research",
    }

    # Keywords that suggest Hermes skills
    HERMES_SKILL_KEYWORDS = {
        "deep-research": ["research", "investigate", "study", "analyze thoroughly", "deep dive"],
        "web": ["search the web", "google", "find online", "look up online"],
        "obsidian": ["note", "obsidian", "vault", "journal", "document this"],
        "code-review": ["review code", "code review", "check this code", "audit code"],
    }

    # OpenRouter free models with capabilities (verified working)
    OPENROUTER_MODELS = {
        "nvidia/nemotron-3-nano-30b-a3b:free": ModelConfig(
            name="nvidia/nemotron-3-nano-30b-a3b:free",
            provider="openrouter",
            capabilities=["summarization", "general", "creative_writing", "classification"],
            context_window=32000,
            speed="fast",
            cost="free"
        ),
        "qwen/qwen3-next-80b-a3b-instruct:free": ModelConfig(
            name="qwen/qwen3-next-80b-a3b-instruct:free",
            provider="openrouter",
            capabilities=["reasoning", "analysis", "general"],
            context_window=32000,
            speed="medium",
            cost="free"
        ),
        "nvidia/nemotron-3-super-120b-a12b:free": ModelConfig(
            name="nvidia/nemotron-3-super-120b-a12b:free",
            provider="openrouter",
            capabilities=["complex_reasoning", "analysis", "code_generation"],
            context_window=32000,
            speed="slow",
            cost="free"
        ),
        "openai/gpt-oss-120b:free": ModelConfig(
            name="openai/gpt-oss-120b:free",
            provider="openrouter",
            capabilities=["code_generation", "reasoning"],
            context_window=32000,
            speed="medium",
            cost="free"
        ),
    }

    # Ollama local models
    OLLAMA_MODELS = {
        "qwen2.5:3b": ModelConfig(
            name="qwen2.5:3b",
            provider="ollama",
            capabilities=["classification", "simple_tasks"],
            speed="fast",
            cost="free"
        ),
        "qwen2.5:7b": ModelConfig(
            name="qwen2.5:7b",
            provider="ollama",
            capabilities=["summarization", "general", "data_processing"],
            speed="fast",
            cost="free"
        ),
        "qwen2.5-coder:7b": ModelConfig(
            name="qwen2.5-coder:7b",
            provider="ollama",
            capabilities=["code_generation", "code_review"],
            speed="fast",
            cost="free"
        ),
        "deepseek-r1:latest": ModelConfig(
            name="deepseek-r1:latest",
            provider="ollama",
            capabilities=["complex_reasoning", "analysis"],
            speed="medium",
            cost="free"
        ),
    }

    # Keywords that indicate Claude is needed
    CLAUDE_KEYWORDS = [
        "implement", "deploy", "fix", "build", "create file",
        "git ", "commit", "push", "merge", "branch",
        "edit ", "modify ", "change ", "update code",
        "run script", "execute", "npm", "pip", "docker",
        "debug", "refactor", "architect", "design system"
    ]

    # Privacy patterns (always local)
    PRIVACY_PATTERNS = [
        "password", "ssn", "social security", "credit card",
        "api key", "secret", "private", "confidential"
    ]

    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        openrouter_api_key: str = None,
        hermes_enabled: bool = True
    ):
        self.ollama_url = ollama_url
        self.openrouter_api_key = openrouter_api_key or self._load_api_key()
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self._router = None
        self._ollama_healthy = None
        self._openrouter_healthy = None
        self._hermes_healthy = None
        self._hermes_bridge = None
        self.hermes_enabled = hermes_enabled
        self.metrics = []
        self._init_router()
        self._init_hermes()

    def _load_config(self) -> dict:
        """Load routing config from file."""
        config_path = Path(__file__).parent / "routing_config.json"
        if config_path.exists():
            try:
                with open(config_path) as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _load_api_key(self) -> str:
        """Load OpenRouter API key from config file or environment."""
        # Try environment variable first
        key = os.environ.get("OPENROUTER_API_KEY", "")
        if key:
            return key

        # Try config file
        config = self._load_config()
        return config.get("openrouter_api_key", "")

    def _init_router(self):
        """Initialize the HybridRouter if available."""
        if HybridRouter is not None:
            try:
                self._router = HybridRouter(ollama_url=self.ollama_url)
            except Exception as e:
                print(f"[TaskRouter] Failed to init HybridRouter: {e}")

    def _init_hermes(self):
        """Initialize the Hermes bridge if enabled."""
        if not self.hermes_enabled:
            return
        try:
            from hermes_bridge import HermesBridge
            self._hermes_bridge = HermesBridge(ollama_url=self.ollama_url)
        except ImportError:
            print("[TaskRouter] hermes_bridge not available")
        except Exception as e:
            print(f"[TaskRouter] Failed to init HermesBridge: {e}")

    def _detect_hermes_skill(self, task_text: str) -> Optional[str]:
        """Detect if task matches a Hermes skill."""
        task_lower = task_text.lower()

        for skill, keywords in self.HERMES_SKILL_KEYWORDS.items():
            if any(kw in task_lower for kw in keywords):
                return skill

        return None

    def check_hermes_health(self) -> bool:
        """Check if Hermes is available."""
        if self._hermes_healthy is not None:
            return self._hermes_healthy

        if not self._hermes_bridge:
            self._hermes_healthy = False
            return False

        self._hermes_healthy = self._hermes_bridge.check_hermes_available()
        return self._hermes_healthy

    def _classify_task_type(self, task_text: str) -> str:
        """Classify task into a type for routing."""
        task_lower = task_text.lower()

        # Check classification FIRST (before code which has "class" in it)
        if any(kw in task_lower for kw in ["classify", "categorize", "sort", "organize", "triage"]):
            return "classification"
        if any(kw in task_lower for kw in ["summarize", "summary", "brief", "overview"]):
            return "summarization"
        if any(kw in task_lower for kw in ["code", "function", "implement", "bug", "fix", "refactor"]):
            return "code_generation"
        if any(kw in task_lower for kw in ["extract", "parse", "format", "convert", "data"]):
            return "data_processing"
        if any(kw in task_lower for kw in ["write", "draft", "compose", "create content", "tweet", "blog"]):
            return "creative_writing"
        if any(kw in task_lower for kw in ["analyze", "compare", "evaluate", "research", "investigate"]):
            return "complex_reasoning"
        return "general"

    def _requires_claude(self, task_text: str) -> Tuple[bool, str]:
        """Check if task requires Claude (file ops, execution, etc)."""
        task_lower = task_text.lower()

        for kw in self.CLAUDE_KEYWORDS:
            if kw in task_lower:
                return True, f"Contains '{kw}' - requires Claude"

        if re.search(r'[/\\][\w\-\.]+[/\\]', task_text) or re.search(r'\.\w{2,4}$', task_text):
            return True, "Contains file paths - requires Claude"

        if re.search(r'`[^`]+`', task_text) or re.search(r'\$\(', task_text):
            return True, "Contains shell commands - requires Claude"

        return False, ""

    def _is_privacy_sensitive(self, text: str) -> bool:
        """Check for privacy-sensitive content."""
        text_lower = text.lower()
        return any(p in text_lower for p in self.PRIVACY_PATTERNS)

    def _estimate_complexity(self, task_text: str) -> float:
        """Estimate task complexity (0-1)."""
        if self._router:
            return self._router.estimate_complexity(task_text)

        score = 0.5
        if len(task_text) > 500:
            score += 0.2
        elif len(task_text) < 100:
            score -= 0.1

        complexity_words = ["analyze", "compare", "evaluate", "synthesize",
                          "design", "architect", "optimize", "comprehensive"]
        task_lower = task_text.lower()
        score += sum(0.05 for w in complexity_words if w in task_lower)

        simple_words = ["summarize", "list", "extract", "count", "format", "check"]
        score -= sum(0.05 for w in simple_words if w in task_lower)

        return max(0.0, min(1.0, score))

    def _select_best_model(
        self,
        task_type: str,
        complexity: float,
        prefer_local: bool = True,
        task_text: str = ""
    ) -> Tuple[str, str, str]:
        """
        Select the best model for a task type and complexity.

        Routing priority:
        1. Hermes with skill (if skill matches and available)
        2. Local Ollama (for simple tasks)
        3. OpenRouter free (for medium tasks)
        4. Claude (for complex tasks)

        Routing tiers by task type:
        - classification: up to 0.9 complexity -> local
        - summarization: up to 0.7 complexity -> local/openrouter
        - code_generation: up to 0.6 complexity -> local/openrouter
        - data_processing: up to 0.8 complexity -> local
        - creative_writing: up to 0.5 complexity -> local/openrouter
        - complex_reasoning: up to 0.3 complexity -> local (deepseek)
        - general: up to 0.6 complexity -> local

        Returns:
            (model_name, provider, hermes_skill)
        """
        hermes_ok = self.hermes_enabled and self.check_hermes_health()
        ollama_ok = prefer_local and self.check_ollama_health()

        # Check if OpenRouter is enabled in config
        config = self._load_config()
        openrouter_enabled = config.get("openrouter_enabled", True)
        openrouter_ok = openrouter_enabled and bool(self.openrouter_api_key)

        # Check for Hermes skill match first (highest priority for skill-based tasks)
        if hermes_ok and task_text:
            hermes_skill = self._detect_hermes_skill(task_text)
            if hermes_skill and complexity < 0.7:
                return f"hermes:{hermes_skill}", "hermes", hermes_skill

        # Task-type specific thresholds for local routing
        local_thresholds = {
            "classification": (0.9, "qwen2.5:3b"),
            "summarization": (0.7, "qwen2.5:7b"),
            "code_generation": (0.6, "qwen2.5-coder:7b"),
            "data_processing": (0.8, "qwen2.5:7b"),
            "creative_writing": (0.5, "qwen2.5:7b"),
            "complex_reasoning": (0.3, "deepseek-r1:latest"),
            "general": (0.6, "qwen2.5:7b"),
        }

        threshold, local_model = local_thresholds.get(task_type, (0.5, "qwen2.5:7b"))

        # Try local Ollama first (expanded threshold when OpenRouter disabled)
        effective_threshold = 0.75 if (not openrouter_ok and ollama_ok) else threshold
        if ollama_ok and complexity < effective_threshold:
            return local_model, "ollama", ""

        # Try OpenRouter for medium complexity (if enabled)
        if openrouter_ok and complexity < 0.75:
            openrouter_models = {
                "summarization": "nvidia/nemotron-3-nano-30b-a3b:free",
                "general": "nvidia/nemotron-3-nano-30b-a3b:free",
                "creative_writing": "nvidia/nemotron-3-nano-30b-a3b:free",
                "classification": "nvidia/nemotron-3-nano-30b-a3b:free",
                "data_processing": "nvidia/nemotron-3-nano-30b-a3b:free",
                "complex_reasoning": "qwen/qwen3-next-80b-a3b-instruct:free",
                "code_generation": "openai/gpt-oss-120b:free",
            }
            model = openrouter_models.get(task_type, "nvidia/nemotron-3-nano-30b-a3b:free")
            return model, "openrouter", ""

        # Complex tasks go to Claude
        return "claude", "claude", ""

    def should_use_local(self, task_text: str, force_cloud: bool = False, prefer_local: bool = True) -> RoutingResult:
        """
        Determine optimal routing for a task.

        Args:
            task_text: The task description
            force_cloud: If True, skip local/openrouter and use Claude
            prefer_local: If True, prefer Ollama over OpenRouter for simple tasks

        Returns:
            RoutingResult with routing decision
        """
        if force_cloud:
            return RoutingResult(
                use_local=False,
                model="claude",
                provider="claude",
                reason="Forced cloud routing",
                task_type="forced",
                complexity=1.0
            )

        # Check if task requires Claude
        requires_claude, reason = self._requires_claude(task_text)
        if requires_claude:
            return RoutingResult(
                use_local=False,
                model="claude",
                provider="claude",
                reason=reason,
                task_type="complex",
                complexity=1.0
            )

        # Privacy-sensitive content always local
        if self._is_privacy_sensitive(task_text):
            model, provider = "qwen2.5:7b", "ollama"
            if not self.check_ollama_health():
                # Fallback to Claude if no local option
                return RoutingResult(
                    use_local=False,
                    model="claude",
                    provider="claude",
                    reason="Privacy content but Ollama unavailable",
                    task_type="privacy",
                    complexity=0.5
                )
            return RoutingResult(
                use_local=True,
                model=model,
                provider=provider,
                reason="Privacy-sensitive content - using local model",
                task_type="privacy",
                complexity=0.0
            )

        # Classify and estimate complexity
        task_type = self._classify_task_type(task_text)
        complexity = self._estimate_complexity(task_text)

        # Select best model (now returns 3 values: model, provider, hermes_skill)
        model, provider, hermes_skill = self._select_best_model(
            task_type, complexity, prefer_local, task_text
        )

        use_local = provider in ["hermes", "ollama", "openrouter"]

        return RoutingResult(
            use_local=use_local,
            model=model,
            provider=provider,
            reason=f"Complexity {complexity:.2f}, type {task_type} -> {provider}",
            task_type=task_type,
            complexity=complexity,
            hermes_skill=hermes_skill
        )

    def execute_local(self, task_text: str, model: str, system_prompt: str = "") -> dict:
        """Execute task on local Ollama model."""
        start_time = time.time()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": task_text})

            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
                timeout=120
            )
            response.raise_for_status()
            result = response.json()

            latency_ms = int((time.time() - start_time) * 1000)
            content = result.get("message", {}).get("content", "")

            self.metrics.append({
                "timestamp": time.time(),
                "model": model,
                "provider": "ollama",
                "latency_ms": latency_ms
            })

            return {
                "success": True,
                "content": content,
                "model": model,
                "provider": "ollama",
                "latency_ms": latency_ms,
                "tokens_estimated": (len(task_text) + len(content)) // 4
            }
        except Exception as e:
            return {"success": False, "error": str(e), "content": ""}

    def execute_openrouter(self, task_text: str, model: str, system_prompt: str = "") -> dict:
        """Execute task via OpenRouter API."""
        if not self.openrouter_api_key:
            return {"success": False, "error": "No OpenRouter API key", "content": ""}

        start_time = time.time()

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": task_text})

            response = requests.post(
                self.openrouter_url,
                headers={
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://openclaw.local",
                    "X-Title": "OpenClaw Kanban"
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 2048
                },
                timeout=120
            )
            response.raise_for_status()
            result = response.json()

            latency_ms = int((time.time() - start_time) * 1000)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            self.metrics.append({
                "timestamp": time.time(),
                "model": model,
                "provider": "openrouter",
                "latency_ms": latency_ms
            })

            return {
                "success": True,
                "content": content,
                "model": model,
                "provider": "openrouter",
                "latency_ms": latency_ms,
                "tokens_estimated": result.get("usage", {}).get("total_tokens", 0)
            }
        except Exception as e:
            return {"success": False, "error": str(e), "content": ""}

    def execute_hermes(self, task_text: str, skill: str = None, system_prompt: str = "") -> dict:
        """Execute task via Hermes CLI with optional skill."""
        if not self._hermes_bridge:
            return {"success": False, "error": "Hermes bridge not available", "content": ""}

        start_time = time.time()

        try:
            if skill:
                result = self._hermes_bridge.execute_hermes_cli(task_text, skill=skill)
            else:
                result = self._hermes_bridge.execute(task_text)

            latency_ms = result.latency_ms

            self.metrics.append({
                "timestamp": time.time(),
                "model": f"hermes:{skill}" if skill else "hermes",
                "provider": "hermes",
                "latency_ms": latency_ms
            })

            return {
                "success": result.success,
                "content": result.content,
                "model": f"hermes:{skill}" if skill else "hermes",
                "provider": "hermes",
                "latency_ms": latency_ms,
                "skill_used": skill,
                "error": result.error if not result.success else None
            }
        except Exception as e:
            return {"success": False, "error": str(e), "content": ""}

    def execute(self, task_text: str, routing: RoutingResult, system_prompt: str = "") -> dict:
        """Execute task using the specified routing."""
        if routing.provider == "hermes":
            return self.execute_hermes(task_text, skill=routing.hermes_skill, system_prompt=system_prompt)
        elif routing.provider == "ollama":
            return self.execute_local(task_text, routing.model, system_prompt)
        elif routing.provider == "openrouter":
            return self.execute_openrouter(task_text, routing.model, system_prompt)
        else:
            return {"success": False, "error": "Claude requires tmux execution", "content": ""}

    def check_ollama_health(self) -> bool:
        """Check if Ollama is running."""
        if self._ollama_healthy is not None:
            return self._ollama_healthy

        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            self._ollama_healthy = response.status_code == 200
        except:
            self._ollama_healthy = False
        return self._ollama_healthy

    def check_openrouter_health(self) -> bool:
        """Check if OpenRouter API key is valid."""
        if not self.openrouter_api_key:
            return False
        if self._openrouter_healthy is not None:
            return self._openrouter_healthy

        try:
            response = requests.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {self.openrouter_api_key}"},
                timeout=5
            )
            self._openrouter_healthy = response.status_code == 200
        except:
            self._openrouter_healthy = False
        return self._openrouter_healthy

    def list_models(self) -> list:
        """List available models."""
        models = []

        # Ollama models
        if self.check_ollama_health():
            try:
                response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models.extend([m["name"] for m in response.json().get("models", [])])
            except:
                pass

        # OpenRouter free models
        if self.openrouter_api_key:
            models.extend(list(self.OPENROUTER_MODELS.keys()))

        return models

    def get_routing_stats(self) -> dict:
        """Get routing statistics."""
        hermes_count = sum(1 for m in self.metrics if m.get('provider') == 'hermes')
        ollama_count = sum(1 for m in self.metrics if m.get('provider') == 'ollama')
        openrouter_count = sum(1 for m in self.metrics if m.get('provider') == 'openrouter')
        cloud_count = sum(1 for m in self.metrics if m.get('provider') == 'claude')
        total = len(self.metrics)

        return {
            "total_tasks": total,
            "hermes_tasks": hermes_count,
            "local_tasks": ollama_count,
            "openrouter_tasks": openrouter_count,
            "cloud_tasks": cloud_count,
            "hermes_percentage": (hermes_count / total * 100) if total > 0 else 0,
            "local_percentage": (ollama_count / total * 100) if total > 0 else 0,
            "openrouter_percentage": (openrouter_count / total * 100) if total > 0 else 0,
            "avg_hermes_latency_ms": sum(m.get('latency_ms', 0) for m in self.metrics if m.get('provider') == 'hermes') / max(hermes_count, 1),
            "avg_local_latency_ms": sum(m.get('latency_ms', 0) for m in self.metrics if m.get('provider') == 'ollama') / max(ollama_count, 1),
            "avg_openrouter_latency_ms": sum(m.get('latency_ms', 0) for m in self.metrics if m.get('provider') == 'openrouter') / max(openrouter_count, 1)
        }

    def get_available_providers(self) -> dict:
        """Get status of all providers."""
        return {
            "hermes": {
                "available": self.check_hermes_health(),
                "skills": list(self.HERMES_SKILLS.values())
            },
            "ollama": {
                "available": self.check_ollama_health(),
                "models": list(self.OLLAMA_MODELS.keys())
            },
            "openrouter": {
                "available": bool(self.openrouter_api_key),
                "models": list(self.OPENROUTER_MODELS.keys())
            },
            "claude": {
                "available": True,
                "models": ["claude-sonnet", "claude-opus"]
            }
        }


# Convenience function
def should_route_local(task_text: str) -> Tuple[bool, str, str, str]:
    """Quick routing check. Returns (use_local, model, provider, reason)."""
    router = KanbanRouter()
    result = router.should_use_local(task_text)
    return result.use_local, result.model, result.provider, result.reason


if __name__ == "__main__":
    router = KanbanRouter()

    print("=" * 60)
    print("Task Router Test - Multi-Provider")
    print("=" * 60)

    # Check providers
    providers = router.get_available_providers()
    print(f"\nOllama: {'OK' if providers['ollama']['available'] else 'UNAVAILABLE'}")
    print(f"OpenRouter: {'OK' if providers['openrouter']['available'] else 'NO API KEY'}")
    print(f"Claude: Always available (via tmux)")

    if providers['ollama']['available']:
        models = router.list_models()
        print(f"\nAvailable models: {', '.join(models[:8])}...")

    # Test routing decisions
    test_tasks = [
        "summarize the daily metrics",
        "implement a new API endpoint for user auth",
        "classify these support tickets by priority",
        "fix the bug in src/utils/parser.js",
        "create a brief status report",
        "analyze the codebase architecture and propose improvements",
        "list the top 5 items from the backlog",
        "git commit and push the changes",
        "draft a tweet about Bitcoin halving cycles"
    ]

    print("\nRouting decisions:")
    print("-" * 60)

    for task in test_tasks:
        result = router.should_use_local(task)
        print(f"[{result.provider:10}] {result.model:35} | {task[:35]}...")
        print(f"            Complexity: {result.complexity:.2f}, Type: {result.task_type}")
