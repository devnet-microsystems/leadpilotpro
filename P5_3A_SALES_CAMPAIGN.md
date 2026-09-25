# P5.3A - Product -> Sales Strategy -> Email Campaign

## Overview

This module acts as the bridge between "understanding what to sell and to whom" (Product Intelligence) and "how to actually pitch it" (Outreach). Given a `Product Profile`, a `Market`, and an `ICP (Target Segment + Buyer Role)`, LeadPilot generates a commercial **Sales Strategy** and a tailored **4-Email Sequence**.

This implementation enforces strict **DRAFT** safety, idempotency, and anti-hallucination rules. It leverages the global `get_ai_provider()` instead of hardcoding LLM services.

## Architecture

We audited the existing `campaigns` and `templates` tables and found them inadequate for sequential, context-aware campaigns (they are flat structures for single-send emails). However, to prevent breaking legacy systems, we created a **parallel product-driven campaign structure** while leaving the legacy system entirely untouched.

### New Schema (Migration P5.3A)

1. **`product_sales_strategies`**: Stores the high-level JSON strategy per unique context.
2. **`product_campaigns`**: Container for the sequence. Stores the status (`DRAFT`, `APPROVED`) and the `sequence_length`.
3. **`email_sequence_messages`**: The individual sequence touches (subject, body, delay_days).

**Unique Identity**: `(product_id, research_campaign_id, market, language, target_segment, buyer_role)`.
This guarantees that we can generate strategies for different roles (e.g. CEO vs VP Sales) in the same market without colliding, while preventing infinite Cartesian explosion. Strategies are only generated for combinations explicitly requested by the `ResearchCampaign`.

## AI Agents

Located in `product_intelligence/sales_strategy_agent.py`.

### 1. `SalesStrategyAgent`
- **Input**: Product profile (fact-checked data), Market, Language, Target Segment, Buyer Role.
- **Output**: Strict JSON (value prop, pain points, proof points, CTA, tone).
- **Safety**: Instructed to treat the product profile as pure data. Explicitly blocked from inventing prices or features.

### 2. `EmailSequenceAgent`
- **Input**: Strategy JSON, Product profile, Sequence length (default 4).
- **Output**: JSON array of messages (subject, body, delay_days, placeholders).
- **Safety**: Validates all `{{ placeholders }}` against an `ALLOWED_FIELDS` list (`first_name`, `company_name`, `why_matched`, etc.). Rejects messages with duplicate bodies or invalid placeholders.

## Sender Safety & Idempotency

- All sequences are generated as **DRAFT**.
- Re-running generation for an existing context will **UPDATE** the DRAFT.
- If a campaign has been marked **APPROVED**, **ACTIVE**, or **SENT**, the system will **SKIP** generation and preserve the existing campaign.
- No auto-sending is performed. The legacy P1-P4 `outreach_sender` is not modified and does not pull from `product_campaigns` automatically.

## P5.3A Status Report

P5.3A STATUS: GREEN

| Feature | Status |
|---|---|
| EMAIL ARCHITECTURE AUDIT | PASS (Built parallel structure) |
| STRATEGY | PASS |
| SEQUENCE | PASS |
| 4 EMAILS | PASS (Configurable length supported) |
| MARKET LOCALIZATION | PASS |
| LANGUAGE | PASS |
| ROLE AWARENESS | PASS (Included in UNIQUE constraint) |
| PRODUCT AWARENESS | PASS |
| ANTI-HALLUCINATION | PASS (System prompts + strict JSON parsing) |
| PERSONALIZATION | PASS |
| PLACEHOLDER VALIDATION | PASS |
| IDEMPOTENCY | PASS (Upsert logic preserves state) |
| DRAFT PRESERVATION | PASS |
| APPROVED PRESERVATION | PASS |
| PROVIDER FAILURE | PASS (Graceful FAILED status) |
| MULTI-MARKET | PASS |
| MULTI-SOURCE | PASS |
| NO AUTO-SEND | PASS |
| REAL AI | PASS |
| REAL E2E | PASS |
| REGRESSION | PASS |

### Files
**Modified:** None
**Created:**
- `migration_p5_3a.py`
- `product_intelligence/sales_campaign_store.py`
- `product_intelligence/sales_strategy_agent.py`
- `tests/test_p5_3a_sales_campaign.py`
- `P5_3A_SALES_CAMPAIGN.md`
