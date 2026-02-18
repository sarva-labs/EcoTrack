# EcoTrack Development Setup Guide

Complete guide to setting up and running the EcoTrack monorepo locally.

## Prerequisites

- Node.js >= 18.0.0
- npm >= 9.0.0
- Python >= 3.11
- Docker and Docker Compose
- Git

## Project Structure

```
EcoTrack/
├── apps/
│   ├── web/              # Next.js 15 frontend (React 19)
│   ├── api/              # NestJS backend API
│   └── ml-api/           # FastAPI ML service
├── packages/             # Shared packages (optional)
├── supabase/
│   └── migrations/       # Database migrations
├── .github/
│   └── workflows/        # CI/CD pipelines
├── docker-compose.yml    # Docker orchestration
├── turbo.json           # Turborepo configuration
└── package.json         # Root package configuration
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/ecotrack/ecotrack.git
cd EcoTrack
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Environment Setup

Copy environment files and configure:

```bash
# Frontend
cp apps/web/.env.example apps/web/.env.local

# Backend API
cp apps/api/.env.example apps/api/.env

# ML API
cp apps/ml-api/.env.example apps/ml-api/.env
```

### 4. Configure Supabase

Option A: Use Supabase Cloud
1. Create account at [supabase.com](https://supabase.com)
2. Create new project
3. Copy URL and keys to environment files

Option B: Self-hosted Supabase
```bash
# Run Supabase locally with Docker
docker-compose up postgres -d
```

### 5. Run Database Migrations

```bash
# Apply migrations to your Supabase database
# Using Supabase CLI (install: npm install -g supabase)
supabase db push
```

### 6. Start Development Servers

Option A: Run all services with Turborepo
```bash
npm run dev
```

Option B: Run services individually
```bash
# Terminal 1 - Frontend
cd apps/web
npm run dev

# Terminal 2 - Backend API
cd apps/api
npm run dev

# Terminal 3 - ML API
cd apps/ml-api
python main.py
```

Option C: Run with Docker Compose
```bash
docker-compose up
```

## Service URLs

- Frontend: http://localhost:3000
- Backend API: http://localhost:3001
- ML API: http://localhost:8000
- API Documentation: http://localhost:3001/api/docs
- ML API Documentation: http://localhost:8000/docs

## Development Workflow

### Running Tests

```bash
# Run all tests
npm run test

# Run tests for specific workspace
npm run test --filter=@ecotrack/web
```

### Linting and Formatting

```bash
# Lint all workspaces
npm run lint

# Format code
npm run format

# Type check
npm run type-check
```

### Building for Production

```bash
# Build all applications
npm run build

# Build specific workspace
npm run build --filter=@ecotrack/api
```

## Technology Stack Details

### Frontend (Next.js 15)
- **Framework**: Next.js 15 with App Router
- **React**: Version 19
- **Styling**: Tailwind CSS + shadcn/ui
- **Forms**: React Hook Form + Zod
- **Maps**: React Leaflet
- **State**: React Server Components

### Backend (NestJS)
- **Framework**: NestJS 10
- **Language**: TypeScript (strict mode)
- **Validation**: class-validator + class-transformer
- **Documentation**: Swagger/OpenAPI
- **Database**: Supabase (PostgreSQL + Auth + Storage)
- **Cache**: Redis

### ML Service (FastAPI)
- **Framework**: FastAPI
- **Object Detection**: YOLOv8 (Ultralytics)
- **Classification**: PyTorch + Transformers
- **Image Processing**: OpenCV, Pillow
- **Deployment**: Uvicorn

## Database Schema

### Trees Table
```sql
- id: UUID (primary key)
- species: VARCHAR(255)
- latitude: DECIMAL(10,8)
- longitude: DECIMAL(11,8)
- estimated_age: INTEGER
- root_spread: DECIMAL(10,2)
- soil_type: VARCHAR(100)
- height: DECIMAL(10,2)
- canopy_diameter: DECIMAL(10,2)
- metadata: JSONB
- user_id: UUID (foreign key)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

## Docker Setup

### Build Images

```bash
# Build all services
docker-compose build

# Build specific service
docker-compose build web
```

### Run Services

```bash
# Start all services
docker-compose up

# Start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Deployment

### Frontend (Vercel)

1. Connect repository to Vercel
2. Configure environment variables
3. Deploy automatically on push to main

### Backend (Railway/Fly.io)

```bash
# Railway
railway up

# Fly.io
fly deploy
```

### ML API (Fly.io)

```bash
cd apps/ml-api
fly deploy
```

## Troubleshooting

### Port Already in Use

```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:3000 | xargs kill -9
```

### Docker Issues

```bash
# Clean up Docker
docker-compose down -v
docker system prune -a

# Rebuild without cache
docker-compose build --no-cache
```

### Module Not Found Errors

```bash
# Clear node_modules and reinstall
rm -rf node_modules apps/*/node_modules
npm install
```

## Contributing

1. Create feature branch: `git checkout -b feature/your-feature`
2. Commit changes: `git commit -m "feat: add your feature"`
3. Push to branch: `git push origin feature/your-feature`
4. Create Pull Request

### Commit Convention

Follow Angular commit convention:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/tooling changes

## Additional Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [NestJS Documentation](https://docs.nestjs.com)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Supabase Documentation](https://supabase.com/docs)
- [Turborepo Documentation](https://turbo.build/repo/docs)

## Support

For issues and questions:
- Create an issue on GitHub
- Check existing documentation
- Review closed issues for solutions

## License

MIT License - see LICENSE file for details
