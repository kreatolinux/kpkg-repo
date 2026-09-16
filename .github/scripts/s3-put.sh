#!/bin/sh
# Minimal AWS SigV4 single-PUT uploader for S3-compatible object stores.
# Uses only curl + openssl, so it works in any builder image.
# usage: s3-put.sh <endpoint> <bucket> <local-file> <remote-key>
# env:   AWS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION (default us-east-1)
set -eu

ENDPOINT="$1"
BUCKET="$2"
FILE="$3"
KEY="$4"
REGION="${AWS_REGION:-us-east-1}"

HOST=$(printf '%s' "$ENDPOINT" | sed -e 's#^https\?://##' -e 's#/$##')
PAYLOAD_HASH=$(sha256sum "$FILE" | awk '{print $1}')
AMZ_DATE=$(date -u +%Y%m%dT%H%M%SZ)
DATESTAMP=${AMZ_DATE%%T*}
SCOPE="$DATESTAMP/$REGION/s3/aws4_request"

CANONICAL="PUT
/$BUCKET/$KEY

host:$HOST
x-amz-content-sha256:$PAYLOAD_HASH
x-amz-date:$AMZ_DATE

host;x-amz-content-sha256;x-amz-date
$PAYLOAD_HASH"

CANONICAL_HASH=$(printf '%s' "$CANONICAL" | sha256sum | awk '{print $1}')
STRING_TO_SIGN="AWS4-HMAC-SHA256
$AMZ_DATE
$SCOPE
$CANONICAL_HASH"

# Derive the signing key: HMAC chain over datestamp, region, service, "aws4_request".
K=$(printf '%s' "$DATESTAMP" | openssl dgst -sha256 -mac HMAC -macopt key:"AWS4$AWS_SECRET_ACCESS_KEY" -binary | od -An -tx1 | tr -d ' \n')
K=$(printf '%s' "$DATESTAMP" | openssl dgst -sha256 -mac HMAC -macopt hexkey:"$K" -binary | od -An -tx1 | tr -d ' \n')
K=$(printf '%s' "$REGION" | openssl dgst -sha256 -mac HMAC -macopt hexkey:"$K" -binary | od -An -tx1 | tr -d ' \n')
K=$(printf '%s' "s3" | openssl dgst -sha256 -mac HMAC -macopt hexkey:"$K" -binary | od -An -tx1 | tr -d ' \n')
K=$(printf '%s' "aws4_request" | openssl dgst -sha256 -mac HMAC -macopt hexkey:"$K" -binary | od -An -tx1 | tr -d ' \n')

SIGNATURE=$(printf '%s' "$STRING_TO_SIGN" | openssl dgst -sha256 -mac HMAC -macopt hexkey:"$K" -hex | awk '{print $NF}')

AUTH="AWS4-HMAC-SHA256 Credential=$AWS_KEY_ID/$SCOPE, SignedHeaders=host;x-amz-content-sha256;x-amz-date, Signature=$SIGNATURE"

HTTP=$(curl -sS -X PUT \
  -H "Authorization: $AUTH" \
  -H "x-amz-date: $AMZ_DATE" \
  -H "x-amz-content-sha256: $PAYLOAD_HASH" \
  --data-binary @"$FILE" \
  -o "$FILE.s3resp" \
  -w '%{http_code}' \
  "$ENDPOINT/$BUCKET/$KEY") || HTTP="curl-error"
case "$HTTP" in
  200|201|204)
    rm -f "$FILE.s3resp"
    exit 0
    ;;
  *)
    echo "S3 PUT failed: HTTP $HTTP for $BUCKET/$KEY"
    cat "$FILE.s3resp" 2>/dev/null || true
    rm -f "$FILE.s3resp"
    exit 1
    ;;
esac
