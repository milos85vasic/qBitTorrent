import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-qbit-login-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    @if (visible()) {
      <div class="modal-overlay show" (click)="onBackdrop($event)">
        <div class="modal">
          <h3>Login to qBittorrent</h3>
          <p class="hint">Enter your qBittorrent WebUI credentials.</p>
          <input type="text" [(ngModel)]="username" placeholder="Username" />
          <input type="password" [(ngModel)]="password" placeholder="Password" />
          <label class="save-label">
            <input type="checkbox" [(ngModel)]="saveCreds" /> Remember me
          </label>
          <div class="error" *ngIf="error()">{{ error() }}</div>
          <div class="modal-actions">
            <button class="cancel-btn" (click)="close()">Cancel</button>
            <button class="submit-btn" [disabled]="loading()" (click)="login()">
              {{ loading() ? 'Logging in...' : 'Login' }}
            </button>
          </div>
        </div>
      </div>
    }
  `,
  styles: [`
    .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 10001; justify-content: center; align-items: center; }
    .modal-overlay.show { display: flex; }
    .modal { background: #1e2a4a; padding: 28px; border-radius: 12px; border: 1px solid #2a3f6a; max-width: 400px; width: 90%; color: #e0e0e0; }
    .modal h3 { color: #e94560; margin-bottom: 6px; font-size: 20px; }
    .hint { color: #888; font-size: 13px; margin-bottom: 16px; }
    input[type="text"], input[type="password"] { width: 100%; padding: 12px; margin-bottom: 12px; border: 1px solid #2a3f6a; border-radius: 8px; background: #0f1a30; color: #e0e0e0; font-size: 15px; }
    .save-label { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #888; margin-bottom: 14px; }
    .save-label input { width: auto; }
    .error { color: #dc3545; font-size: 13px; margin-bottom: 12px; }
    .modal-actions { display: flex; gap: 10px; }
    .modal-actions button { flex: 1; padding: 10px; border-radius: 8px; border: none; cursor: pointer; font-size: 15px; }
    .cancel-btn { background: #333; color: #ccc; }
    .submit-btn { background: #e94560; color: #fff; }
    .submit-btn:disabled { background: #555; cursor: not-allowed; }
  `]
})
export class QbitLoginDialogComponent {
  private api = inject(ApiService);
  private toast = inject(ToastService);

  visible = signal(false);
  username = signal('admin');
  password = signal('');
  saveCreds = signal(false);
  loading = signal(false);
  error = signal('');
  onSuccess?: () => void;

  open(onSuccess?: () => void): void {
    this.visible.set(true);
    this.error.set('');
    this.onSuccess = onSuccess;
  }

  close(): void {
    this.visible.set(false);
  }

  login(): void {
    if (!this.username() || !this.password()) {
      this.error.set('Please enter username and password');
      return;
    }
    this.loading.set(true);
    this.api.qbitLogin({
      username: this.username(),
      password: this.password(),
      save: this.saveCreds()
    }).subscribe({
      next: (res) => {
        this.loading.set(false);
        if (res.status === 'authenticated') {
          this.toast.success('Logged in to qBittorrent');
          this.close();
          this.onSuccess?.();
        } else {
          this.error.set(res.error || 'Login failed');
        }
      },
      error: (err) => {
        this.loading.set(false);
        this.error.set(err.error?.error || 'Connection error');
      }
    });
  }

  onBackdrop(event: MouseEvent): void {
    if (event.target === event.currentTarget) this.close();
  }
}
