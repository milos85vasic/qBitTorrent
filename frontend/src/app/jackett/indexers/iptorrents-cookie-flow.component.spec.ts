// IptorrentsCookieFlowComponent spec.
//
// CONST-XII anti-bluff narrative
// ------------------------------
// `TestPanelRenders` reads the on-screen instruction text. A stub
//   template that omitted the cookie example would FAIL the substring
//   assertion on "uid=" + "pass=".
// `TestEmptyDoesNotPost` clicks Save with an empty textarea and
//   asserts NEITHER credService.upsert NOR idxService.configure was
//   called. A stub that POSTed regardless would FAIL.
// `TestSavePostsBoth` asserts both POSTs fire AND that they fire in
//   order (credentials first, then indexers). A stub that only fired
//   one would FAIL.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { Subject, of } from 'rxjs';
import { IptorrentsCookieFlowComponent } from './iptorrents-cookie-flow.component';
import { CredentialsService } from '../credentials/credentials.service';
import { IndexersService } from './indexers.service';

function setup(opts?: {
  upsert?: ReturnType<typeof vi.fn>;
  configure?: ReturnType<typeof vi.fn>;
}) {
  const credService = {
    list: vi.fn(() => of([])),
    upsert: opts?.upsert ?? vi.fn(() => of({})),
    delete: vi.fn(() => of(undefined)),
  };
  const idxService = {
    configure: opts?.configure ?? vi.fn(() => of({})),
    list: vi.fn(() => of([])),
    delete: vi.fn(() => of(undefined)),
    test: vi.fn(() => of({ status: 'ok' })),
    setEnabled: vi.fn(() => of({})),
    listCatalog: vi.fn(() => of({ total: 0, page: 1, page_size: 20, items: [] })),
    refreshCatalog: vi.fn(() => of({ refreshed_count: 0, errors: [] })),
    listRuns: vi.fn(() => of([])),
    getRun: vi.fn(() => of({})),
    triggerRun: vi.fn(() => of({})),
  };
  TestBed.configureTestingModule({
    imports: [IptorrentsCookieFlowComponent],
    providers: [
      { provide: CredentialsService, useValue: credService },
      { provide: IndexersService, useValue: idxService },
    ],
  });
  const fixture = TestBed.createComponent(IptorrentsCookieFlowComponent);
  fixture.componentInstance.indexerId = 'iptorrents';
  fixture.componentInstance.requiredFields = ['cookieheader'];
  return { fixture, credService, idxService };
}

describe('IptorrentsCookieFlowComponent', () => {
  beforeEach(() => TestBed.resetTestingModule());

  it('TestPanelRenders: shows the cookie instruction panel with the example string', async () => {
    const { fixture } = setup();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('iptorrents');
    expect(text).toContain('uid=');
    expect(text).toContain('pass=');
    // Required field shown:
    expect(text).toContain('cookieheader');
  });

  it('TestEmptyDoesNotPost: Save with an empty textarea is disabled and fires no requests', async () => {
    const { fixture, credService, idxService } = setup();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const saveBtn = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="cookie-save"]') as HTMLButtonElement | null;
    expect(saveBtn).not.toBeNull();
    expect(saveBtn!.disabled).toBe(true);
    // Clicking a disabled button should not fire either way; assert no calls:
    saveBtn!.click();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(credService.upsert).not.toHaveBeenCalled();
    expect(idxService.configure).not.toHaveBeenCalled();
  });

  it('TestSavePostsBoth: typing a cookie + clicking Save POSTs credentials THEN indexers in order', async () => {
    const upsertSubj = new Subject<unknown>();
    const configureSubj = new Subject<unknown>();
    const upsert = vi.fn(() => upsertSubj.asObservable());
    const configure = vi.fn(() => configureSubj.asObservable());
    const { fixture, credService, idxService } = setup({ upsert, configure });

    let savedFired = false;
    fixture.componentInstance.saved.subscribe(() => (savedFired = true));
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const ta = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="cookie-input"]') as HTMLTextAreaElement;
    ta.value = 'uid=12345; pass=abcdef';
    ta.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const saveBtn = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="cookie-save"]') as HTMLButtonElement;
    expect(saveBtn.disabled).toBe(false);
    saveBtn.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    // credService.upsert must be called first; idxService.configure
    // must NOT have fired yet (we haven't completed the upsert obs).
    expect(credService.upsert).toHaveBeenCalledTimes(1);
    expect(credService.upsert).toHaveBeenCalledWith({
      name: 'IPTORRENTS',
      cookies: 'uid=12345; pass=abcdef',
    });
    expect(idxService.configure).not.toHaveBeenCalled();

    // Now resolve upsert; configure should fire next.
    upsertSubj.next({});
    upsertSubj.complete();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(idxService.configure).toHaveBeenCalledTimes(1);
    expect(idxService.configure).toHaveBeenCalledWith('iptorrents', {
      credential_name: 'IPTORRENTS',
    });

    // Now resolve configure; saved should fire.
    configureSubj.next({});
    configureSubj.complete();
    fixture.detectChanges();
    await fixture.whenStable();
    expect(savedFired).toBe(true);
  });

  it('TestSavedEmits: when both POSTs succeed, (saved) emits exactly once', async () => {
    const { fixture } = setup();
    let savedCount = 0;
    fixture.componentInstance.saved.subscribe(() => savedCount++);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const ta = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="cookie-input"]') as HTMLTextAreaElement;
    ta.value = 'uid=1; pass=2';
    ta.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    const saveBtn = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="cookie-save"]') as HTMLButtonElement;
    saveBtn.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(savedCount).toBe(1);
  });
});
