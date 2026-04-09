odoo.define('frcs_inventory.pos_payment_patch', function (require) {
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');
    const { useState } = owl;

    const FrcsPaymentScreen = (PaymentScreen) =>
        class extends PaymentScreen {
            setup() {
                super.setup();
                this.state = useState({ selectedMethod: null });

                // Build a name-insensitive mapping of payment methods
                const normalize = (s) => (s || '').toString().toLowerCase().replace(/[^a-z0-9]/g, '');
                this.paymentMethodsByKey = {};
                (this.env.pos && this.env.pos.payment_methods || []).forEach((pm) => {
                    this.paymentMethodsByKey[normalize(pm.name)] = pm;
                });
            }

            // Helper: resolve a common button label to a payment method
            _findPaymentMethodByCommonName(name) {
                const key = (s) => (s || '').toString().toLowerCase().replace(/[^a-z0-9]/g, '');
                const candidates = [name];
                if (name === 'M-Paisa' || name === 'mPaisa') {
                    candidates.push('mPaisa', 'M-Paisa', 'MPaisa', 'M Paisa');
                } else if (name === 'Card') {
                    candidates.push('CARD');
                } else if (name === 'Cash') {
                    candidates.push('CASH');
                }
                for (const label of candidates) {
                    const pm = this.paymentMethodsByKey[key(label)];
                    if (pm) return pm;
                }
                return null;
            }

            addPaymentByName(name) {
                const pm = this._findPaymentMethodByCommonName(name);
                if (!pm) {
                    this.showPopup('ErrorPopup', {
                        title: this.env._t('Payment Method Not Found'),
                        body: this.env._t(`No payment method named "${name}" is available in this POS.`),
                    });
                    return;
                }
                this.addNewPaymentLine(pm);
            }

            addNewPaymentLine(paymentMethod) {
                // Prevent duplicates of the same method
                const lines = this.currentOrder.get_paymentlines ? this.currentOrder.get_paymentlines() : (this.currentOrder.paymentlines || []);
                const exists = lines.find((l) => (l.payment_method || l.payment_method_id)?.id === paymentMethod.id);
                if (exists) {
                    this.showPopup('ErrorPopup', {
                        title: this.env._t('Duplicate Payment Not Allowed'),
                        body: this.env._t(`You already selected ${paymentMethod.name}.`),
                    });
                    return;
                }

                this.state.selectedMethod = paymentMethod.name;
                super.addNewPaymentLine(paymentMethod);

                // Auto-focus on the amount input of the new line
                setTimeout(() => {
                    const root = this.el || document;
                    const input = root.querySelector('.paymentline.selected input');
                    if (input) input.focus();
                }, 150);
            }

            getButtonColor(name) {
                const active = (this.state.selectedMethod || '').toLowerCase();
                const is = (n) => active === n.toLowerCase();
                if (is('Cash')) return 'background:#28a745;color:white;';
                if (is('Card')) return 'background:#007bff;color:white;';
                if (is('M-Paisa') || is('mPaisa')) return 'background:#ff9800;color:white;';
                return '';
            }
        };

    Registries.Component.extend(PaymentScreen, FrcsPaymentScreen);
    return FrcsPaymentScreen;
});

