export type RadiusOption = "Bucuresti" | "50" | "100" | "200" | "All Romania";
export type JobStatus = "queued" | "running" | "done" | "failed";

export interface JobResponse {
  id: string;
  query: string;
  radiusOption: RadiusOption;
  includeUnknownLocation: boolean;
  status: JobStatus;
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
  price: string | null;
  currency: string | null;
  size: string | null;
  locationCity: string | null;
  locationAddress: string | null;
  distanceKm: number | null;
  locationUnknown: boolean;
}
