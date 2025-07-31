#!/bin/bash
# run this on your local machine with browser access

CLIENT_ID="8nPz86DgDt5X991wAm9bhKJHCaCC19nf"
CLIENT_SECRET="ATOA8Imc3BNmESlJXZ14-VL7Rv8YjcI9SJKXyPn43AZeq0_VzT8Kyi0995CUYsNPpuyJ2112CE7D"
REDIRECT_URI="http://localhost:8080"  # or your configured redirect URI

# Step 1: Generate authorization URL
AUTH_URL="https://auth.atlassian.com/authorize?audience=api.atlassian.com&client_id=${CLIENT_ID}&scope=read%3Ajira-user%20read%3Ajira-work%20write%3Ajira-work&redirect_uri=${REDIRECT_URI}&state=your-state&response_type=code&prompt=consent"

echo "Open this URL in your browser:"
echo $AUTH_URL

echo "After authorization, you'll be redirected to your redirect URI with a 'code' parameter."
echo "Copy that authorization code and paste it here:"
read -p "Authorization code: " AUTH_CODE

# Step 2: Exchange code for tokens
RESPONSE=$(curl -s --request POST \
  --url 'https://auth.atlassian.com/oauth/token' \
  --header 'Content-Type: application/json' \
  --data '{
    "grant_type": "authorization_code",
    "client_id": "'"$CLIENT_ID"'",
    "client_secret": "'"$CLIENT_SECRET"'",
    "code": "'"$AUTH_CODE"'",
    "redirect_uri": "'"$REDIRECT_URI"'"
  }')

ACCESS_TOKEN=$(echo $RESPONSE | jq -r .access_token)
REFRESH_TOKEN=$(echo $RESPONSE | jq -r .refresh_token)

echo "Access Token: $ACCESS_TOKEN"
echo "Refresh Token: $REFRESH_TOKEN"
echo ""
echo "Save this refresh token for your container:"
echo "REFRESH_TOKEN=$REFRESH_TOKEN"
