// Angular client for the boba-jackett `/api/v1/jackett/indexers`,
// `/catalog`, and `/autoconfig` REST surfaces (Tasks 16-22 backend,
// OpenAPI: IndexerDTO, IndexerConfigureBody, IndexerPatchBody,
// IndexerTestResult, CatalogPageDTO, CatalogRefreshResultDTO,
// RunSummaryDTO, AutoconfigResult).
//
// Auth model:
//   - GET    is open (no Authorization header sent — Task 15 middleware
//            allows GET without admin/admin).
//   - POST   requires `Authorization: Basic admin:admin`.
//   - PATCH  requires `Authorization: Basic admin:admin`.
//   - DELETE requires `Authorization: Basic admin:admin`.
import {
  Injectable,
  InjectionToken,
  Optional,
  Inject,
  inject,
} from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

/**
 * DI token for the boba-jackett base URL. Tests override with
 * `provide: BOBA_JACKETT_BASE_URL, useValue: 'http://test-host:7189'`.
 */
export const BOBA_JACKETT_BASE_URL = new InjectionToken<string>(
  'BOBA_JACKETT_BASE_URL_INDEXERS',
);

const DEFAULT_BASE_URL =
  typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:7189`
    : 'http://localhost:7189';

export type IndexerTestStatus =
  | 'ok'
  | 'auth_failed'
  | 'unreachable'
  | 'empty_results';

/** Mirrors the OpenAPI `IndexerDTO`. */
export interface IndexerMetadata {
  id: string;
  display_name: string;
  type: string;
  configured_at_jackett: boolean;
  linked_credential_name: string | null;
  enabled_for_search: boolean;
  last_jackett_sync_at: string | null;
  last_test_status: IndexerTestStatus | null;
  last_test_at: string | null;
}

export interface IndexerConfigureBody {
  credential_name: string;
  extra_fields?: Array<Record<string, unknown>>;
}

export interface IndexerTestResult {
  status: IndexerTestStatus;
  details?: string;
}

/** Mirrors `CatalogItemDTO`. */
export interface CatalogItem {
  id: string;
  display_name: string;
  type: string;
  language?: string;
  description?: string;
  required_fields: string[];
}

/** Mirrors `CatalogPageDTO`. */
export interface CatalogPage {
  total: number;
  page: number;
  page_size: number;
  items: CatalogItem[];
}

export interface CatalogQuery {
  search?: string;
  type?: string;
  language?: string;
  page?: number;
  page_size?: number;
}

export interface CatalogRefreshResult {
  refreshed_count: number;
  errors: string[];
}

/** Mirrors `RunSummaryDTO`. */
export interface RunSummary {
  id: number;
  ran_at: string;
  discovered_count: number;
  configured_now_count: number;
  error_count: number;
}

/** Mirrors `AutoconfigResult` (full run detail). */
export interface RunDetail {
  ran_at: string;
  discovered: string[];
  matched_indexers: Record<string, string>;
  configured_now: string[];
  already_present: string[];
  skipped_no_match: string[];
  skipped_ambiguous: Array<{ env_name?: string; candidates?: string[] }>;
  served_by_native_plugin: string[];
  errors: string[];
}

function adminBasicAuthHeader(): HttpHeaders {
  return new HttpHeaders({ Authorization: `Basic ${btoa('admin:admin')}` });
}

@Injectable({ providedIn: 'root' })
export class IndexersService {
  private http = inject(HttpClient);
  private baseUrl: string;

  constructor(@Optional() @Inject(BOBA_JACKETT_BASE_URL) baseUrl?: string) {
    this.baseUrl = baseUrl ?? DEFAULT_BASE_URL;
  }

  /** GET /api/v1/jackett/indexers — open, no auth header. */
  list(): Observable<IndexerMetadata[]> {
    return this.http.get<IndexerMetadata[]>(
      `${this.baseUrl}/api/v1/jackett/indexers`,
    );
  }

  /** POST /api/v1/jackett/indexers/{id} — admin/admin. */
  configure(
    id: string,
    body: IndexerConfigureBody,
  ): Observable<IndexerMetadata> {
    return this.http.post<IndexerMetadata>(
      `${this.baseUrl}/api/v1/jackett/indexers/${encodeURIComponent(id)}`,
      body,
      { headers: adminBasicAuthHeader() },
    );
  }

  /** DELETE /api/v1/jackett/indexers/{id} — admin/admin. */
  delete(id: string): Observable<void> {
    return this.http.delete<void>(
      `${this.baseUrl}/api/v1/jackett/indexers/${encodeURIComponent(id)}`,
      { headers: adminBasicAuthHeader() },
    );
  }

  /** POST /api/v1/jackett/indexers/{id}/test — admin/admin. */
  test(id: string): Observable<IndexerTestResult> {
    return this.http.post<IndexerTestResult>(
      `${this.baseUrl}/api/v1/jackett/indexers/${encodeURIComponent(id)}/test`,
      {},
      { headers: adminBasicAuthHeader() },
    );
  }

  /** PATCH /api/v1/jackett/indexers/{id} — admin/admin. */
  setEnabled(id: string, enabled: boolean): Observable<IndexerMetadata> {
    return this.http.patch<IndexerMetadata>(
      `${this.baseUrl}/api/v1/jackett/indexers/${encodeURIComponent(id)}`,
      { enabled_for_search: enabled },
      { headers: adminBasicAuthHeader() },
    );
  }

  /** GET /api/v1/jackett/catalog — open. */
  listCatalog(query: CatalogQuery = {}): Observable<CatalogPage> {
    let params = new HttpParams();
    if (query.search !== undefined && query.search !== '')
      params = params.set('search', query.search);
    if (query.type !== undefined && query.type !== '')
      params = params.set('type', query.type);
    if (query.language !== undefined && query.language !== '')
      params = params.set('language', query.language);
    if (query.page !== undefined) params = params.set('page', String(query.page));
    if (query.page_size !== undefined)
      params = params.set('page_size', String(query.page_size));
    return this.http.get<CatalogPage>(
      `${this.baseUrl}/api/v1/jackett/catalog`,
      { params },
    );
  }

  /** POST /api/v1/jackett/catalog/refresh — admin/admin. */
  refreshCatalog(): Observable<CatalogRefreshResult> {
    return this.http.post<CatalogRefreshResult>(
      `${this.baseUrl}/api/v1/jackett/catalog/refresh`,
      {},
      { headers: adminBasicAuthHeader() },
    );
  }

  /** GET /api/v1/jackett/autoconfig/runs — open. */
  listRuns(limit = 50): Observable<RunSummary[]> {
    const params = new HttpParams().set('limit', String(limit));
    return this.http.get<RunSummary[]>(
      `${this.baseUrl}/api/v1/jackett/autoconfig/runs`,
      { params },
    );
  }

  /** GET /api/v1/jackett/autoconfig/runs/{id} — open. */
  getRun(id: number): Observable<RunDetail> {
    return this.http.get<RunDetail>(
      `${this.baseUrl}/api/v1/jackett/autoconfig/runs/${id}`,
    );
  }

  /** POST /api/v1/jackett/autoconfig/run — admin/admin. */
  triggerRun(): Observable<RunDetail> {
    return this.http.post<RunDetail>(
      `${this.baseUrl}/api/v1/jackett/autoconfig/run`,
      {},
      { headers: adminBasicAuthHeader() },
    );
  }
}
