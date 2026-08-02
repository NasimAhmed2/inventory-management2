document.addEventListener("DOMContentLoaded", function () {

    const tbody = document.getElementById("itemRows");
    const addButton = document.getElementById("addItemRow");

    //--------------------------------------------------
    // Build Product Lookup
    //--------------------------------------------------

    const categories = [...new Set(PRODUCTS.map(p => p.category))];

    //--------------------------------------------------
    // Create Row
    //--------------------------------------------------

    function newRow() {

        const tr = document.createElement("tr");

        tr.innerHTML = `

<td>

<select class="form-select category-select" name="category[]">

<option value="">Select</option>

${categories.map(c =>
`<option value="${c}">${c}</option>`
).join("")}

</select>

</td>

<td>

<select class="form-select product-select" name="product_id[]">

<option value="">Select Product</option>

</select>

</td>

<td>

<input
class="form-control stock-display"
readonly
>

</td>

<td>

<input
type="number"
min="1"
value="1"
name="quantity[]"
class="form-control quantity"
>

</td>

<td>

<input
type="number"
step="0.01"
value="0"
name="rate[]"
class="form-control rate"
>

</td>

<td>

<input
class="form-control line-total"
readonly
value="0.00"
>

</td>

<td>

<input
class="form-control"
name="item_remarks[]"
>

</td>

<td class="text-center">

<button
type="button"
class="btn btn-danger btn-sm removeRow"
>

<i class="fas fa-times"></i>

</button>

</td>

`;

        tbody.appendChild(tr);

    }

    //--------------------------------------------------
    // Category Changed
    //--------------------------------------------------

    tbody.addEventListener("change", function (e) {

        if (!e.target.classList.contains("category-select"))
            return;

        const row = e.target.closest("tr");

        const category = e.target.value;

        const productSelect =
            row.querySelector(".product-select");

        productSelect.innerHTML =
            '<option value="">Select Product</option>';

        PRODUCTS
            .filter(p => p.category === category)
            .forEach(product => {

                productSelect.innerHTML += `

<option value="${product.id}">

${product.item_name}

</option>

`;

            });

    });

    //--------------------------------------------------
    // Product Changed
    //--------------------------------------------------

    tbody.addEventListener("change", function (e) {

        if (!e.target.classList.contains("product-select"))
            return;

        const row = e.target.closest("tr");

        const product = PRODUCTS.find(
            p => p.id == e.target.value
        );

        if (!product)
            return;

        row.querySelector(".stock-display").value =
            product.available_stock;

        row.querySelector(".rate").value =
            product.selling_price.toFixed(2);

        calculateRow(row);

    });

    //--------------------------------------------------
    // Qty / Rate Changed
    //--------------------------------------------------

    tbody.addEventListener("input", function (e) {

        if (
            e.target.classList.contains("quantity") ||
            e.target.classList.contains("rate")
        ) {

            calculateRow(
                e.target.closest("tr")
            );

        }

    });

    //--------------------------------------------------
    // Remove Row
    //--------------------------------------------------

    tbody.addEventListener("click", function (e) {

        if (!e.target.closest(".removeRow"))
            return;

        e.target.closest("tr").remove();

        calculateTotals();

    });

    //--------------------------------------------------
    // Add Row
    //--------------------------------------------------

    addButton.addEventListener(
        "click",
        newRow
    );

    //--------------------------------------------------
    // Row Total
    //--------------------------------------------------

    function calculateRow(row) {

        const qty = parseFloat(
            row.querySelector(".quantity").value || 0
        );

        const rate = parseFloat(
            row.querySelector(".rate").value || 0
        );

        row.querySelector(".line-total").value =
            (qty * rate).toFixed(2);

        calculateTotals();

    }

    //--------------------------------------------------
    // Grand Total
    //--------------------------------------------------

    function calculateTotals() {

        let parts = 0;

        document
            .querySelectorAll(".line-total")
            .forEach(input => {

                parts += parseFloat(
                    input.value || 0
                );

            });

        const labour = parseFloat(
            document.getElementById("labourCharge").value || 0
        );

        const other = parseFloat(
            document.getElementById("otherCharge").value || 0
        );

        document.getElementById("partsTotal").value =
            parts.toFixed(2);

        document.getElementById("labourDisplay").value =
            labour.toFixed(2);

        document.getElementById("otherDisplay").value =
            other.toFixed(2);

        document.getElementById("estimatedTotal").value =
            (parts + labour + other).toFixed(2);

    }

    //--------------------------------------------------
    // Charges Changed
    //--------------------------------------------------

    document
        .querySelectorAll(".estimate-field")
        .forEach(field => {

            field.addEventListener(
                "input",
                calculateTotals
            );

        });

    //--------------------------------------------------
    // Existing Rows
    //--------------------------------------------------

    document
        .querySelectorAll("#itemRows tr")
        .forEach(row => {

            calculateRow(row);

        });

    //--------------------------------------------------
    // First Empty Row
    //--------------------------------------------------

    if (
        tbody.children.length === 0
    ) {

        newRow();

    }

});