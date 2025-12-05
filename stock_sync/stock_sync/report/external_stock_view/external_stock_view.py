# Copyright (c) 2025, Pal Shah and contributors
# For license information, please see license.txt

# stock_sync/report/external_stock_view/external_stock_view.py

import frappe
from frappe import _
from frappe.utils import flt, cint, getdate, nowdate

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    
    # Add summary row
    if data:
        summary = get_summary(data)
        data.append([])  # Empty row
        data.append(summary)
    
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "source_site",
            "label": _("Source Site"),
            "fieldtype": "Link",
            "options": "Site Connection",
            "width": 120
        },
        {
            "fieldname": "warehouse",
            "label": _("Warehouse"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "actual_qty",
            "label": _("Actual Qty"),
            "fieldtype": "Float",
            "width": 90,
            "precision": 2
        },
        {
            "fieldname": "reserved_qty",
            "label": _("Reserved Qty"),
            "fieldtype": "Float",
            "width": 90,
            "precision": 2
        },
        {
            "fieldname": "ordered_qty",
            "label": _("Ordered Qty"),
            "fieldtype": "Float",
            "width": 90,
            "precision": 2
        },
        {
            "fieldname": "available_qty",
            "label": _("Available Qty"),
            "fieldtype": "Float",
            "width": 90,
            "precision": 2
        },
        {
            "fieldname": "last_sync",
            "label": _("Last Sync"),
            "fieldtype": "Datetime",
            "width": 140
        },
        {
            "fieldname": "age",
            "label": _("Age (hours)"),
            "fieldtype": "Float",
            "width": 80,
            "precision": 1
        }
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    query = """
        SELECT
            esv.item_code,
            esv.item_name,
            esv.source_site,
            esv.warehouse,
            esv.actual_qty,
            esv.reserved_qty,
            esv.ordered_qty,
            esv.available_qty,
            esv.last_sync,
            TIMESTAMPDIFF(HOUR, esv.last_sync, NOW()) as age
        FROM `tabExternal Stock View` esv
        WHERE esv.docstatus = 0
        {conditions}
        ORDER BY esv.source_site, esv.item_code, esv.warehouse
    """.format(conditions=conditions)
    
    data = frappe.db.sql(query, filters, as_dict=1)
    
    return data

def get_conditions(filters):
    conditions = []
    
    if filters.get("source_site"):
        conditions.append("esv.source_site = %(source_site)s")
    
    if filters.get("item_code"):
        conditions.append("esv.item_code = %(item_code)s")
    
    if filters.get("warehouse"):
        conditions.append("esv.warehouse = %(warehouse)s")
    
    if filters.get("last_sync_from"):
        conditions.append("esv.last_sync >= %(last_sync_from)s")
    
    if filters.get("last_sync_to"):
        conditions.append("esv.last_sync <= DATE_ADD(%(last_sync_to)s, INTERVAL 1 DAY)")
    
    if filters.get("show_only_available"):
        conditions.append("esv.available_qty > 0")
    
    return " AND " + " AND ".join(conditions) if conditions else ""

def get_summary(data):
    total_items = len(data)
    total_actual_qty = sum([flt(d.actual_qty) for d in data])
    total_reserved_qty = sum([flt(d.reserved_qty) for d in data])
    total_ordered_qty = sum([flt(d.ordered_qty) for d in data])
    total_available_qty = sum([flt(d.available_qty) for d in data])
    
    # Count sites
    sites = set([d.source_site for d in data])
    
    return {
        "item_code": f"<b>{_('SUMMARY')}</b>",
        "item_name": f"<b>{total_items} {_('items from')} {len(sites)} {_('sites')}</b>",
        "actual_qty": f"<b>{total_actual_qty:,.2f}</b>",
        "reserved_qty": f"<b>{total_reserved_qty:,.2f}</b>",
        "ordered_qty": f"<b>{total_ordered_qty:,.2f}</b>",
        "available_qty": f"<b>{total_available_qty:,.2f}</b>",
        "indent": 0,
        "bold": 1,
        "background_color": "#f0f0f0"
    }