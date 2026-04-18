import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import {
  SearchRequest, SearchResponse, DownloadRequest, DownloadResponse,
  ActiveDownload, Schedule, Hook, AuthStatus, QbitCredentials,
  MagnetResponse, StatsResponse
} from '../models/search.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private baseUrl = '';

  search(req: SearchRequest): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(`${this.baseUrl}/api/v1/search`, req);
  }

  getSearch(searchId: string): Observable<SearchResponse> {
    return this.http.get<SearchResponse>(`${this.baseUrl}/api/v1/search/${searchId}`);
  }

  abortSearch(searchId: string): Observable<{ search_id: string; status: string }> {
    return this.http.post<{ search_id: string; status: string }>(`${this.baseUrl}/api/v1/search/${searchId}/abort`, {});
  }

  download(req: DownloadRequest): Observable<DownloadResponse> {
    return this.http.post<DownloadResponse>(`${this.baseUrl}/api/v1/download`, req);
  }

  downloadFile(req: DownloadRequest): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/api/v1/download/file`, req, { responseType: 'blob' });
  }

  generateMagnet(req: DownloadRequest): Observable<MagnetResponse> {
    return this.http.post<MagnetResponse>(`${this.baseUrl}/api/v1/magnet`, req);
  }

  getActiveDownloads(): Observable<{ downloads: ActiveDownload[]; count: number }> {
    return this.http.get<{ downloads: ActiveDownload[]; count: number }>(`${this.baseUrl}/api/v1/downloads/active`);
  }

  getSchedules(): Observable<{ schedules: Schedule[] }> {
    return this.http.get<{ schedules: Schedule[] }>(`${this.baseUrl}/api/v1/schedules`);
  }

  createSchedule(schedule: Partial<Schedule>): Observable<Schedule> {
    return this.http.post<Schedule>(`${this.baseUrl}/api/v1/schedules`, schedule);
  }

  deleteSchedule(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/api/v1/schedules/${id}`);
  }

  getHooks(): Observable<{ hooks: Hook[]; count: number }> {
    return this.http.get<{ hooks: Hook[]; count: number }>(`${this.baseUrl}/api/v1/hooks`);
  }

  createHook(hook: Partial<Hook>): Observable<Hook> {
    return this.http.post<Hook>(`${this.baseUrl}/api/v1/hooks`, hook);
  }

  deleteHook(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/api/v1/hooks/${id}`);
  }

  getAuthStatus(): Observable<AuthStatus> {
    return this.http.get<AuthStatus>(`${this.baseUrl}/api/v1/auth/status`);
  }

  qbitLogin(creds: QbitCredentials): Observable<{ status: string; version?: string; message?: string; error?: string }> {
    return this.http.post<{ status: string; version?: string; message?: string; error?: string }>(`${this.baseUrl}/api/v1/auth/qbittorrent`, creds);
  }

  getStats(): Observable<StatsResponse> {
    return this.http.get<StatsResponse>(`${this.baseUrl}/api/v1/stats`);
  }

  getConfig(): Observable<{ qbittorrent_url: string }> {
    return this.http.get<{ qbittorrent_url: string }>(`${this.baseUrl}/api/v1/config`);
  }
}
