@description('Location for all resources')
param location string = resourceGroup().location

@description('Cosmos DB account name')
param cosmosAccountName string

@description('Storage account name')
param storageAccountName string

@description('Azure AI Search service name')
param searchServiceName string

@description('Azure OpenAI service name')
param aoaiName string

@description('Function App name')
param functionAppName string

@description('Web App name for UI')
param webAppName string = 'rag-ui-conf'

// ===== Storage Account =====
resource storage 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    isHnsEnabled: true // ADLS gen2
  }
}

// Create blob containers
resource rawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: '${storage.name}/default/raw'
  properties: {
    publicAccess: 'None'
  }
}

resource processedContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: '${storage.name}/default/processed'
  properties: {
    publicAccess: 'None'
  }
}

// ===== Cosmos DB (Gremlin) – Serverless =====
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  tags: {
    CostTier: 'Dev'
  }
  properties: {
    capabilities: [
      {
        name: 'EnableGremlin'
      }
    ]
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
  }
}

// Create Cosmos DB database
resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases@2023-04-15' = {
  parent: cosmos
  name: 'confluence'
  properties: {
    resource: {
      id: 'confluence'
    }
  }
}

// Create Cosmos DB graph container
resource cosmosGraph 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases/graphs@2023-04-15' = {
  parent: cosmosDb
  name: 'pages'
  properties: {
    resource: {
      id: 'pages'
      partitionKey: {
        paths: ['/pageId']
        kind: 'Hash'
      }
    }
  }
}

// ===== Azure AI Search – Free tier =====
resource search 'Microsoft.Search/searchServices@2020-08-01' = {
  name: searchServiceName
  location: location
  sku: {
    name: 'free' // Free tier for dev
  }
  properties: {
    hostingMode: 'default'
    replicaCount: 1
    partitionCount: 1
  }
}

// ===== Azure OpenAI – S0 tier =====
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
    customSubDomainName: aoaiName
  }
}

// ===== Function App (Consumption Plan) =====
resource plan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: '${functionAppName}-plan'
  location: location
  sku: {
    name: 'Y1' // Consumption plan
    tier: 'Dynamic'
  }
  properties: {
    reserved: true // Linux
  }
}

resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'STORAGE_CONN'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'COSMOS_ACCOUNT'
          value: cosmos.name
        }
        {
          name: 'COSMOS_KEY'
          value: cosmos.listKeys().primaryMasterKey
        }
        {
          name: 'COSMOS_DB'
          value: 'confluence'
        }
        {
          name: 'COSMOS_GRAPH'
          value: 'pages'
        }
        {
          name: 'SEARCH_ENDPOINT'
          value: 'https://${search.name}.search.windows.net'
        }
        {
          name: 'SEARCH_INDEX'
          value: 'confluence-idx'
        }
        {
          name: 'AOAI_ENDPOINT'
          value: aoai.properties.endpoint
        }
        {
          name: 'AOAI_KEY'
          value: aoai.listKeys().key1
        }
        {
          name: 'AOAI_EMBED_DEPLOY'
          value: 'text-embedding-3-large'
        }
      ]
    }
  }
  dependsOn: [plan]
}

// ===== App Service (React UI) – F1 free tier =====
resource appPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: '${webAppName}-plan'
  location: location
  sku: {
    name: 'F1' // Free tier
    tier: 'Free'
  }
}

resource webApp 'Microsoft.Web/sites@2022-09-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: appPlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'NODE|18-lts'
    }
  }
}

// ===== Outputs =====
output storageAccountName string = storage.name
output storageAccountKey string = storage.listKeys().keys[0].value
output cosmosAccountName string = cosmos.name
output cosmosKey string = cosmos.listKeys().primaryMasterKey
output searchServiceName string = search.name
output searchServiceKey string = search.listAdminKeys().primaryKey
output aoaiEndpoint string = aoai.properties.endpoint
output aoaiKey string = aoai.listKeys().key1
output functionAppName string = functionApp.name
output webAppName string = webApp.name 