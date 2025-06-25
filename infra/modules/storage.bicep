@description('Location for the storage account')
param location string = resourceGroup().location

@description('Storage account name')
param storageAccountName string

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

// ===== Outputs =====
output storageAccountName string = storage.name
output storageAccountKey string = storage.listKeys().keys[0].value
output storageConnectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=core.windows.net' 