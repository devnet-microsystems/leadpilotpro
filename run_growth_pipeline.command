#!/bin/bash
# LeadPilot Pro — unified local market intelligence launcher for macOS M1.
# Double-clickable after: chmod +x run_growth_pipeline.command
#
# This single launcher installs the local environment, performs rate-limited
# public market research from user-provided Bing queries, collects from
# user-provided company URLs, imports public business contacts into
# a review queue, previews messages, and sends only manually approved batches.

set -Eeuo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="$SCRIPT_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/logs"
TEMPLATE_FILE="$SCRIPT_DIR/templates/agency_intro.txt"
OUTREACH_DB="$SCRIPT_DIR/outreach_queue.sqlite3"
OUTREACH_AUDIT="$SCRIPT_DIR/outreach_audit.jsonl"

# Direct company-URL collector inputs and outputs.
SEED_FILE="$SCRIPT_DIR/seed_sites.csv"
DIRECT_LEADS_FILE="$SCRIPT_DIR/b2b_enterprise_leads.csv"
DIRECT_COLLECTOR_AUDIT="$SCRIPT_DIR/lead_collector_audit.jsonl"

# Public market-research search inputs and outputs.
QUERY_FILE="$SCRIPT_DIR/market_research_queries.csv"
OSINT_LEADS_FILE="$SCRIPT_DIR/public_business_leads.csv"
OSINT_DATABASE="$SCRIPT_DIR/public_osint_state.sqlite3"
OSINT_AUDIT="$SCRIPT_DIR/public_osint_audit.jsonl"

CAMPAIGN_DEFAULT="wordpress-agencies-pilot"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
info() { printf '[INFO] %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1" >&2; }
fail() { printf '[ERROR] %s\n' "$1" >&2; exit 1; }

trap 'fail "The launcher stopped at line $LINENO. Read the message above and the audit logs for details."' ERR

ensure_python() {
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "python3 was not found. Install Python 3.11+ for macOS Apple Silicon, then run this file again."
  "$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("Python 3.10 or newer is required.")
PY
}

bootstrap() {
  ensure_python
  mkdir -p "$LOG_DIR" "$SCRIPT_DIR/templates"

  if [[ ! -d "$VENV_DIR" ]]; then
    info "Creating local Python virtual environment…"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  info "Installing or updating local dependencies…"
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt" >/dev/null
  if ! "$VENV_DIR/bin/python" -c 'from playwright.sync_api import sync_playwright' >/dev/null 2>&1; then
    fail "Playwright is unavailable after installation. Check the network connection and rerun the launcher."
  fi
  if ! "$VENV_DIR/bin/python" -m playwright install chromium; then
    fail "Chromium installation failed. With a network connection, rerun: .venv/bin/python -m playwright install chromium"
  fi

  [[ -f "$SCRIPT_DIR/.env" ]] || {
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    chmod 600 "$SCRIPT_DIR/.env"
    warn "Created .env. Set your SMTP details before using the send option."
  }
  [[ -f "$SEED_FILE" ]] || {
    cp "$SCRIPT_DIR/seed_sites.example.csv" "$SEED_FILE"
    warn "Created seed_sites.csv. Replace example values with approved company URLs before direct collection."
  }
  [[ -f "$QUERY_FILE" ]] || {
    cp "$SCRIPT_DIR/market_research_queries.example.csv" "$QUERY_FILE"
    warn "Created market_research_queries.csv. Review the queries before public market research."
  }
}

load_env() {
  [[ -f "$SCRIPT_DIR/.env" ]] || fail "Missing .env. Run setup first."
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
  set +a
}

prompt_campaign() {
  local campaign
  read -r -p "Campaign name [${CAMPAIGN_DEFAULT}]: " campaign
  printf '%s' "${campaign:-$CAMPAIGN_DEFAULT}"
}

choose_template() {
  local selected_file
  printf "\nAvailable templates in templates/:\n" >&2
  for t in "$SCRIPT_DIR"/templates/*.txt; do
    printf "  - %s\n" "$(basename "$t")" >&2
  done
  read -r -p "Enter the template filename to use [agency_intro.txt]: " selected_file >&2
  selected_file="${selected_file:-agency_intro.txt}"
  TEMPLATE_FILE="$SCRIPT_DIR/templates/$selected_file"
  [[ -f "$TEMPLATE_FILE" ]] || fail "Template file not found: $TEMPLATE_FILE"
}

import_leads_file() {
  local leads_file="$1"
  local campaign
  [[ -s "$leads_file" ]] || { warn "No contacts CSV was created: $leads_file"; return 0; }
  campaign="$(prompt_campaign)"
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" \
    --database "$OUTREACH_DB" \
    --audit-log "$OUTREACH_AUDIT" \
    import --csv "$leads_file" --campaign "$campaign"
  info "Imported contacts are pending review. Choose option 6 to inspect them before approval."
}

run_public_osint_debug() {
  [[ -s "$QUERY_FILE" ]] || fail "market_research_queries.csv is missing or empty. Add one test query first."
  bold "OSINT debug — one query, one test run"
  info "The browser will be visible. No email is sent. Debug files are saved under debug_osint/."
  rm -rf "$SCRIPT_DIR/debug_osint"
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/public_osint_market_research.py" \
    --queries "$QUERY_FILE" \
    --output "$SCRIPT_DIR/debug_public_business_leads.csv" \
    --database "$SCRIPT_DIR/debug_public_osint_state.sqlite3" \
    --audit-log "$SCRIPT_DIR/debug_public_osint_audit.jsonl" \
    --results-per-query 3 \
    --max-queries 1 \
    --max-contact-pages-per-site 1 \
    --debug-dir "$SCRIPT_DIR/debug_osint" \
    --fast \
    --headed \
    --log-level DEBUG
  printf '\n'
  info "Debug finished. Inspect debug_osint/*.html and *.png plus debug_public_osint_audit.jsonl."
}

run_public_osint_research() {
  [[ -s "$QUERY_FILE" ]] || fail "market_research_queries.csv is missing or empty. Add approved business queries first."
  bold "Public OSINT market research"
  info "This performs one Bing result page per query, waits between queries, skips blocks, respects robots.txt, and stores only public business contacts."
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/public_osint_market_research.py" \
    --queries "$QUERY_FILE" \
    --output "$OSINT_LEADS_FILE" \
    --database "$OSINT_DATABASE" \
    --audit-log "$OSINT_AUDIT" \
    --results-per-query 10 \
    --max-contact-pages-per-site 2
  import_leads_file "$OSINT_LEADS_FILE"
}

run_direct_company_collection() {
  [[ -s "$SEED_FILE" ]] || fail "seed_sites.csv is missing or empty. Add approved company URLs first."
  bold "Collection from approved company URLs"
  info "The collector honours robots.txt and stores only explicitly published business contacts."
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/public_business_lead_collector.py" \
    --input "$SEED_FILE" \
    --output "$DIRECT_LEADS_FILE" \
    --database "$SCRIPT_DIR/lead_collector_state.sqlite3" \
    --audit-log "$DIRECT_COLLECTOR_AUDIT"
  import_leads_file "$DIRECT_LEADS_FILE"
}

review_queue() {
  bold "Pending review queue"
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" --database "$OUTREACH_DB" list --status pending_review
  printf '\n'
  info "Approve only records with a verified company fit and a factual, public reason for contact."
}

approve_prospect() {
  local input reason campaign
  read -r -p "Enter prospect ID to approve ONE, or type 'ALL' to approve all pending: " input
  if [[ "$input" == "ALL" || "$input" == "all" ]]; then
    campaign="$(prompt_campaign)"
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" \
      --database "$OUTREACH_DB" \
      --audit-log "$OUTREACH_AUDIT" \
      approve-all --campaign "$campaign" --reason "Identified via OSINT market research for LeadPilot Pro"
  else
    [[ "$input" =~ ^[0-9]+$ ]] || fail "Prospect ID must be a number or 'ALL'."
    read -r -p "Public factual reason for contact: " reason
    [[ -n "${reason// }" ]] || fail "A public factual reason is required."
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" \
      --database "$OUTREACH_DB" \
      --audit-log "$OUTREACH_AUDIT" \
      approve --id "$input" --reason "$reason"
  fi
}

preview_campaign() {
  local campaign
  campaign="$(prompt_campaign)"
  load_env
  choose_template
  bold "Preview only — no email will be sent"
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" \
    --database "$OUTREACH_DB" \
    --audit-log "$OUTREACH_AUDIT" \
    send --campaign "$campaign" --template "$TEMPLATE_FILE" --limit 2
}

send_approved_batch() {
  local campaign limit confirmation
  campaign="$(prompt_campaign)"
  load_env
  choose_template
  read -r -p "How many already-approved records should be sent now? [1-20]: " limit
  [[ "$limit" =~ ^([1-9]|1[0-9]|20)$ ]] || fail "For safety, choose an integer from 1 to 20."
  bold "Final check"
  info "This will send up to $limit email(s) from ${OUTREACH_FROM_EMAIL:-your configured sender} to manually approved, non-suppressed business contacts."
  read -r -p "Type SEND to confirm this real email action: " confirmation
  [[ "$confirmation" == "SEND" ]] || { info "No email was sent."; return 0; }
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" \
    --database "$OUTREACH_DB" \
    --audit-log "$OUTREACH_AUDIT" \
    send --campaign "$campaign" --template "$TEMPLATE_FILE" --limit "$limit" --send --confirm-send
}

suppress_address() {
  local email reason
  read -r -p "Business email to suppress: " email
  read -r -p "Reason [opt-out or exclusion]: " reason
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" \
    --database "$OUTREACH_DB" \
    --audit-log "$OUTREACH_AUDIT" \
    suppress --email "$email" --reason "${reason:-manual opt-out or exclusion}"
}

show_status() {
  bold "Pipeline status"
  printf '\nPending review:\n'
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" --database "$OUTREACH_DB" list --status pending_review || true
  printf '\nApproved:\n'
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" --database "$OUTREACH_DB" list --status approved || true
  printf '\nSent:\n'
  "$VENV_DIR/bin/python" "$SCRIPT_DIR/outreach_sender.py" --database "$OUTREACH_DB" list --status sent || true
  printf '\nPipeline files:\n'
  [[ -f "$OSINT_LEADS_FILE" ]] && printf '  OSINT research CSV: %s\n' "$OSINT_LEADS_FILE"
  [[ -f "$DIRECT_LEADS_FILE" ]] && printf '  Direct-site collector CSV: %s\n' "$DIRECT_LEADS_FILE"
  [[ -f "$OSINT_AUDIT" ]] && printf '  OSINT audit: %s\n' "$OSINT_AUDIT"
  [[ -f "$DIRECT_COLLECTOR_AUDIT" ]] && printf '  Direct collector audit: %s\n' "$DIRECT_COLLECTOR_AUDIT"
  [[ -f "$OUTREACH_AUDIT" ]] && printf '  Outreach audit: %s\n' "$OUTREACH_AUDIT"
}

launch_dashboard() {
  bold "Starting LeadPilot Pro Web Dashboard..."
  info "Opening http://127.0.0.1:8000 in your browser. Press Ctrl+C in this terminal to stop."
  (sleep 1.5 && open "http://127.0.0.1:8000" 2>/dev/null || true) &
  "$VENV_DIR/bin/uvicorn" web_server:app --host 127.0.0.1 --port 8000
}

main_menu() {
  bootstrap
  
  if [[ "${1:-}" != "debug" ]]; then
    launch_dashboard
    return 0
  fi

  while true; do
    printf '\n'
    bold "--- DEBUG CLI ---"
    printf '%s\n' \
      "1) Setup / verify local environment" \
      "2) Public OSINT market research from Bing queries + import" \
      "3) OSINT DEBUG — one query + browser + snapshots" \
      "4) Collect from approved company URLs + import" \
      "5) Edit configuration and query files" \
      "6) View pending review queue" \
      "7) Approve prospects (Single or All)" \
      "8) Preview approved campaign emails (no sending)" \
      "9) Send a small batch of approved emails" \
      "10) Add an opt-out / do-not-contact record" \
      "11) Show pipeline status" \
      "12) Exit"
    read -r -p "Choose an option: " choice
    case "$choice" in
      1) bootstrap ;;
      2) run_public_osint_research ;;
      3) run_public_osint_debug ;;
      4) run_direct_company_collection ;;
      5) info "Edit .env, market_research_queries.csv, seed_sites.csv and templates/agency_intro.txt with your preferred text editor." ;;
      6) review_queue ;;
      7) approve_prospect ;;
      8) preview_campaign ;;
      9) send_approved_batch ;;
      10) suppress_address ;;
      11) show_status ;;
      12) info "Goodbye."; exit 0 ;;
      *) warn "Choose a number from 1 to 12." ;;
    esac
  done
}

main_menu "$@"
