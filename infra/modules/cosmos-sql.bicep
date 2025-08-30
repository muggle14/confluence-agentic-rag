@description('Location for Cosmos DB')
param location string = resourceGroup().location

@description('Cosmos DB account name')
param cosmosAccountName string

@description('Cosmos DB database name')
param databaseName string = 'rag-sessions'

@description('Cosmos DB container name')
param containerName string = 'sessions'

@description('Throughput for the container (RU/s)')
param throughput int = 400

@description('Tags for resource')
param tags object = {
  CostTier: 'Dev'
  Purpose: 'SessionStorage'
  API: 'SQL'
}

// ===== Cosmos DB (SQL API) for Session Storage =====
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  tags: tags
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
      maxStalenessPrefix: 100
      maxIntervalInSeconds: 5
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'  // Use serverless for cost optimization
      }
    ]
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    publicNetworkAccess: 'Enabled'
    enableFreeTier: false  // Set to true if eligible for free tier
  }
}

// Create SQL Database
resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmos
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Create Sessions Container with partition key
resource sessionContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDb
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: ['/session_id']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
        compositeIndexes: [
          [
            {
              path: '/user_id'
              order: 'ascending'
            }
            {
              path: '/updated_at'
              order: 'descending'
            }
          ]
        ]
      }
      uniqueKeyPolicy: {
        uniqueKeys: []
      }
      conflictResolutionPolicy: {
        mode: 'LastWriterWins'
        conflictResolutionPath: '/_ts'
      }
    }
    // Don't specify throughput for serverless accounts
  }
}

// ===== Outputs =====
output cosmosAccountName string = cosmos.name
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output cosmosKey string = cosmos.listKeys().primaryMasterKey
output cosmosDatabaseName string = cosmosDb.name
output cosmosContainerName string = sessionContainer.name
output connectionString string = 'AccountEndpoint=${cosmos.properties.documentEndpoint};AccountKey=${cosmos.listKeys().primaryMasterKey};'