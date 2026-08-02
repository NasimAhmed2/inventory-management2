document.addEventListener("DOMContentLoaded", function () {

    const mobile = document.getElementById("mobile");
    const customerId = document.getElementById("customer_id");

    const existingCustomer = document.getElementById("existingCustomer");
    const newCustomerSection = document.getElementById("newCustomerSection");

    const existingName = document.getElementById("existing_name");
    const existingEmail = document.getElementById("existing_email");
    const existingAddress = document.getElementById("existing_address");

    //-------------------------------------------------------
    // Lookup Customer
    //-------------------------------------------------------

    let timer = null;

    mobile.addEventListener("keyup", function () {

        clearTimeout(timer);

        const value = this.value.trim();

        customerId.value = "";

        existingCustomer.classList.add("d-none");

        newCustomerSection.classList.add("d-none");

        if (value.length < 7) {
            return;
        }

        timer = setTimeout(function () {

            fetch(`/ajax/customer-lookup/?mobile=${encodeURIComponent(value)}`)

                .then(response => response.json())

                .then(data => {

                    if (data.found) {

                        customerId.value = data.customer.id;

                        existingName.innerText = data.customer.name;

                        existingEmail.innerText =
                            data.customer.email || "-";

                        existingAddress.innerText =
                            data.customer.address || "-";

                        existingCustomer.classList.remove("d-none");

                        newCustomerSection.classList.add("d-none");

                    } else {

                        customerId.value = "";

                        existingCustomer.classList.add("d-none");

                        newCustomerSection.classList.remove("d-none");

                    }

                })

                .catch(function (err) {

                    console.error(err);

                });

        }, 500);

    });

    //-------------------------------------------------------
    // Reset Form When Modal Closed
    //-------------------------------------------------------

    const modal = document.getElementById("ticketModal");

    modal.addEventListener("hidden.bs.modal", function () {

        document.getElementById("ticketForm").reset();

        customerId.value = "";

        existingCustomer.classList.add("d-none");

        newCustomerSection.classList.add("d-none");

    });

});