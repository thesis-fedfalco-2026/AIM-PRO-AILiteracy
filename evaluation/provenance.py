"""Content-free implementation identity and an allowlist of effective settings."""
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import json
import platform
import subprocess

from agent_system.config import OrchestratorSettings, load_model_catalog


def fingerprint(value) -> str:
    return sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def implementation(base_dir: Path) -> dict:
    # Hash only implementation/configuration and synthetic fixtures, never .env,
    # databases, runtime archives, learner files or arbitrary untracked paths.
    patterns = ("evaluation/*.py", "agent_system/*.py", "learning/*.py", "document_search/*.py", "aimpro/*.py",
                "agents/**/*.md", "control/*.md", "categories/*.md", "skills/**/SKILL.md",
                "tests/fixtures/alm/*.json", "docs/resources/metamodello-agnostico-apprendimento.json",
                "main.py", "model.properties", "runtime.properties", "requirements.txt")
    files = sorted({p for pattern in patterns for p in base_dir.glob(pattern) if p.is_file()})
    digests = {p.relative_to(base_dir).as_posix(): sha256(p.read_bytes()).hexdigest() for p in files}
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=base_dir,
                                         stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=base_dir,
                                            stderr=subprocess.DEVNULL, text=True))
    except (OSError, subprocess.SubprocessError):
        commit, dirty = None, None
    return {"commit": commit, "dirty": dirty, "implementation_sha256": fingerprint(digests), "files_sha256": digests}


def configuration(base_dir: Path, *, mode: str, planning_mode: str, case_ids, repeat: int) -> dict:
    catalog = load_model_catalog(base_dir / "model.properties")
    live = mode == "live"
    local = live and catalog.lead_profile == "local"
    settings = catalog.orchestrator if local else OrchestratorSettings(max_steps=6 if not live else catalog.orchestrator.max_steps)
    profile = catalog.profiles[catalog.lead_profile]
    return {
        "planning_mode": planning_mode, "case_ids": list(case_ids), "repeat": repeat,
        "search_backend": "mock", "search_unlimited_text": live and not local,
        "worker": "injected", "semantic_review": "live" if live else "ACCEPT",
        "benign_synthesis": "live" if live else "echo",
        "attack_synthesis": "injected", "orchestrator": settings.model_dump(),
        "lead": ({"profile": catalog.lead_profile, "provider": profile.provider, "model": profile.model,
                  "stream": profile.stream, "allow_paid": profile.allow_paid,
                  "settings": catalog.settings.model_dump()} if live else {"provider": "scripted"}),
        "python": platform.python_version(),
        "packages": {name: version(name) for name in ("crewai", "pydantic", "mcp")},
    }
