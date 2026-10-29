import os
import re
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from django.views.decorators.http import require_POST
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Q, Sum
from django.http import FileResponse, Http404
from django.core.paginator import Paginator
from .models import Product, InventoryStock, InventoryMovement
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import F
import xlrd
from .models import (
    Product, PurchaseInvoice, PurchaseLineItem, UserProfile, Vendor, 
    ServiceReport, Customer, Ticket, SalesInvoice, VendorLedger,  
    Product_Categories, SalesLineItem, 
)

from .services import (
    InventoryService, CustomerService, TicketService, ServiceReportService,
    SaleService, VendorLedgerService, VendorLedgerEmailService,
)

from .helpers import (
    generate_item_code, generate_vendor_code, generate_invoice_number
)


from django.shortcuts import render, redirect, get_object_or_404
import json
from datetime import date, datetime
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from openpyxl import load_workbook, Workbook
from openpyxl.styles import Font, Alignment

from .forms import ProductForm
# from .models import Product_Categories


User = get_user_model()

CATEGORY_HSN = {}

for entry in Product_Categories.objects.all():
    CATEGORY_HSN.setdefault(entry.category_name, []).append(
        (entry.hsn_code, entry.description)
    )

print("CATEGORY_HSN:", CATEGORY_HSN)  # Debugging line to check the contents of CATEGORY_HSN

def generate_customer_code():

    prefix = date.today().strftime("C%y%m")

    last = (
        Customer.objects
        .filter(customer_code__startswith=prefix)
        .order_by("-customer_code")
        .first()
    )

    if last:

        number = int(last.customer_code[-4:]) + 1

    else:

        number = 1

    return f"{prefix}{number:04d}"

def placeholder_view(request, page_title="Coming Soon"):
    return render(request, "placeholder.html", {"page_title": page_title})



def day_reports(request):
    today = timezone.localdate()
    zero = Decimal("0.00")

    # Purchases dated today
    purchases = PurchaseInvoice.objects.filter(
        invoice_date=today
    ).select_related("vendor")

    purchase_total = purchases.aggregate(
        total=Sum("grand_total")
    )["total"] or zero

    # Only today's sale invoices
    sales_invoices = SalesInvoice.objects.filter(
        invoice_date=today
    ).select_related("customer", "payment_details")

    sale_lines = SalesLineItem.objects.filter(
        invoice__in=sales_invoices
    ).select_related("invoice")

    # Product costs from InventoryStock.last_cost
    item_codes = set(sale_lines.values_list("item_code", flat=True))

    product_costs = dict(
        InventoryStock.objects.filter(
            product__item_code__in=item_codes
        ).values_list("product__item_code", "last_cost")
    )

    sales_total = zero
    return_total = zero
    cost_total = zero
    invoice_sales = {}

    for line in sale_lines:
        line_amount = line.rate * line.quantity
        invoice_id = line.invoice_id

        invoice_sales[invoice_id] = (
            invoice_sales.get(invoice_id, zero) + line_amount
        )

        if line.invoice.sale_type == "RETURN":
            return_total += line_amount
        else:
            sales_total += line_amount

            unit_cost = product_costs.get(line.item_code) or zero
            cost_total += unit_cost * line.quantity

    # Estimated profit on regular sales, before other expenses
    estimated_profit = sales_total - cost_total

    # Today's payment collection totals
    payment_totals = sales_invoices.aggregate(
        cash=Sum("payment_details__cash_amount"),
        upi=Sum("payment_details__upi_amount"),
        card=Sum("payment_details__card_amount"),
        credit=Sum("payment_details__credit_amount"),
    )

    cash_total = payment_totals["cash"] or zero
    upi_total = payment_totals["upi"] or zero
    card_total = payment_totals["card"] or zero
    credit_total = payment_totals["credit"] or zero

    collection_total = cash_total + upi_total + card_total

    # Show each invoice's line-item value in the invoice table
    for invoice in sales_invoices:
        invoice.report_total = invoice_sales.get(invoice.pk, zero)

    context = {
        "today": today,
        "purchases": purchases,
        "sales_invoices": sales_invoices,
        "purchase_total": purchase_total,
        "sales_total": sales_total,
        "return_total": return_total,
        "cost_total": cost_total,
        "estimated_profit": estimated_profit,
        "cash_total": cash_total,
        "upi_total": upi_total,
        "card_total": card_total,
        "credit_total": credit_total,
        "collection_total": collection_total,
    }

    return render(request, "day_reports.html", context)


def sales_customers(request):

    customers = Customer.objects.all().order_by("name", "id")

    search = request.GET.get("search", "").strip()

    if search:
        customers = customers.filter(
            Q(customer_code__icontains=search) |
            Q(name__icontains=search) |
            Q(mobile__icontains=search) |
            Q(email__icontains=search)
        )

    if request.method == "POST":

        ajax_request = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
        )

        try:
            with transaction.atomic():

                customer_id = request.POST.get("customer_id")

                if customer_id:

                    CustomerService.update_customer(
                        customer_id=customer_id,
                        request=request,
                    )

                    customer = Customer.objects.get(pk=customer_id)

                    message = "Customer updated successfully."

                else:

                    customer_code = request.POST.get(
                        "customer_code", ""
                    ).strip()

                    name = request.POST.get(
                        "name", ""
                    ).strip()

                    mobile = request.POST.get(
                        "mobile", ""
                    ).strip()

                    existing_customer = Customer.objects.filter(
                        customer_code__iexact=customer_code,
                        name__iexact=name,
                        mobile=mobile,
                    ).first()

                    if existing_customer:

                        if ajax_request:
                            return JsonResponse(
                                {
                                    "success": False,
                                    "message": (
                                        "Customer already exists: "
                                        f"{existing_customer.customer_code} - "
                                        f"{existing_customer.name}"
                                    ),
                                },
                                status=409,
                            )

                        messages.warning(
                            request,
                            (
                                f"Customer already exists! "
                                f"Code: {existing_customer.customer_code}, "
                                f"Name: {existing_customer.name}, "
                                f"Mobile: {existing_customer.mobile}."
                            )
                        )

                        return redirect("sales_customers")

                    CustomerService.create_customer(request=request)

                    customer = Customer.objects.filter(
                        customer_code__iexact=customer_code,
                        name__iexact=name,
                        mobile=mobile,
                    ).first()

                    if not customer:
                        raise Exception(
                            "Customer was not found after creation."
                        )

                    message = "Customer created successfully."

            if ajax_request:
                return JsonResponse({
                    "success": True,
                    "message": message,
                    "customer": {
                        "id": customer.id,
                        "customer_code": customer.customer_code,
                        "name": customer.name,
                        "mobile": customer.mobile or "",
                    },
                })

            messages.success(request, message)

        except Exception as e:

            if ajax_request:
                return JsonResponse(
                    {
                        "success": False,
                        "message": str(e),
                    },
                    status=400,
                )

            messages.error(request, str(e))

        return redirect("sales_customers")

    paginator = Paginator(customers, 20)

    page_number = request.GET.get("page")
    customers_page = paginator.get_page(page_number)

    context = {
        "customers": customers_page,
        "search": search,
    }

    return render(request, "customers.html", context)

@require_POST
def sales_customers_create(request):

    try:
        with transaction.atomic():

            customer_code = request.POST.get(
                "customer_code", ""
            ).strip()

            name = request.POST.get(
                "name", ""
            ).strip()

            mobile = request.POST.get(
                "mobile", ""
            ).strip()

            if not name:
                return JsonResponse({
                    "success": False,
                    "message": "Customer name is required."
                }, status=400)

            existing_customer = Customer.objects.filter(
                customer_code__iexact=customer_code,
                name__iexact=name,
                mobile=mobile,
            ).first()

            if existing_customer:
                return JsonResponse({
                    "success": False,
                    "message": "This customer already exists."
                }, status=409)

            CustomerService.create_customer(request=request)

            customer = Customer.objects.filter(
                customer_code__iexact=customer_code,
                name__iexact=name,
                mobile=mobile,
            ).first()

            if not customer:
                raise Exception(
                    "Customer was not found after creation."
                )

            return JsonResponse({
                "success": True,
                "message": "Customer created successfully.",
                "customer": {
                    "id": customer.id,
                    "customer_code": customer.customer_code,
                    "name": customer.name,
                    "mobile": customer.mobile or "",
                }
            })

    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": str(e),
        }, status=400)


@login_required
def sales_customers_excel(request):

    if request.method != "POST":
        return redirect("sales_customers")

    excel_file = request.FILES.get("excel_file")

    if not excel_file:
        messages.error(request, "Please select an Excel file.")
        return redirect("sales_customers")

    extension = os.path.splitext(excel_file.name)[1].lower()

    if extension not in [".xlsx", ".xls"]:
        messages.error(
            request,
            "Invalid file format. Please upload an .xlsx or .xls file."
        )
        return redirect("sales_customers")

    if excel_file.size > 5 * 1024 * 1024:
        messages.error(request, "File size must not exceed 5 MB.")
        return redirect("sales_customers")

    workbook = None

    try:
        # Open the first worksheet
        if extension == ".xlsx":
            workbook = load_workbook(
                excel_file,
                read_only=True,
                data_only=True
            )
            worksheet = workbook.active
            rows = worksheet.iter_rows(values_only=True)

        else:
            workbook = xlrd.open_workbook(
                file_contents=excel_file.read()
            )
            worksheet = workbook.sheet_by_index(0)

            rows = (
                worksheet.row_values(i)
                for i in range(worksheet.nrows)
            )

        headers = next(rows, None)

        if not headers:
            messages.error(request, "The Excel file is empty.")
            return redirect("sales_customers")

        # Normalize headers
        normalized_headers = [
            str(header).strip().lower() if header is not None else ""
            for header in headers
        ]

        required_columns = [
            "type",
            "name",
            "mobile",
            "email",
            "payment",
            "creditlimit",
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in normalized_headers
        ]

        if missing_columns:
            messages.error(
                request,
                "Missing Excel columns: "
                + ", ".join(missing_columns)
                + ". Required columns: Type, Name, Mobile, Email, "
                  "Payment, CreditLimit."
            )
            return redirect("sales_customers")

        column_index = {
            name: normalized_headers.index(name)
            for name in required_columns
        }

        def cell_value(row, column_name):
            index = column_index[column_name]

            if index >= len(row) or row[index] is None:
                return ""

            value = row[index]

            # Avoid converting whole numbers to strings ending in .0
            if isinstance(value, float) and value.is_integer():
                value = int(value)

            return str(value).strip()

        imported = 0
        skipped = 0
        errors = []

        valid_customer_types = {
            "consumer",
            "retailer",
            "wholesaler",
        }

        valid_payment_types = {
            "cash",
            "credit",
        }

        for row_number, row in enumerate(rows, start=2):

            # Skip completely empty rows
            if not row or all(
                value is None or str(value).strip() == ""
                for value in row
            ):
                continue

            customer_type = cell_value(row, "type").lower()
            name = cell_value(row, "name")
            mobile = cell_value(row, "mobile")
            email = cell_value(row, "email")
            payment_type = cell_value(row, "payment").lower()
            credit_limit_text = cell_value(row, "creditlimit")

            if not customer_type or not name or not mobile:
                skipped += 1
                errors.append(
                    f"Row {row_number}: Type, Name and Mobile are required."
                )
                continue

            if customer_type not in valid_customer_types:
                skipped += 1
                errors.append(
                    f"Row {row_number}: Invalid customer type "
                    f"'{customer_type}'."
                )
                continue

            if len(name) > 255 or len(mobile) > 20:
                skipped += 1
                errors.append(
                    f"Row {row_number}: Name or Mobile exceeds "
                    "the allowed length."
                )
                continue

            if email:
                try:
                    validate_email(email)
                except ValidationError:
                    skipped += 1
                    errors.append(
                        f"Row {row_number}: Invalid email '{email}'."
                    )
                    continue

            if not payment_type:
                payment_type = "cash"

            if payment_type not in valid_payment_types:
                skipped += 1
                errors.append(
                    f"Row {row_number}: Payment must be cash or credit."
                )
                continue

            try:
                credit_limit = (
                    Decimal(credit_limit_text)
                    if credit_limit_text
                    else Decimal("0")
                )

                if (
                    not credit_limit.is_finite()
                    or credit_limit < 0
                    or credit_limit.as_tuple().exponent < -2
                    or credit_limit >= Decimal("10000000000000")
                ):
                    raise InvalidOperation

            except (InvalidOperation, ValueError):
                skipped += 1
                errors.append(
                    f"Row {row_number}: CreditLimit must be a "
                    "non-negative amount with at most two decimal places."
                )
                continue

            try:
                with transaction.atomic():

                    # Use the existing customer-code generator
                    customer_code = (
                        CustomerService.generate_customer_code()
                    )

                    # Protect against a code collision
                    if Customer.objects.filter(
                        customer_code=customer_code
                    ).exists():
                        raise ValueError(
                            f"Generated customer code {customer_code} "
                            "already exists. Please check the code generator."
                        )

                    # Avoid importing the same customer twice
                    existing_customer = Customer.objects.filter(
                        name__iexact=name,
                        mobile=mobile,
                    ).first()

                    if existing_customer:
                        skipped += 1
                        errors.append(
                            f"Row {row_number}: Customer already exists "
                            f"({existing_customer.customer_code} - "
                            f"{existing_customer.name})."
                        )
                        continue

                    Customer.objects.create(
                        customer_code=customer_code,
                        customer_type=customer_type,
                        name=name,
                        mobile=mobile,
                        email=email,
                        payment_type=payment_type,
                        credit_limit=credit_limit,
                    )

                imported += 1

            except Exception as e:
                skipped += 1
                errors.append(
                    f"Row {row_number}: Could not import {name}. {str(e)}"
                )

        if imported:
            messages.success(
                request,
                f"Import completed. {imported} customer(s) added; "
                f"{skipped} row(s) skipped."
            )
        else:
            messages.warning(
                request,
                f"No customers were imported. {skipped} row(s) skipped."
            )

        # Display up to five row-level errors
        for error in errors[:5]:
            messages.warning(request, error)

        if len(errors) > 5:
            messages.warning(
                request,
                f"{len(errors) - 5} additional row errors were not displayed."
            )

    except Exception:
        messages.error(
            request,
            "Unable to read the Excel file. Please check that it is a "
            "valid Excel file and try again."
        )

    finally:
        if workbook is not None and extension == ".xlsx":
            workbook.close()

    return redirect("sales_customers")


def customer_delete(request, pk):

    if request.method == "POST":

        customer = get_object_or_404(
            Customer,
            pk=pk
        )

        customer.delete()

        messages.success(
            request,
            "Customer deleted successfully."
        )

    return redirect("sales_customers")

# ==========================================================
# Ticket List
# ==========================================================

@login_required
def tickets(request):

    tickets = TicketService.list_tickets(request)

    context = {
        "tickets": tickets,
        "status": request.GET.get("status", "OPEN"),
        "search": request.GET.get("search", ""),
        "status_choices": Ticket.STATUS_CHOICES,
        "ticket_device_types": Ticket.DEVICE_TYPES,
    }

    return render(request, "tickets.html", context)


# ==========================================================
# Create Ticket
# ==========================================================

@login_required
def ticket_create(request):

    if request.method != "POST":
        return redirect("tickets")

    try:
        TicketService.create_ticket(request)

        messages.success(
            request,
            "Ticket created successfully."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("tickets")


# ==========================================================
# Update Ticket
# ==========================================================

@login_required
def ticket_update(request, pk):

    if request.method != "POST":
        return redirect("tickets")

    try:

        TicketService.update_ticket(
            request=request,
            ticket_id=pk,
        )

        messages.success(
            request,
            "Ticket updated successfully."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("tickets")


# ==========================================================
# Ticket Detail
# ==========================================================

@login_required
def ticket_detail(request, pk):

    context = TicketService.get_ticket_context(pk)

    return render(
        request,
        "ticket_detail.html",
        context,
    )


# ==========================================================
# Close Ticket
# ==========================================================

@login_required
def ticket_close(request, pk):

    if request.method != "POST":
        return redirect("tickets")

    try:

        TicketService.close_ticket(
            ticket_id=pk,
            user=request.user,
        )

        messages.success(
            request,
            "Ticket closed successfully."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("tickets")


# ==========================================================
# Delete Ticket
# ==========================================================

@login_required
def ticket_delete(request, pk):

    if request.method != "POST":
        return redirect("tickets")

    try:

        TicketService.delete_ticket(pk)

        messages.success(
            request,
            "Ticket deleted successfully."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("tickets")


# ==========================================================
# Print Ticket
# ==========================================================

@login_required
def ticket_print(request, pk):

    context = TicketService.get_print_context(pk)

    return render(
        request,
        "ticket_print.html",
        context,
    )


# ==========================================================
# Customer Lookup (AJAX)
# ==========================================================

@login_required
def customer_lookup(request):

    mobile = request.GET.get("mobile", "").strip()

    return JsonResponse(
        TicketService.customer_lookup(mobile)
    )


@login_required
def purchases_vendors(request):

    query = request.GET.get("q", "").strip()

    vendors = Vendor.objects.all()

    if query:
        vendors = vendors.filter(
            Q(vendor_code__icontains=query) |
            Q(name__icontains=query)
        )

    vendor_to_edit = None

    edit_id = request.GET.get("edit")

    if edit_id:
        vendor_to_edit = Vendor.objects.filter(
            pk=edit_id
        ).first()

    if request.method == "POST":

        vendor_id = request.POST.get("vendor_id")

        vendor_code = request.POST.get(
            "vendor_code", ""
        ).strip().lower()

        name = request.POST.get(
            "name", ""
        ).strip()

        pan = request.POST.get(
            "pan", ""
        ).strip()

        vat_number = request.POST.get(
            "vat_number", ""
        ).strip()

        mobile = request.POST.get(
            "mobile", ""
        ).strip()

        email = request.POST.get(
            "email", ""
        ).strip()

        address = request.POST.get(
            "address", ""
        ).strip()

        opening_balance = request.POST.get(
            "opening_balance", "0"
        ).strip()
        opening_balance_type = request.POST.get(
            "opening_balance_type",
            "DR"
        ).strip().upper()

        if not name:
            messages.error(
                request,
                "Vendor name is required."
            )

        else:

            if vendor_id:

                # =========================
                # UPDATE VENDOR
                # =========================

                vendor = Vendor.objects.get(
                    pk=vendor_id
                )

                vendor.name = name
                vendor.pan = pan
                vendor.vat_number = vat_number
                vendor.mobile = mobile
                vendor.email = email
                vendor.address = address

                if vendor_code:
                    vendor.vendor_code = vendor_code

                vendor.save()

                messages.success(
                    request,
                    "Vendor updated successfully."
                )

            else:

                # =========================
                # CREATE VENDOR
                # =========================
                opening_balance_amount = Decimal(opening_balance or "0")
                with transaction.atomic():

                    vendor_code = (
                        vendor_code
                        or generate_vendor_code()
                    )

                    vendor = Vendor.objects.create(
                        vendor_code=vendor_code,
                        name=name,
                        pan=pan,
                        vat_number=vat_number,
                        mobile=mobile,
                        email=email,
                        address=address,
                        opening_balance=opening_balance_amount
                    )

                    # =========================
                    # OPENING BALANCE LEDGER
                    # =========================

                    if opening_balance_amount != 0:

                        if opening_balance_type == "DR":
                            dr_amount = opening_balance_amount
                            cr_amount = Decimal("0.00")

                            closing_balance = opening_balance_amount

                        else:  # CR
                            dr_amount = Decimal("0.00")
                            cr_amount = opening_balance_amount

                            closing_balance = -opening_balance_amount

                        VendorLedger.objects.create(
                            vendor=vendor,

                            transaction_date=timezone.now().date(),

                            transaction_type="opening",

                            amount=opening_balance_amount,

                            mode=None,

                            remark="Opening Balance",

                            dr=dr_amount,

                            cr=cr_amount,

                            closing_balance=closing_balance,
                        )
                messages.success(
                    request,
                    "Vendor created successfully."
                )

        return redirect("purchases_vendors")

    context = {
        "vendors": vendors,
        "query": query,
        "vendor_to_edit": vendor_to_edit,
        "next_vendor_code": generate_vendor_code(),
    }

    return render(
        request,
        "purchases_vendors.html",
        context
    )

@login_required
def purchases_vendors_excel(request):
    if request.method != "POST":
        return redirect("purchases_vendors")

    excel_file = request.FILES.get("excel_file")

    if not excel_file:
        messages.error(request, "Please select an Excel file.")
        return redirect("purchases_vendors")

    if not excel_file.name.lower().endswith((".xlsx", ".xls")):
        messages.error(request, "Please upload an .xlsx or .xls file.")
        return redirect("purchases_vendors")

    if excel_file.size > 5 * 1024 * 1024:
        messages.error(request, "File size cannot exceed 5 MB.")
        return redirect("purchases_vendors")

    try:
        # Read Excel file
        if excel_file.name.lower().endswith(".xlsx"):
            workbook = load_workbook(
                excel_file,
                read_only=True,
                data_only=True
            )
            sheet = workbook.active
            rows = sheet.iter_rows(values_only=True)

        else:
            import xlrd

            workbook = xlrd.open_workbook(
                file_contents=excel_file.read()
            )
            sheet = workbook.sheet_by_index(0)
            rows = (
                sheet.row_values(row_index)
                for row_index in range(sheet.nrows)
            )

        rows = iter(rows)
        headers = next(rows, None)

        if not headers:
            messages.error(request, "The Excel file is empty.")
            return redirect("purchases_vendors")

        def normalize_header(value):
            return str(value or "").strip().lower().replace("_", " ")

        header_map = {
            normalize_header(value): index
            for index, value in enumerate(headers)
            if value is not None and str(value).strip()
        }

        # Accept common header variations
        aliases = {
            "vat": "vat number",
            "vat no": "vat number",
            "opening balance type": "opening balance type",
            "balance type": "opening balance type",
        }

        header_map = {
            aliases.get(header, header): index
            for header, index in header_map.items()
        }

        required_headers = [
            "name",
            "pan",
            "vat number",
            "mobile",
            "email",
            "address",
            "opening balance",
            "opening balance type",
        ]

        missing_headers = [
            header for header in required_headers
            if header not in header_map
        ]

        if missing_headers:
            messages.error(
                request,
                "Missing Excel columns: "
                + ", ".join(missing_headers)
            )
            return redirect("purchases_vendors")

        def get_value(row, column):
            index = header_map[column]

            if index >= len(row):
                return ""

            value = row[index]

            if value is None:
                return ""

            return str(value).strip()

        imported_count = 0
        errors = []

        for row_number, row in enumerate(rows, start=2):
            if not any(
                value is not None and str(value).strip()
                for value in row
            ):
                continue

            try:
                name = get_value(row, "name")
                pan = get_value(row, "pan")
                vat_number = get_value(row, "vat number")
                mobile = get_value(row, "mobile")
                email = get_value(row, "email")
                address = get_value(row, "address")

                opening_balance_text = get_value(
                    row, "opening balance"
                )

                opening_balance_type = (
                    get_value(row, "opening balance type").upper()
                    or "DR"
                )

                if not name:
                    raise ValueError("Vendor name is required.")

                if opening_balance_type not in ("DR", "CR"):
                    raise ValueError(
                        "Opening Balance Type must be DR or CR."
                    )

                try:
                    opening_balance = Decimal(
                        opening_balance_text or "0"
                    )
                except InvalidOperation:
                    raise ValueError(
                        "Opening Balance must be a valid number."
                    )

                if not opening_balance.is_finite():
                    raise ValueError(
                        "Opening Balance must be a valid number."
                    )

                if opening_balance < 0:
                    raise ValueError(
                        "Opening Balance cannot be negative."
                    )

                if opening_balance > Decimal("9999999999999.99"):
                    raise ValueError(
                        "Opening Balance is too large."
                    )

                with transaction.atomic():
                    vendor_code = generate_vendor_code()

                    vendor = Vendor.objects.create(
                        vendor_code=vendor_code,
                        name=name,
                        pan=pan,
                        vat_number=vat_number,
                        mobile=mobile,
                        email=email,
                        address=address,
                        opening_balance=opening_balance,
                    )

                    if opening_balance != 0:
                        if opening_balance_type == "DR":
                            dr_amount = opening_balance
                            cr_amount = Decimal("0.00")
                            closing_balance = opening_balance
                        else:
                            dr_amount = Decimal("0.00")
                            cr_amount = opening_balance
                            closing_balance = -opening_balance

                        VendorLedger.objects.create(
                            vendor=vendor,
                            transaction_date=timezone.localdate(),
                            transaction_type="opening",
                            amount=opening_balance,
                            mode=None,
                            remark="Opening Balance",
                            dr=dr_amount,
                            cr=cr_amount,
                            closing_balance=closing_balance,
                        )

                imported_count += 1

            except (ValueError, InvalidOperation, IntegrityError) as exc:
                errors.append(f"Row {row_number}: {exc}")

            except Exception as exc:
                errors.append(f"Row {row_number}: Import failed ({exc})")

        if imported_count:
            messages.success(
                request,
                f"Successfully imported {imported_count} vendor(s)."
            )

        if errors:
            messages.error(
                request,
                "Some rows could not be imported: "
                + " | ".join(errors[:5])
            )

            if len(errors) > 5:
                messages.error(
                    request,
                    f"And {len(errors) - 5} additional row(s) failed."
                )

        if imported_count == 0 and not errors:
            messages.warning(
                request,
                "No vendor records were found to import."
            )

    except Exception as exc:
        messages.error(
            request,
            f"Could not read the Excel file: {exc}"
        )

    finally:
        if "workbook" in locals() and excel_file.name.lower().endswith(".xlsx"):
            workbook.close()

    return redirect("purchases_vendors")

@login_required
def vendor_ledger_download(request, vendor_id):

    vendor = get_object_or_404(
        Vendor,
        pk=vendor_id
    )

    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    if not from_date or not to_date:
        messages.error(
            request,
            "Please select both dates."
        )
        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )

    try:
        from_date = datetime.strptime(
            from_date,
            "%Y-%m-%d"
        ).date()

        to_date = datetime.strptime(
            to_date,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        messages.error(
            request,
            "Invalid date."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )

    if from_date > to_date:

        messages.error(
            request,
            "From date cannot be after To date."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )

    # ==========================================
    # BALANCE BEFORE SELECTED PERIOD
    # ==========================================

    previous_transaction = VendorLedger.objects.filter(
        vendor=vendor,
        transaction_date__lt=from_date,
    ).order_by(
        "-transaction_date",
        "-id",
    ).first()

    opening_balance = (
        previous_transaction.closing_balance
        if previous_transaction
        else Decimal("0.00")
    )

    # ==========================================
    # TRANSACTIONS DURING SELECTED PERIOD
    # ==========================================

    transactions = VendorLedger.objects.filter(
        vendor=vendor,
        transaction_date__gte=from_date,
        transaction_date__lte=to_date,
    ).select_related(
        "against_invoice"
    ).order_by(
        "transaction_date",
        "id",
    )

    # ==========================================
    # CREATE EXCEL
    # ==========================================

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Vendor Ledger"

    # Vendor information
    worksheet["A1"] = "Vendor Ledger"
    worksheet["A1"].font = Font(
        bold=True,
        size=16
    )

    worksheet["A3"] = "Vendor"
    worksheet["B3"] = vendor.name

    worksheet["A4"] = "Vendor Code"
    worksheet["B4"] = vendor.vendor_code

    worksheet["A5"] = "Period"
    worksheet["B5"] = (
        f"{from_date.strftime('%d-%m-%Y')} "
        f"to "
        f"{to_date.strftime('%d-%m-%Y')}"
    )

    worksheet["A6"] = "Opening Balance"
    worksheet["B6"] = opening_balance

    # ==========================================
    # TABLE HEADER
    # ==========================================

    header_row = 8

    headers = [
        "Date",
        "Transaction",
        "Invoice",
        "Mode",
        "Remark",
        "Debit",
        "Credit",
        "Balance",
    ]

    for column, header in enumerate(headers, start=1):

        cell = worksheet.cell(
            row=header_row,
            column=column,
            value=header,
        )

        cell.font = Font(bold=True)
        cell.alignment = Alignment(
            horizontal="center"
        )

    # ==========================================
    # TRANSACTIONS
    # ==========================================

    row = header_row + 1

    running_balance = opening_balance

    for entry in transactions:

        running_balance += entry.cr
        running_balance -= entry.dr

        invoice_number = ""

        if entry.against_invoice:
            invoice_number = (
                entry.against_invoice.invoice_number
            )

        worksheet.cell(
            row=row,
            column=1,
            value=entry.transaction_date,
        )

        worksheet.cell(
            row=row,
            column=2,
            value=entry.get_transaction_type_display(),
        )

        worksheet.cell(
            row=row,
            column=3,
            value=invoice_number,
        )

        worksheet.cell(
            row=row,
            column=4,
            value=entry.get_mode_display()
            if entry.mode
            else "",
        )

        worksheet.cell(
            row=row,
            column=5,
            value=entry.remark or "",
        )

        worksheet.cell(
            row=row,
            column=6,
            value=entry.dr,
        )

        worksheet.cell(
            row=row,
            column=7,
            value=entry.cr,
        )

        worksheet.cell(
            row=row,
            column=8,
            value=running_balance,
        )

        row += 1

    # ==========================================
    # FINAL BALANCE
    # ==========================================

    worksheet.cell(
        row=row + 1,
        column=1,
        value="Closing Balance",
    )

    worksheet.cell(
        row=row + 1,
        column=1,
    ).font = Font(bold=True)

    worksheet.cell(
        row=row + 1,
        column=2,
        value=running_balance,
    )

    worksheet.cell(
        row=row + 1,
        column=2,
    ).font = Font(bold=True)

    # ==========================================
    # FORMATTING
    # ==========================================

    for row_cells in worksheet.iter_rows(
        min_row=header_row,
        max_row=row,
    ):

        for cell in row_cells:

            cell.alignment = Alignment(
                vertical="center"
            )

    # Date format
    for cell in worksheet["A"]:

        if hasattr(cell.value, "strftime"):
            cell.number_format = "DD-MM-YYYY"

    # Amount columns
    for column in ["B", "F", "G", "H"]:

        for cell in worksheet[column]:

            if isinstance(
                cell.value,
                (int, float, Decimal)
            ):
                cell.number_format = '#,##0.00'

    # Column widths
    worksheet.column_dimensions["A"].width = 15
    worksheet.column_dimensions["B"].width = 20
    worksheet.column_dimensions["C"].width = 20
    worksheet.column_dimensions["D"].width = 15
    worksheet.column_dimensions["E"].width = 35
    worksheet.column_dimensions["F"].width = 15
    worksheet.column_dimensions["G"].width = 15
    worksheet.column_dimensions["H"].width = 18

    # ==========================================
    # RESPONSE
    # ==========================================

    filename = (
        f"{vendor.vendor_code}_ledger_"
        f"{from_date.strftime('%Y%m%d')}_"
        f"{to_date.strftime('%Y%m%d')}.xlsx"
    )

    response = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        )
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    workbook.save(response)

    return response

@login_required
def vendor_ledger_email(request, vendor_id):

    vendor = get_object_or_404(
        Vendor,
        pk=vendor_id
    )


    if request.method != "POST":

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    recipient_email = request.POST.get(
        "email",
        ""
    ).strip()

    from_date_value = request.POST.get(
        "from_date",
        ""
    ).strip()

    to_date_value = request.POST.get(
        "to_date",
        ""
    ).strip()


    # ==========================================
    # Validate Email
    # ==========================================

    if not recipient_email:

        messages.error(
            request,
            "Vendor email address is required."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    # ==========================================
    # Validate Dates
    # ==========================================

    try:

        from_date = datetime.strptime(
            from_date_value,
            "%Y-%m-%d"
        ).date()

        to_date = datetime.strptime(
            to_date_value,
            "%Y-%m-%d"
        ).date()

    except ValueError:

        messages.error(
            request,
            "Please select valid dates."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    if from_date > to_date:

        messages.error(
            request,
            "From date cannot be after To date."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    # ==========================================
    # Generate Excel
    # ==========================================

    excel_data = VendorLedgerService.generate_excel(
        vendor=vendor,
        from_date=from_date,
        to_date=to_date,
    )


    filename = (
        f"{vendor.vendor_code}_ledger_"
        f"{from_date.strftime('%Y%m%d')}_"
        f"{to_date.strftime('%Y%m%d')}.xlsx"
    )


    # ==========================================
    # Send Email
    # ==========================================

    try:

        VendorLedgerEmailService.send_ledger(
            vendor=vendor,
            recipient_email=recipient_email,
            from_date=from_date,
            to_date=to_date,
            excel_file=excel_data,
            filename=filename,
        )

    except Exception as e:

        messages.error(
            request,
            f"Unable to send email: {str(e)}"
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    messages.success(
        request,
        f"Vendor ledger emailed successfully to {recipient_email}."
    )


    return redirect(
        "vendor_ledger",
        vendor_id=vendor.id
    )

@login_required
@transaction.atomic
def vendor_transaction_add(request, vendor_id):

    vendor = get_object_or_404(
        Vendor,
        pk=vendor_id
    )

    if request.method != "POST":
        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    # ==========================================
    # Get form values
    # ==========================================

    transaction_type = request.POST.get(
        "transaction_type",
        ""
    ).strip()

    transaction_date_value = request.POST.get(
        "transaction_date",
        ""
    ).strip()

    amount_value = request.POST.get(
        "amount",
        ""
    ).strip()

    mode = request.POST.get(
        "mode",
        ""
    ).strip()

    invoice_id = request.POST.get(
        "against_invoice",
        ""
    ).strip()

    reference = request.POST.get(
        "reference",
        ""
    ).strip()

    remark = request.POST.get(
        "remark",
        ""
    ).strip()

    attachment = request.FILES.get(
        "attachment"
    )


    # ==========================================
    # Validate transaction type
    # ==========================================

    if transaction_type not in [
        "payment",
        "return",
    ]:

        messages.error(
            request,
            "Invalid transaction type."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    # ==========================================
    # Validate date
    # ==========================================

    try:

        transaction_date = datetime.strptime(
            transaction_date_value,
            "%Y-%m-%d"
        ).date()

    except (ValueError, TypeError):

        messages.error(
            request,
            "Please enter a valid transaction date."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    # ==========================================
    # Validate amount
    # ==========================================

    try:

        amount = Decimal(amount_value)

    except (InvalidOperation, TypeError):

        messages.error(
            request,
            "Please enter a valid amount."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    if amount <= 0:

        messages.error(
            request,
            "Amount must be greater than zero."
        )

        return redirect(
            "vendor_ledger",
            vendor_id=vendor.id
        )


    # ==========================================
    # Payment mode
    # ==========================================

    if transaction_type == "payment":

        valid_modes = [
            "cash",
            "bank",
            "upi",
            "credit_card",
        ]

        if mode not in valid_modes:

            messages.error(
                request,
                "Please select a valid payment mode."
            )

            return redirect(
                "vendor_ledger",
                vendor_id=vendor.id
            )

    else:

        # Purchase return has no payment mode
        mode = None


    # ==========================================
    # Optional invoice
    # ==========================================

    against_invoice = None

    if invoice_id:

        against_invoice = PurchaseInvoice.objects.filter(
            pk=invoice_id,
            vendor=vendor,
        ).first()

        if not against_invoice:

            messages.error(
                request,
                "Selected invoice does not belong to this vendor."
            )

            return redirect(
                "vendor_ledger",
                vendor_id=vendor.id
            )


    # ==========================================
    # Accounting
    # ==========================================

    # Vendor payable:
    #
    # Purchase        -> CR
    # Payment         -> DR
    # Purchase Return -> DR

    dr = amount
    cr = Decimal("0.00")


    # ==========================================
    # Create ledger entry
    # ==========================================

    VendorLedger.objects.create(

        vendor=vendor,

        transaction_date=transaction_date,

        transaction_type=transaction_type,

        amount=amount,

        mode=mode,

        against_invoice=against_invoice,

        reference=reference,

        remark=remark,

        attachment=attachment,

        dr=dr,

        cr=cr,

    )


    # ==========================================
    # Recalculate running balances
    # ==========================================

    VendorLedgerService.recalculate(
        vendor
    )


    # ==========================================
    # Success message
    # ==========================================

    if transaction_type == "payment":

        messages.success(
            request,
            f"Payment of ₹{amount:,.2f} recorded successfully."
        )

    else:

        messages.success(
            request,
            f"Purchase return of ₹{amount:,.2f} recorded successfully."
        )


    return redirect(
        "vendor_ledger",
        vendor_id=vendor.id
    )

def purchases_invoices(request):
    invoices = PurchaseInvoice.objects.select_related("vendor").prefetch_related("items")

    if request.method == "POST":
        with transaction.atomic():
            vendor_id = request.POST.get("vendor")
            invoice_date_value = request.POST.get("invoice_date")
            credit_period = request.POST.get("credit_period", "0")
            narration = request.POST.get("narration", "").strip()
            invoice_number = request.POST.get("invoice_number", "").strip()
            pdf_file = request.FILES.get("pdf_file")

            if not vendor_id or not invoice_date_value:
                messages.error(request, "Please select a vendor and invoice date.")
                return redirect("purchases_invoices")

            invoice_date = datetime.strptime(invoice_date_value, "%Y-%m-%d").date()
            invoice_number = invoice_number or generate_invoice_number(invoice_date)
            vendor = Vendor.objects.get(pk=vendor_id)

            invoice = PurchaseInvoice.objects.create(
                invoice_number=invoice_number,
                vendor=vendor,
                invoice_date=invoice_date,
                credit_period=int(credit_period or 0),
                narration=narration,
            )

            if pdf_file:
                file_name = f"{uuid.uuid4().hex}_{pdf_file.name}"
                file_path = os.path.join(settings.MEDIA_ROOT, "purchases", file_name)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "wb+") as destination:
                    for chunk in pdf_file.chunks():
                        destination.write(chunk)
                invoice.pdf_path = os.path.join("purchases", file_name)
                invoice.save(update_fields=["pdf_path"])

            line_categories = request.POST.getlist("item_category[]")
            line_codes = request.POST.getlist("item_code[]")
            line_names = request.POST.getlist("item_name[]")
            line_specs = request.POST.getlist("item_specification[]")
            line_quantities = request.POST.getlist("quantity[]")
            line_rates = request.POST.getlist("rate[]")
            line_hsn = request.POST.getlist("hsn[]")

            line_totals = []
            for index, item_code in enumerate(line_codes):
                category = line_categories[index] if index < len(line_categories) else ""
                quantity = line_quantities[index] if index < len(line_quantities) else "1"
                rate = line_rates[index] if index < len(line_rates) else "0"
                if not category or not item_code or not quantity or not rate:
                    continue

                product = Product.objects.filter(category=category, item_code=item_code).first()
                if not product:
                    continue

                qty = int(quantity)
                rate_value = Decimal(rate)
                line_total = Decimal(qty) * rate_value
                line_totals.append(line_total)

                PurchaseLineItem.objects.create(
                    invoice=invoice,
                    item_name=product.item_name or line_names[index],
                    item_code=product.item_code,
                    specification=product.specification or line_specs[index],
                    quantity=qty,
                    rate=rate_value,
                    line_total=line_total,
                    hs_code=product.hs_code or line_hsn[index],
                )

                try:
                    InventoryService.purchase(
                        product=product,
                        quantity=qty,
                        unit_cost=rate_value,
                        document_number=invoice,
                        user=request.user,
                        remarks=f"Purchase from {invoice.vendor.name}",
                    )

                except Exception as e:
                    messages.error(request, str(e))
                    raise

            invoice.total_amount = sum(line_totals, Decimal("0"))
            invoice.grand_total = invoice.total_amount
            invoice.save(update_fields=["total_amount", "grand_total"])

            VendorLedger.objects.create(
                vendor=vendor,
                transaction_date=invoice.invoice_date,
                transaction_type="purchase",
                amount=invoice.grand_total,
                against_invoice=invoice,
                remark=f"Purchase Invoice {invoice.invoice_number}",
                cr=invoice.grand_total,
                dr=Decimal("0.00"),
            )

            VendorLedgerService.recalculate(vendor)

            messages.success(request, "Purchase invoice created successfully.")
            return redirect("purchases_invoices")

    products = Product.objects.all().order_by("category", "item_code")
    product_categories = sorted({product.category for product in products if product.category})
    products_json = []
    
    for product in products:

        try:
            available_stock = (
                product.stock.quantity_available
            )
        except InventoryStock.DoesNotExist:
            available_stock = 0

        products_json.append({
            "id": product.id,
            "category": product.category,
            "item_code": product.item_code,
            "item_name": product.item_name,
            "specification": product.specification,
            "selling_price": float(
                product.selling_price
            ),
            "available_stock": available_stock,
        })
    context = {
        "invoices": invoices,
        "vendors": Vendor.objects.all().order_by("name"),
        "products": products,
        "products_json": products_json,
        "product_categories": product_categories,
    }
    return render(request, "purchase_invoices.html", context)

@login_required
def vendor_ledger(request, vendor_id):

    vendor = get_object_or_404(
        Vendor,
        pk=vendor_id
    )

    transactions = VendorLedger.objects.filter(
        vendor=vendor
    ).select_related(
        "against_invoice"
    ).order_by(
        "-transaction_date",
        "-id"
    )[:20]

    latest_transaction = VendorLedger.objects.filter(
        vendor=vendor
    ).order_by(
        "-transaction_date",
        "-id"
    ).first()

    closing_balance = (
        latest_transaction.closing_balance
        if latest_transaction
        else Decimal("0.00")
    )

    # ==========================================
    # Process closing balance for display
    # ==========================================

    if closing_balance < 0:

        display_balance = abs(closing_balance)
        balance_type = "Dr"

    else:

        display_balance = closing_balance
        balance_type = "Cr"

    return render(
        request,
        "vendor_ledger.html",
        {
            "vendor": vendor,
            "transactions": transactions,
            "closing_balance": closing_balance,
            "display_balance": display_balance,
            "balance_type": balance_type,
        }
    )

def purchase_invoice_pdf(request, invoice_id):
    invoice = PurchaseInvoice.objects.filter(pk=invoice_id).first()
    if not invoice or not invoice.pdf_path:
        raise Http404("PDF not found")

    file_path = os.path.join(settings.MEDIA_ROOT, invoice.pdf_path)
    if not os.path.exists(file_path):
        raise Http404("PDF not found")

    return FileResponse(open(file_path, "rb"), content_type="application/pdf")




def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Login successful.")
            if user.is_superuser:
                return redirect("home")
            return redirect("login")

        messages.error(request, "Invalid email or password.")

    return render(request, "login.html")


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        business_name = request.POST.get("business_name", "").strip()
        mobile_number = request.POST.get("mobile_number", "").strip()
        password = request.POST.get("password", "")
        repeat_password = request.POST.get("repeat_password", "")

        if not all([name, email, business_name, mobile_number, password, repeat_password]):
            messages.error(request, "Please fill in all the required fields.")
        elif password != repeat_password:
            messages.error(request, "Passwords do not match.")
        elif len(password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
        elif not mobile_number.isdigit() or len(mobile_number) < 10:
            messages.error(request, "Please enter a valid mobile number.")
        else:
            try:
                validate_email(email)
            except ValidationError:
                messages.error(request, "Please enter a valid email address.")
                return render(request, "signup.html")

            if User.objects.filter(email=email).exists():
                messages.error(request, "A user with this email already exists.")
            else:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=name,
                )
                user.is_superuser = True
                user.is_staff = True
                user.save()
                UserProfile.objects.create(
                    user=user,
                    full_name=name,
                    business_name=business_name,
                    mobile_number=mobile_number,
                )
                messages.success(request, "Signup successful. Please login.")
                return redirect("login")

    return render(request, "signup.html")


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("login")

@login_required
def home(request):

    if not request.user.is_superuser:
        return redirect("login")

    product_count = Product.objects.count()
    customer_count = Customer.objects.count()
    vendor_count = Vendor.objects.count()

    total_stock_value = sum(
        stock.total_value
        for stock in InventoryStock.objects.all()
    )

    # Last 5 purchases
    recent_purchases = PurchaseInvoice.objects.select_related(
        "vendor"
    ).order_by("-invoice_date", "-id")[:5]

    # Last 5 sales
    recent_sales = SalesInvoice.objects.select_related(
        "customer"
    ).order_by("-invoice_date", "-id")[:5]

    # Top 10 low stock items
    low_stock_items = InventoryStock.objects.select_related(
        "product"
    ).filter(
        quantity_on_hand__lte=F("product__reorder_level")
    ).order_by(
        "quantity_on_hand"
    )[:10]

    return render(request, "index.html", {
        "product_count": product_count,
        "customer_count": customer_count,
        "vendor_count": vendor_count,
        "total_stock_value": total_stock_value,

        "recent_purchases": recent_purchases,
        "recent_sales": recent_sales,
        "low_stock_items": low_stock_items,
    })

def inventory_products_categories(request):

    if request.method == "POST":

        action = request.POST.get("action")

        try:
            with transaction.atomic():

                if action == "add_category":

                    category_name = request.POST.get(
                        "category_name", ""
                    ).strip()

                    hsn_code = request.POST.get(
                        "hsn_code", ""
                    ).strip()

                    description = request.POST.get(
                        "description", ""
                    ).strip()

                    if not category_name:
                        raise ValueError("Category name is required.")

                    if Product_Categories.objects.filter(
                        category_name__iexact=category_name
                    ).exists():
                        raise ValueError("This category already exists.")

                    Product_Categories.objects.create(
                        category_name=category_name,
                        hsn_code=hsn_code,
                        description=description,
                    )

                    messages.success(
                        request, "Category added successfully."
                    )

                elif action == "add_hsn":

                    category_name = request.POST.get(
                        "category_name", ""
                    ).strip()

                    hsn_code = request.POST.get(
                        "hsn_code", ""
                    ).strip()

                    description = request.POST.get(
                        "description", ""
                    ).strip()

                    if not hsn_code:
                        raise ValueError("HSN code is required.")

                    if not Product_Categories.objects.filter(
                        category_name=category_name
                    ).exists():
                        raise ValueError("Please select a valid category.")

                    Product_Categories.objects.create(
                        category_name=category_name,
                        hsn_code=hsn_code,
                        description=description,
                    )

                    messages.success(
                        request, "HSN code added successfully."
                    )

                elif action == "edit_hsn":

                    entry = get_object_or_404(
                        Product_Categories,
                        pk=request.POST.get("entry_id"),
                    )

                    category_name = request.POST.get(
                        "category_name", ""
                    ).strip()

                    hsn_code = request.POST.get(
                        "hsn_code", ""
                    ).strip()

                    description = request.POST.get(
                        "description", ""
                    ).strip()

                    if not category_name or not hsn_code:
                        raise ValueError(
                            "Category name and HSN code are required."
                        )

                    # If this is a new category name, create the category's
                    # first row; otherwise use the selected existing category.
                    entry.category_name = category_name
                    entry.hsn_code = hsn_code
                    entry.description = description
                    entry.save()

                    messages.success(
                        request, "HSN entry updated successfully."
                    )

                else:
                    raise ValueError("Invalid action.")

        except Exception as e:
            messages.error(request, str(e))

        return redirect("inventory_products_categories")

    entries = Product_Categories.objects.all().order_by(
        "category_name", "hsn_code"
    )

    categories = sorted(
        set(entries.values_list("category_name", flat=True)),
        key=str.casefold,
    )

    context = {
        "page_title": "Product Categories & HSN Codes",
        "entries": entries,
        "categories": categories,
    }

    return render(
        request,
        "product_categories.html",
        context,
    )


@login_required
def inventory_products_categories_excel(request):

    if request.method != "POST":
        return redirect("inventory_products_categories")

    excel_file = request.FILES.get("excel_file")

    if not excel_file:
        messages.error(request, "Please select an Excel file.")
        return redirect("inventory_products_categories")

    extension = os.path.splitext(excel_file.name)[1].lower()

    if extension not in [".xlsx", ".xls"]:
        messages.error(
            request,
            "Invalid file format. Please upload an .xlsx or .xls file."
        )
        return redirect("inventory_products_categories")

    # Limit upload size to 5 MB
    if excel_file.size > 5 * 1024 * 1024:
        messages.error(request, "File size must not exceed 5 MB.")
        return redirect("inventory_products_categories")

    try:
        # Read Excel data
        if extension == ".xlsx":
            workbook = load_workbook(
                excel_file,
                read_only=True,
                data_only=True
            )
            worksheet = workbook.active
            rows = worksheet.iter_rows(values_only=True)

        else:
            workbook = xlrd.open_workbook(file_contents=excel_file.read())
            worksheet = workbook.sheet_by_index(0)
            rows = (
                worksheet.row_values(row_index)
                for row_index in range(worksheet.nrows)
            )

        # Read the first row as column headers
        headers = next(rows, None)

        if not headers:
            messages.error(request, "The Excel file is empty.")
            return redirect("inventory_products_categories")

        # Normalize headers: Category, CATEGORY and category are equivalent
        normalized_headers = [
            str(header).strip().lower() if header is not None else ""
            for header in headers
        ]

        required_columns = ["category", "description", "hsn"]

        missing_columns = [
            column
            for column in required_columns
            if column not in normalized_headers
        ]

        if missing_columns:
            messages.error(
                request,
                "Missing required columns: "
                + ", ".join(missing_columns)
                + ". Required columns are: category, description, hsn."
            )
            return redirect("inventory_products_categories")

        # Find each column's position
        category_index = normalized_headers.index("category")
        description_index = normalized_headers.index("description")
        hsn_index = normalized_headers.index("hsn")

        imported = 0
        skipped = 0

        with transaction.atomic():

            for row_number, row in enumerate(rows, start=2):

                # Ignore completely empty rows
                if not row or all(
                    value is None or str(value).strip() == ""
                    for value in row
                ):
                    continue

                # Safely read values from the row
                category_name = (
                    str(row[category_index]).strip()
                    if category_index < len(row)
                    and row[category_index] is not None
                    else ""
                )

                description = (
                    str(row[description_index]).strip()
                    if description_index < len(row)
                    and row[description_index] is not None
                    else ""
                )

                hsn_value = (
                    row[hsn_index]
                    if hsn_index < len(row)
                    else ""
                )

                # Keep numeric HSN values as integer strings where possible.
                # Excel cells formatted as text retain leading zeros.
                if isinstance(hsn_value, float) and hsn_value.is_integer():
                    hsn_code = str(int(hsn_value))
                else:
                    hsn_code = (
                        str(hsn_value).strip()
                        if hsn_value is not None
                        else ""
                    )

                if not category_name or not hsn_code:
                    skipped += 1
                    continue

                # Prevent duplicate category + HSN combinations.
                # Existing records are left unchanged.
                _, created = Product_Categories.objects.get_or_create(
                    category_name=category_name,
                    hsn_code=hsn_code,
                    defaults={
                        "description": description,
                    }
                )

                if created:
                    imported += 1
                else:
                    skipped += 1

        messages.success(
            request,
            f"Import completed. Added: {imported}. "
            f"Skipped: {skipped} (empty required fields or existing entries)."
        )

    except Exception as e:
        messages.error(
            request,
            f"Could not process the Excel file. "
            f"Please check the file and try again. Details: {e}"
        )

    finally:
        if extension == ".xlsx" and "workbook" in locals():
            workbook.close()

    return redirect("inventory_products_categories")



def inventory_products(request):
    """
    Product Listing + Create Product
    """

    search = request.GET.get("search", "").strip()

    if request.method == "POST":

        form = ProductForm(request.POST)

        if form.is_valid():

            try:
                with transaction.atomic():

                    opening_qty = form.cleaned_data.get("opening_qty") or 0
                    purchase_price = form.cleaned_data.get("purchase_price") or 0
                    
                    product = form.save()

                    product.item_code = generate_item_code(product.category)
                    product.save()

                    stock, created = InventoryStock.objects.get_or_create(
                        product=product
                    )

                    stock.quantity_on_hand = opening_qty
                    stock.last_cost = purchase_price
                    stock.save()

                messages.success(
                    request,
                    f"Product added successfully. Item Code: {product.item_code}"
                )

                return redirect("inventory_products")

            except Exception as e:
                messages.error(request, str(e))

        else:
            print("PRODUCT FORM ERRORS:", form.errors)

            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(
                        request,
                        f"{field}: {error}"
                    )

    else:

        form = ProductForm()

    products = Product.objects.all()

    if search:

        products = products.filter(
            Q(item_code__icontains=search)
            | Q(item_name__icontains=search)
            | Q(category__icontains=search)
            | Q(hs_code__icontains=search)
        )

    paginator = Paginator(products, 20)

    products_page = paginator.get_page(
        request.GET.get("page")
    )

    context = {

        "page_title": "Products",

        "products": products_page,

        "search": search,

        "category_hsn": CATEGORY_HSN,

        "form": form,

    }

    return render(
        request,
        "products.html",
        context,
    )


@login_required

@login_required
def inventory_products_excel(request):

    if request.method != "POST":
        return redirect("inventory_products")

    excel_file = request.FILES.get("excel_file")

    if not excel_file:
        messages.error(request, "Please select an Excel file.")
        return redirect("inventory_products")

    extension = os.path.splitext(excel_file.name)[1].lower()

    if extension not in [".xlsx", ".xls"]:
        messages.error(
            request,
            "Invalid file format. Please upload an .xlsx or .xls file."
        )
        return redirect("inventory_products")

    if excel_file.size > 5 * 1024 * 1024:
        messages.error(request, "File size must not exceed 5 MB.")
        return redirect("inventory_products")

    workbook = None

    try:
        # Read Excel file
        if extension == ".xlsx":
            workbook = load_workbook(
                excel_file,
                read_only=True,
                data_only=True
            )
            worksheet = workbook.active
            rows = worksheet.iter_rows(values_only=True)

        else:
            workbook = xlrd.open_workbook(
                file_contents=excel_file.read()
            )
            worksheet = workbook.sheet_by_index(0)

            rows = (
                worksheet.row_values(i)
                for i in range(worksheet.nrows)
            )

        headers = next(rows, None)

        if not headers:
            messages.error(request, "The Excel file is empty.")
            return redirect("inventory_products")

        # Normalize headers: lowercase and remove extra spaces
        normalized_headers = [
            " ".join(str(header).strip().lower().split())
            if header is not None else ""
            for header in headers
        ]

        # Support common alternative header names
        header_aliases = {
            "hsn code": "hsn",
            "unit of measure": "unit",
            "whole sale quantity": "whole sale qty",
            "wholesale price": "whole sale price",
            "wholesale qty": "whole sale qty",
            "opening stock": "opening qty",
            "opening quantity": "opening qty",
            "reorder": "reorder level",
        }

        normalized_headers = [
            header_aliases.get(header, header)
            for header in normalized_headers
        ]

        required_columns = [
            "item name",
            "brand",
            "model number",
            "category",
            "hsn",
            "specification",
            "stock tracking",
            "selling price",
            "whole sale price",
            "whole sale qty",
            "unit",
            "reorder level",
            "opening qty",
            "purchase price",
        ]

        missing_columns = [
            column for column in required_columns
            if column not in normalized_headers
        ]

        if missing_columns:
            messages.error(
                request,
                "Missing Excel columns: "
                + ", ".join(missing_columns)
                + ". Please use the complete product Excel template."
            )
            return redirect("inventory_products")

        # Get the first position of each header
        column_index = {
            name: normalized_headers.index(name)
            for name in required_columns
        }

        def cell_value(row, column_name):
            index = column_index[column_name]

            if index >= len(row) or row[index] is None:
                return ""

            value = row[index]

            if isinstance(value, float) and value.is_integer():
                value = int(value)

            return str(value).strip()

        def decimal_value(value, field_name, row_number):
            if value == "":
                return Decimal("0.00")

            try:
                result = Decimal(value)

                if not result.is_finite() or result < 0:
                    raise ValueError

                return result

            except Exception:
                raise ValueError(
                    f"Row {row_number}: {field_name} must be "
                    "a valid non-negative number."
                )

        def whole_number(value, field_name, row_number, default=0):
            if value == "":
                return default

            try:
                number = Decimal(value)

                if (
                    not number.is_finite()
                    or number < 0
                    or number != number.to_integral_value()
                ):
                    raise ValueError

                return int(number)

            except Exception:
                raise ValueError(
                    f"Row {row_number}: {field_name} must be "
                    "a non-negative whole number."
                )

        def boolean_value(value, row_number):
            value = value.strip().lower()

            if value == "":
                return False

            if value in ("true", "yes", "1"):
                return True

            if value in ("false", "no", "0"):
                return False

            raise ValueError(
                f"Row {row_number}: Stock Tracking must be "
                "True or False."
            )

        imported = 0
        skipped = 0
        errors = []

        with transaction.atomic():

            for row_number, row in enumerate(rows, start=2):

                # Ignore empty rows
                if not row or all(
                    value is None or str(value).strip() == ""
                    for value in row
                ):
                    continue

                item_name = cell_value(row, "item name")
                brand = cell_value(row, "brand")
                model_number = cell_value(row, "model number")
                category = cell_value(row, "category")
                hsn = cell_value(row, "hsn")
                specification = cell_value(row, "specification")
                unit = cell_value(row, "unit") or "pcs"

                try:
                    # Required values
                    if not item_name or not category:
                        raise ValueError(
                            f"Row {row_number}: Item Name and Category "
                            "are required."
                        )

                    # Validate numeric fields
                    selling_price = decimal_value(
                        cell_value(row, "selling price"),
                        "Selling Price",
                        row_number
                    )

                    whole_sale_price = decimal_value(
                        cell_value(row, "whole sale price"),
                        "Whole Sale Price",
                        row_number
                    )

                    purchase_price = decimal_value(
                        cell_value(row, "purchase price"),
                        "Purchase Price",
                        row_number
                    )

                    whole_sale_qty = whole_number(
                        cell_value(row, "whole sale qty"),
                        "Whole Sale Qty",
                        row_number
                    )

                    reorder_level = whole_number(
                        cell_value(row, "reorder level"),
                        "Reorder Level",
                        row_number,
                        default=10
                    )

                    opening_qty = whole_number(
                        cell_value(row, "opening qty"),
                        "Opening Qty",
                        row_number
                    )

                    stock_tracking = boolean_value(
                        cell_value(row, "stock tracking"),
                        row_number
                    )

                    with transaction.atomic():

                        # Generate item code using your existing function
                        item_code = generate_item_code(category)

                        # Create product
                        product = Product.objects.create(
                            item_code=item_code,
                            item_name=item_name,
                            brand=brand,
                            model_number=model_number,
                            category=category,
                            hs_code=hsn,
                            specification=specification,
                            stock_tracking=stock_tracking,
                            selling_price=selling_price,
                            whole_sale_price=whole_sale_price,
                            whole_sale_qty=whole_sale_qty,
                            unit_of_measure=unit,
                            reorder_level=reorder_level,
                        )

                        # Initialize stock and purchase cost
                        InventoryStock.objects.create(
                            product=product,
                            quantity_on_hand=opening_qty,
                            last_cost=purchase_price,
                        )

                    imported += 1

                except Exception as e:
                    skipped += 1
                    errors.append(
                        f"Row {row_number}: Could not import "
                        f"{item_name or '(unnamed product)'}. {str(e)}"
                    )

        if imported:
            messages.success(
                request,
                f"Import completed. {imported} product(s) added; "
                f"{skipped} row(s) skipped."
            )
        else:
            messages.warning(
                request,
                f"No products were imported. {skipped} row(s) skipped."
            )

        for error in errors[:5]:
            messages.warning(request, error)

        if len(errors) > 5:
            messages.warning(
                request,
                f"{len(errors) - 5} additional row errors "
                "were not displayed."
            )

    except Exception:
        messages.error(
            request,
            "Unable to read the Excel file. Please check that it is a "
            "valid Excel file and try again."
        )

    finally:
        if workbook is not None and extension == ".xlsx":
            workbook.close()

    return redirect("inventory_products")





@require_POST
def product_update(request, pk):
    """
    Update Existing Product
    """

    product = get_object_or_404(
        Product,
        pk=pk
    )

    form = ProductForm(
        request.POST,
        instance=product
    )

    if form.is_valid():

        form.save()

        messages.success(
            request,
            "Product updated successfully."
        )

    else:

        messages.error(
            request,
            "Unable to update product."
        )

    return redirect("inventory_products")


@require_POST
def product_delete(request, pk):
    """
    Delete Product
    """

    product = get_object_or_404(
        Product,
        pk=pk
    )

    try:

        product.delete()

        messages.success(
            request,
            "Product deleted successfully."
        )

    except Exception:

        messages.error(
            request,
            "Unable to delete product."
        )

    return redirect("inventory_products")




def inventory_stock(request):
    """
    Inventory Stock Dashboard
    """

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "")

    # ----------------------------------------------------
    # Ensure every product has a stock record
    # ----------------------------------------------------

    for product in Product.objects.all():

        InventoryStock.objects.get_or_create(
            product=product,
            defaults={
                "quantity_on_hand": 0,
                "quantity_reserved": 0,
                "last_cost": Decimal("0.00"),
            },
        )

    # ----------------------------------------------------
    # Fetch Stock
    # ----------------------------------------------------

    stocks = (
        InventoryStock.objects
        .select_related("product")
        .order_by("product__item_code")
    )

    # ----------------------------------------------------
    # Search
    # ----------------------------------------------------

    if search:

        stocks = stocks.filter(

            Q(product__item_code__icontains=search) |
            Q(product__item_name__icontains=search) |
            Q(product__category__icontains=search)

        )

    # ----------------------------------------------------
    # Build Dashboard Data
    # ----------------------------------------------------

    stock_rows = []

    healthy = 0
    low = 0
    critical = 0

    total_inventory_value = Decimal("0.00")

    for stock in stocks:

        available = stock.quantity_on_hand - stock.quantity_reserved

        value = stock.quantity_on_hand * stock.last_cost

        total_inventory_value += value

        # -----------------------
        # Status
        # -----------------------

        if stock.quantity_on_hand < 2:

            stock_status = "Critical"

            badge = "danger"

            row = "table-danger"

            critical += 1

        elif stock.quantity_on_hand <= stock.product.reorder_level:

            stock_status = "Low"

            badge = "warning"

            row = "table-warning"

            low += 1

        else:

            stock_status = "Healthy"

            badge = "success"

            row = "table-success"

            healthy += 1

        stock_rows.append({

            "id": stock.id,

            "product": stock.product,

            "on_hand": stock.quantity_on_hand,

            "reserved": stock.quantity_reserved,

            "available": available,

            "last_cost": stock.last_cost,

            "value": value,

            "status": stock_status,

            "badge": badge,

            "row_class": row,

            "updated_at": stock.updated_at,

        })

    # ----------------------------------------------------
    # Status Filter
    # ----------------------------------------------------

    if status:

        stock_rows = [

            row for row in stock_rows

            if row["status"].lower() == status.lower()

        ]

    # ----------------------------------------------------
    # Pagination
    # ----------------------------------------------------

    paginator = Paginator(stock_rows, 20)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    # ----------------------------------------------------
    # Context
    # ----------------------------------------------------

    context = {

        "page_title": "Stock Summary",

        "page_obj": page_obj,

        "search": search,

        "status": status,

        "total_products": Product.objects.count(),

        "healthy_count": healthy,

        "low_count": low,

        "critical_count": critical,

        "inventory_value": total_inventory_value,

    }

    return render(
        request,
        "stock_summary.html",
        context,
    )



def inventory_movements(request):
    """
    Stock Movement Ledger
    """

    # =====================================================
    # Filters
    # =====================================================

    search = request.GET.get("search", "").strip()
    movement_type = request.GET.get("movement_type", "").strip()
    product_id = request.GET.get("product", "").strip()
    from_date = request.GET.get("from_date", "").strip()
    to_date = request.GET.get("to_date", "").strip()

    # =====================================================
    # Base Query
    # =====================================================

    all_movements = (
        InventoryMovement.objects
        .select_related("product", "created_by")
        .order_by("-movement_date", "-id")
    )

    # =====================================================
    # Dashboard (Always Overall)
    # =====================================================

    today = timezone.localdate()

    today_movements = all_movements.filter(
        movement_date__date=today
    )

    incoming_qty = (
        today_movements.filter(
            movement_type__in=InventoryMovement.INCOMING_TYPES
        ).aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    outgoing_qty = (
        today_movements.filter(
            movement_type__in=InventoryMovement.OUTGOING_TYPES
        ).aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    today_count = today_movements.count()

    # =====================================================
    # Filtered Ledger
    # =====================================================

    movements = all_movements

    if search:

        movements = movements.filter(

            Q(product__item_code__icontains=search)

            |

            Q(product__item_name__icontains=search)

            |

            Q(document_number__icontains=search)

            |

            Q(remarks__icontains=search)

        )

    if movement_type:

        movements = movements.filter(

            movement_type=movement_type

        )

    if product_id:

        movements = movements.filter(

            product_id=product_id

        )

    if from_date:

        movements = movements.filter(

            movement_date__date__gte=from_date

        )

    if to_date:

        movements = movements.filter(

            movement_date__date__lte=to_date

        )

    # =====================================================
    # Pagination
    # =====================================================

    paginator = Paginator(

        movements,

        25,

    )

    page_obj = paginator.get_page(

        request.GET.get("page")

    )

    # =====================================================
    # Context
    # =====================================================

    context = {

        "page_title": "Stock Movements",

        "page_obj": page_obj,

        "products": Product.objects.order_by("item_name"),

        "movement_choices": InventoryMovement.MOVEMENT_TYPES,

        "search": search,

        "movement_type": movement_type,

        "product_id": product_id,

        "from_date": from_date,

        "to_date": to_date,

        # Dashboard

        "today_count": today_count,

        "incoming_qty": incoming_qty,

        "outgoing_qty": outgoing_qty,

        "net_qty": incoming_qty - outgoing_qty,

    }

    return render(
        request,
        "stock_movements.html",
        context,
    )


# ==========================================================
# Service Report List
# ==========================================================

@login_required
def service_reports(request):

    context = {

        "pending_tickets": ServiceReportService.pending_tickets(request),

        "reports": ServiceReportService.list_reports(request),

        "search": request.GET.get("search", ""),

        "ticket_status": request.GET.get("ticket_status", "OPEN"),

        "report_status": request.GET.get("report_status", "ALL"),

        "status_choices": ServiceReport.STATUS_CHOICES,

        "products": Product.objects.order_by(
            "category",
            "item_name",
        ),

    }

    return render(
        request,
        "service_reports.html",
        context,
    )


# ==========================================================
# Create
# ==========================================================

@login_required
def service_report_create(request, ticket_id):

    ticket = get_object_or_404(
        Ticket.objects.select_related("customer"),
        pk=ticket_id,
    )

    if request.method == "POST":

        ServiceReportService.create_report(
            request=request,
            ticket=ticket,
        )

        messages.success(
            request,
            "Service report created successfully."
        )

        return redirect("service_reports")
    products_json = []

    for product in Product.objects.select_related("stock").order_by(
        "category",
        "item_name",
    ):

        products_json.append({
            "id": product.id,
            "category": product.category,
            "item_name": product.item_name,
            "item_code": product.item_code,
            "specification": product.specification,
            "selling_price": float(product.selling_price),
            "available_stock": (
                product.stock.quantity_available
                if hasattr(product, "stock") else 0
            ),
        })

    product_categories = sorted({
        product.category
        for product in Product.objects.all()
        if product.category
    })

    context = {

        "ticket": ticket,

        "products": Product.objects.order_by(
            "category",
            "item_name",
        ),
        "product_categories": product_categories,
        "products_json": json.dumps(products_json),
    }

    return render(
        request,
        "service_report_form.html",
        context,
    )


@login_required
def service_report_edit(request, pk):

    report = get_object_or_404(
        ServiceReport.objects.select_related(
            "ticket",
            "ticket__customer",
        ),
        pk=pk,
    )

    if request.method == "POST":

        ServiceReportService.update_report(
            request=request,
            report_id=pk,
        )

        messages.success(
            request,
            "Service report updated successfully."
        )

        return redirect("service_reports")
    products_json = []

    for product in Product.objects.select_related("stock").order_by(
        "category",
        "item_name",
    ):

        products_json.append({
            "id": product.id,
            "category": product.category,
            "item_name": product.item_name,
            "item_code": product.item_code,
            "specification": product.specification,
            "selling_price": float(product.selling_price),
            "available_stock": (
                product.stock.quantity_available
                if hasattr(product, "stock") else 0
            ),
        })

    product_categories = sorted({
        product.category
        for product in Product.objects.all()
        if product.category
    })

    context = {

        "report": report,

        "ticket": report.ticket,

        "products": Product.objects.order_by(
            "category",
            "item_name",
        ),
        "product_categories": product_categories,
        "products_json": json.dumps(products_json),
    }

    return render(
        request,
        "service_report_form.html",
        context,
    )

# ==========================================================
# Update
# ==========================================================

@login_required
def service_report_update(request, pk):

    if request.method != "POST":
        return redirect("service_reports")

    try:

        ServiceReportService.update_report(
            request=request,
            report_id=pk,
        )

        messages.success(
            request,
            "Service report updated successfully."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("service_reports")


# ==========================================================
# Detail
# ==========================================================

@login_required
def service_report_detail(request, pk):

    context = ServiceReportService.get_report_context(pk)

    return render(
        request,
        "service_report_detail.html",
        context,
    )


# ==========================================================
# Submit
# ==========================================================

@login_required
def service_report_submit(request, pk):

    if request.method != "POST":
        return redirect("service_reports")

    try:

        ServiceReportService.submit_report(pk)

        messages.success(
            request,
            "Service report submitted successfully."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("service_reports")


# ==========================================================
# Approve
# ==========================================================

@login_required
def service_report_approve(request, pk):

    if request.method != "POST":
        return redirect("service_reports")

    try:

        ServiceReportService.approve_report(
            report_id=pk,
            user=request.user,
        )

        messages.success(
            request,
            "Service report approved successfully."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("service_reports")


# ==========================================================
# Reject
# ==========================================================

@login_required
def service_report_reject(request, pk):

    if request.method != "POST":
        return redirect("service_reports")

    try:

        ServiceReportService.reject_report(pk)

        messages.success(
            request,
            "Service report rejected successfully."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("service_reports")


# ==========================================================
# Complete
# ==========================================================

@login_required
def service_report_complete(request, pk):

    if request.method != "POST":
        return redirect("service_reports")

    try:

        ServiceReportService.complete_report(pk)

        messages.success(
            request,
            "Service report marked as completed."
        )

    except Exception as e:

        messages.error(
            request,
            str(e)
        )

    return redirect("service_reports")

# ==========================================================
# SALES INVOICES
# ==========================================================

@login_required
def sales_invoices(request):

    invoices = (
        SalesInvoice.objects
        .select_related(
            "customer",
            "service_report",
            "service_report__ticket",
        )
        .prefetch_related("items")
        .order_by("-invoice_date", "-id")
    )

    search = request.GET.get("search", "").strip()
    sale_type = request.GET.get("sale_type", "ALL")
    status = request.GET.get("status", "ALL")

    if search:

        invoices = invoices.filter(
            Q(invoice_number__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(customer__mobile__icontains=search)
        )

    if sale_type != "ALL":
        invoices = invoices.filter(
            sale_type=sale_type
        )

    if status != "ALL":
        invoices = invoices.filter(
            status=status
        )

    context = {
        "invoices": invoices,
        "search": search,
        "sale_type": sale_type,
        "status": status,
        "sale_type_choices": SalesInvoice.SALE_TYPE_CHOICES,
        "status_choices": SalesInvoice.STATUS_CHOICES,
    }

    return render(
        request,
        "sales_invoices.html",
        context,
    )

@login_required
def sales_invoice_create(request):

    customers = Customer.objects.order_by("name")

    products = (
        Product.objects
        .select_related("stock")
        .order_by(
            "category",
            "item_name",
        )
    )

    approved_reports = (
        ServiceReport.objects
        .filter(
            status=ServiceReport.APPROVED,
            sales_invoice__isnull=True,
        )
        .select_related(
            "ticket",
            "ticket__customer",
            "technician",
        )
        .prefetch_related(
            "items",
            "items__product",
        )
        .order_by("-created_at")
    )

    products_json = []

    for product in products:

        try:
            available_stock = (
                product.stock.quantity_available
            )
        except InventoryStock.DoesNotExist:
            available_stock = 0

        products_json.append({
            "id": product.id,
            "category": product.category,
            "item_code": product.item_code,
            "item_name": product.item_name,
            "specification": product.specification,
            "selling_price": float(
                product.selling_price
            ),
            "available_stock": available_stock,
        })

    context = {
        "customers": customers,

        "products": products,

        "products_json": products_json,

        "approved_reports": approved_reports,

        "sale_type_choices": (
            SalesInvoice.SALE_TYPE_CHOICES
        ),
    }

    return render(
        request,
        "sales_invoice_form.html",
        context,
    )

@login_required
def sales_invoice_create_save(request):

    if request.method != "POST":
        return redirect("sales_invoice_create")

    sale_type = request.POST.get(
        "sale_type",
        "DIRECT",
    ).upper()

    try:

        # ==================================================
        # DIRECT SALE
        # ==================================================

        if sale_type == "DIRECT":

            customer_id = request.POST.get(
                "customer"
            )

            if not customer_id:
                raise ValueError(
                    "Please select a customer."
                )

            customer = get_object_or_404(
                Customer,
                pk=customer_id,
            )

            invoice = SaleService.create_direct_sale(
                customer=customer,
                request=request,
                user=request.user,
            )

        # ==================================================
        # REPAIR SALE
        # ==================================================

        elif sale_type == "REPAIR":

            service_report_id = request.POST.get(
                "service_report"
            )

            if not service_report_id:
                raise ValueError(
                    "Please select a service report."
                )

            service_report = get_object_or_404(
                ServiceReport.objects.select_related(
                    "ticket",
                    "ticket__customer",
                ),
                pk=service_report_id,
            )

            invoice = SaleService.create_repair_sale(
                service_report=service_report,
                request=request,
                user=request.user,
            )

        # ==================================================
        # SALE RETURN
        # ==================================================

        elif sale_type == "RETURN":

            customer_id = request.POST.get(
                "customer"
            )

            if not customer_id:
                raise ValueError(
                    "Please select a customer."
                )

            customer = get_object_or_404(
                Customer,
                pk=customer_id,
            )

            invoice = SaleService.create_sale_return(
                customer=customer,
                request=request,
                user=request.user,
            )

        else:

            raise ValueError(
                "Invalid sale type."
            )

        messages.success(
            request,
            (
                f"Sales invoice "
                f"{invoice.invoice_number} "
                f"created successfully."
            ),
        )

        return redirect(
            "sales_invoice_detail",
            invoice_id=invoice.id,
        )

    except Exception as e:

        messages.error(
            request,
            str(e),
        )

        return redirect(
            "sales_invoice_create"
        )


@login_required
def sales_invoice_detail(
    request,
    invoice_id,
):

    invoice = get_object_or_404(
        SalesInvoice.objects
        .select_related(
            "customer",
            "service_report",
            "service_report__ticket",
            "service_report__ticket__customer",
            "service_report__technician",
        )
        .prefetch_related(
            "items",
            "service_report__items",
            "service_report__items__product",
        ),
        pk=invoice_id,
    )

    context = {
        "invoice": invoice,
    }

    return render(
        request,
        "sales_invoice_detail.html",
        context,
    )

@login_required
def sales_service_report_data(
    request,
    report_id,
):

    report = get_object_or_404(
        ServiceReport.objects
        .select_related(
            "ticket",
            "ticket__customer",
            "technician",
        )
        .prefetch_related(
            "items",
            "items__product",
        ),
        pk=report_id,
        status=ServiceReport.APPROVED,
    )

    if SalesInvoice.objects.filter(
        service_report=report
    ).exists():

        return JsonResponse(
            {
                "success": False,
                "message": (
                    "This service report has "
                    "already been invoiced."
                ),
            },
            status=400,
        )

    items = []

    for item in report.items.all():

        items.append({
            "product_id": item.product_id,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "specification": item.specification,
            "quantity": item.quantity,
            "rate": float(
                item.estimated_rate
            ),
            "line_total": float(
                item.line_total
            ),
            "remarks": item.remarks,
        })

    return JsonResponse({
        "success": True,

        "report": {
            "id": report.id,
            "report_number": report.report_number,

            "ticket_id": report.ticket_id,

            "ticket_number": (
                report.ticket.ticket_number
            ),

            "customer_id": (
                report.ticket.customer_id
            ),

            "customer_name": (
                report.ticket.customer.name
            ),

            "customer_mobile": (
                report.ticket.customer.mobile
            ),

            "inspection_notes": (
                report.inspection_notes
            ),

            "problem_found": (
                report.problem_found
            ),

            "repair_solution": (
                report.repair_solution
            ),

            "labor_charge": float(
                report.labor_charge
            ),

            "other_charge": float(
                report.other_charge
            ),

            "estimated_total": float(
                report.estimated_total
            ),

            "items": items,
        },
    })

@login_required
def sales_customer_search(request):

    search = request.GET.get(
        "search",
        "",
    ).strip()

    customers = Customer.objects.all()

    if search:

        customers = customers.filter(
            Q(name__icontains=search)
            | Q(mobile__icontains=search)
            | Q(customer_code__icontains=search)
        )

    data = []

    for customer in customers[:50]:

        data.append({
            "id": customer.id,
            "customer_code": customer.customer_code,
            "name": customer.name,
            "mobile": customer.mobile,
            "address": customer.address,
        })

    return JsonResponse({
        "success": True,
        "customers": data,
    })
