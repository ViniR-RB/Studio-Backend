import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

type Query = Record<string, string | number | boolean>;

@Injectable({ providedIn: 'root' })
export class ApiHttp {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = '/api/v1';

  get<T>(path: string, query?: Query, context?: HttpContext): Observable<T> {
    return this.http.get<T>(`${this.baseUrl}${path}`, { params: new HttpParams({ fromObject: query ?? {} }), context });
  }

  post<T>(path: string, body: unknown, context?: HttpContext): Observable<T> {
    return this.http.post<T>(`${this.baseUrl}${path}`, body, { context });
  }
}
