import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { PageSummary } from '../../core/schemas/page.schema';
import { LucideFiles, LucideLogOut, LucideSparkles } from '@lucide/angular';

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive, LucideFiles, LucideLogOut, LucideSparkles],
  template: `
    <aside class="flex h-dvh min-h-0 flex-col gap-8 overflow-y-auto border-r border-line bg-white p-6 max-[780px]:h-auto max-[780px]:min-h-0 max-[780px]:overflow-visible">
      <div class="flex items-center gap-2 text-lg font-black"><svg lucideSparkles [size]="18" class="text-brand"></svg><span>Studio</span></div>
      <nav aria-label="Navegação principal" class="grid gap-1">
        <a routerLink="/pages" routerLinkActive="bg-brand/10 text-brand" class="flex items-center gap-2 rounded-xl p-3 font-bold text-muted no-underline hover:bg-brand/10 hover:text-brand"><svg lucideFiles [size]="16"></svg> Minhas páginas</a>
      </nav>
      <div class="grid min-w-0 gap-1">
        <p class="m-0 text-[.65rem] font-black tracking-widest text-slate-400">PÁGINAS RECENTES</p>
        @if (pages().length === 0) { <small class="text-muted">Nenhuma página criada.</small> }
        @for (page of pages(); track page.id) { <a class="flex min-w-0 gap-2 rounded-xl p-3 font-bold text-muted no-underline hover:bg-slate-50" [href]="'/api/v1/pages/' + page.slug" target="_blank" rel="noreferrer"><span class="truncate">{{ page.slug }}</span><small class="text-slate-400">{{ page.status }}</small></a> }
      </div>
      <button class="mt-auto flex items-center gap-2 border-0 bg-transparent p-3 text-left text-muted" type="button" (click)="logout.emit()"><svg lucideLogOut [size]="16"></svg> Sair</button>
    </aside>
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SidebarComponent {
  readonly pages = input<PageSummary[]>([]);
  readonly logout = output<void>();
}

