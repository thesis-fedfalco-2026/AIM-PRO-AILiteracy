import os


# Keep tests offline; these are CrewAI's supported opt-out switches and must be
# set before importing CrewAI.
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["CREWAI_TRACING_ENABLED"] = "false"
