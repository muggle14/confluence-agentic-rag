@description('Location for Function App')
param location string = resourceGroup().location

@description('Function App name')
param functionAppName string

@description('Storage account name for Function App')
param storageAccountName string

@description('Storage account key')
@secure()
param storageAccountKey string

@description('Cosmos DB account name')
param cosmosAccountName string

@description('Cosmos DB key')
@secure()
param cosmosKey string

@description('Search service name')
param searchServiceName string

@description('Search service key')
@secure()
param searchKey string

@description('Confluence configuration')
param confluenceBase string
@secure()
param confluenceToken string
param confluenceEmail string

@description('Ingestion settings')
param deltadays string = '1'
param confluenceSpaceKeys string = ''

// ===== App Service Plan for Function App =====
resource functionPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: '${functionAppName}-plan'
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true // Linux
  }
}

// ===== Function App =====
resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: functionPlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        // Azure Functions runtime settings
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccountKey};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccountKey};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: '${functionAppName}-content'
        }
        // Storage configuration
        {
          name: 'STORAGE_CONN'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccountKey};EndpointSuffix=core.windows.net'
        }
        {
          name: 'STORAGE_ACCOUNT'
          value: storageAccountName
        }
        {
          name: 'STORAGE_KEY'
          value: storageAccountKey
        }
        // Cosmos DB configuration
        {
          name: 'COSMOS_ACCOUNT'
          value: cosmosAccountName
        }
        {
          name: 'COSMOS_KEY'
          value: cosmosKey
        }
        {
          name: 'COSMOS_DB'
          value: 'confluence'
        }
        {
          name: 'COSMOS_GRAPH'
          value: 'pages'
        }
        // Search configuration
        {
          name: 'SEARCH_ENDPOINT'
          value: 'https://${searchServiceName}.search.windows.net'
        }
        {
          name: 'SEARCH_SERVICE'
          value: searchServiceName
        }
        {
          name: 'SEARCH_KEY'
          value: searchKey
        }
        {
          name: 'SEARCH_INDEX'
          value: 'confluence-idx'
        }
        // Confluence API configuration
        {
          name: 'CONFLUENCE_BASE'
          value: confluenceBase
        }
        {
          name: 'CONFLUENCE_TOKEN'
          value: confluenceToken
        }
        {
          name: 'CONFLUENCE_EMAIL'
          value: confluenceEmail
        }
        // Ingestion settings
        {
          name: 'DELTA_DAYS'
          value: deltadays
        }
        {
          name: 'CONFLUENCE_SPACE_KEYS'
          value: confluenceSpaceKeys
        }
        // Application Insights
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: applicationInsights.properties.InstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: applicationInsights.properties.ConnectionString
        }
      ]
    }
  }
}

// ===== Application Insights =====
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${functionAppName}-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Request_Source: 'rest'
  }
}

// ===== Storage containers for ingestion =====
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: storageAccountName
}

// Ensure metadata container exists
resource metadataContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: '${storageAccount.name}/default/metadata'
  properties: {
    publicAccess: 'None'
  }
}

// ===== Outputs =====
output functionAppName string = functionApp.name
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output applicationInsightsName string = applicationInsights.name
output applicationInsightsInstrumentationKey string = applicationInsights.properties.InstrumentationKey 