import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { AuthRepository } from '../core/repositories/auth.repository';
import { PagesRepository } from '../core/repositories/pages.repository';
import { PageSummary } from '../core/schemas/page.schema';
import { SidebarComponent } from '../ui/molecules/sidebar.component';

@Component({ selector: 'app-shell', imports: [RouterOutlet, SidebarComponent], template: `<div class="grid h-dvh grid-cols-[250px_minmax(0,1fr)] overflow-hidden max-[780px]:block max-[780px]:h-auto max-[780px]:min-h-dvh"><app-sidebar [pages]="pages()" (logout)="logout()" /><main class="min-h-0 overflow-y-auto p-[clamp(1.5rem,5vw,5rem)] max-[780px]:overflow-visible"><router-outlet /></main></div>`, changeDetection: ChangeDetectionStrategy.OnPush })
export class AppShellComponent {
  private readonly auth = inject(AuthRepository); private readonly pagesApi = inject(PagesRepository); private readonly router = inject(Router);
  protected readonly pages = signal<PageSummary[]>([]);
  constructor() { this.pagesApi.list().subscribe({ next: (pages) => this.pages.set(pages) }); }
  logout() { this.auth.logout().subscribe(() => this.router.navigateByUrl('/login')); }
}
