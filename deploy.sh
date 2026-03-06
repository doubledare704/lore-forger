#!/bin/bash
# LoreForge - GCP Deployment Script
# This script deploys the application to Google Cloud Run.

set -e

# --- Configuration ---
SERVICE_NAME="lore-forger"
REGION="us-central1" # Change as needed
# ---------------------

echo "🚀 Starting LoreForge deployment to Google Cloud..."

# 1. Verify gcloud CLI is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed. Please visit https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# 2. Get the current active project
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" == "(unset)" ]; then
    echo "❌ Error: No Google Cloud project is configured."
    echo "Run: gcloud config set project [YOUR_PROJECT_ID]"
    exit 1
fi

echo "📦 Project ID: $PROJECT_ID"
echo "📍 Region: $REGION"

# 3. Enable required Google Cloud APIs
echo "🔌 Enabling required APIs (this may take a minute)..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    firestore.googleapis.com \
    aiplatform.googleapis.com \
    generativelanguage.googleapis.com

# 4. Deploy to Cloud Run
# This command builds the container using Cloud Build and deploys it to Cloud Run.
# It uses the Dockerfile in the root directory.
echo "🛠 Building and deploying service..."

# Collect environment variables to set
ENV_VARS="LOREFORGE_CORS_ORIGINS=*"

# If GOOGLE_API_KEY is present in the local environment, pass it along.
# For production, it's recommended to use Google Cloud Secret Manager.
if [ -n "$GOOGLE_API_KEY" ]; then
    echo "🔑 Injecting GOOGLE_API_KEY from local environment..."
    ENV_VARS="$ENV_VARS,GOOGLE_API_KEY=$GOOGLE_API_KEY"
else
    echo "⚠️  GOOGLE_API_KEY not found in local environment."
    echo "   Ensure it's set in the Cloud Run console after deployment if needed."
fi

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --region "$REGION" \
    --allow-unauthenticated \
    --set-env-vars="$ENV_VARS" \
    --memory 1Gi \
    --cpu 1

# 5. Output the result
if [ $? -eq 0 ]; then
    echo "✅ Success! Your application is now live."
    echo "🔗 You can find the URL in the output above."
else
    echo "❌ Deployment failed. Check the logs above for more information."
    exit 1
fi
