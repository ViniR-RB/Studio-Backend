export type GenerationStatusValue = 'queued' | 'running' | 'succeeded' | 'failed' | 'published' | string;

export interface GenerationRequest {
  product_name: string;
  product_description: string;
  target_audience: string;
  tone: string;
}

export interface GenerationAccepted {
  job_id: string;
  status: GenerationStatusValue;
}

export interface GenerationStatus {
  job_id: string;
  status: GenerationStatusValue;
  error: string | null;
  slug: string | null;
}
