@description('Location for all resources')
param location string = resourceGroup().location

@description('Storage account name')
param storageAccountName string = 'stgragconf'

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
  }
}

output storageAccountName string = storage.name 