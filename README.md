# py-prototype

Questo progetto resta indipendente dal Python globale e tiene Jupyter isolato nel virtualenv.

L'obiettivo è testare un flusso locale con Ollama in Docker e notebook Jupyter, usando modelli leggeri come `phi` o `gemma`.

## Struttura
- Tutte le dipendenze in `.venv`
- Kernel Jupyter registrato dentro `.venv`
- Runtime Jupyter dentro `.venv/var/jupyter/runtime`

## Setup rapido di ambiente
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install jupyterlab ipykernel
```
## Registra il kernel nel virtualenv
```bash
python -m ipykernel install --prefix "$PWD/.venv" --name py-prototype-local --display-name "Python (.venv py-prototype)"
```

## Runtime Jupyter nel progetto
Crea la cartella runtime locale.

```bash
mkdir -p .venv/var/jupyter/runtime
```

## Per usare il progetto
installa anche le librerie necessarie (esempio):
```bash
python -m pip install crewai langchain langchain-community
```

## Docker (CPU only)
Il compose avvia due istanze di Ollama separate:

Ogni servizio mantiene il proprio volume, quindi il modello scaricato resta disponibile nei riavvii.

```bash
docker compose up -d
```

I servizi `ollama-phi-pull` e `ollama-gemma-pull` scaricano rispettivamente `phi` e `gemma` e poi stampano `ready`.


## Opzioni per gestire i pull (evitare avvii inutili)

1) Profile-based (opzione 2)

- file: `docker-compose.profiles.yml`
- i servizi `ollama-phi-pull` e `ollama-gemma-pull` sono assegnati al profilo `bootstrap`.
- comandi utili:

```bash
docker compose -f docker-compose.profiles.yml up -d
docker compose -f docker-compose.profiles.yml --profile bootstrap up -d
```

2) Wait-and-pull script (opzione 3)

- file: `docker-compose.waitpull.yml` + `scripts/wait_and_pull.sh`
- il servizio di pull aspetta che l'istanza Ollama risponda e poi esegue `ollama pull` solo se necessario.
- comandi utili:

```bash
docker compose -f docker-compose.waitpull.yml up -d
```

Per usare entrambi i modelli senza cambiare il compose:

Nel notebook scegli il modello commentando/decommentando la riga dedicata in [notebook.ipynb](notebook.ipynb):

Per l'URL scegli la riga corretta in base a dove gira Ollama:

## Note operative
- Il servizio `app` serve se vuoi eseguire codice Python containerizzato oltre al notebook.
- Se lavori solo da notebook, puoi anche avviare soltanto i servizi Ollama.
- La scelta del modello resta esplicita nel notebook e nel compose, non c'e` routing automatico.

## Esempi di file locali (NON versionati)
Questi file devono restare locali e non finire nel repository.

### .env (locale)
```
JUPYTER_RUNTIME_DIR=.venv/var/jupyter/runtime
```

### IDE specifics (json format)
```
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.envFile": "${workspaceFolder}/.env",
  "jupyter.notebookFileRoot": "${workspaceFolder}"
}
```

## Dipendenze
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install crewai langchain langchain-community langgraph
```