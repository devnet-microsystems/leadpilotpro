FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app
COPY requirements.txt .

# Install dependencies and update Playwright to match requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

# Initialize the database schema only. The admin password must be supplied
# at runtime through LEADPILOT_ADMIN_PASSWORD (Cloud Run / secret manager).
RUN python -c "from schema_bootstrap import ensure_all_schema; ensure_all_schema('outreach_queue.sqlite3')"

# Expose port (Cloud Run uses PORT environment variable)
ENV PORT 8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn web_server:app --host 0.0.0.0 --port ${PORT}"]
