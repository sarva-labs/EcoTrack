/**
 * Typed API client for communicating with EcoTrack API.
 *
 * All domain-specific functions are grouped by namespace.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/* ------------------------------------------------------------------ */
/*  Shared types                                                       */
/* ------------------------------------------------------------------ */

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export interface ApiError {
  status: number;
  message: string;
}

/* ------------------------------------------------------------------ */
/*  Generic fetch wrapper                                              */
/* ------------------------------------------------------------------ */

export async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(
      `API error ${response.status}: ${body || response.statusText}`,
    );
  }

  return response.json() as Promise<T>;
}

/* ------------------------------------------------------------------ */
/*  Climate API                                                        */
/* ------------------------------------------------------------------ */

export const climateApi = {
  getObservations: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/climate/observations?${new URLSearchParams(params)}`,
    ),

  getForecast: (data: Record<string, unknown>) =>
    fetchApi<any>("/api/v1/climate/forecast", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getAnomalies: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/climate/anomalies?${new URLSearchParams(params)}`,
    ),

  getTrends: (params: Record<string, string>) =>
    fetchApi<any>(`/api/v1/climate/trends?${new URLSearchParams(params)}`),

  getVariables: () => fetchApi<any>("/api/v1/climate/variables"),
};

/* ------------------------------------------------------------------ */
/*  Biodiversity API                                                   */
/* ------------------------------------------------------------------ */

export const biodiversityApi = {
  getSpecies: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/biodiversity/species?${new URLSearchParams(params)}`,
    ),

  getEcosystemHealth: (params: Record<string, string>) =>
    fetchApi<any>(
      `/api/v1/biodiversity/ecosystem-health?${new URLSearchParams(params)}`,
    ),

  getHotspots: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/biodiversity/hotspots?${new URLSearchParams(params)}`,
    ),

  getConservationStatus: () =>
    fetchApi<any>("/api/v1/biodiversity/conservation-status"),

  assessHabitat: (data: Record<string, unknown>) =>
    fetchApi<any>("/api/v1/biodiversity/habitat-assessment", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

/* ------------------------------------------------------------------ */
/*  Health API                                                         */
/* ------------------------------------------------------------------ */

export const healthApi = {
  getAirQuality: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/health/air-quality?${new URLSearchParams(params)}`,
    ),

  getDiseaseRisk: (params: Record<string, string>) =>
    fetchApi<any>(
      `/api/v1/health/disease-risk?${new URLSearchParams(params)}`,
    ),

  getHeatVulnerability: (params: Record<string, string>) =>
    fetchApi<any>(
      `/api/v1/health/heat-vulnerability?${new URLSearchParams(params)}`,
    ),

  getHealthAlerts: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/health/alerts?${new URLSearchParams(params)}`,
    ),
};

/* ------------------------------------------------------------------ */
/*  Food Security API                                                  */
/* ------------------------------------------------------------------ */

export const foodSecurityApi = {
  getCropYield: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/food-security/crop-yield?${new URLSearchParams(params)}`,
    ),

  getDroughtAlerts: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/food-security/drought-alerts?${new URLSearchParams(params)}`,
    ),

  getFoodSecurityIndex: (params: Record<string, string>) =>
    fetchApi<any>(
      `/api/v1/food-security/index?${new URLSearchParams(params)}`,
    ),

  predictYield: (data: Record<string, unknown>) =>
    fetchApi<any>("/api/v1/food-security/predict-yield", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

/* ------------------------------------------------------------------ */
/*  Resources API                                                      */
/* ------------------------------------------------------------------ */

export const resourcesApi = {
  getWaterStress: (params: Record<string, string>) =>
    fetchApi<PaginatedResponse<any>>(
      `/api/v1/resources/water-stress?${new URLSearchParams(params)}`,
    ),

  getEnvironmentalJustice: (params: Record<string, string>) =>
    fetchApi<any>(
      `/api/v1/resources/environmental-justice?${new URLSearchParams(params)}`,
    ),

  getResourceAllocation: (params: Record<string, string>) =>
    fetchApi<any>(
      `/api/v1/resources/allocation?${new URLSearchParams(params)}`,
    ),

  optimizeAllocation: (data: Record<string, unknown>) =>
    fetchApi<any>("/api/v1/resources/optimize", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

/* ------------------------------------------------------------------ */
/*  Agents / Analytics API                                             */
/* ------------------------------------------------------------------ */

export const agentsApi = {
  query: (data: { question: string; domain?: string }) =>
    fetchApi<any>("/api/v1/agents/query", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getConversations: () => fetchApi<any>("/api/v1/agents/conversations"),
};

export const analyticsApi = {
  getSummary: () => fetchApi<any>("/api/v1/analytics/summary"),

  getCrossDomainCorrelations: (params: Record<string, string>) =>
    fetchApi<any>(
      `/api/v1/analytics/correlations?${new URLSearchParams(params)}`,
    ),

  getSystemHealth: () => fetchApi<any>("/api/v1/analytics/system-health"),
};
