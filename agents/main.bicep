
// main.bicep
// Complete Azure infrastructure for Confluence Q&A System with AutoGen

@description('Location for all resources')
param location string = resourceGroup().location

@description('Environment name')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('Confluence organization name')
param confluenceOrg string

@secure()
@description('Confluence API token')
param confluenceToken string

// Naming convention
var prefix = 'confluenceqa'
var uniqueSuffix = uniqueString(resourceGroup().id)
var namingConvention = '${prefix}-${environment}-${uniqueSuffix}'

// ===== Storage Account =====
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: toLower('${prefix}${environment}${uniqueSuffix}')
  location: location
  sku: {
    name: environment == 'prod' ? 'Standard_ZRS' : 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    encryption: {
      services: {
        blob: {
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }

  resource blobService 'blobServices' = {
    name: 'default'
    
    resource rawContainer 'containers' = {
      name: 'raw-confluence'
      properties: {
        publicAccess: 'None'
      }
    }
    
    resource processedContainer 'containers' = {
      name: 'processed-confluence'
      properties: {
        publicAccess: 'None'
      }
    }
  }
}

// ===== Cosmos DB Account (Serverless) =====
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: '${namingConvention}-cosmos'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Serverless'
    capabilities: [
      {
        name: 'EnableGremlin'
      }
      {
        name: 'EnableServerless'
      }
    ]
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    backupPolicy: {
      type: 'Continuous'
    }
  }
}

// ===== Cosmos DB SQL Database =====
resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: 'confluence'
  properties: {
    resource: {
      id: 'confluence'
    }
  }
}

// ===== Cosmos DB Containers =====
resource thinkingStepsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: cosmosDatabase
  name: 'thinking_steps'
  properties: {
    resource: {
      id: 'thinking_steps'
      partitionKey: {
        paths: ['/conversationId']
        kind: 'Hash'
      }
      indexingPolicy: {
        automatic: true
        indexingMode: 'consistent'
      }
    }
  }
}

resource conversationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: cosmosDatabase
  name: 'conversations'
  properties: {
    resource: {
      id: 'conversations'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
      }
      defaultTtl: 2592000 // 30 days
    }
  }
}

resource linearTicketsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: cosmosDatabase
  name: 'linear_tickets'
  properties: {
    resource: {
      id: 'linear_tickets'
      partitionKey: {
        paths: ['/linearIssueId']
        kind: 'Hash'
      }
    }
  }
}

// ===== Cosmos DB Gremlin Database =====
resource gremlinDatabase 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: 'confluence'
  properties: {
    resource: {
      id: 'confluence'
    }
  }
}

resource gremlinGraph 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases/graphs@2023-11-15' = {
  parent: gremlinDatabase
  name: 'pages'
  properties: {
    resource: {
      id: 'pages'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
      }
    }
  }
}

// ===== Azure Cognitive Search =====
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: '${namingConvention}-search'
  location: location
  sku: {
    name: environment == 'prod' ? 'standard' : 'basic'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    publicNetworkAccess: 'Enabled'
    semanticSearch: environment == 'prod' ? 'standard' : 'free'
  }
}

// ===== Azure OpenAI =====
resource cognitiveAccount 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: '${namingConvention}-openai'
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'OpenAI'
  properties: {
    customSubDomainName: '${namingConvention}-openai'
    publicNetworkAccess: 'Enabled'
  }
}

// ===== OpenAI Deployments =====
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: cognitiveAccount
  name: 'text-embedding-3-large'
  sku: {
    name: 'Standard'
    capacity: environment == 'prod' ? 120 : 20
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: '1'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.Default'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: cognitiveAccount
  name: 'gpt-4o'
  sku: {
    name: 'Standard'
    capacity: environment == 'prod' ? 80 : 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-05-13'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.Default'
  }
  dependsOn: [
    embeddingDeployment // Deploy one at a time
  ]
}

// ===== Application Insights =====
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namingConvention}-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    RetentionInDays: environment == 'prod' ? 90 : 30
    IngestionMode: 'ApplicationInsights'
  }
}

// ===== Container Registry =====
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: toLower('${prefix}${environment}${uniqueSuffix}')
  location: location
  sku: {
    name: environment == 'prod' ? 'Premium' : 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// ===== App Service Plan =====
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${namingConvention}-plan'
  location: location
  sku: {
    name: environment == 'prod' ? 'P1v3' : 'B1'
    tier: environment == 'prod' ? 'PremiumV3' : 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// ===== Web App for API =====
resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '${namingConvention}-api'
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOCKER|${containerRegistry.properties.loginServer}/confluence-qa-api:latest'
      alwaysOn: environment == 'prod'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${containerRegistry.properties.loginServer}'
        }
        {
          name: 'DOCKER_ENABLE_CI'
          value: 'true'
        }
        // Azure Configuration
        {
          name: 'AZ_SUBSCRIPTION_ID'
          value: subscription().subscriptionId
        }
        {
          name: 'AZ_RESOURCE_GROUP'
          value: resourceGroup().name
        }
        {
          name: 'AZ_LOCATION'
          value: location
        }
        // Cosmos DB
        {
          name: 'COSMOS_ACCOUNT'
          value: cosmosAccount.name
        }
        {
          name: 'COSMOS_KEY'
          value: cosmosAccount.listKeys().primaryMasterKey
        }
        {
          name: 'COSMOS_DB'
          value: 'confluence'
        }
        {
          name: 'COSMOS_GRAPH'
          value: 'pages'
        }
        // Storage
        {
          name: 'STORAGE_ACCOUNT'
          value: storageAccount.name
        }
        {
          name: 'STORAGE_KEY'
          value: storageAccount.listKeys().keys[0].value
        }
        // Search
        {
          name: 'SEARCH_SERVICE'
          value: searchService.name
        }
        {
          name: 'SEARCH_INDEX'
          value: 'confluence-idx'
        }
        {
          name: 'SEARCH_ENDPOINT'
          value: 'https://${searchService.name}.search.windows.net'
        }
        {
          name: 'SEARCH_KEY'
          value: searchService.listAdminKeys().primaryKey
        }
        // OpenAI
        {
          name: 'AOAI_RESOURCE'
          value: cognitiveAccount.name
        }
        {
          name: 'AOAI_ENDPOINT'
          value: cognitiveAccount.properties.endpoint
        }
        {
          name: 'AOAI_KEY'
          value: cognitiveAccount.listKeys().key1
        }
        {
          name: 'AOAI_EMBED_DEPLOY'
          value: embeddingDeployment.name
        }
        {
          name: 'AOAI_CHAT_DEPLOY'
          value: chatDeployment.name
        }
        // Confluence
        {
          name: 'CONFLUENCE_ORG'
          value: confluenceOrg
        }
        {
          name: 'CONFLUENCE_BASE'
          value: 'https://${confluenceOrg}.atlassian.net/wiki/rest/api'
        }
        {
          name: 'CONFLUENCE_TOKEN'
          value: confluenceToken
        }
        // App Insights
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        // System Config
        {
          name: 'MAX_HOPS'
          value: '3'
        }
        {
          name: 'CONFIDENCE_THRESHOLD'
          value: '0.7'
        }
        {
          name: 'EDGE_TYPES'
          value: 'ParentOf,LinksTo,References'
        }
      ]
    }
  }
}

// ===== Role Assignments =====
// Storage Blob Data Contributor
resource storageBlobDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, webApp.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services User
resource cognitiveServicesUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: cognitiveAccount
  name: guid(cognitiveAccount.id, webApp.id, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor
resource searchIndexDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, webApp.id, '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7')
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ===== Outputs =====
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
output cosmosAccountEndpoint string = cosmosAccount.properties.documentEndpoint