@description('Location for Azure OpenAI')
param location string = resourceGroup().location

@description('Azure OpenAI service name')
param aoaiName string

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

// ===== Outputs =====
output aoaiName string = aoai.name
output aoaiEndpoint string = aoai.properties.endpoint
output aoaiKey string = aoai.listKeys().key1 