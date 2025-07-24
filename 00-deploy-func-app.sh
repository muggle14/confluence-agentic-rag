#!/usr/bin/env bash
# 00-deploy-func-app.sh  —  Run-from-Package end-to-end

set -euo pipefail

# ──────────────── defaults (edit if you like) ───────────────────────
RG="rg-rag-confluence"          # resource-group of the Function App
APP="func-rag-conf-prem"        # Function App name
SA="stgragconf"                 # storage account that will hold the ZIP
CONTAINER="processed"           # e.g. "$web" or any existing / new container
FUNC_DIR="func-app"             # local folder that contains host.json
ZIP_NAME="funcapp_pkg.zip"      # name of the package file
# ─────────────────────────────────────────────────────────────────────

# ──────────────── helper: RFC-3339 timestamp +365 d ──────────────────
now_plus_1y() {
  if command -v gdate >/dev/null 2>&1; then
    gdate -u -d "+365 days" "+%Y-%m-%dT%H:%MZ"        # GNU coreutils
  else
    date -u -v +365d "+%Y-%m-%dT%H:%MZ"               # BSD/macOS
  fi
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FUNC_APP_DIR="$SCRIPT_DIR/$FUNC_DIR"

# ──────────────── ensure dependencies are installed locally ───────────
echo "📚 Installing dependencies locally for run-from-package..."
(cd "$FUNC_APP_DIR" && \
  pip install -r requirements.txt -t .python_packages/lib/site-packages --quiet)

# ──────────────── package the function app (FIXED STRUCTURE) ──────────
echo "📦 Zipping '${FUNC_DIR}' → ${ZIP_NAME} (from app directory root)"
rm -f "$SCRIPT_DIR/$ZIP_NAME"

# CRITICAL FIX: cd into func-app so host.json is at ZIP root
(cd "$FUNC_APP_DIR" && \
zip -rq "$SCRIPT_DIR/${ZIP_NAME}" . \
    -x '*.git*' '__pycache__/*' '.venv/*' 'env/*' \
       'local.settings.json' 'tests/*' '*.pyc' \
       '.DS_Store' '.pytest_cache/*')

echo "✅ Package created with host.json at root level"

# ──────────────── make sure the blob container exists ───────────────
echo "🪣 Ensuring container '${CONTAINER}' exists in storage account '${SA}'"
az storage container create \
  --account-name "$SA" \
  --name "$CONTAINER" \
  --auth-mode login >/dev/null 2>&1 || echo "Container already exists or created"

# ──────────────── upload the ZIP package ─────────────────────────────
echo "📤 Uploading package to 'https://${SA}.blob.core.windows.net/${CONTAINER}/${ZIP_NAME}'"
az storage blob upload \
  --account-name "$SA" \
  --container-name "$CONTAINER" \
  --name "$ZIP_NAME" \
  --file "$SCRIPT_DIR/$ZIP_NAME" \
  --overwrite \
  --auth-mode login >/dev/null

# ──────────────── build a 1-year account-key SAS ─────────────────────
EXPIRY=$(now_plus_1y)
echo "🔑 Generating read-only SAS (expires $EXPIRY)"

ACC_KEY=$(az storage account keys list \
            --account-name "$SA" \
            --resource-group "$RG" \
            --query "[0].value" -o tsv)

SAS=$(az storage blob generate-sas \
        --account-name "$SA" \
        --account-key "$ACC_KEY" \
        --container-name "$CONTAINER" \
        --name "$ZIP_NAME" \
        --permissions r \
        --expiry "$EXPIRY" -o tsv)

PKG_URL="https://${SA}.blob.core.windows.net/${CONTAINER}/${ZIP_NAME}?${SAS}"
echo "📄 Package URL created."

# ──────────────── set proper Function App settings (FIXED) ───────────
echo "⚙️  Setting proper Function App configuration on '${APP}'"

# First, ensure core runtime settings are correct
az functionapp config appsettings set \
  -g "$RG" -n "$APP" \
  --settings \
    FUNCTIONS_WORKER_RUNTIME="python" \
    FUNCTIONS_EXTENSION_VERSION="~4" \
    PYTHON_VERSION="3.11" \
  >/dev/null

# CRITICAL FIX: Set run-from-package and REMOVE conflicting build settings
echo "🔧 Configuring run-from-package (removing conflicting build settings)"
az functionapp config appsettings set \
  -g "$RG" -n "$APP" \
  --settings WEBSITE_RUN_FROM_PACKAGE="$PKG_URL" \
  >/dev/null

# Remove conflicting settings that interfere with run-from-package
az functionapp config appsettings delete \
  -g "$RG" -n "$APP" \
  --setting-names SCM_DO_BUILD_DURING_DEPLOYMENT ENABLE_ORYX_BUILD \
  >/dev/null 2>&1 || echo "Build settings already removed or didn't exist"

echo "♻️  Restarting Function App to pick up the new package"
az functionapp restart -g "$RG" -n "$APP" >/dev/null

echo -e "\n✅ Deployment finished!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 VERIFICATION STEPS:"
echo "   1. Stream logs: func azure functionapp logstream $APP -g $RG"
echo "   2. Look for: 'Host initialized / Job host started'"
echo "   3. Check logs: /home/LogFiles/Application/Functions/Host/<timestamp>.log"
echo "   4. Test endpoint: curl -X POST https://${APP}.azurewebsites.net/api/graph_enrichment_skill"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Clean up local zip file
rm -f "$SCRIPT_DIR/$ZIP_NAME"
echo "🧹 Cleaned up local ZIP file"