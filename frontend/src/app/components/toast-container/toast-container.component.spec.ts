import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { ToastContainerComponent } from './toast-container.component';
import { ToastService } from '../../services/toast.service';

describe('ToastContainerComponent', () => {
  let toast: ToastService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ToastContainerComponent],
    }).compileComponents();
    toast = TestBed.inject(ToastService);
  });

  it('renders without error', () => {
    const fx = TestBed.createComponent(ToastContainerComponent);
    fx.detectChanges();
    expect(fx.componentInstance).toBeTruthy();
  });

  it('exposes toastService on the instance (for template access)', () => {
    const fx = TestBed.createComponent(ToastContainerComponent);
    fx.detectChanges();
    expect(fx.componentInstance.toastService).toBe(toast);
  });

  it('renders one .toast element per toast in the queue', () => {
    const fx = TestBed.createComponent(ToastContainerComponent);
    fx.detectChanges();
    toast.show('first', 'info', 0);
    toast.show('second', 'error', 0);
    fx.detectChanges();
    const toasts = (fx.nativeElement as HTMLElement).querySelectorAll('.toast');
    expect(toasts).toHaveLength(2);
  });

  it('applies toast-{type} class to each toast', () => {
    const fx = TestBed.createComponent(ToastContainerComponent);
    fx.detectChanges();
    toast.show('ok', 'success', 0);
    fx.detectChanges();
    const el = (fx.nativeElement as HTMLElement).querySelector('.toast');
    expect(el?.classList.contains('toast-success')).toBe(true);
  });

  it('renders the message text', () => {
    const fx = TestBed.createComponent(ToastContainerComponent);
    fx.detectChanges();
    toast.show('hello world', 'info', 0);
    fx.detectChanges();
    const msg = (fx.nativeElement as HTMLElement).querySelector('.toast-message');
    expect(msg?.textContent).toContain('hello world');
  });

  it('renders dismiss button with aria-label="Dismiss"', () => {
    const fx = TestBed.createComponent(ToastContainerComponent);
    fx.detectChanges();
    toast.show('x', 'info', 0);
    fx.detectChanges();
    const btn = (fx.nativeElement as HTMLElement).querySelector('.toast-dismiss') as HTMLButtonElement | null;
    expect(btn).toBeTruthy();
    expect(btn?.getAttribute('aria-label')).toBe('Dismiss');
  });

  it('clicking dismiss removes the toast via the service', () => {
    const fx = TestBed.createComponent(ToastContainerComponent);
    fx.detectChanges();
    toast.show('x', 'info', 0);
    fx.detectChanges();
    const btn = (fx.nativeElement as HTMLElement).querySelector('.toast-dismiss') as HTMLButtonElement;
    btn.click();
    fx.detectChanges();
    expect(toast.toasts()).toHaveLength(0);
    expect((fx.nativeElement as HTMLElement).querySelectorAll('.toast')).toHaveLength(0);
  });

  it('shows nothing when the queue is empty', () => {
    const fx = TestBed.createComponent(ToastContainerComponent);
    fx.detectChanges();
    expect((fx.nativeElement as HTMLElement).querySelectorAll('.toast')).toHaveLength(0);
  });
});
