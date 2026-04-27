// HistoryTabComponent spec.
//
// CONST-XII anti-bluff narrative
// ------------------------------
// `TestRendersRunRows` asserts run IDs + counts appear in DOM. A stub
//   that didn't iterate the runs signal would FAIL.
// `TestExpandLoadsDetail` clicks a row, asserts service.getRun was
//   called AND that the rendered detail block contains the
//   AutoconfigResult JSON. A stub toggleExpand that only flipped the
//   expandedId flag without calling getRun would FAIL.
// `TestTriggerFiresPost` clicks "Run autoconfig now", asserts
//   triggerRun was called AND that listRuns was re-called afterwards.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { HistoryTabComponent } from './history-tab.component';
import {
  IndexersService,
  RunSummary,
  RunDetail,
} from './indexers.service';

function makeRun(id: number, overrides: Partial<RunSummary> = {}): RunSummary {
  return {
    id,
    ran_at: '2026-04-27T20:00:00Z',
    discovered_count: 0,
    configured_now_count: 0,
    error_count: 0,
    ...overrides,
  };
}

interface ServiceStub {
  listRuns: ReturnType<typeof vi.fn>;
  getRun: ReturnType<typeof vi.fn>;
  triggerRun: ReturnType<typeof vi.fn>;
}

function makeStub(overrides: Partial<ServiceStub> = {}): ServiceStub {
  return {
    listRuns: vi.fn(() => of([])),
    getRun: vi.fn(() => of({} as RunDetail)),
    triggerRun: vi.fn(() => of({} as RunDetail)),
    ...overrides,
  };
}

function setup(stub: ServiceStub) {
  TestBed.configureTestingModule({
    imports: [HistoryTabComponent],
    providers: [{ provide: IndexersService, useValue: stub }],
  });
  return TestBed.createComponent(HistoryTabComponent);
}

describe('HistoryTabComponent', () => {
  beforeEach(() => TestBed.resetTestingModule());

  it('TestEmptyState: shows "no autoconfig runs" message when listRuns=[]', async () => {
    const stub = makeStub();
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('no autoconfig runs');
    expect(stub.listRuns).toHaveBeenCalledTimes(1);
    expect(stub.listRuns).toHaveBeenCalledWith(50);
  });

  it('TestRendersRunRows: lists each run with its summary counts', async () => {
    const runs = [
      makeRun(1, { discovered_count: 3, configured_now_count: 2, error_count: 0 }),
      makeRun(2, { discovered_count: 4, configured_now_count: 0, error_count: 1, ran_at: '2026-04-27T22:00:00Z' }),
    ];
    const stub = makeStub({ listRuns: vi.fn(() => of(runs)) });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="run-row-1"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="run-row-2"]')).not.toBeNull();
    const text = el.textContent ?? '';
    expect(text).toContain('#1');
    expect(text).toContain('#2');
    // Counts visible:
    expect(text).toContain('3');
    expect(text).toContain('1');
  });

  it('TestExpandLoadsDetail: clicking a row calls service.getRun and renders the JSON detail', async () => {
    const detail: RunDetail = {
      ran_at: '2026-04-27T20:00:00Z',
      discovered: ['RUTRACKER'],
      matched_indexers: { RUTRACKER: 'rutracker' },
      configured_now: ['RUTRACKER'],
      already_present: [],
      skipped_no_match: [],
      skipped_ambiguous: [],
      served_by_native_plugin: ['NNMCLUB'],
      errors: [],
    };
    const runs = [makeRun(7)];
    const stub = makeStub({
      listRuns: vi.fn(() => of(runs)),
      getRun: vi.fn(() => of(detail)),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const row = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="run-row-7"]') as HTMLElement;
    expect(row).not.toBeNull();
    row.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(stub.getRun).toHaveBeenCalledTimes(1);
    expect(stub.getRun).toHaveBeenCalledWith(7);

    const detailEl = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="run-detail-7"]');
    expect(detailEl).not.toBeNull();
    const detailText = detailEl?.textContent ?? '';
    expect(detailText).toContain('RUTRACKER');
    expect(detailText).toContain('NNMCLUB');
    expect(detailText).toContain('served_by_native_plugin');
  });

  it('TestTriggerFiresPost: clicking "Run autoconfig now" calls triggerRun and refreshes listRuns', async () => {
    const stub = makeStub({
      listRuns: vi.fn().mockReturnValue(of([])),
      triggerRun: vi.fn(() => of({} as RunDetail)),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const trigger = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="trigger-run"]') as HTMLButtonElement;
    expect(trigger).not.toBeNull();
    trigger.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(stub.triggerRun).toHaveBeenCalledTimes(1);
    // listRuns called twice: once on init, once after trigger.
    expect(stub.listRuns).toHaveBeenCalledTimes(2);
  });

  it('TestErrorRenders: surfaces error message when listRuns fails', async () => {
    const stub = makeStub({
      listRuns: vi.fn(() => throwError(() => new Error('boom: history API'))),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const errEl = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="history-error"]');
    expect(errEl).not.toBeNull();
    expect(errEl?.textContent).toContain('boom: history API');
  });
});
