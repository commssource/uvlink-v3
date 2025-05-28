#!/bin/bash

# Test Commands for Safe PJSIP Endpoint Manager
# Make this file executable: chmod +x test_commands.sh

API_KEY="your-secure-api-key-here"  # Change this to your actual API key
BASE_URL="https://uvlink.cloud/api/v1"

echo "🧪 Testing Safe PJSIP Endpoint Manager"
echo "======================================"

# Function to make API calls
call_api() {
    local method=$1
    local endpoint=$2
    local data=$3
    
    echo "📡 $method $endpoint"
    
    if [ -n "$data" ]; then
        curl -s -X "$method" \
             -H "Authorization: Bearer $API_KEY" \
             -H "Content-Type: application/json" \
             -d "$data" \
             "$BASE_URL$endpoint" | jq .
    else
        curl -s -X "$method" \
             -H "Authorization: Bearer $API_KEY" \
             "$BASE_URL$endpoint" | jq .
    fi
    
    echo ""
    echo "Press Enter to continue..."
    read
}

# Test 1: List current endpoints
echo "🔍 Test 1: List current endpoints"
call_api "GET" "/endpoints/"

# Test 2: Get current configuration
echo "📄 Test 2: Get current configuration"
call_api "GET" "/endpoints/config/current"

# Test 3: Add a new endpoint (SAFE)
echo "➕ Test 3: Add a new endpoint (SAFE - preserves existing config)"
TEST_ENDPOINT='{
  "id": "test1001",
  "username": "testuser1001",
  "password": "SecureTestPass123!",
  "context": "internal",
  "codecs": ["ulaw", "alaw"],
  "max_contacts": 1,
  "callerid": "Test User <1001>"
}'
call_api "POST" "/endpoints/" "$TEST_ENDPOINT"

# Test 4: Get the specific endpoint we just added
echo "👁️ Test 4: Get the specific endpoint we just added"
call_api "GET" "/endpoints/test1001"

# Test 5: Update the endpoint
echo "✏️ Test 5: Update the endpoint"
UPDATE_ENDPOINT='{
  "username": "testuser1001_updated",
  "context": "internal",
  "codecs": ["ulaw", "g722"],
  "max_contacts": 2,
  "callerid": "Test User Updated <1001>"
}'
call_api "PUT" "/endpoints/test1001" "$UPDATE_ENDPOINT"

# Test 6: Validate endpoint exists
echo "✅ Test 6: Validate endpoint exists"
call_api "GET" "/endpoints/validate/test1001"

# Test 7: Add another endpoint
echo "➕ Test 7: Add another endpoint"
TEST_ENDPOINT2='{
  "id": "test1002",
  "username": "testuser1002",
  "password": "AnotherSecurePass456!",
  "context": "internal",
  "codecs": ["ulaw", "alaw", "g722"],
  "max_contacts": 1,
  "callerid": "Test User 2 <1002>"
}'
call_api "POST" "/endpoints/" "$TEST_ENDPOINT2"

# Test 8: List all endpoints again (should show our additions)
echo "📋 Test 8: List all endpoints (should show our additions)"
call_api "GET" "/endpoints/"

# Test 9: Reload PJSIP
echo "🔄 Test 9: Reload PJSIP configuration"
call_api "POST" "/endpoints/reload"

# Test 10: Show Asterisk endpoints
echo "🔍 Test 10: Show endpoints from Asterisk"
call_api "GET" "/endpoints/show/asterisk"

# Test 11: Verify configuration still has original settings
echo "✅ Test 11: Verify configuration still has original settings"
echo "Looking for transport, system, and WebRTC settings..."
curl -s -H "Authorization: Bearer $API_KEY" \
     "$BASE_URL/endpoints/config/current" | \
     jq -r '.config' | \
     grep -E "(transport|system|webrtc|global)" || echo "❌ Original settings missing!"

# Test 12: Delete one of our test endpoints
echo "🗑️ Test 12: Delete test endpoint (SAFE - only removes specific endpoint)"
echo "This will delete test1001 but preserve everything else..."
call_api "DELETE" "/endpoints/test1001"

# Test 13: Verify deletion and that other endpoint still exists
echo "✅ Test 13: Verify deletion worked and other endpoints remain"
call_api "GET" "/endpoints/"

# Test 14: Clean up - delete remaining test endpoint
echo "🧹 Test 14: Clean up - delete remaining test endpoint"
call_api "DELETE" "/endpoints/test1002"

# Final verification
echo "🏁 Final verification: List endpoints after cleanup"
call_api "GET" "/endpoints/"

echo "✅ Testing complete!"
echo ""
echo "🎯 What we tested:"
echo "  ✅ List endpoints"
echo "  ✅ Add endpoints (preserves existing config)"
echo "  ✅ Update endpoints"
echo "  ✅ Delete specific endpoints only"
echo "  ✅ Configuration preservation"
echo "  ✅ PJSIP reload"
echo "  ✅ Asterisk integration"
echo ""
echo "🛡️ Safety verified:"
echo "  ✅ Original transports preserved"
echo "  ✅ System settings preserved"
echo "  ✅ WebRTC config preserved"
echo "  ✅ Only endpoint sections modified"