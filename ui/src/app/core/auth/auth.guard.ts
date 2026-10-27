import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthRepository } from '../repositories/auth.repository';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthRepository);
  const router = inject(Router);
  return auth.me().pipe(map(() => true), catchError(() => of(router.parseUrl('/login'))));
};
