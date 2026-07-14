targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@minLength(1)
@description('Primary location for all resources. Must support Azure Functions Flex Consumption and the default Microsoft Foundry gpt-5.4 Global Standard deployment.')
@allowed([
  'centralus'
  'eastus'
  'eastus2'
  'northcentralus'
  'southcentralus'
  'westus'
])
@metadata({
  azd: {
    type: 'location'
  }
})
param location string

@description('Microsoft Foundry model deployment name.')
param foundryModel string = 'gpt-5.4'

@description('Microsoft Foundry model name.')
param foundryModelName string = 'gpt-5.4'

@description('Microsoft Foundry model version.')
param foundryModelVersion string = '2026-03-05'

@description('Microsoft Foundry deployment capacity.')
param foundryDeploymentCapacity int = 50

@description('Reasoning effort for supported Foundry reasoning models.')
@allowed([
  'none'
  'low'
  'medium'
  'high'
  'xhigh'
])
param reasoningEffort string = 'medium'

@description('Reasoning summary mode for supported Foundry reasoning models.')
@allowed([
  'auto'
  'concise'
  'detailed'
])
param reasoningSummary string = 'concise'

@description('Object ID of the user/principal running the deployment. Used to (a) grant Storage Queue Data Message Sender so the interactive queue-connector sign-in can enqueue routed decisions, and (b) allow that user to authorize/use the queue connection. Populated by azd from AZURE_PRINCIPAL_ID.')
param principalId string = ''

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }
var functionAppName = '${abbrs.webSitesFunctions}expense-agent-${resourceToken}'
var foundryAccountName = 'cog-${resourceToken}'
var foundryProjectName = '${foundryAccountName}-proj'
var deploymentStorageContainerName = 'app-package-${take(functionAppName, 32)}-${take(toLower(uniqueString(functionAppName, resourceToken)), 7)}'
var connectorGatewayName = 'cg-${resourceToken}'

var inputQueueName = 'expense-requests'
var outputQueueNames = [
  'expense-approved'
  'expense-review'
  'expense-flagged'
]
var allQueueNames = union([inputQueueName], outputQueueNames)

// Resource Group
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

// User Assigned Managed Identity
module apiUserAssignedIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: 'apiUserAssignedIdentity'
  scope: rg
  params: {
    location: location
    tags: tags
    name: '${abbrs.managedIdentityUserAssignedIdentities}expense-agent-${resourceToken}'
  }
}

// Microsoft Foundry
module foundry './app/foundry.bicep' = {
  name: 'foundry'
  scope: rg
  params: {
    accountName: foundryAccountName
    projectName: foundryProjectName
    location: location
    tags: tags
    modelDeploymentName: foundryModel
    modelName: foundryModelName
    modelVersion: foundryModelVersion
    deploymentCapacity: foundryDeploymentCapacity
    managedIdentityPrincipalId: apiUserAssignedIdentity.outputs.principalId
  }
}

// App Service Plan (Flex Consumption)
module appServicePlan 'br/public:avm/res/web/serverfarm:0.1.1' = {
  name: 'appserviceplan'
  scope: rg
  params: {
    name: '${abbrs.webServerFarms}${resourceToken}'
    sku: {
      name: 'FC1'
      tier: 'FlexConsumption'
    }
    reserved: true
    location: location
    tags: tags
  }
}

// Function App
module api './app/api.bicep' = {
  name: 'api'
  scope: rg
  params: {
    name: functionAppName
    location: location
    tags: tags
    applicationInsightsName: monitoring.outputs.name
    appServicePlanId: appServicePlan.outputs.resourceId
    runtimeName: 'python'
    runtimeVersion: '3.13'
    storageAccountName: storage.outputs.name
    deploymentStorageContainerName: deploymentStorageContainerName
    identityId: apiUserAssignedIdentity.outputs.resourceId
    identityClientId: apiUserAssignedIdentity.outputs.clientId
    appSettings: {
      AZURE_FUNCTIONS_AGENTS_PROVIDER: 'foundry'
      FOUNDRY_PROJECT_ENDPOINT: foundry.outputs.projectEndpoint
      FOUNDRY_MODEL: foundry.outputs.modelDeploymentName
      AZURE_FUNCTIONS_AGENTS_REASONING_EFFORT: reasoningEffort
      AZURE_FUNCTIONS_AGENTS_REASONING_SUMMARY: reasoningSummary
      AZURE_CLIENT_ID: apiUserAssignedIdentity.outputs.clientId
      OUTPUT_STORAGE_ACCOUNT: storage.outputs.name
      // Queue routing connector (built-in MCP tool azurequeues_PutMessage_V2). The MCP
      // server URL is produced by the connector gateway; the agent authenticates to it
      // with the function's managed identity (QUEUE_MCP_CLIENT_ID). The agent passes the
      // storage account name (OUTPUT_STORAGE_ACCOUNT) + destination queue to the tool.
      QUEUE_MCP_SERVER_URL: connectorGateway.outputs.mcpServerUrl
      QUEUE_MCP_CLIENT_ID: apiUserAssignedIdentity.outputs.clientId
      ENABLE_MULTIPLATFORM_BUILD: 'true'
      PYTHON_ENABLE_INIT_INDEXING: '1'
    }
  }
}

// Storage Account
module storage 'br/public:avm/res/storage/storage-account:0.8.3' = {
  name: 'storage'
  scope: rg
  params: {
    name: '${abbrs.storageStorageAccounts}${resourceToken}'
    allowBlobPublicAccess: false
    // Shared-key (local auth) is disabled to satisfy the enforced org policy
    // "Azure Storage Policy to disable local auth" (Deny). The Function app uses
    // managed identity for AzureWebJobsStorage + deployment storage, so no
    // shared-key access is needed.
    allowSharedKeyAccess: false
    dnsEndpointType: 'Standard'
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
    blobServices: {
      containers: [
        { name: deploymentStorageContainerName }
      ]
    }
    minimumTlsVersion: 'TLS1_2'
    location: location
    tags: tags
  }
}

// Input + per-outcome output queues
module storageQueues './app/storage-queues.bicep' = {
  name: 'storageQueues'
  scope: rg
  params: {
    storageAccountName: storage.outputs.name
    queueNames: allQueueNames
  }
}

// RBAC — storage data roles + app insights metrics publisher for the function identity
module rbac './app/rbac.bicep' = {
  name: 'rbacAssignments'
  scope: rg
  params: {
    storageAccountName: storage.outputs.name
    appInsightsName: monitoring.outputs.name
    managedIdentityPrincipalId: apiUserAssignedIdentity.outputs.principalId
    // The interactive queue connector enqueues as the authorizing user, so that user
    // needs Storage Queue Data Message Sender to route decisions.
    authorizerPrincipalId: principalId
  }
}

// Azure Queues routing connector exposed to the agent as a built-in MCP tool.
module connectorGateway './app/connector-gateway.bicep' = {
  name: 'connectorGateway'
  scope: rg
  params: {
    connectorGatewayName: connectorGatewayName
    location: location
    tags: tags
    functionPrincipalId: apiUserAssignedIdentity.outputs.principalId
    authorizerPrincipalId: principalId
  }
}

// Log Analytics
module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.7.0' = {
  name: '${uniqueString(deployment().name, location)}-loganalytics'
  scope: rg
  params: {
    name: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    location: location
    tags: tags
    dataRetention: 30
  }
}

// Application Insights
module monitoring 'br/public:avm/res/insights/component:0.4.1' = {
  name: '${uniqueString(deployment().name, location)}-appinsights'
  scope: rg
  params: {
    name: '${abbrs.insightsComponents}${resourceToken}'
    location: location
    tags: tags
    workspaceResourceId: logAnalytics.outputs.resourceId
    disableLocalAuth: true
  }
}

// Outputs
output AZURE_LOCATION string = location
output AZURE_FUNCTION_NAME string = api.outputs.SERVICE_API_NAME
output FOUNDRY_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output FOUNDRY_MODEL string = foundry.outputs.modelDeploymentName
output OUTPUT_STORAGE_ACCOUNT string = storage.outputs.name
output INPUT_QUEUE_NAME string = inputQueueName
output QUEUE_MCP_SERVER_URL string = connectorGateway.outputs.mcpServerUrl
output ROUTE_QUEUE_CONNECTION_NAME string = connectorGateway.outputs.connectionName
output CONNECTOR_GATEWAY_NAME string = connectorGateway.outputs.gatewayName
