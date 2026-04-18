import { Component, inject, signal, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { ToastService } from '../../services/toast.service';
import { DialogService } from '../../services/dialog.service';
import { SseService } from '../../services/sse.service';
import {
  SearchResult, SearchResponse, ActiveDownload, Schedule, Hook,
  TrackerStatus, Source
} from '../../models/search.model';
import { MagnetDialogComponent } from '../magnet-dialog/magnet-dialog.component';
import { QbitLoginDialogComponent } from '../qbit-login-dialog/qbit-login-dialog.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, MagnetDialogComponent, QbitLoginDialogComponent],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  private dialog = inject(DialogService);
  private sse = inject(SseService);

  @ViewChild(MagnetDialogComponent) magnetDialog!: MagnetDialogComponent;
  @ViewChild(QbitLoginDialogComponent) qbitDialog!: QbitLoginDialogComponent;

  // Search state
  query = signal('');
  isSearching = signal(false);
  searchId = signal('');
  searchStatus = signal('');
  results = signal<SearchResult[]>([]);
  liveResults = signal<SearchResult[]>([]);
  totalResults = signal(0);
  mergedResults = signal(0);

  // Sorting
  sortColumn = signal('seeds');
  sortDirection = signal<'asc' | 'desc'>('desc');

  // Tabs
  activeTab = signal('results');

  // Stats
  stats = signal({ active_searches: 0, completed_searches: 0, trackers_count: 0 });
  trackers = signal<TrackerStatus[]>([]);

  // Downloads
  activeDownloads = signal<ActiveDownload[]>([]);

  // Schedules
  schedules = signal<Schedule[]>([]);
  schedName = signal('');
  schedQuery = signal('');
  schedInterval = signal(60);

  // Hooks
  hooks = signal<Hook[]>([]);

  // Auth
  qbitAuthenticated = signal(false);
  pendingAction?: { type: 'schedule' | 'addMagnet'; index: number };

  // Config
  config = signal({ qbittorrent_url: 'http://localhost:7185' });

  private sseSub?: any;
  private pollInterval?: any;
  private statsInterval?: any;

  ngOnInit(): void {
    this.loadStats();
    this.loadAuthStatus();
    this.api.getConfig().subscribe(c => this.config.set(c));
    this.statsInterval = setInterval(() => {
      this.loadStats();
      this.loadAuthStatus();
      this.loadDownloads();
    }, 30000);
  }

  ngOnDestroy(): void {
    this.sse.disconnect();
    if (this.pollInterval) clearInterval(this.pollInterval);
    if (this.statsInterval) clearInterval(this.statsInterval);
    if (this.sseSub) this.sseSub.unsubscribe();
  }

  // Stats & Auth
  loadStats(): void {
    this.api.getStats().subscribe(s => {
      this.stats.set(s);
      this.trackers.set(s.trackers || []);
    });
  }

  loadAuthStatus(): void {
    this.api.getAuthStatus().subscribe(status => {
      const qbit = status.trackers?.['qbittorrent'];
      this.qbitAuthenticated.set(!!(qbit?.has_session || qbit?.authenticated));
    });
  }

  // Search
  doSearch(): void {
    if (this.isSearching()) {
      this.abortSearch();
      return;
    }
    const q = this.query().trim();
    if (!q) return;

    this.isSearching.set(true);
    this.searchStatus.set('Searching...');
    this.results.set([]);
    this.liveResults.set([]);

    this.api.search({ query: q, limit: 50, sort_by: this.sortColumn(), sort_order: this.sortDirection() }).subscribe({
      next: (resp) => {
        this.searchId.set(resp.search_id);
        this.searchStatus.set(`Found ${resp.total_results} results...`);
        if (resp.status === 'completed' && resp.results.length > 0) {
          this.results.set(resp.results);
          this.totalResults.set(resp.total_results);
          this.mergedResults.set(resp.merged_results);
          this.searchStatus.set(`Found ${resp.total_results} results (${resp.merged_results} merged)`);
          this.isSearching.set(false);
        } else {
          this.connectSse(resp.search_id);
        }
      },
      error: (err) => {
        this.toast.error('Search failed: ' + (err.error?.detail || err.message));
        this.isSearching.set(false);
        this.searchStatus.set('Search failed');
      }
    });
  }

  connectSse(searchId: string): void {
    this.sse.connect(searchId);
    this.sseSub = this.sse.events.subscribe(event => {
      switch (event.event) {
        case 'result_found':
          this.addLiveResult(event.data);
          break;
        case 'results_update':
          this.searchStatus.set(`Found ${event.data.total_results} results...`);
          break;
        case 'search_complete':
          this.isSearching.set(false);
          if (event.data.total_results > 0) {
            this.searchStatus.set(`Found ${event.data.total_results} results (${event.data.merged_results} merged)`);
            this.loadSearchResults(searchId);
          } else {
            this.searchStatus.set('No results found.');
          }
          this.sse.disconnect();
          break;
        case 'error':
          this.toast.warning('Real-time connection error');
          this.isSearching.set(false);
          this.sse.disconnect();
          break;
      }
    });
  }

  loadSearchResults(searchId: string): void {
    this.api.getSearch(searchId).subscribe(resp => {
      this.results.set(resp.results);
      this.totalResults.set(resp.total_results);
      this.mergedResults.set(resp.merged_results);
    });
  }

  abortSearch(): void {
    const sid = this.searchId();
    if (sid) {
      this.api.abortSearch(sid).subscribe(() => {
        this.toast.info('Search cancelled');
      });
    }
    this.sse.disconnect();
    this.isSearching.set(false);
    this.searchStatus.set('Search cancelled.');
  }

  addLiveResult(data: any): void {
    const normalized: SearchResult = {
      name: data.name || 'Unknown',
      size: data.size || '0 B',
      seeds: data.seeds || 0,
      leechers: data.leechers || 0,
      tracker: data.tracker || 'unknown',
      download_urls: [data.link || ''],
      sources: [{ tracker: data.tracker || 'unknown', seeds: data.seeds || 0, leechers: data.leechers || 0 }],
      quality: 'unknown',
      content_type: 'unknown',
      metadata: null,
      freeleech: false
    };
    this.liveResults.update(r => [...r, normalized]);
  }

  // Sorting
  sortResults(column: string): void {
    if (this.sortColumn() === column) {
      this.sortDirection.update(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      this.sortColumn.set(column);
      this.sortDirection.set('desc');
    }
    this.renderSortedResults();
  }

  renderSortedResults(): void {
    const col = this.sortColumn();
    const dir = this.sortDirection();
    const qw: Record<string, number> = { uhd_8k: 6, uhd_4k: 5, full_hd: 4, hd: 3, sd: 2, unknown: 1 };

    const sorted = [...this.results()];
    sorted.sort((a, b) => {
      let cmp = 0;
      switch (col) {
        case 'name':
          cmp = (a.name || '').toLowerCase().localeCompare((b.name || '').toLowerCase());
          break;
        case 'type': {
          const av = a.content_type || 'unknown';
          const bv = b.content_type || 'unknown';
          const unknownFirst = dir === 'desc';
          if (av === 'unknown' && bv !== 'unknown') return unknownFirst ? -1 : 1;
          if (bv === 'unknown' && av !== 'unknown') return unknownFirst ? 1 : -1;
          cmp = av.localeCompare(bv);
          break;
        }
        case 'size':
          cmp = this.parseSize(a.size) - this.parseSize(b.size);
          break;
        case 'seeds':
          cmp = (a.seeds || 0) - (b.seeds || 0);
          break;
        case 'leechers':
          cmp = (a.leechers || 0) - (b.leechers || 0);
          break;
        case 'quality':
          cmp = (qw[a.quality] || 1) - (qw[b.quality] || 1);
          break;
        case 'sources':
          cmp = (a.sources?.length || 0) - (b.sources?.length || 0);
          break;
      }
      return dir === 'asc' ? cmp : -cmp;
    });
    this.results.set(sorted);
  }

  parseSize(sizeStr: string): number {
    if (!sizeStr) return 0;
    const m = sizeStr.match(/([\d.]+)\s*([KMGT]?B)/i);
    if (!m) return 0;
    const val = parseFloat(m[1]);
    const unit = m[2].toUpperCase();
    const mult: Record<string, number> = { B: 1, KB: 1024, MB: 1024 ** 2, GB: 1024 ** 3, TB: 1024 ** 4 };
    return val * (mult[unit] || 1);
  }

  formatSize(value: number | string): string {
    if (!value && value !== 0) return '0 B';
    if (typeof value === 'string') {
      if (value.match(/^[\d.]+\s*[KMGT]?B$/i)) return value;
      const num = parseFloat(value);
      if (!isNaN(num)) value = num; else return value || '0 B';
    }
    const bytes = parseFloat(String(value)) || 0;
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
  }

  getSortClass(col: string): string {
    if (this.sortColumn() !== col) return 'sortable';
    return 'sortable ' + this.sortDirection();
  }

  // Actions
  async doSchedule(index: number): Promise<void> {
    const results = this.results();
    const r = results[index];
    if (!r) return;

    const confirmed = await this.dialog.confirm({
      title: 'Send to qBittorrent?',
      message: `Add "${r.name}" to qBittorrent?`,
      confirmText: 'Send',
      cancelText: 'Cancel'
    });
    if (!confirmed) return;

    if (!this.qbitAuthenticated()) {
      this.pendingAction = { type: 'schedule', index };
      this.qbitDialog.open(() => this.executeSchedule(index));
      return;
    }
    this.executeSchedule(index);
  }

  executeSchedule(index: number): void {
    const r = this.results()[index];
    if (!r) return;
    this.api.download({ result_id: String(index), download_urls: r.download_urls }).subscribe({
      next: (res) => {
        if (res.status === 'initiated' || res.added_count > 0) {
          this.toast.success(`Sent "${r.name}" to qBittorrent`);
        } else if (res.status === 'auth_failed') {
          this.toast.error('qBittorrent auth failed. Please login.');
          this.pendingAction = { type: 'schedule', index };
          this.qbitDialog.open(() => this.executeSchedule(index));
        } else {
          this.toast.error('Failed to send to qBittorrent');
        }
      },
      error: (err) => {
        this.toast.error('Error: ' + (err.error?.error || err.message));
      }
    });
  }

  async doDownload(index: number): Promise<void> {
    const r = this.results()[index];
    if (!r) return;

    const confirmed = await this.dialog.confirm({
      title: 'Download Torrent?',
      message: `Download "${r.name}"?`,
      confirmText: 'Download',
      cancelText: 'Cancel'
    });
    if (!confirmed) return;

    this.api.downloadFile({ result_id: String(index), download_urls: r.download_urls }).subscribe({
      next: (blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'download.torrent';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        this.toast.success(`Downloaded "${r.name}"`);
      },
      error: () => {
        this.toast.error('Download failed');
      }
    });
  }

  async doMagnet(index: number): Promise<void> {
    const r = this.results()[index];
    if (!r) return;
    this.api.generateMagnet({ result_id: r.name, download_urls: r.download_urls }).subscribe({
      next: (res) => {
        this.magnetDialog.open(res.magnet, () => {
          this.api.download({ result_id: String(index), download_urls: [res.magnet] }).subscribe({
            next: (dres) => {
              if (dres.added_count > 0) {
                this.toast.success('Added magnet to qBittorrent');
              } else {
                this.toast.error('Failed to add magnet');
              }
            },
            error: () => this.toast.error('Failed to add magnet')
          });
        });
      },
      error: () => this.toast.error('Failed to generate magnet link')
    });
  }

  // Tab: Downloads
  loadDownloads(): void {
    this.api.getActiveDownloads().subscribe(d => {
      this.activeDownloads.set(d.downloads || []);
    });
  }

  // Tab: Schedules
  loadSchedules(): void {
    this.api.getSchedules().subscribe(s => {
      this.schedules.set(s.schedules || []);
    });
  }

  createSchedule(): void {
    const name = this.schedName().trim();
    const query = this.schedQuery().trim();
    const interval = this.schedInterval();
    if (!name || !query) return;
    this.api.createSchedule({ name, query, interval_minutes: interval }).subscribe({
      next: () => {
        this.toast.success('Schedule created');
        this.schedName.set('');
        this.schedQuery.set('');
        this.loadSchedules();
      },
      error: () => this.toast.error('Failed to create schedule')
    });
  }

  deleteSchedule(id: string): void {
    this.api.deleteSchedule(id).subscribe({
      next: () => {
        this.toast.success('Schedule deleted');
        this.loadSchedules();
      },
      error: () => this.toast.error('Failed to delete schedule')
    });
  }

  // Tab: Hooks
  loadHooks(): void {
    this.api.getHooks().subscribe(h => {
      this.hooks.set(h.hooks || []);
    });
  }

  deleteHook(id: string): void {
    this.api.deleteHook(id).subscribe({
      next: () => {
        this.toast.success('Hook deleted');
        this.loadHooks();
      },
      error: () => this.toast.error('Failed to delete hook')
    });
  }

  // Tab switch
  switchTab(tab: string): void {
    this.activeTab.set(tab);
    if (tab === 'downloads') this.loadDownloads();
    if (tab === 'trackers') this.loadStats();
    if (tab === 'schedules') this.loadSchedules();
    if (tab === 'hooks') this.loadHooks();
  }

  downloadStateClass(state: string): string {
    if (['stalledDL', 'forcedDL', 'downloading'].includes(state)) return 'downloading';
    if (['uploading', 'stalledUP', 'forcedUP'].includes(state)) return 'seeding';
    if (['pausedDL', 'pausedUP'].includes(state)) return 'paused';
    return 'unknown';
  }

  formatEta(seconds: number): string {
    if (seconds >= 8640000) return '-';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return (h > 0 ? h + 'h ' : '') + (m > 0 ? m + 'm ' : '') + s + 's';
  }

  // Helpers
  trackerHtml(sources: Source[]): string {
    if (!sources?.length) return '';
    const counts: Record<string, number> = {};
    sources.forEach(s => { counts[s.tracker || 'unknown'] = (counts[s.tracker || 'unknown'] || 0) + 1; });
    const names = Object.keys(counts);
    if (names.length > 1 || sources.length > 1) {
      let html = '<span class="merged-indicator"><span class="merge-icon">&#x2697;</span>Merged</span>';
      names.forEach(t => {
        const isFree = t.includes('[free]');
        html += `<span class="tracker-tag${isFree ? ' freeleech' : ''}">${t} (x${counts[t]})</span>`;
      });
      return html;
    }
    const t = sources[0]?.tracker || 'unknown';
    const isFree = t.includes('[free]');
    return `<span class="tracker-tag${isFree ? ' freeleech' : ''}">${t}</span>`;
  }

  escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}
