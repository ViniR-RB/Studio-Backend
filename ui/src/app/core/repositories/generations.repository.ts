import { inject, Injectable } from '@angular/core';
import { ApiHttp } from '../http/api-http.service';
import { GenerationAccepted, GenerationRequest, GenerationStatus } from '../schemas/generation.schema';

@Injectable({ providedIn: 'root' })
export class GenerationsRepository {
  private readonly api = inject(ApiHttp);

  create(request: GenerationRequest) {
    return this.api.post<GenerationAccepted>('/generations', request);
  }

  status(jobId: string) {
    return this.api.get<GenerationStatus>(`/generations/${jobId}`);
  }
}
