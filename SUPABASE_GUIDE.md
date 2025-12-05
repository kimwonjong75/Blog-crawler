# Supabase Integration Guide

This guide explains how to set up Supabase to allow access to your blog database from multiple PCs.

## 1. Project Setup (Supabase)

1. Go to [Supabase](https://supabase.com/) and sign up/log in.
2. Click **"New Project"**.
3. Select an organization and enter details:
   - **Name**: Blog Crawler
   - **Database Password**: (Generate a strong password and save it)
   - **Region**: Select a region close to you (e.g., Seoul, Tokyo)
4. Click **"Create new project"**.
5. Wait for the database to be provisioned.

## 2. Database & Auth Configuration

### Database Schema
1. Once the project is ready, go to the **SQL Editor** (icon on the left).
2. Click **"New query"**.
3. Copy the content of `supabase_setup.sql` from this repository and paste it into the query editor.
4. Click **"Run"** to create tables and security policies.

### Authentication
1. Go to **Authentication** > **Providers**.
2. Ensure **Email** provider is enabled.
3. (Optional) Disable "Confirm email" in **Authentication** > **URL Configuration** if you want to test quickly without email verification, or use a real email to verify.

## 3. Client Setup

### Web Client (`supabase_client.html`)
We have created a simple web interface `supabase_client.html` to manage blogs and view posts.

1. Open `supabase_client.html` in your browser.
2. It will ask for **Supabase URL** and **Anon Key**.
   - You can find these in Supabase Dashboard > **Project Settings** > **API**.
3. Enter them to connect.
4. Sign up with an email/password.
5. Once logged in, you can add blogs and view posts.

### Environment Variables (for Python/Streamlit)
If you plan to integrate Supabase into the Python backend:

1. Add the following to your `.env` file:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   ```
2. You will need to install the Python client:
   ```bash
   pip install supabase
   ```
3. Update `app.py` or `db_manager.py` to use Supabase instead of SQLite (Migration required).

## 4. Security

- **RLS (Row Level Security)**: We enabled RLS in `supabase_setup.sql`.
  - Blogs: Publicly readable, but only the creator can edit/delete.
  - Posts: Publicly readable, authenticated users can add/edit.
- **HTTPS**: Supabase API is HTTPS by default.
- **Environment Variables**: Never commit `.env` or hardcode keys in public files. In `supabase_client.html`, keys are input by the user (stored in LocalStorage) to avoid hardcoding.

## 5. Testing & Deployment

- **Testing**: Open `supabase_client.html` on different browsers or devices (using the hosted URL if deployed).
- **Deployment**: You can host `supabase_client.html` on Vercel, Netlify, or GitHub Pages.
- **Performance**: Use Supabase Dashboard to monitor database usage.

## Next Steps
- Migrate existing data from SQLite to Supabase using a Python script.
- Update `app.py` to fetch data from Supabase instead of local SQLite if you want the Streamlit app to be cloud-connected.
