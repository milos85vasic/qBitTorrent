// Tab container for the `/jackett/indexers` page (Tasks 28-30).
//
// Three tabs: Configured | Browse Catalog | History. Plain <button>
// tabs + a `signal<TabId>` track which is active — no @angular/material
// (per dispatch instruction). Each tab is its own standalone component
// imported lazily here.
import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ConfiguredTabComponent } from './configured-tab.component';
import { CatalogTabComponent } from './catalog-tab.component';
import { HistoryTabComponent } from './history-tab.component';

type TabId = 'configured' | 'catalog' | 'history';

@Component({
  selector: 'app-jackett-indexers',
  standalone: true,
  imports: [
    CommonModule,
    ConfiguredTabComponent,
    CatalogTabComponent,
    HistoryTabComponent,
  ],
  templateUrl: './indexers.component.html',
  styleUrls: ['./indexers.component.scss'],
})
export class IndexersComponent {
  activeTab = signal<TabId>('configured');
  /** Bumped whenever a sibling tab adds an indexer; the configured
   *  tab watches this via @Input refreshSignal and re-fetches. */
  configuredRefresh = signal<number>(0);

  setTab(t: TabId): void {
    this.activeTab.set(t);
  }

  onIndexerAdded(): void {
    this.configuredRefresh.update((n) => n + 1);
    this.activeTab.set('configured');
  }
}
