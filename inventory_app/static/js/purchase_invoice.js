
document.addEventListener("DOMContentLoaded", function () {

    const purchaseForm = document.getElementById("purchase-invoice-form");
    const tableBody = document.getElementById("purchase-items-body");
    const addRowBtn = document.getElementById("addRowBtn");
    const invoiceTotal = document.getElementById("invoiceTotal");

    const vendorSearch = document.getElementById("vendor-search");
    const vendorId = document.getElementById("vendor-id");
    const vendorSuggestions = document.getElementById("vendor-suggestions");

    // ==========================================================
    // LOAD DATA
    // ==========================================================

    let products = [];
    let vendors = [];

    try {
        products = JSON.parse(document.getElementById("products-data").textContent);
    } catch (error) {
        console.error("Unable to load products:", error);
    }

    try {
        vendors = JSON.parse(document.getElementById("vendors-data").textContent);
    } catch (error) {
        console.error("Unable to load vendors:", error);
    }

    // ==========================================================
    // HELPERS
    // ==========================================================

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function findProduct(itemCode, category) {
        return products.find(product =>
            String(product.item_code) === String(itemCode) &&
            String(product.category || "") === String(category || "")
        );
    }

    // ==========================================================
    // TOTALS
    // ==========================================================

    function updateTotals() {

        let total = 0;

        tableBody.querySelectorAll(".purchase-item-row").forEach(row => {

            const qty = parseFloat(row.querySelector(".quantity").value || 0);
            const rate = parseFloat(row.querySelector(".rate").value || 0);
            const vatRate = parseFloat(row.querySelector(".vat-rate").value || 0);

            const itemAmount = qty * rate;
            const totalVat = itemAmount * vatRate / 100;
            const lineTotal = itemAmount + totalVat;

            row.querySelector(".total-vat").value = totalVat.toFixed(2);
            row.querySelector(".line-total").value = lineTotal.toFixed(2);

            total += lineTotal;
        });

        invoiceTotal.textContent = total.toFixed(2);
    }

    // ==========================================================
    // VENDOR AUTOCOMPLETE
    // ==========================================================

    let matchingVendors = [];

    function searchVendors(query) {

        query = query.toLowerCase().trim();
        vendorSuggestions.innerHTML = "";

        if (!query) {
            vendorSuggestions.style.display = "none";
            matchingVendors = [];
            return;
        }

        matchingVendors = vendors.filter(vendor => (
            String(vendor.name || "").toLowerCase().includes(query) ||
            String(vendor.vendor_code || "").toLowerCase().includes(query) ||
            String(vendor.pan || "").toLowerCase().includes(query)
        )).slice(0, 5);

        if (!matchingVendors.length) {
            vendorSuggestions.style.display = "none";
            return;
        }

        matchingVendors.forEach((vendor, index) => {

            const option = document.createElement("button");

            option.type = "button";
            option.className = "list-group-item list-group-item-action";

            option.innerHTML = `
                <div class="fw-semibold">
                    ${escapeHtml(vendor.vendor_code)} - ${escapeHtml(vendor.name)}
                </div>
                <small class="text-muted">
                    PAN: ${escapeHtml(vendor.pan || "N/A")}
                    | Mobile: ${escapeHtml(vendor.mobile || "N/A")}
                </small>
            `;

            option.addEventListener("click", function () {
                selectVendor(index);
            });

            vendorSuggestions.appendChild(option);
        });

        vendorSuggestions.style.display = "block";
    }

    function selectVendor(index) {

        const vendor = matchingVendors[index];
        if (!vendor) return;

        vendorSearch.value = `${vendor.vendor_code} - ${vendor.name}`;
        vendorId.value = vendor.id;

        vendorSuggestions.style.display = "none";
        vendorSearch._activeSuggestionIndex = -1;
        vendorSearch.focus();
    }

    vendorSearch.addEventListener("input", function () {
        vendorId.value = "";
        this._activeSuggestionIndex = -1;
        searchVendors(this.value);
    });

    // ==========================================================
    // PRODUCT HELPERS
    // ==========================================================

    function clearProductFields(row) {

        row.querySelector(".item-product-id").value = "";
        row.querySelector(".item-category").value = "";

        row.querySelector(".item-code").value = "";
        row.querySelector(".item-name").value = "";
        row.querySelector(".item-spec").value = "";
        row.querySelector(".hsn").value = "";
    }

    function selectProduct(row, product) {

        row.querySelector(".item-product-id").value = product.id || "";
        row.querySelector(".item-category").value = product.category || "";

        row.querySelector(".item-code").value = product.item_code || "";
        row.querySelector(".item-name").value = product.item_name || "";
        row.querySelector(".item-spec").value = product.specification || "";
        row.querySelector(".hsn").value = product.hs_code || "";

        row.querySelector(".rate").value = product.last_rate || 0;
        row.querySelector(".selling_rate").value = product.selling_price || 0;

        updateTotals();
    }

    // ==========================================================
    // PRODUCT SEARCH AND ROW EVENTS
    // ==========================================================

    function attachRowEvents(row) {

        if (row.dataset.eventsAttached === "true") return;

        row.dataset.eventsAttached = "true";

        const searchInput = row.querySelector(".item-search");
        const suggestions = row.querySelector(".item-suggestions");

        const quantityInput = row.querySelector(".quantity");
        const rateInput = row.querySelector(".rate");
        const vatRateInput = row.querySelector(".vat-rate");

        const removeButton = row.querySelector(".remove-purchase-item");

        row._matchingProducts = [];

        searchInput.addEventListener("input", function () {

            const searchText = this.value.trim().toLowerCase();

            this._activeSuggestionIndex = -1;

            clearProductFields(row);
            row._matchingProducts = [];
            suggestions.innerHTML = "";

            if (!searchText) {
                suggestions.style.display = "none";
                return;
            }

            const matches = products.map(product => {

                const code = String(product.item_code || "").toLowerCase();
                const name = String(product.item_name || "").toLowerCase();

                let score = 0;

                if (code === searchText) score = 100;
                else if (name === searchText) score = 95;
                else if (code.startsWith(searchText)) score = 90;
                else if (name.startsWith(searchText)) score = 85;
                else if (code.includes(searchText)) score = 70;
                else if (name.includes(searchText)) score = 60;

                return { product, score };

            })
            .filter(result => result.score > 0)
            .sort((a, b) => b.score - a.score)
            .slice(0, 5);

            if (!matches.length) {

                suggestions.innerHTML = `
                    <div class="list-group-item text-muted small">
                        No matching product found
                    </div>
                `;

                suggestions.style.display = "block";
                return;
            }

            row._matchingProducts = matches.map(result => result.product);

            matches.forEach((result, index) => {

                const product = result.product;
                const option = document.createElement("button");

                option.type = "button";
                option.className = "list-group-item list-group-item-action";

                option.innerHTML = `
                    <div class="fw-semibold">${escapeHtml(product.item_code)}</div>
                    <div class="small text-muted">${escapeHtml(product.item_name)}</div>
                `;

                option.addEventListener("click", function () {
                    selectProductFromDropdown(row, index);
                });

                suggestions.appendChild(option);
            });

            suggestions.style.display = "block";
        });

        function selectProductFromDropdown(currentRow, index) {

            const product = currentRow._matchingProducts[index];
            if (!product) return;

            selectProduct(currentRow, product);

            searchInput.value = product.item_code + " - " + product.item_name;

            suggestions.style.display = "none";
            searchInput._activeSuggestionIndex = -1;
            searchInput.focus();
        }

        quantityInput.addEventListener("input", updateTotals);
        rateInput.addEventListener("input", updateTotals);
        vatRateInput.addEventListener("input", updateTotals);

        removeButton.addEventListener("click", function () {
            row.remove();
            updateTotals();
        });
    }

    // ==========================================================
    // ADD NEW ROW
    // ==========================================================

    function addNewRow() {

        const newRow = document.createElement("tr");
        newRow.classList.add("purchase-item-row");

        newRow.innerHTML = `
            <td>
                <div class="position-relative">
                    <input type="text"
                           class="form-control item-search"
                           placeholder="Search code or product name..."
                           autocomplete="off"
                           required>

                    <div class="item-suggestions list-group position-absolute w-100 shadow-sm"
                         style="display:none; z-index:9999; max-height:240px; overflow-y:auto;">
                    </div>
                </div>

                <input type="hidden" name="product_id[]" class="item-product-id">
                <input type="hidden" name="item_category[]" class="item-category">
            </td>

            <td><input type="text" class="form-control item-code" name="item_code[]" readonly></td>
            <td><input type="text" class="form-control item-name" name="item_name[]" readonly></td>
            <td><input type="text" class="form-control item-spec" name="item_specification[]" readonly></td>
            <td><input type="text" class="form-control hsn" name="hsn[]" readonly></td>

            <td>
                <input type="number" class="form-control quantity"
                       name="quantity[]" value="1" min="1" step="1" required>
            </td>

            <td>
                <input type="number" class="form-control rate"
                       name="rate[]" value="0" min="0" step="0.01" required>
            </td>

            <td>
                <input type="number" class="form-control vat-rate"
                       name="vat_rate[]" value="13" min="0" step="0.01" required>
            </td>

            <td>
                <input type="text" class="form-control total-vat"
                       name="total_vat[]" value="0.00" readonly>
            </td>

            <td>
                <input type="number" class="form-control selling_rate"
                       name="selling_rate[]" value="0" min="0" step="0.01" required>
            </td>

            <td>
                <input type="text" class="form-control line-total" readonly>
            </td>

            <td class="text-center">
                <button type="button" class="btn btn-sm btn-outline-danger remove-purchase-item">
                    <i class="fas fa-trash"></i>
                </button>
            </td>
        `;

        tableBody.appendChild(newRow);

        attachRowEvents(newRow);
        updateTotals();

        newRow.querySelector(".item-search").focus();
    }

    addRowBtn.addEventListener("click", addNewRow);

    // ==========================================================
    // INITIALIZE EXISTING ROWS FOR EDITING
    // ==========================================================

    tableBody.querySelectorAll(".purchase-item-row").forEach(row => {

        attachRowEvents(row);

        const itemCode = row.querySelector(".item-code").value;

        // Match the existing item with the product JSON.
        const product = products.find(p =>
            String(p.item_code) === String(itemCode)
        );

        if (product) {

            row.querySelector(".item-product-id").value = product.id || "";
            row.querySelector(".item-category").value = product.category || "";

            // Do not overwrite existing purchase rate or MRP.
        } else if (itemCode) {
            console.warn("Product not found for existing invoice item:", itemCode);
        }
    });

    // ==========================================================
    // KEYBOARD NAVIGATION
    // ==========================================================

    function getNavigationFields() {

        const selector = [
            'input:not([type="hidden"]):not([type="submit"]):not([readonly]):not([disabled])',
            'select:not([disabled])',
            'textarea:not([disabled])',
            'button:not([disabled]):not(.list-group-item-action)'
        ].join(",");

        return Array.from(purchaseForm.querySelectorAll(selector)).filter(field => (
            field.offsetParent !== null &&
            !field.closest(".item-suggestions") &&
            !field.closest("#vendor-suggestions")
        ));
    }

    function moveFocus(currentField, direction) {

        const fields = getNavigationFields();
        const currentIndex = fields.indexOf(currentField);
        const nextIndex = currentIndex + direction;

        if (currentIndex === -1 || nextIndex < 0 || nextIndex >= fields.length) return;

        fields[nextIndex].focus();

        if (
            fields[nextIndex].tagName === "INPUT" &&
            !["file", "date"].includes(fields[nextIndex].type)
        ) {
            fields[nextIndex].select?.();
        }
    }

    function handleAutocompleteKeydown(e, input, suggestions) {

        const options = suggestions.querySelectorAll("button.list-group-item-action");

        if (e.key === "Escape") {
            e.preventDefault();
            suggestions.style.display = "none";
            input._activeSuggestionIndex = -1;
            return true;
        }

        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();

            if (options.length) {
                let index = input._activeSuggestionIndex ?? -1;

                if (index < 0 || index >= options.length) index = 0;

                options[index].click();
            }

            return true;
        }

        if ((e.key === "ArrowDown" || e.key === "ArrowUp") && options.length) {

            e.preventDefault();

            let index = input._activeSuggestionIndex ?? -1;

            index = e.key === "ArrowDown"
                ? (index + 1) % options.length
                : (index <= 0 ? options.length - 1 : index - 1);

            input._activeSuggestionIndex = index;

            options.forEach((option, i) => {
                option.classList.toggle("active", i === index);
            });

            options[index].scrollIntoView({ block: "nearest" });

            return true;
        }

        return false;
    }

    purchaseForm.addEventListener("keydown", function (e) {

        const activeField = e.target;

        const isVendorSearch = activeField.id === "vendor-search";
        const isProductSearch = activeField.classList.contains("item-search");

        if (isVendorSearch || isProductSearch) {

            const suggestions = isVendorSearch
                ? vendorSuggestions
                : activeField.closest(".position-relative").querySelector(".item-suggestions");

            if (handleAutocompleteKeydown(e, activeField, suggestions)) return;
        }

        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {

            if (activeField.tagName === "TEXTAREA") return;

            if (
                activeField.tagName === "INPUT" &&
                ["text", "search", "email", "tel", "url", "password"].includes(activeField.type)
            ) {
                const start = activeField.selectionStart;
                const end = activeField.selectionEnd;
                const length = activeField.value.length;

                if (e.key === "ArrowRight" && end < length) return;
                if (e.key === "ArrowLeft" && start > 0) return;
            }

            e.preventDefault();
            moveFocus(activeField, e.key === "ArrowRight" ? 1 : -1);
            return;
        }

        if (e.key === "Enter") {

            if (
                activeField.tagName === "BUTTON" ||
                activeField.type === "submit" ||
                activeField.tagName === "TEXTAREA" ||
                activeField.type === "file"
            ) {
                return;
            }

            e.preventDefault();
            moveFocus(activeField, 1);
        }

    }, true);

    // ==========================================================
    // CLOSE DROPDOWNS
    // ==========================================================

    document.addEventListener("click", function (e) {

        if (!vendorSearch.contains(e.target) && !vendorSuggestions.contains(e.target)) {
            vendorSuggestions.style.display = "none";
        }

        tableBody.querySelectorAll(".purchase-item-row").forEach(row => {

            const searchInput = row.querySelector(".item-search");
            const suggestions = row.querySelector(".item-suggestions");

            if (!searchInput.contains(e.target) && !suggestions.contains(e.target)) {
                suggestions.style.display = "none";
            }
        });
    });

    // ==========================================================
    // INITIALIZE TOTALS
    // ==========================================================

    updateTotals();

});
