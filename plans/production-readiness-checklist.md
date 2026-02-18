# EcoTrack Production Readiness Checklist

## Executive Summary

This document identifies **67 critical gaps** that must be addressed before deploying EcoTrack to production. It covers security vulnerabilities, missing testing infrastructure, compliance requirements, operational procedures, and architectural improvements needed for a production-ready ecological intelligence platform.

**Priority Levels**:
- 🔴 **CRITICAL** (28 items): Must be implemented before production
- 🟡 **HIGH** (24 items): Should be implemented in first production release  
- 🟢 **MEDIUM** (15 items): Can be implemented post-launch but planned

**Current Production Readiness**: 35% (Foundation complete, production hardening needed)

---

## 1. Security Gaps (12 Critical Issues)

### 🔴 CRITICAL Security Issues

#### 1.1 No Security Headers Configured
**Impact**: Vulnerable to XSS, clickjacking, MIME sniffing attacks  
**Fix Required**: Add security headers to Next.js

```typescript
// apps/web/next.config.ts - ADD THIS
const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Permissions-Policy', value: 'camera=*, geolocation=*, microphone=()' },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob: https:",
              "connect-src 'self' https://*.supabase.co",
            ].join('; '),
          },
        ],
      },
    ];
  },
};
```

**Test**: Run `curl -I https://your-domain.com` and verify headers present

#### 1.2 No Rate Limiting Implemented
**Impact**: Vulnerable to DoS attacks, API abuse  
**Fix Required**:

```bash
cd apps/api
npm install @nestjs/throttler
```

```typescript
// apps/api/src/app.module.ts
import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler';
import { APP_GUARD } from '@nestjs/core';

@Module({
  imports: [
    ThrottlerModule.forRoot({
      ttl: 60,
      limit: 100, // 100 requests per minute per IP
    }),
  ],
  providers: [
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,
    },
  ],
})
```

**Test**: Make 101 requests in 60 seconds, verify 101st is rejected

#### 1.3 No Input Sanitization
**Impact**: XSS vulnerabilities in user-generated content  
**Fix Required**:

```bash
cd apps/web
npm install dompurify
npm install --save-dev @types/dompurify
```

```typescript
// apps/web/src/lib/sanitize.ts
import DOMPurify from 'dompurify';

export function sanitizeHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br'],
    ALLOWED_ATTR: [],
  });
}

// Usage: Always sanitize before rendering user content
<div dangerouslySetInnerHTML={{ __html: sanitizeHtml(userInput) }} />
```

#### 1.4 No Environment Variable Validation
**Impact**: Silent failures if env vars missing, security risks  
**Fix Required**:

```typescript
// apps/api/src/config/env.validation.ts
import { plainToInstance } from 'class-transformer';
import { IsString, IsUrl, validateSync } from 'class-validator';

class EnvironmentVariables {
  @IsUrl({ require_tld: false })
  SUPABASE_URL: string;

  @IsString()
  SUPABASE_SERVICE_KEY: string;

  @IsString()
  REDIS_HOST: string;

  @IsString()
  NODE_ENV: string;
}

export function validate(config: Record<string, unknown>) {
  const validatedConfig = plainToInstance(EnvironmentVariables, config, {
    enableImplicitConversion: true,
  });
  
  const errors = validateSync(validatedConfig, {
    skipMissingProperties: false,
  });

  if (errors.length > 0) {
    throw new Error(`Config validation error: ${errors.toString()}`);
  }
  
  return validatedConfig;
}

// apps/api/src/app.module.ts
ConfigModule.forRoot({
  validate,
})
```

#### 1.5 CORS Too Permissive in Development
**Impact**: Production deployment might inherit dev CORS settings  
**Fix Required**:

```typescript
// apps/api/src/main.ts
app.enableCors({
  origin: process.env.NODE_ENV === 'production' 
    ? [process.env.FRONTEND_URL!] 
    : true,
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
  allowedHeaders: ['Content-Type', 'Authorization'],
});
```

#### 1.6 No File Upload Validation
**Impact**: Malicious files could be uploaded  
**Fix Required**:

```typescript
// apps/web/src/lib/file-validation.ts
const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export async function validateImageFile(file: File): Promise<void> {
  // Check MIME type
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
    throw new Error('Invalid file type. Only JPEG, PNG, and WebP allowed.');
  }
  
  // Check file size
  if (file.size > MAX_FILE_SIZE) {
    throw new Error('File too large. Maximum size is 10MB.');
  }
  
  // Check magic number (first bytes)
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer.slice(0, 4));
  
  const jpeg = bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  const png = bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;
  const webp = bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46;
  
  if (!(jpeg || png || webp)) {
    throw new Error('File content does not match declared type.');
  }
}
```

### 🟡 HIGH Priority Security

#### 1.7 No Secrets Management Strategy
**Current**: Using `.env` files  
**Recommended**: Use platform secrets (Vercel Env Vars, Railway Secrets)

#### 1.8 No Token Refresh Mechanism
**Impact**: Users forced to re-login frequently  
**Fix**:

```typescript
// apps/web/src/lib/auth.ts
export async function refreshSession() {
  const supabase = createClient();
  const { data, error } = await supabase.auth.refreshSession();
  
  if (error) {
    window.location.href = '/auth/login';
    return null;
  }
  
  return data.session;
}

// Call this on app startup or when detecting expired token
```

#### 1.9 No Dependency Vulnerability Scanning
**Fix**: Add GitHub Action

```yaml
# .github/workflows/security.yml
name: Security Scan
on: [push, pull_request]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm audit --audit-level=high
      - run: npm run lint
```

#### 1.10 No HTTPS Enforcement
**Current**: Relies on platform  
**Action**: Verify HTTPS redirect configured in production

### 🟢 MEDIUM Priority Security

#### 1.11 No License Compliance Check
**Fix**:

```bash
npm install -g license-checker
license-checker --summary --production
```

#### 1.12 No DDoS Protection
**Recommended**: Enable Cloudflare proxy or platform DDoS protection

---

## 2. Testing Strategy Gaps (5 Critical Issues)

### 🔴 CRITICAL Testing Gaps

#### 2.1 ZERO Test Files Exist
**Impact**: No confidence in code quality, high risk of bugs  
**Current Coverage**: 0%  
**Target**: 70% minimum

**Action Required**:

```bash
# Install test dependencies
cd apps/api
npm install -D @nestjs/testing jest @types/jest ts-jest supertest

cd apps/web
npm install -D @testing-library/react @testing-library/jest-dom jest-environment-jsdom @types/jest
```

**Unit Test Example**:

```typescript
// apps/api/src/trees/trees.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { TreesService } from './trees.service';

describe('TreesService', () => {
  let service: TreesService;
  let mockSupabase: any;

  beforeEach(async () => {
    mockSupabase = {
      from: jest.fn().mockReturnThis(),
      insert: jest.fn().mockReturnThis(),
      select: jest.fn().mockReturnThis(),
      single: jest.fn().mockResolvedValue({ data: mockTree, error: null }),
    };

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        TreesService,
        { provide: 'SUPABASE_CLIENT', useValue: mockSupabase },
        { provide: 'CACHE_MANAGER', useValue: mockCacheManager },
      ],
    }).compile();

    service = module.get<TreesService>(TreesService);
  });

  it('should create a tree', async () => {
    const dto = { species: 'Oak', latitude: 37.7749, longitude: -122.4194 };
    const result = await service.create(dto, 'user-id');
    
    expect(result).toHaveProperty('id');
    expect(result.species).toBe('Oak');
  });

  it('should reject invalid coordinates', async () => {
    const dto = { species: 'Oak', latitude: 91, longitude: -122.4194 };
    await expect(service.create(dto, 'user-id')).rejects.toThrow();
  });
});
```

**Integration Test Example**:

```typescript
// apps/api/test/trees.e2e-spec.ts
import { Test } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from '../src/app.module';

describe('Trees API (e2e)', () => {
  let app: INestApplication;
  let authToken: string;

  beforeAll(async () => {
    const moduleFixture = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    await app.init();

    // Get auth token
    authToken = await getTestAuthToken();
  });

  it('/trees (POST) should create tree', () => {
    return request(app.getHttpServer())
      .post('/trees')
      .set('Authorization', `Bearer ${authToken}`)
      .send({
        species: 'Oak',
        latitude: 37.7749,
        longitude: -122.4194,
      })
      .expect(201)
      .expect((res) => {
        expect(res.body).toHaveProperty('id');
        expect(res.body.species).toBe('Oak');
      });
  });

  it('/trees/viewport (GET) should return trees in bounds', () => {
    return request(app.getHttpServer())
      .get('/trees/viewport')
      .query({ minLat: 37, maxLat: 38, minLng: -123, maxLng: -122 })
      .expect(200)
      .expect((res) => {
        expect(Array.isArray(res.body)).toBe(true);
      });
  });

  afterAll(async () => {
    await app.close();
  });
});
```

#### 2.2 No E2E Tests for Critical Flows
**Impact**: User-facing features untested  
**Fix**: Add Playwright tests

```bash
npm install -D @playwright/test
```

```typescript
// apps/web/tests/e2e/detection-flow.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Tree Detection Flow', () => {
  test('complete detection workflow', async ({ page }) => {
    // Login
    await page.goto('/auth/login');
    await page.fill('[name="email"]', 'test@example.com');
    await page.click('[type="submit"]');
    
    // Navigate to detect page
    await page.goto('/detect');
    
    // Upload image
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('./test-fixtures/oak-tree.jpg');
    
    // Wait for detection
    await page.waitForSelector('[data-testid="detection-result"]', {
      timeout: 10000,
    });
    
    // Verify species
    const species = await page.locator('[data-testid="species-name"]').textContent();
    expect(species).toBeTruthy();
    
    // Save tree
    await page.click('[data-testid="save-button"]');
    
    // Verify redirect to map
    await expect(page).toHaveURL('/map');
    
    // Verify tree appears on map
    await page.waitForSelector('[data-testid="tree-marker"]');
  });
});
```

#### 2.3 No Load Testing
**Impact**: Don't know performance under load  
**Fix**:

```bash
npm install -D artillery
```

```yaml
# load-test.yml
config:
  target: "https://api.ecotrack.com"
  phases:
    - duration: 60
      arrivalRate: 10
      name: "Warm up"
    - duration: 120
      arrivalRate: 50
      name: "Sustained load"
    - duration: 60
      arrivalRate: 100
      name: "Peak load"
scenarios:
  - name: "Get trees in viewport"
    flow:
      - get:
          url: "/trees/viewport?minLat=37&maxLat=38&minLng=-123&maxLng=-122"
          
  - name: "Create tree"
    flow:
      - post:
          url: "/trees"
          headers:
            Authorization: "Bearer {{$randomString()}}"
          json:
            species: "Oak"
            latitude: 37.7749
            longitude: -122.4194
```

Run: `artillery run load-test.yml`

### 🟡 HIGH Priority Testing

#### 2.4 No ML Model Accuracy Testing
**Fix**:

```python
# apps/ml-api/tests/test_detection_accuracy.py
import pytest
from services.detection_service import TreeDetectionService

def test_detection_accuracy():
    service = TreeDetectionService()
    test_dataset = load_labeled_test_images()
    
    correct = 0
    total = len(test_dataset)
    
    for image, expected_count in test_dataset:
        detections = service.detect_trees(image, confidence_threshold=0.5)
        if len(detections) == expected_count:
            correct += 1
    
    accuracy = correct / total
    assert accuracy >= 0.80, f"Detection accuracy {accuracy:.2%} below 80% threshold"

def test_classification_accuracy():
    service = TreeClassificationService()
    test_dataset = load_labeled_species_images()
    
    correct = 0
    total = len(test_dataset)
    
    for image, expected_species in test_dataset:
        result = service.classify_species(image)
        if result['species'] == expected_species:
            correct += 1
    
    accuracy = correct / total
    assert accuracy >= 0.75, f"Classification accuracy {accuracy:.2%} below 75% threshold"
```

#### 2.5 No Visual Regression Testing
**Recommended**: Add Storybook + Chromatic

### 🟢 MEDIUM Priority Testing

#### 2.6 No Accessibility Testing
**Recommended**: Add pa11y or axe-core tests

---

## 3. Error Handling & Resilience (6 Critical Issues)

### 🔴 CRITICAL Error Handling Gaps

#### 3.1 No Global Error Boundary
**Impact**: Unhandled errors crash the app  
**Fix**:

```typescript
// apps/web/src/app/error.tsx
'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/button';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to error tracking service
    console.error('Application error:', error);
    // TODO: Send to Sentry
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-4">
      <h2 className="text-2xl font-bold mb-4">Something went wrong!</h2>
      <p className="text-gray-600 mb-4">
        We've been notified and are working on it.
      </p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
```

```typescript
// apps/web/src/app/global-error.tsx
'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body>
        <h2>Application Error</h2>
        <button onClick={reset}>Try again</button>
      </body>
    </html>
  );
}
```

#### 3.2 No Standardized API Error Responses
**Impact**: Inconsistent error handling  
**Fix**:

```typescript
// apps/api/src/common/filters/http-exception.filter.ts
import { ExceptionFilter, Catch, ArgumentsHost, HttpException, HttpStatus } from '@nestjs/common';
import { Request, Response } from 'express';

@Catch(HttpException)
export class HttpExceptionFilter implements ExceptionFilter {
  catch(exception: HttpException, host: ArgumentsHost) {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request>();
    const status = exception.getStatus();
    const exceptionResponse = exception.getResponse();

    const errorResponse = {
      statusCode: status,
      timestamp: new Date().toISOString(),
      path: request.url,
      method: request.method,
      message: typeof exceptionResponse === 'string' 
        ? exceptionResponse 
        : (exceptionResponse as any).message || 'Internal server error',
      error: exception.name,
      ...(process.env.NODE_ENV === 'development' && {
        stack: exception.stack,
      }),
    };

    // Log error
    console.error('[HTTP Exception]', errorResponse);

    response.status(status).json(errorResponse);
  }
}

// Register in main.ts
app.useGlobalFilters(new HttpExceptionFilter());
```

#### 3.3 No Retry Logic for Failed Requests
**Impact**: Transient network failures cause permanent failures  
**Fix**:

```typescript
// apps/web/src/lib/api-client.ts
export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  maxRetries = 3,
  backoffMs = 1000
): Promise<Response> {
  let lastError: Error;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);
      
      // Success
      if (response.ok) {
        return response;
      }
      
      // Don't retry client errors (4xx)
      if (response.status >= 400 && response.status < 500) {
        throw new Error(`Client error ${response.status}: ${response.statusText}`);
      }
      
      // Retry server errors (5xx) and network errors
      lastError = new Error(`Server error ${response.status}: ${response.statusText}`);
      
    } catch (error) {
      lastError = error as Error;
      
      // Don't retry on last attempt
      if (attempt === maxRetries) {
        break;
      }
    }
    
    // Exponential backoff: 1s, 2s, 4s
    const delay = backoffMs * Math.pow(2, attempt);
    await new Promise(resolve => setTimeout(resolve, delay));
    
    console.log(`Retrying request (attempt ${attempt + 1}/${maxRetries})...`);
  }
  
  throw lastError!;
}

// Usage
const response = await fetchWithRetry('/api/trees', { method: 'GET' });
```

#### 3.4 No Circuit Breaker for ML Service
**Impact**: Cascading failures if ML service is down  
**Fix**:

```typescript
// apps/api/src/common/circuit-breaker.ts
export class CircuitBreaker {
  private failureCount = 0;
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private nextAttempt = Date.now();

  constructor(
    private threshold: number = 5,
    private timeout: number = 60000, // 60 seconds
    private name: string = 'Circuit'
  ) {}

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() < this.nextAttempt) {
        throw new Error(`${this.name} circuit breaker is OPEN`);
      }
      this.state = 'HALF_OPEN';
      console.log(`${this.name} circuit breaker entering HALF_OPEN state`);
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess() {
    this.failureCount = 0;
    if (this.state === 'HALF_OPEN') {
      console.log(`${this.name} circuit breaker closing`);
      this.state = 'CLOSED';
    }
  }

  private onFailure() {
    this.failureCount++;
    
    if (this.failureCount >= this.threshold) {
      console.error(`${this.name} circuit breaker opening after ${this.failureCount} failures`);
      this.state = 'OPEN';
      this.nextAttempt = Date.now() + this.timeout;
    }
  }

  getState() {
    return {
      state: this.state,
      failures: this.failureCount,
      nextAttempt: this.state === 'OPEN' ? new Date(this.nextAttempt) : null,
    };
  }
}

// Usage in ML service
const mlCircuitBreaker = new CircuitBreaker(5, 60000, 'ML Service');

async function callMLService(imageUrl: string) {
  return mlCircuitBreaker.execute(async () => {
    const response = await fetch(`${ML_API_URL}/detect/trees`, {
      method: 'POST',
      body: JSON.stringify({ image_url: imageUrl }),
    });
    
    if (!response.ok) {
      throw new Error('ML service error');
    }
    
    return response.json();
  });
}
```

#### 3.5 No Graceful Degradation
**Impact**: App completely breaks if ML service is down  
**Fix**: Allow manual species entry as fallback

```typescript
// apps/web/src/app/detect/page.tsx
const handleMLFailure = () => {
  setShowManualEntry(true);
  toast({
    title: 'Detection unavailable',
    description: 'Please enter tree details manually',
    variant: 'warning',
  });
};

try {
  const mlResult = await detectTree(image);
  setDetectionResult(mlResult);
} catch (error) {
  handleMLFailure();
}
```

#### 3.6 No Request Timeout Configuration
**Impact**: Hanging requests consume resources  
**Fix**:

```typescript
// apps/api/src/main.ts
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  
  // Set global timeout
  app.use((req, res, next) => {
    req.setTimeout(30000); // 30 seconds
    res.setTimeout(30000);
    next();
  });
  
  await app.listen(3001);
}
```

### 🟡 HIGH Priority Error Handling

#### 3.7 No Dead Letter Queue for Failed Jobs
**Recommended**: Implement job queue with DLQ for async tasks

#### 3.8 No Database Connection Pool Monitoring
**Action**: Monitor Supabase connection usage

---

## 4. Monitoring & Observability (6 Critical Issues)

### 🔴 CRITICAL Monitoring Gaps

#### 4.1 No Application Performance Monitoring (APM)
**Impact**: Can't diagnose production issues  
**Fix**: Add Sentry

```bash
npm install @sentry/nextjs @sentry/node
```

```typescript
// apps/web/sentry.client.config.ts
import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,
  integrations: [
    new Sentry.BrowserTracing(),
    new Sentry.Replay({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
});
```

```typescript
// apps/api/src/main.ts
import * as Sentry from '@sentry/node';
import '@sentry/tracing';

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 1.0,
  integrations: [
    new Sentry.Integrations.Http({ tracing: true }),
  ],
});

// Add request handler
app.use(Sentry.Handlers.requestHandler());
app.use(Sentry.Handlers.tracingHandler());

// Add error handler (after routes)
app.use(Sentry.Handlers.errorHandler());
```

**Cost**: Free tier: 5K events/month

#### 4.2 No Structured Logging
**Impact**: Logs not searchable or parseable  
**Fix**:

```bash
cd apps/api
npm install winston nest-winston
```

```typescript
// apps/api/src/config/logger.config.ts
import { WinstonModule } from 'nest-winston';
import * as winston from 'winston';

export const loggerConfig = WinstonModule.createLogger({
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.errors({ stack: true }),
        winston.format.json(),
      ),
    }),
    // In production, also log to file or service
    ...(process.env.NODE_ENV === 'production'
      ? [
          new winston.transports.File({
            filename: 'logs/error.log',
            level: 'error',
            format: winston.format.json(),
          }),
          new winston.transports.File({
            filename: 'logs/combined.log',
            format: winston.format.json(),
          }),
        ]
      : []),
  ],
});

// Usage
this.logger.log('Tree created', {
  userId,
  treeId: result.id,
  species: result.species,
  timestamp: new Date().toISOString(),
});
```

#### 4.3 No Health Check Endpoints
**Current**: Basic health check exists  
**Required**: Comprehensive health checks

```bash
cd apps/api
npm install @nestjs/terminus
```

```typescript
// apps/api/src/health/health.controller.ts
import { Controller, Get } from '@nestjs/common';
import {
  HealthCheck,
  HealthCheckService,
  HttpHealthIndicator,
  MemoryHealthIndicator,
} from '@nestjs/terminus';

@Controller('health')
export class HealthController {
  constructor(
    private health: HealthCheckService,
    private http: HttpHealthIndicator,
    private memory: MemoryHealthIndicator,
  ) {}

  @Get()
  @HealthCheck()
  check() {
    return this.health.check([
      // Check database
      () => this.checkDatabase(),
      
      // Check ML service
      () => this.http.pingCheck(
        'ml-service',
        `${process.env.ML_API_URL}/health`,
      ),
      
      // Check memory usage
      () => this.memory.checkHeap('memory_heap', 150 * 1024 * 1024), // 150MB
      () => this.memory.checkRSS('memory_rss', 150 * 1024 * 1024),
    ]);
  }

  private async checkDatabase() {
    try {
      const { data, error } = await this.supabase
        .from('trees')
        .select('count')
        .limit(1);
      
      return {
        database: {
          status: error ? 'down' : 'up',
        },
      };
    } catch (e) {
      return {
        database: {
          status: 'down',
          error: e.message,
        },
      };
    }
  }
}
```

**Add to module**:

```typescript
// apps/api/src/app.module.ts
import { TerminusModule } from '@nestjs/terminus';
import { HttpModule } from '@nestjs/axios';
import { HealthController } from './health/health.controller';

@Module({
  imports: [
    TerminusModule,
    HttpModule,
    // ...
  ],
  controllers: [HealthController],
})
```

#### 4.4 No Metrics Collection
**Impact**: Can't track business KPIs  
**Fix**:

```typescript
// apps/api/src/common/metrics.service.ts
import { Injectable } from '@nestjs/common';

@Injectable()
export class MetricsService {
  private metrics = new Map<string, number>();

  increment(metric: string, value: number = 1) {
    const current = this.metrics.get(metric) || 0;
    this.metrics.set(metric, current + value);
    
    // In production, send to monitoring service
    // (DataDog, New Relic, CloudWatch, etc.)
  }

  gauge(metric: string, value: number) {
    this.metrics.set(metric, value);
  }

  getMetrics() {
    return Object.fromEntries(this.metrics);
  }

  // Convenience methods
  incrementTreesCreated() {
    this.increment('trees.created');
  }

  incrementDetectionRequests() {
    this.increment('ml.detection_requests');
  }

  incrementApiErrors() {
    this.increment('api.errors');
  }

  setActiveUsers(count: number) {
    this.gauge('users.active', count);
  }
}

// Add metrics endpoint
@Controller('metrics')
export class MetricsController {
  constructor(private metricsService: MetricsService) {}

  @Get()
  getMetrics() {
    return this.metricsService.getMetrics();
  }
}
```

#### 4.5 No Real-Time Alerting
**Impact**: Don't know when things break  
**Required**: Configure alerts

```yaml
# alerts-config.yml (Pseudocode for monitoring service)
alerts:
  - name: HighErrorRate
    condition: error_rate > 5%
    duration: 5m
    severity: critical
    channels: [email, slack]
    message: "Error rate is {{value}}%"
    
  - name: SlowAPIResponse
    condition: p95_response_time > 3s
    duration: 10m
    severity: warning
    channels: [slack]
    
  - name: HighMemoryUsage
    condition: memory_usage > 80%
    duration: 5m
    severity: warning
    
  - name: MLServiceDown
    condition: ml_health_check_failures > 3
    duration: 2m
    severity: critical
    channels: [email, slack, pagerduty]
```

#### 4.6 No Request Tracing
**Impact**: Can't trace requests across services  
**Recommended**: Add correlation IDs

```typescript
// apps/api/src/common/middleware/correlation-id.middleware.ts
import { Injectable, NestMiddleware } from '@nestjs/common';
import { Request, Response, NextFunction } from 'express';
import { v4 as uuidv4 } from 'uuid';

@Injectable()
export class CorrelationIdMiddleware implements NestMiddleware {
  use(req: Request, res: Response, next: NextFunction) {
    const correlationId = req.headers['x-correlation-id'] || uuidv4();
    req['correlationId'] = correlationId;
    res.setHeader('X-Correlation-Id', correlationId);
    next();
  }
}

// Log with correlation ID
this.logger.log('Processing request', {
  correlationId: req['correlationId'],
  method: req.method,
  url: req.url,
});
```

### 🟡 HIGH Priority Monitoring

#### 4.7 No User Analytics
**Recommended**: Add privacy-friendly analytics (Plausible, Fathom)

#### 4.8 No Performance Budgets
**Required**: Define and enforce performance budgets
- LCP < 2.5s
- FID < 100ms
- CLS < 0.1

---

## 5. Compliance & Legal (6 Critical Issues)

### 🔴 CRITICAL Compliance Gaps

#### 5.1 No Privacy Policy
**Impact**: GDPR/CCPA non-compliance, legal risk  
**Required**: Create privacy policy page

```typescript
// apps/web/src/app/privacy/page.tsx
export default function PrivacyPage() {
  return (
    <div className="container mx-auto py-8 prose max-w-4xl">
      <h1>Privacy Policy</h1>
      <p>Last updated: January 24, 2026</p>

      <h2>1. Information We Collect</h2>
      <ul>
        <li><strong>Account Information</strong>: Email address, name</li>
        <li><strong>Tree Data</strong>: Images, GPS coordinates, species information</li>
        <li><strong>Usage Data</strong>: Anonymous analytics, error logs</li>
        <li><strong>Device Information</strong>: Browser type, IP address</li>
      </ul>

      <h2>2. How We Use Your Information</h2>
      <ul>
        <li>Provide and improve our services</li>
        <li>Process tree detection and classification</li>
        <li>Generate ecological reports and insights</li>
        <li>Communicate service updates</li>
      </ul>

      <h2>3. Data Sharing</h2>
      <p>We do not sell your personal data. We may share data with:</p>
      <ul>
        <li>Service providers (Supabase, Vercel) under strict agreements</li>
        <li>Researchers (anonymized aggregate data only, with consent)</li>
        <li>Legal authorities (if required by law)</li>
      </ul>

      <h2>4. Your Rights</h2>
      <p>Under GDPR and CCPA, you have the right to:</p>
      <ul>
        <li>Access your personal data</li>
        <li>Correct inaccurate data</li>
        <li>Delete your account and data</li>
        <li>Export your data</li>
        <li>Opt-out of data collection</li>
        <li>Object to automated decision-making</li>
      </ul>

      <h2>5. Data Retention</h2>
      <ul>
        <li>Account data: Retained until account deletion</li>
        <li>Tree data: Retained for ecological research (can be deleted on request)</li>
        <li>Analytics: Aggregated and anonymized after 90 days</li>
      </ul>

      <h2>6. Security</h2>
      <p>We use industry-standard security measures including:</p>
      <ul>
        <li>Encryption in transit (HTTPS/TLS)</li>
        <li>Encryption at rest (AES-256)</li>
        <li>Regular security audits</li>
        <li>Access controls and authentication</li>
      </ul>

      <h2>7. Contact Us</h2>
      <p>For privacy concerns: <a href="mailto:privacy@ecotrack.com">privacy@ecotrack.com</a></p>
      <p>Data Protection Officer: dpo@ecotrack.com</p>
    </div>
  );
}
```

**Also create**: Terms of Service, Cookie Policy

#### 5.2 No Cookie Consent Banner
**Impact**: GDPR non-compliance  
**Fix**:

```bash
cd apps/web
npm install react-cookie-consent
```

```typescript
// apps/web/src/components/CookieConsent.tsx
'use client';

import CookieBanner from 'react-cookie-consent';
import Link from 'next/link';

export function CookieConsent() {
  return (
    <CookieBanner
      location="bottom"
      buttonText="Accept All"
      declineButtonText="Decline"
      enableDeclineButton
      cookieName="ecotrack-cookie-consent"
      style={{ background: '#2B373B', padding: '20px' }}
      buttonStyle={{ 
        background: '#4ade80', 
        color: '#fff', 
        fontSize: '14px',
        borderRadius: '8px',
        padding: '10px 20px',
      }}
      declineButtonStyle={{
        background: 'transparent',
        border: '1px solid #fff',
        color: '#fff',
        fontSize: '14px',
        borderRadius: '8px',
        padding: '10px 20px',
      }}
      expires={150}
      onAccept={() => {
        // Enable analytics
        console.log('Cookies accepted');
      }}
      onDecline={() => {
        // Disable analytics
        console.log('Cookies declined');
      }}
    >
      We use cookies to improve your experience, analyze site traffic, and for marketing.{' '}
      <Link href="/privacy" className="underline">
        Learn more
      </Link>
    </CookieBanner>
  );
}

// Add to layout
// apps/web/src/app/layout.tsx
import { CookieConsent } from '@/components/CookieConsent';

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
        <CookieConsent />
      </body>
    </html>
  );
}
```

#### 5.3 No GDPR Data Export
**Impact**: Users can't exercise data portability rights  
**Fix**:

```typescript
// apps/api/src/users/users.controller.ts
@Get('export')
@UseGuards(AuthGuard)
@ApiBearerAuth()
@ApiOperation({ summary: 'Export user data (GDPR)' })
async exportUserData(@Request() req) {
  const userId = req.user.id;
  
  // Fetch all user data
  const [trees, profile, images] = await Promise.all([
    this.treesService.findByUserId(userId),
    this.usersService.getProfile(userId),
    this.imagesService.findByUserId(userId),
  ]);
  
  const exportData = {
    export_date: new Date().toISOString(),
    user_profile: profile,
    trees: trees,
    images: images.map(img => ({
      url: img.url,
      captured_at: img.captured_at,
    })),
    metadata: {
      total_trees: trees.length,
      account_created: profile.created_at,
    },
  };
  
  // Return as downloadable JSON
  return {
    filename: `ecotrack-data-${userId}-${Date.now()}.json`,
    data: exportData,
  };
}
```

#### 5.4 No GDPR Right to be Forgotten
**Impact**: Users can't delete their accounts  
**Fix**:

```typescript
// apps/api/src/users/users.controller.ts
@Delete('account')
@UseGuards(AuthGuard)
@ApiBearerAuth()
@HttpCode(204)
@ApiOperation({ summary: 'Delete account (GDPR)' })
async deleteAccount(@Request() req) {
  const userId = req.user.id;
  
  // Soft delete all user data
  await this.treesService.softDeleteByUserId(userId);
  await this.imagesService.deleteByUserId(userId);
  await this.usersService.softDeleteAccount(userId);
  
  // Schedule hard delete after 30 days
  await this.scheduleHardDelete(userId, 30);
  
  // Send confirmation email
  await this.emailService.sendAccountDeletionConfirmation(
    req.user.email
  );
  
  return { 
    message: 'Account deletion initiated. Data will be permanently deleted in 30 days.' 
  };
}
```

#### 5.5 No Data Retention Policy
**Impact**: Unclear data lifecycle  
**Required**: Document retention periods

```markdown
# Data Retention Policy

## User Account Data
- Active accounts: Retained indefinitely
- Deleted accounts: Soft-deleted for 30 days, then hard-deleted
- Inactive accounts (no login > 2 years): Email notification, then deletion after 90 days

## Tree Data
- User-created trees: Retained until user deletion or explicit delete
- Anonymized aggregate data: Retained indefinitely for research

## Images
- Original uploads: Retained for 1 year, then deleted (thumbnail kept)
- Thumbnails: Retained as long as tree record exists

## Logs
- Application logs: Retained for 90 days
- Audit logs: Retained for 7 years (compliance)
- Error logs: Retained for 1 year

## Analytics
- Raw analytics: Aggregated and anonymized after 90 days
- Aggregated data: Retained indefinitely
```

#### 5.6 No Audit Logging
**Impact**: Can't prove compliance with data access requests  
**Fix**:

```typescript
// apps/api/src/common/audit-logger.service.ts
import { Injectable } from '@nestjs/common';

@Injectable()
export class AuditLoggerService {
  async logEvent(event: {
    userId: string;
    action: string;
    resource: string;
    resourceId?: string;
    ipAddress?: string;
    userAgent?: string;
    metadata?: any;
  }) {
    await this.supabase.from('audit_logs').insert({
      user_id: event.userId,
      action: event.action, // e.g., 'tree.create', 'tree.delete', 'data.export'
      resource: event.resource, // e.g., 'tree', 'user', 'image'
      resource_id: event.resourceId,
      ip_address: event.ipAddress,
      user_agent: event.userAgent,
      metadata: event.metadata,
      timestamp: new Date().toISOString(),
    });
  }
}

// Usage
await this.auditLogger.logEvent({
  userId: req.user.id,
  action: 'tree.create',
  resource: 'tree',
  resourceId: tree.id,
  ipAddress: req.ip,
  userAgent: req.headers['user-agent'],
  metadata: { species: tree.species },
});
```

**Migration**:

```sql
-- supabase/migrations/003_audit_logs.sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    metadata JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user ON audit_logs (user_id, timestamp DESC);
CREATE INDEX idx_audit_logs_action ON audit_logs (action, timestamp DESC);
CREATE INDEX idx_audit_logs_resource ON audit_logs (resource, resource_id);
```

### 🟡 HIGH Priority Compliance

#### 5.7 No Age Verification
**Required if targeting minors**: Add age gate or parental consent

#### 5.8 No Accessibility Statement
**Recommended**: Document accessibility features and limitations

---

## 6. Backup & Disaster Recovery (4 Critical Issues)

### 🔴 CRITICAL Backup Gaps

#### 6.1 No Automated Database Backups Beyond Supabase
**Current**: Relying solely on Supabase automatic backups  
**Risk**: Vendor lock-in, single point of failure  
**Fix**: Add independent backup strategy

```bash
#!/bin/bash
# scripts/backup-database.sh

# Configuration
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups/database"
S3_BUCKET="s3://ecotrack-backups"

# Create backup directory
mkdir -p $BACKUP_DIR

# Export database (requires pg_dump access to Supabase)
# Note: Supabase provides daily backups, but add weekly full backups
echo "Creating backup: ecotrack_$DATE.sql"

# Option 1: If you have direct PostgreSQL access
# pg_dump $DATABASE_URL > "$BACKUP_DIR/ecotrack_$DATE.sql"

# Option 2: Use Supabase CLI
supabase db dump -f "$BACKUP_DIR/ecotrack_$DATE.sql"

# Compress backup
gzip "$BACKUP_DIR/ecotrack_$DATE.sql"

# Upload to S3 (or your cloud storage)
aws s3 cp "$BACKUP_DIR/ecotrack_$DATE.sql.gz" "$S3_BUCKET/database/"

# Clean up old backups (keep last 30 days locally)
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

# Keep 12 monthly backups in S3
# (Add logic to keep one backup per month for 12 months)

echo "Backup completed: ecotrack_$DATE.sql.gz"
```

**Schedule with cron**:

```cron
# Run daily at 2 AM
0 2 * * * /path/to/backup-database.sh >> /var/log/ecotrack-backup.log 2>&1
```

**Or use GitHub Actions**:

```yaml
# .github/workflows/backup.yml
name: Database Backup
on:
  schedule:
    - cron: '0 2 * * *' # Daily at 2 AM UTC
  workflow_dispatch: # Manual trigger

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Supabase CLI
        run: |
          curl -fsSL https://github.com/supabase/cli/releases/download/v1.0.0/supabase_1.0.0_linux_amd64.tar.gz | tar xz
          sudo mv supabase /usr/local/bin/
      
      - name: Create backup
        env:
          SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
          SUPABASE_PROJECT_ID: ${{ secrets.SUPABASE_PROJECT_ID }}
        run: |
          mkdir -p backups
          supabase db dump -p $SUPABASE_PROJECT_ID -f backups/backup-$(date +%Y%m%d).sql
      
      - name: Upload to S3
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          aws s3 cp backups/ s3://ecotrack-backups/database/ --recursive
```

#### 6.2 No Point-in-Time Recovery Testing
**Impact**: Don't know if backups actually work  
**Required**: Monthly restore drills

```markdown
# Disaster Recovery Procedure

## Recovery Time Objective (RTO)
Target: 4 hours from incident detection to full restoration

## Recovery Point Objective (RPO)
Target: Maximum 1 hour of data loss

## Monthly Drill Procedure

### Week 1: Backup Verification
1. Download latest backup from S3
2. Verify file integrity (checksum)
3. Check backup size is reasonable

### Week 2: Restore to Staging
1. Spin up staging database instance
2. Restore from latest backup
3. Verify data integrity:
   ```sql
   SELECT COUNT(*) FROM trees;
   SELECT COUNT(*) FROM users;
   SELECT MAX(created_at) FROM trees; -- Should be recent
   ```
4. Run smoke tests
5. Document restore time

### Week 3: Point-in-Time Recovery
1. Identify specific timestamp to restore to
2. Use Supabase PITR or backup closest to that time
3. Verify specific records exist/don't exist as expected

### Week 4: Full Disaster Recovery Simulation
1. **Scenario**: Primary database is corrupted
2. **Response**:
   - Activate incident response team
   - Switch DNS to maintenance page
   - Restore latest backup to new database
   - Update application connection strings
   - Run full test suite
   - Gradually restore traffic
3. **Document**:
   - Total time taken
   - Issues encountered
   - Action items for improvement

## Quarterly: Disaster Recovery Drill
- Simulate complete platform failure
- Restore all services (database, API, frontend)
- Measure total recovery time
- Update runbook with learnings
```

#### 6.3 No File Storage Backup Strategy
**Current**: Supabase Storage has built-in redundancy  
**Action**: Verify and document Supabase Storage backup policies

```typescript
// apps/api/src/storage/storage-backup.service.ts
export class StorageBackupService {
  async backupCriticalImages() {
    // Identify critical images (e.g., verified trees, featured images)
    const criticalImages = await this.findCriticalImages();
    
    // Copy to secondary storage (S3, Google Cloud Storage)
    for (const image of criticalImages) {
      const imageData = await this.downloadFromSupabase(image.url);
      await this.uploadToBackupStorage(imageData, image.id);
    }
  }
  
  private async findCriticalImages() {
    return this.supabase
      .from('tree_images')
      .select('*')
      .eq('is_critical', true)
      .order('created_at', { ascending: false })
      .limit(1000);
  }
}
```

#### 6.4 No Configuration Backup
**Impact**: Infrastructure config not versioned  
**Fix**: Everything in Git

```bash
# Verify all config is in Git
git add terraform/
git add k8s/
git add .env.example
git add docker-compose.yml
git commit -m "Add infrastructure config"
```

### 🟡 HIGH Priority Backup

#### 6.5 No Backup Monitoring
**Required**: Alert if backups fail

```typescript
// Add to monitoring service
async checkBackupStatus() {
  const lastBackup = await getLastBackupTime();
  const hoursSinceBackup = (Date.now() - lastBackup) / (1000 * 60 * 60);
  
  if (hoursSinceBackup > 25) { // Should run daily
    await alertTeam('Backup has not run in 25+ hours');
  }
}
```

---

## 7. Performance & Scalability (6 Critical Issues)

### 🔴 CRITICAL Performance Gaps

#### 7.1 No Image Optimization
**Impact**: Slow page loads, high bandwidth costs  
**Fix**:

```typescript
// apps/web/next.config.ts
const nextConfig: NextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.supabase.co',
      },
    ],
    formats: ['image/avif', 'image/webp'],
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },
};

// Usage
import Image from 'next/image';

<Image
  src={tree.image_url}
  alt={tree.species}
  width={300}
  height={300}
  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
  placeholder="blur"
  blurDataURL={tree.thumbnail_url}
/>
```

**Generate thumbnails on upload**:

```typescript
// apps/api/src/trees/trees.service.ts
async createWithThumbnail(image: Buffer) {
  // Generate thumbnail (use Sharp or Supabase Transform)
  const thumbnail = await this.generateThumbnail(image);
  
  // Upload both
  const [imageUrl, thumbnailUrl] = await Promise.all([
    this.uploadImage(image),
    this.uploadThumbnail(thumbnail),
  ]);
  
  return { imageUrl, thumbnailUrl };
}
```

#### 7.2 Missing Database Indexes
**Impact**: Slow queries, poor performance  
**Fix**: Add indexes for common queries

```sql
-- supabase/migrations/004_performance_indexes.sql

-- Index for viewport queries (most common)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trees_viewport 
  ON trees (latitude, longitude, created_at DESC) 
  WHERE deleted_at IS NULL;

-- Index for user's trees
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trees_user_created 
  ON trees (user_id, created_at DESC) 
  WHERE deleted_at IS NULL;

-- Index for species filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trees_species_active 
  ON trees (species) 
  WHERE deleted_at IS NULL;

-- Composite index for common filter combinations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trees_species_health 
  ON trees (species, health_status) 
  WHERE deleted_at IS NULL;

-- Full-text search index (if not already created)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trees_species_search 
  ON trees USING GIN (to_tsvector('english', species));

-- Analyze tables to update statistics
ANALYZE trees;
ANALYZE tree_images;
```

**Test query performance**:

```sql
-- Before adding index
EXPLAIN ANALYZE 
SELECT * FROM trees 
WHERE latitude BETWEEN 37 AND 38 
  AND longitude BETWEEN -123 AND -122 
  AND deleted_at IS NULL 
ORDER BY created_at DESC 
LIMIT 100;

-- Should use Index Scan, not Seq Scan
-- Execution time should be < 50ms
```

#### 7.3 No Caching Strategy
**Current**: Basic Redis caching exists  
**Required**: Comprehensive caching

```typescript
// apps/api/src/common/cache-keys.ts
export const CACHE_KEYS = {
  TREES_VIEWPORT: (bounds: string) => `trees:viewport:${bounds}`,
  TREE_DETAIL: (id: string) => `tree:${id}`,
  USER_STATS: (userId: string) => `user:stats:${userId}`,
  SPECIES_LIST: () => 'species:list',
  HEATMAP_DATA: (region: string) => `heatmap:${region}`,
} as const;

export const CACHE_TTL = {
  TREES_VIEWPORT: 30, // 30 seconds (frequently changing)
  TREE_DETAIL: 300, // 5 minutes
  USER_STATS: 600, // 10 minutes
  SPECIES_LIST: 3600, // 1 hour (rarely changes)
  HEATMAP_DATA: 1800, // 30 minutes
} as const;
```

**HTTP Caching Headers**:

```typescript
// apps/api/src/trees/trees.controller.ts
@Get('viewport')
@Header('Cache-Control', 'public, max-age=30, s-maxage=60, stale-while-revalidate=120')
async getTreesInViewport(...) {
  // ...
}

@Get(':id')
@Header('Cache-Control', 'public, max-age=300, immutable')
async findOne(@Param('id') id: string) {
  // ...
}
```

#### 7.4 No CDN Configuration
**Impact**: Slow asset loading globally  
**Fix**: Vercel automatically provides CDN, but verify

```typescript
// apps/web/next.config.ts
const nextConfig: NextConfig = {
  // Vercel automatically configures CDN
  // For custom CDN:
  assetPrefix: process.env.CDN_URL || '',
};
```

#### 7.5 No Code Splitting
**Impact**: Large JavaScript bundles  
**Fix**: Implement lazy loading

```typescript
// apps/web/src/app/map/page.tsx
import dynamic from 'next/dynamic';
import { Suspense } from 'react';

// Lazy load map (Leaflet doesn't work with SSR)
const TreeMap = dynamic(() => import('@/components/TreeMap'), {
  loading: () => (
    <div className="flex items-center justify-center h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
    </div>
  ),
  ssr: false,
});

export default function MapPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <TreeMap />
    </Suspense>
  );
}
```

#### 7.6 No Response Compression
**Impact**: Higher bandwidth costs, slower responses  
**Fix**:

```bash
cd apps/api
npm install compression
```

```typescript
// apps/api/src/main.ts
import * as compression from 'compression';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  
  // Enable compression
  app.use(compression({
    threshold: 1024, // Only compress responses > 1KB
  }));
  
  await app.listen(3001);
}
```

### 🟡 HIGH Priority Performance

#### 7.7 No Database Connection Pooling Config
**Action**: Verify Supabase pooler settings
- Transaction mode: Best for serverless (short connections)
- Session mode: Better for traditional apps (long connections)

#### 7.8 No Pagination on List Endpoints
**Current**: Limit parameter exists  
**Required**: Cursor-based pagination for large datasets

```typescript
// apps/api/src/trees/trees.controller.ts
@Get()
async findAll(
  @Query('cursor') cursor?: string,
  @Query('limit') limit: number = 20
) {
  return this.treesService.findAllPaginated(cursor, Math.min(limit, 100));
}

// apps/api/src/trees/trees.service.ts
async findAllPaginated(cursor?: string, limit: number = 20) {
  let query = this.supabase
    .from('trees')
    .select('*')
    .is('deleted_at', null)
    .order('created_at', { ascending: false })
    .limit(limit + 1); // Fetch one extra to determine if more exist
  
  if (cursor) {
    query = query.lt('created_at', cursor);
  }
  
  const { data, error } = await query;
  
  if (error) throw new Error(error.message);
  
  const hasMore = data.length > limit;
  const items = hasMore ? data.slice(0, limit) : data;
  const nextCursor = hasMore ? items[items.length - 1].created_at : null;
  
  return {
    items,
    nextCursor,
    hasMore,
  };
}
```

### 🟢 MEDIUM Priority Performance

#### 7.9 No Service Worker for Offline Support
**Recommended**: Add PWA capabilities

```typescript
// apps/web/public/sw.js
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('ecotrack-v1').then((cache) => {
      return cache.addAll([
        '/',
        '/map',
        '/offline',
        '/manifest.json',
      ]);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).catch(() => {
        // Return offline page for navigation requests
        if (event.request.mode === 'navigate') {
          return caches.match('/offline');
        }
      });
    })
  );
});
```

#### 7.10 No Database Read Replicas
**Future**: Configure read replicas for high read workload

---

## 8. API Design & Versioning (3 Critical Issues)

### 🔴