import { Component } from '@angular/core';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { ToastContainerComponent } from './components/toast-container/toast-container.component';
import { ConfirmDialogComponent } from './components/confirm-dialog/confirm-dialog.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [DashboardComponent, ToastContainerComponent, ConfirmDialogComponent],
  template: `
    <app-dashboard></app-dashboard>
    <app-toast-container></app-toast-container>
    <app-confirm-dialog></app-confirm-dialog>
  `,
  styles: [`
    :host {
      display: block;
      min-height: 100vh;
      background: var(--color-bg-primary);
      color: var(--color-text-primary);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    }
  `]
})
export class AppComponent {
  title = 'Merge Search Dashboard';
}
