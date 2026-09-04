import os
from configparser import ConfigParser
from pathlib import Path

from crewai import Agent, Crew, LLM, Task
from dotenv import load_dotenv


load_dotenv()


def load_llm_options(path=Path(__file__).with_name("model.properties")):
    properties = ConfigParser()
    if not properties.read(path):
        raise ValueError(f"Model properties not found: {path}")

    backend = properties["llm"]["backend"].lower()
    section = f"backend:{backend}"
    if section not in properties:
        raise ValueError(f"Unsupported LLM backend: {backend}")

    model = properties[section].get("model")
    api_key_name = f"{backend.upper()}_API_KEY"
    api_key = os.getenv(api_key_name)
    if not model:
        raise ValueError(f"Set model for backend {backend} in {path}")
    if not api_key:
        raise ValueError(f"Set {api_key_name} in .env")

    return {
        "provider": "hosted_vllm" if backend == "vllm" else backend,
        "model": model,
        "api_key": api_key,
        "base_url": properties[section]["base_url"],
        "temperature": properties.getfloat("llm", "temperature"),
        "top_p": properties.getfloat("llm", "top_p"),
        "max_tokens": properties.getint("llm", "max_tokens"),
        "timeout": properties.getint("llm", "timeout"),
    }


def build_crew(llm):
    analyst = Agent(
        role="Research Analyst",
        goal="Extract exactly 3 key points about {topic}",
        backstory="You are a strict analyst. Be factual and concise.",
        llm=llm,
    )
    writer = Agent(
        role="Technical Writer",
        goal="Write a very short summary from the key points",
        backstory="You write compact technical summaries with no fluff.",
        llm=llm,
    )
    editor = Agent(
        role="Editor",
        goal="Polish output without changing meaning",
        backstory="You enforce clarity, brevity, and consistency.",
        llm=llm,
    )

    return Crew(
        agents=[analyst, writer, editor],
        tasks=[
            Task(
                description="Analyze {topic}. Output exactly 3 bullet points in English. Each bullet max 10 words. No intro. No conclusion.",
                expected_output="Exactly 3 concise bullets in English.",
                agent=analyst,
            ),
            Task(
                description="Use only the research bullets. Write one paragraph in English, max 60 words. Do not add new facts.",
                expected_output="One concise paragraph in English.",
                agent=writer,
            ),
            Task(
                description="Edit for clarity and brevity. Keep meaning unchanged. Output only final text in English, max 50 words.",
                expected_output="Final concise English text.",
                agent=editor,
            ),
        ],
        verbose=True,
    )


if __name__ == "__main__":
    result = build_crew(LLM(**load_llm_options())).kickoff(
        inputs={"topic": "a backend-agnostic AI workflow with CrewAI"}
    )
    print(result)
