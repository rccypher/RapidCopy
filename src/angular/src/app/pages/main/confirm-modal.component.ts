import {Component, Input} from "@angular/core";
import {NgbActiveModal} from "@ng-bootstrap/ng-bootstrap";

/**
 * A small reusable confirmation dialog rendered in-app via NgbModal, replacing the
 * native browser confirm() (which is unstyleable, jarring, and can double-fire).
 * Open with NgbModal.open(ConfirmModalComponent), set the inputs on the instance,
 * and await modalRef.result (resolves true on confirm, rejects on cancel/dismiss).
 */
@Component({
    selector: "app-confirm-modal",
    template: `
        <div class="modal-header">
            <h5 class="modal-title">{{ title }}</h5>
            <button type="button" class="btn-close" aria-label="Close" (click)="modal.dismiss()"></button>
        </div>
        <div class="modal-body">
            <p style="white-space: pre-line; margin: 0;">{{ message }}</p>
        </div>
        <div class="modal-footer">
            <button type="button" class="btn btn-secondary" (click)="modal.dismiss()">{{ cancelText }}</button>
            <button type="button"
                    [class]="danger ? 'btn btn-danger' : 'btn btn-primary'"
                    (click)="modal.close(true)">{{ confirmText }}</button>
        </div>
    `
})
export class ConfirmModalComponent {
    @Input() title = "Confirm";
    @Input() message = "";
    @Input() confirmText = "Confirm";
    @Input() cancelText = "Cancel";
    @Input() danger = false;

    constructor(public modal: NgbActiveModal) {}
}
