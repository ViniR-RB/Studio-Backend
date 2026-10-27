import { ChangeDetectionStrategy, Component, ElementRef, input, output, viewChild } from '@angular/core';
import { LucideX } from '@lucide/angular';

@Component({
  selector: 'app-modal',
  imports: [LucideX],
  template: `
    <dialog #dialog class="m-auto max-h-[90dvh] w-[min(960px,calc(100vw-2rem))] rounded-2xl border border-line bg-white p-0 text-ink shadow-2xl backdrop:bg-slate-950/50" (click)="closeOnBackdrop($event)">
      <header class="flex items-center justify-between border-b border-line px-5 py-4">
        <h2 class="m-0 text-lg font-bold">{{ title() }}</h2>
        <button class="rounded-lg border-0 bg-transparent p-2 text-muted hover:bg-slate-100" type="button" aria-label="Fechar" (click)="close()"><svg lucideX [size]="18"></svg></button>
      </header>
      <div class="p-6"><ng-content /></div>
      <footer class="flex items-center justify-between gap-3 border-t border-line px-6 py-4">
        <button class="rounded-xl border border-line bg-white px-4 py-3 font-bold text-muted hover:bg-slate-50" type="button" (click)="close()">Cancelar</button>
        @if (showConfirm()) {
          <button class="rounded-xl bg-brand px-4 py-3 font-extrabold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-55" type="button" [disabled]="confirmDisabled()" (click)="confirmed.emit()">{{ confirmLabel() }}</button>
        }
      </footer>
    </dialog>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ModalComponent {
  readonly title = input('Visualizar página');
  readonly closed = output<void>();
  readonly opened = output<void>();
  readonly confirmed = output<void>();
  readonly showConfirm = input(false);
  readonly confirmDisabled = input(false);
  readonly confirmLabel = input('Confirmar');
  private readonly dialog = viewChild<ElementRef<HTMLDialogElement>>('dialog');

  open() { this.dialog()?.nativeElement.showModal(); this.opened.emit(); }
  close() { this.dialog()?.nativeElement.close(); this.closed.emit(); }
  closeOnBackdrop(event: MouseEvent) { if (event.target === event.currentTarget) this.close(); }
}
