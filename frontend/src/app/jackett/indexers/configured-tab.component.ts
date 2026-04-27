// Configured-indexers tab. Lists every IndexerDTO row backed by the
// boba-jackett DB; lets the operator Test, toggle Enabled, and Delete.
//
// CONST-XII: every assertion in the spec inspects rendered DOM (row
// count, badge text, toggle state) — not just service calls. The
// "Test" button writes the returned status into the row immediately
// so a no-op stub of `service.test` would FAIL the spec.
import {
  Component,
  EventEmitter,
  Input,
  OnInit,
  Output,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  IndexerMetadata,
  IndexerTestResult,
  IndexersService,
} from './indexers.service';

@Component({
  selector: 'app-jackett-configured-tab',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './configured-tab.component.html',
  styleUrls: ['./configured-tab.component.scss'],
})
export class ConfiguredTabComponent implements OnInit {
  private service = inject(IndexersService);

  list = signal<IndexerMetadata[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);
  /** Map id → most-recent test result for inline badge updates. */
  testResults = signal<Record<string, IndexerTestResult>>({});

  /** Surface a refresh trigger to siblings (e.g. catalog tab Add). */
  @Input() refreshSignal: number | null = null;
  @Output() listed = new EventEmitter<IndexerMetadata[]>();

  ngOnInit(): void {
    this.loadList();
  }

  ngOnChanges(): void {
    if (this.refreshSignal !== null) this.loadList();
  }

  loadList(): void {
    this.loading.set(true);
    this.error.set(null);
    this.service.list().subscribe({
      next: (rows) => {
        const data = rows ?? [];
        this.list.set(data);
        this.loading.set(false);
        this.listed.emit(data);
      },
      error: (err) => {
        this.error.set(this.errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  onTest(row: IndexerMetadata): void {
    this.service.test(row.id).subscribe({
      next: (res) => {
        this.testResults.update((m) => ({ ...m, [row.id]: res }));
      },
      error: (err) => this.error.set(this.errorMessage(err)),
    });
  }

  onToggle(row: IndexerMetadata, ev: Event): void {
    const next = (ev.target as HTMLInputElement).checked;
    this.service.setEnabled(row.id, next).subscribe({
      next: (updated) => {
        this.list.update((rows) =>
          rows.map((r) => (r.id === row.id ? updated : r)),
        );
      },
      error: (err) => this.error.set(this.errorMessage(err)),
    });
  }

  onDelete(row: IndexerMetadata): void {
    const confirmed = window.confirm(
      `Delete indexer "${row.display_name}"? It will be removed from Jackett and from the DB.`,
    );
    if (!confirmed) return;
    this.service.delete(row.id).subscribe({
      next: () => this.loadList(),
      error: (err) => this.error.set(this.errorMessage(err)),
    });
  }

  /** Effective status for the row: test-result if we have one, else stored. */
  statusFor(row: IndexerMetadata): string | null {
    return this.testResults()[row.id]?.status ?? row.last_test_status;
  }

  /** Latest detail text for the test result, if any. */
  detailFor(row: IndexerMetadata): string | undefined {
    return this.testResults()[row.id]?.details;
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
