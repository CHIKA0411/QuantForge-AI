# QuantForge AI Frontend Deployment Guide

This guide describes how to deploy the Next.js frontend to Vercel and link it to your backend.

---

## Method 1: Vercel GitHub Integration (Recommended)

This is the easiest and most robust method. Vercel will automatically build and deploy your project whenever you push code changes to GitHub.

### Step 1: Push Local Changes to GitHub
Make sure all your latest changes are pushed to your remote repository:
```bash
git add .
git commit -m "Configure deployment guides and verify Next.js build"
git push origin main
```

### Step 2: Import Project to Vercel
1. Go to the [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **Add New...** and select **Project**.
3. Import your repository: `CHIKA0411/QuantForge-AI`.

### Step 3: Configure Project Settings
In the Vercel project configuration page:
- **Framework Preset:** Next.js (automatically detected)
- **Root Directory:** Set this to `frontend` (since your repository is a monorepo containing both `backend` and `frontend` folders).
- **Build Command:** `npm run build` (default)
- **Output Directory:** `.next` (default)

### Step 4: Environment Variables
Under the **Environment Variables** section, add the following key:
- **Key:** `BACKEND_URL`
- **Value:** The public URL of your FastAPI backend (e.g. `https://api.quantforge.com/api`).
- **Key:** `NEXT_PUBLIC_API_BASE`
- **Value:** `/api`

### Step 5: Deploy
Click **Deploy**. Vercel will build and provision your frontend application. Once done, you will receive a production URL (e.g., `https://quantforge-ai.vercel.app`).

---

## Method 2: Deploying via Vercel CLI

If you prefer deploying directly from your command line without linking to GitHub, you can use the Vercel CLI.

### Step 1: Install Vercel CLI
Run the following command in your terminal to install Vercel CLI globally:
```bash
npm install -g vercel
```
*Alternatively, you can run it via `npx` without a global install: `npx vercel`.*

### Step 2: Run Deployment Command
Navigate to the `frontend` directory and initiate the deployment:
```bash
cd frontend
vercel login
vercel
```
1. Follow the authentication prompts in your browser.
2. Link the project to your Vercel account.
3. When asked for environment variables, you can set `BACKEND_URL` in the Vercel Dashboard after the project is created.

### Step 3: Deploy to Production
To build and deploy directly to production:
```bash
vercel --prod
```

---

## Backend Deployment Notes
Since the frontend uses serverless functions to proxy `/api/*` to the FastAPI backend, you need to ensure the backend is publicly available.
- If you use **Render**, **Railway**, or **AWS EC2** for the backend, make sure to set the CORS configuration on the FastAPI side to accept requests from your Vercel frontend domain.
- Verify that your SQLite database (`quantforge.db`) is either persistent or that you migrate to a managed database like PostgreSQL (`TimescaleDB`) for production.
