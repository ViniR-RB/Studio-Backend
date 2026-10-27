import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-button',
  template: `<button class="rounded-xl border-0 bg-brand px-4 py-3 font-extrabold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-55" [type]="type()" [disabled]="disabled()"><ng-content /></button>`,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ButtonComponent {
  readonly type = input<'button' | 'submit' | 'reset'>('button');
  readonly disabled = input(false);
}
