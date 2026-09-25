FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app
COPY requirements.txt .

# Install dependencies and update Playwright to match requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium

COPY . .

# Initialize the database with schema and default admin user, then set password to LeadPilot2026!
RUN python -c "from schema_bootstrap import ensure_all_schema; ensure_all_schema('outreach_queue.sqlite3'); import hashlib, os, sqlite3; new_salt = os.urandom(16); new_hash = hashlib.pbkdf2_hmac('sha256', b'LeadPilot2026!', new_salt, 100000); conn = sqlite3.connect('outreach_queue.sqlite3'); conn.execute('UPDATE users SET password_hash = ?, salt = ? WHERE username = ?', (new_hash, new_salt, 'admin')); conn.commit()"

# Expose port (Cloud Run uses PORT environment variable)
ENV PORT 8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn web_server:app --host 0.0.0.0 --port ${PORT}"]
