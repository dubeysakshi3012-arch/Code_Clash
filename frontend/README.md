# CodeClash Frontend

Next.js frontend for CodeClash platform.

## Setup

1. **Install dependencies**
   ```bash
   npm install
   ```

2. **Set up environment variables**
   ```bash
   cp .env.local.example .env.local
   # Edit .env.local with your API URL
   ```

3. **Run development server**
   ```bash
   npm run dev
   ```

The frontend will be available at `http://localhost:3000`

## Features

- User authentication (login/register)
- Dashboard with ELO rating display
- Assessment flow with language selection
- Question display and code submission
- Results page with ELO update

## Pages

- `/` - Landing page
- `/login` - Login page
- `/register` - Registration page
- `/dashboard` - User dashboard
- `/assessment/[id]` - Assessment taking interface
