# EcoTrack: End-to-End Implementation Strategy

## Executive Summary

This document outlines a comprehensive, phased implementation strategy for EcoTrack that delivers a production-ready ecological intelligence platform. The strategy emphasizes incremental value delivery, independent component testing, and architectural consistency across the monorepo.

**Timeline**: 16-20 weeks across 4 phases  
**Approach**: Agile with 2-week sprints  
**Testing Strategy**: Test each component independently before integration  
**Deployment**: Continuous delivery to staging, controlled production releases

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Phase 1: Foundation (Weeks 1-4)](#phase-1-foundation-weeks-1-4)
3. [Phase 2: ML Pipeline (Weeks 5-8)](#phase-2-ml-pipeline-weeks-5-8)
4. [Phase 3: Geospatial (Weeks 9-12)](#phase-3-geospatial-weeks-9-12)
5. [Phase 4: Production (Weeks 13-16)](#phase-4-production-weeks-13-16)
6. [Technical Integration Points](#technical-integration-points)
7. [Database Architecture](#database-architecture)
8. [Monitoring & Observability](#monitoring--observability)
9. [Dataset Preparation](#dataset-preparation)

---

## System Architecture

### Data Flow: Camera to Map

```
User Action: Open Camera
     ↓
PWA: Request Permissions (Camera + GPS)
     ↓
Capture Image + Get GPS Coordinates
     ↓
Client: Compress Image (max 1920x1080, JPEG quality 85%)
     ↓
Upload to Supabase Storage (signed URL)
     ↓
POST to FastAPI ML Service
  - YOLOv8: Detect trees in image
  - ResNet: Classify species
  - Return: Bounding boxes + Species + Confidence
     ↓
Cache Results in Redis (5min TTL)
     ↓
POST to NestJS API
  - Validate data
  - Enrich with metadata
  - Store in PostgreSQL with PostGIS
     ↓
WebSocket/SSE: Notify connected clients
     ↓
Frontend: Update Map in Real-time
     ↓
Background Job: Calculate CO₂ impact
```

### Service Communication

```
┌──────────────────┐
│   Next.js 15     │
│   (Frontend)     │
└────────┬─────────┘
         │
    HTTP/REST
         │
    ┌────┴────┬───────────────┐
    │         │               │
┌───▼──┐  ┌──▼───┐     ┌─────▼────┐
│NestJS│  │FastAPI│    │ Supabase │
│ API  │  │  ML   │    │  (Auth+  │
│      │  │       │    │   Data)  │
└───┬──┘  └───┬──┘     └─────┬────┘
    │         │              │
    └────┬────┴──────────────┘
         │
    ┌────▼────┐
    │  Redis  │
    │  Cache  │
    └─────────┘
```

---

## Phase 1: Foundation (Weeks 1-4)

### Goal
Establish solid foundation with database, authentication, and core APIs.

### Sprint 1 (Weeks 1-2): Database & Auth

#### 1.1 Enhanced Database Schema with PostGIS

**Migration File**: `supabase/migrations/002_enhanced_schema.sql`

```sql
-- Enable PostGIS for spatial operations
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enhanced trees table
CREATE TABLE trees (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    species VARCHAR(255) NOT NULL,
    
    -- Spatial data (PostGIS GEOGRAPHY for accurate distance calculations)
    location GEOGRAPHY(POINT, 4326) NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    
    -- Tree characteristics
    estimated_age INTEGER CHECK (estimated_age >= 0 AND estimated_age <= 2000),
    height DECIMAL(10, 2) CHECK (height >= 0 AND height <= 150),
    canopy_diameter DECIMAL(10, 2) CHECK (canopy_diameter >= 0),
    root_spread DECIMAL(10, 2) CHECK (root_spread >= 0),
    dbh DECIMAL(10, 2), -- Diameter at breast height (cm)
    health_status VARCHAR(50) DEFAULT 'unknown' 
        CHECK (health_status IN ('healthy', 'good', 'fair', 'poor', 'dead', 'unknown')),
    
    -- Environmental data
    soil_type VARCHAR(100),
    soil_ph DECIMAL(4, 2) CHECK (soil_ph >= 0 AND soil_ph <= 14),
    elevation DECIMAL(10, 2),
    
    -- ML metadata
    detection_confidence DECIMAL(5, 4) CHECK (detection_confidence >= 0 AND detection_confidence <= 1),
    classification_confidence DECIMAL(5, 4) CHECK (classification_confidence >= 0 AND classification_confidence <= 1),
    image_url TEXT,
    thumbnail_url TEXT,
    detection_metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Ownership & audit
    user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified_at TIMESTAMP WITH TIME ZONE,
    verified_by UUID REFERENCES auth.users(id),
    
    -- Soft delete
    deleted_at TIMESTAMP WITH TIME ZONE,
    
    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(species, ''))
    ) STORED
);

-- Critical spatial index for map queries
CREATE INDEX idx_trees_location ON trees USING GIST (location);
CREATE INDEX idx_trees_lat_lng ON trees (latitude, longitude) WHERE deleted_at IS NULL;

-- Performance indexes
CREATE INDEX idx_trees_species ON trees (species) WHERE deleted_at IS NULL;
CREATE INDEX idx_trees_user_id ON trees (user_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_trees_created_at ON trees (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_trees_health ON trees (health_status) WHERE deleted_at IS NULL;
CREATE INDEX idx_trees_search ON trees USING GIN (search_vector);

-- Composite index for common query patterns
CREATE INDEX idx_trees_species_location ON trees (species, location) 
    WHERE deleted_at IS NULL;

-- Function: Automatically update location from lat/lng
CREATE OR REPLACE FUNCTION update_tree_location()
RETURNS TRIGGER AS $$
BEGIN
    NEW.location = ST_SetSRID(
        ST_MakePoint(NEW.longitude, NEW.latitude),
        4326
    )::geography;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_tree_location
    BEFORE INSERT OR UPDATE OF latitude, longitude ON trees
    FOR EACH ROW
    EXECUTE FUNCTION update_tree_location();

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_trees_timestamp
    BEFORE UPDATE ON trees
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- RLS Policies
ALTER TABLE trees ENABLE ROW LEVEL SECURITY;

-- Anyone can view non-deleted trees
CREATE POLICY "Trees viewable by everyone" ON trees
    FOR SELECT USING (deleted_at IS NULL);

-- Authenticated users can insert trees
CREATE POLICY "Users can insert trees" ON trees
    FOR INSERT 
    WITH CHECK (auth.uid() = user_id AND deleted_at IS NULL);

-- Users can update their own trees
CREATE POLICY "Users can update own trees" ON trees
    FOR UPDATE 
    USING (auth.uid() = user_id);

-- Users can soft delete their own trees
CREATE POLICY "Users can delete own trees" ON trees
    FOR UPDATE 
    USING (auth.uid() = user_id)
    WITH CHECK (deleted_at IS NOT NULL);

-- PostgreSQL function for viewport query
CREATE OR REPLACE FUNCTION trees_in_viewport(
    min_lat DECIMAL,
    max_lat DECIMAL,
    min_lng DECIMAL,
    max_lng DECIMAL,
    max_results INTEGER DEFAULT 200
)
RETURNS TABLE (
    id UUID,
    species VARCHAR,
    latitude DECIMAL,
    longitude DECIMAL,
    height DECIMAL,
    health_status VARCHAR,
    detection_confidence DECIMAL,
    image_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id,
        t.species,
        t.latitude,
        t.longitude,
        t.height,
        t.health_status,
        t.detection_confidence,
        t.thumbnail_url as image_url,
        t.created_at
    FROM trees t
    WHERE t.latitude BETWEEN min_lat AND max_lat
      AND t.longitude BETWEEN min_lng AND max_lng
      AND t.deleted_at IS NULL
    ORDER BY t.created_at DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql STABLE;

-- Function for radial search (trees nearby)
CREATE OR REPLACE FUNCTION trees_nearby(
    lat DECIMAL,
    lng DECIMAL,
    radius_meters INTEGER DEFAULT 5000
)
RETURNS TABLE (
    id UUID,
    species VARCHAR,
    latitude DECIMAL,
    longitude DECIMAL,
    distance_meters DOUBLE PRECISION,
    height DECIMAL,
    health_status VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        t.id,
        t.species,
        t.latitude,
        t.longitude,
        ST_Distance(
            t.location,
            ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography
        ) as distance_meters,
        t.height,
        t.health_status
    FROM trees t
    WHERE t.deleted_at IS NULL
      AND ST_DWithin(
          t.location,
          ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography,
          radius_meters
      )
    ORDER BY distance_meters ASC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql STABLE;

-- Additional tables
CREATE TABLE tree_images (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tree_id UUID REFERENCES trees(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    thumbnail_url TEXT,
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    uploaded_by UUID REFERENCES auth.users(id),
    is_primary BOOLEAN DEFAULT false,
    width INTEGER,
    height INTEGER,
    file_size_bytes INTEGER
);

CREATE INDEX idx_tree_images_tree_id ON tree_images (tree_id);
CREATE INDEX idx_tree_images_primary ON tree_images (tree_id, is_primary) 
    WHERE is_primary = true;

-- Detection jobs for async processing
CREATE TABLE detection_jobs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    image_url TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' 
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    result JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    user_id UUID REFERENCES auth.users(id),
    processing_time_ms INTEGER
);

CREATE INDEX idx_detection_jobs_status ON detection_jobs (status, created_at);
CREATE INDEX idx_detection_jobs_user ON detection_jobs (user_id, created_at DESC);

-- User profiles (extended)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name VARCHAR(255),
    avatar_url TEXT,
    bio TEXT,
    location VARCHAR(255),
    trees_mapped INTEGER DEFAULT 0,
    reputation_score INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Analytics events for tracking
CREATE TABLE analytics_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB DEFAULT '{}'::jsonb,
    user_id UUID REFERENCES auth.users(id),
    session_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_analytics_type ON analytics_events (event_type, created_at DESC);
CREATE INDEX idx_analytics_user ON analytics_events (user_id, created_at DESC);
CREATE INDEX idx_analytics_session ON analytics_events (session_id, created_at DESC);

-- Species lookup table
CREATE TABLE tree_species (
    id SERIAL PRIMARY KEY,
    common_name VARCHAR(255) NOT NULL,
    scientific_name VARCHAR(255) UNIQUE NOT NULL,
    family VARCHAR(255),
    description TEXT,
    native_regions TEXT[],
    avg_height_meters DECIMAL(10, 2),
    avg_lifespan_years INTEGER,
    co2_sequestration_kg_per_year DECIMAL(10, 2), -- Average CO2 captured per year
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_species_common ON tree_species (common_name);
CREATE INDEX idx_species_scientific ON tree_species (scientific_name);
```

**Testing Queries**:

```sql
-- Test viewport query
SELECT * FROM trees_in_viewport(37.7, 37.8, -122.5, -122.4, 100);

-- Test nearby search
SELECT * FROM trees_nearby(37.7749, -122.4194, 5000);

-- Test full-text search
SELECT id, species, latitude, longitude
FROM trees
WHERE search_vector @@ to_tsquery('english', 'oak | maple')
  AND deleted_at IS NULL
LIMIT 20;

-- Test spatial join (find trees near each other)
SELECT t1.id, t1.species, t2.species as nearby_species,
       ST_Distance(t1.location, t2.location) as distance
FROM trees t1
CROSS JOIN trees t2
WHERE t1.id != t2.id
  AND ST_DWithin(t1.location, t2.location, 100)
  AND t1.deleted_at IS NULL
  AND t2.deleted_at IS NULL
LIMIT 10;
```

#### 1.2 Authentication Implementation

**File**: `apps/web/src/middleware.ts`

```typescript
import { createServerClient, type CookieOptions } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return request.cookies.get(name)?.value;
        },
        set(name: string, value: string, options: CookieOptions) {
          request.cookies.set({
            name,
            value,
            ...options,
          });
          response = NextResponse.next({
            request: {
              headers: request.headers,
            },
          });
          response.cookies.set({
            name,
            value,
            ...options,
          });
        },
        remove(name: string, options: CookieOptions) {
          request.cookies.set({
            name,
            value: '',
            ...options,
          });
          response = NextResponse.next({
            request: {
              headers: request.headers,
            },
          });
          response.cookies.set({
            name,
            value: '',
            ...options,
          });
        },
      },
    }
  );

  // Refresh session if expired
  await supabase.auth.getSession();

  // Protected routes
  const protectedPaths = ['/dashboard', '/detect', '/profile'];
  const isProtectedPath = protectedPaths.some(path =>
    request.nextUrl.pathname.startsWith(path)
  );

  if (isProtectedPath) {
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session) {
      const redirectUrl = new URL('/auth/login', request.url);
      redirectUrl.searchParams.set('redirectTo', request.nextUrl.pathname);
      return NextResponse.redirect(redirectUrl);
    }
  }

  return response;
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
};
```

### Sprint 2 (Weeks 3-4): Core APIs

#### 1.3 NestJS Trees Service (Enhanced)

**File**: `apps/api/src/trees/trees.service.ts`

```typescript
import { Injectable, Inject, NotFoundException, BadRequestException } from '@nestjs/common';
import { SupabaseClient } from '@supabase/supabase-js';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { Cache } from 'cache-manager';
import { SUPABASE_CLIENT } from '../supabase/supabase.module';
import { CreateTreeDto } from './dto/create-tree.dto';

@Injectable()
export class TreesService {
  constructor(
    @Inject(SUPABASE_CLIENT)
    private readonly supabase: SupabaseClient,
    @Inject(CACHE_MANAGER)
    private cacheManager: Cache,
  ) {}

  async create(createTreeDto: CreateTreeDto, userId: string) {
    // Validate coordinates
    if (
      createTreeDto.latitude < -90 ||
      createTreeDto.latitude > 90 ||
      createTreeDto.longitude < -180 ||
      createTreeDto.longitude > 180
    ) {
      throw new BadRequestException('Invalid coordinates');
    }

    const { data, error } = await this.supabase
      .from('trees')
      .insert([{ ...createTreeDto, user_id: userId }])
      .select()
      .single();

    if (error) {
      throw new Error(`Failed to create tree: ${error.message}`);
    }

    // Invalidate cache for this area
    await this.invalidateRegionCache(
      createTreeDto.latitude,
      createTreeDto.longitude
    );

    return data;
  }

  async findInViewport(
    minLat: number,
    maxLat: number,
    minLng: number,
    maxLng: number,
    limit = 200
  ) {
    const cacheKey = `viewport:${minLat}:${maxLat}:${minLng}:${maxLng}:${limit}`;
    
    // Check cache first
    const cached = await this.cacheManager.get(cacheKey);
    if (cached) {
      return cached;
    }

    // Query database
    const { data, error } = await this.supabase.rpc('trees_in_viewport', {
      min_lat: minLat,
      max_lat: maxLat,
      min_lng: minLng,
      max_lng: maxLng,
      max_results: limit,
    });

    if (error) {
      throw new Error(`Failed to fetch trees: ${error.message}`);
    }

    // Cache for 30 seconds
    await this.cacheManager.set(cacheKey, data, 30000);

    return data;
  }

  async findNearby(latitude: number, longitude: number, radiusMeters = 5000) {
    const cacheKey = `nearby:${latitude}:${longitude}:${radiusMeters}`;
    
    const cached = await this.cacheManager.get(cacheKey);
    if (cached) {
      return cached;
    }

    const { data, error } = await this.supabase.rpc('trees_nearby', {
      lat: latitude,
      lng: longitude,
      radius_meters: radiusMeters,
    });

    if (error) {
      throw new Error(`Failed to fetch nearby trees: ${error.message}`);
    }

    // Cache for 60 seconds
    await this.cacheManager.set(cacheKey, data, 60000);

    return data;
  }

  async findOne(id: string) {
    const { data, error } = await this.supabase
      .from('trees')
      .select('*')
      .eq('id', id)
      .is('deleted_at', null)
      .single();

    if (error || !data) {
      throw new NotFoundException(`Tree with ID ${id} not found`);
    }

    return data;
  }

  async update(id: string, updateTreeDto: any, userId: string) {
    const { data, error } = await this.supabase
      .from('trees')
      .update(updateTreeDto)
      .eq('id', id)
      .eq('user_id', userId)
      .is('deleted_at', null)
      .select()
      .single();

    if (error || !data) {
      throw new NotFoundException(`Tree with ID ${id} not found or unauthorized`);
    }

    // Invalidate cache
    await this.invalidateRegionCache(data.latitude, data.longitude);

    return data;
  }

  async softDelete(id: string, userId: string) {
    const { data, error } = await this.supabase
      .from('trees')
      .update({ deleted_at: new Date().toISOString() })
      .eq('id', id)
      .eq('user_id', userId)
      .select()
      .single();

    if (error || !data) {
      throw new NotFoundException(`Tree with ID ${id} not found or unauthorized`);
    }

    await this.invalidateRegionCache(data.latitude, data.longitude);

    return { message: 'Tree deleted successfully' };
  }

  private async invalidateRegionCache(lat: number, lng: number) {
    // Invalidate cache in a 0.1 degree radius
    const keys = await this.cacheManager.store.keys();
    const pattern = new RegExp(`viewport:${lat.toFixed(1)}.*:${lng.toFixed(1)}`);
    
    for (const key of keys) {
      if (pattern.test(key)) {
        await this.cacheManager.del(key);
      }
    }
  }
}
```

**File**: `apps/api/src/trees/trees.controller.ts`

```typescript
import {
  Controller,
  Get,
  Post,
  Put,
  Delete,
  Body,
  Param,
  Query,
  UseGuards,
  Request,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiBearerAuth } from '@nestjs/swagger';
import { TreesService } from './trees.service';
import { CreateTreeDto } from './dto/create-tree.dto';
import { UpdateTreeDto } from './dto/update-tree.dto';
import { AuthGuard } from '../auth/auth.guard';

@ApiTags('trees')
@Controller('trees')
export class TreesController {
  constructor(private readonly treesService: TreesService) {}

  @Post()
  @UseGuards(AuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Create a new tree record' })
  @ApiResponse({ status: 201, description: 'Tree created successfully' })
  async create(@Body() createTreeDto: CreateTreeDto, @Request() req: any) {
    return this.treesService.create(createTreeDto, req.user.id);
  }

  @Get('viewport')
  @ApiOperation({ summary: 'Get trees within map viewport' })
  @ApiResponse({ status: 200, description: 'Returns trees in viewport' })
  async getTreesInViewport(
    @Query('minLat') minLat: number,
    @Query('maxLat') maxLat: number,
    @Query('minLng') minLng: number,
    @Query('maxLng') maxLng: number,
    @Query('limit') limit?: number,
  ) {
    return this.treesService.findInViewport(
      +minLat,
      +maxLat,
      +minLng,
      +maxLng,
      limit ? +limit : undefined
    );
  }

  @Get('nearby')
  @ApiOperation({ summary: 'Get trees near a location' })
  @ApiResponse({ status: 200, description: 'Returns nearby trees' })
  async getTreesNearby(
    @Query('lat') lat: number,
    @Query('lng') lng: number,
    @Query('radius') radius?: number,
  ) {
    return this.treesService.findNearby(+lat, +lng, radius ? +radius : undefined);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Get tree by ID' })
  @ApiResponse({ status: 200, description: 'Returns a single tree' })
  @ApiResponse({ status: 404, description: 'Tree not found' })
  async findOne(@Param('id') id: string) {
    return this.treesService.findOne(id);
  }

  @Put(':id')
  @UseGuards(AuthGuard)
  @ApiBearerAuth()
  @ApiOperation({ summary: 'Update tree' })
  @ApiResponse({ status: 200, description: 'Tree updated successfully' })
  async update(
    @Param('id') id: string,
    @Body() updateTreeDto: UpdateTreeDto,
    @Request() req: any,
  ) {
    return this.treesService.update(id, updateTreeDto, req.user.id);
  }

  @Delete(':id')
  @UseGuards(AuthGuard)
  @ApiBearerAuth()
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Delete tree' })
  @ApiResponse({ status: 204, description: 'Tree deleted successfully' })
  async remove(@Param('id') id: string, @Request() req: any) {
    return this.treesService.softDelete(id, req.user.id);
  }
}
```

**Redis Cache Configuration**:

**File**: `apps/api/src/app.module.ts` (add cache config)

```typescript
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { CacheModule } from '@nestjs/cache-manager';
import { redisStore } from 'cache-manager-redis-yet';
import type { RedisClientOptions } from 'redis';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '.env',
    }),
    CacheModule.registerAsync<RedisClientOptions>({
      isGlobal: true,
      useFactory: async () => ({
        store: await redisStore({
          socket: {
            host: process.env.REDIS_HOST || 'localhost',
            port: parseInt(process.env.REDIS_PORT || '6379'),
          },
        }),
        ttl: 60 * 1000, // Default 60 seconds
      }),
    }),
    // ... other modules
  ],
})
export class AppModule {}
```

### Phase 1 Checklist

- [ ] PostgreSQL with PostGIS extension enabled
- [ ] Database migrations applied successfully
- [ ] Spatial indexes verified with EXPLAIN ANALYZE
- [ ] Authentication flows working (Google OAuth, magic link, anonymous)
- [ ] Protected routes redirect to login
- [ ] NestJS CRUD API operational
- [ ] Viewport query returns results in <500ms
- [ ] Redis caching working
- [ ] File upload to Supabase Storage functional
- [ ] CI/CD pipeline deploying to staging
- [ ] Unit tests coverage >70%
- [ ] Integration tests passing

---

## Phase 2: ML Pipeline (Weeks 5-8)

### Goal
Implement tree detection and species classification using YOLOv8 and ResNet.

### Sprint 3 (Weeks 5-6): YOLOv8 Detection

#### 2.1 YOLOv8 Implementation

**File**: `apps/ml-api/services/detection_service.py`

```python
import torch
from ultralytics import YOLO
import numpy as np
import cv2
from typing import List, Dict, Tuple
import os
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class TreeDetectionService:
    """Service for detecting trees in images using YOLOv8"""
    
    def __init__(self):
        model_path = os.getenv('MODEL_YOLO_PATH', './models/yolov8n.pt')
        
        logger.info(f"Loading YOLOv8 model from {model_path}")
        self.model = YOLO(model_path)
        
        # Use GPU if available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        logger.info(f"Using device: {self.device}")
        
        # COCO class IDs for tree-like objects
        self.tree_classes = [60, 58, 62]  # tree, potted plant, bench (sometimes trees)
        
    async def detect_trees(
        self, 
        image: np.ndarray,
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45
    ) -> List[Dict]:
        """
        Detect trees in an image
        
        Args:
            image: Input image as numpy array (BGR format from OpenCV)
            confidence_threshold: Minimum confidence for detection (0-1)
            iou_threshold: IoU threshold for NMS
            
        Returns:
            List of detections with bounding boxes, confidence, and metadata
        """
        try:
            # Run inference
            results = self.model(
                image,
                conf=confidence_threshold,
                iou=iou_threshold,
                verbose=False
            )
            
            detections = []
            
            for result in results:
                boxes = result.boxes
                
                for box in boxes:
                    class_id = int(box.cls[0])
                    
                    # Filter for tree-like objects
                    if class_id in self.tree_classes:
                        bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                        
                        detection = {
                            'bbox': {
                                'x1': float(bbox[0]),
                                'y1': float(bbox[1]),
                                'x2': float(bbox[2]),
                                'y2': float(bbox[3]),
                                'width': float(bbox[2] - bbox[0]),
                                'height': float(bbox[3] - bbox[1]),
                            },
                            'confidence': float(box.conf[0]),
                            'class_id': class_id,
                            'class_name': result.names[class_id],
                        }
                        
                        detections.append(detection)
            
            logger.info(f"Detected {len(detections)} trees in image")
            return detections
            
        except Exception as e:
            logger.error(f"Detection failed: {str(e)}")
            raise
    
    def draw_detections(
        self, 
        image: np.ndarray, 
        detections: List[Dict],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels on image
        
        Args:
            image: Input image
            detections: List of detections from detect_trees()
            color: BGR color tuple for boxes
            thickness: Line thickness
            
        Returns:
            Annotated image
        """
        output = image.copy()
        
        for det in detections:
            bbox = det['bbox']
            x1, y1 = int(bbox['x1']), int(bbox['y1'])
            x2, y2 = int(bbox['x2']), int(bbox['y2'])
            confidence = det['confidence']
            
            # Draw rectangle
            cv2.rectangle(output, (x1, y1), (x2, y2), color, thickness)
            
            # Draw label background
            label = f"Tree {confidence:.2f}"
            (label_width, label_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            
            cv2.rectangle(
                output,
                (x1, y1 - label_height - baseline - 5),
                (x1 + label_width, y1),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                output,
                label,
                (x1, y1 - baseline - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                1
            )
        
        return output
    
    def crop_detection(
        self,
        image: np.ndarray,
        bbox: Dict
    ) -> np.ndarray:
        """
        Crop image to detection bounding box with padding
        
        Args:
            image: Input image
            bbox: Bounding box dictionary
            
        Returns:
            Cropped image region
        """
        h, w = image.shape[:2]
        
        # Add 10% padding
        padding = 0.1
        x1 = max(0, int(bbox['x1'] - bbox['width'] * padding))
        y1 = max(0, int(bbox['y1'] - bbox['height'] * padding))
        x2 = min(w, int(bbox['x2'] + bbox['width'] * padding))
        y2 = min(h, int(bbox['y2'] + bbox['height'] * padding))
        
        return image[y1:y2, x1:x2]
```

#### 2.2 Species Classification Service

**File**: `apps/ml-api/services/classification_service.py`

```python
import torch
import torchvision.transforms as transforms
from torchvision import models
import numpy as np
from PIL import Image
from typing import List, Dict
import os
import json
import logging

logger = logging.getLogger(__name__)

class TreeClassificationService:
    """Service for classifying tree species using ResNet"""
    
    def __init__(self):
        # Load model architecture
        self.model = models.resnet50(weights='IMAGENET1K_V2')
        
        # Load species metadata
        self.species_info = self.load_species_info()
        num_species = len(self.species_info)
        
        # Replace final layer for tree species
        self.model.fc = torch.nn.Linear(
            self.model.fc.in_features, 
            num_species
        )
        
        # Load fine-tuned weights if available
        model_path = os.getenv('MODEL_SPECIES_PATH', './models/species_classifier.pth')
        if os.path.exists(model_path):
            logger.info(f"Loading fine-tuned model from {model_path}")
            self.model.load_state_dict(torch.load(model_path, map_location='cpu'))
        else:
            logger.warning(f"Fine-tuned model not found at {model_path}, using base model")
        
        self.model.eval()
        
        # Use GPU if available
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model.to(self.device)
        logger.info(f"Classification model using device: {self.device}")
        
        # Image preprocessing pipeline
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
    
    def load_species_info(self) -> List[Dict]:
        """Load species metadata from JSON file"""
        species_file = './data/species.json'
        
        if os.path.exists(species_file):
            with open(species_file, 'r') as f:
                return json.load(f)
        else:
            # Default species list (will be replaced with actual data)
            logger.warning("Species file not found, using default list")
            return [
                {
                    "id": 0,
                    "common_name": "Oak Tree",
                    "scientific_name": "Quercus",
                    "avg_co2_kg_per_year": 21.8
                },
                {
                    "id": 1,
                    "common_name": "Maple Tree",
                    "scientific_name": "Acer",
                    "avg_co2_kg_per_year": 18.5
                },
                # ... more species
            ]
    
    async def classify_species(
        self, 
        image: np.ndarray,
        top_k: int = 5
    ) -> Dict:
        """
        Classify tree species from image
        
        Args:
            image: Input image as numpy array (BGR format)
            top_k: Number of top predictions to return
            
        Returns:
            Classification results with confidence scores
        """
        try:
            # Convert BGR to RGB and then to PIL Image
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image_pil = Image.fromarray(image_rgb)
            
            # Preprocess
            input_tensor = self.transform(image_pil).unsqueeze(0)
            input_tensor = input_tensor.to(self.device)
            
            # Inference
            with torch.no_grad():
                outputs = self.model(input_tensor)
                probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
            
            # Get top K predictions
            top_probs, top_indices = torch.topk(probabilities, min(top_k, len(self.species_info)))
            
            # Build result
            top_species = self.species_info[top_indices[0].item()]
            
            results = {
                'species': top_species['common_name'],
                'scientific_name': top_species.get('scientific_name', ''),
                'confidence': float(top_probs[0].item()),
                'avg_co2_kg_per_year': top_species.get('avg_co2_kg_per_year', 20.0),
                'alternatives': [
                    {
                        'species': self.species_info[idx.item()]['common_name'],
                        'scientific_name': self.species_info[idx.item()].get('scientific_name', ''),
                        'confidence': float(prob.item())
                    }
                    for prob, idx in zip(top_probs[1:], top_indices[1:])
                ]
            }
            
            logger.info(f"Classified as {results['species']} with confidence {results['confidence']:.2f}")
            return results
            
        except Exception as e:
            logger.error(f"Classification failed: {str(e)}")
            raise
```

#### 2.3 Updated FastAPI Main

**File**: `apps/ml-api/main.py` (Complete rewrite)

```python
import os
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import cv2
import numpy as np
from io import BytesIO
import uvicorn

from services.detection_service import TreeDetectionService
from services.classification_service import TreeClassificationService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="EcoTrack ML API",
    description="Machine Learning API for tree detection and species classification",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
detection_service = TreeDetectionService()
classification_service = TreeClassificationService()

# Pydantic models
class DetectionResult(BaseModel):
    bbox: dict
    confidence: float
    class_id: int
    class_name: str

class ClassificationResult(BaseModel):
    species: str
    scientific_name: str
    confidence: float
    avg_co2_kg_per_year: float
    alternatives: List[dict]

class DetectionResponse(BaseModel):
    detections: List[DetectionResult]
    count: int
    image_size: dict

# Routes
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "EcoTrack ML API is running",
        "version": "1.0.0",
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "models": {
            "tree_detection": "loaded",
            "species_classification": "loaded",
        },
        "device": detection_service.device,
    }

@app.post("/detect/trees", response_model=DetectionResponse)
async def detect_trees(
    file: UploadFile = File(...),
    confidence: float = Query(0.5, ge=0.0, le=1.0),
    return_image: bool = Query(False)
):
    """
    Detect trees in uploaded image using YOLOv8
    
    - **file**: Image file (JPEG, PNG)
    - **confidence**: Minimum confidence threshold (0-1)
    - **return_image**: If true, returns annotated image instead of JSON
    """
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Detect trees
        detections = await detection_service.detect_trees(
            image, 
            confidence_threshold=confidence
        )
        
        # Return results
        if return_image:
            # Draw detections and return annotated image
            annotated = detection_service.draw_detections(image, detections)
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return StreamingResponse(
                BytesIO(buffer.tobytes()),
                media_type="image/jpeg"
            )
        else:
            # Return JSON results
            return DetectionResponse(
                detections=detections,
                count=len(detections),
                image_size={
                    'width': image.shape[1],
                    'height': image.shape[0]
                }
            )
    
    except Exception as e:
        logger.error(f"Detection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

@app.post("/classify/species", response_model=ClassificationResult)
async def classify_species(
    file: UploadFile = File(...),
    top_k: int = Query(5, ge=1, le=10)
):
    """
    Classify tree species from uploaded image
    
    - **file**: Image file containing a tree
    - **top_k**: Number of top predictions to return
    """
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Classify species
        result = await classification_service.classify_species(image, top_k=top_k)
        
        return ClassificationResult(**result)
    
    except Exception as e:
        logger.error(f"Classification error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")

@app.post("/detect-and-classify")
async def detect_and_classify(
    file: UploadFile = File(...),
    confidence: float = Query(0.5, ge=0.0, le=1.0)
):
    """
    Complete pipeline: detect trees and classify each detection
    
    This endpoint combines tree detection and species classification
    """
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Detect trees
        detections = await detection_service.detect_trees(
            image,
            confidence_threshold=confidence
        )
        
        # Classify each detection
        results = []
        for detection in detections:
            # Crop to detection bbox
            cropped = detection_service.crop_detection(image, detection['bbox'])
            
            # Classify cropped region
            classification = await classification_service.classify_species(cropped, top_k=3)
            
            results.append({
                'detection': detection,
                'classification': classification
            })
        
        return {
            'count': len(results),
            'results': results
        }
    
    except Exception as e:
        logger.error(f"Pipeline error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )
```

### Sprint 4 (Weeks 7-8): Frontend Integration

#### 2.4 Complete Detection Workflow

See NEXT_STEPS.md for camera capture and detection page implementation.

### Phase 2 Checklist

- [ ] YOLOv8 model downloaded and loaded
- [ ] Detection endpoint returns bounding boxes
- [ ] Species classification model ready
- [ ] Classification accuracy >75% on test set
- [ ] Camera capture working on mobile
- [ ] Image upload and compression functional
- [ ] Complete detection workflow operational
- [ ] ML API performance: <3s response time
- [ ] Error handling for failed detections
- [ ] Unit tests for ML services
- [ ] Integration tests for complete pipeline

---

## Phase 3: Geospatial & Mapping (Weeks 9-12)

### Goal
Interactive map with real-time tree visualization and spatial analytics.

### Sprint 5 (Weeks 9-10): Map Implementation

See NEXT_STEPS.md and earlier sections for:
- TreeMap component with React Leaflet
- Marker clustering
- Viewport-based loading
- Spatial query optimization

### Sprint 6 (Weeks 11-12): Analytics Dashboard

See earlier sections for:
- Dashboard with statistics
- Species distribution charts
- CO₂ impact estimation
- User activity tracking

### Phase 3 Checklist

- [ ] Interactive map with tree markers
- [ ] Marker clustering for performance
- [ ] Viewport queries optimized (<500ms)
- [ ] Redis caching working
- [ ] Dashboard showing user statistics
- [ ] CO₂ estimation algorithm implemented
- [ ] Species distribution charts
- [ ] Real-time updates via WebSocket/SSE

---

## Phase 4: Production Ready (Weeks 13-16)

### Goal
Production deployment, monitoring, and optimization.

### Sprint 7 (Weeks 13-14): Deployment

#### 4.1 Deployment Checklist

**Frontend (Vercel)**:
```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
cd apps/web
vercel --prod
```

**Backend (Railway)**:
```bash
# Install Railway CLI
npm i -g @railway/cli

# Deploy
cd apps/api
railway up
```

**ML API (Fly.io)**:
```bash
# Deploy
cd apps/ml-api
fly deploy
```

#### 4.2 Environment Variables

Set in production:
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_KEY`
- `REDIS_HOST` and `REDIS_PORT`
- `ML_API_URL`

### Sprint 8 (Weeks 15-16): Monitoring

#### 4.3 Monitoring Setup

**Frontend Monitoring** (Vercel Analytics):
- Already integrated
- Monitor Core Web Vitals

**Backend Monitoring** (Sentry):

```typescript
// apps/api/src/main.ts
import * as Sentry from "@sentry/node";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
});
```

**ML API Monitoring**:

```python
# apps/ml-api/main.py
from sentry_sdk.integrations.fastapi import FastApiIntegration
import sentry_sdk

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("PYTHON_ENV", "development"),
    traces_sample_rate=1.0,
    integrations=[FastApiIntegration()],
)
```

#### 4.4 Performance Optimization

1. **Database Query Optimization**:
   - Add EXPLAIN ANALYZE to slow queries
   - Optimize spatial indexes
   - Consider materialized views for analytics

2. **Caching Strategy**:
   - Viewport queries: 30s TTL
   - Nearby queries: 60s TTL
   - User stats: 5min TTL

3. **Image Optimization**:
   - Client-side compression
   - Thumbnail generation
   - CDN for image delivery

4. **API Rate Limiting**:

```typescript
// apps/api/src/main.ts
import rateLimit from 'express-rate-limit';

app.use(
  rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100, // limit each IP to 100 requests per windowMs
  })
);
```

### Phase 4 Checklist

- [ ] All services deployed to production
- [ ] SSL certificates configured
- [ ] Monitoring and alerting set up
- [ ] Error tracking with Sentry
- [ ] Performance monitoring active
- [ ] Backup strategy implemented
- [ ] Rate limiting configured
- [ ] Security headers set
- [ ] Load testing completed
- [ ] Documentation updated

---

## Technical Integration Points

### Next.js ↔ NestJS
- HTTP REST API
- Authentication via Supabase JWT
- Error handling with try/catch
- TypeScript types shared via packages

### Next.js ↔ FastAPI
- HTTP REST for ML operations
- File upload via FormData
- Async operations with loading states
- Error handling for ML failures

### NestJS ↔ Supabase
- Supabase client for database operations
- RLS policies enforce security
- Real-time subscriptions for updates
- Storage for file management

### NestJS ↔ Redis
- Cache-Manager integration
- Session storage
- Rate limiting data
- ML result caching

### FastAPI ↔ Redis (Future)
- Model result caching
- Queue for async processing
- Rate limiting

---

## Database Architecture

### Key Design Decisions

1. **PostGIS for Spatial Data**:
   - GEOGRAPHY type for accurate distance calculations
   - GIST indexes for fast spatial queries
   - Native PostgreSQL functions for common operations

2. **Row Level Security**:
   - Users can only modify their own trees
   - Public read access for all non-deleted trees
   - Admin role for verification

3. **Soft Deletes**:
   - Preserve data for analytics
   - Easy to restore accidentally deleted trees
   - Filter out in queries with WHERE deleted_at IS NULL

4. **JSONB for Flexibility**:
   - detection_metadata for ML-specific data
   - Easy to add new fields without migrations
   - Supports complex queries

---

## Monitoring & Observability

### Metrics to Track

**Application Metrics**:
- Request rate (requests/second)
- Response time (p50, p95, p99)
- Error rate (%)
- Active users

**Business Metrics**:
- Trees mapped per day
- Species distribution
- User retention
- Detection accuracy

**Infrastructure Metrics**:
- CPU usage
- Memory usage
- Database connections
- Cache hit rate

### Alerting

Set up alerts for:
- Error rate > 5%
- Response time p95 > 3s
- Database CPU > 80%
- Cache hit rate < 70%

---

## Dataset Preparation

### YOLOv8 Training Data

**Sources**:
1. iNaturalist: 1M+ tree images
2. PlantCLEF: Large-scale dataset
3. Custom data: Crowdsourced from app

**Labeling**:
- Use Label Studio or CVAT
- Bounding boxes around trees
- Minimum 1000 images per species

**Training**:
```python
from ultralytics import YOLO

# Load base model
model = YOLO('yolov8n.pt')

# Train on custom dataset
results = model.train(
    data='tree_dataset.yaml',
    epochs=100,
    imgsz=640,
    batch=16,
    patience=10,
)
```

### Species Classification Data

**Dataset Structure**:
```
data/
  species/
    oak/
      oak_001.jpg
      oak_002.jpg
    maple/
      maple_001.jpg
    ...
```

**Augmentation**:
- Random rotation
- Random brightness/contrast
- Random crop
- Horizontal flip

---

## Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| ML model accuracy <80% | High | Use pre-trained models, fine-tune on quality data |
| Spatial queries slow | High | Optimize indexes, implement caching |
| Camera not working on iOS | Medium | Use polyfills, test on multiple devices |
| Supabase rate limits | Medium | Implement Redis caching, optimize queries |
| Image upload failures | Low | Retry logic, better error messages |

### Business Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Low user adoption | High | Marketing, user testing, feedback loops |
| Poor data quality | Medium | Verification system, community moderation |
| Cost overruns | Medium | Monitor usage, optimize resources |

---

## Success Criteria

### Phase 1
- ✅ All developers can run project locally
- ✅ Database migrations apply successfully
- ✅ Authentication working
- ✅ API endpoints functional

### Phase 2
- ✅ Tree detection >80% accuracy
- ✅ Species classification >75% accuracy
- ✅ Camera capture works on mobile
- ✅ Complete workflow saves trees

### Phase 3
- ✅ Map loads trees in viewport
- ✅ Spatial queries <500ms
- ✅ Dashboard shows statistics
- ✅ CO₂ estimation functional

### Phase 4
- ✅ Deployed to production
- ✅ Monitoring active
- ✅ <2s page load time
- ✅ 99.5% uptime

---

## Next Actions

1. **Week 1**: Run `npm install`, set up Supabase, apply migrations
2. **Week 2**: Implement authentication, test protected routes
3. **Week 3**: Build NestJS CRUD API with Redis caching
4. **Week 4**: File upload pipeline, integration tests
5. **Week 5**: Download YOLOv8, implement detection service
6. **Week 6**: Train/fine-tune species classifier
7. **Week 7**: Build camera capture component
8. **Week 8**: Complete detection workflow page
9. **Week 9**: Implement interactive map
10. **Week 10**: Optimize spatial queries
11. **Week 11**: Build analytics dashboard
12. **Week 12**: CO₂ estimation and charts
13. **Week 13**: Deploy to production
14. **Week 14**: Performance optimization
15. **Week 15**: Monitoring setup
16. **Week 16**: Load testing and final polish

---

## Conclusion

This implementation strategy provides a clear, actionable path from foundation to production. Each phase delivers tangible value and can be tested independently. The modular architecture ensures components can evolve without breaking the system.

**Remember**: Start small, iterate quickly, and always keep the user experience at the forefront.

🌱 **Let's build EcoTrack and make an impact on climate change!**
