import { ChangeDetectionStrategy, Component } from '@angular/core';
import { GenerationFormComponent } from '../features/generations/generation-form.component';

@Component({
  selector: 'app-generation-page',
  imports: [GenerationFormComponent],
  template: `
    <main class="grid max-w-5xl grid-cols-[minmax(0,1fr)_minmax(320px,520px)] items-center gap-20 max-[780px]:grid-cols-1 max-[780px]:gap-8">
      <section class="max-w-xl">
        <p class="eyebrow">DROPSHIPPING / STUDIO</p>
        <h1>Crie páginas que vendem.</h1>
        <p class="lead">Descreva seu produto e acompanhe a geração da landing page em um só lugar.</p>
      </section>
      <section class="rounded-2xl border border-line bg-white p-8 shadow-2xl shadow-slate-900/5"><app-generation-form /></section>
    </main>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GenerationPageComponent {}
