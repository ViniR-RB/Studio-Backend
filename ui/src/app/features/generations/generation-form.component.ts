import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize } from 'rxjs';
import { GenerationsRepository } from '../../core/repositories/generations.repository';
import { GenerationStatus } from '../../core/schemas/generation.schema';
import { ButtonComponent } from '../../ui/atoms/button.component';
import { input, output } from '@angular/core';

@Component({
  selector: 'app-generation-form',
  imports: [ReactiveFormsModule, ButtonComponent],
  template: `
    <form class="grid gap-5" [formGroup]="form" (ngSubmit)="submit()" novalidate>
      <div><label for="product-name">Produto</label><input id="product-name" formControlName="product_name" placeholder="Ex.: Garrafa térmica" /></div>
      <div><label for="description">Descrição</label><textarea id="description" formControlName="product_description" rows="4" placeholder="O que torna o produto especial?"></textarea></div>
      <div><label for="audience">Público-alvo</label><input id="audience" formControlName="target_audience" placeholder="Ex.: Pessoas que trabalham em home office" /></div>
      <div><label for="tone">Tom</label><input id="tone" formControlName="tone" /></div>
      @if (error()) { <p class="error" role="alert">{{ error() }}</p> }
      @if (status(); as current) { <p class="status" role="status">Status: {{ current.status }}</p> }
      <app-button type="submit" [disabled]="form.invalid || loading()">{{ loading() ? 'Enviando…' : submitLabel() }}</app-button>
    </form>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GenerationFormComponent {
  readonly created = output<void>();
  readonly submitLabel = input('Gerar landing page');
  private readonly fb = inject(NonNullableFormBuilder);
  private readonly repository = inject(GenerationsRepository);
  protected readonly loading = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly status = signal<GenerationStatus | null>(null);
  protected readonly form = this.fb.group({
    product_name: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(160)]],
    product_description: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(5000)]],
    target_audience: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(240)]],
    tone: ['clear and persuasive', [Validators.required, Validators.maxLength(120)]],
  });

  submit() {
    if (this.form.invalid) return this.form.markAllAsTouched();
    this.loading.set(true);
    this.error.set(null);
    this.repository.create(this.form.getRawValue()).pipe(finalize(() => this.loading.set(false))).subscribe({
      next: (accepted) => { this.status.set({ job_id: accepted.job_id, status: accepted.status, error: null, slug: null }); this.created.emit(); },
      error: (response) => this.error.set(response.error?.detail ?? 'Não foi possível iniciar a geração.'),
    });
  }
}
