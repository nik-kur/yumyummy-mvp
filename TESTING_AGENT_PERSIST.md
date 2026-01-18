# Manual Testing Instructions for Agent Persistence

This document describes how to test that agent workflow results are correctly persisted to the database.

## Prerequisites

1. Backend is running: `uvicorn app.main:app --reload`
2. Database is set up and accessible
3. Environment variables are configured (`.env` file with `OPENAI_API_KEY`, `DATABASE_URL`, etc.)

## Test 1: log_meal intent

### Step 1: Call /agent/run with a meal description

```bash
curl -X POST http://127.0.0.1:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": "12345",
    "text": "сырники из кофемании"
  }'
```

Expected response: JSON with `intent: "log_meal"` (or `"eatout"`), `totals` with non-zero values, and `items` array.

### Step 2: Get user_id from /users endpoint

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": "12345"
  }'
```

Note the `id` field from the response (e.g., `{"id": 1, "telegram_id": "12345", ...}`).

### Step 3: Check /day endpoint for today

```bash
# Replace {user_id} with the id from step 2
# Replace {today} with today's date in YYYY-MM-DD format
curl http://127.0.0.1:8000/day/{user_id}/{today}
```

Example:
```bash
curl http://127.0.0.1:8000/day/1/2024-01-15
```

Expected response: JSON with:
- `total_calories` > 0
- `meals` array containing at least one entry
- The meal entry should have `description_user` matching the meal name
- `calories`, `protein_g`, `fat_g`, `carbs_g` should match the `totals` from step 1

## Test 2: product intent

### Step 1: Call /agent/run with a product query

```bash
curl -X POST http://127.0.0.1:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": "12345",
    "text": "творог Президент 200г"
  }'
```

Expected response: JSON with `intent: "product"`, `totals` with non-zero values.

### Step 2: Verify in /day endpoint

Use the same user_id and today's date:

```bash
curl http://127.0.0.1:8000/day/{user_id}/{today}
```

Expected: The meal entry should appear in the `meals` array with correct nutrition values.

## Test 3: eatout intent

### Step 1: Call /agent/run with a restaurant dish

```bash
curl -X POST http://127.0.0.1:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": "12345",
    "text": "Pumpkin Spice Latte из Starbucks"
  }'
```

Expected response: JSON with `intent: "eatout"`, `totals` with non-zero values.

### Step 2: Verify in /day endpoint

```bash
curl http://127.0.0.1:8000/day/{user_id}/{today}
```

Expected: The meal entry should appear with restaurant dish name and nutrition values.

## Test 4: help/unknown intents (should NOT persist)

### Step 1: Call /agent/run with a help query

```bash
curl -X POST http://127.0.0.1:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": "12345",
    "text": "что ты умеешь?"
  }'
```

Expected response: JSON with `intent: "help"`, `totals` all zeros, `items` empty.

### Step 2: Verify NO new meal entry

```bash
curl http://127.0.0.1:8000/day/{user_id}/{today}
```

Expected: No new meal entries should be created (only previous test entries if any).

## Test 5: Empty result (should NOT persist)

### Step 1: Call /agent/run with a query that returns empty result

```bash
curl -X POST http://127.0.0.1:8000/agent/run \
  -H "Content-Type: application/json" \
  -d '{
    "telegram_id": "12345",
    "text": "штрихкод 1234567890123"
  }'
```

Expected response: JSON with `intent: "barcode"` (or other), but `totals` all zeros, `items` empty, `confidence: null`.

### Step 2: Verify NO new meal entry

```bash
curl http://127.0.0.1:8000/day/{user_id}/{today}
```

Expected: No new meal entries should be created.

## Verification Checklist

- [ ] log_meal intent creates meal entry in database
- [ ] product intent creates meal entry in database
- [ ] eatout intent creates meal entry in database
- [ ] barcode intent creates meal entry (if data found)
- [ ] help/unknown intents do NOT create meal entries
- [ ] Empty results (all zeros, no items, no confidence) do NOT create meal entries
- [ ] Meal entries appear in /day endpoint
- [ ] User is auto-created if doesn't exist
- [ ] UserDay is auto-created for today if doesn't exist
- [ ] Day totals are correctly aggregated

## Troubleshooting

If meal entries are not appearing:

1. Check backend logs for `[PERSIST]` messages
2. Verify database connection is working
3. Check that `intent` is one of: `log_meal`, `product`, `eatout`, `barcode`
4. Verify that `totals` are not all zeros OR `items` is not empty OR `confidence` is not null
5. Check for exceptions in logs with `[PERSIST] Error persisting agent result`
