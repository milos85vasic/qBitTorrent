import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideRouter, Router } from '@angular/router';
import { AppComponent } from './app.component';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { SseService } from './services/sse.service';

describe('AppComponent', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        // Provide a router with the dashboard at '/' so router-outlet
        // mounts <app-dashboard> the same way main.ts does at runtime.
        provideRouter([
          { path: '', component: DashboardComponent },
        ]),
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
    expect(fx.componentInstance).toBeTruthy();
  });

  it('exposes a title property', () => {
    const fx = TestBed.createComponent(AppComponent);
    fx.detectChanges();
    expect(fx.componentInstance.title).toBe('Боба Dashboard');
  });

  it('renders the primary nav with Dashboard + Jackett links', () => {
    const fx = TestBed.createComponent(AppComponent);
    fx.detectChanges();
    const el = fx.nativeElement as HTMLElement;
    const dash = el.querySelector('[data-testid="nav-dashboard"]');
    const jackett = el.querySelector('[data-testid="nav-jackett"]');
    expect(dash?.getAttribute('href')).toBe('/');
    expect(jackett?.getAttribute('href')).toBe('/jackett');
  });

  it('renders the dashboard via router-outlet on /, plus toast/confirm chrome', async () => {
    const fx = TestBed.createComponent(AppComponent);
    const router = TestBed.inject(Router);
    fx.detectChanges();
    await router.navigate(['/']);
    fx.detectChanges();
    drainBootstrapRequests();
    fx.detectChanges();
    const el = fx.nativeElement as HTMLElement;
    expect(el.querySelector('app-dashboard')).not.toBeNull();
    expect(el.querySelector('app-toast-container')).not.toBeNull();
    expect(el.querySelector('app-confirm-dialog')).not.toBeNull();
  });
});
