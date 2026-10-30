from __future__ import annotations

from collections import Counter

from learning.contracts import EntityRef, Finding
from learning.context import Snapshot
from learning.metamodel import load_contract
from learning.rules import evaluate_rule


def _refs(items) -> set[EntityRef]:
    return {EntityRef.model_validate(item) for item in items}


def _cyclic(graph: dict[EntityRef, set[EntityRef]]) -> bool:
    visited, active = set(), set()

    def visit(node):
        if node in active:
            return True
        if node in visited:
            return False
        active.add(node)
        if any(visit(child) for child in graph.get(node, ())):
            return True
        active.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def validate_snapshot(snapshot: Snapshot) -> tuple[Finding, ...]:
    findings = list(snapshot.findings)
    contract = load_contract()
    for kind, relation, code in (("Topic", "parentTopics", "R04"), ("ProcessNode", "children", "R06")):
        graph = {entity.ref: _refs(entity.fields[relation]) for entity in snapshot.of_type(kind)}
        if _cyclic(graph):
            findings.append(Finding(code=code, target=kind, reason="La gerarchia contiene un ciclo."))
    obligations = {}
    for prerequisite in snapshot.of_type("Prerequisite"):
        if prerequisite.fields["kind"] == "MANDATORY":
            dependent = EntityRef.model_validate(prerequisite.fields["dependent"])
            obligations.setdefault(dependent, set()).add(EntityRef.model_validate(prerequisite.fields["requiredTarget"]))
    if _cyclic(obligations):
        findings.append(Finding(code="R05", target="Prerequisite", reason="Ciclo di prerequisiti obbligatori."))
    for entity in snapshot.entities.values():
        f = entity.fields
        if entity.type == "DomainModel" and any(
            contract.entity_types[ref["type"]]["instanceLayer"] != "domain_configuration" for ref in f["definitions"]
        ):
            findings.append(Finding(code="R02", target=entity.id, reason="Il modello contiene riferimenti a stato operativo."))
        if entity.type == "ProcessNode" and ((f["kind"] == "PHASE" and f["activities"]) or
                                              (f["kind"] == "UNIT" and (f["children"] or f.get("composition")))):
            findings.append(Finding(code="R06", target=entity.id, reason="Struttura PHASE/UNIT incompatibile."))
        if entity.type == "LearningDesign":
            try:
                root = snapshot.get(f["root"])
                if root.fields["kind"] != "PHASE":
                    raise ValueError()
                parents, visited, pending = Counter(), set(), [root]
                while pending:
                    node = pending.pop()
                    if node.ref in visited:
                        continue
                    visited.add(node.ref)
                    for child in node.fields["children"]:
                        child_ref = EntityRef.model_validate(child)
                        parents[child_ref] += 1
                        pending.append(snapshot.get(child_ref))
                if any(count > 1 for count in parents.values()):
                    raise ValueError()
            except ValueError:
                findings.append(Finding(code="R06", target=entity.id, reason="Radice o genitori del percorso non validi."))
        if entity.type == "Rubric":
            keys = [item["key"] for item in f["criteria"]]
            duplicate = len(keys) != len(set(keys))
            for criterion in f["criteria"]:
                levels = [item["key"] for item in criterion["levels"]]
                duplicate |= len(levels) != len(set(levels))
            if duplicate:
                findings.append(Finding(code="R10", target=entity.id, reason="Chiavi duplicate nella rubrica."))
        if entity.type == "AssessmentSpecification":
            covered = set()
            for activity in f["activities"]:
                try:
                    covered |= _refs(snapshot.get(activity).fields["outcomes"])
                except ValueError:
                    pass
            if not _refs(f["outcomes"]) <= covered:
                findings.append(Finding(code="R07", target=entity.id, reason="Verifica priva della copertura dichiarata."))
    return tuple(findings)


def check_readiness(snapshot: Snapshot, target: EntityRef, action: str, *, learner_ref=None,
                    policy=None, subject_key=None) -> tuple[Finding, ...]:
    findings, visited = [], set()

    def check(ref):
        ref = EntityRef.model_validate(ref)
        if ref in visited:
            return set()
        visited.add(ref)
        try:
            item = snapshot.get(ref)
        except ValueError:
            findings.append(Finding(code="R02", target=ref.id, reason="Oggetto necessario non disponibile."))
            return set()
        f = item.fields
        for prerequisite in snapshot.active_domain():
            if prerequisite.type != "Prerequisite":
                continue
            p = prerequisite.fields
            if EntityRef.model_validate(p["dependent"]) != ref:
                continue
            status = "UNKNOWN"
            if p.get("satisfactionRule"):
                rule_ref = EntityRef.model_validate(p["satisfactionRule"])
                states = [snapshot.get(state_ref) for state_ref in snapshot.context.fields["learningStates"]
                          if EntityRef.model_validate(state_ref) in snapshot.entities
                          and snapshot.get(state_ref).fields["outcome"] == p["requiredTarget"]
                          and learner_ref is not None
                          and snapshot.get(state_ref).fields["learner"] == learner_ref.model_dump()]
                inputs = {"acquired": all(state.fields["progress"] == "ACQUIRED" for state in states)} if states else {}
                status = evaluate_rule(rule_ref, snapshot, inputs, snapshot.rule_bindings)
            if status != "SATISFIED":
                severity = "WARNING" if p["kind"] in {"RECOMMENDED", "RECOMMENDED_SEQUENCE"} else "BLOCKING"
                findings.append(Finding(code="R05", target=item.id, severity=severity,
                                        reason="Prerequisito non soddisfatto o non determinabile."))
        if item.type == "LearningDesign":
            coverage = check(f["root"])
            if not _refs(f["outcomes"]) <= coverage:
                findings.append(Finding(code="R07", target=item.id, reason="Percorso senza copertura completa degli obiettivi."))
            return coverage
        if item.type == "ProcessNode":
            children = f["children"] if f["kind"] == "PHASE" else f["activities"]
            if not children or (f["kind"] == "PHASE" and not f.get("composition")):
                findings.append(Finding(code="R06", target=item.id, reason="Nodo in bozza, non pronto."))
            if action == "advance" and not f.get("completionRule"):
                findings.append(Finding(code="R06", target=item.id, reason="Manca la regola di completamento."))
            coverage = set()
            for child in children:
                coverage |= check(child)
            if not _refs(f["outcomes"]) <= coverage:
                findings.append(Finding(code="R07", target=item.id, reason="Obiettivi del nodo non coperti."))
            return coverage
        if item.type == "ActivityDefinition":
            from learning.decisions import approval_valid
            from learning.policies import scope_allows
            for requirement in f["resourceRequirements"]:
                try:
                    required = snapshot.get(requirement)
                except ValueError:
                    findings.append(Finding(code="R08", target=item.id, reason="Requisito di risorsa irrisolto."))
                    continue
                if required.fields["mandatory"] and not any(
                    binding.fields.get("requirement") == requirement and binding.fields["valid"]
                    and binding.ref.model_dump() in snapshot.context.fields["resourceBindings"]
                    and policy is not None and approval_valid(binding, snapshot, policy)
                    and scope_allows(policy, binding.fields["usageScope"], snapshot.context.id, subject_key, (item.id,))
                    for binding in snapshot.of_type("ResourceBinding")
                ):
                    findings.append(Finding(code="R08", target=item.id, reason="Risorsa obbligatoria non approvata o assente."))
            return _refs(f["outcomes"])
        return set()

    check(target)
    return tuple(findings)
