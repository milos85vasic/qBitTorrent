// ConfiguredTabComponent spec.
//
// CONST-XII anti-bluff narrative
// ------------------------------
// `TestRendersRows` reads the rendered DOM (rows[]+textContent) — a
//   stub that never iterates `list()` would FAIL because the indexer
//   IDs would be missing from the DOM.
// `TestActionRunsAndShowsBadge` clicks the Test button, asserts that
//   `service.test` was called with the row id AND that a status badge
//   with the returned text now appears in the DOM. A stub `onTest`
//   that no-ops would FAIL the spy assertion AND the DOM check.
// `TestToggleCallsService` flips the checkbox, asserts setEnabled
//   was called with the row id + new bool. A stub onToggle would FAIL
//   the spy.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { ConfiguredTabComponent } from './configured-tab.component';
import {
  IndexersService,
  IndexerMetadata,
} from './indexers.service';

function makeIndexer(id: string, overrides: Partial<IndexerMetadata> = {}): IndexerMetadata {
  return {
    id,
    display_name: id.toUpperCase(),
    type: 'public',
    configured_at_jackett: true,
    linked_credential_name: null,
    enabled_for_search: true,
    last_jackett_sync_at: null,
    last_test_status: null,
    last_test_at: null,
    ...overrides,
  };
}

interface ServiceStub {
  list: ReturnType<typeof vi.fn>;
  test: ReturnType<typeof vi.fn>;
  setEnabled: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
  configure: ReturnType<typeof vi.fn>;
}

function makeStub(overrides: Partial<ServiceStub> = {}): ServiceStub {
  return {
    list: vi.fn(() => of([])),
    test: vi.fn(),
    setEnabled: vi.fn(),
    delete: vi.fn(),
    configure: vi.fn(),
    ...overrides,
  };
}

function setup(stub: ServiceStub) {
  TestBed.configureTestingModule({
    imports: [ConfiguredTabComponent],
    providers: [{ provide: IndexersService, useValue: stub }],
  });
  return TestBed.createComponent(ConfiguredTabComponent);
}

describe('ConfiguredTabComponent', () => {
  beforeEach(() => TestBed.resetTestingModule());

  it('TestEmptyState: renders "No indexers configured" when list is empty', async () => {
    const stub = makeStub({ list: vi.fn(() => of([])) });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('no indexers configured');
    expect(stub.list).toHaveBeenCalledTimes(1);
  });

  it('TestRendersRows: renders one row per indexer with id + display name in the DOM', async () => {
    const rows = [
      makeIndexer('rutracker', { display_name: 'RuTracker (RU)' }),
      makeIndexer('iptorrents', { display_name: 'IPTorrents', linked_credential_name: 'IPTORRENTS', type: 'private' }),
    ];
    const stub = makeStub({ list: vi.fn(() => of(rows)) });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const trEls = el.querySelectorAll('tr.idx-row');
    expect(trEls.length).toBe(2);
    const text = el.textContent ?? '';
    expect(text).toContain('rutracker');
    expect(text).toContain('RuTracker (RU)');
    expect(text).toContain('iptorrents');
    expect(text).toContain('IPTorrents');
    // Linked credential rendered for the second row:
    expect(text).toContain('IPTORRENTS');
  });

  it('TestActionRunsAndShowsBadge: clicking Test calls service.test and renders the returned status', async () => {
    const row = makeIndexer('rutracker');
    const stub = makeStub({
      list: vi.fn(() => of([row])),
      test: vi.fn(() => of({ status: 'ok', details: '25 results' })),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    // Initially "untested":
    const initial = el.querySelector('[data-testid="status-rutracker"]')?.textContent ?? '';
    expect(initial.toLowerCase()).toContain('untested');

    const testBtn = el.querySelector('[data-testid="test-rutracker"]') as HTMLButtonElement | null;
    expect(testBtn).not.toBeNull();
    testBtn!.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(stub.test).toHaveBeenCalledTimes(1);
    expect(stub.test).toHaveBeenCalledWith('rutracker');

    // DOM now reflects the status returned by the service:
    const statusBadge = el.querySelector('[data-testid="status-rutracker"]');
    expect(statusBadge?.textContent?.trim()).toBe('ok');
    const detailEl = el.querySelector('[data-testid="detail-rutracker"]');
    expect(detailEl?.textContent).toContain('25 results');
  });

  it('TestDeleteConfirms: confirm-true calls service.delete with row id and refreshes list', async () => {
    const row = makeIndexer('iptorrents');
    const stub = makeStub({
      list: vi.fn().mockReturnValueOnce(of([row])).mockReturnValueOnce(of([])),
      delete: vi.fn(() => of(undefined)),
    });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const delBtn = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="delete-iptorrents"]') as HTMLButtonElement | null;
    expect(delBtn).not.toBeNull();
    delBtn!.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(stub.delete).toHaveBeenCalledTimes(1);
    expect(stub.delete).toHaveBeenCalledWith('iptorrents');
    expect(stub.list).toHaveBeenCalledTimes(2);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('no indexers configured');
    confirmSpy.mockRestore();
  });

  it('TestToggleCallsService: clicking the toggle calls setEnabled with the new bool and DOM reflects', async () => {
    const row = makeIndexer('rutracker', { enabled_for_search: true });
    const updated = { ...row, enabled_for_search: false };
    const stub = makeStub({
      list: vi.fn(() => of([row])),
      setEnabled: vi.fn(() => of(updated)),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const toggle = el.querySelector('[data-testid="toggle-rutracker"]') as HTMLInputElement;
    expect(toggle.checked).toBe(true);
    toggle.checked = false;
    toggle.dispatchEvent(new Event('change'));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(stub.setEnabled).toHaveBeenCalledTimes(1);
    expect(stub.setEnabled).toHaveBeenCalledWith('rutracker', false);
    const toggleAfter = el.querySelector('[data-testid="toggle-rutracker"]') as HTMLInputElement;
    expect(toggleAfter.checked).toBe(false);
  });

  it('TestErrorRenders: surfaces error message when service.list fails', async () => {
    const stub = makeStub({
      list: vi.fn(() => throwError(() => new Error('boom: backend down'))),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const errorEl = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="configured-error"]');
    expect(errorEl).not.toBeNull();
    expect(errorEl?.textContent).toContain('boom: backend down');
  });
});
