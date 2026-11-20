#!/usr/bin/env bash
# One-shot deploy: bash deploy.sh <unique-app-name>
set -e
APP=${1:?Usage: bash deploy.sh <unique-app-name>}
RG=rg-campusmate; LOC=centralindia; AI=${APP}-ai

az group create -n $RG -l $LOC --tags project=campusmate env=college
az cognitiveservices account create -n $AI -g $RG -l $LOC --kind CognitiveServices \
  --sku S0 --custom-domain $AI --yes
KEY=$(az cognitiveservices account keys list -n $AI -g $RG --query key1 -o tsv)
EP=$(az cognitiveservices account show -n $AI -g $RG --query properties.endpoint -o tsv)

az webapp up -n $APP -g $RG -l $LOC --runtime "PYTHON:3.11" --sku B1
az webapp config set -n $APP -g $RG --startup-file "gunicorn --bind=0.0.0.0 --timeout 120 app:app"
az webapp config appsettings set -n $APP -g $RG --settings \
  AI_ENDPOINT=$EP AI_KEY=$KEY AI_REGION=$LOC SCM_DO_BUILD_DURING_DEPLOYMENT=true
echo "Live at: https://$APP.azurewebsites.net"
