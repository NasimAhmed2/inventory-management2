document.addEventListener("DOMContentLoaded", function () {

    // ==========================================================
    // Elements
    // ==========================================================

    const saleType = document.getElementById("sale-type");

    const customerSection =
        document.getElementById("customer-section");

    const customerSelect =
        document.getElementById("customer");

    const customerMobile =
        document.getElementById("customer-mobile");

    const repairSection =
        document.getElementById("repair-section");

    const serviceReportSelect =
        document.getElementById("service-report");

    const repairInfo =
        document.getElementById("repair-info");

    const itemsSection =
        document.getElementById("items-section");

    const itemsBody =
        document.getElementById("sale-items-body");

    const repairInvoiceSection =
        document.getElementById("repair-invoice-section");

    const repairItemsBody =
        document.getElementById("repair-items-body");

    const summarySection =
        document.getElementById("summary-section");

    const submitSection =
        document.getElementById("submit-section");

    const addItemButton =
        document.getElementById("add-item");

    const discountInput =
        document.getElementById("discount-amount");


    // ==========================================================
    // Product Data
    // ==========================================================

    let products = [];

    const productsElement =
        document.getElementById("products-data");

    if (productsElement) {

        try {
            products = JSON.parse(
                productsElement.textContent
            );
        } catch (error) {

            console.error(
                "Unable to read product data:",
                error
            );

            products = [];
        }
    }


    // ==========================================================
    // Customer Data
    // ==========================================================

    let customers = [];

    const customersElement =
        document.getElementById("customers-data");

    if (customersElement) {

        try {
            customers = JSON.parse(
                customersElement.textContent
            );
        } catch (error) {

            console.error(
                "Unable to read customer data:",
                error
            );

            customers = [];
        }
    }


    // ==========================================================
    // Utility
    // ==========================================================

    function money(value) {

        value = parseFloat(value);

        if (isNaN(value)) {
            value = 0;
        }

        return value.toFixed(2);
    }


    function escapeHtml(value) {

        if (value === null || value === undefined) {
            return "";
        }

        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }


    // ==========================================================
    // Customer Selection
    // ==========================================================

    customerSelect.addEventListener(
        "change",
        function () {

            const customerId =
                this.value;

            const customer =
                customers.find(
                    c =>
                        String(c.id) ===
                        String(customerId)
                );

            if (customer) {

                customerMobile.value =
                    customer.mobile || "";

            } else {

                customerMobile.value = "";

            }
        }
    );


    // ==========================================================
    // Sale Type
    // ==========================================================

    saleType.addEventListener(
        "change",
        function () {

            resetSaleForm();

            const type = this.value;

            if (!type) {
                return;
            }


            // ----------------------------------------------
            // Direct Sale
            // ----------------------------------------------

            if (type === "DIRECT") {

                customerSection.style.display =
                    "block";

                itemsSection.style.display =
                    "block";

                summarySection.style.display =
                    "block";

                submitSection.style.setProperty(
                    "display",
                    "flex",
                    "important"
                );

                addItem();

                return;
            }


            // ----------------------------------------------
            // Repair
            // ----------------------------------------------

            if (type === "REPAIR") {

                repairSection.style.display =
                    "block";

                repairInvoiceSection.style.display =
                    "block";

                summarySection.style.display =
                    "block";

                submitSection.style.setProperty(
                    "display",
                    "flex",
                    "important"
                );

                return;
            }


            // ----------------------------------------------
            // Sale Return
            // ----------------------------------------------

            if (type === "RETURN") {

                customerSection.style.display =
                    "block";

                itemsSection.style.display =
                    "block";

                summarySection.style.display =
                    "block";

                submitSection.style.setProperty(
                    "display",
                    "flex",
                    "important"
                );

                addItem();

                return;
            }

        }
    );


    // ==========================================================
    // Reset Sale Form
    // ==========================================================

    function resetSaleForm() {

        customerSection.style.display =
            "none";

        repairSection.style.display =
            "none";

        itemsSection.style.display =
            "none";

        repairInvoiceSection.style.display =
            "none";

        summarySection.style.display =
            "none";

        submitSection.style.setProperty(
            "display",
            "none",
            "important"
        );


        itemsBody.innerHTML = "";

        repairItemsBody.innerHTML = "";


        repairInfo.style.display =
            "none";


        document.getElementById(
            "repair-ticket"
        ).textContent = "-";

        document.getElementById(
            "repair-customer"
        ).textContent = "-";

        document.getElementById(
            "repair-technician"
        ).textContent = "-";


        document.getElementById(
            "repair-estimated-total"
        ).textContent = "0.00";


        document.getElementById(
            "repair-parts-total"
        ).textContent = "0.00";

        document.getElementById(
            "repair-labor"
        ).textContent = "0.00";

        document.getElementById(
            "repair-other"
        ).textContent = "0.00";

        document.getElementById(
            "repair-total"
        ).textContent = "0.00";


        document.getElementById(
            "summary-total"
        ).textContent = "0.00";

        document.getElementById(
            "summary-tax"
        ).textContent = "0.00";

        document.getElementById(
            "summary-grand-total"
        ).textContent = "0.00";


        discountInput.value = "0";


        customerSelect.value = "";

        customerMobile.value = "";

        serviceReportSelect.value = "";
    }


    // ==========================================================
    // Add Product Row
    // ==========================================================

    addItemButton.addEventListener(
        "click",
        function () {

            addItem();

        }
    );


    function addItem() {

        const row = document.createElement("tr");

        row.classList.add("sale-item-row");

        row.innerHTML = `

            <!-- Product Search -->
            <td>
                <div class="position-relative">

                    <input
                        type="text"
                        class="form-control form-control-sm product-search"
                        placeholder="Search code or product name..."
                        autocomplete="off"
                        required
                    >

                    <div
                        class="product-suggestions list-group position-absolute w-100 shadow-sm"
                        style="
                            display:none;
                            z-index:1050;
                            max-height:240px;
                            overflow-y:auto;
                        "
                    ></div>

                </div>

                <!-- Hidden product ID -->
                <input
                    type="hidden"
                    name="product_id[]"
                    class="item-product-id"
                >

                <!-- Hidden category -->
                <input
                    type="hidden"
                    name="item_category[]"
                    class="item-category"
                >
            </td>


            <!-- Item Code -->
            <td>

                <input
                    type="text"
                    name="item_code[]"
                    class="form-control form-control-sm item-code"
                    readonly
                >

            </td>


            <!-- Item Name -->
            <td>

                <input
                    type="text"
                    name="item_name[]"
                    class="form-control form-control-sm item-name"
                    readonly
                >

            </td>


            <!-- Quantity -->
            <td>

                <input
                    type="number"
                    name="quantity[]"
                    class="form-control form-control-sm item-quantity"
                    value="1"
                    min="1"
                    step="1"
                    required
                >

            </td>


            <!-- Rate -->
            <td>

                <input
                    type="number"
                    name="rate[]"
                    class="form-control form-control-sm item-rate"
                    value="0"
                    min="0"
                    step="0.01"
                    required
                >

            </td>


            <!-- Tax % -->
            <td>

                <input
                    type="number"
                    name="tax_percentage[]"
                    class="form-control form-control-sm item-tax-percentage"
                    value="13"
                    min="0"
                    step="0.01"
                >

            </td>


            <!-- Tax Amount -->
            <td>

                <input
                    type="text"
                    name="tax_amount[]"
                    class="form-control form-control-sm item-tax-amount"
                    value="0.00"
                    readonly
                >

            </td>


            <!-- Line Amount -->
            <td>

                <input
                    type="text"
                    name="line_total[]"
                    class="form-control form-control-sm item-line-total"
                    value="0.00"
                    readonly
                >

            </td>


            <!-- Remove -->
            <td class="text-center">

                <button
                    type="button"
                    class="btn btn-sm btn-outline-danger remove-item"
                    title="Remove Item"
                >
                    <i class="fas fa-trash"></i>
                </button>

            </td>

        `;


        itemsBody.appendChild(row);


        attachRowEvents(row);


        calculateInvoice();

    }


    // ==========================================================
    // Row Events
    // ==========================================================

    function attachRowEvents(row) {
        console.log("ATTACH ROW EVENTS FIRED");

        const searchInput =
            row.querySelector(".product-search");

        const suggestions =
            row.querySelector(".product-suggestions");

        const quantityInput =
            row.querySelector(".item-quantity");

        const rateInput =
            row.querySelector(".item-rate");

        const taxInput =
            row.querySelector(".item-tax-percentage");

        const removeButton =
            row.querySelector(".remove-item");


        // ======================================================
        // Product Search
        // ======================================================

        searchInput.addEventListener("input", function () {
            console.log("SEARCH FIRED:", this.value);
            const searchText =
                this.value.trim().toLowerCase();

            clearProductFields(row);

            if (!searchText) {

                suggestions.innerHTML = "";
                suggestions.style.display = "none";

                return;
            }


            // --------------------------------------------------
            // Find matching products
            // --------------------------------------------------

            const matches = products
                .map(product => {

                    const code =
                        String(product.item_code || "").toLowerCase();

                    const name =
                        String(product.item_name || "").toLowerCase();

                    let score = 0;

                    // Exact code/name
                    if (code === searchText) {
                        score = 100;
                    }

                    else if (name === searchText) {
                        score = 95;
                    }

                    // Code starts with search
                    else if (code.startsWith(searchText)) {
                        score = 90;
                    }

                    // Name starts with search
                    else if (name.startsWith(searchText)) {
                        score = 85;
                    }

                    // Code contains search
                    else if (code.includes(searchText)) {
                        score = 70;
                    }

                    // Name contains search
                    else if (name.includes(searchText)) {
                        score = 60;
                    }

                    return {
                        product: product,
                        score: score
                    };

                })

                .filter(result => result.score > 0)

                .sort((a, b) => {

                    if (b.score !== a.score) {
                        return b.score - a.score;
                    }

                    return String(a.product.item_code)
                        .localeCompare(
                            String(b.product.item_code)
                        );

                })

                .slice(0, 5);

                console.log("SEARCH TEXT:", searchText);
                console.log("MATCHES:", matches);


            // --------------------------------------------------
            // No results
            // --------------------------------------------------

            if (matches.length === 0) {
                console.log("SUGGESTIONS matches:", matches);
                suggestions.innerHTML = `
                    <div class="list-group-item text-muted small">
                        No matching product found
                    </div>
                `;
                console.log("SUGGESTIONS ELEMENT:", suggestions);
                suggestions.style.display = "block";

                return;
            }


            // --------------------------------------------------
            // Display top 5 suggestions
            // --------------------------------------------------

            suggestions.innerHTML = "";


            matches.forEach(result => {

                const product = result.product;


                const item =
                    document.createElement("button");

                item.type = "button";

                item.className =
                    "list-group-item list-group-item-action";


                item.innerHTML = `

                    <div class="fw-semibold">
                        ${escapeHtml(product.item_code)}
                    </div>

                    <div class="small text-muted">
                        ${escapeHtml(product.item_name)}
                    </div>

                `;


                item.addEventListener("click", function () {

                    selectProduct(row, product);

                    suggestions.innerHTML = "";

                    suggestions.style.display = "none";

                });


                suggestions.appendChild(item);

            });
            console.log("SUGGESTIONS ELEMENT:", suggestions);

            suggestions.style.display = "block";

        });


        // ======================================================
        // Quantity
        // ======================================================

        quantityInput.addEventListener("input", function () {

            calculateRow(row);

        });


        // ======================================================
        // Rate
        // ======================================================

        rateInput.addEventListener("input", function () {

            calculateRow(row);

        });


        // ======================================================
        // Tax %
        // ======================================================

        taxInput.addEventListener("input", function () {

            calculateRow(row);

        });


        // ======================================================
        // Remove
        // ======================================================

        removeButton.addEventListener("click", function () {

            row.remove();

            calculateInvoice();

        });


        // ======================================================
        // Hide suggestions when clicking elsewhere
        // ======================================================

        document.addEventListener("click", function (event) {

            if (!row.contains(event.target)) {

                suggestions.style.display = "none";

            }

        });

    }

    

    // ==========================================================
    // Select Product
    // ==========================================================

    function selectProduct(row, product) {

        // Product ID
        row.querySelector(".item-product-id").value =
            product.id;


        // Category
        row.querySelector(".item-category").value =
            product.category || "";


        // Item Code
        row.querySelector(".item-code").value =
            product.item_code;


        // Item Name
        row.querySelector(".item-name").value =
            product.item_name;


        // Selling Price
        row.querySelector(".item-rate").value =
            money(product.selling_price);


        // Search box
        row.querySelector(".product-search").value =
            `${product.item_code} (${product.item_name})`;


        // Recalculate
        calculateRow(row);

    }


    // ==========================================================
    // Clear Product Fields
    // ==========================================================

    function clearProductFields(row) {

        row.querySelector(".item-product-id").value = "";

        row.querySelector(".item-category").value = "";

        row.querySelector(".item-code").value = "";

        row.querySelector(".item-name").value = "";

        row.querySelector(".item-rate").value = "0";

    }

    // ==========================================================
    // Escape HTML
    // ==========================================================

    function escapeHtml(value) {

        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");

    }


    // ==========================================================
    // Calculate Individual Row
    // ==========================================================

    function calculateRow(row) {

        const quantity =
            parseFloat(
                row.querySelector(
                    ".item-quantity"
                ).value
            ) || 0;


        const rate =
            parseFloat(
                row.querySelector(
                    ".item-rate"
                ).value
            ) || 0;


        const taxPercentage =
            parseFloat(
                row.querySelector(
                    ".item-tax-percentage"
                ).value
            ) || 0;


        const baseAmount =
            quantity * rate;


        const taxAmount =
            baseAmount *
            taxPercentage /
            100;


        const lineTotal =
            baseAmount +
            taxAmount;


        row.querySelector(
            ".item-tax-amount"
        ).value =
            money(taxAmount);


        row.querySelector(
            ".item-line-total"
        ).value =
            money(lineTotal);


        calculateInvoice();

    }


    // ==========================================================
    // Calculate Direct Sale / Return Invoice
    // ==========================================================

    function calculateInvoice() {

        let totalAmount = 0;

        let totalTax = 0;


        document
            .querySelectorAll(
                ".sale-item-row"
            )
            .forEach(
                row => {

                    const quantity =
                        parseFloat(
                            row.querySelector(
                                ".item-quantity"
                            ).value
                        ) || 0;


                    const rate =
                        parseFloat(
                            row.querySelector(
                                ".item-rate"
                            ).value
                        ) || 0;


                    const taxPercentage =
                        parseFloat(
                            row.querySelector(
                                ".item-tax-percentage"
                            ).value
                        ) || 0;


                    const baseAmount =
                        quantity * rate;


                    const taxAmount =
                        baseAmount *
                        taxPercentage /
                        100;


                    const lineTotal =
                        baseAmount +
                        taxAmount;


                    totalAmount +=
                        baseAmount;


                    totalTax +=
                        taxAmount;


                    row.querySelector(
                        ".item-tax-amount"
                    ).value =
                        money(taxAmount);


                    row.querySelector(
                        ".item-line-total"
                    ).value =
                        money(lineTotal);

                }
            );


        updateSummary(
            totalAmount,
            totalTax
        );

    }


    // ==========================================================
    // Update Summary
    // ==========================================================

    function updateSummary(
        totalAmount,
        taxAmount
    ) {

        const discount =
            parseFloat(
                discountInput.value
            ) || 0;


        const beforeDiscount =
            totalAmount +
            taxAmount;


        let grandTotal =
            beforeDiscount -
            discount;


        if (grandTotal < 0) {
            grandTotal = 0;
        }


        document.getElementById(
            "summary-total"
        ).textContent =
            money(totalAmount);


        document.getElementById(
            "summary-tax"
        ).textContent =
            money(taxAmount);


        document.getElementById(
            "summary-grand-total"
        ).textContent =
            money(grandTotal);

    }


    // ==========================================================
    // Discount Changed
    // ==========================================================

    discountInput.addEventListener(
        "input",
        function () {

            if (
                saleType.value === "DIRECT" ||
                saleType.value === "RETURN"
            ) {

                calculateInvoice();

            } else if (
                saleType.value === "REPAIR"
            ) {

                calculateRepairTotal();

            }

        }
    );


    // ==========================================================
    // Service Report Selection
    // ==========================================================

    serviceReportSelect.addEventListener(
        "change",
        function () {

            const reportId =
                this.value;


            if (!reportId) {

                clearRepair();

                return;
            }


            loadServiceReport(
                reportId
            );

        }
    );


    // ==========================================================
    // Load Service Report
    // ==========================================================

    function loadServiceReport(
        reportId
    ) {

        repairInfo.style.display =
            "none";


        const url =
            `/sales/service-report/${reportId}/data/`;


        fetch(url, {
            method: "GET",
            headers: {
                "X-Requested-With":
                    "XMLHttpRequest"
            }
        })

        .then(response => {

            if (!response.ok) {
                throw new Error(
                    "Unable to load service report."
                );
            }

            return response.json();

        })

        .then(data => {

            if (!data.success) {

                alert(
                    data.message ||
                    "Unable to load service report."
                );

                clearRepair();

                return;
            }


            const report =
                data.report;


            // ----------------------------------------------
            // Customer
            // ----------------------------------------------

            customerSection.style.display =
                "block";


            customerSelect.value =
                report.customer_id;


            customerMobile.value =
                report.customer_mobile || "";


            // ----------------------------------------------
            // Report Information
            // ----------------------------------------------

            document.getElementById(
                "repair-ticket"
            ).textContent =
                report.ticket_number;


            document.getElementById(
                "repair-customer"
            ).textContent =
                report.customer_name;


            document.getElementById(
                "repair-technician"
            ).textContent =
                report.technician;


            document.getElementById(
                "repair-estimated-total"
            ).textContent =
                money(
                    report.estimated_total
                );


            repairInfo.style.display =
                "block";


            // ----------------------------------------------
            // Items
            // ----------------------------------------------

            repairItemsBody.innerHTML = "";


            let partsTotal = 0;


            report.items.forEach(
                item => {

                    const lineTotal =
                        parseFloat(
                            item.line_total
                        ) || 0;


                    partsTotal +=
                        lineTotal;


                    const row =
                        document.createElement(
                            "tr"
                        );


                    row.innerHTML = `

                        <td>

                            ${escapeHtml(
                                item.item_name
                            )}

                        </td>

                        <td>

                            ${escapeHtml(
                                item.specification || ""
                            )}

                        </td>

                        <td>

                            ${item.quantity}

                        </td>

                        <td class="text-end">

                            ${money(
                                item.rate
                            )}

                        </td>

                        <td class="text-end">

                            ${money(
                                lineTotal
                            )}

                        </td>

                    `;


                    repairItemsBody.appendChild(
                        row
                    );

                }
            );


            // ----------------------------------------------
            // Charges
            // ----------------------------------------------

            document.getElementById(
                "repair-parts-total"
            ).textContent =
                money(partsTotal);


            document.getElementById(
                "repair-labor"
            ).textContent =
                money(
                    report.labor_charge
                );


            document.getElementById(
                "repair-other"
            ).textContent =
                money(
                    report.other_charge
                );


            calculateRepairTotal();

        })

        .catch(error => {

            console.error(error);

            alert(
                "Unable to load service report."
            );

            clearRepair();

        });

    }


    // ==========================================================
    // Repair Total
    // ==========================================================

    function calculateRepairTotal() {

        const parts =
            parseFloat(
                document.getElementById(
                    "repair-parts-total"
                ).textContent
            ) || 0;


        const labor =
            parseFloat(
                document.getElementById(
                    "repair-labor"
                ).textContent
            ) || 0;


        const other =
            parseFloat(
                document.getElementById(
                    "repair-other"
                ).textContent
            ) || 0;


        const total =
            parts +
            labor +
            other;


        const discount =
            parseFloat(
                discountInput.value
            ) || 0;


        let grandTotal =
            total -
            discount;


        if (grandTotal < 0) {
            grandTotal = 0;
        }


        document.getElementById(
            "repair-total"
        ).textContent =
            money(total);


        document.getElementById(
            "summary-total"
        ).textContent =
            money(total);


        document.getElementById(
            "summary-tax"
        ).textContent =
            "0.00";


        document.getElementById(
            "summary-grand-total"
        ).textContent =
            money(grandTotal);

    }


    // ==========================================================
    // Clear Repair
    // ==========================================================

    function clearRepair() {

        repairInfo.style.display =
            "none";


        repairItemsBody.innerHTML =
            "";


        customerSelect.value =
            "";

        customerMobile.value =
            "";


        document.getElementById(
            "repair-ticket"
        ).textContent = "-";


        document.getElementById(
            "repair-customer"
        ).textContent = "-";


        document.getElementById(
            "repair-technician"
        ).textContent = "-";


        document.getElementById(
            "repair-estimated-total"
        ).textContent = "0.00";


        document.getElementById(
            "repair-parts-total"
        ).textContent = "0.00";


        document.getElementById(
            "repair-labor"
        ).textContent = "0.00";


        document.getElementById(
            "repair-other"
        ).textContent = "0.00";


        document.getElementById(
            "repair-total"
        ).textContent = "0.00";


        document.getElementById(
            "summary-total"
        ).textContent = "0.00";


        document.getElementById(
            "summary-tax"
        ).textContent = "0.00";


        document.getElementById(
            "summary-grand-total"
        ).textContent = "0.00";


        discountInput.value =
            "0";

    }


    // ==========================================================
    // Form Validation
    // ==========================================================

    document
        .getElementById(
            "sales-invoice-form"
        )
        .addEventListener(
            "submit",
            function (event) {

                const type =
                    saleType.value;


                if (!type) {

                    event.preventDefault();

                    alert(
                        "Please select a sale type."
                    );

                    return;
                }


                // ------------------------------------------
                // Direct / Return
                // ------------------------------------------

                if (
                    type === "DIRECT" ||
                    type === "RETURN"
                ) {

                    if (!customerSelect.value) {

                        event.preventDefault();

                        alert(
                            "Please select a customer."
                        );

                        return;
                    }


                    const rows =
                        document.querySelectorAll(
                            ".sale-item-row"
                        );


                    if (rows.length === 0) {

                        event.preventDefault();

                        alert(
                            "Please add at least one item."
                        );

                        return;
                    }


                    let valid =
                        true;


                    rows.forEach(
                        row => {

                            const code =
                                row.querySelector(
                                    ".item-code"
                                ).value;


                            const quantity =
                                parseInt(
                                    row.querySelector(
                                        ".item-quantity"
                                    ).value
                                ) || 0;


                            const rate =
                                parseFloat(
                                    row.querySelector(
                                        ".item-rate"
                                    ).value
                                ) || 0;


                            if (
                                !code ||
                                quantity <= 0 ||
                                rate < 0
                            ) {

                                valid =
                                    false;

                            }

                        }
                    );


                    if (!valid) {

                        event.preventDefault();

                        alert(
                            "Please complete all item details."
                        );

                        return;
                    }

                }


                // ------------------------------------------
                // Repair
                // ------------------------------------------

                if (type === "REPAIR") {

                    if (
                        !serviceReportSelect.value
                    ) {

                        event.preventDefault();

                        alert(
                            "Please select an approved service report."
                        );

                        return;
                    }


                    if (
                        !customerSelect.value
                    ) {

                        event.preventDefault();

                        alert(
                            "Customer could not be determined from the service report."
                        );

                        return;
                    }

                }


                // ------------------------------------------
                // Discount validation
                // ------------------------------------------

                const discount =
                    parseFloat(
                        discountInput.value
                    ) || 0;


                if (discount < 0) {

                    event.preventDefault();

                    alert(
                        "Discount cannot be negative."
                    );

                    return;
                }


                // Prevent double click

                const submitButton =
                    document.getElementById(
                        "generate-invoice"
                    );


                submitButton.disabled =
                    true;


                submitButton.innerHTML = `
                    <i class="fas fa-spinner fa-spin"></i>
                    Creating Invoice...
                `;

            }
        );

    


});


