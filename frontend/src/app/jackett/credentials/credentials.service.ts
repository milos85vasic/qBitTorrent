// Angular client for the boba-jackett `/api/v1/jackett/credentials`
// REST surface (Tasks 14-15 backend, OpenAPI: CredentialDTO +
// CredentialPostBody).
//
// Auth model:
//   - GET    is open (no Authorization header sent — see Task 15
//            middleware which allows GET without admin/admin).
//   - POST   requires `Authorization: Basic admin:admin`.
//   - DELETE requires `Authorization: Basic admin:admin`.
//
// Plaintext credential values (`username`, `password`, `cookies`) are
// only ever sent on POST bodies — they are NEVER returned by the API
// (CredentialDTO only echoes `has_*` booleans + timestamps).
import { Injectable, InjectionToken, Optional, Inject, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

/**
 * DI token for the boba-jackett base URL. Tests override with
 * `provide: BOBA_JACKETT_BASE_URL, useValue: 'http://test-host:7189'`.
 * When unprovided, the service falls back to `DEFAULT_BASE_URL`.
 */
export const BOBA_JACKETT_BASE_URL = new InjectionToken<string>('BOBA_JACKETT_BASE_URL');

const DEFAULT_BASE_URL = 'http://localhost:7189';

/** Mirrors the OpenAPI `CredentialDTO`. Plaintext values are never echoed. */
export interface CredentialMetadata {
  /** Upper-case env-var prefix, e.g. `RUTRACKER`. */
  name: string;
  kind: 'userpass' | 'cookie';
  has_username: boolean;
  has_password: boolean;
  has_cookies: boolean;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
}

/**
 * Mirrors the OpenAPI `CredentialPostBody`. PATCH semantics — only
 * fields present on the body are updated server-side. Callers MUST omit
 * any field they do not want to change.
 */
export interface CredentialUpsertBody {
  name: string;
  username?: string;
  password?: string;
  cookies?: string;
}

/** Pre-computed `Basic admin:admin` header value. */
function adminBasicAuthHeader(): HttpHeaders {
  return new HttpHeaders({ Authorization: `Basic ${btoa('admin:admin')}` });
}

@Injectable({ providedIn: 'root' })
export class CredentialsService {
  private http = inject(HttpClient);
  private baseUrl: string;

  constructor(@Optional() @Inject(BOBA_JACKETT_BASE_URL) baseUrl?: string) {
    this.baseUrl = baseUrl ?? DEFAULT_BASE_URL;
  }

  /** GET /api/v1/jackett/credentials — open, no auth header. */
  list(): Observable<CredentialMetadata[]> {
    return this.http.get<CredentialMetadata[]>(`${this.baseUrl}/api/v1/jackett/credentials`);
  }

  /** POST /api/v1/jackett/credentials — requires admin/admin. */
  upsert(body: CredentialUpsertBody): Observable<CredentialMetadata> {
    return this.http.post<CredentialMetadata>(
      `${this.baseUrl}/api/v1/jackett/credentials`,
      body,
      { headers: adminBasicAuthHeader() },
    );
  }

  /** DELETE /api/v1/jackett/credentials/:name — requires admin/admin. */
  delete(name: string): Observable<void> {
    const encoded = encodeURIComponent(name);
    return this.http.delete<void>(
      `${this.baseUrl}/api/v1/jackett/credentials/${encoded}`,
      { headers: adminBasicAuthHeader() },
    );
  }
}
