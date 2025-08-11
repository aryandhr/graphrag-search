#!/bin/bash

# This script sets up Google Secret Manager secrets for the GraphRAG Search application
# Run this ONCE before deploying to Google Cloud Run

echo "Setting up Google Cloud Secrets for GraphRAG Search..."
echo "=================================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI is not installed. Please install it first:"
    echo "https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo ""
    echo "Please create a .env file with your environment variables."
    echo "You can copy .env.template to .env and fill in your values:"
    echo "  cp .env.template .env"
    echo "  # Then edit .env with your actual values"
    echo ""
    exit 1
fi

# Load environment variables from .env file
echo "Loading environment variables from .env file..."
set -a  # automatically export all variables
source .env
set +a  # disable automatic export

# Get current project
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: No Google Cloud project is set."
    echo "Please run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "Using project: $PROJECT_ID"
echo ""

# Function to create or update a secret
create_secret() {
    SECRET_NAME=$1
    SECRET_VALUE=$2
    
    if [ -z "$SECRET_VALUE" ]; then
        echo "⚠️  Skipping $SECRET_NAME (no value found in .env)"
        return
    fi
    
    # Check if secret exists
    if gcloud secrets describe $SECRET_NAME --project=$PROJECT_ID &> /dev/null; then
        echo "Secret $SECRET_NAME exists, updating..."
        echo -n "$SECRET_VALUE" | gcloud secrets versions add $SECRET_NAME --data-file=- --project=$PROJECT_ID
    else
        echo "Creating secret $SECRET_NAME..."
        echo -n "$SECRET_VALUE" | gcloud secrets create $SECRET_NAME --data-file=- --project=$PROJECT_ID
    fi
    echo "✅ $SECRET_NAME configured"
}

# Create secrets from environment variables
echo "Creating secrets in Google Secret Manager..."
echo ""

# Get API key (prefer OPENAI_API_KEY, fall back to GRAPHRAG_API_KEY)
API_KEY="${OPENAI_API_KEY:-$GRAPHRAG_API_KEY}"

# Create secrets for sensitive values
create_secret "openai-api-key" "$API_KEY"
create_secret "neo4j-password" "$NEO4J_PASSWORD"

# Create PostgreSQL secret if password is provided
if [ ! -z "$POSTGRES_PASSWORD" ]; then
    create_secret "postgres-password" "$POSTGRES_PASSWORD"
fi

# Grant Cloud Run service account access to secrets
echo ""
echo "Granting Cloud Run access to secrets..."

SERVICE_ACCOUNT="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

# Always grant access to required secrets
for SECRET in "openai-api-key" "neo4j-password"; do
    echo "Granting access to $SECRET..."
    gcloud secrets add-iam-policy-binding $SECRET \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        --project=$PROJECT_ID --quiet
done

# Grant access to PostgreSQL secret if it exists
if [ ! -z "$POSTGRES_PASSWORD" ]; then
    echo "Granting access to postgres-password..."
    gcloud secrets add-iam-policy-binding postgres-password \
        --member="serviceAccount:$SERVICE_ACCOUNT" \
        --role="roles/secretmanager.secretAccessor" \
        --project=$PROJECT_ID --quiet
fi

echo ""
echo "🎉 Secrets setup complete!"
echo ""
echo "Configured secrets:"
echo "  - openai-api-key: $([ ! -z "$API_KEY" ] && echo "✅" || echo "❌")"
echo "  - neo4j-password: $([ ! -z "$NEO4J_PASSWORD" ] && echo "✅" || echo "❌")"
echo "  - postgres-password: $([ ! -z "$POSTGRES_PASSWORD" ] && echo "✅" || echo "❌ (optional)")"
echo ""
echo "Environment variables for deployment:"
echo "  - NEO4J_URI: $([ ! -z "$NEO4J_URI" ] && echo "✅" || echo "❌")"
echo "  - NEO4J_DATABASE: $([ ! -z "$NEO4J_DATABASE" ] && echo "✅" || echo "❌")"
echo "  - NEO4J_USERNAME: $([ ! -z "$NEO4J_USERNAME" ] && echo "✅" || echo "❌")"
echo ""
echo "You can now deploy your application using:"
echo "gcloud builds submit --config cloudbuild.yaml" 