export type RadiusOption = "Bucuresti" | "50" | "100" | "200" | "All Romania";
export type JobState = "queued" | "running" | "done" | "failed";

export interface CreateJobInput {
  query: string;
  radiusOption: RadiusOption;
  includeUnknownLocation: boolean;
  maxUrls: number;
  timeBudgetSeconds: number;
}

export interface JobResponse {
  id: string;
  query: string;
  radiusOption: RadiusOption;
  includeUnknownLocation: boolean;
  status: JobState;
  progress: number;
  totalCandidateUrls: number;
  processedUrls: number;
  foundProducts: number;
  errors: number;
  errorMessage?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ResultItem {
  id: string;
  productName: string;
  website: string;
  sourceUrl: string;
  price: number | null;
  currency: string | null;
  size: string | null;
  locationCity: string | null;
  locationAddress: string | null;
  distanceKm: number | null;
  locationUnknown: boolean;
}

export interface ResultsResponse {
  total: number;
  page: number;
  pageSize: number;
  items: ResultItem[];
}
