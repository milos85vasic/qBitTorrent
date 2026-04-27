// Smoke spec for the legacy CLI-scaffold `App` standalone component.
// The actually-bootstrapped root is `AppComponent` (see main.ts +
// app.component.ts); its coverage lives in app.component.spec.ts.
//
// Phase 5 swapped the marketing-page placeholder for a real nav +
// router-outlet shell, so we assert on the nav structure instead of
// the old "Hello, frontend" greeting.
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('renders the primary nav with Dashboard + Jackett links', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    const dash = compiled.querySelector('[data-testid="nav-dashboard"]');
    const jackett = compiled.querySelector('[data-testid="nav-jackett"]');
    expect(dash?.getAttribute('href')).toBe('/');
    expect(jackett?.getAttribute('href')).toBe('/jackett');
  });
});
