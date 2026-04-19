import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { DialogService } from './dialog.service';

describe('DialogService', () => {
  let svc: DialogService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    svc = TestBed.inject(DialogService);
  });

  it('starts hidden with empty title/message', () => {
    const state = svc.confirmDialog();
    expect(state.visible).toBe(false);
    expect(state.data.title).toBe('');
    expect(state.data.message).toBe('');
  });

  it('confirm() sets visible + stores data + returns a Promise', async () => {
    const pending = svc.confirm({ title: 'T', message: 'M', confirmText: 'OK' });
    expect(svc.confirmDialog().visible).toBe(true);
    expect(svc.confirmDialog().data.title).toBe('T');
    expect(svc.confirmDialog().data.message).toBe('M');
    expect(svc.confirmDialog().data.confirmText).toBe('OK');
    svc.resolveConfirm(true);
    await expect(pending).resolves.toBe(true);
  });

  it('resolveConfirm(false) resolves with false and hides dialog', async () => {
    const pending = svc.confirm({ title: 'T', message: 'M' });
    svc.resolveConfirm(false);
    await expect(pending).resolves.toBe(false);
    expect(svc.confirmDialog().visible).toBe(false);
  });

  it('resolveConfirm preserves last data snapshot (for post-close animations)', async () => {
    const pending = svc.confirm({ title: 'Hello', message: 'World' });
    svc.resolveConfirm(true);
    await pending;
    expect(svc.confirmDialog().visible).toBe(false);
    expect(svc.confirmDialog().data.title).toBe('Hello');
    expect(svc.confirmDialog().data.message).toBe('World');
  });

  it('resolveConfirm is safe when no resolver is registered', () => {
    // Manually hide state so resolve is undefined.
    svc.confirmDialog.set({ visible: true, data: { title: 'x', message: 'y' } });
    expect(() => svc.resolveConfirm(true)).not.toThrow();
    expect(svc.confirmDialog().visible).toBe(false);
  });

  it('confirmClass can indicate a danger-styled action', () => {
    svc.confirm({ title: 'Delete?', message: 'gone', confirmClass: 'danger' });
    expect(svc.confirmDialog().data.confirmClass).toBe('danger');
    svc.resolveConfirm(false);
  });

  it('supports sequential confirmations', async () => {
    const p1 = svc.confirm({ title: 'A', message: '1' });
    svc.resolveConfirm(true);
    await expect(p1).resolves.toBe(true);
    const p2 = svc.confirm({ title: 'B', message: '2' });
    svc.resolveConfirm(false);
    await expect(p2).resolves.toBe(false);
  });
});
