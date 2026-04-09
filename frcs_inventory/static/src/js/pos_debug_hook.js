/** @odoo-module **/

// Lightweight debug hook to confirm POS product data reaches the frontend
// Works with and without debug=assets by polling until the POS store is ready.
(function () {
    try {
        console.log("✅ POS debug hook active");
    } catch (_) {}

    let attempts = 0;
    const maxAttempts = 30; // ~30s
    const timer = setInterval(() => {
        attempts += 1;
        try {
            const pos = (window.odoo && (window.odoo.__DEBUG__?.services?.pos || window.odoo.services?.pos)) || null;
            const models = pos && pos.models;
            const productModel = models && models["product.product"];
            if (productModel && productModel.getAll) {
                const all = productModel.getAll();
                console.log("✅ POS loaded:", all.length, "products");
                if (all.length) {
                    const p = all[0];
                    console.log("Example:", p.display_name, p.x_total_price, p.x_price_incl_tax);
                }
                clearInterval(timer);
            } else if (attempts >= maxAttempts) {
                console.warn("⚠️ POS store not yet available (timeout)");
                clearInterval(timer);
            }
        } catch (e) {
            if (attempts >= maxAttempts) {
                console.warn("⚠️ POS debug hook error:", e);
                clearInterval(timer);
            }
        }
    }, 1000);
})();

