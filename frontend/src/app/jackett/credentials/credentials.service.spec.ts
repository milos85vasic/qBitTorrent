// CredentialsService unit spec.
//
// CONST-XII anti-bluff narrative
// ------------------------------
// These tests assert on REQUEST SHAPE (URL, method, headers, body) using
// HttpTestingController.expectOne — NOT on "subscriber receives data".
// A stub service that returned a hardcoded array would FAIL `TestList`
// because `http.expectOne(...)` would never match (no real HTTP call
// fires) and `http.verify()` in afterEach would also blow up. Likewise a
// stub `upsert` that just returned `of(...)` without invoking HttpClient
// would FAIL `TestUpsert` for the same reason.

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import {
  CredentialsService,
  BOBA_JACKETT_BASE_URL,
  CredentialMetadata,
} from './credentials.service';

const ADMIN_BASIC = `Basic ${btoa('admin:admin')}`;
const TEST_BASE = 'http://test-host:7189';

describe('CredentialsService', () => {
  let svc: CredentialsService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: BOBA_JACKETT_BASE_URL, useValue: TEST_BASE },
        CredentialsService,
      ],
    });
    svc = TestBed.inject(CredentialsService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  it('TestList: GETs /api/v1/jackett/credentials WITHOUT Authorization header and returns parsed array', () => {
    const stub: CredentialMetadata[] = [
      {
        name: 'RUTRACKER',
        kind: 'userpass',
        has_username: true,
        has_password: true,
        has_cookies: false,
        created_at: '2026-04-27T00:00:00Z',
        updated_at: '2026-04-27T00:00:00Z',
        last_used_at: null,
      },
      {
        name: 'NNMCLUB',
        kind: 'cookie',
        has_username: false,
        has_password: false,
        has_cookies: true,
        created_at: '2026-04-26T00:00:00Z',
        updated_at: '2026-04-26T00:00:00Z',
        last_used_at: '2026-04-27T01:00:00Z',
      },
    ];

    let received: CredentialMetadata[] | undefined;
    svc.list().subscribe((r) => {
      received = r;
    });

    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/credentials`);
    expect(tr.request.method).toBe('GET');
    // GET is open per Task 15 — no auth header should be sent.
    expect(tr.request.headers.has('Authorization')).toBe(false);
    tr.flush(stub);

    expect(received).toEqual(stub);
    expect(received).toHaveLength(2);
    expect(received?.[0].name).toBe('RUTRACKER');
  });

  it('TestList: returns [] when backend has no credentials', () => {
    let received: CredentialMetadata[] | undefined;
    svc.list().subscribe((r) => {
      received = r;
    });
    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/credentials`);
    tr.flush([]);
    expect(received).toEqual([]);
  });

  it('TestUpsert: POSTs the body to /api/v1/jackett/credentials with admin/admin Basic auth', () => {
    const body = { name: 'X', username: 'u', password: 'p' };
    let received: CredentialMetadata | undefined;
    svc.upsert(body).subscribe((r) => {
      received = r;
    });

    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/credentials`);
    expect(tr.request.method).toBe('POST');
    expect(tr.request.body).toEqual(body);
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);

    const respStub: CredentialMetadata = {
      name: 'X',
      kind: 'userpass',
      has_username: true,
      has_password: true,
      has_cookies: false,
      created_at: '2026-04-27T00:00:00Z',
      updated_at: '2026-04-27T00:00:00Z',
      last_used_at: null,
    };
    tr.flush(respStub);
    expect(received).toEqual(respStub);
  });

  it('TestUpsert: omits unset PATCH fields from the body', () => {
    // Caller passes ONLY name + cookies — username/password must not appear.
    const body = { name: 'NNMCLUB', cookies: 'sid=abc' };
    svc.upsert(body).subscribe();

    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/credentials`);
    expect(tr.request.method).toBe('POST');
    // Verify the EXACT serialized body — extra fields would imply
    // accidental inclusion of placeholders.
    expect(tr.request.body).toEqual(body);
    expect(Object.keys(tr.request.body)).toEqual(['name', 'cookies']);
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);
    tr.flush({});
  });

  it('TestDelete: DELETEs /api/v1/jackett/credentials/:name with admin/admin Basic auth and resolves on 204', () => {
    let completed = false;
    svc.delete('RUTRACKER').subscribe({ complete: () => { completed = true; } });

    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/credentials/RUTRACKER`);
    expect(tr.request.method).toBe('DELETE');
    expect(tr.request.headers.get('Authorization')).toBe(ADMIN_BASIC);

    tr.flush(null, { status: 204, statusText: 'No Content' });
    expect(completed).toBe(true);
  });

  it('TestDelete: URL-encodes credential names containing special characters', () => {
    svc.delete('A/B').subscribe();
    // Angular's HttpClient does NOT auto-encode path segments — the
    // service must encode them itself. If it doesn't, expectOne fails
    // because the URL contains a literal '/'.
    const tr = http.expectOne(`${TEST_BASE}/api/v1/jackett/credentials/A%2FB`);
    expect(tr.request.method).toBe('DELETE');
    tr.flush(null, { status: 204, statusText: 'No Content' });
  });

  it('TestGetLatestRun: chains GET /autoconfig/runs?limit=1 then GET /autoconfig/runs/{id}', () => {
    // CONST-XII narrative: a stub getLatestRun that hardcoded a return
    // value would FAIL `http.expectOne` for the limit=1 list call AND
    // for the subsequent detail call. The composed two-step chain
    // proves we drive the real wire calls.
    let received: { served_by_native_plugin?: string[] } | null | undefined;
    svc.getLatestRun().subscribe((r) => (received = r));

    const listReq = http.expectOne(
      (req) =>
        req.url === `${TEST_BASE}/api/v1/jackett/autoconfig/runs` &&
        req.params.get('limit') === '1',
    );
    expect(listReq.request.method).toBe('GET');
    listReq.flush([
      {
        id: 42,
        ran_at: '2026-04-27T20:00:00Z',
        discovered_count: 1,
        configured_now_count: 1,
        error_count: 0,
      },
    ]);

    const detailReq = http.expectOne(
      `${TEST_BASE}/api/v1/jackett/autoconfig/runs/42`,
    );
    expect(detailReq.request.method).toBe('GET');
    detailReq.flush({
      ran_at: '2026-04-27T20:00:00Z',
      discovered: [],
      matched_indexers: {},
      configured_now: [],
      already_present: [],
      skipped_no_match: [],
      skipped_ambiguous: [],
      served_by_native_plugin: ['NNMCLUB'],
      errors: [],
    });

    expect(received).not.toBeNull();
    expect(received?.served_by_native_plugin).toEqual(['NNMCLUB']);
  });

  it('TestGetLatestRun: returns null when no runs exist (skips detail call)', () => {
    let received: unknown;
    svc.getLatestRun().subscribe((r) => (received = r));
    const listReq = http.expectOne(
      (req) =>
        req.url === `${TEST_BASE}/api/v1/jackett/autoconfig/runs` &&
        req.params.get('limit') === '1',
    );
    listReq.flush([]);
    // No detail call should be issued — afterEach's http.verify() will
    // fail if a stub naively chained anyway.
    expect(received).toBeNull();
  });

  it('falls back to the default base URL when BOBA_JACKETT_BASE_URL is not provided', () => {
    // Override-free TestBed — service uses its built-in default.
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        CredentialsService,
      ],
    });
    const localSvc = TestBed.inject(CredentialsService);
    const localHttp = TestBed.inject(HttpTestingController);

    localSvc.list().subscribe();
    const tr = localHttp.expectOne('http://localhost:7189/api/v1/jackett/credentials');
    expect(tr.request.method).toBe('GET');
    tr.flush([]);
    localHttp.verify();
  });
});
