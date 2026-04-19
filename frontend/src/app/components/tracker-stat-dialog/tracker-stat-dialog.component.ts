import { Component, signal, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TrackerSearchStat } from '../../models/search.model';

@Component({
  selector: 'app-tracker-stat-dialog',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './tracker-stat-dialog.component.html',
  styleUrls: ['./tracker-stat-dialog.component.scss']
})
export class TrackerStatDialogComponent {
  visible = signal(false);
  stat = signal<TrackerSearchStat | null>(null);
  copyLabel = signal('Copy JSON');

  open(stat: TrackerSearchStat): void {
    this.stat.set(stat);
    this.copyLabel.set('Copy JSON');
    this.visible.set(true);
  }

  close(): void {
    this.visible.set(false);
  }

  onBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) this.close();
  }

  @HostListener('document:keydown.escape')
  onEsc(): void {
    if (this.visible()) this.close();
  }

  asJson(): string {
    const s = this.stat();
    if (!s) return '';
    try {
      return JSON.stringify(s, null, 2);
    } catch {
      return String(s);
    }
  }

  copyJson(): void {
    const text = this.asJson();
    if (!text) return;
    const done = () => {
      this.copyLabel.set('Copied!');
      setTimeout(() => this.copyLabel.set('Copy JSON'), 1500);
    };
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(() => this.fallbackCopy(text, done));
    } else {
      this.fallbackCopy(text, done);
    }
  }

  private fallbackCopy(text: string, onDone: () => void): void {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    } catch {
      // Swallow: copy failure is non-fatal.
    }
    onDone();
  }

  formatDuration(ms: number | null): string {
    if (ms === null || ms === undefined) return '-';
    if (ms < 1000) return `${ms} ms`;
    const s = ms / 1000;
    if (s < 60) return `${s.toFixed(2)} s`;
    const m = Math.floor(s / 60);
    const rem = s - m * 60;
    return `${m}m ${rem.toFixed(1)}s`;
  }

  formatTimestamp(iso: string | null): string {
    if (!iso) return '-';
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  }

  statusClass(status: string | undefined): string {
    if (!status) return 'unknown';
    return 'status-' + status;
  }

  hasNotes(): boolean {
    const s = this.stat();
    if (!s?.notes) return false;
    return Object.keys(s.notes).length > 0;
  }

  notesEntries(): { key: string; value: string }[] {
    const s = this.stat();
    if (!s?.notes) return [];
    return Object.entries(s.notes).map(([key, v]) => ({
      key,
      value: typeof v === 'string' ? v : JSON.stringify(v),
    }));
  }
}
