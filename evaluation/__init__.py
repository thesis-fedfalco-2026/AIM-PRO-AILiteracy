"""Adversarial evaluation suite for the learning-request path (#25)."""
from pathlib import Path

from agent_system.telemetry import configure_vendor_privacy

# As main.py does, and before any CrewAI import: CrewAI decides at import whether this
# is a first run, which would enable vendor tracing defaults and print a consent panel
# on stdout.
configure_vendor_privacy(Path(__file__).resolve().parents[1])
