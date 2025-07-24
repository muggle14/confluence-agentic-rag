# Confluence Q&A System - Infrastructure Setup Guide

## Table of Contents
- [0. Prerequisites](#0-prerequisites-envexample)
- [1. Resource Provisioning (Bicep)](#1-resource-provisioning-bicep--cost-optimised)
- [2. Add-on: Automate Microsoft Graph App Registration](#2-add-on-automate-microsoft-graph-app-registration-optional)

---

## 0. Prerequisites (.env.example)

> 🏷️ **Cost-savvy tips for a personal dev sub**
> • Choose the lowest-cost SKUs (`F2` App Service, `Serverless` Cosmos, Search `basic`) unless performance tests say otherwise.
> • Re-use an existing **Resource Group**, **Storage V2 account**, or **Application Insights** instance if one is already in your dev sub – just point the Bicep parameters at the existing names.

```bash
# Azure Subscription details
AZ_SUBSCRIPTION_ID=e4ec0439-fe05-4c6e-bdc1-2d454fe9f504
AZ_RESOURCE_GROUP=rg-rag-confluence
AZ_LOCATION=WestUS2

# Cosmos DB
COSMOS_ACCOUNT=cosmos-rag-conf
COSMOS_KEY=<autofill by script>
COSMOS_DB=confluence
COSMOS_GRAPH=pages

# Storage
STORAGE_ACCOUNT=stgragconf

# Azure AI Search
SEARCH_SERVICE=srch-rag-conf
SEARCH_INDEX=confluence-idx

# Azure OpenAI
AOAI_RESOURCE=aoai-rag-conf
AOAI_EMBED_DEPLOY=text-embedding-3-large
# AOAI_CHAT_DEPLOY=gpt-4o

# Function App
FUNC_APP=func-rag-conf

# Confluence
CONFLUENCE_BASE=https://hchaturvedi14.atlassian.net/wiki/rest/api
CONFLUENCE_TOKEN=ATATT3xFfGF0S2zwzdh90pA77o3ciZ8JltwNiMbX3zuGJe7xkx0-OXtafNBkZ2T5HQ0lPH_R4XGGnlruLOD2H-inzvFP3_ApuYvmQMLXYwuE4exIIFbrBU_G_WJdcYUXqAGqJpNgGtuEqkyu7twK7O2AelvmTcO4jD90WAWzTGkGHp9kGNGniqM=62EEAF74
```

---

## 1. Resource Provisioning (Bicep – **cost-optimised**)

### 1.1 `main.bicep` (single-file quick start)

Below is a **compressed, cheapest-tier** template that stands up every service in one shot. Adjust parameters to point at pre-existing resources if you already have them (→ 💸 **zero cost** for re-use).

```bicep
param location string = resourceGroup().location
param cosmosAccountName string
param storageAccountName string
param searchServiceName string
param aoaiName string
param functionAppName string

resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    capabilities: [
      {
        name: 'EnableGremlin'
      }
    ]
    databaseAccountOfferType: 'Standard'
  }
}

resource search 'Microsoft.Search/searchServices@2023-10-01-preview' = {
  name: searchServiceName
  location: location
  sku: {
    name: 'standard'
  }
  properties: {
    hostingMode: 'default'
    replicaCount: 1
    partitionCount: 1
  }
}

resource aoai 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: aoaiName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'OpenAI'
  properties: {
    apiProperties: {
      kind: 'OpenAI'
    }
  }
}

resource plan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: '${functionAppName}-plan'
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
}

resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: plan.id
    siteConfig: {
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
      ]
    }
  }
  dependsOn: [plan]
}
```

### 1.2 Deploy via AZ CLI (with reuse flags)

If you already have a dev storage account or App Insights resource, pass their names to reuse them and **skip new cost**.

```bash
az deployment group create \
  --resource-group $AZ_RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters \
    location=$AZ_LOCATION \
    existingStorage=$EXISTING_STORAGE_ACCOUNT   # optional reuse
```

```bash
az deployment group create \
  --resource-group $AZ_RESOURCE_GROUP \
  --template-file main.bicep \
  --parameters \
    cosmosAccountName=$COSMOS_ACCOUNT \
    storageAccountName=$STORAGE_ACCOUNT \
    searchServiceName=$SEARCH_SERVICE \
    aoaiName=$AOAI_RESOURCE \
    functionAppName=$FUNC_APP
```

---

## 2. Add-on: Automate Microsoft Graph App Registration (optional)

Azure Bicep does not natively expose Entra ID app-registration resources, but you can embed a Deployment Script that calls Microsoft Graph to create the registration, add delegated scopes, and generate a client secret – all inside the same deployment.

### 2.1 `graph-app.bicep`

```bicep
param appDisplayName string
param redirectUris array = ['http://localhost:3000']

resource ds 'Microsoft.Resources/deploymentScripts@2020-10-01' = {
  name: 'graphAppRegistration'
  location: resourceGroup().location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${resourceGroup().id}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/graphDSId': {}
    }
  }
  properties: {
    azCliVersion: '2.57.0'
    timeout: 'PT15M'
    cleanupPreference: 'OnSuccess'
    environmentVariables: [
      { name: 'APP_NAME', value: appDisplayName },
      { name: 'REDIRECT_URIS', value: string(redirectUris) }
    ]
    scriptContent: '''
      #!/bin/bash
      set -e
      appJson=$(az rest --resource "https://graph.microsoft.com/" \
        --method POST \
        --uri "/v1.0/applications" \
        --body "{\"displayName\":\"$APP_NAME\",\"signInAudience\":\"AzureADandPersonalMicrosoftAccount\"}")
      appId=$(echo $appJson | jq -r '.appId')
      objId=$(echo $appJson | jq -r '.id')

      # Redirect URI
      az rest --resource "https://graph.microsoft.com/" --method PATCH \
        --uri "/v1.0/applications/$objId" \
        --body "{\"web\":{\"redirectUris\":$REDIRECT_URIS}}"

      # Client secret
      secretJson=$(az rest --resource "https://graph.microsoft.com/" \
        --method POST \
        --uri "/v1.0/applications/$objId/addPassword" \
        --body '{"passwordCredential":{"displayName":"dev-secret"}}')
      secret=$(echo $secretJson | jq -r '.secretText')

      echo "APPLICATION_ID=$appId" >> $AZ_SCRIPTS_OUTPUT_PATH
      echo "CLIENT_SECRET=$secret" >> $AZ_SCRIPTS_OUTPUT_PATH
    '''
    forceUpdateTag: utcNow()
  }
}

output clientId string = ds.outputs.APPLICATION_ID
output clientSecret string = ds.outputs.CLIENT_SECRET
```

> **Prerequisite**: Grant the managed identity **Application Developer** role once in the tenant.

### 2.2 Wire into main.bicep

```bicep
param createGraphApp bool = false
module graphApp 'graph-app.bicep' = if (createGraphApp) {
  name: 'graphApp'
  params: {
    appDisplayName: 'Graph-Personal-Dev'
  }
}
```

### 2.3 Manual quick-test

```bash
msalinteractive(){
python - <<'PY'
from msal import PublicClientApplication
import os, json
app = PublicClientApplication(os.environ['MS_GRAPH_CLIENT_ID'], authority='https://login.microsoftonline.com/consumers')
print(app.acquire_token_interactive(['User.Read'])['access_token'][:80])
PY
}
```

Run `msalinteractive` after the deployment; token retrieval proves the app works for personal accounts.

---

## 3. Cost Optimization Strategies

### 3.1 Service Tier Recommendations

| Service | Recommended Tier | Cost Impact | When to Upgrade |
|---------|------------------|-------------|-----------------|
| **App Service** | F1 (Free) | $0/month | When you need custom domains or SSL |
| **Cosmos DB** | Serverless | Pay-per-request | When you have consistent high traffic |
| **Azure AI Search** | Free | $0/month | When you need more than 3 indexes |
| **Azure OpenAI** | S0 | Pay-per-token | Only tier available |
| **Function App** | Consumption (Y1) | Pay-per-execution | When you need dedicated hosting |

### 3.2 Resource Reuse Benefits

- **Existing Storage Account**: Save ~$20/month
- **Existing App Insights**: Save ~$5/month
- **Existing Resource Group**: No additional cost
- **Shared VNet**: Reduce networking costs

### 3.3 Monitoring Cost

```bash
# Check current costs
az consumption usage list --billing-period-name 202401

# Set up budget alerts
az monitor action-group create \
  --name "cost-alert" \
  --resource-group $AZ_RESOURCE_GROUP \
  --short-name "cost" \
  --action email admin@yourdomain.com
```

---

## 4. Security Considerations

### 4.1 Network Security

- **Private Endpoints**: Enable for production workloads
- **VNet Integration**: Isolate resources in private networks
- **Firewall Rules**: Restrict access to specific IP ranges

### 4.2 Identity & Access Management

- **Managed Identities**: Use for service-to-service authentication
- **Role-Based Access Control**: Follow principle of least privilege
- **Key Rotation**: Implement regular key rotation policies

### 4.3 Data Protection

- **Encryption at Rest**: Enabled by default on all services
- **Encryption in Transit**: TLS 1.2+ enforced
- **Backup Policies**: Configure appropriate retention periods

---

## 5. Troubleshooting

### 5.1 Common Deployment Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| **Name already exists** | Resource name conflict | Use unique naming convention |
| **Quota exceeded** | Service limits reached | Request quota increase |
| **Authentication failed** | Invalid credentials | Check service principal permissions |
| **Template validation error** | Bicep syntax issue | Validate template before deployment |

### 5.2 Debug Commands

```bash
# Validate Bicep template
az bicep build --file main.bicep

# Check deployment status
az deployment group show \
  --resource-group $AZ_RESOURCE_GROUP \
  --name deployment-name

# View deployment logs
az deployment group list \
  --resource-group $AZ_RESOURCE_GROUP \
  --output table
```

### 5.3 Performance Optimization

- **Resource Location**: Deploy services in the same region
- **Connection Pooling**: Configure appropriate pool sizes
- **Caching**: Implement Redis Cache for frequently accessed data
- **CDN**: Use Azure CDN for static content delivery

---

## 6. Next Steps

1. **Deploy the infrastructure** using the provided Bicep templates
2. **Configure environment variables** in your `.env` file
3. **Test the deployment** with the provided validation scripts
4. **Set up monitoring** and cost alerts
5. **Implement security best practices** for production use

This infrastructure setup provides a cost-effective, scalable foundation for your Confluence Q&A system while maintaining security and performance standards.
