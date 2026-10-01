# Deploying MedChat AI on Azure

This guide uses the Azure CLI (`az`). Names in `<angle brackets>` are yours to choose. Azure model names, versions and regional availability change over time, so check the Azure AI Foundry model catalog for what your subscription and region currently offer.

## 1. Create the Azure OpenAI resource and a GPT-4 deployment

```bash
az login
az group create --name <rg> --location eastus

az cognitiveservices account create \
  --name <openai-resource> --resource-group <rg> \
  --kind OpenAI --sku S0 --location eastus \
  --custom-domain <openai-resource>

# Deploy a GPT-4-family model. Pick a model/version available in your region,
# for example gpt-4o; older GPT-4 versions are being retired.
az cognitiveservices account deployment create \
  --name <openai-resource> --resource-group <rg> \
  --deployment-name gpt-4 \
  --model-name <model-name> --model-version <model-version> --model-format OpenAI \
  --sku-name Standard --sku-capacity 10
```

Get the endpoint and key:

```bash
az cognitiveservices account show -n <openai-resource> -g <rg> --query properties.endpoint -o tsv
az cognitiveservices account keys list -n <openai-resource> -g <rg> --query key1 -o tsv
```

You can also do all of this in the portal: create an **Azure OpenAI** resource, open it in **Azure AI Foundry**, and use **Deployments → Deploy model**.

## 2a. Deploy the app to Azure Container Apps (uses the Dockerfile)

```bash
az containerapp up \
  --name medchat-ai --resource-group <rg> --location eastus \
  --source . --ingress external --target-port 8000 \
  --env-vars LLM_PROVIDER=azure \
             AZURE_OPENAI_ENDPOINT=<endpoint> \
             AZURE_OPENAI_API_KEY=<key> \
             AZURE_OPENAI_DEPLOYMENT=gpt-4
```

For production, store the key as a Container Apps secret (`az containerapp secret set`) and reference it with `secretref:`, or use a managed identity with Key Vault, rather than a plain environment variable.

## 2b. Or deploy to Azure App Service (no Docker)

```bash
az webapp up --name <app-name> --resource-group <rg> --runtime "PYTHON:3.12" --sku B1

az webapp config set --name <app-name> --resource-group <rg> \
  --startup-file "python -m uvicorn medchat.api:app --host 0.0.0.0 --port 8000"

az webapp config appsettings set --name <app-name> --resource-group <rg> --settings \
  LLM_PROVIDER=azure \
  AZURE_OPENAI_ENDPOINT=<endpoint> \
  AZURE_OPENAI_API_KEY=<key> \
  AZURE_OPENAI_DEPLOYMENT=gpt-4 \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

## 3. Verify

```bash
curl https://<your-app-host>/api/health
# {"status":"ok","provider":"azure","model":"gpt-4",...}
```

Then open the site. The header status pill should read "Azure OpenAI · <model>".

## Production checklist

- Set `ALLOWED_ORIGINS` to your site's origin instead of `*`.
- Keep keys in Key Vault or app secrets, never in the repository.
- The in-memory rate limiter is per instance. Behind multiple instances, use Azure API Management or Front Door rate limiting.
- Enable Application Insights for request tracing.
- Handling real patient data requires much more (a BAA, access controls, audit logging, data retention policies). See the README's safety notes.
