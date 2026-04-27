// Browse Catalog tab — server-side paginated table backed by
// GET /api/v1/jackett/catalog. Each row's "Add" opens
// IndexerAddDialogComponent pre-populated with the row's required_fields.
//
// CONST-XII: the spec asserts pagination buttons trigger fresh
// listCatalog calls with the new `page` AND that the rendered DOM
// reflects the new items. A stub that ignored the page param would
// FAIL the assertion on the request argument.
import {
  Component,
  EventEmitter,
  OnInit,
  Output,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  IndexersService,
  CatalogItem,
  CatalogPage,
  CatalogQuery,
} from './indexers.service';
import { IndexerAddDialogComponent } from './indexer-add-dialog.component';

@Component({
  selector: 'app-jackett-catalog-tab',
  standalone: true,
  imports: [CommonModule, FormsModule, IndexerAddDialogComponent],
  templateUrl: './catalog-tab.component.html',
  styleUrls: ['./catalog-tab.component.scss'],
})
export class CatalogTabComponent implements OnInit {
  private service = inject(IndexersService);

  page = signal<number>(1);
  pageSize = signal<number>(20);
  searchTerm = signal<string>('');
  total = signal<number>(0);
  items = signal<CatalogItem[]>([]);
  loading = signal<boolean>(true);
  error = signal<string | null>(null);
  refreshMessage = signal<string | null>(null);

  /** Currently-open Add dialog (null when closed). */
  dialogItem = signal<CatalogItem | null>(null);

  @Output() added = new EventEmitter<void>();

  ngOnInit(): void {
    this.fetch();
  }

  fetch(): void {
    this.loading.set(true);
    this.error.set(null);
    const q: CatalogQuery = {
      page: this.page(),
      page_size: this.pageSize(),
    };
    if (this.searchTerm() !== '') q.search = this.searchTerm();
    this.service.listCatalog(q).subscribe({
      next: (resp: CatalogPage) => {
        this.items.set(resp.items ?? []);
        this.total.set(resp.total);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  onSearchSubmit(): void {
    this.page.set(1);
    this.fetch();
  }

  onSearchInput(value: string): void {
    this.searchTerm.set(value);
  }

  prevPage(): void {
    if (this.page() <= 1) return;
    this.page.update((p) => p - 1);
    this.fetch();
  }

  nextPage(): void {
    const totalPages = Math.max(1, Math.ceil(this.total() / this.pageSize()));
    if (this.page() >= totalPages) return;
    this.page.update((p) => p + 1);
    this.fetch();
  }

  refresh(): void {
    this.refreshMessage.set(null);
    this.service.refreshCatalog().subscribe({
      next: (res) => {
        this.refreshMessage.set(
          `Refreshed ${res.refreshed_count} indexer(s)` +
            (res.errors.length > 0 ? ` (${res.errors.length} errors)` : ''),
        );
        this.fetch();
      },
      error: (err) => this.error.set(this.errorMessage(err)),
    });
  }

  openAdd(item: CatalogItem): void {
    this.dialogItem.set(item);
  }

  closeDialog(): void {
    this.dialogItem.set(null);
  }

  onSaved(): void {
    this.dialogItem.set(null);
    this.added.emit();
  }

  totalPages(): number {
    return Math.max(1, Math.ceil(this.total() / this.pageSize()));
  }

  private errorMessage(err: unknown): string {
    if (err && typeof err === 'object') {
      const e = err as {
        message?: string;
        error?: { error?: string; message?: string } | string;
      };
      if (e.error && typeof e.error === 'object') {
        return e.error.error ?? e.error.message ?? e.message ?? String(err);
      }
      if (typeof e.error === 'string' && e.error.length > 0) return e.error;
      if (e.message) return e.message;
    }
    return String(err);
  }
}
