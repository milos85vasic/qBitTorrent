import { describe, it, expect } from 'vitest';
import type {
  SearchRequest,
  SearchResponse,
  SearchResult,
  Source,
  Metadata,
  TrackerStatus,
  DownloadRequest,
  DownloadResponse,
  DownloadResult,
  ActiveDownload,
  Schedule,
  Hook,
  AuthStatus,
  QbitCredentials,
  MagnetResponse,
  StatsResponse,
  Toast,
} from './search.model';

// NOTE: search.model.ts only contains TypeScript interfaces (no runtime
// classes or factory functions). The best we can do at runtime is
// structurally validate objects that claim to conform. These tests
// pin down the expected shape so accidental field renames are caught
// during compilation AND at runtime via JSON round-trip.

describe('search.model interfaces', () => {
  describe('SearchRequest', () => {
    it('accepts the minimal required shape', () => {
      const req: SearchRequest = { query: 'ubuntu' };
      expect(req.query).toBe('ubuntu');
    });

    it('accepts all optional fields', () => {
      const req: SearchRequest = {
        query: 'ubuntu',
        category: 'linux',
        limit: 50,
        enable_metadata: true,
        validate_trackers: false,
        sort_by: 'seeds',
        sort_order: 'desc',
      };
      expect(req.sort_order).toBe('desc');
      expect(req.limit).toBe(50);
    });
  });

  describe('Source', () => {
    it('has tracker + seed/leecher counts', () => {
      const s: Source = { tracker: 'rutracker', seeds: 42, leechers: 7 };
      expect(s.tracker).toBe('rutracker');
      expect(s.seeds + s.leechers).toBe(49);
    });
  });

  describe('SearchResult', () => {
    it('constructs a complete result including metadata null', () => {
      const result: SearchResult = {
        name: 'Ubuntu 22.04',
        size: '3.5 GB',
        seeds: 100,
        leechers: 2,
        download_urls: ['magnet:?xt=urn:btih:abc'],
        quality: 'full_hd',
        content_type: 'software',
        sources: [{ tracker: 'rutracker', seeds: 100, leechers: 2 }],
        metadata: null,
        freeleech: false,
      };
      expect(result.sources).toHaveLength(1);
      expect(result.metadata).toBeNull();
      expect(result.freeleech).toBe(false);
    });

    it('accepts rich metadata', () => {
      const meta: Metadata = {
        source: 'tmdb',
        title: 'Ubuntu',
        year: 2022,
        content_type: 'software',
        poster_url: 'https://example.com/p.jpg',
        overview: 'linux',
        genres: ['OS'],
      };
      const result: SearchResult = {
        name: 'x',
        size: '1 GB',
        seeds: 0,
        leechers: 0,
        download_urls: [],
        quality: 'unknown',
        content_type: 'unknown',
        sources: [],
        metadata: meta,
        freeleech: true,
      };
      expect(result.metadata?.title).toBe('Ubuntu');
      expect(result.metadata?.year).toBe(2022);
    });
  });

  describe('SearchResponse', () => {
    it('survives JSON round-trip', () => {
      const resp: SearchResponse = {
        search_id: 'abc',
        query: 'q',
        status: 'completed',
        results: [],
        total_results: 0,
        merged_results: 0,
        trackers_searched: ['rutracker'],
        started_at: '2026-01-01T00:00:00Z',
        completed_at: '2026-01-01T00:00:05Z',
      };
      const decoded = JSON.parse(JSON.stringify(resp)) as SearchResponse;
      expect(decoded.search_id).toBe('abc');
      expect(decoded.trackers_searched).toEqual(['rutracker']);
    });
  });

  describe('TrackerStatus', () => {
    it('round-trips optional last_checked', () => {
      const t: TrackerStatus = {
        name: 'rutracker',
        url: 'https://rutracker.org',
        enabled: true,
        health_status: 'healthy',
      };
      expect(t.last_checked).toBeUndefined();
    });
  });

  describe('DownloadRequest / DownloadResponse / DownloadResult', () => {
    it('carries result_id + download_urls', () => {
      const req: DownloadRequest = {
        result_id: 'r-1',
        download_urls: ['https://a', 'https://b'],
      };
      expect(req.download_urls).toHaveLength(2);
    });

    it('DownloadResponse aggregates per-url results', () => {
      const dr: DownloadResult = {
        url: 'https://a',
        status: 'ok',
        method: 'magnet',
      };
      const resp: DownloadResponse = {
        download_id: 'd',
        status: 'initiated',
        urls_count: 1,
        added_count: 1,
        results: [dr],
      };
      expect(resp.results[0].url).toBe('https://a');
      expect(resp.added_count).toBe(resp.urls_count);
    });
  });

  describe('ActiveDownload', () => {
    it('has numeric bandwidth + progress fields', () => {
      const d: ActiveDownload = {
        name: 'x',
        size: 1024,
        progress: 0.5,
        dlspeed: 2048,
        upspeed: 512,
        state: 'downloading',
        hash: 'deadbeef',
        eta: 60,
      };
      expect(d.progress).toBeGreaterThanOrEqual(0);
      expect(d.progress).toBeLessThanOrEqual(1);
    });
  });

  describe('Schedule', () => {
    it('carries interval + name + query', () => {
      const s: Schedule = {
        id: '1',
        name: 'daily',
        query: 'ubuntu',
        interval_minutes: 60,
        status: 'active',
      };
      expect(s.interval_minutes).toBe(60);
    });
  });

  describe('Hook', () => {
    it('defaults enabled to an explicit boolean', () => {
      const h: Hook = {
        hook_id: 'h1',
        name: 'cool',
        event: 'download_complete',
        script_path: '/tmp/s.sh',
        enabled: true,
      };
      expect(h.enabled).toBe(true);
    });
  });

  describe('AuthStatus / QbitCredentials', () => {
    it('AuthStatus keys trackers by name', () => {
      const s: AuthStatus = {
        trackers: {
          qbittorrent: { authenticated: true, has_session: true, username: 'admin' },
        },
      };
      expect(s.trackers['qbittorrent'].username).toBe('admin');
    });

    it('QbitCredentials save is optional', () => {
      const c: QbitCredentials = { username: 'admin', password: 'admin' };
      expect(c.save).toBeUndefined();
      const c2: QbitCredentials = { ...c, save: true };
      expect(c2.save).toBe(true);
    });
  });

  describe('MagnetResponse / StatsResponse', () => {
    it('MagnetResponse includes hashes', () => {
      const m: MagnetResponse = { magnet: 'magnet:?xt=urn:btih:abc', hashes: ['abc'] };
      expect(m.hashes[0]).toBe('abc');
    });

    it('StatsResponse may omit trackers list', () => {
      const s: StatsResponse = {
        active_searches: 1,
        completed_searches: 2,
        trackers_count: 3,
      };
      expect(s.trackers).toBeUndefined();
    });
  });

  describe('Toast', () => {
    it('accepts every declared type', () => {
      const types: Toast['type'][] = ['success', 'error', 'warning', 'info'];
      for (const t of types) {
        const toast: Toast = { id: 'x', message: 'm', type: t };
        expect(toast.type).toBe(t);
      }
    });

    it('allows optional duration', () => {
      const toast: Toast = { id: 'x', message: 'm', type: 'info', duration: 100 };
      expect(toast.duration).toBe(100);
    });
  });
});
