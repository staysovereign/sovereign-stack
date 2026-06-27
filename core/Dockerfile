FROM python:3.12-slim

WORKDIR /app

COPY core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build context is the repo root (see docker-compose core.build.context).
# The app uses absolute imports rooted at the repo: core.*, engine.*,
# delivery.*, advisor.*, reply.* — so all of these packages must be present.
COPY core/ ./core/
COPY engine/ ./engine/
COPY delivery/ ./delivery/
COPY advisor/ ./advisor/
COPY reply/ ./reply/

CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
