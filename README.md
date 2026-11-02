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

## Tracciamento Langfuse (facoltativo)

La telemetria è disattivata per impostazione predefinita. Con `LANGFUSE_ENABLED` assente o `false` il modulo non importa Langfuse/OpenInference e non invia dati. Le dipendenze sono incluse in `requirements.txt` per eseguire anche i test di integrazione con esportatore in memoria.

Per avviare solo l'osservabilità, senza Qdrant, TEI o vLLM:

```bash
docker compose -f compose.local.yml --profile observability up -d
```

La configurazione principale include lo stesso profilo: `docker compose --profile observability up -d` avvia anche Qdrant e TEI e richiede la loro configurazione. Lo stack Langfuse comprende web, worker, Postgres, ClickHouse, Redis e MinIO, con volumi dedicati. Solo web (`127.0.0.1:3000`) e MinIO (`127.0.0.1:9090`, per media) espongono porte host; non occupa le porte di TEI/Qdrant. Le immagini Langfuse seguono la versione maggiore 4 della configurazione upstream: fissare digest validati per installazioni persistenti.

### Prima configurazione e prova completa

1. Installare le dipendenze con `.venv/bin/python -m pip install -r requirements.txt` e avviare lo stack con il comando precedente.
2. Aprire <http://127.0.0.1:3000>. Non esistono credenziali predefinite: scegliere **Sign up**, creare account, organizzazione e progetto.
3. Nel progetto aprire **Settings → API Keys** e creare una coppia Public Key (`pk-lf-...`) e Secret Key (`sk-lf-...`). Sono diverse dalla password di accesso.
4. Creare una chiave nelle [impostazioni API di OpenRouter](https://openrouter.ai/settings/keys).
5. Eseguire `openssl rand -hex 32`: copiare il risultato in `LANGFUSE_HASH_SALT`. Questo valore viene generato localmente, non fornito da Langfuse.
6. Creare o aggiornare `.env` nella radice del repository con i valori reali al posto dei segnaposto:


```dotenv
OPENROUTER_API_KEY=la-chiave-openrouter
SEARCH_BACKEND=mock
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=http://127.0.0.1:3000
LANGFUSE_HASH_SALT=il-risultato-di-openssl
LANGFUSE_SYNTHETIC_DATA_ONLY=true
```

Il blocco precedente è per la prova con fixture sintetiche. Tenere `.env` locale: non committare chiavi o password. Per un’installazione persistente, usare valori casuali privati anche per `LF_NEXTAUTH_SECRET`, `LF_SALT`, `LF_ENCRYPTION_KEY` (64 cifre esadecimali), `LF_POSTGRES_PASSWORD`, `LF_CLICKHOUSE_PASSWORD`, `LF_REDIS_PASSWORD` e `LF_MINIO_PASSWORD` (almeno 8 caratteri). I valori predefiniti Compose servono esclusivamente alle prove locali con dati sintetici. Conservare il salt stabile per correlare lo stesso soggetto; cambiarlo cambia gli identificatori pseudonimi.

Ogni `Orchestrator.run` produce una radice `learning.request`, raggruppata per ExecutionContext, con richiesta e risposta. Sotto la radice: generazioni Lead, autorizzazione del piano, step, ricerca MCP lato client, chiamate worker, revisioni semantiche e controlli deterministici. Gli span OpenInference CrewAI e OpenAI si annidano nelle osservazioni correnti. L'instrumentor OpenAI acquisisce prompt, completamenti, modello e token anche per OpenRouter nativo in streaming; le chiamate di conversione strutturata e i tentativi aggiuntivi restano visibili come chiamate distinte. La durata degli span misura la latenza. I costi monetari dipendono dal catalogo prezzi/configurazione del modello in Langfuse, non vengono stimati dal prototipo.

Gli esiti semantici sono score categorici `ACCEPT` / `REJECT` / `UNCERTAIN`; i controlli e gli step registrano anche `SUCCEEDED` / `FAILED` / `SKIPPED`. La traccia include ID richiesta, versione e fingerprint del metamodello, profili per agente, ruoli, modalità e commit Git. I programmi `python -m learning`, `main.py` e `smoke.py` svuotano la coda prima di uscire, anche in caso di errore.

7. Verificare la configurazione, eseguire i test e la prova con il modello gratuito. Lo smoke usa documenti sintetici tramite MCP e non richiede Qdrant o TEI:


```bash
docker compose -f compose.local.yml --profile observability config --quiet
.venv/bin/python -m unittest tests.test_telemetry -v
LANGFUSE_ENABLED=false .venv/bin/python -m unittest discover -q
.venv/bin/python smoke.py --runs 1
```

8. Attendere `PASS 1/1`: la prova reale può richiedere alcuni minuti. Tornare nel progetto Langfuse, aprire **Tracing** e aggiornare l’elenco. Aprire l’ultima `learning.request`: deve contenere `lead.call`, `authorize_plan`, uno step con `document_search` e `worker.call`, le revisioni `semantic_review`, la sintesi e `check_final_response`. Le chiamate OpenAI/OpenRouter mostrano modello, token e durata; gli esiti sono visibili come score.

### Diagnosi di una prova fallita

- Se la traccia non compare, verificare `LANGFUSE_ENABLED=true`, endpoint locale e coppia di chiavi dello stesso progetto. Il processo invia le osservazioni prima di terminare.
- `Plan rejected (ValueError)` significa che i controlli hanno bloccato il piano prima di eseguire i task: aprire `authorize_plan` nella traccia e leggere `status_message` e il piano in input. `step.agent` è il nome del worker (`lesson-explainer`); `specialization` è il riferimento esatto con `type: AgentSpecialization`, `id: teacher-demo`, `version: 1` nella fixture smoke. Non sono intercambiabili.
- Se un worker viene rifiutato, leggere il verdetto e il motivo in `semantic_review` (stage `WORKER`) e i codici in `check_worker_output`. Un rifiuto semantico produce un esito di fallimento anche se il modello ha restituito del testo.
- Il link a `app.crewai.com` appartiene al collector nativo CrewAI, separato da Langfuse. Il prototipo lo disattiva; usare la propria istanza locale per consultare le tracce.
- Il test usa un modello gratuito e non passa a un modello a pagamento in caso di errori o indisponibilità. Una prova riuscita verifica l’integrazione su fixture sintetiche, non garantisce l’esito di ogni futura generazione.

### Dati e conservazione


Non usare Langfuse Cloud con dati reali. Per vedere anche i contenuti delle fixture LEARNING nello smoke, impostare `LANGFUSE_SYNTHETIC_DATA_ONLY=true`: questa dichiarazione disabilita l’oscuramento dei contenuti LEARNING, conservando la pseudonimizzazione. Gli endpoint `*.langfuse.com` richiedono l'esplicito `LANGFUSE_SYNTHETIC_DATA_ONLY=true`, da impostare solo per fixture sintetiche. Per dati reali usare l'istanza del progetto. `subject_key` diventa un HMAC SHA-256 con salt privato; il mascheramento copre anche identità incorporate nei prompt. In modalità LEARNING viene oscurato conservativamente tutto il contenuto di input/output, inclusi i messaggi catturati automaticamente, per evitare che consegne ed evidenze del discente ricompaiano attraverso prompt o sintesi. Restano disponibili struttura, esiti, codici dei controlli e metriche dei token. PREPARATION conserva i contenuti per il debug: non inserirvi dati personali non necessari.

La finestra prevista di conservazione è 30 giorni. La cancellazione automatica nativa richiede Langfuse Self Hosted Enterprise: configurare la licenza e `Project Settings → Data Retention = 30`. Per il provisioning headless sono disponibili `LANGFUSE_INIT_ORG_ID/NAME`, `LANGFUSE_INIT_PROJECT_ID/NAME`, `LANGFUSE_INIT_USER_EMAIL/PASSWORD` e le chiavi del progetto: `LANGFUSE_INIT_PROJECT_RETENTION` riceve `LANGFUSE_RETENTION_DAYS` (default 30). Non modifica progetti già esistenti. Senza licenza, la retention nativa non si attiva: prevedere una procedura amministrativa di cancellazione e verificarla prima di raccogliere dati reali. `down` conserva i dati; la cancellazione dei volumi è irreversibile e va pianificata separatamente.

Riferimenti: [integrazione CrewAI](https://langfuse.com/integrations/frameworks/crewai), [mascheramento degli span](https://langfuse.com/docs/observability/features/masking), [installazione Compose](https://langfuse.com/self-hosting/deployment/docker-compose), [retention e requisiti di licenza](https://langfuse.com/docs/administration/data-retention).

Il prototipo disattiva il collector cloud nativo di CrewAI e conserva il consenso negativo nella propria `.cache/crewai`, senza cambiare le preferenze globali dell’utente. Le tracce applicative restano dirette al solo endpoint Langfuse configurato. Nel piano, `step.agent` deve essere il `registryName` del worker (es. `lesson-explainer`); `specialization` è invece il riferimento esatto `AgentSpecialization` (es. `teacher-demo`). Il prompt presenta esplicitamente le coppie autorizzate; il controllo continua a rifiutare riferimenti errati.
