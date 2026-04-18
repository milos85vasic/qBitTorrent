import { Injectable, signal } from '@angular/core';

export interface ConfirmDialogData {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  confirmClass?: string;
}

@Injectable({ providedIn: 'root' })
export class DialogService {
  confirmDialog = signal<{ visible: boolean; data: ConfirmDialogData; resolve?: (value: boolean) => void }>({
    visible: false,
    data: { title: '', message: '' }
  });

  confirm(data: ConfirmDialogData): Promise<boolean> {
    return new Promise(resolve => {
      this.confirmDialog.set({ visible: true, data, resolve });
    });
  }

  resolveConfirm(value: boolean): void {
    const current = this.confirmDialog();
    if (current.resolve) {
      current.resolve(value);
    }
    this.confirmDialog.set({ visible: false, data: current.data });
  }
}
