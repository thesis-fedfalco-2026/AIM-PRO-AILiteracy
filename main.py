from crewai import Agent, Crew, LLM, Task

OLLAMA_BASE_URL = "http://localhost:11434"
PHI_MODEL = "phi"
GEMMA_MODEL = "gemma"

llm_phi = LLM(model=PHI_MODEL, base_url=OLLAMA_BASE_URL, provider="ollama")
llm_gemma = LLM(model=GEMMA_MODEL, base_url=OLLAMA_BASE_URL, provider="ollama")



def is_llm_ok(llm, prompt: str) -> str:
    return llm.call(prompt)


print(f"Base URL: {OLLAMA_BASE_URL}")
print(f"Gemma model: {GEMMA_MODEL} says: {is_llm_ok(llm_gemma, 'Gemma smoke test. Reply with OK if you work.')}")
print(f"Phi model: {PHI_MODEL} says: {is_llm_ok(llm_phi, 'Phi smoke test. Reply with OK if you work.')}")


analyst = Agent(
    role="Research Analyst",
    goal="Extract exactly 3 key points about {topic}",
    backstory="You are a strict analyst. Be factual and concise.",
    llm=llm_gemma,
)

writer = Agent(
    role="Technical Writer",
    goal="Write a very short summary from the key points",
    backstory="You write compact technical summaries with no fluff.",
    llm=llm_gemma,
)

editor = Agent(
    role="Editor",
    goal="Polish output without changing meaning",
    backstory="You enforce clarity, brevity, and consistency.",
    llm=llm_gemma,
)

research_task = Task(
    description="Analyze {topic}. Output exactly 3 bullet points in English. Each bullet max 10 words. No intro. No conclusion.",
    expected_output="Exactly 3 concise bullets in English.",
    agent=analyst,
)

writing_task = Task(
    description="Use only the research bullets. Write one paragraph in English, max 60 words. Do not add new facts.",
    expected_output="One concise paragraph in English.",
    agent=writer,
)

edit_task = Task(
    description="Edit for clarity and brevity. Keep meaning unchanged. Output only final text in English, max 50 words.",
    expected_output="Final concise English text.",
    agent=editor,
)

crew = Crew(
    agents=[analyst, writer, editor],
    tasks=[research_task, writing_task, edit_task],
    verbose=True,
)

if __name__ == "__main__":
    result = crew.kickoff(inputs={"topic": "a local AI workflow with Ollama, LangChain, and CrewAI"})
    print(result)