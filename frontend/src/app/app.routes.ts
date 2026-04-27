import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  {
    path: 'jackett',
    loadChildren: () =>
      import('./jackett/jackett.routes').then((m) => m.JACKETT_ROUTES),
  },
  { path: '**', redirectTo: '' },
];
