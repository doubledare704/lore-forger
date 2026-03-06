# LoreForge ⚔️📜

LoreForge is an AI-powered campaign builder for tabletop RPGs. It uses FastAPI, SvelteKit, Google Firestore, and the Gemini API to forge rich, immersive worlds with just a few incantations.

## 🚀 Features

- **AI-Powered Generation**: Uses Gemini to build world lore, characters, and quests.
- **Dynamic Presentations**: Generates Reveal.js decks to visualize your campaign.
- **Persistent State**: Stores world data in Google Cloud Firestore.
- **Real-time Streaming**: Utilizes Server-Sent Events (SSE) for fluid AI responses.

## 📂 Project Structure

- `backend/`: FastAPI service handling AI logic, data persistence, and serving the frontend.
- `frontend/`: SvelteKit user interface for interacting with the AI grimoire.
- `Dockerfile`: Multi-stage Docker build that bundles the frontend and backend.

## 🛠 Local Development

### 🐍 Backend
1. Install [uv](https://astral.sh/uv/): `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Sync dependencies: `uv sync`
3. Set up Google Cloud Application Default Credentials: `gcloud auth application-default login`
4. Run the API: `uvicorn backend.app.main:app --reload --port 8000`

### 🎨 Frontend
1. Navigate to `/frontend`.
2. Install dependencies: `npm install`
3. Run development server: `npm run dev` (Connects to backend on port 8000).

## ☁️ Deployment to Google Cloud Platform

LoreForge is optimized for **Google Cloud Run**.

### Why Cloud Run?
- **Serverless**: No server management required.
- **Scale-to-Zero**: You only pay when the app is being used.
- **Performance**: High concurrency support, perfect for the FastAPI/SvelteKit stack.
- **GCP Native**: Easy access to Vertex AI (Gemini/Imagen) and Firestore.

### 🚀 Quick Deployment
We've included a bash script to automate the entire deployment process.

1.  **Configure gcloud**:
    ```bash
    gcloud auth login
    gcloud config set project [YOUR_PROJECT_ID]
    ```
2.  **Run the script**:
    ```bash
    ./deploy.sh
    ```
    This script will:
    - Enable required APIs (Cloud Run, Cloud Build, Firestore, Vertex AI).
    - Build your container image using Cloud Build.
    - Deploy the service to Cloud Run with optimized settings.

### 🗄 Firestore Setup
Ensure your project has a Firestore database initialized in **Native mode**.
1. Go to the [Firestore Console](https://console.cloud.google.com/firestore).
2. Create a database (default location is usually fine).
3. The application will automatically create the necessary collections.

## ⚙️ Configuration

Environment variables can be set in the Cloud Run console or passed via the CLI:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | - | The API key for Gemini calls. **Required for LoreForge to work.** |
| `LOREFORGE_GEMINI_MODEL` | `gemini-3-flash-preview` | The Gemini model to use for lore. |
| `LOREFORGE_IMAGE_MODEL` | `imagen-4.0-fast-generate-001` | The Imagen model to use for visuals. |
| `LOREFORGE_CORS_ORIGINS` | `http://localhost:5173` | Allowed CORS origins. |
| `LOREFORGE_DECK_IMAGES` | `1` | Whether to generate images for decks. |
| `LOREFORGE_AUTO_IMAGE_FOR_SCENES` | `1` | Auto-generate images for story beats. |

### 🔑 Managing Secrets (GOOGLE_API_KEY)

For **Cloud Run**, there are two main ways to inject your `GOOGLE_API_KEY`:

#### 1. Quick & Simple (Environment Variable)
Pass it directly to the deployment script:
```bash
export GOOGLE_API_KEY=your_actual_key_here
./deploy.sh
```
This will set it as an environment variable in the Cloud Run service.

#### 2. Secure (Secret Manager) - Recommended
1. Create a secret in [Google Cloud Secret Manager](https://console.cloud.google.com/security/secret-manager) named `GOOGLE_API_KEY`.
2. Give the Cloud Run service account permission to access this secret (`Secret Manager Secret Accessor` role).
3. Update your Cloud Run service to mount this secret as an environment variable:
   ```bash
   gcloud run services update lore-forger \
       --set-secrets=GOOGLE_API_KEY=GOOGLE_API_KEY:latest \
       --region us-central1
   ```
