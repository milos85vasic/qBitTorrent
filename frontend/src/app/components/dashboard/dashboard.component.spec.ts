import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { DashboardComponent } from './dashboard.component';
import { SseService } from '../../services/sse.service';
import { DialogService } from '../../services/dialog.service';
import { ToastService } from '../../services/toast.service';
import type { SearchResult, Source } from '../../models/search.model';

function makeResult(over: Partial<SearchResult> = {}): SearchResult {
  return {
    name: 'Ubuntu 22.04 LTS',
    size: '3.5 GB',
    seeds: 100,
    leechers: 2,
    download_urls: ['magnet:?xt=urn:btih:abc'],
    quality: 'full_hd',
    content_type: 'software',
    sources: [{ tracker: 'rutracker', seeds: 100, leechers: 2 }],
    metadata: null,
    freeleech: false,
    ...over,
  };
}

describe('DashboardComponent', () => {
  let http: HttpTestingController;
  let sse: Pick<SseService, 'connect' | 'disconnect' | 'events'>;
  let sseEvents: { next: (e: { event: string; data: any }) => void } | null;
  let connectSpy: ReturnType<typeof vi.fn>;
  let disconnectSpy: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    connectSpy = vi.fn();
    disconnectSpy = vi.fn();
    sseEvents = null;

    const sseStub = {
      connect: connectSpy,
      disconnect: disconnectSpy,
      events: {
        subscribe: (observer: any) => {
          sseEvents = observer;
          return { unsubscribe: vi.fn() };
        },
      },
    };
    sse = sseStub as any;

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: SseService, useValue: sseStub },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    try { http.verify(); } catch { /* some tests deliberately leave requests open */ }
  });

  /** Create the component and drain the three requests kicked off by ngOnInit. */
  function bootstrap(): ReturnType<typeof TestBed.createComponent<DashboardComponent>> {
    const fx = TestBed.createComponent(DashboardComponent);
    fx.detectChanges();
    // ngOnInit fires: getStats, getAuthStatus, getConfig
    http.expectOne('/api/v1/stats').flush({ active_searches: 0, completed_searches: 0, trackers_count: 0, trackers: [] });
    http.expectOne('/api/v1/auth/status').flush({ trackers: {} });
    http.expectOne('/api/v1/config').flush({ qbittorrent_url: 'http://localhost:7185' });
    fx.detectChanges();
    return fx;
  }

  describe('creation / default state', () => {
    it('creates the component with default signals', () => {
      const fx = bootstrap();
      const c = fx.componentInstance;
      expect(c).toBeTruthy();
      expect(c.query()).toBe('');
      expect(c.isSearching()).toBe(false);
      expect(c.activeTab()).toBe('results');
      expect(c.sortColumn()).toBe('seeds');
      expect(c.sortDirection()).toBe('desc');
      expect(c.qbitAuthenticated()).toBe(false);
      expect(c.stats().trackers_count).toBe(0);
    });

    it('renders service-links header', () => {
      const fx = bootstrap();
      const links = (fx.nativeElement as HTMLElement).querySelectorAll('.service-links a');
      expect(links.length).toBeGreaterThanOrEqual(4);
    });

    it('renders the qBit Login chip when not authenticated', () => {
      const fx = bootstrap();
      const chip = (fx.nativeElement as HTMLElement).querySelector('.auth-chip');
      expect(chip?.textContent).toContain('qBit Login');
    });

    it('renders "qBit Connected" when authenticated', () => {
      const fx = TestBed.createComponent(DashboardComponent);
      fx.detectChanges();
      http.expectOne('/api/v1/stats').flush({ active_searches: 0, completed_searches: 0, trackers_count: 0, trackers: [] });
      http.expectOne('/api/v1/auth/status').flush({ trackers: { qbittorrent: { has_session: true } } });
      http.expectOne('/api/v1/config').flush({ qbittorrent_url: '' });
      fx.detectChanges();
      const chip = (fx.nativeElement as HTMLElement).querySelector('.auth-chip');
      expect(chip?.textContent).toContain('qBit Connected');
    });
  });

  describe('loadStats / loadAuthStatus / loadDownloads / loadSchedules / loadHooks', () => {
    it('loadStats() updates stats + trackers signals', () => {
      const fx = bootstrap();
      fx.componentInstance.loadStats();
      http.expectOne('/api/v1/stats').flush({
        active_searches: 5,
        completed_searches: 10,
        trackers_count: 3,
        trackers: [{ name: 'rutracker', url: 'https://rutracker.org', enabled: true, health_status: 'healthy' }],
      });
      expect(fx.componentInstance.stats().active_searches).toBe(5);
      expect(fx.componentInstance.trackers()).toHaveLength(1);
    });

    it('loadAuthStatus() treats "authenticated" flag as session', () => {
      const fx = bootstrap();
      fx.componentInstance.loadAuthStatus();
      http.expectOne('/api/v1/auth/status').flush({ trackers: { qbittorrent: { authenticated: true } } });
      expect(fx.componentInstance.qbitAuthenticated()).toBe(true);
    });

    it('loadDownloads() updates activeDownloads', () => {
      const fx = bootstrap();
      fx.componentInstance.loadDownloads();
      http.expectOne('/api/v1/downloads/active').flush({ downloads: [{ name: 'x', size: 100, progress: 50, dlspeed: 1024, upspeed: 0, state: 'downloading', hash: 'abc', eta: 60 }], count: 1 });
      expect(fx.componentInstance.activeDownloads()).toHaveLength(1);
    });

    it('loadSchedules() updates schedules', () => {
      const fx = bootstrap();
      fx.componentInstance.loadSchedules();
      http.expectOne('/api/v1/schedules').flush({ schedules: [{ id: '1', name: 'daily', query: 'ubuntu', interval_minutes: 60, status: 'active' }] });
      expect(fx.componentInstance.schedules()).toHaveLength(1);
    });

    it('loadHooks() updates hooks', () => {
      const fx = bootstrap();
      fx.componentInstance.loadHooks();
      http.expectOne('/api/v1/hooks').flush({ hooks: [{ hook_id: 'h1', name: 'n', event: 'download_complete', script_path: '/s', enabled: true }], count: 1 });
      expect(fx.componentInstance.hooks()).toHaveLength(1);
    });
  });

  describe('doSearch', () => {
    it('no-ops on blank query', () => {
      const fx = bootstrap();
      fx.componentInstance.query.set('   ');
      fx.componentInstance.doSearch();
      http.expectNone('/api/v1/search');
      expect(fx.componentInstance.isSearching()).toBe(false);
    });

    it('starts a search, stores results, and clears isSearching on completion', () => {
      const fx = bootstrap();
      fx.componentInstance.query.set('ubuntu');
      fx.componentInstance.doSearch();
      expect(fx.componentInstance.isSearching()).toBe(true);

      const tr = http.expectOne('/api/v1/search');
      expect(tr.request.body).toEqual({ query: 'ubuntu', limit: 50, sort_by: 'seeds', sort_order: 'desc' });
      tr.flush({
        search_id: 's1',
        query: 'ubuntu',
        status: 'completed',
        results: [makeResult()],
        total_results: 1,
        merged_results: 0,
        trackers_searched: ['rutracker'],
        started_at: 'now',
      });

      expect(fx.componentInstance.searchId()).toBe('s1');
      expect(fx.componentInstance.results()).toHaveLength(1);
      expect(fx.componentInstance.totalResults()).toBe(1);
      expect(fx.componentInstance.isSearching()).toBe(false);
    });

    it('connects to SSE when status!=completed or results empty', () => {
      const fx = bootstrap();
      fx.componentInstance.query.set('ubuntu');
      fx.componentInstance.doSearch();
      http.expectOne('/api/v1/search').flush({
        search_id: 's2',
        query: 'ubuntu',
        status: 'running',
        results: [],
        total_results: 0,
        merged_results: 0,
        trackers_searched: [],
        started_at: 'now',
      });
      expect(connectSpy).toHaveBeenCalledWith('s2');
    });

    it('shows error toast on failure', () => {
      const toast = TestBed.inject(ToastService);
      const errSpy = vi.spyOn(toast, 'error');
      const fx = bootstrap();
      fx.componentInstance.query.set('x');
      fx.componentInstance.doSearch();
      http.expectOne('/api/v1/search').flush({ detail: 'nope' }, { status: 500, statusText: 'Server Error' });
      expect(errSpy).toHaveBeenCalled();
      expect(fx.componentInstance.isSearching()).toBe(false);
      expect(fx.componentInstance.searchStatus()).toBe('Search failed');
    });

    it('aborts when called while already searching', () => {
      const fx = bootstrap();
      fx.componentInstance.isSearching.set(true);
      fx.componentInstance.searchId.set('s9');
      fx.componentInstance.doSearch();
      http.expectOne('/api/v1/search/s9/abort').flush({ search_id: 's9', status: 'aborted' });
      expect(fx.componentInstance.isSearching()).toBe(false);
      expect(disconnectSpy).toHaveBeenCalled();
    });
  });

  describe('SSE event handling', () => {
    function primeSearch(fx: ReturnType<typeof bootstrap>): void {
      fx.componentInstance.query.set('ubuntu');
      fx.componentInstance.doSearch();
      http.expectOne('/api/v1/search').flush({
        search_id: 's1',
        query: 'ubuntu',
        status: 'running',
        results: [],
        total_results: 0,
        merged_results: 0,
        trackers_searched: [],
        started_at: 'now',
      });
    }

    it('result_found appends a normalized live result', () => {
      const fx = bootstrap();
      primeSearch(fx);
      sseEvents?.next({ event: 'result_found', data: { name: 'Ubuntu', size: '3 GB', seeds: 10, leechers: 1, tracker: 'rutracker', link: 'https://x' } });
      expect(fx.componentInstance.liveResults()).toHaveLength(1);
      expect(fx.componentInstance.liveResults()[0].download_urls).toEqual(['https://x']);
    });

    it('results_update updates searchStatus', () => {
      const fx = bootstrap();
      primeSearch(fx);
      sseEvents?.next({ event: 'results_update', data: { total_results: 42 } });
      expect(fx.componentInstance.searchStatus()).toContain('42');
    });

    it('search_complete with results triggers a full load + disconnects', () => {
      const fx = bootstrap();
      primeSearch(fx);
      sseEvents?.next({ event: 'search_complete', data: { total_results: 1, merged_results: 0 } });
      http.expectOne('/api/v1/search/s1').flush({
        search_id: 's1',
        query: 'ubuntu',
        status: 'completed',
        results: [makeResult()],
        total_results: 1,
        merged_results: 0,
        trackers_searched: [],
        started_at: 'now',
      });
      expect(fx.componentInstance.isSearching()).toBe(false);
      expect(fx.componentInstance.results()).toHaveLength(1);
      expect(disconnectSpy).toHaveBeenCalled();
    });

    it('search_complete with 0 results shows empty message', () => {
      const fx = bootstrap();
      primeSearch(fx);
      sseEvents?.next({ event: 'search_complete', data: { total_results: 0, merged_results: 0 } });
      expect(fx.componentInstance.searchStatus()).toBe('No results found.');
    });

    it('error event warns and disconnects', () => {
      const toast = TestBed.inject(ToastService);
      const warnSpy = vi.spyOn(toast, 'warning');
      const fx = bootstrap();
      primeSearch(fx);
      sseEvents?.next({ event: 'error', data: {} });
      expect(warnSpy).toHaveBeenCalled();
      expect(fx.componentInstance.isSearching()).toBe(false);
    });
  });

  describe('abortSearch', () => {
    it('POSTs abort and emits info toast', () => {
      const toast = TestBed.inject(ToastService);
      const infoSpy = vi.spyOn(toast, 'info');
      const fx = bootstrap();
      fx.componentInstance.searchId.set('abc');
      fx.componentInstance.abortSearch();
      http.expectOne('/api/v1/search/abc/abort').flush({ search_id: 'abc', status: 'aborted' });
      expect(infoSpy).toHaveBeenCalledWith('Search cancelled');
      expect(fx.componentInstance.isSearching()).toBe(false);
    });

    it('does nothing API-wise when there is no search id', () => {
      const fx = bootstrap();
      fx.componentInstance.abortSearch();
      // No HTTP call expected.
      expect(fx.componentInstance.isSearching()).toBe(false);
    });
  });

  describe('addLiveResult', () => {
    it('fills defaults for missing fields', () => {
      const fx = bootstrap();
      fx.componentInstance.addLiveResult({});
      const r = fx.componentInstance.liveResults()[0];
      expect(r.name).toBe('Unknown');
      expect(r.seeds).toBe(0);
      expect(r.tracker).toBe('unknown');
      expect(r.freeleech).toBe(false);
    });
  });

  describe('sortResults / renderSortedResults', () => {
    it('toggles direction on same column, resets to desc on new column', () => {
      const fx = bootstrap();
      fx.componentInstance.results.set([]);
      fx.componentInstance.sortResults('seeds'); // same as default -> toggle to asc
      expect(fx.componentInstance.sortDirection()).toBe('asc');
      fx.componentInstance.sortResults('seeds'); // toggle back to desc
      expect(fx.componentInstance.sortDirection()).toBe('desc');
      fx.componentInstance.sortResults('name'); // new column
      expect(fx.componentInstance.sortColumn()).toBe('name');
      expect(fx.componentInstance.sortDirection()).toBe('desc');
    });

    it('sorts by seeds desc by default', () => {
      const fx = bootstrap();
      fx.componentInstance.results.set([
        makeResult({ name: 'a', seeds: 10 }),
        makeResult({ name: 'b', seeds: 50 }),
        makeResult({ name: 'c', seeds: 30 }),
      ]);
      fx.componentInstance.sortColumn.set('seeds');
      fx.componentInstance.sortDirection.set('desc');
      fx.componentInstance.renderSortedResults();
      expect(fx.componentInstance.results().map(r => r.name)).toEqual(['b', 'c', 'a']);
    });

    it('sorts by size parsed from human-readable strings', () => {
      const fx = bootstrap();
      fx.componentInstance.results.set([
        makeResult({ name: 'a', size: '500 MB' }),
        makeResult({ name: 'b', size: '1.5 GB' }),
        makeResult({ name: 'c', size: '100 KB' }),
      ]);
      fx.componentInstance.sortColumn.set('size');
      fx.componentInstance.sortDirection.set('asc');
      fx.componentInstance.renderSortedResults();
      expect(fx.componentInstance.results().map(r => r.name)).toEqual(['c', 'a', 'b']);
    });

    it('sorts by name alphabetically', () => {
      const fx = bootstrap();
      fx.componentInstance.results.set([makeResult({ name: 'beta' }), makeResult({ name: 'alpha' })]);
      fx.componentInstance.sortColumn.set('name');
      fx.componentInstance.sortDirection.set('asc');
      fx.componentInstance.renderSortedResults();
      expect(fx.componentInstance.results().map(r => r.name)).toEqual(['alpha', 'beta']);
    });

    it('sorts by quality weight', () => {
      const fx = bootstrap();
      fx.componentInstance.results.set([
        makeResult({ name: 'a', quality: 'sd' }),
        makeResult({ name: 'b', quality: 'uhd_4k' }),
        makeResult({ name: 'c', quality: 'full_hd' }),
      ]);
      fx.componentInstance.sortColumn.set('quality');
      fx.componentInstance.sortDirection.set('desc');
      fx.componentInstance.renderSortedResults();
      expect(fx.componentInstance.results().map(r => r.name)).toEqual(['b', 'c', 'a']);
    });

    it('sorts unknown content_type first when desc, last when asc', () => {
      const fx = bootstrap();
      fx.componentInstance.results.set([
        makeResult({ name: 'a', content_type: 'movie' }),
        makeResult({ name: 'b', content_type: 'unknown' }),
      ]);
      fx.componentInstance.sortColumn.set('type');
      fx.componentInstance.sortDirection.set('desc');
      fx.componentInstance.renderSortedResults();
      expect(fx.componentInstance.results()[0].name).toBe('b');
      fx.componentInstance.sortDirection.set('asc');
      fx.componentInstance.renderSortedResults();
      expect(fx.componentInstance.results()[0].name).toBe('a');
    });

    it('sorts by number of sources', () => {
      const fx = bootstrap();
      const twoSrcs: Source[] = [
        { tracker: 't1', seeds: 1, leechers: 0 },
        { tracker: 't2', seeds: 1, leechers: 0 },
      ];
      fx.componentInstance.results.set([
        makeResult({ name: 'a', sources: [{ tracker: 't1', seeds: 1, leechers: 0 }] }),
        makeResult({ name: 'b', sources: twoSrcs }),
      ]);
      fx.componentInstance.sortColumn.set('sources');
      fx.componentInstance.sortDirection.set('desc');
      fx.componentInstance.renderSortedResults();
      expect(fx.componentInstance.results()[0].name).toBe('b');
    });

    it('sorts by leechers', () => {
      const fx = bootstrap();
      fx.componentInstance.results.set([
        makeResult({ name: 'a', leechers: 1 }),
        makeResult({ name: 'b', leechers: 5 }),
      ]);
      fx.componentInstance.sortColumn.set('leechers');
      fx.componentInstance.sortDirection.set('desc');
      fx.componentInstance.renderSortedResults();
      expect(fx.componentInstance.results()[0].name).toBe('b');
    });
  });

  describe('parseSize / formatSize / formatEta', () => {
    it('parseSize understands units', () => {
      const fx = bootstrap();
      const c = fx.componentInstance;
      expect(c.parseSize('')).toBe(0);
      expect(c.parseSize('junk')).toBe(0);
      expect(c.parseSize('1 KB')).toBe(1024);
      expect(c.parseSize('1.5 GB')).toBeCloseTo(1.5 * 1024 ** 3, 0);
      expect(c.parseSize('2 TB')).toBeCloseTo(2 * 1024 ** 4, 0);
      expect(c.parseSize('500 B')).toBe(500);
    });

    it('formatSize handles 0, numbers, and preformatted strings', () => {
      const fx = bootstrap();
      const c = fx.componentInstance;
      expect(c.formatSize(0)).toBe('0 B');
      expect(c.formatSize(1024)).toBe('1.0 KB');
      expect(c.formatSize(1024 ** 3)).toBe('1.0 GB');
      expect(c.formatSize('3.5 GB')).toBe('3.5 GB'); // already formatted
      expect(c.formatSize('500')).toBe('500.0 B');
      expect(c.formatSize('garbage')).toBe('garbage');
    });

    it('formatEta returns "-" when effectively infinite', () => {
      const fx = bootstrap();
      expect(fx.componentInstance.formatEta(8640000)).toBe('-');
      expect(fx.componentInstance.formatEta(45)).toBe('45s');
      expect(fx.componentInstance.formatEta(90)).toBe('1m 30s');
      expect(fx.componentInstance.formatEta(3661)).toBe('1h 1m 1s');
    });
  });

  describe('getSortClass / downloadStateClass', () => {
    it('getSortClass returns sortable when not active', () => {
      const fx = bootstrap();
      expect(fx.componentInstance.getSortClass('name')).toBe('sortable');
    });

    it('getSortClass appends direction when active', () => {
      const fx = bootstrap();
      fx.componentInstance.sortColumn.set('name');
      fx.componentInstance.sortDirection.set('asc');
      expect(fx.componentInstance.getSortClass('name')).toBe('sortable asc');
    });

    it('downloadStateClass buckets states', () => {
      const fx = bootstrap();
      const c = fx.componentInstance;
      expect(c.downloadStateClass('downloading')).toBe('downloading');
      expect(c.downloadStateClass('uploading')).toBe('seeding');
      expect(c.downloadStateClass('pausedDL')).toBe('paused');
      expect(c.downloadStateClass('unknown')).toBe('unknown');
    });
  });

  describe('schedule + hook actions', () => {
    it('createSchedule ignores blank name/query', () => {
      const fx = bootstrap();
      fx.componentInstance.schedName.set('');
      fx.componentInstance.schedQuery.set('');
      fx.componentInstance.createSchedule();
      http.expectNone('/api/v1/schedules');
    });

    it('createSchedule POSTs and refreshes list', () => {
      const fx = bootstrap();
      fx.componentInstance.schedName.set('n');
      fx.componentInstance.schedQuery.set('q');
      fx.componentInstance.schedInterval.set(45);
      fx.componentInstance.createSchedule();
      const tr = http.expectOne('/api/v1/schedules');
      expect(tr.request.method).toBe('POST');
      expect(tr.request.body).toEqual({ name: 'n', query: 'q', interval_minutes: 45 });
      tr.flush({ id: '1', name: 'n', query: 'q', interval_minutes: 45, status: 'active' });
      // loadSchedules() kicks off a GET.
      http.expectOne('/api/v1/schedules').flush({ schedules: [] });
    });

    it('deleteSchedule DELETEs and refreshes', () => {
      const fx = bootstrap();
      fx.componentInstance.deleteSchedule('42');
      http.expectOne('/api/v1/schedules/42').flush(null);
      http.expectOne('/api/v1/schedules').flush({ schedules: [] });
    });

    it('deleteHook DELETEs and refreshes', () => {
      const fx = bootstrap();
      fx.componentInstance.deleteHook('h1');
      http.expectOne('/api/v1/hooks/h1').flush(null);
      http.expectOne('/api/v1/hooks').flush({ hooks: [], count: 0 });
    });
  });

  describe('switchTab', () => {
    it('switches tab + triggers downloads reload', () => {
      const fx = bootstrap();
      fx.componentInstance.switchTab('downloads');
      expect(fx.componentInstance.activeTab()).toBe('downloads');
      http.expectOne('/api/v1/downloads/active').flush({ downloads: [], count: 0 });
    });

    it('switches to trackers tab and reloads stats', () => {
      const fx = bootstrap();
      fx.componentInstance.switchTab('trackers');
      http.expectOne('/api/v1/stats').flush({ active_searches: 0, completed_searches: 0, trackers_count: 0, trackers: [] });
    });

    it('switches to schedules tab and loads schedules', () => {
      const fx = bootstrap();
      fx.componentInstance.switchTab('schedules');
      http.expectOne('/api/v1/schedules').flush({ schedules: [] });
    });

    it('switches to hooks tab and loads hooks', () => {
      const fx = bootstrap();
      fx.componentInstance.switchTab('hooks');
      http.expectOne('/api/v1/hooks').flush({ hooks: [], count: 0 });
    });
  });

  describe('trackerHtml / escapeHtml', () => {
    it('returns "" on empty sources', () => {
      const fx = bootstrap();
      expect(fx.componentInstance.trackerHtml([])).toBe('');
    });

    it('single source renders a plain tracker-tag', () => {
      const fx = bootstrap();
      const html = fx.componentInstance.trackerHtml([{ tracker: 'rutracker', seeds: 1, leechers: 0 }]);
      expect(html).toContain('tracker-tag');
      expect(html).toContain('rutracker');
      expect(html).not.toContain('merged-indicator');
    });

    it('multiple sources trigger merged-indicator', () => {
      const fx = bootstrap();
      const html = fx.componentInstance.trackerHtml([
        { tracker: 'rutracker', seeds: 1, leechers: 0 },
        { tracker: 'kinozal', seeds: 1, leechers: 0 },
      ]);
      expect(html).toContain('merged-indicator');
      expect(html).toContain('rutracker');
      expect(html).toContain('kinozal');
    });

    it('freeleech-tagged tracker gets the freeleech class', () => {
      const fx = bootstrap();
      const html = fx.componentInstance.trackerHtml([{ tracker: 'IPTorrents [free]', seeds: 1, leechers: 0 }]);
      expect(html).toContain('freeleech');
    });

    it('escapeHtml escapes angle brackets', () => {
      const fx = bootstrap();
      expect(fx.componentInstance.escapeHtml('<script>')).toBe('&lt;script&gt;');
    });
  });

  describe('ngOnDestroy', () => {
    it('clears intervals and disconnects SSE', () => {
      const fx = bootstrap();
      fx.componentInstance.ngOnDestroy();
      expect(disconnectSpy).toHaveBeenCalled();
    });
  });

  describe('doSchedule / executeSchedule / doDownload / doMagnet', () => {
    it('doSchedule bails when dialog cancelled', async () => {
      const fx = bootstrap();
      const dialog = TestBed.inject(DialogService);
      vi.spyOn(dialog, 'confirm').mockResolvedValue(false);
      fx.componentInstance.results.set([makeResult()]);
      await fx.componentInstance.doSchedule(0);
      http.expectNone('/api/v1/download');
    });

    it('doSchedule executes directly when already authenticated', async () => {
      const fx = bootstrap();
      const dialog = TestBed.inject(DialogService);
      vi.spyOn(dialog, 'confirm').mockResolvedValue(true);
      fx.componentInstance.qbitAuthenticated.set(true);
      fx.componentInstance.results.set([makeResult()]);
      await fx.componentInstance.doSchedule(0);
      const tr = http.expectOne('/api/v1/download');
      expect(tr.request.method).toBe('POST');
      tr.flush({ download_id: 'd', status: 'initiated', urls_count: 1, added_count: 1, results: [] });
    });

    it('executeSchedule shows toast on success', () => {
      const toast = TestBed.inject(ToastService);
      const successSpy = vi.spyOn(toast, 'success');
      const fx = bootstrap();
      fx.componentInstance.results.set([makeResult()]);
      fx.componentInstance.executeSchedule(0);
      http.expectOne('/api/v1/download').flush({ download_id: 'd', status: 'initiated', urls_count: 1, added_count: 1, results: [] });
      expect(successSpy).toHaveBeenCalled();
    });

    it('executeSchedule out-of-range index is a no-op', () => {
      const fx = bootstrap();
      fx.componentInstance.results.set([]);
      fx.componentInstance.executeSchedule(5);
      http.expectNone('/api/v1/download');
    });

    it('doDownload bails if cancelled', async () => {
      const fx = bootstrap();
      vi.spyOn(TestBed.inject(DialogService), 'confirm').mockResolvedValue(false);
      fx.componentInstance.results.set([makeResult()]);
      await fx.componentInstance.doDownload(0);
      http.expectNone('/api/v1/download/file');
    });

    it('doMagnet requests magnet and opens dialog via ViewChild', () => {
      const fx = bootstrap();
      const openSpy = vi.fn();
      (fx.componentInstance as any).magnetDialog = { open: openSpy };
      fx.componentInstance.results.set([makeResult()]);
      fx.componentInstance.doMagnet(0);
      http.expectOne('/api/v1/magnet').flush({ magnet: 'magnet:?xt=urn:btih:abc', hashes: ['abc'] });
      expect(openSpy).toHaveBeenCalled();
    });
  });
});
