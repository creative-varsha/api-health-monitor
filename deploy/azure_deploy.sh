#!/usr/bin/env bash
# One-shot Azure deployment: Cosmos DB (Mongo API, free tier) + ACR + Container Apps.
# Prereqs: Azure CLI installed, `az login` done. Run from the project root:
#   bash deploy/azure_deploy.sh
set -euo pipefail

RG="rg-health-monitor"
LOCATION="centralindia"
SUFFIX="$RANDOM"
COSMOS="cosmos-healthmon-$SUFFIX"
ACR="acrhealthmon$SUFFIX"
ENV_NAME="cae-health-monitor"
APP="api-health-monitor"
IMAGE="health-monitor:latest"

az extension add --name containerapp --upgrade -y
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.OperationalInsights --wait

echo "==> Resource group"
az group create -n "$RG" -l "$LOCATION" -o none

echo "==> Cosmos DB for MongoDB (free tier: 1000 RU/s + 25 GB)"
az cosmosdb create -n "$COSMOS" -g "$RG" \
  --kind MongoDB --server-version 4.2 \
  --enable-free-tier true \
  --default-consistency-level Session \
  --locations regionName="$LOCATION" failoverPriority=0 isZoneRedundant=False -o none

MONGO_URI=$(az cosmosdb keys list -n "$COSMOS" -g "$RG" --type connection-strings \
  --query "connectionStrings[0].connectionString" -o tsv)

echo "==> Container registry + cloud image build (no local Docker needed)"
az acr create -n "$ACR" -g "$RG" --sku Basic --admin-enabled true -o none
az acr build -r "$ACR" -t "$IMAGE" .

ACR_USER=$(az acr credential show -n "$ACR" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR" --query "passwords[0].value" -o tsv)

echo "==> Container Apps environment + app"
az containerapp env create -n "$ENV_NAME" -g "$RG" -l "$LOCATION" -o none

# min=max=1 replica: the background poller must run once, and must never scale to zero.
az containerapp create -n "$APP" -g "$RG" --environment "$ENV_NAME" \
  --image "$ACR.azurecr.io/$IMAGE" \
  --registry-server "$ACR.azurecr.io" \
  --registry-username "$ACR_USER" --registry-password "$ACR_PASS" \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 1 \
  --cpu 0.25 --memory 0.5Gi \
  --secrets mongo-uri="$MONGO_URI" \
  --env-vars MONGODB_URI=secretref:mongo-uri MONGODB_DB=health_monitor \
             POLL_INTERVAL_SECONDS=300 LOG_LEVEL=INFO -o none

FQDN=$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)

cat <<EOF

Deployed!
  Swagger docs : https://$FQDN/docs
  Health check : https://$FQDN/health

Seed the 4 demo services:
  python scripts/seed.py https://$FQDN

Save these for GitHub Actions secrets / cleanup:
  RESOURCE_GROUP=$RG   ACR_NAME=$ACR   APP_NAME=$APP
Tear everything down later with:  az group delete -n $RG --yes --no-wait
EOF
