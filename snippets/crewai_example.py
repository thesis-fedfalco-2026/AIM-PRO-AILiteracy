# Esempio di definizione agente in CrewAI con Ollama
from crewai import Agent

# Assumendo che 'llm' sia stato configurato come negli snippet precedenti
agent = Agent(
    role='Researcher',
    goal='Trovare informazioni su {topic}',
    backstory='Sei un esperto ricercatore...',
    llm=llm
)
