"""Live, free OpenRouter generation with real MCP stdio and synthetic evidence."""

import argparse
import logging
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from learning.context import LearningRequest
from learning.contracts import EntityRef
from learning.metamodel import load_contract, validate_entity
from learning.policies import TrustedPolicy
from learning.service import LearningService
from learning.store import LearningStore
import os
import time
from urllib.parse import urlparse

from main import BASE_DIR, build_orchestrator
from agent_system.config import ConfigurationError, load_model_catalog, parse_agent_file
from dotenv import load_dotenv


QUESTION = (
    "What deployment procedure does the synthetic technical deployment guide prescribe? "
    "Use one Teacher task with authorized search_documents retrieval, query deployment, k 3. "
    "Cite the actual Resource reference supplied in source_refs. "
    "State explicitly that these are synthetic example steps, not a verified real-world procedure or completed deployment."
)
SOURCE = "technical-deployment-guide"


def prepare_demo(store, factory):
    bundle = json.loads((BASE_DIR / "tests/fixtures/alm/acceptance.json").read_text())
    contract = load_contract()
    service = LearningService(store, contract, TrustedPolicy.model_validate(bundle["policy"]), factory)
    service.bootstrap("demo", "admin")
    proposal = service.propose("demo", "admin", tuple(EntityRef.model_validate(ref) for ref in bundle["targets"]),
        tuple(validate_entity(item, contract) for item in bundle["candidates"]), bundle["explanation"])
    service.decide("demo", "admin", proposal.ref, "APPROVE", "Fixture sintetica esaminata per smoke")
    service.apply("demo", "admin", proposal.ref, "demo-activation")
    return service


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=1)
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be positive")
    load_dotenv(BASE_DIR / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from crewai.events.utils.console_formatter import set_suppress_console_output

    set_suppress_console_output(True)
    for handler in logging.getLogger().handlers:
        handler.addFilter(logging.Filter("agent_system"))
    try:
        catalog = load_model_catalog(BASE_DIR / "model.properties")
        # This command must never switch generation providers silently.
        profiles = {catalog.lead_profile} | {
            parse_agent_file(path).profile for path in (BASE_DIR / "agents").glob("*.md")
        }
        if profiles != {"openrouter"}:
            raise ConfigurationError("Smoke requires the openrouter profile for Lead and workers")
        profile = catalog.profiles["openrouter"]
        if urlparse(profile.base_url or "").hostname != "openrouter.ai":
            raise ConfigurationError("Smoke requires a model at openrouter.ai")
        if not profile.model.endswith(":free") or profile.allow_paid:
            raise ConfigurationError("Smoke requires a :free model with allow_paid = false")
        for index in range(1, args.runs + 1):
            started = time.monotonic()
            print(f"RUN {index}/{args.runs}: {catalog.profiles['openrouter'].model}", flush=True)
            orchestrator = build_orchestrator(model_catalog=catalog, environ={**os.environ, "SEARCH_BACKEND": "mock"})
            searches, workers = [], []
            search, worker = orchestrator.search, orchestrator.task_tool.worker

            def checked_search(query, k, *, scope):
                result = search(query, k, scope=scope)
                searches.append(result)
                return result

            def checked_worker(config, task):
                result = worker(config, task)
                workers.append((config.name, result))
                return result

            orchestrator.search = checked_search
            orchestrator.task_tool.worker = checked_worker
            with TemporaryDirectory() as temporary, LearningStore(Path(temporary) / "demo.sqlite") as store:
                service = prepare_demo(store, lambda: orchestrator)
                request = LearningRequest(request_id=f"smoke-{index}",context_ref=store.read_context("demo").ref,
                    subject_key="learner",text=QUESTION,topic_refs=(EntityRef(type="Topic",id="deployment",version="1"),))
                answer = service.request(request)
                if store.read_context("demo").fields["learningStates"]:
                    raise ValueError("Explanation must not assign learning progress")
            checks = {
                "retrieval_count": len(searches) == 1,
                "scoped_source": len(searches) == 1 and any(
                    doc["metadata"]["source"] == SOURCE for doc in searches[0]["documents"]),
                "worker_count": len(workers) == 1,
                "teacher_output": len(workers) == 1 and workers[0][0] == "lesson-explainer" and bool(workers[0][1].content.strip()),
                "answer_kind": answer.kind == "ANSWER",
                "source_citation": any(c.source.id == SOURCE for c in answer.citations),
                "task_success": any(e.type == "TaskResult" and e.fields["status"] == "SUCCEEDED" for e in orchestrator.last_records),
            }
            failed = [name for name, passed in checks.items() if not passed]
            if failed:
                print(f"FAIL {index}/{args.runs}: {', '.join(failed)}")
                return 1
            print(f"PASS {index}/{args.runs} ({time.monotonic() - started:.1f}s): plan, MCP, worker, citation", flush=True)
            print(answer.model_dump_json(indent=2), flush=True)
    except ConfigurationError as error:
        print(f"FAIL: {error}")
        return 2
    except Exception as error:
        print(f"FAIL: {type(error).__name__}; see agent_system diagnostics")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
