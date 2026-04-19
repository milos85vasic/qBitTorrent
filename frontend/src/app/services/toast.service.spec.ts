import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { ToastService } from './toast.service';

describe('ToastService', () => {
  let svc: ToastService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    svc = TestBed.inject(ToastService);
  });

  it('starts with an empty queue', () => {
    expect(svc.toasts()).toEqual([]);
  });

  it('show() appends a toast with the supplied type', () => {
    svc.show('hello', 'info', 1000);
    const queue = svc.toasts();
    expect(queue).toHaveLength(1);
    expect(queue[0].message).toBe('hello');
    expect(queue[0].type).toBe('info');
    expect(queue[0].duration).toBe(1000);
    expect(queue[0].id).toBeTruthy();
  });

  it('success() sets type=success', () => {
    svc.success('saved');
    expect(svc.toasts()[0].type).toBe('success');
  });

  it('error() sets type=error with 6000ms default duration', () => {
    svc.error('boom');
    expect(svc.toasts()[0].type).toBe('error');
    expect(svc.toasts()[0].duration).toBe(6000);
  });

  it('warning() sets type=warning with 5000ms default duration', () => {
    svc.warning('careful');
    expect(svc.toasts()[0].type).toBe('warning');
    expect(svc.toasts()[0].duration).toBe(5000);
  });

  it('info() sets type=info', () => {
    svc.info('fyi');
    expect(svc.toasts()[0].type).toBe('info');
  });

  it('dismiss() removes a single toast by id', () => {
    svc.show('a', 'info', 0);
    svc.show('b', 'info', 0);
    const firstId = svc.toasts()[0].id;
    svc.dismiss(firstId);
    expect(svc.toasts()).toHaveLength(1);
    expect(svc.toasts()[0].message).toBe('b');
  });

  it('dismissAll() clears the queue', () => {
    svc.show('a', 'info', 0);
    svc.show('b', 'info', 0);
    svc.dismissAll();
    expect(svc.toasts()).toEqual([]);
  });

  it('auto-dismisses after the supplied duration', fakeAsync(() => {
    svc.show('gone', 'info', 500);
    expect(svc.toasts()).toHaveLength(1);
    tick(499);
    expect(svc.toasts()).toHaveLength(1);
    tick(1);
    expect(svc.toasts()).toHaveLength(0);
  }));

  it('duration=0 keeps the toast indefinitely', fakeAsync(() => {
    svc.show('sticky', 'info', 0);
    tick(60000);
    expect(svc.toasts()).toHaveLength(1);
  }));

  it('multiple toasts get unique ids', () => {
    svc.show('a', 'info', 0);
    svc.show('b', 'info', 0);
    const ids = svc.toasts().map(t => t.id);
    expect(new Set(ids).size).toBe(2);
  });

  it('id format includes a timestamp prefix', () => {
    const spy = vi.spyOn(Date, 'now').mockReturnValue(1234567890);
    try {
      svc.show('ts', 'info', 0);
      expect(svc.toasts()[0].id.startsWith('1234567890-')).toBe(true);
    } finally {
      spy.mockRestore();
    }
  });
});
