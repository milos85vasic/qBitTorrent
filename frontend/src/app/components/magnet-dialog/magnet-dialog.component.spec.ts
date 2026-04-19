import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { MagnetDialogComponent } from './magnet-dialog.component';

describe('MagnetDialogComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MagnetDialogComponent],
    }).compileComponents();
  });

  function host(fx: { nativeElement: HTMLElement }): HTMLElement {
    return fx.nativeElement;
  }

  it('renders nothing when hidden', () => {
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    expect(host(fx).querySelector('.modal-overlay')).toBeNull();
  });

  it('open() sets magnet signal + makes it visible', () => {
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open('magnet:?xt=urn:btih:abc');
    fx.detectChanges();
    expect(fx.componentInstance.visible()).toBe(true);
    expect(fx.componentInstance.magnet()).toBe('magnet:?xt=urn:btih:abc');
    const ta = host(fx).querySelector('textarea') as HTMLTextAreaElement;
    expect(ta.value).toBe('magnet:?xt=urn:btih:abc');
  });

  it('open() records the optional addToQbit callback', () => {
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    const cb = vi.fn();
    fx.componentInstance.open('magnet:x', cb);
    fx.detectChanges();
    fx.componentInstance.onAdd();
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it('onAdd() is a no-op when no callback was registered', () => {
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open('magnet:x');
    expect(() => fx.componentInstance.onAdd()).not.toThrow();
  });

  it('close() hides the dialog', () => {
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open('magnet:x');
    fx.componentInstance.close();
    fx.detectChanges();
    expect(fx.componentInstance.visible()).toBe(false);
    expect(host(fx).querySelector('.modal-overlay')).toBeNull();
  });

  it('copy() writes magnet to clipboard and closes', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open('magnet:abc');
    await fx.componentInstance.copy();
    // Let the microtask .then() run.
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith('magnet:abc');
    expect(fx.componentInstance.visible()).toBe(false);
  });

  it('copy() falls back to execCommand when clipboard API rejects', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'));
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    // jsdom does not ship document.execCommand; define the property
    // before spying. The shim only needs to exist + be spy-able; the
    // component's fallback path calls it and we assert the invocation.
    if (!('execCommand' in document)) {
      Object.defineProperty(document, 'execCommand', {
        configurable: true,
        writable: true,
        value: () => true,
      });
    }
    const execSpy = vi.spyOn(document, 'execCommand').mockReturnValue(true);
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open('magnet:xyz');
    await fx.componentInstance.copy();
    // Drain microtask + fallback execution.
    await new Promise(r => setTimeout(r, 0));
    expect(execSpy).toHaveBeenCalledWith('copy');
    expect(fx.componentInstance.visible()).toBe(false);
    execSpy.mockRestore();
  });

  it('closeAfterOpen() schedules a close via setTimeout', async () => {
    vi.useFakeTimers();
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open('magnet:x');
    fx.componentInstance.closeAfterOpen();
    expect(fx.componentInstance.visible()).toBe(true);
    vi.advanceTimersByTime(500);
    expect(fx.componentInstance.visible()).toBe(false);
    vi.useRealTimers();
  });

  it('onBackdrop() closes on overlay click, ignores inner clicks', () => {
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open('magnet:x');
    fx.detectChanges();
    const overlay = host(fx).querySelector('.modal-overlay') as HTMLDivElement;
    const modal = overlay.querySelector('.modal') as HTMLElement;

    const innerEvent = new MouseEvent('click');
    Object.defineProperty(innerEvent, 'target', { value: modal });
    Object.defineProperty(innerEvent, 'currentTarget', { value: overlay });
    fx.componentInstance.onBackdrop(innerEvent);
    expect(fx.componentInstance.visible()).toBe(true);

    const backdropEvent = new MouseEvent('click');
    Object.defineProperty(backdropEvent, 'target', { value: overlay });
    Object.defineProperty(backdropEvent, 'currentTarget', { value: overlay });
    fx.componentInstance.onBackdrop(backdropEvent);
    expect(fx.componentInstance.visible()).toBe(false);
  });

  it('renders Close / Copy / Open / Add action buttons when visible', () => {
    const fx = TestBed.createComponent(MagnetDialogComponent);
    fx.detectChanges();
    fx.componentInstance.open('magnet:x');
    fx.detectChanges();
    const labels = Array.from(host(fx).querySelectorAll('.modal-actions > *')).map(b => (b.textContent || '').trim());
    expect(labels).toEqual(['Close', 'Copy', 'Open', 'Add']);
  });
});
