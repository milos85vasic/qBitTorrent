import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { DialogService } from '../../services/dialog.service';

describe('ConfirmDialogComponent', () => {
  let dialog: DialogService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConfirmDialogComponent],
    }).compileComponents();
    dialog = TestBed.inject(DialogService);
  });

  function host(fx: { nativeElement: HTMLElement }): HTMLElement {
    return fx.nativeElement;
  }

  it('renders nothing when confirmDialog.visible is false', () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    expect(host(fx).querySelector('.modal-overlay')).toBeNull();
  });

  it('renders modal with supplied title and message when visible', () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    void dialog.confirm({ title: 'Proceed?', message: 'Are you sure?' });
    fx.detectChanges();
    expect(host(fx).querySelector('h3')?.textContent).toContain('Proceed?');
    expect(host(fx).querySelector('.modal-message')?.textContent).toContain('Are you sure?');
  });

  it('uses supplied confirmText / cancelText labels', () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    void dialog.confirm({ title: 't', message: 'm', confirmText: 'Go', cancelText: 'Stop' });
    fx.detectChanges();
    const texts = Array.from(host(fx).querySelectorAll('button')).map(b => (b.textContent || '').trim());
    expect(texts).toContain('Go');
    expect(texts).toContain('Stop');
  });

  it('falls back to "Confirm" / "Cancel" when labels omitted', () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    void dialog.confirm({ title: 't', message: 'm' });
    fx.detectChanges();
    const texts = Array.from(host(fx).querySelectorAll('button')).map(b => (b.textContent || '').trim());
    expect(texts).toContain('Confirm');
    expect(texts).toContain('Cancel');
  });

  it('cancel button resolves the confirm promise with false', async () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    const pending = dialog.confirm({ title: 't', message: 'm' });
    fx.detectChanges();
    const cancelBtn = host(fx).querySelector('.cancel-btn') as HTMLButtonElement;
    cancelBtn.click();
    await expect(pending).resolves.toBe(false);
  });

  it('submit button resolves the confirm promise with true', async () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    const pending = dialog.confirm({ title: 't', message: 'm' });
    fx.detectChanges();
    const submitBtn = host(fx).querySelector('.submit-btn') as HTMLButtonElement;
    submitBtn.click();
    await expect(pending).resolves.toBe(true);
  });

  it('applies btn-danger class when confirmClass==="danger"', () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    void dialog.confirm({ title: 't', message: 'm', confirmClass: 'danger' });
    fx.detectChanges();
    const submitBtn = host(fx).querySelector('.submit-btn') as HTMLButtonElement;
    expect(submitBtn.classList.contains('btn-danger')).toBe(true);
  });

  it('clicking the backdrop resolves with false', async () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    const pending = dialog.confirm({ title: 't', message: 'm' });
    fx.detectChanges();
    const overlay = host(fx).querySelector('.modal-overlay') as HTMLDivElement;
    // Simulate click where event.target === event.currentTarget.
    const event = new MouseEvent('click', { bubbles: true });
    Object.defineProperty(event, 'target', { value: overlay });
    Object.defineProperty(event, 'currentTarget', { value: overlay });
    fx.componentInstance.onBackdrop(event);
    await expect(pending).resolves.toBe(false);
  });

  it('onBackdrop ignores clicks on child elements (event.target !== currentTarget)', () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    void dialog.confirm({ title: 't', message: 'm' });
    fx.detectChanges();
    const overlay = host(fx).querySelector('.modal-overlay') as HTMLDivElement;
    const modal = overlay.querySelector('.modal') as HTMLElement;
    const event = new MouseEvent('click', { bubbles: true });
    Object.defineProperty(event, 'target', { value: modal });
    Object.defineProperty(event, 'currentTarget', { value: overlay });
    // Should NOT close the dialog.
    fx.componentInstance.onBackdrop(event);
    fx.detectChanges();
    expect(dialog.confirmDialog().visible).toBe(true);
    // Clean up pending promise.
    dialog.resolveConfirm(false);
  });

  it('applies "show" class when visible', () => {
    const fx = TestBed.createComponent(ConfirmDialogComponent);
    fx.detectChanges();
    void dialog.confirm({ title: 't', message: 'm' });
    fx.detectChanges();
    const overlay = host(fx).querySelector('.modal-overlay') as HTMLDivElement;
    expect(overlay.classList.contains('show')).toBe(true);
    dialog.resolveConfirm(false);
  });
});
