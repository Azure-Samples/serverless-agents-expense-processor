// Azure Queues "routing" connector, exposed to the agent as a built-in MCP tool.
//
// The agent routes each decision by calling the built-in MCP tool
// `azurequeues_PutMessage_V2` (see src/mcp.json + src/expense_processor.agent.md).
// That tool is served by the connector gateway below:
//
//   connectorGateways/{gateway}                      - the shared gateway (system-assigned MI)
//     /connections/{queue-route}                     - an Azure Queues connection (interactive OAuth)
//       /accessPolicies/{principal}                  - who may invoke the connection via the gateway
//     /mcpserverconfigs/{Azure-Queues-put-message}   - projects PutMessage_V2 as an MCP tool
//
// Authentication: the Azure Queues connection uses `tokenBasedAuth`
// ("Microsoft Entra ID Integrated") — a one-time interactive sign-in at
// https://connectors.azure.com after deployment. The connector then enqueues
// messages as the authorizing user, so that user needs the *Storage Queue Data
// Message Sender* role on the storage account (granted in rbac.bicep for
// `authorizerPrincipalId`).
//
// Managed-identity auth for the connection is NOT used: under the org policy
// `allowSharedKeyAccess: false`, the connector-gateway preview's managed-identity
// path returns 401 (it falls back to shared key). Interactive OAuth is the only
// key-free connection auth that works here.

@description('Name of the connector gateway (shared across connectors).')
param connectorGatewayName string

@description('Location for the gateway.')
param location string = resourceGroup().location

@description('Tags to apply to the gateway.')
param tags object = {}

@description('Object (principal) ID of the Function app managed identity that invokes the MCP server.')
param functionPrincipalId string

@description('Object (principal) ID of the user who will authorize the queue connection at connectors.azure.com. Leave empty to add no user access policy.')
param authorizerPrincipalId string = ''

@description('Entra tenant ID used for the connection access policies.')
param connectionTenantId string = tenant().tenantId

@description('Name of the Azure Queues connection resource.')
param connectionName string = 'queue-route'

@description('Name of the MCP server config resource.')
param mcpServerConfigName string = 'Azure-Queues-put-message'

resource gateway 'Microsoft.Web/connectorGateways@2026-05-01-preview' = {
  name: connectorGatewayName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// Azure Queues connection authenticated with interactive Microsoft Entra ID sign-in.
resource queueConnection 'Microsoft.Web/connectorGateways/connections@2026-05-01-preview' = {
  parent: gateway
  name: connectionName
  properties: {
    connectorName: 'azurequeues'
    displayName: 'Expense Routing Queue Connection'
    parameterValueSet: {
      name: 'tokenBasedAuth'
      values: {}
    }
  }
}

// Allow the Function app's managed identity to invoke the connection via the gateway MCP server.
resource functionAccessPolicy 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = {
  parent: queueConnection
  name: functionPrincipalId
  location: location
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: {
        objectId: functionPrincipalId
        tenantId: connectionTenantId
      }
    }
  }
}

// Allow the authorizing user (who signs in at connectors.azure.com) to manage/use the connection.
resource authorizerAccessPolicy 'Microsoft.Web/connectorGateways/connections/accessPolicies@2026-05-01-preview' = if (!empty(authorizerPrincipalId)) {
  parent: queueConnection
  name: empty(authorizerPrincipalId) ? 'placeholder' : authorizerPrincipalId
  location: location
  properties: {
    principal: {
      type: 'ActiveDirectory'
      identity: {
        objectId: authorizerPrincipalId
        tenantId: connectionTenantId
      }
    }
  }
}

// Project the Azure Queues "Put a message on a queue (V2)" operation as an MCP tool the agent can call.
resource queueMcpServer 'Microsoft.Web/connectorGateways/mcpserverconfigs@2026-05-01-preview' = {
  parent: gateway
  name: mcpServerConfigName
  properties: {
    description: 'Azure Queues put-message action so the expense processor agent routes each decision to the destination queue chosen by amount.'
    state: 'Enabled'
    disableApiKeyAuth: false
    settings: {
      textOnlyContent: true
    }
    policies: []
    connectors: [
      {
        connectionName: connectionName
        name: 'azurequeues'
        displayName: 'Azure Queues'
        description: ''
        operations: [
          {
            name: 'PutMessage_V2'
            displayName: 'Put a message on a queue (V2)'
            description: 'Adds the compact decision JSON as a message on the destination queue chosen by amount.'
            agentParameters: [
              {
                name: 'storageAccountName'
                schema: {
                  type: 'string'
                  description: 'Name of the Azure Storage account that owns the destination queues, e.g. stexpense.'
                }
              }
              {
                name: 'queueName'
                schema: {
                  type: 'string'
                  description: 'Destination queue chosen by amount: expense-approved, expense-review, or expense-flagged.'
                }
              }
              {
                name: 'message'
                schema: {
                  type: 'string'
                  description: 'Message body: the compact decision JSON.'
                }
              }
            ]
            userParameters: []
          }
        ]
      }
    ]
  }
  dependsOn: [
    queueConnection
  ]
}

@description('MCP server endpoint URL for the queue routing tool (QUEUE_MCP_SERVER_URL app setting).')
output mcpServerUrl string = queueMcpServer.properties.mcpEndpointUrl

@description('Name of the queue connection to authorize at connectors.azure.com.')
output connectionName string = connectionName

@description('Name of the connector gateway.')
output gatewayName string = gateway.name
