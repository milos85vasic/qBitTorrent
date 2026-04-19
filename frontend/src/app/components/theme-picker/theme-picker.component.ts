import { Component, ElementRef, HostListener, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ThemeService } from '../../services/theme.service';
import { Palette } from '../../models/palette.model';

@Component({
  selector: 'app-theme-picker',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './theme-picker.component.html',
  styleUrls: ['./theme-picker.component.scss'],
})
export class ThemePickerComponent {
  private readonly theme = inject(ThemeService);
  private readonly host = inject(ElementRef<HTMLElement>);

  readonly availablePalettes = this.theme.availablePalettes;
  readonly palette = this.theme.palette;
  readonly mode = this.theme.mode;

  readonly open = signal(false);

  toggleOpen(): void {
    this.open.update((v) => !v);
  }

  toggleMode(): void {
    this.theme.toggleMode();
  }

  pick(id: string): void {
    this.theme.setPalette(id);
    this.open.set(false);
  }

  trackByPalette(_index: number, p: Palette): string {
    return p.id;
  }

  /**
   * Close the palette menu when clicking anywhere outside this
   * component. We identify "inside" via `ElementRef.nativeElement`
   * plus a DOM `contains()` check — robust against re-parenting or
   * multiple instances.
   */
  @HostListener('document:click', ['$event'])
  closeIfOpen(event: Event): void {
    if (!this.open()) return;
    const target = event.target as Node | null;
    const root = this.host?.nativeElement as HTMLElement | undefined;
    if (!root || !target) {
      this.open.set(false);
      return;
    }
    if (root === target || root.contains(target)) {
      return;
    }
    this.open.set(false);
  }
}
