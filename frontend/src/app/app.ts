// Legacy CLI-scaffold root component. The actually-bootstrapped root is
// `AppComponent` in app.component.ts (see main.ts). This file is kept
// because some tooling still references it. Both shells render the
// same nav + router-outlet shape.
import { Component, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly title = signal('frontend');
}
