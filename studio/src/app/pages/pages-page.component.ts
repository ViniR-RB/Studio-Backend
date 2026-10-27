import { ChangeDetectionStrategy, Component, inject, signal, viewChild } from '@angular/core';
import { PagesRepository } from '../core/repositories/pages.repository';
import { PageSummary } from '../core/schemas/page.schema';
import { GenerationFormComponent } from '../features/generations/generation-form.component';
import { ModalComponent } from '../ui/atoms/modal.component';
import { LucideFilePlus2 } from '@lucide/angular';

@Component({
  selector: 'app-pages-page',
  imports: [ModalComponent, GenerationFormComponent, LucideFilePlus2],
  template: `
    <section>
      <div class="mb-8 flex items-end justify-between gap-4">
        <div><p class="text-xs font-black tracking-widest text-brand">STUDIO / PÁGINAS</p><h1 class="my-4 text-6xl font-black tracking-[-.07em] max-[780px]:text-4xl">Minhas páginas.</h1></div>
        <button class="flex items-center gap-2 rounded-xl bg-brand px-4 py-3 font-extrabold text-white hover:opacity-90" type="button" (click)="create()"><svg lucideFilePlus2 [size]="17"></svg><span>Nova página</span></button>
      </div>
      <div class="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
        @for (page of pages(); track page.id) { <button class="grid cursor-pointer gap-2 rounded-2xl border border-line bg-white p-5 text-left text-ink hover:border-brand" type="button" (click)="openPage(page)"><strong>{{ page.slug }}</strong><span class="text-sm text-muted">{{ page.status }}</span></button> } @empty { <p>Nenhuma página publicada ainda.</p> }
      </div>
      <app-modal #createModal title="Nova página" [showConfirm]="false"><app-generation-form (created)="refreshAndClose()" /></app-modal>
    </section>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PagesPageComponent {
  private readonly repository = inject(PagesRepository);
  protected readonly pages = signal<PageSummary[]>([]);
  private readonly createModal = viewChild<ModalComponent>('createModal');

  constructor() { this.refresh(); }
  create() { this.createModal()?.open(); }
  openPage(page: PageSummary) { window.open(`/api/v1/pages/${page.slug}`, '_blank', 'noopener,noreferrer'); }
  refreshAndClose() { this.refresh(); this.createModal()?.close(); }
  private refresh() { this.repository.list().subscribe({ next: (pages) => this.pages.set(pages) }); }
}
