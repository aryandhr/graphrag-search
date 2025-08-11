# Deployment Guide for Google Cloud Run

## Overview
This guide explains how to deploy the GraphRAG Search application to Google Cloud Run with secure secret management using Google Secret Manager.

### Prerequisites
1. **Google Cloud CLI installed**: https://cloud.google.com/sdk/docs/install
2. **Google Cloud Project**: Create one at https://console.cloud.google.com
3. **Billing enabled** on your Google Cloud Project

### One-Command Deployment

1. **Set up your environment variables**:
   ```bash
   # Edit .env with your actual values (Neo4j, OpenAI API key, etc.)
   ```

2. **Configure Google Cloud**:
   ```bash
   # Set your project
   gcloud config set project YOUR_PROJECT_ID
   
   # Authenticate
   gcloud auth login
   ```

3. **Deploy**:
   ```bash
   # Make deployment script executable and run it
   chmod +x deploy.sh
   ./deploy.sh
   ```

That's it! The script will handle everything automatically:
- Enable required Google Cloud APIs
- Set up secrets in Google Secret Manager
- Build and deploy your application
- Provide you with the service URL

## Environment Variables

The application requires these environment variables:

### Required Variables
- `NEO4J_URI`: Your Neo4j Aura instance URI (e.g., `neo4j+s://xxxxx.databases.neo4j.io`)
- `NEO4J_DATABASE`: Database name (usually `neo4j`)
- `NEO4J_USERNAME`: Neo4j username (usually `neo4j`)
- `NEO4J_PASSWORD`: Your Neo4j password (stored as secret)
- `OPENAI_API_KEY`: Your OpenAI API key (stored as secret)

### Optional Variables (PostgreSQL)
- `POSTGRES_HOST`: PostgreSQL host
- `POSTGRES_DATABASE`: Database name
- `POSTGRES_USER`: Username
- `POSTGRES_PASSWORD`: Password (stored as secret)
- `POSTGRES_PORT`: Port (default: 5432)

## Security Features

✅ **Secrets are securely stored** in Google Secret Manager, not in your code  
✅ **No secrets in Git** - all sensitive values are properly excluded  
✅ **Automatic secret rotation** support  
✅ **Proper IAM permissions** for Cloud Run service account  

## After Deployment

After successful deployment, you'll get:
- **Service URL**: `https://graphrag-search-xxxxx-uc.a.run.app`
- **Health Check**: `{SERVICE_URL}/health`
- **Query Endpoint**: `{SERVICE_URL}/query`

### Testing Your Deployment
```bash
# Health check
curl https://your-service-url/health

# Query endpoint (requires POST with JSON body)
curl -X POST https://your-service-url/query \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "email": "user@example.com"}'
```

## Monitoring and Maintenance

### View Logs
```bash
gcloud run services logs read graphrag-search --region us-central1
```

### Update Deployment
```bash
# After making code changes, simply run:
./deploy.sh
# Or manually:
gcloud builds submit --config cloudbuild.yaml
```

### Update Secrets
```bash
# Update your .env file with new values, then run:
./setup-gcp-secrets.sh
```

## Troubleshooting

### Common Issues

**❌ "Service not initialized"**
- Check that all required environment variables are set in `.env`
- Verify Neo4j credentials are correct
- Check Cloud Run logs for detailed error messages

**❌ "Database connection failed"**
- Ensure Neo4j Aura instance is running (not paused)
- Verify the URI uses `neo4j+s://` protocol for Aura
- Check Neo4j credentials in Secret Manager

**❌ "OpenAI API issues"**
- Verify API key is valid and has sufficient credits
- Check OpenAI usage limits

**❌ "Cloud Build failures"**
- Ensure billing is enabled on your GCP project
- Check that all required APIs are enabled
- Verify you have sufficient IAM permissions

### Getting Help

1. **Check logs**: `gcloud run services logs read graphrag-search --region us-central1`
2. **Verify secrets**: Go to Google Cloud Console → Secret Manager
3. **Check service status**: Go to Google Cloud Console → Cloud Run
4. **Test locally**: Run the application locally first to verify it works 