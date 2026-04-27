// CatalogTabComponent spec.
//
// CONST-XII anti-bluff narrative
// ------------------------------
// `TestEmptyState` reads textContent — a stub that never iterates the
//   items signal would FAIL because "no indexers in catalog" must
//   appear in the DOM.
// `TestRendersItems` reads each row's `data-testid` AND `textContent`.
//   A stub `fetch` that left the items signal empty would FAIL the
//   row-count assertion.
// `TestPaginationCallsListWithNewPage` clicks Next, asserts
//   listCatalog was called with `page: 2`. A stub nextPage that
//   ignored the page change would FAIL the call-arguments assertion.
// `TestSearchFires` asserts the request param `search` equals the
//   typed value. A stub that ignored searchTerm would FAIL because
//   the call would have no search arg.
// `TestRefreshFires` asserts refreshCatalog was called AND that
//   listCatalog was re-invoked afterwards. A stub that only updated a
//   message would FAIL the re-invocation count.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { CatalogTabComponent } from './catalog-tab.component';
import {
  IndexersService,
  CatalogItem,
  CatalogPage,
} from './indexers.service';
import { CredentialsService } from '../credentials/credentials.service';

function makeItem(id: string, overrides: Partial<CatalogItem> = {}): CatalogItem {
  return {
    id,
    display_name: id.toUpperCase(),
    type: 'public',
    required_fields: ['username', 'password'],
    ...overrides,
  };
}

interface ServiceStub {
  listCatalog: ReturnType<typeof vi.fn>;
  refreshCatalog: ReturnType<typeof vi.fn>;
  configure: ReturnType<typeof vi.fn>;
}

function makeStub(overrides: Partial<ServiceStub> = {}): ServiceStub {
  return {
    listCatalog: vi.fn(() => of({ total: 0, page: 1, page_size: 20, items: [] } as CatalogPage)),
    refreshCatalog: vi.fn(() => of({ refreshed_count: 0, errors: [] })),
    configure: vi.fn(() => of({})),
    ...overrides,
  };
}

function setup(stub: ServiceStub) {
  TestBed.configureTestingModule({
    imports: [CatalogTabComponent],
    providers: [
      { provide: IndexersService, useValue: stub },
      { provide: CredentialsService, useValue: { list: vi.fn(() => of([])) } },
    ],
  });
  return TestBed.createComponent(CatalogTabComponent);
}

describe('CatalogTabComponent', () => {
  beforeEach(() => TestBed.resetTestingModule());

  it('TestEmptyState: shows "No indexers in catalog" when items=[]', async () => {
    const stub = makeStub();
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('no indexers in catalog');
    expect(stub.listCatalog).toHaveBeenCalledTimes(1);
  });

  it('TestRendersItems: renders one row per CatalogItem with required_fields', async () => {
    const items = [
      makeItem('rutracker', { display_name: 'RuTracker', type: 'private', required_fields: ['username', 'password'] }),
      makeItem('eztv', { display_name: 'EZTV', type: 'public', required_fields: [] }),
    ];
    const page: CatalogPage = { total: 2, page: 1, page_size: 20, items };
    const stub = makeStub({ listCatalog: vi.fn(() => of(page)) });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[data-testid="cat-row-rutracker"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="cat-row-eztv"]')).not.toBeNull();
    const text = el.textContent ?? '';
    expect(text).toContain('RuTracker');
    expect(text).toContain('EZTV');
    expect(text).toContain('username');
    expect(text).toContain('password');
  });

  it('TestPaginationCallsListWithNewPage: Next button calls listCatalog({page:2})', async () => {
    const page1: CatalogPage = {
      total: 30,
      page: 1,
      page_size: 20,
      items: [makeItem('rutracker')],
    };
    const page2: CatalogPage = {
      total: 30,
      page: 2,
      page_size: 20,
      items: [makeItem('eztv')],
    };
    const stub = makeStub({
      listCatalog: vi.fn().mockReturnValueOnce(of(page1)).mockReturnValueOnce(of(page2)),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const next = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="catalog-next"]') as HTMLButtonElement | null;
    expect(next).not.toBeNull();
    next!.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(stub.listCatalog).toHaveBeenCalledTimes(2);
    const lastCall = stub.listCatalog.mock.calls[1][0];
    expect(lastCall.page).toBe(2);
    // DOM updated to second page:
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('eztv');
  });

  it('TestSearchFires: typing+submit calls listCatalog with search param', async () => {
    const stub = makeStub({
      listCatalog: vi.fn(() => of({ total: 0, page: 1, page_size: 20, items: [] } as CatalogPage)),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    const input = el.querySelector('[data-testid="catalog-search"]') as HTMLInputElement;
    input.value = 'rut';
    input.dispatchEvent(new Event('input'));
    fixture.detectChanges();
    const submit = el.querySelector('[data-testid="catalog-search-submit"]') as HTMLButtonElement;
    submit.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(stub.listCatalog).toHaveBeenCalledTimes(2);
    expect(stub.listCatalog.mock.calls[1][0].search).toBe('rut');
    expect(stub.listCatalog.mock.calls[1][0].page).toBe(1);
  });

  it('TestRefreshFires: clicking Refresh calls refreshCatalog AND re-fetches the list', async () => {
    const stub = makeStub({
      listCatalog: vi.fn(() =>
        of({ total: 0, page: 1, page_size: 20, items: [] } as CatalogPage),
      ),
      refreshCatalog: vi.fn(() => of({ refreshed_count: 7, errors: [] })),
    });
    const fixture = setup(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const refreshBtn = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="catalog-refresh"]') as HTMLButtonElement | null;
    expect(refreshBtn).not.toBeNull();
    refreshBtn!.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(stub.refreshCatalog).toHaveBeenCalledTimes(1);
    expect(stub.listCatalog).toHaveBeenCalledTimes(2);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Refreshed 7');
  });
});
