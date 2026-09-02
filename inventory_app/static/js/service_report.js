document.addEventListener("DOMContentLoaded", function () {

    const tbody = document.getElementById("itemRows");
    const addButton = document.getElementById("addItemRow");

    // --------------------------------------------------
    // Safety
    // --------------------------------------------------

    if (!tbody || !addButton) {
        return;
    }


    // --------------------------------------------------
    // Product Lookup
    // --------------------------------------------------

    const categories = [
        ...new Set(
            PRODUCTS
                .map(product => product.category)
                .filter(Boolean)
        )
    ];


    // --------------------------------------------------
    // Escape HTML
    // --------------------------------------------------

    function escapeHtml(value) {

        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");

    }


    // --------------------------------------------------
    // Money
    // --------------------------------------------------

    function money(value) {

        value = parseFloat(value);

        if (isNaN(value)) {
            value = 0;
        }

        return value.toFixed(2);
    }


    // --------------------------------------------------
    // Create New Row
    // --------------------------------------------------

    function newRow() {

        const tr = document.createElement("tr");

        tr.innerHTML = `

            <!-- 1. Category -->
            <td>

                <select
                    class="form-select category-select"
                    name="category[]"
                >

                    <option value="">
                        Select
                    </option>

                    ${categories.map(category => `
                        <option value="${escapeHtml(category)}">
                            ${escapeHtml(category)}
                        </option>
                    `).join("")}

                </select>

            </td>


            <!-- 2. Product -->
            <td>

                <select
                    class="form-select product-select"
                    name="product_id[]"
                >

                    <option value="">
                        Select Product
                    </option>

                </select>

            </td>


            <!-- 3. Available -->
            <td>

                <input
                    type="text"
                    class="form-control stock-display"
                    value="0"
                    readonly
                >

            </td>


            <!-- 4. Quantity -->
            <td>

                <input
                    type="number"
                    min="1"
                    value="1"
                    name="quantity[]"
                    class="form-control quantity"
                >

            </td>


            <!-- 5. Rate -->
            <td>

                <input
                    type="number"
                    step="0.01"
                    min="0"
                    value="0"
                    name="rate[]"
                    class="form-control rate"
                >

            </td>


            <!-- 6. Tax % -->
            <td>

                <input
                    type="number"
                    step="0.01"
                    min="0"
                    value="13"
                    name="tax_percent[]"
                    class="form-control tax-percent"
                >

            </td>


            <!-- 7. Tax -->
            <td>

                <input
                    type="text"
                    name="tax[]"
                    class="form-control tax"
                    value="0.00"
                    readonly
                >

            </td>


            <!-- 8. Line Total -->
            <td>

                <input
                    type="text"
                    class="form-control line-total"
                    value="0.00"
                    readonly
                >

            </td>


            <!-- 9. Remarks -->
            <td>

                <input
                    type="text"
                    name="item_remarks[]"
                    class="form-control"
                >

            </td>


            <!-- 10. Remove -->
            <td class="text-center">

                <button
                    type="button"
                    class="btn btn-danger btn-sm removeRow"
                    title="Remove"
                >

                    <i class="fas fa-times"></i>

                </button>

            </td>

        `;

        tbody.appendChild(tr);

    }


    // --------------------------------------------------
    // Category Changed
    // --------------------------------------------------

    tbody.addEventListener("change", function (event) {

        if (!event.target.classList.contains("category-select")) {
            return;
        }

        const row = event.target.closest("tr");

        const category = event.target.value;

        const productSelect =
            row.querySelector(".product-select");

        productSelect.innerHTML = `
            <option value="">
                Select Product
            </option>
        `;

        if (!category) {
            clearProductFields(row);
            return;
        }

        PRODUCTS
            .filter(product => product.category === category)
            .forEach(product => {

                const option =
                    document.createElement("option");

                option.value = product.id;

                option.textContent =
                    product.item_name;

                productSelect.appendChild(option);

            });

    });


    // --------------------------------------------------
    // Product Changed
    // --------------------------------------------------

    tbody.addEventListener("change", function (event) {

        if (!event.target.classList.contains("product-select")) {
            return;
        }

        const row =
            event.target.closest("tr");

        const product =
            PRODUCTS.find(
                product =>
                    String(product.id) ===
                    String(event.target.value)
            );

        if (!product) {
            clearProductFields(row);
            return;
        }

        const stockDisplay =
            row.querySelector(".stock-display");

        const rateInput =
            row.querySelector(".rate");

        stockDisplay.value =
            product.available_stock ?? 0;

        /*
         * Product selling price becomes
         * the default estimated rate.
         *
         * User can overwrite it.
         */

        rateInput.value =
            Number(product.selling_price || 0).toFixed(2);

        calculateRow(row);

    });


    // --------------------------------------------------
    // Quantity / Rate / Tax % Changed
    // --------------------------------------------------

    tbody.addEventListener("input", function (event) {

        if (
            event.target.classList.contains("quantity") ||
            event.target.classList.contains("rate") ||
            event.target.classList.contains("tax-percent")
        ) {

            calculateRow(
                event.target.closest("tr")
            );

        }

    });


    // --------------------------------------------------
    // Remove Row
    // --------------------------------------------------

    tbody.addEventListener("click", function (event) {

        const button =
            event.target.closest(".removeRow");

        if (!button) {
            return;
        }

        const row =
            button.closest("tr");

        if (row) {
            row.remove();
        }

        calculateTotals();

    });


    // --------------------------------------------------
    // Add Row
    // --------------------------------------------------

    addButton.addEventListener("click", function () {

        newRow();

        calculateTotals();

    });


    // --------------------------------------------------
    // Calculate Individual Row
    // --------------------------------------------------

    function calculateRow(row) {

        if (!row) {
            return;
        }

        const quantityInput =
            row.querySelector(".quantity");

        const rateInput =
            row.querySelector(".rate");

        const taxPercentInput =
            row.querySelector(".tax-percent");

        const taxInput =
            row.querySelector(".tax");

        const totalInput =
            row.querySelector(".line-total");


        const quantity =
            parseFloat(
                quantityInput?.value || 0
            ) || 0;


        const rate =
            parseFloat(
                rateInput?.value || 0
            ) || 0;


        const taxPercent =
            parseFloat(
                taxPercentInput?.value || 0
            ) || 0;


        // Same calculation as sales invoice

        const baseAmount =
            quantity * rate;


        const taxAmount =
            baseAmount *
            taxPercent /
            100;


        const lineTotal =
            baseAmount +
            taxAmount;


        // Tax amount

        if (taxInput) {

            taxInput.value =
                money(taxAmount);

        }


        // Line total

        if (totalInput) {

            totalInput.value =
                money(lineTotal);

        }


        calculateTotals();

    }


    // --------------------------------------------------
    // Calculate Overall Estimate
    // --------------------------------------------------

    function calculateTotals() {

        let partsTotal = 0;


        document
            .querySelectorAll(
                "#itemRows .line-total"
            )
            .forEach(input => {

                partsTotal +=
                    parseFloat(
                        input.value || 0
                    ) || 0;

            });


        const laborInput =
            document.getElementById("laborCharge");

        const otherInput =
            document.getElementById("otherCharge");


        const labor =
            parseFloat(
                laborInput?.value || 0
            ) || 0;


        const other =
            parseFloat(
                otherInput?.value || 0
            ) || 0;


        const estimatedTotal =
            partsTotal +
            labor +
            other;


        const partsTotalInput =
            document.getElementById("partsTotal");

        const laborDisplay =
            document.getElementById("labourDisplay");

        const otherDisplay =
            document.getElementById("otherDisplay");

        const estimatedTotalInput =
            document.getElementById("estimatedTotal");


        if (partsTotalInput) {

            partsTotalInput.value =
                money(partsTotal);

        }


        if (laborDisplay) {

            laborDisplay.value =
                money(labor);

        }


        if (otherDisplay) {

            otherDisplay.value =
                money(other);

        }


        if (estimatedTotalInput) {

            estimatedTotalInput.value =
                money(estimatedTotal);

        }

    }


    // --------------------------------------------------
    // Labour / Other Charges Changed
    // --------------------------------------------------

    document
        .querySelectorAll(".estimate-field")
        .forEach(field => {

            field.addEventListener(
                "input",
                calculateTotals
            );

        });


    // --------------------------------------------------
    // Clear Product Fields
    // --------------------------------------------------

    function clearProductFields(row) {

        const productSelect =
            row.querySelector(".product-select");

        const stockDisplay =
            row.querySelector(".stock-display");

        const rateInput =
            row.querySelector(".rate");

        const taxInput =
            row.querySelector(".tax");

        const lineTotalInput =
            row.querySelector(".line-total");


        if (productSelect) {
            productSelect.value = "";
        }


        if (stockDisplay) {
            stockDisplay.value = "0";
        }


        if (rateInput) {
            rateInput.value = "0";
        }


        if (taxInput) {
            taxInput.value = "0.00";
        }


        if (lineTotalInput) {
            lineTotalInput.value = "0.00";
        }

    }


    // --------------------------------------------------
    // Initialize Existing Rows
    // --------------------------------------------------

    document
        .querySelectorAll("#itemRows tr")
        .forEach(row => {

            const productSelect =
                row.querySelector(".product-select");


            const productId =
                productSelect?.value;


            const product =
                PRODUCTS.find(
                    product =>
                        String(product.id) ===
                        String(productId)
                );


            if (product) {

                const stockDisplay =
                    row.querySelector(
                        ".stock-display"
                    );

                if (stockDisplay) {

                    stockDisplay.value =
                        product.available_stock ?? 0;

                }

            }


            /*
             * Recalculate the existing row
             * using quantity, rate and tax %.
             */

            calculateRow(row);

        });


    // --------------------------------------------------
    // Create First Empty Row
    // --------------------------------------------------

    if (tbody.children.length === 0) {

        newRow();

    }


    // --------------------------------------------------
    // Final Initial Calculation
    // --------------------------------------------------

    calculateTotals();

});