// Autoconfig History tab — list of last-N runs with on-demand expand
// to load each run's full RunDetail (AutoconfigResult) JSON.
//
// CONST-XII: the spec asserts the trigger button POSTs /autoconfig/run
// AND that after success the list refreshes. A stub onTrigger that
// only set a state flag would FAIL the spy + the post-trigger list()
// call count assertion.
import {
  Component,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  IndexersService,
  RunSummary,
  RunDetail,
} from './indexers.service';

@Component({
  selector: 'app-jackett-history-tab',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './history-tab.component.html',
  styleUrls: ['./history-tab.component.scss'],
})
export class HistoryTabComponent implements OnInit {
  private service = inject(IndexersService);

  runs = signal<RunSummary[]>([]);
  loading = signal<boolean>(true);
  error = signal<string | null>(null);
  triggering = signal<boolean>(false);

  expandedId = signal<number | null>(null);
  detailById = signal<Record<number, RunDetail>>({});

  ngOnInit(): void {
    this.loadList();
  }

  loadList(): void {
    this.loading.set(true);
    this.error.set(null);
    this.service.listRuns(50).subscribe({
      next: (rows) => {
        this.runs.set(rows ?? []);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  onTrigger(): void {
    this.triggering.set(true);
    this.service.triggerRun().subscribe({
      next: () => {
        this.triggering.set(false);
        this.loadList();
      },
      error: (err) => {
        this.triggering.set(false);
        this.error.set(this.errorMessage(err));
      },
    });
  }

  toggleExpand(row: RunSummary): void {
    if (this.expandedId() === row.id) {
      this.expandedId.set(null);
      return;
    }
    this.expandedId.set(row.id);
    if (this.detailById()[row.id]) return;
    this.service.getRun(row.id).subscribe({
      next: (detail) => {
        this.detailById.update((m) => ({ ...m, [row.id]: detail }));
      },
      error: (err) => this.error.set(this.errorMessage(err)),
    });
  }

  detailFor(id: number): RunDetail | undefined {
    return this.detailById()[id];
  }

  detailJson(id: number): string {
    const d = this.detailById()[id];
    if (!d) return 'Loading…';
    return JSON.stringify(d, null, 2);
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
