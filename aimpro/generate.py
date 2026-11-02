"""Write or check deterministic schemas generated from the unchanged export."""

import argparse
import json
from pathlib import Path

from aimpro.audit import DEFAULT_PROJECT
from aimpro.contracts import Contracts


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "docs/aimpro/generated"


def artifacts(contracts):
    schemas = contracts.schemas()
    return {"manifest.json": contracts.manifest(),
            **{f"{name}.schema.json": schema for name, schema in schemas.items()}}


def generate(project=DEFAULT_PROJECT, output=DEFAULT_OUTPUT, *, check=False):
    expected = {name: json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
                for name, value in artifacts(Contracts(project)).items()}
    output = Path(output)
    if check:
        actual = {p.name for p in output.glob("*.json")}
        return actual == set(expected) and all(
            (output / name).read_text(encoding="utf-8") == value for name, value in expected.items())
    if output.exists() and {p.name for p in output.glob("*.json")} - set(expected):
        raise ValueError("Output contains unexpected JSON files; use a clean generation directory")
    output.mkdir(parents=True, exist_ok=True)
    for name, value in expected.items():
        (output / name).write_text(value, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", nargs="?", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not generate(args.project, args.output, check=args.check):
        parser.exit(1, "Generated contracts differ; regenerate and review the artifacts.\n")


if __name__ == "__main__":
    main()
