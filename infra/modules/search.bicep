@description('Location for Azure AI Search')
param location string = 'centralus'

@description('Azure AI Search service name')
param searchServiceName string

// ===== Azure AI Search – Standard tier =====
resource search 'Microsoft.Search/searchServices@2020-08-01' = {
  name: searchServiceName
  location: location
  sku: {
    name: 'standard' // Standard tier for vector index
  }
  properties: {
    hostingMode: 'default'
    replicaCount: 1
    partitionCount: 1
    publicNetworkAccess: 'enabled'
  }
}

// ===== Outputs =====
output searchServiceName string = search.name
output searchServiceKey string = search.listAdminKeys().primaryKey
output searchServiceEndpoint string = 'https://${search.name}.search.windows.net' 