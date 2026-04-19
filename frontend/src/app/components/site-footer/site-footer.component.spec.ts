import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { SiteFooterComponent } from './site-footer.component';

/**
 * Site-footer tests — re-port of the original TDD suite from commit
 * 368d7fe (tests/integration/test_manual_issues.py::TestFooter) that
 * validated the legacy server-rendered footer. Re-expressed here as
 * Angular TestBed specs so the footer is guarded by the frontend
 * suite too.
 */
describe('SiteFooterComponent', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SiteFooterComponent],
    }).compileComponents();
  });

  it('creates', () => {
    const fx = TestBed.createComponent(SiteFooterComponent);
    expect(fx.componentInstance).toBeTruthy();
  });

  it('renders "Made with" text', () => {
    const fx = TestBed.createComponent(SiteFooterComponent);
    fx.detectChanges();
    const text = (fx.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('Made with');
  });

  it('renders a heart symbol (❤, HTML entity, or unicode heart)', () => {
    const fx = TestBed.createComponent(SiteFooterComponent);
    fx.detectChanges();
    const html = (fx.nativeElement as HTMLElement).innerHTML;
    // After rendering, the ❤ entity is resolved to the U+2764 character.
    const heartIndicators = ['❤', '\u2764', '&#10084;', '&hearts;', '♥'];
    expect(heartIndicators.some(h => html.includes(h))).toBe(true);
  });

  it('renders a clickable Vasic Digital link to https://www.vasic.digital', () => {
    const fx = TestBed.createComponent(SiteFooterComponent);
    fx.detectChanges();
    const anchor = (fx.nativeElement as HTMLElement).querySelector('a');
    expect(anchor).toBeTruthy();
    expect(anchor!.getAttribute('href')).toBe('https://www.vasic.digital');
    expect(anchor!.textContent).toContain('Vasic Digital');
  });

  it('link opens in a new tab with rel="noopener noreferrer"', () => {
    const fx = TestBed.createComponent(SiteFooterComponent);
    fx.detectChanges();
    const anchor = (fx.nativeElement as HTMLElement).querySelector('a')!;
    expect(anchor.getAttribute('target')).toBe('_blank');
    const rel = anchor.getAttribute('rel') ?? '';
    expect(rel).toContain('noopener');
    expect(rel).toContain('noreferrer');
  });

  it('footer element has role="contentinfo" for a11y landmarks', () => {
    const fx = TestBed.createComponent(SiteFooterComponent);
    fx.detectChanges();
    const footer = (fx.nativeElement as HTMLElement).querySelector('footer');
    expect(footer?.getAttribute('role')).toBe('contentinfo');
  });

  it('heart span carries an accessible label', () => {
    const fx = TestBed.createComponent(SiteFooterComponent);
    fx.detectChanges();
    const heart = (fx.nativeElement as HTMLElement).querySelector('.heart')!;
    expect(heart.getAttribute('aria-label')).toBe('love');
  });
});
