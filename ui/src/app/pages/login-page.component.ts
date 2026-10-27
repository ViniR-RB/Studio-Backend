import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { AuthRepository } from '../core/repositories/auth.repository';
import { ButtonComponent } from '../ui/atoms/button.component';

@Component({
  selector: 'app-login-page',
  imports: [ReactiveFormsModule, ButtonComponent],
  template: `<main class="grid min-h-dvh place-items-center p-6"><section class="w-full max-w-lg rounded-2xl border border-line bg-white p-8 shadow-2xl shadow-slate-900/5"><p class="eyebrow">STUDIO ACCESS</p><h1>Entrar.</h1><form class="grid gap-5" [formGroup]="form" (ngSubmit)="submit()"><div><label for="email">E-mail</label><input id="email" type="email" formControlName="email" autocomplete="email" /></div><div><label for="password">Senha</label><input id="password" type="password" formControlName="password" autocomplete="current-password" /></div>@if (error()) { <p class="error" role="alert">{{ error() }}</p> }<app-button type="submit" [disabled]="form.invalid || loading()">{{ loading() ? 'Entrando…' : 'Entrar' }}</app-button></form></section></main>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginPageComponent {
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly auth = inject(AuthRepository);
  private readonly router = inject(Router);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly form = this.fb.group({ email: ['', [Validators.required, Validators.email]], password: ['', [Validators.required, Validators.minLength(8)]] });
  submit() {
    if (this.form.invalid) return this.form.markAllAsTouched();
    this.loading.set(true); this.error.set(null);
    this.auth.login(this.form.getRawValue()).pipe(finalize(() => this.loading.set(false))).subscribe({ next: () => this.router.navigateByUrl('/pages'), error: (response) => this.error.set(response.error?.detail ?? 'Não foi possível entrar.') });
  }
}
