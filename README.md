# CrewAI multi-agent orchestrator

Lead Agent carica worker configurati in `agents/*.md`, delega task tramite `TaskTool` e sintetizza una risposta finale. Configurazione LLM usa profili nominati in `model.properties`; secret restano in `.env`.

## Installazione

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Configurazione

Impostare `app.lead_model` e profili `[profile:<nome>]` in `model.properties`. Ogni `model:` nei file `agents/*.md` riferisce uno di questi profili.

```dotenv
VLLM_API_KEY=local-development
```

Tool worker sono nomi registrati dalla composition root. Skill worker sono directory locali `skills/<nome>/SKILL.md`. Nomi sconosciuti bloccano avvio; import dinamici non sono ammessi.

## Esecuzione locale

```bash
docker compose up -d
.venv/bin/python main.py "Progetta un servizio affidabile di elaborazione documenti"
```

## Test

```bash
.venv/bin/python -m unittest -v
```

## Arresto vLLM

```bash
docker compose down
```

Usare `docker compose down -v` solo quando si vuole eliminare anche la cache modelli.
