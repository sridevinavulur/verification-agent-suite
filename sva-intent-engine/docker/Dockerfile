FROM python:3.11-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e ".[dev]"

# Deterministic offline entrypoint; no network or LLM required.
ENTRYPOINT ["sva-intent"]
CMD ["demo"]
