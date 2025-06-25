# Confluence Q&A System - Infrastructure

This directory contains all the infrastructure code and deployment scripts for the Confluence Q&A system.

## 📁 Directory Structure

```
infra/
├── main.bicep                 # Main Bicep template for Azure resources
├── main.bicepparam           # Parameters file for Bicep template
├── setup.sh                 # Complete setup script (recommended)
├── deploy.sh                # Infrastructure deployment script
├── test-resources.sh        # Resource validation tests
├── test-confluence-api.py   # Confluence API connectivity test
├── .env.template           # Environment variables template (hidden file)
├── host.json               # Azure Functions host configuration
├── requirements.txt        # Python dependencies for Azure Functions
├── confluence-ingestion/   # Azure Function for Confluence data ingestion
│   ├── __init__.py        # Function implementation
│   └── function.json      # Function binding configuration
└── README.md             # This file
```

## 🚀 Quick Start

### Prerequisites

1. **Azure CLI** installed and configured
2. **jq** for JSON processing
3. **Python 3.8+** (for testing scripts)
4. **Azure subscription** with appropriate permissions

### Option 1: Complete Setup (Recommended)

Run the complete setup script that handles everything:

```bash
cd infra
./setup.sh
```

This script will:
- Check prerequisites
- Set up environment variables
- Validate Bicep templates
- Deploy Azure resources
- Run validation tests
- Provide next steps

### Option 2: Manual Step-by-Step

1. **Set up environment variables**:
   ```bash
   cp .env.template ../.env
   # Edit ../.env with your values
   ```

2. **Deploy infrastructure**:
   ```bash
   ./deploy.sh
   ```

3. **Run validation tests**:
   ```bash
   ./test-resources.sh
   ```

4. **Test Confluence API**:
   ```bash
   python3 test-confluence-api.py
   ```

## 🏗️ Infrastructure Components

### Azure Resources Created

| Resource | SKU/Tier | Purpose |
|----------|----------|---------|
| **Storage Account** | Standard_LRS | Raw and processed data storage |
| **Cosmos DB** | Standard | Graph database for page relationships |
| **Azure AI Search** | Free | Vector and text search |
| **Azure OpenAI** | S0 | Embeddings and chat completions |
| **Function App** | Consumption (Y1) | Confluence data ingestion |
| **Web App** | F1 (Free) | Frontend UI hosting |

### Cost Optimization

- **Free tiers** used where possible (AI Search, Web App)
- **Consumption plan** for Function App (pay-per-execution)
- **Standard tier** for Cosmos DB (can be changed to Serverless)
- **Local Redundant Storage** for cost efficiency

## 🔧 Configuration

### Environment Variables

The system uses the following environment variables:

```bash
# Azure Subscription
AZ_SUBSCRIPTION_ID=your-subscription-id
AZ_RESOURCE_GROUP=rg-rag-confluence
AZ_LOCATION=WestUS2

# Resource Names
COSMOS_ACCOUNT=cosmos-rag-conf
STORAGE_ACCOUNT=stgragconf
SEARCH_SERVICE=srch-rag-conf
AOAI_RESOURCE=aoai-rag-conf
FUNC_APP=func-rag-conf

# Confluence API (Basic Authentication)
CONFLUENCE_BASE=https://your-org.atlassian.net/wiki/rest/api
CONFLUENCE_TOKEN=your-api-token
CONFLUENCE_EMAIL=your-email@domain.com
```

### Confluence API Token

To create a Confluence API token:

1. Go to [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a label (e.g., "Confluence Q&A System")
4. Copy the token and add it to your `.env` file
5. **Important**: Also add your email address as `CONFLUENCE_EMAIL` for Basic Authentication

## 🧪 Testing & Validation

### Resource Validation

The `test-resources.sh` script validates:
- All Azure resources exist
- Resource connectivity
- Service endpoints are accessible
- Authentication is working

### Confluence API Testing

The `test-confluence-api.py` script tests:
- API connectivity using Basic Authentication
- Authentication with email and token
- Permissions to read content
- Available spaces and pages
- Rate limiting

Run it with:
```bash
python3 test-confluence-api.py
```

## 📊 Monitoring

### Azure Portal

Monitor your resources in the Azure Portal:
- Resource Group: Check all resources are running
- Function App: Monitor execution logs
- Storage Account: Check data ingestion
- Cosmos DB: Monitor graph operations

### Logs and Metrics

- **Function App logs**: Available in Azure Portal or Application Insights
- **Storage metrics**: Monitor blob operations and costs
- **Cosmos DB metrics**: Track RU consumption and query performance

## 🔄 Data Flow

1. **Azure Function** (Timer trigger every 6 hours)
   - Calls Confluence API using Basic Authentication
   - Stores raw JSON in Storage Account (`raw` container)

2. **Processing Pipeline** (Manual/Scheduled)
   - Processes raw data
   - Stores structured data in Storage Account (`processed` container)
   - Populates Cosmos DB graph with relationships

3. **Embedding Pipeline** (Manual/Scheduled)
   - Generates embeddings using Azure OpenAI
   - Stores vectors in Azure AI Search

## 🛠️ Troubleshooting

### Common Issues

1. **Resource name conflicts**
   - Azure resource names must be globally unique
   - Modify names in `main.bicepparam` if needed

2. **Quota limits**
   - Check Azure subscription quotas
   - Request increases if needed

3. **Authentication errors**
   - Verify Azure CLI login: `az account show`
   - Check service principal permissions

4. **Confluence API errors**
   - Verify API token is valid
   - Check token permissions
   - Ensure CONFLUENCE_EMAIL is set correctly
   - Test with `test-confluence-api.py`

### Debug Commands

```bash
# Check Azure login
az account show

# Validate Bicep template
az bicep build --file main.bicep

# Check deployment status
az deployment group show --name deployment-name --resource-group rg-rag-confluence

# Test specific resource
az storage account show --name stgragconf --resource-group rg-rag-confluence
```

## 🔄 Updates and Maintenance

### Updating Infrastructure

1. Modify `main.bicep` or `main.bicepparam`
2. Run `./deploy.sh` to apply changes
3. Run `./test-resources.sh` to validate

### Updating Function Code

1. Modify code in `confluence-ingestion/`
2. Deploy using Azure Functions Core Tools:
   ```bash
   func azure functionapp publish func-rag-conf --python
   ```

### Scaling Considerations

- **Storage**: Automatically scales with usage
- **Cosmos DB**: Monitor RU consumption, scale as needed
- **Function App**: Consumption plan scales automatically
- **AI Search**: Upgrade from Free tier when needed

## 📚 Next Steps

After infrastructure deployment:

1. **Deploy Function App code** for data ingestion
2. **Set up Azure OpenAI model deployments**
3. **Configure embedding pipeline**
4. **Deploy frontend application**
5. **Set up monitoring and alerting**

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review Azure Portal for error messages
3. Check function logs in Application Insights
4. Verify all environment variables are set correctly

## 📄 License

This infrastructure code is part of the Confluence Q&A System project. 