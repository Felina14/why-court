#!/usr/bin/env bash
# Deploy Why Court serverless (Lambda + function URL + S3) with CloudFormation. No Docker needed.
#   WHYCOURT_GUARDRAIL_ID=... ./deploy/deploy.sh            deploy or update
#   aws cloudformation delete-stack --stack-name why-court   remove it (empty the data and UI buckets first)
set -euo pipefail
cd "$(dirname "$0")/.."
STACK=${STACK:-why-court}
REGION=${AWS_REGION:-us-east-1}
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
CODE_BUCKET=${CODE_BUCKET:-why-court-code-$ACCOUNT-$REGION}
BUILD=${BUILD:-build/lambda}
: "${WHYCOURT_GUARDRAIL_ID:?set WHYCOURT_GUARDRAIL_ID}"

echo "== packaging (Linux arm64, Python 3.12)"
rm -rf "$BUILD" && mkdir -p "$BUILD/pkg"
python3 -m pip install -q --target "$BUILD/pkg" --platform manylinux2014_aarch64 --implementation cp \
  --python-version 3.12 --only-binary=:all: --upgrade \
  "strands-agents[a2a]==1.63.0" "boto3>=1.35" "pydantic>=2.7" fastapi python-multipart pypdf mangum
cp -R app whycourt web books "$BUILD/pkg/"
find "$BUILD/pkg" -name __pycache__ -type d -prune -exec rm -rf {} +
(cd "$BUILD/pkg" && zip -qr9 ../court.zip .)
KEY="court-$(shasum -a 256 "$BUILD/court.zip" | cut -c1-16).zip"

echo "== uploading $KEY"
aws s3api head-bucket --bucket "$CODE_BUCKET" 2>/dev/null || {
  if [ "$REGION" = us-east-1 ]; then aws s3api create-bucket --bucket "$CODE_BUCKET" --region "$REGION" >/dev/null
  else aws s3api create-bucket --bucket "$CODE_BUCKET" --region "$REGION" \
         --create-bucket-configuration LocationConstraint="$REGION" >/dev/null; fi
  aws s3api put-public-access-block --bucket "$CODE_BUCKET" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true; }
aws s3 cp "$BUILD/court.zip" "s3://$CODE_BUCKET/$KEY" --region "$REGION" >/dev/null

echo "== deploying stack $STACK"
aws cloudformation deploy --region "$REGION" --stack-name "$STACK" --template-file deploy/template.yaml \
  --capabilities CAPABILITY_IAM --no-fail-on-empty-changeset --parameter-overrides \
  CodeBucket="$CODE_BUCKET" CodeKey="$KEY" GuardrailId="$WHYCOURT_GUARDRAIL_ID" \
  GuardrailVersion="${WHYCOURT_GUARDRAIL_VERSION:-1}" RehearDays="${WHYCOURT_REHEAR_DAYS:-7}"
out() { aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
API=$(out Url); API=${API%/}; UI=$(out UiBucket)

echo "== publishing the UI to S3 + CloudFront"
rm -rf "$BUILD/ui" && mkdir -p "$BUILD/ui/static" && cp -R web/. "$BUILD/ui/static/"
mv "$BUILD/ui/static/index.html" "$BUILD/ui/static/teacher.html" "$BUILD/ui/"
printf 'window.WHYCOURT_API = "%s";\n' "$API" > "$BUILD/ui/static/config.js"
printf '%s' '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">⚖️</text></svg>' \
  > "$BUILD/ui/favicon.ico"
aws s3 sync "$BUILD/ui/static" "s3://$UI/static" --delete --region "$REGION" --exclude config.js \
  --cache-control "public, max-age=86400" >/dev/null
aws s3 cp "$BUILD/ui/static/config.js" "s3://$UI/static/config.js" --cache-control "no-cache" >/dev/null
for f in index.html teacher.html; do
  aws s3 cp "$BUILD/ui/$f" "s3://$UI/$f" --content-type "text/html; charset=utf-8" --cache-control "no-cache" >/dev/null
done
aws s3 cp "$BUILD/ui/favicon.ico" "s3://$UI/favicon.ico" --content-type image/svg+xml >/dev/null
aws cloudfront create-invalidation --distribution-id "$(out SiteId)" --paths "/*" >/dev/null
echo "UI:  $(out Site)"
echo "API: $API"
