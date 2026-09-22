from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from datetime import date
from django.db.models import Q
from django.conf import settings
from django.core.mail import EmailMessage
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

from .models import (
    Product,
    ServiceReport,
    ServiceReportItem,
    Ticket,
    InventoryMovement, 
    InventoryStock, 
    Customer, 
    Ticket,
    SalesLineItem,
    SalesInvoice,
    VendorLedger,
)






class InventoryService:
    """
    Central service responsible for all inventory transactions.

    Every module (Purchase, Sale, Repair, etc.) must call this service
    instead of modifying InventoryStock directly.
    """

    # ----------------------------------------------------------
    # Internal Helper
    # ----------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def _record_movement(
        *,
        product,
        movement_type,
        quantity,
        from_location,
        to_location,
        unit_cost=Decimal("0.00"),
        document_number="",
        reference_type="",
        reference_id=None,
        remarks="",
        user=None,
    ):

        stock, _ = InventoryStock.objects.get_or_create(
            product=product
        )

        # -------------------------
        # Incoming
        # -------------------------

        incoming = {
            "PURCHASE",
            "SALE_RETURN",
            "REPAIR_RETURN",
            "OPENING",
        }

        # -------------------------
        # Outgoing
        # -------------------------

        outgoing = {
            "SALE",
            "PURCHASE_RETURN",
            "REPAIR_ISSUE",
        }

        # -------------------------
        # Increase Stock
        # -------------------------

        if movement_type in incoming:

            stock.quantity_on_hand = F("quantity_on_hand") + quantity

        # -------------------------
        # Decrease Stock
        # -------------------------

        elif movement_type in outgoing:

            stock.refresh_from_db()

            if stock.quantity_on_hand < quantity:

                raise ValueError(
                    f"Insufficient stock for {product.item_name}"
                )

            stock.quantity_on_hand = (
                F("quantity_on_hand") - quantity
            )

        # -------------------------
        # Adjustment / Transfer
        # handled separately
        # -------------------------

        stock.last_cost = unit_cost

        stock.save()

        stock.refresh_from_db()

        movement = InventoryMovement.objects.create(

            product=product,

            movement_type=movement_type,

            quantity=quantity,

            from_location=from_location,

            to_location=to_location,

            unit_cost=unit_cost,

            document_number=document_number,

            reference_type=reference_type,

            reference_id=reference_id,

            remarks=remarks,

            created_by=user,

        )

        return movement

    # ----------------------------------------------------------
    # Purchase
    # ----------------------------------------------------------

    @staticmethod
    def purchase(
        *,
        product,
        quantity,
        unit_cost,
        document_number,
        user=None,
        remarks="",
    ):

        return InventoryService._record_movement(

            product=product,

            movement_type=InventoryMovement.PURCHASE,

            quantity=quantity,

            from_location=InventoryMovement.VENDOR,

            to_location=InventoryMovement.WAREHOUSE,

            unit_cost=unit_cost,

            document_number=document_number,

            reference_type="Purchase",

            remarks=remarks,

            user=user,

        )

    # ----------------------------------------------------------
    # Sale
    # ----------------------------------------------------------

    @staticmethod
    def sale(
        *,
        product,
        quantity,
        document_number,
        user=None,
        remarks="",
    ):

        return InventoryService._record_movement(

            product=product,

            movement_type=InventoryMovement.SALE,

            quantity=quantity,

            from_location=InventoryMovement.WAREHOUSE,

            to_location=InventoryMovement.CUSTOMER,

            document_number=document_number,

            reference_type="Sale",

            remarks=remarks,

            user=user,

        )

    # ----------------------------------------------------------
    # Purchase Return
    # ----------------------------------------------------------

    @staticmethod
    def purchase_return(
        *,
        product,
        quantity,
        document_number,
        user=None,
        remarks="",
    ):

        return InventoryService._record_movement(

            product=product,

            movement_type=InventoryMovement.PURCHASE_RETURN,

            quantity=quantity,

            from_location=InventoryMovement.WAREHOUSE,

            to_location=InventoryMovement.VENDOR,

            document_number=document_number,

            reference_type="Purchase Return",

            remarks=remarks,

            user=user,

        )

    # ----------------------------------------------------------
    # Sale Return
    # ----------------------------------------------------------

    @staticmethod
    def sale_return(
        *,
        product,
        quantity,
        unit_cost,
        document_number,
        user=None,
        remarks="",
    ):

        return InventoryService._record_movement(

            product=product,

            movement_type=InventoryMovement.SALE_RETURN,

            quantity=quantity,

            from_location=InventoryMovement.CUSTOMER,

            to_location=InventoryMovement.WAREHOUSE,

            unit_cost=unit_cost,

            document_number=document_number,

            reference_type="Sale Return",

            remarks=remarks,

            user=user,

        )

    # ----------------------------------------------------------
    # Issue To Repair
    # ----------------------------------------------------------

    @staticmethod
    def issue_to_repair(
        *,
        product,
        quantity,
        document_number,
        user=None,
        remarks="",
    ):

        return InventoryService._record_movement(

            product=product,

            movement_type=InventoryMovement.REPAIR_ISSUE,

            quantity=quantity,

            from_location=InventoryMovement.WAREHOUSE,

            to_location=InventoryMovement.REPAIR,

            document_number=document_number,

            reference_type="Repair",

            remarks=remarks,

            user=user,

        )

    # ----------------------------------------------------------
    # Return From Repair
    # ----------------------------------------------------------

    @staticmethod
    def return_from_repair(
        *,
        product,
        quantity,
        document_number,
        user=None,
        remarks="",
    ):

        stock = InventoryStock.objects.get(product=product)

        return InventoryService._record_movement(

            product=product,

            movement_type=InventoryMovement.REPAIR_RETURN,

            quantity=quantity,

            from_location=InventoryMovement.REPAIR,

            to_location=InventoryMovement.WAREHOUSE,

            unit_cost=stock.last_cost,

            document_number=document_number,

            reference_type="Repair",

            remarks=remarks,

            user=user,

        )


class TicketService:

    # ==========================================================
    # Customer Code Generator
    # ==========================================================

    @staticmethod
    def generate_customer_code():

        prefix = date.today().strftime("C%y%m")

        last_customer = (
            Customer.objects.filter(
                customer_code__startswith=prefix
            )
            .order_by("-customer_code")
            .first()
        )

        if last_customer:
            number = int(last_customer.customer_code[-4:]) + 1
        else:
            number = 1

        return f"{prefix}{number:04d}"

    # ==========================================================
    # Ticket Listing
    # ==========================================================

    @staticmethod
    def list_tickets(request):

        tickets = (
            Ticket.objects
            .select_related(
                "customer",
                "created_by",
                "assigned_to",
            )
            .all()
        )

        search = request.GET.get("search", "").strip()

        if search:

            tickets = tickets.filter(

                Q(ticket_number__icontains=search) |

                Q(customer__name__icontains=search) |

                Q(customer__mobile__icontains=search) |

                Q(device_type__icontains=search) |

                Q(brand__icontains=search) |

                Q(model__icontains=search) |

                Q(serial_number__icontains=search)

            )

        status = request.GET.get("status", "OPEN")

        if status != "ALL":
            tickets = tickets.filter(status=status)

        return tickets.order_by("-created_at")

    # ==========================================================
    # Customer Lookup
    # ==========================================================

    @staticmethod
    def customer_lookup(mobile):

        if not mobile:

            return {
                "found": False
            }

        customer = Customer.objects.filter(
            mobile=mobile
        ).first()

        if not customer:

            return {
                "found": False
            }

        return {

            "found": True,

            "customer": {

                "id": customer.id,

                "customer_code": customer.customer_code,

                "name": customer.name,

                "mobile": customer.mobile,

                "email": customer.email,

                "address": customer.address,

                "vat_number": customer.vat_number,

                "payment_type": customer.payment_type,

                "credit_limit": str(customer.credit_limit),

            }

        }

    # ==========================================================
    # Create Ticket
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def create_ticket(request):

        customer_id = request.POST.get("customer_id")

        mobile = request.POST.get(
            "mobile",
            ""
        ).strip()

        if customer_id:

            customer = Customer.objects.get(
                pk=customer_id
            )

        else:

            customer = Customer.objects.create(

                customer_code=TicketService.generate_customer_code(),

                name=request.POST.get("name"),

                mobile=mobile,

                email=request.POST.get(
                    "email",
                    "",
                ),

                address=request.POST.get(
                    "address",
                    "",
                ),

                vat_number=request.POST.get(
                    "vat_number",
                    "",
                ),

                payment_type=request.POST.get(
                    "payment_type",
                    "cash",
                ),

                credit_limit=request.POST.get(
                    "credit_limit",
                    0,
                ),

            )

        ticket = Ticket.objects.create(

            customer=customer,

            device_type=request.POST.get(
                "device_type"
            ),

            brand=request.POST.get(
                "brand"
            ),

            model=request.POST.get(
                "model"
            ),

            serial_number=request.POST.get(
                "serial_number"
            ),

            accessories=request.POST.get(
                "accessories"
            ),

            issue_description=request.POST.get(
                "issue_description"
            ),

            priority=request.POST.get(
                "priority",
                Ticket.NORMAL,
            ),

            estimated_delivery=request.POST.get(
                "estimated_delivery"
            ) or None,

            remarks=request.POST.get(
                "remarks"
            ),

            created_by=request.user,

            assigned_to=request.user,

        )

        return ticket

    # ==========================================================
    # Update Ticket
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def update_ticket(
        request,
        ticket_id,
    ):

        ticket = Ticket.objects.select_related(
            "customer"
        ).get(
            pk=ticket_id
        )

        customer = ticket.customer

        customer.name = request.POST.get(
            "name"
        )

        customer.mobile = request.POST.get(
            "mobile"
        )

        customer.email = request.POST.get(
            "email"
        )

        customer.address = request.POST.get(
            "address"
        )

        customer.vat_number = request.POST.get(
            "vat_number"
        )

        customer.payment_type = request.POST.get(
            "payment_type"
        )

        customer.credit_limit = request.POST.get(
            "credit_limit",
            0,
        )

        customer.save()

        ticket.device_type = request.POST.get(
            "device_type"
        )

        ticket.brand = request.POST.get(
            "brand"
        )

        ticket.model = request.POST.get(
            "model"
        )

        ticket.serial_number = request.POST.get(
            "serial_number"
        )

        ticket.accessories = request.POST.get(
            "accessories"
        )

        ticket.issue_description = request.POST.get(
            "issue_description"
        )

        ticket.priority = request.POST.get(
            "priority"
        )

        ticket.estimated_delivery = request.POST.get(
            "estimated_delivery"
        ) or None

        ticket.remarks = request.POST.get(
            "remarks"
        )

        ticket.assigned_to = request.user

        ticket.save()

        return ticket

    # ==========================================================
    # Ticket Detail
    # ==========================================================

    @staticmethod
    def get_ticket_context(ticket_id):

        ticket = (
            Ticket.objects
            .select_related(
                "customer",
                "created_by",
                "assigned_to",
            )
            .get(pk=ticket_id)
        )

        return {

            "ticket": ticket

        }

    # ==========================================================
    # Close Ticket
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def close_ticket(
        ticket_id,
        user=None,
    ):

        ticket = Ticket.objects.get(
            pk=ticket_id
        )

        ticket.status = Ticket.CLOSED

        ticket.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return ticket

    # ==========================================================
    # Delete Ticket
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def delete_ticket(ticket_id):

        ticket = Ticket.objects.get(
            pk=ticket_id
        )

        ticket.delete()

    # ==========================================================
    # Print
    # ==========================================================

    @staticmethod
    def get_print_context(ticket_id):

        ticket = (
            Ticket.objects
            .select_related(
                "customer"
            )
            .get(pk=ticket_id)
        )

        return {

            "ticket": ticket

        }
    

class CustomerService:

    # ----------------------------------------------------------
    # Customer Code
    # ----------------------------------------------------------

    @staticmethod
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

    # ----------------------------------------------------------
    # Create
    # ----------------------------------------------------------

    @staticmethod
    def create_customer(request):

        return Customer.objects.create(

            customer_code=CustomerService.generate_customer_code(),

            name=request.POST.get("name"),

            mobile=request.POST.get("mobile"),

            email=request.POST.get("email"),

            address=request.POST.get("address"),

            vat_number=request.POST.get("vat_number"),

            payment_type=request.POST.get(
                "payment_type",
                "cash",
            ),

            credit_limit=request.POST.get(
                "credit_limit",
                0,
            ),

        )

    # ----------------------------------------------------------
    # Update
    # ----------------------------------------------------------

    @staticmethod
    def update_customer(customer_id, request):

        customer = Customer.objects.get(
            pk=customer_id
        )

        customer.name = request.POST.get("name")

        customer.mobile = request.POST.get("mobile")

        customer.email = request.POST.get("email")

        customer.address = request.POST.get("address")

        customer.vat_number = request.POST.get("vat_number")

        customer.payment_type = request.POST.get(
            "payment_type"
        )

        customer.credit_limit = request.POST.get(
            "credit_limit",
            0,
        )

        customer.save()

        return customer




class ServiceReportService:

    

    @staticmethod
    def generate_report_number():

        from django.utils import timezone

        today = timezone.now().strftime("%Y%m%d")

        last = (
            ServiceReport.objects.filter(
                report_number__startswith=f"SR-{today}"
            )
            .order_by("-id")
            .first()
        )

        if last:

            seq = int(
                last.report_number.split("-")[-1]
            ) + 1

        else:

            seq = 1

        return f"SR-{today}-{seq:04d}"


    @staticmethod
    def save_items(report, request):

        product_ids = request.POST.getlist("product_id[]")
        quantities = request.POST.getlist("quantity[]")
        rates = request.POST.getlist("rate[]")
        tax_percentages = request.POST.getlist("tax_percent[]")
        remarks = request.POST.getlist("item_remarks[]")

        for i, product_id in enumerate(product_ids):

            if not product_id:
                continue

            product = Product.objects.get(
                pk=product_id
            )

            quantity = int(
                quantities[i]
            )

            rate = Decimal(
                rates[i]
            )

            tax_percentage = Decimal(
                tax_percentages[i]
                if i < len(tax_percentages) and tax_percentages[i]
                else "13"
            )

            ServiceReportItem.objects.create(

                service_report=report,

                product=product,

                item_code=product.item_code,

                item_name=product.item_name,

                specification=product.specification,

                quantity=quantity,

                estimated_rate=rate,

                tax_percentage=tax_percentage,

                remarks=(
                    remarks[i]
                    if i < len(remarks)
                    else ""
                ),

            )

    # ==========================================================
    # List Service Reports
    # ==========================================================

    @staticmethod
    def list_reports(request):

        reports = (
            ServiceReport.objects
            .select_related(
                "ticket",
                "ticket__customer",
                "technician",
            )
            .prefetch_related("items")
        )

        search = request.GET.get("search", "").strip()

        if search:

            reports = reports.filter(

                Q(report_number__icontains=search) |

                Q(ticket__ticket_number__icontains=search) |

                Q(ticket__customer__name__icontains=search) |

                Q(ticket__customer__mobile__icontains=search)

            )

        report_status = request.GET.get("report_status", "ALL")

        if report_status != "ALL":

            reports = reports.filter(status=report_status)

        return reports.order_by("-created_at")

    # ==========================================================
    # Pending Tickets
    # ==========================================================

    @staticmethod
    def pending_tickets(request):

        tickets = (
            Ticket.objects
            .select_related("customer")
            .filter(service_report__isnull=True)
        )

        search = request.GET.get("search", "").strip()

        if search:

            tickets = tickets.filter(

                Q(ticket_number__icontains=search) |

                Q(customer__name__icontains=search) |

                Q(customer__mobile__icontains=search) |

                Q(device_type__icontains=search) |

                Q(brand__icontains=search) |

                Q(model__icontains=search) |

                Q(serial_number__icontains=search)

            )

        status = request.GET.get("ticket_status", "OPEN")

        if status != "ALL":

            tickets = tickets.filter(status=status)

        return tickets.order_by("-created_at")


    # ==========================================================
    # Create Report
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def create_report(request, ticket):

        report = ServiceReport.objects.create(

            report_number=ServiceReportService.generate_report_number(),

            ticket=ticket,

            technician=request.user,

            inspection_notes=request.POST.get(
                "inspection_notes",
                "",
            ),

            problem_found=request.POST.get(
                "problem_found",
                "",
            ),

            repair_solution=request.POST.get(
                "repair_solution",
                "",
            ),

            labor_charge=Decimal(
                request.POST.get(
                    "labor_charge",
                    "0",
                )
            ),

            other_charge=Decimal(
                request.POST.get(
                    "other_charge",
                    "0",
                )
            ),

            remarks=request.POST.get(
                "remarks",
                "",
            ),

            created_by=request.user,

            status=(
                ServiceReport.SUBMITTED
                if request.POST.get("action") == "submit"
                else ServiceReport.DRAFT
            ),

        )

        ServiceReportService.save_items(
            report,
            request,
        )

        return report

    # ==========================================================
    # Update Report
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def update_report(request, report_id):
        print(report_id)
        print("----- ALL POST DATA -----") 
        print(request.POST)
        report = ServiceReport.objects.get(
            pk=report_id
        )
        report.inspection_notes = request.POST.get(
            "inspection_notes",
            "",
        )

        report.problem_found = request.POST.get(
            "problem_found",
            "",
        )

        report.repair_solution = request.POST.get(
            "repair_solution",
            "",
        )

        report.labor_charge = Decimal(
            request.POST.get(
                "labor_charge",
                "0",
            )
        )

        report.other_charge = Decimal(
            request.POST.get(
                "other_charge",
                "0",
            )
        )

        report.remarks = request.POST.get(
            "remarks",
            "",
        )

        report.status = (
            ServiceReport.SUBMITTED
            if request.POST.get("action") == "submit"
            else ServiceReport.DRAFT
        )

        report.save()

        report.items.all().delete()

        ServiceReportService.save_items(
            report,
            request,
        )

        return report

    # ==========================================================
    # Get Report
    # ==========================================================

    @staticmethod
    def get_report_context(report_id):

        report = (
            ServiceReport.objects
            .select_related(
                "ticket",
                "ticket__customer",
                "technician",
            )
            .prefetch_related(
                "items",
                "items__product",
            )
            .get(pk=report_id)
        )

        return {

            "report": report,

            "products": Product.objects.order_by(
                "category",
                "item_name",
            ),

        }

    # ==========================================================
    # Submit
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def submit_report(report_id):

        report = ServiceReport.objects.get(
            pk=report_id
        )

        report.status = ServiceReport.SUBMITTED

        report.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return report

    # ==========================================================
    # Approve
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def approve_report(report_id, user):

        report = ServiceReport.objects.get(
            pk=report_id
        )

        report.status = ServiceReport.APPROVED

        report.approved_by = user

        report.approved_at = timezone.now()

        report.save()

        return report

    # ==========================================================
    # Reject
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def reject_report(report_id):

        report = ServiceReport.objects.get(
            pk=report_id
        )

        report.status = ServiceReport.REJECTED

        report.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return report

    # ==========================================================
    # Complete
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def complete_report(report_id):

        report = ServiceReport.objects.get(
            pk=report_id
        )

        report.status = ServiceReport.COMPLETED

        report.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return report


    from decimal import Decimal, InvalidOperation







class SaleService:

    # ==========================================================
    # Invoice Number
    # ==========================================================

    @staticmethod
    def generate_invoice_number():

        today = timezone.localdate()

        prefix = f"SI-{today.strftime('%Y%m%d')}"

        last_invoice = (
            SalesInvoice.objects
            .filter(invoice_number__startswith=prefix)
            .order_by("-id")
            .first()
        )

        if last_invoice:
            try:
                last_number = int(
                    last_invoice.invoice_number.split("-")[-1]
                )
            except (ValueError, IndexError):
                last_number = 0
        else:
            last_number = 0

        return f"{prefix}-{last_number + 1:04d}"

    # ==========================================================
    # Decimal Helper
    # ==========================================================

    @staticmethod
    def decimal_value(value, default=Decimal("0.00")):

        try:
            if value in (None, ""):
                return default

            return Decimal(str(value))

        except (InvalidOperation, TypeError, ValueError):
            return default

    # ==========================================================
    # DIRECT SALE
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def create_direct_sale(
        *,
        customer,
        request,
        user,
    ):

        invoice_date = request.POST.get(
            "invoice_date"
        ) or timezone.localdate()

        discount = SaleService.decimal_value(
            request.POST.get("discount_amount")
        )

        notes = request.POST.get(
            "notes",
            ""
        ).strip()

        discount_remark = request.POST.get(
            "discount_remark",
            ""
        ).strip()

        payment_mode = request.POST.get(
            "payment_mode",
            "cash",
        ).strip().lower()

        invoice_number = SaleService.generate_invoice_number()

        invoice = SalesInvoice.objects.create(
            invoice_number=invoice_number,
            customer=customer,
            invoice_date=invoice_date,
            sale_type="DIRECT",
            status="confirmed",
            payment_mode=payment_mode,
            notes=SaleService.build_notes(
                notes,
                discount_remark,
            ),
        )

        SaleService._create_direct_items(
            invoice=invoice,
            request=request,
            user=user,
        )

        SaleService._finalize_invoice(
            invoice=invoice,
            discount=discount,
        )

        return invoice

    # ==========================================================
    # DIRECT SALE ITEMS
    # ==========================================================

    @staticmethod
    def _create_direct_items(
        *,
        invoice,
        request,
        user,
    ):

        product_ids = request.POST.getlist(
            "product_id[]"
        )

        quantities = request.POST.getlist(
            "quantity[]"
        )

        rates = request.POST.getlist(
            "rate[]"
        )

        tax_percentages = request.POST.getlist(
            "tax_percentage[]"
        )

        serial_numbers = request.POST.getlist(
            "serial_number[]"
        )

        for index, product_id in enumerate(product_ids):

            if not product_id:
                continue

            product = Product.objects.get(
                pk=product_id
            )

            quantity = int(
                quantities[index]
                if index < len(quantities)
                else 1
            )

            rate = SaleService.decimal_value(
                rates[index]
                if index < len(rates)
                else product.selling_price
            )

            tax_percentage = SaleService.decimal_value(
                tax_percentages[index]
                if index < len(tax_percentages)
                else 13
            )

            serial_number = (
                serial_numbers[index]
                if index < len(serial_numbers)
                else ""
            )

            subtotal = (
                Decimal(quantity) * rate
            )

            tax_amount = (
                subtotal * tax_percentage / Decimal("100")
            )

            line_total = (
                subtotal + tax_amount
            )

            SalesLineItem.objects.create(

                invoice=invoice,

                item_code=product.item_code,

                item_name=product.item_name,

                specification=product.specification,

                quantity=quantity,

                rate=rate,

                tax_percentage=tax_percentage,

                tax_amount=tax_amount,

                discount_percentage=Decimal("0.00"),

                discount_amount=Decimal("0.00"),

                line_total=line_total,

                serial_number=serial_number,

            )

            # ----------------------------------------------
            # DIRECT SALE MOVES STOCK OUT
            # ----------------------------------------------

            InventoryService.sale(

                product=product,

                quantity=quantity,

                document_number=invoice,

                user=user,

                remarks=(
                    f"Direct sale "
                    f"{invoice.invoice_number}"
                ),

            )

    # ==========================================================
    # REPAIR SALE
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def create_repair_sale(
        *,
        service_report,
        request,
        user,
    ):

        if service_report.status != ServiceReport.APPROVED:

            raise ValueError(
                "Only an approved service report "
                "can be invoiced."
            )

        if SalesInvoice.objects.filter(
            service_report=service_report
        ).exists():

            raise ValueError(
                "This service report has already "
                "been invoiced."
            )

        invoice_date = request.POST.get(
            "invoice_date"
        ) or timezone.localdate()

        discount = SaleService.decimal_value(
            request.POST.get("discount_amount")
        )

        notes = request.POST.get(
            "notes",
            ""
        ).strip()

        discount_remark = request.POST.get(
            "discount_remark",
            ""
        ).strip()

        invoice = SalesInvoice.objects.create(

            invoice_number=SaleService.generate_invoice_number(),

            customer=service_report.ticket.customer,

            invoice_date=invoice_date,

            sale_type="REPAIR",

            service_report=service_report,

            status="confirmed",

            notes=SaleService.build_notes(
                notes,
                discount_remark,
            ),

        )

        # --------------------------------------------------
        # Copy Service Report Items
        # --------------------------------------------------

        for item in service_report.items.select_related(
            "product"
        ):

            product = item.product

            quantity = item.quantity

            rate = item.estimated_rate

            # Service report estimate is already the
            # repair selling rate.

            line_total = (
                Decimal(quantity) * rate
            )

            SalesLineItem.objects.create(

                invoice=invoice,

                item_code=product.item_code,

                item_name=product.item_name,

                specification=product.specification,

                quantity=quantity,

                rate=rate,

                tax_percentage=Decimal("0.00"),

                tax_amount=Decimal("0.00"),

                discount_percentage=Decimal("0.00"),

                discount_amount=Decimal("0.00"),

                line_total=line_total,

            )

        # --------------------------------------------------
        # Labour / Other Charges
        #
        # These are not Product lines.
        # We include them in invoice total.
        # --------------------------------------------------

        parts_total = sum(
            (
                item.line_total
                for item in invoice.items.all()
            ),
            Decimal("0.00"),
        )

        labour = service_report.labor_charge

        other = service_report.other_charge

        subtotal = (
            parts_total
            + labour
            + other
        )

        invoice.total_amount = subtotal

        invoice.tax_amount = Decimal("0.00")

        invoice.discount_amount = discount

        invoice.grand_total = max(
            subtotal - discount,
            Decimal("0.00"),
        )

        invoice.save(
            update_fields=[
                "total_amount",
                "tax_amount",
                "discount_amount",
                "grand_total",
            ]
        )

        # IMPORTANT:
        #
        # We DO NOT call InventoryService.sale()
        # here.
        #
        # The service report approval already moved
        # the required parts out of warehouse stock.

        return invoice

    # ==========================================================
    # SALE RETURN
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def create_sale_return(
        *,
        customer,
        request,
        user,
    ):

        invoice_date = request.POST.get(
            "invoice_date"
        ) or timezone.localdate()

        discount = SaleService.decimal_value(
            request.POST.get("discount_amount")
        )

        notes = request.POST.get(
            "notes",
            ""
        ).strip()

        discount_remark = request.POST.get(
            "discount_remark",
            ""
        ).strip()

        invoice = SalesInvoice.objects.create(

            invoice_number=SaleService.generate_invoice_number(),

            customer=customer,

            invoice_date=invoice_date,

            sale_type="RETURN",

            status="confirmed",

            notes=SaleService.build_notes(
                notes,
                discount_remark,
            ),

        )

        product_ids = request.POST.getlist(
            "product_id[]"
        )

        quantities = request.POST.getlist(
            "quantity[]"
        )

        rates = request.POST.getlist(
            "rate[]"
        )

        tax_percentages = request.POST.getlist(
            "tax_percentage[]"
        )

        for index, product_id in enumerate(product_ids):

            if not product_id:
                continue

            product = Product.objects.get(
                pk=product_id
            )

            quantity = int(
                quantities[index]
            )

            rate = SaleService.decimal_value(
                rates[index]
                if index < len(rates)
                else product.selling_price
            )

            tax_percentage = SaleService.decimal_value(
                tax_percentages[index]
                if index < len(tax_percentages)
                else 13
            )

            subtotal = (
                Decimal(quantity) * rate
            )

            tax_amount = (
                subtotal
                * tax_percentage
                / Decimal("100")
            )

            line_total = (
                subtotal + tax_amount
            )

            SalesLineItem.objects.create(

                invoice=invoice,

                item_code=product.item_code,

                item_name=product.item_name,

                specification=product.specification,

                quantity=quantity,

                rate=rate,

                tax_percentage=tax_percentage,

                tax_amount=tax_amount,

                line_total=line_total,

            )

            # ----------------------------------------------
            # RETURN MOVES STOCK BACK INTO WAREHOUSE
            # ----------------------------------------------

            InventoryService.sale_return(

                product=product,

                quantity=quantity,

                unit_cost=product.selling_price,

                document_number=invoice,

                user=user,

                remarks=(
                    f"Sale return "
                    f"{invoice.invoice_number}"
                ),

            )

        SaleService._finalize_invoice(
            invoice=invoice,
            discount=discount,
        )

        return invoice

    # ==========================================================
    # Finalize Invoice
    # ==========================================================
    @staticmethod
    def _finalize_invoice(
        *,
        invoice,
        discount=Decimal("0.00"),
    ):

        subtotal = sum(
            (
                item.quantity * item.rate
                for item in invoice.items.all()
            ),
            Decimal("0.00"),
        )

        tax_amount = sum(
            (
                item.tax_amount
                for item in invoice.items.all()
            ),
            Decimal("0.00"),
        )

        total_before_discount = (
            subtotal + tax_amount
        )

        grand_total = max(
            total_before_discount - discount,
            Decimal("0.00"),
        )

        invoice.total_amount = subtotal
        invoice.tax_amount = tax_amount
        invoice.discount_amount = discount
        invoice.grand_total = grand_total

        invoice.save(
            update_fields=[
                "total_amount",
                "tax_amount",
                "discount_amount",
                "grand_total",
            ]
        )

    # ==========================================================
    # Notes
    # ==========================================================

    @staticmethod
    def build_notes(
        notes,
        discount_remark,
    ):

        parts = []

        if notes:
            parts.append(notes)

        if discount_remark:

            parts.append(
                f"Discount Remark: {discount_remark}"
            )

        return "\n".join(parts)



class VendorLedgerService:

    @staticmethod
    def recalculate(vendor):

        entries = VendorLedger.objects.filter(
            vendor=vendor
        ).order_by(
            "transaction_date",
            "id"
        )

        balance = Decimal("0.00")

        for entry in entries:

            balance += entry.cr
            balance -= entry.dr

            entry.closing_balance = balance

        VendorLedger.objects.bulk_update(
            entries,
            ["closing_balance"]
        )

        return balance


    @staticmethod
    def generate_excel(
        vendor,
        from_date,
        to_date,
    ):

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


        workbook = Workbook()

        worksheet = workbook.active

        worksheet.title = "Vendor Ledger"


        # ==========================================
        # Header
        # ==========================================

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
        # Table
        # ==========================================

        header_row = 8

        headers = [
            "Date",
            "Transaction",
            "Invoice / Reference",
            "Mode",
            "Remark",
            "Debit",
            "Credit",
            "Balance",
        ]

        for column, header in enumerate(
            headers,
            start=1
        ):

            cell = worksheet.cell(
                row=header_row,
                column=column,
                value=header
            )

            cell.font = Font(
                bold=True
            )

            cell.alignment = Alignment(
                horizontal="center"
            )


        row = header_row + 1

        running_balance = opening_balance


        # ==========================================
        # Opening Balance Row
        # ==========================================

        worksheet.cell(
            row=row,
            column=2,
            value="Opening Balance"
        ).font = Font(
            bold=True
        )

        if opening_balance < 0:

            worksheet.cell(
                row=row,
                column=6,
                value=abs(opening_balance)
            )

        elif opening_balance > 0:

            worksheet.cell(
                row=row,
                column=7,
                value=opening_balance
            )

        worksheet.cell(
            row=row,
            column=8,
            value=opening_balance
        )

        row += 1


        # ==========================================
        # Transactions
        # ==========================================

        for entry in transactions:

            running_balance += entry.cr
            running_balance -= entry.dr


            invoice_reference = ""

            if entry.against_invoice:

                invoice_reference = (
                    entry.against_invoice.invoice_number
                )

            elif entry.reference:

                invoice_reference = entry.reference


            mode_display = ""

            if entry.mode:

                mode_display = (
                    entry.get_mode_display()
                )


            worksheet.cell(
                row=row,
                column=1,
                value=entry.transaction_date
            )

            worksheet.cell(
                row=row,
                column=2,
                value=entry.get_transaction_type_display()
            )

            worksheet.cell(
                row=row,
                column=3,
                value=invoice_reference
            )

            worksheet.cell(
                row=row,
                column=4,
                value=mode_display
            )

            worksheet.cell(
                row=row,
                column=5,
                value=entry.remark or ""
            )

            worksheet.cell(
                row=row,
                column=6,
                value=entry.dr
            )

            worksheet.cell(
                row=row,
                column=7,
                value=entry.cr
            )

            worksheet.cell(
                row=row,
                column=8,
                value=running_balance
            )

            row += 1


        # ==========================================
        # Closing Balance
        # ==========================================

        closing_row = row + 1

        worksheet.cell(
            row=closing_row,
            column=1,
            value="Closing Balance"
        ).font = Font(
            bold=True
        )

        worksheet.cell(
            row=closing_row,
            column=8,
            value=running_balance
        ).font = Font(
            bold=True
        )


        # ==========================================
        # Formatting
        # ==========================================

        for cell in worksheet["A"]:
            cell.alignment = Alignment(
                vertical="center"
            )


        for row_cells in worksheet.iter_rows(
            min_row=header_row,
            max_row=closing_row
        ):

            for cell in row_cells:

                if cell.column in [6, 7, 8]:

                    cell.number_format = (
                        '#,##0.00'
                    )


        worksheet.column_dimensions["A"].width = 15
        worksheet.column_dimensions["B"].width = 22
        worksheet.column_dimensions["C"].width = 25
        worksheet.column_dimensions["D"].width = 18
        worksheet.column_dimensions["E"].width = 35
        worksheet.column_dimensions["F"].width = 15
        worksheet.column_dimensions["G"].width = 15
        worksheet.column_dimensions["H"].width = 18


        # ==========================================
        # Return Excel as bytes
        # ==========================================

        output = BytesIO()

        workbook.save(output)

        output.seek(0)

        return output.getvalue()

class VendorLedgerEmailService:

    @staticmethod
    def send_ledger(
        vendor,
        recipient_email,
        from_date,
        to_date,
        excel_file,
        filename,
    ):

        subject = (
            f"Vendor Ledger - "
            f"{vendor.name} - "
            f"{from_date.strftime('%d-%m-%Y')} to "
            f"{to_date.strftime('%d-%m-%Y')}"
        )

        message = f"""
            Dear {vendor.name},

            Please find attached your vendor ledger for the period:

            {from_date.strftime('%d-%m-%Y')} to {to_date.strftime('%d-%m-%Y')}

            The attached Excel file contains the opening balance,
            transactions during the selected period, and closing balance.

            Regards,
            Inventory Management
            """

        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[recipient_email],
        )

        email.attach(
            filename,
            excel_file,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        email.send(
            fail_silently=False
        )