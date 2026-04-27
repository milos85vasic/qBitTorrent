// `/jackett/credentials` page — operator-facing CRUD over the
// boba-jackett credentials store (Tasks 14-15 backend, Spec §8.1).
//
// State: pure signals (`list`, `loading`, `error`, `dialogState`). The
// service still returns Observables (HttpClient is RxJS-native); the
// component bridges into signals via subscribe + `set(...)`.
//
// PATCH semantics for upsert: the dialog only emits the fields the
// operator actually typed. The service forwards them verbatim, so the
// backend keeps unspecified fields untouched.
//
// Delete flow: `window.confirm` (no fancy custom modal yet — the
// existing dashboard `ConfirmDialog` is dashboard-coupled; cheap
// browser confirm is sufficient for an operator-only management
// surface). On confirm-true → `service.delete(name)` → on success →
// `loadList()` to refresh.
import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  CredentialsService,
  CredentialMetadata,
  CredentialUpsertBody,
} from './credentials.service';
import { CredentialEditDialogComponent } from './credential-edit-dialog.component';

/**
 * Task 32 — informational banner driven by the most recent
 * AutoconfigResult.served_by_native_plugin list. The credentials those
 * names point to are wired into the qBittorrent native plugin (Boba's
 * own scrapers) instead of Jackett. Showing this avoids the operator
 * thinking "my credentials aren't being used" when they actually are
 * — just by a different code path.
 */

interface DialogState {
  open: boolean;
  /** null → "Add" mode; otherwise "Edit" mode pinned to that row. */
  existing: CredentialMetadata | null;
}

@Component({
  selector: 'app-jackett-credentials',
  standalone: true,
  imports: [CommonModule, CredentialEditDialogComponent],
  templateUrl: './credentials.component.html',
  styleUrls: ['./credentials.component.scss'],
})
export class CredentialsComponent implements OnInit {
  private service = inject(CredentialsService);

  list = signal<CredentialMetadata[]>([]);
  loading = signal<boolean>(true);
  error = signal<string | null>(null);
  dialogState = signal<DialogState>({ open: false, existing: null });
  /** Task 32 — names that the autoconfig run flagged as served by a native qBittorrent plugin. */
  servedByNativePlugin = signal<string[]>([]);

  ngOnInit(): void {
    this.loadList();
    this.loadLatestRun();
  }

  private loadLatestRun(): void {
    this.service.getLatestRun().subscribe({
      next: (detail) => {
        this.servedByNativePlugin.set(detail?.served_by_native_plugin ?? []);
      },
      error: () => {
        // Banner is informational; suppress errors to avoid masking the
        // primary credentials error surface.
        this.servedByNativePlugin.set([]);
      },
    });
  }

  loadList(): void {
    this.loading.set(true);
    this.error.set(null);
    this.service.list().subscribe({
      next: (creds) => {
        this.list.set(creds ?? []);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(this.errorMessage(err));
        this.loading.set(false);
      },
    });
  }

  openAdd(): void {
    this.dialogState.set({ open: true, existing: null });
  }

  openEdit(row: CredentialMetadata): void {
    this.dialogState.set({ open: true, existing: row });
  }

  closeDialog(): void {
    this.dialogState.set({ open: false, existing: null });
  }

  onSave(body: CredentialUpsertBody): void {
    this.service.upsert(body).subscribe({
      next: () => {
        this.closeDialog();
        this.loadList();
      },
      error: (err) => {
        this.error.set(this.errorMessage(err));
      },
    });
  }

  onDelete(row: CredentialMetadata): void {
    const confirmed = window.confirm(
      `Delete credential "${row.name}"? This removes it from the DB and from .env.`,
    );
    if (!confirmed) return;
    this.service.delete(row.name).subscribe({
      next: () => this.loadList(),
      error: (err) => this.error.set(this.errorMessage(err)),
    });
  }

  /** Coalesce HttpErrorResponse | Error | unknown into a display string. */
  private errorMessage(err: unknown): string {
    if (err && typeof err === 'object') {
      const e = err as { message?: string; error?: { error?: string; message?: string } | string };
      if (e.error && typeof e.error === 'object') {
        return e.error.error ?? e.error.message ?? e.message ?? String(err);
      }
      if (typeof e.error === 'string' && e.error.length > 0) return e.error;
      if (e.message) return e.message;
    }
    return String(err);
  }
}
