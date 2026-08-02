document.addEventListener("DOMContentLoaded", function () {

    /* ==========================================================
       Category / HSN Data
    ========================================================== */

    const categoryData = JSON.parse(
        document.getElementById("category-data").textContent
    );

    /* ==========================================================
       Elements
    ========================================================== */

    const modalTitle = document.getElementById("productModalTitle");

    const submitButton = document.getElementById("btnSaveProduct");

    const productForm = document.getElementById("productForm");

    const btnAdd = document.getElementById("btnAddProduct");

    const category = document.getElementById("category");

    const hsn = document.getElementById("hs_code");

    /* ==========================================================
       Populate HSN Dropdown
    ========================================================== */

    function populateHSN(selectedHSN = "") {

        const selectedCategory = category.value;

        hsn.innerHTML = "";

        const first = document.createElement("option");

        first.value = "";

        first.textContent = "Select HSN";

        hsn.appendChild(first);

        if (!categoryData[selectedCategory]) return;

        categoryData[selectedCategory].forEach(function (item) {

            const option = document.createElement("option");

            option.value = item[0];

            option.textContent = item[0] + " - " + item[1];

            if (selectedHSN === item[0]) {

                option.selected = true;

            }

            hsn.appendChild(option);

        });

    }

    category.addEventListener("change", function () {

        populateHSN();

    });

    /* ==========================================================
       Reset Form
    ========================================================== */

    function resetForm() {

        productForm.reset();

        category.selectedIndex = 0;

        populateHSN();

        document.getElementById("reorder_level").value = 10;

    }

    /* ==========================================================
       Add Product
    ========================================================== */

    btnAdd.addEventListener("click", function () {

        resetForm();

        modalTitle.innerHTML = "Add Product";

        submitButton.innerHTML =
            '<i class="fas fa-save"></i> Save Product';

        productForm.action =
            productForm.dataset.createUrl;

    });

    /* ==========================================================
       Edit Product
    ========================================================== */

    document.querySelectorAll(".edit-product").forEach(function (button) {

        button.addEventListener("click", function () {

            modalTitle.innerHTML = "Edit Product";

            submitButton.innerHTML =
                '<i class="fas fa-save"></i> Update Product';

            document.getElementById("item_code").value =
                this.dataset.code;

            document.getElementById("item_name").value =
                this.dataset.name;

            document.getElementById("category").value =
                this.dataset.category;

            populateHSN(this.dataset.hsn);

            document.getElementById("specification").value =
                this.dataset.specification;

            document.getElementById("unit_of_measure").value =
                this.dataset.unit;

            document.getElementById("reorder_level").value =
                this.dataset.reorder;

            productForm.action =
                productForm.dataset.updateUrlTemplate.replace(
                    "0",
                    this.dataset.id
                );

        });

    });

    /* ==========================================================
       Auto Hide Alerts
    ========================================================== */

    setTimeout(function () {

        document.querySelectorAll(".auto-dismiss").forEach(function (alert) {

            alert.classList.remove("show");

            setTimeout(function () {

                alert.remove();

            }, 300);

        });

    }, 4000);

});

/* ==========================================================
   Delete Product
========================================================== */

const deleteForm = document.getElementById("deleteForm");

const deleteName = document.getElementById("deleteProductName");

document.querySelectorAll(".delete-product").forEach(function (button) {

    button.addEventListener("click", function () {

        deleteName.textContent = this.dataset.name;

       deleteForm.action =
            deleteForm.dataset.deleteUrlTemplate.replace(
                "0",
                this.dataset.id
            );

    });

});