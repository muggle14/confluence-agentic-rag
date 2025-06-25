@description('Location for Cosmos DB')
param location string = resourceGroup().location

@description('Cosmos DB account name')
param cosmosAccountName string

@description('Cosmos DB database name')
param databaseName string = 'confluence'

@description('Cosmos DB graph name')
param graphName string = 'pages'

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
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Create Cosmos DB graph container
resource cosmosGraph 'Microsoft.DocumentDB/databaseAccounts/gremlinDatabases/graphs@2023-04-15' = {
  parent: cosmosDb
  name: graphName
  properties: {
    resource: {
      id: graphName
      partitionKey: {
        paths: ['/pageId']
        kind: 'Hash'
      }
    }
  }
}

// ===== Outputs =====
output cosmosAccountName string = cosmos.name
output cosmosKey string = cosmos.listKeys().primaryMasterKey
output cosmosEndpoint string = cosmos.properties.documentEndpoint 