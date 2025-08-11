#!/bin/bash

# GraphRAG Search Deployment Script
# This script handles the complete deployment process to Google Cloud Run

set -e  # Exit on any error

echo "🚀 GraphRAG Search Deployment Script"
echo "===================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ ERROR: gcloud CLI is not installed. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ ERROR: You are not authenticated with gcloud."
    echo "   Please run: gcloud auth login"
    exit 1
fi

# Check if project is set
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ ERROR: No Google Cloud project is set."
    echo "   Please run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "📋 Using Google Cloud Project: $PROJECT_ID"
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found!"
    echo ""
    echo "Please create a .env file with your environment variables."
    if [ -f ".env.template" ]; then
        echo "You can copy the template and fill in your values:"
        echo "   cp .env.template .env"
        echo "   # Then edit .env with your actual values"
    fi
    echo ""
    exit 1
fi

# Load environment variables from .env file
echo "📋 Loading environment variables from .env file..."
# Use a more robust method that handles special characters and strips comments
while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    if [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]]; then
        continue
    fi
    # Export the variable, stripping inline comments
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
        # Remove inline comments (everything after # including the #)
        clean_line=$(echo "$line" | sed 's/[[:space:]]*#.*$//')
        export "$clean_line"
    fi
done < .env

# Validate required environment variables
if [ -z "$NEO4J_URI" ]; then
    echo "❌ ERROR: NEO4J_URI is required in .env file"
    exit 1
fi

if [ -z "$NEO4J_DATABASE" ]; then
    echo "❌ ERROR: NEO4J_DATABASE is required in .env file"
    exit 1
fi

if [ -z "$NEO4J_USERNAME" ]; then
    echo "❌ ERROR: NEO4J_USERNAME is required in .env file"
    exit 1
fi

if [ -z "$NEO4J_PASSWORD" ]; then
    echo "❌ ERROR: NEO4J_PASSWORD is required in .env file"
    exit 1
fi

API_KEY="${OPENAI_API_KEY:-$GRAPHRAG_API_KEY}"
if [ -z "$API_KEY" ]; then
    echo "❌ ERROR: Either OPENAI_API_KEY or GRAPHRAG_API_KEY is required in .env file"
    exit 1
fi

echo "✅ Environment variables validated"
echo ""

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com secretmanager.googleapis.com --project=$PROJECT_ID

# Set up secrets
echo ""
echo "🔐 Setting up secrets in Google Secret Manager..."
chmod +x setup-gcp-secrets.sh
./setup-gcp-secrets.sh

if [ $? -ne 0 ]; then
    echo "❌ ERROR: Failed to set up secrets. Please check the output above."
    exit 1
fi

# Deploy to Cloud Run
echo ""
echo "🚀 Deploying to Google Cloud Run..."
echo "This may take several minutes..."
echo ""

# Build substitutions string, properly escaping special characters
SUBSTITUTIONS="_NEO4J_URI=${NEO4J_URI},_NEO4J_DATABASE=${NEO4J_DATABASE},_NEO4J_USERNAME=${NEO4J_USERNAME}"

# Add PostgreSQL substitutions if they exist
if [ ! -z "$POSTGRES_HOST" ]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_POSTGRES_HOST=${POSTGRES_HOST}"
fi
if [ ! -z "$POSTGRES_DATABASE" ]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_POSTGRES_DATABASE=${POSTGRES_DATABASE}"
fi
if [ ! -z "$POSTGRES_USER" ]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_POSTGRES_USER=${POSTGRES_USER}"
fi
if [ ! -z "$POSTGRES_PORT" ]; then
    SUBSTITUTIONS="${SUBSTITUTIONS},_POSTGRES_PORT=${POSTGRES_PORT}"
fi

echo "📋 Using substitutions: $SUBSTITUTIONS"
echo ""

gcloud builds submit --config cloudbuild.yaml --substitutions="$SUBSTITUTIONS" --project=$PROJECT_ID

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Deployment successful!"
    echo ""
    
    # Get the service URL
    SERVICE_URL=$(gcloud run services describe graphrag-search --region=us-central1 --format="value(status.url)" --project=$PROJECT_ID)
    
    echo "📋 Deployment Summary:"
    echo "   Service URL: $SERVICE_URL"
    echo "   Health Check: $SERVICE_URL/health"
    echo "   Query Endpoint: $SERVICE_URL/query"
    echo ""
    
    echo "🔍 Testing deployment..."
    if curl -s -f "$SERVICE_URL/health" > /dev/null; then
        echo "✅ Health check passed!"
    else
        echo "⚠️  Health check failed. Check the logs:"
        echo "   gcloud run services logs read graphrag-search --region us-central1"
    fi
    
    echo ""
    echo "📚 Useful commands:"
    echo "   View logs: gcloud run services logs read graphrag-search --region us-central1"
    echo "   Update service: gcloud builds submit --config cloudbuild.yaml"
    echo "   Delete service: gcloud run services delete graphrag-search --region us-central1"
    echo ""
    
else
    echo ""
    echo "❌ Deployment failed!"
    echo "Check the build logs above for details."
    echo ""
    echo "Common issues:"
    echo "   - Missing or invalid environment variables in .env"
    echo "   - Insufficient permissions"
    echo "   - Billing not enabled on the project"
    echo ""
    exit 1
fi 