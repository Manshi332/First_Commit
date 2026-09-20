# CivicFlow — build with Finch (no Docker Desktop, no AWS account needed):
#   finch build -t civicflow .
#   finch run -p 8501:8501 civicflow
# Or bring up the whole local stack (app + Ollama + LocalStack) at once:
#   finch compose up

FROM python:3.11-slim

WORKDIR /app

# System deps some wheels (Pillow, pydeck) may need to compile/run cleanly.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]