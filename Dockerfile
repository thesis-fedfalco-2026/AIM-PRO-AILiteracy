FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir crewai langchain langchain-community langchain-ollama langgraph

COPY . .

CMD ["python", "main.py"]
