
document.addEventListener("DOMContentLoaded", function () {

    const tableBody =
        document.querySelector("#purchase-items-body");

    const addRowBtn =
        document.getElementById("addRowBtn");

    const invoiceTotal =
        document.getElementById("invoiceTotal");


    // ==========================================================
    // PRODUCT DATA
    // ==========================================================

    let products = [];

    const productsElement =
        document.getElementById("products-data");

    if (productsElement) {

        try {

            products =
                JSON.parse(productsElement.textContent);

            console.log(
                "Purchase products loaded:",
                products.length
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
    // ESCAPE HTML
    // ==========================================================

    function escapeHtml(value) {

        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }


    // ==========================================================
    // CALCULATE TOTALS
    // ==========================================================

    function updateTotals() {

        let total = 0;

        tableBody
            .querySelectorAll(".purchase-item-row")
            .forEach(function (row) {

                const qty =
                    parseFloat(
                        row.querySelector(".quantity").value || 0
                    );

                const rate =
                    parseFloat(
                        row.querySelector(".rate").value || 0
                    );

                const lineTotal =
                    qty * rate;

                row.querySelector(
                    ".line-total"
                ).value = lineTotal.toFixed(2);

                total += lineTotal;
            });


        invoiceTotal.textContent =
            total.toFixed(2);
    }


    // ==========================================================
    // CLEAR PRODUCT FIELDS
    // ==========================================================

    function clearProductFields(row) {

        row.querySelector(".item-product-id").value = "";
        row.querySelector(".item-category").value = "";

        row.querySelector(".item-code").value = "";
        row.querySelector(".item-name").value = "";
        row.querySelector(".item-spec").value = "";
        row.querySelector(".hsn").value = "";
    }


    // ==========================================================
    // SELECT PRODUCT
    // ==========================================================

    function selectProduct(row, product) {

        row.querySelector(
            ".item-product-id"
        ).value = product.id || "";

        row.querySelector(
            ".item-category"
        ).value = product.category || "";

        row.querySelector(
            ".item-code"
        ).value = product.item_code || "";

        row.querySelector(
            ".item-name"
        ).value = product.item_name || "";

        row.querySelector(
            ".item-spec"
        ).value = product.specification || "";

        row.querySelector(
            ".hsn"
        ).value = product.hs_code || "";


        // Purchase rate remains manually entered.
        // We do NOT use selling_price here.
    }


    // ==========================================================
    // ATTACH ROW EVENTS
    // ==========================================================

    function attachRowEvents(row) {

        const searchInput =
            row.querySelector(".item-search");

        const suggestions =
            row.querySelector(".item-suggestions");

        const quantityInput =
            row.querySelector(".quantity");

        const rateInput =
            row.querySelector(".rate");

        const removeButton =
            row.querySelector(".remove-purchase-item");


        // ======================================================
        // PRODUCT SEARCH
        // ======================================================

        searchInput.addEventListener(
            "input",
            function () {

                const searchText =
                    this.value.trim().toLowerCase();


                clearProductFields(row);


                if (!searchText) {

                    suggestions.innerHTML = "";

                    suggestions.style.display =
                        "none";

                    return;
                }


                // ==================================================
                // FIND MATCHES
                // ==================================================

                const matches = products

                    .map(function (product) {

                        const code =
                            String(
                                product.item_code || ""
                            ).toLowerCase();

                        const name =
                            String(
                                product.item_name || ""
                            ).toLowerCase();


                        let score = 0;


                        // Exact code
                        if (code === searchText) {

                            score = 100;
                        }


                        // Exact name
                        else if (name === searchText) {

                            score = 95;
                        }


                        // Code starts with search
                        else if (
                            code.startsWith(searchText)
                        ) {

                            score = 90;
                        }


                        // Name starts with search
                        else if (
                            name.startsWith(searchText)
                        ) {

                            score = 85;
                        }


                        // Code contains search
                        else if (
                            code.includes(searchText)
                        ) {

                            score = 70;
                        }


                        // Name contains search
                        else if (
                            name.includes(searchText)
                        ) {

                            score = 60;
                        }


                        return {
                            product: product,
                            score: score
                        };

                    })

                    .filter(function (result) {

                        return result.score > 0;

                    })

                    .sort(function (a, b) {

                        if (
                            b.score !== a.score
                        ) {

                            return (
                                b.score -
                                a.score
                            );
                        }


                        return String(
                            a.product.item_code
                        ).localeCompare(
                            String(
                                b.product.item_code
                            )
                        );

                    })

                    .slice(0, 5);


                // ==================================================
                // NO RESULTS
                // ==================================================

                if (matches.length === 0) {

                    suggestions.innerHTML = `
                        <div class="list-group-item text-muted small">
                            No matching product found
                        </div>
                    `;

                    suggestions.style.display =
                        "block";

                    return;
                }


                // ==================================================
                // DISPLAY SUGGESTIONS
                // ==================================================

                suggestions.innerHTML = "";


                matches.forEach(function (result) {

                    const product =
                        result.product;


                    const item =
                        document.createElement(
                            "button"
                        );


                    item.type = "button";

                    item.className =
                        "list-group-item list-group-item-action";


                    item.innerHTML = `
                        <div class="fw-semibold">
                            ${escapeHtml(
                                product.item_code
                            )}
                        </div>

                        <div class="small text-muted">
                            ${escapeHtml(
                                product.item_name
                            )}
                        </div>
                    `;


                    item.addEventListener(
                        "click",
                        function () {

                            selectProduct(
                                row,
                                product
                            );

                            searchInput.value =
                                product.item_code +
                                " - " +
                                product.item_name;


                            suggestions.innerHTML =
                                "";

                            suggestions.style.display =
                                "none";
                        }
                    );


                    suggestions.appendChild(item);

                });


                suggestions.style.display =
                    "block";

            }
        );


        // ======================================================
        // QUANTITY
        // ======================================================

        quantityInput.addEventListener(
            "input",
            updateTotals
        );


        // ======================================================
        // RATE
        // ======================================================

        rateInput.addEventListener(
            "input",
            updateTotals
        );


        // ======================================================
        // REMOVE ROW
        // ======================================================

        removeButton.addEventListener(
            "click",
            function () {

                row.remove();

                updateTotals();
            }
        );
    }


    // ==========================================================
    // ADD NEW ROW
    // ==========================================================

    addRowBtn.addEventListener(
        "click",
        function () {

            const newRow =
                document.createElement("tr");

            newRow.classList.add(
                "purchase-item-row"
            );


            newRow.innerHTML = `
                <td>
                    <div class="position-relative">

                        <input
                            type="text"
                            class="form-control item-search"
                            placeholder="Search code or product name..."
                            autocomplete="off"
                            required
                        >

                        <div
                            class="item-suggestions list-group position-absolute w-100 shadow-sm"
                            style="
                                display:none;
                                z-index:9999;
                                max-height:240px;
                                overflow-y:auto;
                            "
                        ></div>

                    </div>

                    <input
                        type="hidden"
                        name="product_id[]"
                        class="item-product-id"
                    >

                    <input
                        type="hidden"
                        name="item_category[]"
                        class="item-category"
                    >
                </td>

                <td>
                    <input
                        type="text"
                        class="form-control item-code"
                        name="item_code[]"
                        readonly
                    >
                </td>

                <td>
                    <input
                        type="text"
                        class="form-control item-name"
                        name="item_name[]"
                        readonly
                    >
                </td>

                <td>
                    <input
                        type="text"
                        class="form-control item-spec"
                        name="item_specification[]"
                        readonly
                    >
                </td>

                <td>
                    <input
                        type="number"
                        class="form-control quantity"
                        name="quantity[]"
                        value="1"
                        min="1"
                        step="1"
                        required
                    >
                </td>

                <td>
                    <input
                        type="number"
                        class="form-control rate"
                        name="rate[]"
                        value="0"
                        min="0"
                        step="0.01"
                        required
                    >
                </td>

                <td>
                    <input
                        type="text"
                        class="form-control line-total"
                        readonly
                    >
                </td>

                <td>
                    <input
                        type="text"
                        class="form-control hsn"
                        name="hsn[]"
                        readonly
                    >
                </td>

                <td class="text-center">

                    <button
                        type="button"
                        class="btn btn-sm btn-outline-danger remove-purchase-item"
                        title="Remove Item"
                    >
                        <i class="fas fa-trash"></i>
                    </button>

                </td>
            `;


            tableBody.appendChild(newRow);

            attachRowEvents(newRow);

            updateTotals();
        }
    );


    // ==========================================================
    // INITIAL ROW
    // ==========================================================

    const firstRow =
        tableBody.querySelector(
            ".purchase-item-row"
        );

    if (firstRow) {

        attachRowEvents(firstRow);
    }


    // ==========================================================
    // INITIAL TOTAL
    // ==========================================================

    updateTotals();

});

