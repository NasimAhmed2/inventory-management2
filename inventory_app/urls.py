from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="login"),
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("home/", views.home, name="home"),
    path("inventory/products/", views.inventory_products, name="inventory_products"),
    path(
        "inventory/products/update/<int:pk>/",
        views.product_update,
        name="product_update",
    ),

    path(
        "inventory/products/delete/<int:pk>/",
        views.product_delete,
        name="product_delete",
    ),
    path("purchases/vendors/", views.purchases_vendors, name="purchases_vendors"),
    path("vendors/<int:vendor_id>/ledger/",views.vendor_ledger,name="vendor_ledger"),
    path("vendors/<int:vendor_id>/ledger/download/",views.vendor_ledger_download,name="vendor_ledger_download"),
    path("vendors/<int:vendor_id>/ledger/email/",views.vendor_ledger_email,name="vendor_ledger_email"),
    path("vendors/<int:vendor_id>/ledger/add/",views.vendor_transaction_add,name="vendor_transaction_add"),
    path("purchases/invoices/", views.purchases_invoices, name="purchases_invoices"),
    path("purchases/invoices/<int:invoice_id>/pdf/", views.purchase_invoice_pdf, name="purchase_invoice_pdf"),

    path("inventory/stock/", views.inventory_stock, name="inventory_stock"),
    path("inventory/movements/", views.inventory_movements, name="inventory_movements"),

    # ==========================================================
    # Customers and Sales
    # ==========================================================
    path("sales/customers/", views.sales_customers, name="sales_customers"),
    path("customers/delete/<int:pk>/", views.customer_delete, name="customer_delete"),

    # path("sales/invoices/", views.placeholder_view, {"page_title": "Sales Invoices"}, name="sales_invoices"),
    path("warehouse/locations/", views.placeholder_view, {"page_title": "Warehouses"}, name="warehouse_locations"),
    path("warehouse/challans/", views.placeholder_view, {"page_title": "Delivery Challans"}, name="warehouse_challans"),
    path("finance/entries/", views.placeholder_view, {"page_title": "Finance Entries"}, name="finance_entries"),
    path("finance/reports/", views.placeholder_view, {"page_title": "Reports"}, name="finance_reports"),
    path("create-user/", views.placeholder_view, {"page_title": "Create User"}, name="create_user"),

    
    # ==========================================================
    # Tickets
    # ==========================================================
    path("tickets/",views.tickets,name="tickets"),
    path("tickets/create/",views.ticket_create,name="ticket_create"),
    path("tickets/<int:pk>/",views.ticket_detail,name="ticket_detail"),
    path("tickets/<int:pk>/update/",views.ticket_update,name="ticket_update"),
    path("tickets/<int:pk>/close/",views.ticket_close,name="ticket_close"),
    path("tickets/<int:pk>/delete/",views.ticket_delete,name="ticket_delete"),
    path("tickets/<int:pk>/print/",views.ticket_print,name="ticket_print"),

    # ==========================================================
    # Service Reports
    # ==========================================================

    path(
        "service-reports/",
        views.service_reports,
        name="service_reports",
    ),

    path(
        "service-reports/create/<int:ticket_id>/",
        views.service_report_create,
        name="service_report_create",
    ),

    path(
        "service-reports/<int:pk>/edit/",
        views.service_report_edit,
        name="service_report_edit",
    ),

    path(
        "service-reports/<int:pk>/",
        views.service_report_detail,
        name="service_report_detail",
    ),

    path(
        "service-reports/<int:pk>/update/",
        views.service_report_update,
        name="service_report_update",
    ),

    path(
        "service-reports/<int:pk>/submit/",
        views.service_report_submit,
        name="service_report_submit",
    ),

    path(
        "service-reports/<int:pk>/approve/",
        views.service_report_approve,
        name="service_report_approve",
    ),

    path(
        "service-reports/<int:pk>/reject/",
        views.service_report_reject,
        name="service_report_reject",
    ),

    path(
        "service-reports/<int:pk>/complete/",
        views.service_report_complete,
        name="service_report_complete",
    ),

    # ==========================================================
    # Sales Invoices
    # ==========================================================

    path(
        "sales/invoices/",
        views.sales_invoices,
        name="sales_invoices",
    ),

    path(
        "sales/invoices/new/",
        views.sales_invoice_create,
        name="sales_invoice_create",
    ),

    path(
        "sales/invoices/create/",
        views.sales_invoice_create_save,
        name="sales_invoice_create_save",
    ),

    path(
        "sales/invoices/<int:invoice_id>/",
        views.sales_invoice_detail,
        name="sales_invoice_detail",
    ),

    # ==========================================================
    # Service Report → Repair Invoice
    # ==========================================================

    path(
        "sales/service-report/<int:report_id>/data/",
        views.sales_service_report_data,
        name="sales_service_report_data",
    ),

    # ==========================================================
    # Customer Search
    # ==========================================================

    path(
        "sales/customers/search/",
        views.sales_customer_search,
        name="sales_customer_search",
    ),


    # ==========================================================
    # AJAX
    # ==========================================================
    path("ajax/customer-lookup/",views.customer_lookup,name="customer_lookup"),
]