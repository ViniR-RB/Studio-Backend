import { inject, Injectable } from '@angular/core';
import { ApiHttp } from '../http/api-http.service';
import { CurrentUser, LoginRequest } from '../schemas/auth.schema';

@Injectable({ providedIn: 'root' })
export class AuthRepository {
  private readonly api = inject(ApiHttp);
  login(request: LoginRequest) { return this.api.post<CurrentUser>('/auth/login', request); }
  me() { return this.api.get<CurrentUser>('/auth/me'); }
  logout() { return this.api.post<void>('/auth/logout', {}); }
}
