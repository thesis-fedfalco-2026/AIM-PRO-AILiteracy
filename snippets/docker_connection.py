from langchain_community.llms import Ollama

# All'interno di Docker, usare l'hostname del servizio
llm = Ollama(
    model="llama3",
    base_url="http://ollama:11434"
)
