from langchain_community.chat_models import ChatOllama
from crewai import Agent, Task, Crew

# Definizione dei due modelli sulla stessa istanza Ollama
# Nota: l'URL è quello del servizio nel docker-compose (es. http://ollama:11434)
llm_phi = ChatOllama(model="phi", base_url="http://localhost:11434")
llm_gemma = ChatOllama(model="gemma", base_url="http://localhost:11434")

# Creazione degli agenti
analista = Agent(
    role="Analista di Ricerca",
    goal="Trovare informazioni su {topic}",
    backstory="Sei un esperto ricercatore, molto sintetico grazie a Phi.",
    llm=llm_phi  # Questo agente userà Phi
)

scrittore = Agent(
    role="Scrittore Creativo",
    goal="Scrivere un post basato sulla ricerca",
    backstory="Sei un blogger creativo che usa Gemma per uno stile fluido.",
    llm=llm_gemma # Questo agente userà Gemma
)

# CrewAI gestirà il passaggio di messaggi tra i due
# chiedendo a Ollama di usare il modello corretto di volta in volta