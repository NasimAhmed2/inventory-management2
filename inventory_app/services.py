from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from datetime import date
from django.db.models import Q
from .models import (
    Product,
    ServiceReport,
    ServiceReportItem,
    Ticket,
    InventoryMovement, 
    InventoryStock, 
    Customer, 
    Ticket
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

    # ==========================================================
    # Report Number Generator
    # ==========================================================

    # @staticmethod
    # def generate_report_number():

    #     prefix = date.today().strftime("SR%y%m")

    #     last = (
    #         ServiceReport.objects
    #         .filter(report_number__startswith=prefix)
    #         .order_by("-report_number")
    #         .first()
    #     )

    #     if last:
    #         number = int(last.report_number[-4:]) + 1
    #     else:
    #         number = 1

    #     return f"{prefix}{number:04d}"

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

        product_ids = request.POST.getlist(
            "product_id[]"
        )

        quantities = request.POST.getlist(
            "quantity[]"
        )

        rates = request.POST.getlist(
            "rate[]"
        )

        remarks = request.POST.getlist(
            "item_remarks[]"
        )

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

            ServiceReportItem.objects.create(

                service_report=report,

                product=product,

                item_code=product.item_code,

                item_name=product.item_name,

                specification=product.specification,

                quantity=quantity,

                estimated_rate=rate,

                line_total=quantity * rate,

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
    def update_report(request, report):

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