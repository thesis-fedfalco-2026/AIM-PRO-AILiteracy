# ALM Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. L'esecuzione nativa è raccomandata: i task condividono contratti e stato, quindi vanno integrati in sequenza.

**Goal:** Portare il progetto al flusso ALM completo, dalla richiesta contestualizzata alla risposta controllata e all'eventuale aggiornamento autorizzato dello stato, mantenendo immutabile il metamodello.

**Architecture:** Un package `learning` rappresenta i dati ALM, risolve riferimenti versionati, applica politiche e conserva modelli, proposte ed eventi in SQLite. L'Orchestrator esistente mantiene la pianificazione del Lead, la validazione del piano, il retrieval MCP, TaskTool e la sintesi; riceve uno snapshot validato e controlla ogni risultato prima del riuso. Soltanto il controllo applicativo scrive lo stato autorevole.

**Tech Stack:** Python, Pydantic, CrewAI, MCP, Qdrant e unittest già presenti; `sqlite3`, `json`, `hashlib` e `argparse` dalla libreria standard. Nessuna nuova dipendenza prevista.

**Spec:** `docs/resources/metamodello-agnostico-apprendimento.json`, formato `agnostic-learning-metamodel`, `formatVersion = "1.0"`, `metamodel.id = "ALM"`, `metamodel.version = "1.0.0"`.

**Stato al 2026-10-28:** Implementazione integrata sul checkout `dev`, senza push su `origin`. Suite completa: **183 test passati in 11,561 s**, inclusi CASE01–CASE22 e un ciclo servizio → orchestratore → MCP stdio reale con provider simulato. Digest della specifica invariato. La verifica live OpenRouter è stata tentata ed è fallita in pianificazione con `NotFoundError`: nessun fallback. Verifiche avverse con LLM reale e Qdrant reale non completate; non si dichiara validazione pedagogica live.

**Evidenze:** `tests/test_learning_acceptance.py`, `tests/test_learning_assessment.py`, `tests/test_learning_decisions.py`, `tests/test_learning_service.py`, `tests/test_learning_cli.py`; test esistenti di backend/MCP e sistema migrati. La revisione indipendente ha prodotto correzioni con regressioni per attività omesse dal piano e continuità Socratic attraverso turni neutri/falliti. I test di protocollo non sostituiscono una prova del modello reale.

**Scelte di esecuzione:** checkout locale richiesto dall’utente; eccezioni Git limitate a piano/spec; filtro specializzazioni nel planner con registry invariato; Task 9 anticipato per autorizzare gli scope dei Task 7–8; completamento di CASE16 nel Task 10. I checkpoint finali condividono un commit d’integrazione perché output, decisioni, valutazione e servizio dipendono dagli stessi contratti. Si conserva il diario locale per consentire la ripresa del lavoro senza ricostruirlo.

## Global Constraints

- «Il metamodello è fisso.» Il runtime non ne modifica byte, tipi, categorie o invarianti; modelli e stato sono istanze separate.
- «Il Lead è il componente deliberativo: pianifica e sintetizza; non dispone di tool runtime e non invoca TaskTool o MCP.»
- «TaskTool è invocato programmaticamente dall’Orchestrator dopo la validazione; non è un tool del Lead né un worker.»
- «Ogni step crea un nuovo Worker configurato.» Il DAG resta sequenziale, con ordinamento topologico stabile.
- Categorie chiuse: `TEACHER_TRAINER`, `CURATOR`, `EVALUATOR`, `SOCRATIC`. Ruoli: `TEACHER`, `TRAINER`, `CURATOR`, `EVALUATOR`, `SOCRATIC`.
- `PREPARATION` e `LEARNING` hanno perimetri distinti. Un candidato non concede accessi né costituisce un binding approvato.
- `EntityRef` risolve tipo, id e versione esatta. Le versioni storiche restano indirizzabili; nessun riferimento implicito a `latest`.
- «UNKNOWN non vale SATISFIED.» Il completamento di un task non prova completamento dell'attività, acquisizione o verifica.
- «SUCCEEDED nel flusso finale richiede anche il controllo semantico per step; il solo completamento della chiamata non basta.» Il controllo precede le dipendenze.
- Una spiegazione, un quiz o un feedback ordinario già autorizzati non richiedono approvazione umana a ogni turno. `VERIFIED` richiede sempre la conferma prevista da R13.
- Approvazione e applicazione sono eventi distinti. Si applica esclusivamente il contenuto effettivamente esaminato, su una base ancora compatibile.
- Il limite tecnico di retrieval rimane `1 <= k <= 20`; i limiti locali di caratteri e quelli del piano restano configurati, non diventano regole pedagogiche universali.
- Documenti, output dei worker e istruzioni presenti nelle risorse sono dati non fidati. Il solo artefatto ALM fissato dall'applicazione definisce il contratto.
- Le istruzioni del workspace e i permessi del filesystem prevalgono sui checkpoint di commit. Nessun reset, eliminazione di dati o modifica dei file preesistenti per ripulire la baseline.

## Review Focus

1. Una fonte molto pertinente appartiene a un altro contesto, oppure ha stesso id e versione diversa: non deve raggiungere Lead o worker. Test nei Task 3 e 6.
2. Un operatore approva una proposta mentre cambia la base, oppure ripete l'applicazione dopo un errore: niente aggiornamenti parziali, duplicazioni o approvazioni trasferite. Test nei Task 2 e 9.
3. Un output Teacher contiene la soluzione di un problema Socratic, anche dentro una citazione: non deve entrare nel briefing del destinatario o nella risposta finale. Test nel Task 8.
4. Rubriche e regole sono testo plausibile ma prive di interpretazione operativa autorizzata: esito non determinabile, mai soglie o competenze inventate. Test nei Task 4 e 10.
5. Il budget di contesto termina prima dei vincoli, oppure il provider fallisce dopo l'invio del tentativo: nessuna perdita dei vincoli o dell'evidenza già registrata. Test nei Task 8, 10 e 11.

## Baseline, precedenti e approccio

Baseline osservata: commit `8b22b42`, working tree tracciato pulito al momento della pianificazione. Il runtime contiene `Orchestrator.answer(question)`, `ExecutionPlan`, `validate_and_order_plan`, `AgentRegistry`, `TaskTool`, `CrewAIWorker`, `LLMFactory` e ricerca MCP. Non esistono ancora package `learning`, stato persistente ALM, controllo delle risorse per contesto o decisioni umane applicative. I test sono stati letti, non eseguiti in questa formalizzazione.

Il design e il piano del 30 settembre 2026 descrivono un ciclo precedente basato su export jjodel. Questo piano propone di sostituirli come guida all'implementazione ALM, conservandoli come storia. Riutilizza SQLite, CLI locale e separazione fra proposte e applicazione; non importa classi jjodel, `Offering` o i precedenti campi di feedback. In caso di conflitto prevalgono richiesta corrente e specifica ALM. Non attribuire al nuovo piano l'approvazione riportata nel vecchio design.

Approcci considerati:

- Adeguamento unico dell'intero runtime: copertura ampia prima della prima dimostrazione, ma diagnosi e revisione difficili.
- Adeguamento incrementale del runtime esistente: aggiunge prima controlli e contratti, poi ciclo completo e verifiche didattiche. È l'approccio raccomandato e formalizzato qui.

L'inserimento del JSON nei soli prompt non soddisfa autorizzazioni, riferimenti o persistenza, quindi non costituisce un'alternativa conforme.

La prima interfaccia resta una CLI locale per un operatore fidato. L'identità selezionata viene confrontata con configurazione amministrativa e partecipanti del contesto; un parametro `--subject` non è autenticazione remota. Non si aggiungono ora un server web, autenticazione multiutente, un interprete di regole libero, un nuovo database vettoriale o worker concorrenti.

## Rappresentazione e interfacce condivise

Queste sono scelte di serializzazione e implementazione. Non cambiano il JSON normativo.

- `learning/contracts.py`: Pydantic per i valori ALM e per `Entity(type: str, id: str, version: str, provenance: Provenance, fields: dict[str, JsonValue])`. `fields` contiene esattamente i campi specifici dell'entityType; i campi comuni restano nell'envelope. `JsonValue` è un valore JSON finito. Ogni riferimento a entità, anche quando il descriptor indica direttamente `Topic` o `Resource`, è un `EntityRef(type, id, version)`.
- Un validatore limitato al formato ALM verifica tutte le 29 entità e gli 8 valueTypes usando i descriptor del contratto fissato. Non interpreta `meaning`, `requirement`, `condition` o testo libero come codice. Le regole semantiche R01–R21 sono controlli Python espliciti, distribuiti nei task sottostanti.
- `Identifier`, `Version` e `Text` usano stringhe non vuote. Non riutilizzare automaticamente la regex minuscola degli agenti per tutte le entità ALM: `registryName` deve invece rispettare il contratto del registry. `Timestamp` richiede data/ora con fuso; `Boolean` esclude numeri; `Number` esclude booleani e valori non finiti. Queste convenzioni di serializzazione vanno documentate.
- `Contract` contiene descriptor, versione e digest; `Snapshot` contiene contesto, `base_version` autorevole, entità autorizzate indicizzate per riferimento e finding. `RunContext` aggiunge soggetto verificato, proiezione per il Lead, specializzazioni ammesse e risoluzione dei permessi. Non è creato da output LLM.
- `LearningRequest` contiene `request_id`, `context_ref`, `subject_key`, `text` e riferimenti opzionali a topic, attività e occorrenza. Il modo didattico e l'eventuale problema attivo sono risolti dal contesto e dall'interazione; il Lead può proporli, non ampliare permessi.
- `LearningResponse` contiene `kind`, `content`, `citations`, `coverage`, `findings`, `proposal_refs`, `state_change_refs`, `application_status`. I kind sono quelli di `ResponseKind`; `application_status` distingue `none`, `pending`, `approved`, `applied`, `not_applied` come rappresentazione di presentazione, non nuova enumerazione ALM.
- `LearningPlanDraft` contiene `steps: tuple[LearningStepDraft, ...]`; ciascuno contiene `step: PlanStep`, `specialization: EntityRef`, `intent`, `activities`, `required_capabilities`, `expected_output` e `coverage`. I riferimenti al problema Socratic sono assegnati e verificati dal controllo sulla richiesta, non liberamente riscritti dal piano. La proiezione tecnica produce l'attuale `ExecutionPlan`.
- `AuthorizedTask` contiene il `WorkerTask` persistibile, `PlanStep`, profilo risolto, perimetro di ricerca, contesto pertinente, output atteso e vincoli. `WorkerOutput` contiene tipo, contenuto, citazioni, copertura, lacune e candidati di proposta; id, provenienza autorevole, status e permessi sono assegnati dal controllo applicativo.
- `LearningStore` è un context manager SQLite. Salva revisioni immutabili, testa autorevole per contesto, appartenenza dei record, candidati e registrazioni di richiesta. Non espone metodi di scrittura come tool LLM. `StateConflict` indica una base incompatibile; gli errori pubblici non contengono dati personali o credenziali.
- `TrustedPolicy` è configurazione locale amministrativa associata a una versione esatta di `PolicySet`. Definisce soggetti, azioni, scope e adattatori disponibili mediante campi strutturati, senza trasformare automaticamente il testo di `PolicySet` in permessi. Una modifica richiede l'autorità prevista. Non viene caricata da materiali recuperati.

## File e responsabilità

| File | Responsabilità |
| --- | --- |
| `learning/__init__.py`, `contracts.py` | Package senza effetti all'importazione; valori, envelope e DTO applicativi |
| `learning/metamodel.py` | Caricamento ALM fissato, controllo strutturale e proiezioni della specifica |
| `learning/store.py` | SQLite, revisioni, candidati, transazioni e idempotenza |
| `learning/policies.py`, `context.py` | Autorità locale, scope, chiusura autorizzata e snapshot della richiesta |
| `learning/validation.py`, `rules.py` | Invarianti di dominio, prontezza e regole operative esplicite |
| `learning/planning.py` | Piano semantico, compatibilità con registry e autorizzazione dei task |
| `learning/outputs.py` | Briefing per destinatario, controlli per step e della risposta finale |
| `learning/decisions.py` | Proposte, contenuto esaminato, decisioni e applicazione |
| `learning/assessment.py` | Occorrenze, evidenze, valutazioni e stato didattico |
| `learning/service.py`, `learning/__main__.py` | Casi d'uso, CLI e gestione delle risposte senza AI |
| `agents/teacher.md`, `trainer.md`, `curator.md`, `evaluator.md`, `socratic.md` | Profili eseguibili dei cinque ruoli |
| `agent_system/orchestrator.py`, `registry.py`, `runtime.py`, `task_tool.py`, `main.py` | Integrazione con controllo semantico e passaggio di output strutturati |
| `document_search/contracts.py`, `backend.py`, `server.py`, `agent_system/mcp_runtime.py` | Perimetro esplicito di ricerca, applicato prima del limite dei risultati |
| `tests/learning_fixtures.py`, `tests/fixtures/alm/*.json` | Dati sintetici e helper condivisi senza accesso alla rete |
| `tests/test_learning_*.py`, test esistenti, `smoke.py`, `README.md` | Prove dei requisiti, regressioni, dimostrazione e istruzioni |

`agent_system/plan.py` conserva i tipi tecnici e l'ordinamento esistenti. `agent_system/config.py` conserva `AgentConfig`: categoria e ambito appartengono ad `AgentSpecialization`. Non introdurre un secondo registry o un secondo motore di esecuzione. Il package `learning` usa il runtime, mentre il runtime riceve controlli/DTO senza importare CLI o store; evitare import circolari.

## Incrementi e criterio di completamento

1. **Fondamenta controllate, Task 1–5:** contratto, record, versioni, autorizzazioni, prontezza e profili verificabili senza LLM.
2. **Esecuzione didattica controllata, Task 6–8:** spiegazione Teacher e failure path su contesti approvati nelle fixture. Non è ancora un prodotto completo né una modalità di importazione che approva dati arbitrari.
3. **Ciclo persistente completo, Task 9–11:** bootstrap, proposte, decisioni, tentativi, feedback e riapertura da CLI.
4. **Conformità verificata, Task 12:** tutti i CASE01–CASE22, regressioni e prova LLM separata. Nessun rilascio dichiarato conforme sulla sola dimostrazione Teacher.

Ogni task segue rosso, modifica minima, verde e revisione del diff. Fare un checkpoint di commit mirato solo se consentito; non includere automaticamente file estranei. Non eseguire la suite completa dopo ogni micro-modifica: usare i test del task e la suite ai confini degli incrementi.

Ordine di esecuzione proposto: Task 1–12 in sequenza. Le dipendenze principali sono 1 per tutti i contratti, 2–3 per ogni accesso allo stato, 4–5 per l'autorizzazione del piano, 6–8 per l'esecuzione, 9 per gli aggiornamenti di 10–11. I test delle fondamenta possono usare contesti approvati sintetici; l'attivazione di dati dell'utente passa dal Task 9. Nessun incremento intermedio abilita la CLI finale prima del Task 11.

## Task 1: fissare il contratto e validare la rappresentazione ALM

**Files:** creare `learning/__init__.py`, `learning/contracts.py`, `learning/metamodel.py`, `tests/test_learning_contracts.py`, `tests/learning_fixtures.py`, `tests/fixtures/alm/minimal.json`; aggiornare `README.md`. Includere nel versionamento il piano e il JSON normativo con eccezioni mirate in `.gitignore`, senza rendere pubblica tutta la directory di risorse.

**Interfaces:** `load_contract(path: Path) -> Contract`; `validate_entity(value: dict, contract: Contract) -> Entity`; `lead_contract(contract: Contract, roles: frozenset[str]) -> str`. L'helper `load_bundle(name: str = "minimal") -> tuple[Entity, ...]` legge e valida le fixture, senza attivare oggetti in produzione.

- [x] Rilevare la baseline con `.venv/bin/python -m unittest discover -v`. Registrare eventuali errori preesistenti senza considerarli regressioni del piano; un timeout non è un pass. Controllare `git status --short` prima delle modifiche.
- [x] Scrivere test per digest, versione supportata, campi sconosciuti, cardinalità, enum, riferimento tipizzato e assenza di coercizioni. Verificare almeno queste asserzioni in `ContractTest`:

```python
self.assertEqual(contract.version, "1.0.0")
self.assertEqual(len(contract.entity_types), 29)
self.assertEqual(len(contract.value_types), 8)
with self.assertRaises(ValueError):
    validate_entity(binding_with_valid_1, contract)  # valid deve essere Boolean
self.assertEqual(spec_path.read_bytes(), original_bytes)
```

- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_contracts -v`; il rosso deve riguardare i nuovi contratti.
- [x] Implementare solo il formato dichiarativo ALM. Fissare SHA-256 `27b1622c8e4752014d65c67817a79369731e2e7e1261aca0fe04d085e2549636` nel loader per questo artefatto; digest/versione diversa produce errore di configurazione, non adattamento silenzioso. JSON Schema o jjodel non sono input supportati. Per collezioni assenti `0..*` usare lista vuota; campo opzionale assente resta assente. Rifiutare `null` dove non espressamente rappresentato dal formato applicativo.
- [x] Costruire `lead_contract` dalle sezioni `readingGuide.leadCore`, con le regole pertinenti e i vincoli globali sempre presenti. I worker ricevono il contratto del proprio ruolo e task. La selezione delle sezioni è codice deterministico; niente riassunto generato dal Lead che possa eliminare divieti.
- [x] Rieseguire i test; verificare che specifica e piano siano visibili a Git dopo l'eccezione mirata. Checkpoint `feat: validate immutable ALM contract`.

## Task 2: conservare versioni, candidati e stato atomico

**Files:** creare `learning/store.py`, `tests/test_learning_store.py`; estendere `contracts.py` e fixture.

**Interfaces:** `LearningStore(path: Path)`; `read(ref: EntityRef, *, owner: str | None, proposal: EntityRef | None = None) -> Entity`; `read_context(context_id: str) -> Entity`; `append_candidates(proposal: EntityRef, entities: tuple[Entity, ...]) -> None`; `record_event(request_id: str, event: Entity) -> Entity`; `commit_change(change: Entity, entities: tuple[Entity, ...], *, expected_version: str, operation_id: str) -> Entity`. Le ultime operazioni sono primitive interne, invocate solo dopo autorizzazione nei Task 9–11.

- [x] Scrivere `test_reopen_preserves_exact_versions`, `test_candidate_cannot_resolve_as_active`, `test_two_writers_one_base`, `test_retry_does_not_apply_twice`, `test_failure_rolls_back_all_rows`. Asserire che la seconda scrittura su una base superata solleva `StateConflict`, che una ripetizione identica restituisce l'esito registrato e che lo stesso `operation_id` con contenuto diverso viene respinto.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_store -v` e verificare il rosso.
- [x] Usare tabelle per revisioni di entità, head del contesto, appartenenza a contesto/proposta e richieste/eventi. Un id identifica un tipo stabile; versioni multiple sono ammesse, la stessa identità/versione con payload differente no. Namespace candidato e attivo restano distinti; le definizioni condivise sono referenziate, non copiate fra sessioni.
- [x] Applicare confronto della base e scritture correlate nella stessa transazione SQLite; includere `StateChange` e aggiornamento della head. Gli eventi di audit e i cambi amministrativi di proposta non avanzano la revisione autorevole. Non mantenere transazioni aperte durante chiamate LLM o MCP. Una ripetizione di richiesta in corso non avvia una seconda esecuzione; se l'esito della consegna è ignoto, dichiararlo senza inventare successo.
- [x] Rieseguire i test, inclusa riapertura del DB e lettura di evidenze riferite a versioni storiche. Checkpoint `feat: persist versioned learning state`.

## Task 3: autorità fidata e caricamento del contesto

**Files:** creare `learning/policies.py`, `learning/context.py`, `tests/test_learning_context.py`, `tests/fixtures/alm/trusted-policy.json`; estendere `contracts.py` e `store.py` solo per letture necessarie.

**Interfaces:** `load_trusted_policy(path: Path, policy_ref: EntityRef) -> TrustedPolicy`; `authorize(policy: TrustedPolicy, subject_key: str, action: str, context_ref: EntityRef) -> None`; `load_context(store: LearningStore, request: LearningRequest, policy: TrustedPolicy, contract: Contract) -> Snapshot`.

- [x] Scrivere `test_missing_identity_stops_before_ai`, `test_role_without_grant_is_denied`, `test_historical_reference_uses_exact_version`, `test_cross_context_evidence_is_denied`, `test_unrelated_missing_model_does_not_block_request`. Asserire zero chiamate LLM/MCP quando manca identità o autorità; nessuna evidenza dell'altro apprendente nello snapshot.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_context -v` e verificare il rosso.
- [x] Fissare in configurazione amministrativa azioni `read`, `interact`, `submit`, `propose`, `decide`, `apply`, `bootstrap` e relativi scope. Un ruolo umano non concede da solo tutte queste azioni. Il caricamento segue la chiusura dei riferimenti necessari, con visited set per i cicli associativi; separare consultabilità dei metadati, contenuti riservati e materiale mostrabile. Le definizioni di dominio possono essere condivise; i record di sessione sono isolati per proprietario.
- [x] Validare contesto e politica prima di selezionare i contenuti. `DRAFT/PREPARATION` può avere `models=[]`; `ACTIVE/LEARNING` no. Se manca il modello iniziale, restituire i finding per il bootstrap, senza inventare storia. Un riferimento obbligatorio irrisolto blocca la porzione che ne dipende; un contesto di base non autorizzato blocca la richiesta intera.
- [x] Rieseguire i test e verificare che nessun dato riservato finisca nei log di errore. Checkpoint `feat: load authorized learning snapshots`.

## Task 4: invarianti, prerequisiti e prontezza

**Files:** creare `learning/validation.py`, `learning/rules.py`, `tests/test_learning_validation.py`; estendere fixture per percorsi, rubriche e prerequisiti.

**Interfaces:** `validate_snapshot(snapshot: Snapshot) -> tuple[Finding, ...]`; `check_readiness(snapshot: Snapshot, target: EntityRef, action: str) -> tuple[Finding, ...]`; `evaluate_rule(rule_ref: EntityRef, snapshot: Snapshot, inputs: dict[str, JsonValue], bindings: RuleBindings) -> Literal["SATISFIED", "NOT_SATISFIED", "UNKNOWN"]`. `RuleBindings` associa versioni esatte a funzioni Python note, definite in configurazione fidata.

- [x] Scrivere test CASE04, CASE13, CASE16 e CASE21: `UNKNOWN` blocca un prerequisito `MANDATORY`; una raccomandazione produce finding senza blocco; riferimenti associativi ciclici sono ammessi; gerarchie cicliche no. Aggiungere `test_unbound_text_rule_is_unknown` e `test_completed_worker_does_not_complete_activity`.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_validation -v` e verificare il rosso.
- [x] Applicare R02–R07: definitions soltanto `domain_configuration`; root PHASE; PHASE senza attività dirette e UNIT senza figli; un solo genitore nel percorso; ordine e regole di completamento espliciti; copertura degli outcome; cicli di obblighi che impediscono l'avvio respinti. Le bozze strutturalmente valide possono essere non pronte. `CO_REQUISITE` richiede una regola congiunta esplicita.
- [x] Applicare R10 a criteri, livelli, chiavi e riferimenti; non inventare pesi, soglie o aggregazioni. Non usare `eval`, import dinamici da dati o LLM per trasformare testo in predicati autorevoli. Implementare soltanto gli adattatori necessari alle fixture e documentarne input e versioni; una regola non supportata resta `UNKNOWN` e impedisce solo l'azione che richiede un esito determinato.
- [x] Rieseguire i test e quelli dei Task 1–3. Checkpoint `feat: enforce learning readiness and invariants`.

## Task 5: specializzazioni e profili minimi

**Files:** creare i cinque file `agents/{teacher,trainer,curator,evaluator,socratic}.md`; modificare `agent_system/registry.py`; creare `learning/planning.py`, `tests/test_learning_profiles.py`; aggiornare fixture e `tests/test_system.py`.

**Interfaces:** `eligible_specializations(snapshot: Snapshot, registry: AgentRegistry, policy: TrustedPolicy) -> tuple[Entity, ...]`; riepiloghi del Lead con `registryName`, categoria, ruolo, topic e limiti autorizzati, senza prompt interni o segreti.

- [x] Scrivere CASE06, CASE14 e CASE20. Asserire: Teacher e Trainer hanno categoria `TEACHER_TRAINER`; manca una quinta categoria; un nome assente dal registry viene respinto; `TEACHER` non concede il ruolo umano `CONTENT_RESPONSIBLE`; un tool eccedente impedisce la delega.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_profiles -v` e verificare il rosso.
- [x] Mantenere metadati eseguibili in `AgentConfig` e ambito pedagogico in `AgentSpecialization`, collegati da `registryName`. I cinque profili usano il provider già configurato. Nessun tool diretto di scrittura; `search_documents` resta sola capacità di retrieval mediato, nei profili cui serve. Le skills non concedono permessi.
- [x] I vecchi agenti `u–z` non sono automaticamente specializzazioni ALM e non compaiono nel catalogo didattico. Mantenerli durante la transizione per i test tecnici; la CLI finale usa solo profili conformi. Non rinominare un reviewer generico in Evaluator senza modificarne responsabilità e controlli. Nessun filtraggio dinamico dei tool necessario al primo incremento: usare profili già minimi e rifiutare quelli eccedenti.
- [x] Rieseguire i test dei profili e del registry; controllare creazione di un worker nuovo per step. Checkpoint `feat: register ALM worker specializations`.

## Task 6: retrieval vincolato a risorse e versioni

**Files:** creare `document_search/contracts.py`; modificare `document_search/backend.py`, `server.py`, `agent_system/mcp_runtime.py`; aggiornare `tests/test_document_search.py`, `test_mcp_client.py`, `test_mcp_stdio.py`; creare `tests/test_learning_retrieval.py`.

**Interfaces:** `SearchScope(mode, resource_keys: tuple[str, ...], source_scope_keys: tuple[str, ...])`; `DocumentSearchClient.search(query: str, k: int, *, scope: SearchScope) -> dict`; stessa estensione obbligatoria a `SearchBackend.search_documents` e al tool MCP. La serializzazione `resource_key` identifica una coppia esatta risorsa/versione senza concatenazioni ambigue.

- [x] Scrivere `test_filter_precedes_k`, `test_empty_scope_never_searches_globally`, `test_version_pairs_are_not_cross_combined`, `test_missing_mapping_is_rejected`, `test_learning_cannot_discover_external_candidates`. Verificare che, con `k=1`, una fonte ammessa poco pertinente sia selezionabile anche se fonti escluse hanno score maggiore.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_retrieval tests.test_document_search tests.test_mcp_client tests.test_mcp_stdio -v`; verificare il rosso sul nuovo perimetro.
- [x] In LEARNING costruire lo scope dall'intersezione di binding validi approvati, destinatario, attività, politica e necessità del task. In PREPARATION usare soltanto source scope amministrativi autorizzati. Non prendere allowlist dal Lead. Un contesto didattico non apre automaticamente un contesto di preparazione né vi copia dati del discente.
- [x] Applicare il filtro sia nel mock sia nella query Qdrant prima di `limit=k`. Aggiornare la whitelist degli argomenti MCP e tutti i client. Lo scope vuoto restituisce assenza di evidenze, mai ricerca globale. Aggiungere ai metadati un'associazione verificabile fra chunk, risorsa/versione e source scope; verificare di nuovo i risultati nel controllo applicativo. Il payload indicizzato deve corrispondere a una versione immutabile del contenuto; un locator esterno modificato non conserva automaticamente l'approvazione.
- [x] Preservare identificatori e mapping nei limiti di risposta: l'attuale riduzione dei metadata alla sola `source` non basta. Chunk privi di provenienza o mapping non diventano fonti approvate. Lo score misura pertinenza. L'endpoint resta MCP stdio locale; non presentare uno scope dichiarato dal chiamante come autenticazione di un futuro servizio remoto.
- [x] Rieseguire i test con il vero sottoprocesso MCP mock. Documentare la migrazione dei metadati della collezione esterna senza popolarla automaticamente; finché mancano, i documenti non sono utilizzabili in LEARNING. Checkpoint `feat: enforce scoped versioned retrieval`.

## Task 7: pianificazione semantica sopra il piano tecnico

**Files:** estendere `learning/planning.py`, `contracts.py`; modificare `agent_system/orchestrator.py`, `main.py`; creare `tests/test_learning_planning.py`; aggiornare i test di orchestrazione coinvolti.

**Interfaces:** `authorize_plan(draft: LearningPlanDraft, context: RunContext, registry: AgentRegistry) -> tuple[AuthorizedTask, ...]`; `Orchestrator.run(request: LearningRequest, *, context: RunContext) -> LearningResponse`. `answer(question: str, *, context: RunContext) -> str` diventa il wrapper testuale: il parametro obbligatorio evita una via didattica priva di contesto. Aggiornare chiamanti, test e smoke nei task successivi prima dell'integrazione finale.

- [x] Scrivere CASE02 e CASE08; aggiungere `test_empty_plan_cannot_bypass_teacher`, `test_prompt_cannot_expand_capabilities`, `test_draft_refs_cannot_authorize_execution`. Un ciclo, agente sconosciuto o retrieval illecito producono zero chiamate a search e TaskTool.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_planning -v` e verificare il rosso.
- [x] Fare produrre al Lead `LearningPlanDraft`, risolvere riferimenti con lo snapshot, verificare ruolo/intento/output/topic e capacità, poi proiettare in `ExecutionPlan` e chiamare `validate_and_order_plan`. Non estrarre autorizzazioni dal testo `task`. Materializzare `TaskPlan` e `WorkerTask` con identità e provenienza applicative. Il piano completo deve essere valido prima della prima esecuzione.
- [x] Distinguere richieste didattiche miste in task distinti; mantenere confini del problema Socratic assegnati dal controllo. Un piano vuoto è ammesso per chiarimento, limiti, stato o sintesi di risultati esistenti, non per una nuova lezione del Lead. Le lacune locali preliminari delimitano la parte pianificabile, senza autorizzare task non pronti.
- [x] Integrare nel loop esistente chiamate ai controlli semantici mediante funzioni tipizzate; non creare un secondo loop di orchestrazione. Il Lead continua a non avere tool. La risoluzione delle credenziali LLM avviene solo dopo i controlli che possono terminare senza AI.
- [x] Rieseguire i test del piano tecnico e semantico; mantenere ordine stabile, esecuzione sequenziale e propagazione degli skip. Checkpoint `feat: authorize semantic learning plans`.

## Task 8: output controllati prima delle dipendenze e della consegna

**Files:** creare `learning/outputs.py`, `tests/test_learning_outputs.py`; modificare `agent_system/orchestrator.py`, `runtime.py`, `task_tool.py`; aggiornare test e doppi del worker.

**Interfaces:** `build_brief(task: AuthorizedTask, previous: dict[str, Entity], evidence: dict) -> str`; `check_worker_output(task: AuthorizedTask, output: WorkerOutput, context: RunContext) -> Entity` restituisce un `TaskResult`; `check_final_response(response: LearningResponse, context: RunContext, results: tuple[Entity, ...]) -> LearningResponse`. Il worker diventa `CrewAIWorker.run(config: AgentConfig, task: str) -> WorkerOutput`; `TaskTool._run(agent_name: str, task: str) -> WorkerOutput` inoltra quel valore senza convertirlo in stringa. Il callable configurato in TaskTool usa la stessa firma del worker. Nessun diritto deriva dal formato strutturato.

- [x] Scrivere CASE03, CASE09, CASE17 e CASE22. Test essenziale: un output respinto produce `FAILED`, il suo dipendente `SKIPPED` e un indipendente resta eseguibile. Asserire che il testo respinto non compaia né nel briefing dipendente né nella sintesi. Aggiungere `test_required_contract_is_never_truncated` e `test_synthesis_cannot_add_uncited_claim_or_solution`.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_outputs -v` e verificare il rosso.
- [x] Usare output strutturati per worker e sintesi, validati con Pydantic. Controllare tipo atteso, riferimenti, fonti realmente recuperate e ammesse, copertura, lacune e proposte. Il worker non può assegnarsi `SUCCEEDED` o dichiarare una scrittura. Soltanto il controllo materializza `TaskResult` e la provenienza.
- [x] Separare controlli deterministici e revisione semantica. Per pertinenza, sostegno effettivo delle citazioni e soluzione Socratic usare una revisione strutturata tramite il modello già configurato, senza tool e senza aggiungere una categoria di worker. Il verdetto è un segnale del controllo, non fonte di autorizzazioni: errore, dubbio esplicito o rifiuto escludono il contenuto. Testare il gate con revisione simulata e successivamente con casi avversi reali. Non dichiarare che un revisore LLM fornisca una garanzia matematica sul linguaggio naturale.
- [x] Prima di ogni trasferimento selezionare solo dati ammissibili per il destinatario. Soluzioni e answer key restano fuori dal briefing Socratic e dalla vista del discente; le citazioni mostrate non possono aggirare questo vincolo. Sullo stesso problema il cambio a Teacher richiede una scelta esplicita compatibile con la politica e un nuovo task. Il turno termina quando occorre una risposta reale del discente.
- [x] Controllare nuovamente la risposta finale dopo la sintesi. Se non è ammissibile, restituire un messaggio applicativo di limite/fallimento senza il contenuto respinto; niente retry aperti. I contratti obbligatori, i vincoli e l'identità delle fonti non vengono troncati: ridurre contenuto opzionale oppure dichiarare contesto insufficiente. Una copertura incompleta produce `PARTIAL_RESULT`; nessun successo produce `FAILURE`.
- [x] Rieseguire test di output, orchestrazione e sistema. Checkpoint `feat: gate worker outputs and final responses`.

## Task 9: proposte, decisioni e applicazione dello stato

**Files:** creare `learning/decisions.py`, `tests/test_learning_decisions.py`; estendere `store.py`, `contracts.py` e fixture.

**Interfaces:** `review_payload_key(target: Entity, candidates: tuple[Entity, ...]) -> str`; `create_proposal(context: RunContext, target_refs: tuple[EntityRef, ...], candidates: tuple[Entity, ...], explanation: str) -> Entity`; `record_decision(store: LearningStore, context: RunContext, target: EntityRef, decision: Literal["APPROVE", "REJECT", "REQUEST_REVISION"], reason: str) -> Entity`; `apply_proposal(store: LearningStore, context: RunContext, proposal: EntityRef, *, operation_id: str) -> Entity` restituisce `StateChange` oppure segnala mancata applicazione.

- [x] Scrivere CASE05, CASE10 e CASE18, più `test_added_candidate_is_not_covered`, `test_decision_cannot_grant_own_authority`, `test_revoked_permission_blocks_apply`, `test_reject_and_revision_do_not_apply`. Asserire che `APPROVED` e `APPLIED` siano distinguibili e che una base incompatibile produca `STALE` senza mutazioni autorevoli.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_decisions -v` e verificare il rosso.
- [x] Validare prima l'intero insieme candidato e i suoi riferimenti interni; i candidati non entrano nel catalogo attivo. Derivare la modifica da target e definizioni candidate strutturate. `proposedChange` è descrizione: non eseguire testo, SQL o patch generati dall'AI.
- [x] Calcolare in applicazione l'identità del contenuto mediante JSON canonico e SHA-256. Definire esplicitamente la proiezione per ChangeProposal, ResourceBinding ed Evaluation: includere contenuto, effetti, scope, evidenze, versioni di base e chiusura dei candidati esaminati; escludere soltanto il digest stesso e metadati amministrativi controllati, come status e collegamenti alla decisione. Cambiare `valid`, scope, effetti o evidenze è sostanziale. Una nuova versione amministrativa con payload identico conserva la decisione originale e la sua versione esaminata.
- [x] Il controllo calcola `coveredPayloadKeys` dalla vista effettivamente presentata al decisore; nessun campo fornito dall'agente può ampliare l'insieme. `REQUEST_REVISION` richiede una nuova revisione da esaminare, senza inventare uno stato `ProposalStatus` ulteriore. Controllare nuovamente autorità e revoche, chiavi e base al momento dell'applicazione.
- [x] Applicare in una transazione le revisioni e `StateChange`; conservare la storia di binding e valutazioni. Un evento di audit o una modifica amministrativa della proposta non invalida da solo la base autorevole. Una modifica sostanziale sì. Una decisione di binding o valutazione può essere diretta oppure coperta esplicitamente dalla proposta.
- [x] Rieseguire test di decisioni e store, compresi retry e crash simulato. Checkpoint `feat: apply reviewed learning proposals atomically`.

## Task 10: evidenze reali, valutazioni e avanzamento

**Files:** creare `learning/assessment.py`, `tests/test_learning_assessment.py`; estendere `rules.py`, `validation.py`, `store.py` e fixture.

**Interfaces:** `record_attempt(store: LearningStore, context: RunContext, activity: EntityRef, content: str, *, request_id: str) -> Entity` restituisce LearningEvidence e persiste la relativa ActivityOccurrence; `validate_evaluation(evaluation: Entity, snapshot: Snapshot) -> tuple[Finding, ...]`; `derive_learning_state(context: RunContext, evaluation: Entity, bindings: RuleBindings) -> Entity`; `derive_activity_status(occurrence: Entity, snapshot: Snapshot, bindings: RuleBindings) -> str`.

- [x] Scrivere CASE07, CASE11, CASE12, CASE15 e CASE16. Asserire: quiz senza risposta non produce Evaluation; assenza di evidenza non assegna livello minimo; ACQUIRED non implica VERIFIED; una conferma umana senza criteri/evidenze validi non basta; due contesti con lo stesso modello restano indipendenti. Aggiungere `test_attempt_survives_provider_failure` e `test_new_rubric_does_not_reinterpret_history`.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_assessment -v` e verificare il rosso.
- [x] Salvare il tentativo prima di avviare la valutazione AI, quando la politica autorizza la registrazione. Ogni evidenza riferisce soggetto, contesto, attività, tentativo/occorrenza e versioni coincidenti. Non attribuire origine osservata al contenuto generato da un worker. Una nuova risposta crea un tentativo distinguibile, senza sovrascrivere il precedente.
- [x] Applicare criteri e livelli della rubrica fissata, tipo di evidenza ammesso, copertura e regole approvate. Una regola assente o non supportata produce feedback descrittivo o proposta, senza esito determinato inventato. Le regole qualitative possono essere valutate dal responsabile autorizzato con motivazione registrata; non diventano automaticamente predicati eseguibili.
- [x] Distinguere `TaskStatus`, `ActivityStatus`, `ProgressStatus` e `VerificationStatus`. ACQUIRED richiede achievementRule soddisfatta e autorizzazione vigente. VERIFIED richiede inoltre verificationRule, valutazione formale, evidenze ammissibili e decisione umana valida. La chiusura di PHASE/UNIT dipende dalle occorrenze e dalla completionRule; SKIPPED non equivale a completamento salvo regola approvata esplicita.
- [x] Una spiegazione isolata può essere erogata senza un corso artificiale. Per trasformare una prestazione in evidenza valutativa servono prima attività, outcome e riferimenti previsti; se assenti, proporne la definizione. Registrazioni ordinarie autorizzate usano una base di politica, senza decisioni umane fittizie.
- [x] Rieseguire test di valutazione, invarianti e decisioni. Checkpoint `feat: track evidence assessment and learning progress`.

## Task 11: ciclo completo da CLI e bootstrap

**Files:** creare `learning/service.py`, `learning/__main__.py`, `tests/test_learning_service.py`, `tests/test_learning_cli.py`; aggiornare `main.py`, `README.md`, `tests/test_system.py`, `smoke.py`, `tests/test_smoke.py`.

**Interfaces:** `LearningService(store, contract, policy, orchestrator_factory)` espone le firme seguenti; ogni metodo risolve il contesto e richiama i controlli dei Task 9–10, senza duplicarli. La factory dell'Orchestrator è lazy.

- `request(request: LearningRequest) -> LearningResponse`.
- `bootstrap(context_id: str, subject_key: str) -> Entity`.
- `propose(context_id: str, subject_key: str, targets: tuple[EntityRef, ...], candidates: tuple[Entity, ...], explanation: str) -> Entity`.
- `decide(context_id: str, subject_key: str, target: EntityRef, decision: Literal["APPROVE", "REJECT", "REQUEST_REVISION"], reason: str) -> Entity`.
- `apply(context_id: str, subject_key: str, proposal: EntityRef, operation_id: str) -> Entity`.
- `submit(context_id: str, subject_key: str, activity: EntityRef, content: str, request_id: str) -> Entity`.
- `show(context_id: str, subject_key: str) -> dict[str, JsonValue]`.

- [x] Scrivere `test_bootstrap_without_model`, `test_missing_policy_stops_without_delegation`, `test_full_cycle_reopens`, `test_ordinary_feedback_needs_no_extra_decision`, `test_failed_apply_is_not_reported_applied`, `test_cli_error_does_not_expose_private_text`. Coprire CASE01 e CASE19 e il percorso di rifiuto/revisione di una proposta.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_service tests.test_learning_cli -v` e verificare il rosso.
- [x] Implementare il ciclo U/C/V obbligatorio; V può restituire CLARIFICATION/FAILURE senza provider. P/R/A/S avvengono nell'Orchestrator. O restituisce l'esito controllato; H sospende soltanto l'applicazione che richiede decisione; D registra eventi autorizzati e applicazioni effettive. Il turno successivo ricarica lo stato e avvia un nuovo ciclo, senza simulare risposte del discente o replanning illimitato.
- [x] Esporre `python -m learning` con comandi `bootstrap`, `propose`, `decide`, `apply`, `ask`, `submit`, `show` e selezione di DB, policy, soggetto e contesto. Le opzioni comuni hanno un solo parser condiviso. `propose` accetta un bundle candidato locale già validabile; `decide` mostra target/versione, contenuto sostanziale e conseguenze prima di registrare la scelta umana. L'importazione non approva implicitamente il candidato.
- [x] Consentire bootstrap DRAFT/PREPARATION con identità e PolicySet fidati e modello vuoto. Il primo modello può essere proposto manualmente: se manca una specializzazione autorizzata non si inventa un Curator né si crea un accesso ad hoc. Dopo decisione e applicazione si fissano le versioni; il passaggio ACTIVE/LEARNING richiede prontezza. Una nuova risorsa esterna si scopre soltanto nel contesto PREPARATION distinto e viene legata a LEARNING con la decisione prevista.
- [x] Rendere `main.py` l'accesso breve a `ask` con contesto esplicito o configurato: la vecchia domanda senza contesto termina con richiesta di configurazione, non con bypass generico. Migrare tutti i chiamanti `.answer(...)`, i doppi di search/worker e lo smoke alle nuove firme. Non servono un secondo endpoint generico o un flag che disattivi i controlli. Riutilizzare `build_orchestrator` e `LLMFactory`; le operazioni manuali e `--help` funzionano senza chiave LLM.
- [x] Documentare il ciclo riproducibile con fixture sintetiche, la CLI come strumento locale fidato, la distinzione fra feedback formativo e decisione formale e la procedura di revisione dei modelli. Nessuna migrazione distruttiva del DB: versionare lo schema, creare backup prima di future migrazioni, rifiutare versioni sconosciute.
- [x] Rieseguire test di servizio, CLI, sistema e smoke simulato; poi la suite completa. Checkpoint `feat: expose the complete ALM learning cycle`.

## Task 12: matrice di conformità e verifica finale

**Files:** creare `tests/test_learning_acceptance.py`, `tests/fixtures/alm/acceptance.json`; aggiornare `smoke.py`, `tests/test_smoke.py`, `README.md` e la matrice seguente con risultati effettivi.

**Interfaces:** i test usano le API pubbliche di LearningService con SQLite temporaneo e provider simulato; i casi che riguardano MCP attraversano anche il server stdio mock reale. `smoke.py` usa un contesto sintetico approvato tramite il normale ciclo e non inserisce dati reali o credenziali nelle fixture.

- [x] Scrivere un test `test_case01` fino a `test_case22`, ciascuno riferito al testo originale dello scenario. Le assertion devono osservare chiamate, dati effettivamente trasferiti, contenuti consegnati e stato persistito; non limitarsi a verificare un messaggio del Lead.
- [x] Eseguire `.venv/bin/python -m unittest tests.test_learning_acceptance -v` e verificare ogni lacuna prima di correggerla nel componente responsabile. Non aggiungere un ramo speciale per il nome del caso.
- [x] Eseguire `.venv/bin/python -m unittest discover -v`. Verificare anche digest invariato della specifica, import senza effetti collaterali, chiusura di SQLite/MCP e assenza di dati personali nei log.
- [x] Eseguire `.venv/bin/python smoke.py --runs 1` solo nell'ambiente configurato per il provider già previsto. Asserire piano autorizzato, retrieval ammesso, TaskResult controllato, fonte corretta e assenza di aggiornamenti pedagogici ingiustificati. Quota o timeout sono fallimenti osservati, non successi sostituiti con risposte prefissate. Non richiedere tre run salvo rischio concreto.
- [ ] Provare con LLM reale un turno Socratic con soluzione presente fra dati non mostrabili, un tentativo di prompt injection e una citazione pertinente ma non probante. Registrare violazioni e limiti della revisione semantica; non equiparare i test simulati a garanzia pedagogica. La verifica Qdrant reale richiede una collezione con mapping versionati e viene dichiarata separatamente se non disponibile.
- [ ] Chiudere il piano solo quando tutti i test deterministici richiesti passano, il ciclo si riapre dal DB e i limiti dei controlli semantici sono documentati. Se manca una prova live, specificare esattamente quale: non chiamare quella parte verificata. Checkpoint `test: verify ALM acceptance scenarios`.

## Copertura normativa

| Regole | Task responsabili | Evidenza richiesta |
| --- | --- | --- |
| R01 | 1, 3, 9, 11 | Digest, separazione livelli, bootstrap e attivazione |
| R02 | 1, 2, 3, 4 | Identità, cardinalità, versioni esatte e chiusura autorizzata |
| R03 | 1, 5 | Dati disciplinari variabili, ruoli umani separati |
| R04, R05 | 4 | Gerarchie, cicli, prerequisiti e UNKNOWN |
| R06, R07 | 4, 7, 10 | Percorsi, copertura, prontezza e completamento |
| R08 | 3, 6, 9, 11 | Scope, binding, candidati e contesti distinti |
| R09 | 6, 8 | Provenienza, derivazioni e sostegno delle citazioni |
| R10, R11, R12 | 4, 10 | Rubriche, tentativi reali, regole ed esiti determinabili |
| R13 | 9, 10 | Acquisizione distinta da verifica e decisione autorizzata |
| R14, R15 | 3, 5, 6, 7 | Minimo privilegio, trasferimento dati senza autorità |
| R16 | 5, 7, 8 | Ruolo/intento/output e continuità Socratic |
| R17 | 7 | Piano valido prima dell'esecuzione e ordine stabile |
| R18 | 8 | Gate per step, skip, fallimento totale e parzialità |
| R19, R20 | 2, 9, 10 | Payload esaminato, transazione, storia e conflitti |
| R21 | 8, 11 | Risposta controllata, fonti e stato effettivamente applicato |

| Scenari | Task che li costruiscono | Verifica finale |
| --- | --- | --- |
| CASE01 | 6, 8, 11 | `test_case01` |
| CASE02 | 7, 10 | `test_case02` |
| CASE03 | 8 | `test_case03` |
| CASE04 | 4 | `test_case04` |
| CASE05 | 6, 9, 11 | `test_case05` |
| CASE06 | 5, 7 | `test_case06` |
| CASE07 | 4, 10 | `test_case07` |
| CASE08 | 7 | `test_case08` |
| CASE09 | 8 | `test_case09` |
| CASE10 | 2, 9 | `test_case10` |
| CASE11 | 2, 3, 10 | `test_case11` |
| CASE12 | 4, 10 | `test_case12` |
| CASE13 | 4 | `test_case13` |
| CASE14 | 5, 7 | `test_case14` |
| CASE15 | 9, 10 | `test_case15` |
| CASE16 | 4, 10 | `test_case16` |
| CASE17 | 8 | `test_case17` |
| CASE18 | 9 | `test_case18` |
| CASE19 | 3, 9, 11 | `test_case19` |
| CASE20 | 1, 5 | `test_case20` |
| CASE21 | 4 | `test_case21` |
| CASE22 | 6, 8 | `test_case22` |

Tutti i descriptor delle 29 entità sono coperti strutturalmente dal Task 1. La loro semantica è distribuita: configurazione e percorsi nei Task 3–5; ExecutionContext/Participant/ResourceBinding nei Task 2, 3, 6 e 9; TaskPlan/WorkerTask/TaskResult nei Task 7–8; ChangeProposal/HumanDecision/StateChange nel Task 9; ActivityOccurrence/LearningEvidence/Evaluation/LearningState nel Task 10. Le famiglie di Strategy restano dati orientativi, non un nuovo enum o una sequenza obbligatoria.

## Confini della consegna e rischi residui

Il piano copre il flusso completo e tutte le regole; non promette l'esecuzione automatica di qualsiasi regola scritta in linguaggio naturale. Un dato o una regola non determinabili producono un limite esplicito. La revisione semantica può sbagliare: occorrono casi reali e controllo dei contenuti, soprattutto per Socratic e citazioni. Le decisioni umane richieste dalla specifica restano obbligatorie indipendentemente dal verdetto LLM.

I nuovi requisiti rendono intenzionalmente incompatibili domanda senza contesto, MCP privo di scope e uso didattico dei vecchi agenti generici. Il piano aggiorna i chiamanti noti (`main.py`, `smoke.py`, test e factory); eventuali consumatori esterni non censiti richiedono adeguamento prima del rilascio. Le collezioni Qdrant non vengono riscritte da questo intervento.

Il piano di implementazione resta locale e fuori dal branch; questa specifica e il metamodello sono versionati in `docs/resources/`. Non modificare il metamodello per aggirare una funzione mancante: completare il controllo oppure dichiarare l'azione non disponibile.

## Revisione del piano

Revisione interna effettuata rispetto a regole, workflow, outputContract, compatibilityMap e scenari del JSON: sono assegnati tutti i 21 requisiti normativi e i 22 scenari; i controlli precedono il riuso degli output, le decisioni precedono le applicazioni richieste e le firme condivise sono indicate sopra. Questa verifica riguarda la copertura del piano, non l'esecuzione dei test o la conformità del software attuale. L'esecuzione proposta è nativa, con revisione del risultato prima dell'integrazione.
