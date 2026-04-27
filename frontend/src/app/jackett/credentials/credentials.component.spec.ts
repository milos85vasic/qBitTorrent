// CredentialsComponent spec.
//
// CONST-XII anti-bluff narrative
// ------------------------------
// `TestRendersTable` reads the rendered <td> text — a stub component
// that never iterates the signal would FAIL because the credential
// names would be missing from the DOM. `TestDeleteConfirms` asserts
// `service.delete` was actually CALLED and that a refresh GET fires —
// a stub that no-ops on click would FAIL the spy assertion.

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { CredentialsComponent } from './credentials.component';
import { CredentialsService, CredentialMetadata } from './credentials.service';

function makeCred(name: string, overrides: Partial<CredentialMetadata> = {}): CredentialMetadata {
  return {
    name,
    kind: 'userpass',
    has_username: true,
    has_password: true,
    has_cookies: false,
    created_at: '2026-04-27T00:00:00Z',
    updated_at: '2026-04-27T00:00:00Z',
    last_used_at: null,
    ...overrides,
  };
}

interface ServiceStub {
  list: ReturnType<typeof vi.fn>;
  upsert: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
}

function setupWith(stub: ServiceStub) {
  TestBed.configureTestingModule({
    imports: [CredentialsComponent],
    providers: [{ provide: CredentialsService, useValue: stub }],
  });
  return TestBed.createComponent(CredentialsComponent);
}

describe('CredentialsComponent', () => {
  beforeEach(() => {
    TestBed.resetTestingModule();
  });

  it('TestRendersTable: renders one row per credential with name + has_username badge text', async () => {
    const stub: ServiceStub = {
      list: vi.fn(() => of([
        makeCred('RUTRACKER', { has_username: true,  has_password: true,  has_cookies: false }),
        makeCred('NNMCLUB',   { kind: 'cookie', has_username: false, has_password: false, has_cookies: true, last_used_at: '2026-04-27T01:00:00Z' }),
      ])),
      upsert: vi.fn(),
      delete: vi.fn(),
    };
    const fixture = setupWith(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    // Names rendered:
    expect(text).toContain('RUTRACKER');
    expect(text).toContain('NNMCLUB');
    // has_username badges rendered (yes / no markers):
    const rows = (fixture.nativeElement as HTMLElement).querySelectorAll('tr.cred-row');
    expect(rows.length).toBe(2);
    // First row: has_username = true → badge "yes"; second row: false → "no".
    const firstUsernameBadge = rows[0].querySelector('[data-testid="badge-username"]');
    const secondUsernameBadge = rows[1].querySelector('[data-testid="badge-username"]');
    expect(firstUsernameBadge?.textContent?.toLowerCase()).toContain('yes');
    expect(secondUsernameBadge?.textContent?.toLowerCase()).toContain('no');
    // service.list() must have been invoked exactly once on init:
    expect(stub.list).toHaveBeenCalledTimes(1);
  });

  it('TestEmptyState: renders the "no credentials yet" message when the list is empty', async () => {
    const stub: ServiceStub = {
      list: vi.fn(() => of([])),
      upsert: vi.fn(),
      delete: vi.fn(),
    };
    const fixture = setupWith(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('no credentials yet');
  });

  it('TestDeleteConfirms: clicking delete triggers window.confirm, calls service.delete with the row name, and refreshes the list', async () => {
    const cred = makeCred('RUTRACKER');
    const stub: ServiceStub = {
      list: vi.fn()
        .mockReturnValueOnce(of([cred]))      // initial load
        .mockReturnValueOnce(of([])),         // refresh after delete
      upsert: vi.fn(),
      delete: vi.fn(() => of(undefined)),
    };
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    const fixture = setupWith(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const deleteBtn = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="delete-RUTRACKER"]') as HTMLButtonElement | null;
    expect(deleteBtn).not.toBeNull();
    deleteBtn!.click();

    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(stub.delete).toHaveBeenCalledTimes(1);
    expect(stub.delete).toHaveBeenCalledWith('RUTRACKER');
    // Refresh fired a second list():
    expect(stub.list).toHaveBeenCalledTimes(2);
    // Empty state now visible:
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text.toLowerCase()).toContain('no credentials yet');

    confirmSpy.mockRestore();
  });

  it('TestDeleteConfirms: cancelling window.confirm does NOT call service.delete', async () => {
    const cred = makeCred('RUTRACKER');
    const stub: ServiceStub = {
      list: vi.fn(() => of([cred])),
      upsert: vi.fn(),
      delete: vi.fn(() => of(undefined)),
    };
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    const fixture = setupWith(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const deleteBtn = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="delete-RUTRACKER"]') as HTMLButtonElement | null;
    deleteBtn!.click();

    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(stub.delete).not.toHaveBeenCalled();

    confirmSpy.mockRestore();
  });

  it('TestErrorRenders: surfaces an error message in the DOM when service.list() fails', async () => {
    const stub: ServiceStub = {
      list: vi.fn(() => throwError(() => new Error('boom: backend offline'))),
      upsert: vi.fn(),
      delete: vi.fn(),
    };
    const fixture = setupWith(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const errorEl = (fixture.nativeElement as HTMLElement).querySelector('[data-testid="error-message"]');
    expect(errorEl).not.toBeNull();
    expect(errorEl?.textContent).toContain('boom: backend offline');
  });

  it('opens the edit dialog when "Add credential" is clicked', async () => {
    const stub: ServiceStub = {
      list: vi.fn(() => of([])),
      upsert: vi.fn(),
      delete: vi.fn(),
    };
    const fixture = setupWith(stub);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    // Dialog hidden initially:
    expect((fixture.nativeElement as HTMLElement).querySelector('[data-testid="edit-dialog"]')).toBeNull();

    const addBtn = (fixture.nativeElement as HTMLElement)
      .querySelector('[data-testid="add-credential"]') as HTMLButtonElement | null;
    expect(addBtn).not.toBeNull();
    addBtn!.click();
    fixture.detectChanges();

    expect((fixture.nativeElement as HTMLElement).querySelector('[data-testid="edit-dialog"]')).not.toBeNull();
  });
});
