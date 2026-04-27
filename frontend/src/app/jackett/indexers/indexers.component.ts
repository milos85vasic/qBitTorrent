// Placeholder — Task 28 will flesh this out with the real indexers
// management page (catalog browse, configured-indexers grid, etc.).
// Kept minimal here so the `/jackett/indexers` route resolves.
import { Component } from '@angular/core';

@Component({
  selector: 'app-jackett-indexers',
  standalone: true,
  template: `
    <section class="jackett-indexers-placeholder" data-testid="indexers-placeholder">
      <h2>Indexers</h2>
      <p>Coming in Task 28.</p>
    </section>
  `,
  styles: [`
    .jackett-indexers-placeholder {
      padding: 24px;
      color: var(--color-text-primary);
    }
    h2 {
      margin: 0 0 8px;
      color: var(--color-accent);
    }
  `],
})
export class IndexersComponent {}
