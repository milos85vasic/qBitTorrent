import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToastService } from '../../services/toast.service';

@Component({
  selector: 'app-toast-container',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="toast-container">
      @for (toast of toastService.toasts(); track toast.id) {
        <div class="toast toast-{{ toast.type }}">
          <span class="toast-message">{{ toast.message }}</span>
          <button class="toast-dismiss" (click)="toastService.dismiss(toast.id)" aria-label="Dismiss">&times;</button>
        </div>
      }
    </div>
  `,
  styles: [`
    .toast-container {
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 9999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-width: 400px;
    }
    .toast {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 14px 18px;
      border-radius: 8px;
      color: #fff;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      animation: slideIn 0.3s ease;
      backdrop-filter: blur(4px);
    }
    .toast-success { background: rgba(40, 167, 69, 0.95); border: 1px solid #28a745; }
    .toast-error { background: rgba(220, 53, 69, 0.95); border: 1px solid #dc3545; }
    .toast-warning { background: rgba(255, 193, 7, 0.95); color: #333; border: 1px solid #ffc107; }
    .toast-info { background: rgba(23, 162, 184, 0.95); border: 1px solid #17a2b8; }
    .toast-message { flex: 1; margin-right: 12px; word-break: break-word; }
    .toast-dismiss {
      background: none;
      border: none;
      color: inherit;
      font-size: 20px;
      cursor: pointer;
      line-height: 1;
      padding: 0 0 2px 0;
      opacity: 0.8;
      transition: opacity 0.2s;
    }
    .toast-dismiss:hover { opacity: 1; }
    @keyframes slideIn {
      from { transform: translateX(120%); opacity: 0; }
      to { transform: translateX(0); opacity: 1; }
    }
  `]
})
export class ToastContainerComponent {
  toastService = inject(ToastService);
}
