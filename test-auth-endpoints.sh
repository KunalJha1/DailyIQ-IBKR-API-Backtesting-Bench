#!/usr/bin/env bash
# Test DailyIQ auth endpoints used by the Tauri Google OAuth flow.
# Usage: bash test-auth-endpoints.sh [BASE_URL]
#   Defaults to http://localhost:3000 (from .env VITE_DAILYIQ_URL)

BASE_URL="${1:-http://localhost:3000}"

echo "=========================================="
echo "Testing DailyIQ auth endpoints"
echo "Base URL: $BASE_URL"
echo "=========================================="
echo ""

# 1. terminal-google-url
echo "--- GET /api-proxy/auth/terminal-google-url ---"
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$BASE_URL/api-proxy/auth/terminal-google-url")
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS:/d')
STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "Status: $STATUS"
echo "Body: $BODY"

if [ "$STATUS" = "200" ]; then
  URL=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('url','MISSING'))" 2>/dev/null)
  if [ "$URL" = "MISSING" ] || [ -z "$URL" ]; then
    echo "FAIL: Response missing 'url' field"
  else
    echo "OK: Got OAuth URL (starts with: ${URL:0:60}...)"
  fi
else
  echo "FAIL: Expected 200, got $STATUS"
fi
echo ""

# 2. terminal-login (email/password)
echo "--- POST /api-proxy/auth/terminal-login ---"
echo "(Testing with dummy credentials to check endpoint exists)"
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"wrongpassword"}' \
  "$BASE_URL/api-proxy/auth/terminal-login")
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS:/d')
STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "Status: $STATUS"
echo "Body: $BODY"

if [ "$STATUS" = "404" ] || [ "$STATUS" = "000" ]; then
  echo "FAIL: Endpoint doesn't exist (got $STATUS)"
elif [ "$STATUS" = "200" ]; then
  # Check response shape
  HAS_KEY=$(echo "$BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('api_key') else 'no')" 2>/dev/null)
  echo "OK: Endpoint exists (api_key present: $HAS_KEY)"
else
  echo "OK: Endpoint exists, returned $STATUS (likely auth error for bad creds — expected)"
fi
echo ""

# 3. terminal-google-exchange (with fake code to check endpoint exists)
echo "--- POST /api-proxy/auth/terminal-google-exchange ---"
echo "(Testing with fake code to check endpoint exists + response shape)"
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
  -H "Content-Type: application/json" \
  -d '{"code":"fake_code_for_endpoint_test"}' \
  "$BASE_URL/api-proxy/auth/terminal-google-exchange")
BODY=$(echo "$RESPONSE" | sed '/HTTP_STATUS:/d')
STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
echo "Status: $STATUS"
echo "Body: $BODY"

if [ "$STATUS" = "404" ] || [ "$STATUS" = "000" ]; then
  echo "FAIL: Endpoint doesn't exist (got $STATUS)"
elif [ "$STATUS" = "200" ]; then
  # Check response shape: needs api_key, user_id, email, name
  python3 - <<'PYEOF'
import sys, json
body = """$BODY"""
try:
    d = json.loads(body)
    missing = [f for f in ['api_key','user_id','email','name'] if not d.get(f)]
    if missing:
        print(f"  WARNING: Response is 200 but missing fields: {missing}")
        print(f"  Got keys: {list(d.keys())}")
    else:
        print("  OK: Response has all required fields (api_key, user_id, email, name)")
except Exception as e:
    print(f"  Could not parse JSON: {e}")
PYEOF
else
  echo "OK: Endpoint exists, returned $STATUS (fake code rejected — expected)"
  # For non-200, just note if it's a recognizable error
  echo "  (If this is 400/422 with 'invalid code' error, endpoint is working correctly)"
fi
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
echo "If terminal-google-url returns 200 with a 'url' field:     GOOD"
echo "If terminal-google-exchange returns 4xx for a fake code:    GOOD (endpoint exists)"
echo "If terminal-google-exchange returns 404/000:                BAD  (endpoint missing)"
echo ""
echo "The most common failure: terminal-google-exchange is missing or"
echo "returns a different JSON shape than {api_key, user_id, email, name}"
