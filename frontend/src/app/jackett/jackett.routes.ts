// Lazy-loaded child routes for the boba-jackett management UI.
//
// Mounted at `/jackett` from app.routes.ts via `loadChildren`. Each
// child component is itself standalone + lazy-loaded so the JS for the
// credentials and indexers pages only ships when the operator
// navigates there.
import { Routes } from '@angular/router';

export const JACKETT_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'credentials' },
  {
    path: 'credentials',
    loadComponent: () =>
      import('./credentials/credentials.component').then((m) => m.CredentialsComponent),
  },
  {
    path: 'indexers',
    loadComponent: () =>
      import('./indexers/indexers.component').then((m) => m.IndexersComponent),
  },
];
