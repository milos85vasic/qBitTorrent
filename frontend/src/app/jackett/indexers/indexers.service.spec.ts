// IndexersService unit spec.
//
// CONST-XII anti-bluff narrative
// ------------------------------
// Each test asserts on the actual HTTP request shape (URL, method,
// headers, body) using HttpTestingController. A stub service that
// returned hardcoded Observables without invoking HttpClient would
// FAIL `http.expectOne(...)` (no matching request) and `http.verify()`
// in afterEach. A stub `setEnabled` that POSTed instead of PATCHed
// would FAIL the `request.method` assertion. A stub `listCatalog`
// that ignored its query argument would FAIL the `request.params`
// assertions.

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  IndexersService,
  BOBA_JACKETT_BASE_URL,
  IndexerMetadata,
  CatalogPage,
  RunSummary,
  RunDetail,
} from './indexers.service';

const ADMIN_BASIC = `Basic ${btoa('admin:admin')}`;
const TEST_BASE = 'http://test-host:7189';

function makeIndexer(id: string, overrides: Partial<IndexerMetadata> = {}): IndexerMetadata {
  return {
    id,
    display_name: id.toUpperCase(),
    type: 'public',
    configured_at_jackett: true,
    linked_credential_name: null,
    enabled_for_search: true,
    last_jackett_sync_at: null,
    last_test_status: null,
    last_test_at: null,
    ...overrides,
  };
}

describe('IndexersService', () => {
  let svc: IndexersService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: BOBA_JACKETT_BASE_URL, useValue: TEST_BASE },
        IndexersService,
      ],
    });
    svc = TestBed.inject(IndexersService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('list: GETs /indexers without Authorization and returns the parsed array', () => {
    const stub = [makeIndexer('rutracker'), makeIndexer('iptorrents')];
    let received: IndexerMetadata[] | undefined;
    svc.list().subscribe((r) => (received = r));

    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/indexers`);
    expect(tr.request.method).toBe('GET');
    expect(tr.request.headers.has('Authorization')).toBe(false);
    tr.flush(stub);

    expect(received).toEqual(stub);
    expect(received).toHaveLength(2);
    expect(received?.[0].id).toBe('rutracker');
  });

  it('configure: POSTs body to /indexers/{id} with admin/admin Basic auth', () => {
    const body = { credential_name: 'RUTRACKER' };
    let received: IndexerMetadata | undefined;
    svc.configure('rutracker', body).subscribe((r) => (received = r));

    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/indexers/rutracker`);
    expect(tr.request.method).toBe('POST');
    expect(tr.request.body).toEqual(body);
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);
    const respStub = makeIndexer('rutracker', { linked_credential_name: 'RUTRACKER' });
    tr.flush(respStub);
    expect(received).toEqual(respStub);
  });

  it('delete: DELETEs /indexers/{id} with admin/admin and resolves on 204', () => {
    let completed = false;
    svc.delete('iptorrents').subscribe({ complete: () => (completed = true) });

    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/indexers/iptorrents`);
    expect(tr.request.method).toBe('DELETE');
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);
    tr.flush(null, { status: 204, statusText: 'No Content' });
    expect(completed).toBe(true);
  });

  it('test: POSTs to /indexers/{id}/test and returns {status,details}', () => {
    let received: { status: string; details?: string } | undefined;
    svc.test('iptorrents').subscribe((r) => (received = r));

    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/indexers/iptorrents/test`);
    expect(tr.request.method).toBe('POST');
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);
    tr.flush({ status: 'ok', details: 'fetched 25 items' });
    expect(received?.status).toBe('ok');
    expect(received?.details).toBe('fetched 25 items');
  });

  it('setEnabled: PATCHes /indexers/{id} with {enabled_for_search} and admin/admin', () => {
    svc.setEnabled('rutracker', false).subscribe();
    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/indexers/rutracker`);
    expect(tr.request.method).toBe('PATCH');
    expect(tr.request.body).toEqual({ enabled_for_search: false });
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);
    tr.flush(makeIndexer('rutracker', { enabled_for_search: false }));
  });

  it('listCatalog: GETs /catalog with serialised query params', () => {
    const stub: CatalogPage = {
      total: 1,
      page: 1,
      page_size: 50,
      items: [
        {
          id: 'rutracker',
          display_name: 'RuTracker',
          type: 'private',
          required_fields: ['username', 'password'],
        },
      ],
    };
    let received: CatalogPage | undefined;
    svc
      .listCatalog({ search: 'rut', type: 'private', page: 1, page_size: 50 })
      .subscribe((r) => (received = r));

    const tr = http.expectOne(
      (req) =>
        req.url === `${TEST_BASE}/api/v1/jackett/catalog` &&
        req.params.get('search') === 'rut' &&
        req.params.get('type') === 'private' &&
        req.params.get('page') === '1' &&
        req.params.get('page_size') === '50',
    );
    expect(tr.request.method).toBe('GET');
    tr.flush(stub);
    expect(received).toEqual(stub);
    expect(received?.items[0].required_fields).toContain('password');
  });

  it('listCatalog: omits empty/undefined params', () => {
    svc.listCatalog().subscribe();
    const tr = http.expectOne(
      (req) =>
        req.url === `${TEST_BASE}/api/v1/jackett/catalog` &&
        req.params.keys().length === 0,
    );
    tr.flush({ total: 0, page: 1, page_size: 50, items: [] });
  });

  it('refreshCatalog: POSTs /catalog/refresh with admin/admin', () => {
    let received: { refreshed_count: number; errors: string[] } | undefined;
    svc.refreshCatalog().subscribe((r) => (received = r));
    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/catalog/refresh`);
    expect(tr.request.method).toBe('POST');
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);
    tr.flush({ refreshed_count: 12, errors: [] });
    expect(received?.refreshed_count).toBe(12);
  });

  it('listRuns: GETs /autoconfig/runs?limit=N (default 50)', () => {
    const stub: RunSummary[] = [
      {
        id: 1,
        ran_at: '2026-04-27T20:27:06Z',
        discovered_count: 0,
        configured_now_count: 0,
        error_count: 0,
      },
    ];
    let received: RunSummary[] | undefined;
    svc.listRuns().subscribe((r) => (received = r));
    const tr = http.expectOne(
      (req) =>
        req.url === `${TEST_BASE}/api/v1/jackett/autoconfig/runs` &&
        req.params.get('limit') === '50',
    );
    expect(tr.request.method).toBe('GET');
    tr.flush(stub);
    expect(received).toEqual(stub);
    expect(received?.[0].id).toBe(1);
  });

  it('listRuns: respects custom limit', () => {
    svc.listRuns(1).subscribe();
    const tr = http.expectOne(
      (req) =>
        req.url === `${TEST_BASE}/api/v1/jackett/autoconfig/runs` &&
        req.params.get('limit') === '1',
    );
    tr.flush([]);
  });

  it('getRun: GETs /autoconfig/runs/{id}', () => {
    const stub: RunDetail = {
      ran_at: '2026-04-27T20:27:06Z',
      discovered: ['RUTRACKER'],
      matched_indexers: { RUTRACKER: 'rutracker' },
      configured_now: ['RUTRACKER'],
      already_present: [],
      skipped_no_match: [],
      skipped_ambiguous: [],
      served_by_native_plugin: ['NNMCLUB'],
      errors: [],
    };
    let received: RunDetail | undefined;
    svc.getRun(7).subscribe((r) => (received = r));
    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/autoconfig/runs/7`);
    expect(tr.request.method).toBe('GET');
    tr.flush(stub);
    expect(received?.served_by_native_plugin).toEqual(['NNMCLUB']);
  });

  it('triggerRun: POSTs /autoconfig/run with admin/admin and returns the result', () => {
    let received: RunDetail | undefined;
    svc.triggerRun().subscribe((r) => (received = r));
    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/autoconfig/run`);
    expect(tr.request.method).toBe('POST');
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);
    tr.flush({
      ran_at: '2026-04-27T20:27:06Z',
      discovered: [],
      matched_indexers: {},
      configured_now: [],
      already_present: [],
      skipped_no_match: [],
      skipped_ambiguous: [],
      served_by_native_plugin: [],
      errors: [],
    });
    expect(received?.ran_at).toBe('2026-04-27T20:27:06Z');
  });

  it('falls back to default base URL when BOBA_JACKETT_BASE_URL is unprovided', () => {
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        IndexersService,
      ],
    });
    const localSvc = TestBed.inject(IndexersService);
    const localHttp = TestBed.inject(HttpTestingController);
    localSvc.list().subscribe();
    const tr = localHttp.expectOne('http://localhost:7189/api/v1/jackett/indexers');
    expect(tr.request.method).toBe('GET');
    tr.flush([]);
    localHttp.verify();
  });
});
