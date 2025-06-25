@description('Location for Azure AI Search')
param location string = resourceGroup().location

@description('Azure AI Search service name')
param searchServiceName string

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

// ===== Outputs =====
output searchServiceName string = search.name
output searchServiceKey string = search.listAdminKeys().primaryKey
output searchServiceEndpoint string = 'https://${search.name}.search.windows.net' 