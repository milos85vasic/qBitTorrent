import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { QbitLoginDialogComponent } from './qbit-login-dialog.component';
import { ToastService } from '../../services/toast.service';

describe('QbitLoginDialogComponent', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [QbitLoginDialogComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
  });

  function host(fx: { nativeElement: HTMLElement }): HTMLElement {
    return fx.nativeElement;
  }

  it('renders nothing when hidden', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    expect(host(fx).querySelector('.modal-overlay')).toBeNull();
  });

  it('defaults username to "admin" and password blank', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    expect(fx.componentInstance.username()).toBe('admin');
    expect(fx.componentInstance.password()).toBe('');
    expect(fx.componentInstance.saveCreds()).toBe(false);
  });

  it('open() makes the modal visible and clears error', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.error.set('stale');
    fx.componentInstance.open();
    fx.detectChanges();
    expect(fx.componentInstance.visible()).toBe(true);
    expect(fx.componentInstance.error()).toBe('');
    expect(host(fx).querySelector('.modal-overlay')).not.toBeNull();
  });

  it('close() hides the dialog', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open();
    fx.componentInstance.close();
    fx.detectChanges();
    expect(fx.componentInstance.visible()).toBe(false);
  });

  it('login() shows error when username is missing', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.username.set('');
    fx.componentInstance.password.set('pw');
    fx.componentInstance.login();
    expect(fx.componentInstance.error()).toBe('Please enter username and password');
    expect(fx.componentInstance.loading()).toBe(false);
    http.expectNone('/api/v1/auth/qbittorrent');
  });

  it('login() shows error when password is missing', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.username.set('admin');
    fx.componentInstance.password.set('');
    fx.componentInstance.login();
    expect(fx.componentInstance.error()).toBe('Please enter username and password');
  });

  it('login() POSTs credentials on submit, clears loading, fires onSuccess on success', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    const success = vi.fn();
    fx.componentInstance.open(success);
    fx.componentInstance.password.set('admin');
    fx.componentInstance.saveCreds.set(true);
    fx.componentInstance.login();
    expect(fx.componentInstance.loading()).toBe(true);

    const tr = http.expectOne('/api/v1/auth/qbittorrent');
    expect(tr.request.method).toBe('POST');
    expect(tr.request.body).toEqual({ username: 'admin', password: 'admin', save: true });
    tr.flush({ status: 'authenticated', version: '4.6' });

    expect(fx.componentInstance.loading()).toBe(false);
    expect(fx.componentInstance.visible()).toBe(false);
    expect(success).toHaveBeenCalledTimes(1);
  });

  it('login() shows server-reported error without closing', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open();
    fx.componentInstance.password.set('bad');
    fx.componentInstance.login();
    const tr = http.expectOne('/api/v1/auth/qbittorrent');
    tr.flush({ status: 'failed', error: 'wrong password' });
    expect(fx.componentInstance.visible()).toBe(true);
    expect(fx.componentInstance.error()).toBe('wrong password');
    expect(fx.componentInstance.loading()).toBe(false);
  });

  it('login() default error message when server omits one', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open();
    fx.componentInstance.password.set('x');
    fx.componentInstance.login();
    http.expectOne('/api/v1/auth/qbittorrent').flush({ status: 'failed' });
    expect(fx.componentInstance.error()).toBe('Login failed');
  });

  it('login() surfaces connection errors', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open();
    fx.componentInstance.password.set('x');
    fx.componentInstance.login();
    const tr = http.expectOne('/api/v1/auth/qbittorrent');
    tr.flush({ error: 'network down' }, { status: 500, statusText: 'Server Error' });
    expect(fx.componentInstance.loading()).toBe(false);
    expect(fx.componentInstance.error()).toBe('network down');
  });

  it('login() falls back to "Connection error" when the error body has no detail', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open();
    fx.componentInstance.password.set('x');
    fx.componentInstance.login();
    http.expectOne('/api/v1/auth/qbittorrent').flush(null, { status: 503, statusText: 'Unavailable' });
    expect(fx.componentInstance.error()).toBe('Connection error');
  });

  it('success path emits a success toast', () => {
    const toast = TestBed.inject(ToastService);
    const spy = vi.spyOn(toast, 'success');
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open();
    fx.componentInstance.password.set('admin');
    fx.componentInstance.login();
    http.expectOne('/api/v1/auth/qbittorrent').flush({ status: 'authenticated' });
    expect(spy).toHaveBeenCalledWith('Logged in to qBittorrent');
  });

  it('onBackdrop closes when clicking overlay but not when clicking modal', () => {
    const fx = TestBed.createComponent(QbitLoginDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open();
    fx.detectChanges();
    const overlay = host(fx).querySelector('.modal-overlay') as HTMLDivElement;
    const modal = overlay.querySelector('.modal') as HTMLElement;

    const innerEvent = new MouseEvent('click');
    Object.defineProperty(innerEvent, 'target', { value: modal });
    Object.defineProperty(innerEvent, 'currentTarget', { value: overlay });
    fx.componentInstance.onBackdrop(innerEvent);
    expect(fx.componentInstance.visible()).toBe(true);

    const outerEvent = new MouseEvent('click');
    Object.defineProperty(outerEvent, 'target', { value: overlay });
    Object.defineProperty(outerEvent, 'currentTarget', { value: overlay });
    fx.componentInstance.onBackdrop(outerEvent);
    expect(fx.componentInstance.visible()).toBe(false);
  });
});
