# Prototipo ALM con agenti CrewAI

Applicazione locale per gestire un contesto di apprendimento ALM con stato e tracciamento in SQLite. Un agente Lead pianifica i compiti, agenti specializzati producono risposte e il codice verifica autorizzazioni, fonti e risultati. La generazione predefinita usa OpenRouter; la ricerca usa `mock` per prove sintetiche oppure Qdrant e TEI per documenti reali.

- [Metamodello ALM 1.0.0](docs/resources/metamodello-agnostico-apprendimento.json)
- [Specifica del dominio](docs/resources/2026-10-27-specifica.md)

## Installazione

Servono Python 3 e, solo per la ricerca reale, Docker Compose 2.20.3 o successivo.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Configurazione

Crea `.env` nella radice del progetto. Per la prova con documenti sintetici imposta `OPENROUTER_API_KEY` e `SEARCH_BACKEND=mock`. Questa modalità non richiede Docker. La chiave non va inserita nel repository.

Il Lead e gli agenti specializzati selezionano il profilo nei rispettivi file `control/lead.md` e `agents/*.md`. `model.properties` definisce fornitore, modello e nome della variabile credenziale; `runtime.properties` definisce il Lead, i parametri di generazione e i limiti. Il modello OpenRouter incluso termina in `:free` e non passa automaticamente a un modello a pagamento. Per usarne uno serve `allow_paid = true` nel suo profilo.

Per cercare documenti reali imposta `SEARCH_BACKEND=qdrant` e configura le variabili seguenti in `.env`:

| Variabile | Uso |
| --- | --- |
| `EMBEDDING_MODEL_ID` | Modello caricato da TEI, per esempio `google/embeddinggemma-300m` |
| `QDRANT_URL`, `QDRANT_COLLECTION` | Endpoint e collezione Qdrant |
| `EMBEDDING_URL`, `EMBEDDING_MODEL` | Endpoint e nome del modello per le richieste embedding |
| `EMBEDDING_DIMENSIONS`, `EMBEDDING_API_KEY` | Dimensione del vettore e credenziale inviata all'endpoint embedding |
| `QDRANT_API_KEY` | Facoltativa, solo se Qdrant la richiede |

Dopo aver accettato la licenza del modello di embedding, popola una volta la cache condivisa prima dell'avvio offline di TEI


`HF_TOKEN` serve solo al caricamento iniziale e non viene passato ai servizi in esecuzione. Avvia i servizi con `docker compose up -d`; TEI ascolta su `127.0.0.1:9000` e Qdrant su `127.0.0.1:6333` (HTTP) e `6334` (gRPC).

Questo progetto **non crea né popola** la collezione Qdrant. Il caricamento dei documenti è esterno: con EmbeddingGemma servono vettori di 768 dimensioni e dati con `text`, `metadata.source` e `metadata.source_scope` per PREPARATION oppure `metadata.resource_key` per LEARNING. In PREPARATION la ricerca richiede un ambito di fonti autorizzato; in LEARNING richiede risorse collegate e approvate, con versioni esatte.

## Flusso locale ALM

I comandi operativi di `python -m learning` richiedono `--db`, `--policy`, `--subject` e `--context` prima del sottocomando. Usa `--help` per vedere `bootstrap`, `propose`, `decide`, `apply`, `abandon`, `ask`, `submit` e `show`.

La CLI è destinata a un operatore locale fidato: `--subject` seleziona un soggetto, **non autentica** una persona da remoto. Proteggi il file policy e il database a livello host. Una risposta generata non approva proposte e non assegna automaticamente progressi al discente.


`bootstrap` rifiuta un contesto già presente: usa un nuovo database per ripetere l'esempio. Se `ask` viene interrotto dopo aver riservato `demo-ask-1`, un amministratore autorizzato può eseguire `alm abandon demo-ask-1`; il tentativo successivo richiede un ID nuovo. `submit` registra una risposta osservata, ma una valutazione deve essere proposta, approvata e applicata separatamente.

## Dati e verifica

Il percorso SQLite è sempre quello passato in `--db`; non esiste un database predefinito. L'apertura di un DB schema v1 crea una copia privata `.v1.bak` (o `.v1.N.bak` se esiste già) e lo migra a v2: ferma gli altri processi che scrivono prima dell'apertura. La versione precedente dell'applicazione non legge v2; ripristinare il backup v1 dopo nuove scritture elimina quelle scritture.

I vecchi nomi delle specializzazioni non sono migrati automaticamente: `teacher` → `lesson-explainer`, `trainer` → `guided-practice-coach`, `socratic` → `reasoning-questioner`. Per `curator` scegli `lesson-support-summarizer` in LEARNING o `resource-candidate-researcher` in PREPARATION; per `evaluator` scegli `learner-response-evaluator` in LEARNING o `assessment-designer` in PREPARATION. Aggiorna le specializzazioni con proposta, revisione e applicazione autorizzate, conservando le versioni storiche.

`docker compose down` conserva i volumi. **`docker compose down -v` elimina anche i dati Qdrant e le cache dei modelli**: non usarlo senza aver salvato i dati necessari.

```bash
.venv/bin/python -m unittest discover -q
.venv/bin/python smoke.py --runs 1
```

I test automatici usano dati sintetici. La prova `smoke.py` chiama davvero il modello OpenRouter gratuito e usa il protocollo MCP, ma seleziona la ricerca `mock`: non verifica la collezione Qdrant, TEI o vLLM locale.
