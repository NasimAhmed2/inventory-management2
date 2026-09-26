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
from django.db import transaction
from django.db.models import F
from .models import (
    Product, 
    PurchaseInvoice, 
    PurchaseLineItem, 
    UserProfile, 
    Vendor, 
    ServiceReport,
    Customer,
    Ticket,
    SalesInvoice,
    VendorLedger,
    
)
from .services import (
    InventoryService, 
    CustomerService, 
    TicketService, 
    ServiceReportService,
    SaleService,
    VendorLedgerService,
    VendorLedgerEmailService,
)


from django.shortcuts import render, redirect, get_object_or_404
import json
from datetime import date, datetime
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from .forms import ProductForm
from .constants import CATEGORY_HSN


User = get_user_model()



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


def generate_vendor_code():
    last_vendor = Vendor.objects.order_by('-id').first()
    if not last_vendor or not last_vendor.vendor_code:
        return "MI001"

    match = re.search(r'(\d+)$', last_vendor.vendor_code.lower())
    if match:
        number = int(match.group(1)) + 1
        return f"MI{number:03d}"
    return "MI001"


def generate_invoice_number(invoice_date):
    prefix = invoice_date.strftime("PI%Y%m%d")
    today_invoices = PurchaseInvoice.objects.filter(invoice_number__startswith=prefix).count()
    return f"{prefix}{today_invoices + 1:03d}"




def sales_customers(request):

    customers = Customer.objects.all().order_by("customer_code")

    search = request.GET.get("search", "").strip()

    if search:

        customers = customers.filter(

            Q(customer_code__icontains=search) |

            Q(name__icontains=search) |

            Q(mobile__icontains=search) |

            Q(email__icontains=search)

        )

    if request.method == "POST":

        try:

            with transaction.atomic():

                customer_id = request.POST.get("customer_id")

                if customer_id:

                    CustomerService.update_customer(
                        customer_id=customer_id,
                        request=request,
                    )

                    messages.success(
                        request,
                        "Customer updated successfully."
                    )

                else:

                    CustomerService.create_customer(
                        request=request,
                    )

                    messages.success(
                        request,
                        "Customer created successfully."
                    )

        except Exception as e:

            messages.error(
                request,
                str(e)
            )

        return redirect("sales_customers")

    context = {

        "customers": customers,

        "search": search,

    }

    return render(
        request,
        "customers.html",
        context,
    )


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


def inventory_products(request):
    """
    Product Listing + Create Product
    """

    search = request.GET.get("search", "").strip()

    if request.method == "POST":

        form = ProductForm(request.POST)

        if form.is_valid():

            product = form.save()

            InventoryStock.objects.get_or_create(
                product=product
            )

            messages.success(
                request,
                "Product added successfully."
            )

            return redirect("inventory_products")

        else:

            messages.error(
                request,
                "Please correct the highlighted errors."
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

    context = {

        "page_title": "Products",

        "products": products,

        "search": search,

        "category_hsn": CATEGORY_HSN,

        "form": form,

    }

    return render(
        request,
        "products.html",
        context,
    )


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
