### Documentation
- Update claude.md when making significant changes
- Keep Linear issues current with TodoWrite tool
- Document any new environment variables in env.template
- Update readme files when adding new features

---

**Remember**: 

- FOCUS ON DEVELOPING THE PLAN BY REVIEWING THE EXISTING CODE BASE SO YOU ARE NOT CREATING ANY NEW ASSET THAT IS ALREADY BUILT BUT ADDING FEATURES TO IT. DO SUGGEST IF IT NEEDS REFACTOR OR ANY GOOD
SOFTWARE ENGINEERING PRINCIPLES.
- USE GITHUB ACTIONS, GITHUB FOR SETTING CODES IN AZURE ML 
- ALL TESTING CODES SHOULD BE LOGICALLY KEPT IN THE SAME FOLDER
- UPDATES IN THE readme.md files should be in the similar files that are meant for it, DON'T 
CREATE NEW FILES IF NOT REQUIRED. 
- ANY NEW ISSUES/TASKS SHOULD BE BACKLOGED IN THE LINEAR APP

## Confluence Q&A System Development Rules

### Core Principles

#### 1. Check for Existing Code First
- **ALWAYS** search the codebase for existing implementations before creating new code
- **REVIEW** all deployment scripts in `/infra` directory for similar functionality
- **EXAMINE** existing modules and functions that might already solve the problem
- **REUSE** existing code whenever possible instead of creating duplicates
- **DOCUMENT** why new code is needed if existing solutions don't meet requirements
- **Always** review directories (like `infra` and `infra/modules`) to ensure functionality does NOT exist before creating new code
- Memorize the principle: Do NOT create a script without first thoroughly checking for existing implementations

#### 2. Azure-First Approach
- **DO NOT** create custom code for functionality that Azure already provides
- **ALWAYS** check Azure services documentation for native features before building custom solutions
- **PREFER** Azure's built-in capabilities (e.g., AI Search indexers, cognitive skills, managed services)
- **USE** Azure's native integrations between services (e.g., AI Search with OpenAI embeddings)

#### 3. Architecture Guidelines
- Keep architecture simple and use managed services
- Avoid unnecessary microservices or API layers
- Leverage Azure's serverless offerings (Functions, Logic Apps) appropriately
- Use Azure's built-in security features instead of custom implementations

#### 4. Code Quality
- Write production-ready code with proper error handling
- Include comprehensive logging using Azure Application Insights
- Follow async/await patterns for Azure SDK operations
- Use environment variables for all configuration

#### 5. Azure AI Search Best Practices
- Use built-in AI enrichment pipelines for embeddings
- Configure indexers with appropriate skills instead of custom processing
- Leverage semantic search capabilities
- Use integrated vectorization through Azure OpenAI skill

#### 6. Cost Optimization
- Choose appropriate service tiers for development/production
- Use serverless where possible to minimize costs
- Monitor usage through Azure Cost Management
- Implement proper data retention policies

#### 7. Documentation
- Document Azure resource dependencies
- Include deployment instructions using Azure CLI/Bicep
- Provide clear environment setup guides
- Reference official Azure documentation

#### 8. Integration Patterns
- Use Azure's native service-to-service authentication (Managed Identities)
- Implement proper retry logic using Polly or Azure SDK features
- Use Azure Service Bus or Event Grid for async communication
- Leverage Azure Key Vault for secrets management

### Specific Don'ts
- Don't create custom embedding APIs when Azure AI Search indexers can handle it
- Don't build authentication systems when Azure AD/Entra ID exists
- Don't implement custom monitoring when Application Insights is available
- Don't create complex deployment scripts when Azure DevOps/GitHub Actions work

### Development Workflow
1. Check for existing code/solutions in the codebase first
2. Research Azure documentation for native features
3. Review existing deployment scripts and modules
4. Design using Azure-native patterns when new code is needed
5. Implement with minimal custom code, reusing existing components
6. Deploy using Infrastructure as Code (Bicep/ARM)
7. Monitor using Azure's built-in tools

Remember: Azure has likely already solved the problem - find and use their solution!
- to memorize Use the confluence-QandA for integrations and infra and use confluence-QandA-agents for agents, tracing etc.
- to memorize, use autogen open telementry for tracing purposes
- think ultrahard, if we do need to create the model client for aysnc interfacing of openai chatcompletionclient.