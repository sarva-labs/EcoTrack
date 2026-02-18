# EcoTrack - Next Steps

Congratulations! Your EcoTrack monorepo is now set up with a comprehensive tech stack. Here are the immediate next steps to get started.

## 1. Install Dependencies

```bash
# Install all workspace dependencies
npm install

# Or if using pnpm
pnpm install
```

Note: TypeScript errors in the IDE are expected until dependencies are installed.

## 2. Configure Environment Variables

### Frontend (apps/web/.env.local)
```bash
cp apps/web/.env.example apps/web/.env.local
```

Edit and add your Supabase credentials:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

### Backend (apps/api/.env)
```bash
cp apps/api/.env.example apps/api/.env
```

Edit and add:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

### ML API (apps/ml-api/.env)
```bash
cp apps/ml-api/.env.example apps/ml-api/.env
```

## 3. Set Up Supabase

### Option A: Supabase Cloud (Recommended for Quick Start)
1. Sign up at [supabase.com](https://supabase.com)
2. Create a new project
3. Copy the URL and keys to your environment files
4. Run the migration:
   ```bash
   # In Supabase Dashboard SQL Editor, run:
   # supabase/migrations/001_create_trees_table.sql
   ```

### Option B: Self-Hosted Supabase
```bash
docker-compose up postgres -d
```

## 4. Install Python Dependencies (for ML API)

```bash
cd apps/ml-api
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 5. Run Development Servers

### Option 1: Run All Services with Turborepo
```bash
npm run dev
```

This starts:
- Frontend: http://localhost:3000
- Backend API: http://localhost:3001
- ML API: http://localhost:8000

### Option 2: Run Services Individually
```bash
# Terminal 1 - Frontend
cd apps/web
npm run dev

# Terminal 2 - Backend
cd apps/api
npm run dev

# Terminal 3 - ML API
cd apps/ml-api
python main.py
```

### Option 3: Docker Compose
```bash
docker-compose up
```

## 6. Access Your Application

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:3001/api/docs
- **ML API Docs**: http://localhost:8000/docs

## 7. Implement Core Features

### Priority 1: Complete shadcn/ui Setup
```bash
cd apps/web
npx shadcn-ui@latest init
```

Install commonly used components:
```bash
npx shadcn-ui@latest add button
npx shadcn-ui@latest add card
npx shadcn-ui@latest add form
npx shadcn-ui@latest add input
npx shadcn-ui@latest add toast
```

### Priority 2: Implement ML Models

1. Download YOLOv8 model:
```bash
cd apps/ml-api/models
# Download from Ultralytics: yolov8n.pt
```

2. Update `apps/ml-api/main.py` to load and use models

### Priority 3: Build Frontend Pages

Create key pages:
- `/map` - Interactive tree map
- `/detect` - Real-time detection interface
- `/dashboard` - User dashboard
- `/auth` - Authentication pages

### Priority 4: Implement Authentication

Add Supabase auth flows:
- Google OAuth
- Magic link login
- Protected routes
- User profile management

## 8. Testing

```bash
# Run linter
npm run lint

# Run type check
npm run type-check

# Run tests (when implemented)
npm run test
```

## 9. Build for Production

```bash
# Build all applications
npm run build

# Test production build locally
npm run start
```

## 10. Deploy

### Frontend to Vercel
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd apps/web
vercel
```

### Backend to Railway
```bash
# Install Railway CLI
npm i -g @railway/cli

# Deploy
cd apps/api
railway up
```

### ML API to Fly.io
```bash
# Install Fly CLI
# https://fly.io/docs/hands-on/install-flyctl/

# Deploy
cd apps/ml-api
fly deploy
```

## Project Structure Overview

```
EcoTrack/
├── apps/
│   ├── web/                    # Next.js frontend
│   │   ├── src/
│   │   │   ├── app/           # App router pages
│   │   │   └── lib/           # Utilities and configs
│   │   ├── Dockerfile
│   │   └── package.json
│   │
│   ├── api/                    # NestJS backend
│   │   ├── src/
│   │   │   ├── trees/         # Trees module
│   │   │   └── supabase/      # Supabase integration
│   │   ├── Dockerfile
│   │   └── package.json
│   │
│   └── ml-api/                 # FastAPI ML service
│       ├── main.py
│       ├── requirements.txt
│       └── Dockerfile
│
├── supabase/
│   └── migrations/             # Database migrations
│
├── .github/
│   └── workflows/              # CI/CD pipelines
│
├── docker-compose.yml          # Local development
├── turbo.json                  # Turborepo config
├── package.json                # Root config
├── README.md                   # Project overview
├── SETUP.md                    # Setup instructions
├── API.md                      # API documentation
└── CONTRIBUTING.md             # Contributing guide
```

## Key Features to Implement

### Phase 1 (MVP)
- [ ] Tree detection from uploaded images
- [ ] Basic species classification
- [ ] GPS-based tree mapping
- [ ] User authentication
- [ ] Tree CRUD operations

### Phase 2
- [ ] Real-time camera detection
- [ ] Enhanced species classification
- [ ] Age and root spread estimation
- [ ] Soil type classification
- [ ] User dashboard with statistics

### Phase 3
- [ ] CO₂ sequestration calculations
- [ ] Community features
- [ ] Mobile applications
- [ ] Advanced analytics
- [ ] Climate impact reporting

## Useful Commands

```bash
# Install new dependency to frontend
npm install <package> --workspace=@ecotrack/web

# Install new dependency to backend
npm install <package> --workspace=@ecotrack/api

# Add new migration
# Create file: supabase/migrations/002_your_migration.sql

# Format all code
npm run format

# Clean all builds and node_modules
npm run clean

# Build specific workspace
npm run build --filter=@ecotrack/web
```

## Learning Resources

- [Next.js 15 Docs](https://nextjs.org/docs)
- [NestJS Docs](https://docs.nestjs.com)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Supabase Docs](https://supabase.com/docs)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [shadcn/ui](https://ui.shadcn.com)
- [YOLOv8](https://docs.ultralytics.com)

## Troubleshooting

### TypeScript Errors
Run `npm install` to install all dependencies and generate type definitions.

### Port Already in Use
Change ports in docker-compose.yml or kill the process using the port.

### Supabase Connection Issues
Verify credentials in .env files and check Supabase project status.

### Docker Build Failures
Try `docker-compose build --no-cache` to rebuild without cache.

## Support

- Documentation: Read SETUP.md, API.md, CONTRIBUTING.md
- Issues: Create a GitHub issue
- Community: Join Discord server (if available)

---

**Ready to build? Start with `npm install` and `npm run dev`!**

🌱 Happy coding and let's make an impact on climate change!
