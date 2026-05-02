# py-prototype

Questo progetto resta indipendente dal Python globale e tiene Jupyter isolato nel virtualenv.

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
Crea la cartella runtime e definisci la variabile d'ambiente locale.

```bash
mkdir -p .venv/var/jupyter/runtime
```

## Per usare il progetto
installa anche le librerie necessarie (esempio):
```bash
python -m pip install crewai langchain langchain-community
```
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
python -m pip install crewai langchain langchain-community
```