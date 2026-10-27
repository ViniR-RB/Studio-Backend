import { inject, Injectable } from '@angular/core';
import { ApiHttp } from '../http/api-http.service';
import { PageSummary } from '../schemas/page.schema';

@Injectable({ providedIn: 'root' })
export class PagesRepository {
  private readonly api = inject(ApiHttp);
  list() { return this.api.get<PageSummary[]>('/pages'); }
}
