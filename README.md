# py-prototype

Workflow CrewAI con backend selezionato staticamente in `model.properties`: vLLM locale o commerciale (es. OpenAI, Anthropic...). L'esecuzione avviene sempre su host tramite `.venv`

## Configurazione

`model.properties` è versionato e contiene solo configurazione non sensibile:

- `backend`: `vllm`, `openai` o `anthropic`;
- modello e `base_url` per ogni backend;
- `temperature`, `top_p`, `max_tokens` e `timeout`.

La scelta statica avviene prima dell'avvio:

Valori attualmente ammessi: `vllm`, `openai`, `anthropic`.

```properties
[llm]
backend = vllm
```

`.env` non è versionato e contiene solo secret:

```dotenv
VLLM_API_KEY=local-development
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
HF_TOKEN=
```

Applicazione legge solo chiave corrispondente al backend configurato. Configurazione mancante termina con errore; nessun fallback implicito.

## Ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "crewai[anthropic]==1.15.18" python-dotenv jupyterlab ipykernel
```

## vLLM locale

Impostare `backend = vllm` e valorizzare `VLLM_API_KEY`. Avviare solo server vLLM:

```bash
docker compose up -d
docker compose ps
```

Poi eseguire workflow sull'host:

```bash
python main.py
```

`base_url = http://127.0.0.1:8000/v1` usa porta pubblicata dal container verso host.

## Provider cloud

Impostare `backend = openai` oppure `backend = anthropic`, valorizzare chiave corrispondente e avviare solo Python:

```bash
python main.py
```

## Verifica

```bash
python -m unittest -v test_main.py
```

Arresto vLLM:

```bash
docker compose down
```

Aggiungere `-v` solo per eliminare anche cache modelli.
