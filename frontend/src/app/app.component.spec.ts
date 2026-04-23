import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { AppComponent } from './app.component';
import { SseService } from './services/sse.service';

describe('AppComponent', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        // Stub SseService since AppComponent > DashboardComponent injects it.
        { provide: SseService, useValue: { connect: () => { /* no-op */ }, disconnect: () => { /* no-op */ }, events: { subscribe: () => ({ unsubscribe: () => { /* no-op */ } }) } } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    try { http.verify(); } catch { /* drained in test */ }
  });

  function drainBootstrapRequests(): void {
    http.expectOne('/api/v1/stats').flush({ active_searches: 0, completed_searches: 0, trackers_count: 0, trackers: [] });
    http.expectOne('/api/v1/auth/status').flush({ trackers: {} });
    http.expectOne('/api/v1/config').flush({ qbittorrent_url: 'http://localhost:7185' });
  }

  it('creates the app', () => {
    const fx = TestBed.createComponent(AppComponent);
    fx.detectChanges();
    drainBootstrapRequests();
    expect(fx.componentInstance).toBeTruthy();
  });

  it('exposes a title property', () => {
    const fx = TestBed.createComponent(AppComponent);
    fx.detectChanges();
    drainBootstrapRequests();
    expect(fx.componentInstance.title).toBe('Боба Dashboard');
  });

  it('renders the dashboard, toast container, and confirm dialog', () => {
    const fx = TestBed.createComponent(AppComponent);
    fx.detectChanges();
    drainBootstrapRequests();
    fx.detectChanges();
    const el = fx.nativeElement as HTMLElement;
    expect(el.querySelector('app-dashboard')).not.toBeNull();
    expect(el.querySelector('app-toast-container')).not.toBeNull();
    expect(el.querySelector('app-confirm-dialog')).not.toBeNull();
  });
});
