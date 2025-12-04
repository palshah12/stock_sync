import frappe
import requests
import json
from frappe.utils import now_datetime
from frappe import _

@frappe.whitelist(allow_guest=False)
def get_stock_for_external():
    """
    API to expose THIS site's stock to OTHER sites
    Returns bin data without creating any doctypes
    """
    try:
        # Get warehouse filter
        warehouse = frappe.request.args.get('warehouse')
        
        # Fetch bin data directly
        filters = {}
        if warehouse:
            filters["warehouse"] = warehouse
        
        bin_data = frappe.db.sql("""
            SELECT 
                bin.item_code,
                item.item_name,
                bin.warehouse,
                bin.actual_qty,
                bin.reserved_qty,
                bin.ordered_qty,
                bin.planned_qty,
                (bin.actual_qty - bin.reserved_qty) as available_qty,
                item.item_group,
                item.stock_uom
            FROM `tabBin` bin
            LEFT JOIN `tabItem` item ON item.name = bin.item_code
            WHERE bin.actual_qty > 0
            {warehouse_filter}
            ORDER BY item.item_code, bin.warehouse
        """.format(
            warehouse_filter="AND bin.warehouse = %(warehouse)s" if warehouse else ""
        ), filters, as_dict=1)
        
        return {
            "success": True,
            "data": bin_data,
            "site": frappe.local.site,
            "timestamp": now_datetime().isoformat(),
            "count": len(bin_data)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Get Stock API Error")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def fetch_partner_stock(site_name, warehouse=None):
    """
    Fetch stock from partner site and store in External Stock View
    """
    try:
        # Get site config
        site = frappe.get_doc("Site Connection", site_name)
        
        if not site.is_active:
            return {"success": False, "error": "Site connection is disabled"}
        
        # Create log
        log = frappe.new_doc("Stock Sync Log")
        log.site = site_name
        log.sync_date = now_datetime()
        log.status = "In Progress"
        log.insert()
        
        # Call partner site API
        headers = {
            "Authorization": f"token {site.api_key}:{site.api_secret or ''}"
        }
        
        params = {}
        if warehouse:
            params["warehouse"] = warehouse
        
        response = requests.get(
            f"{site.site_url}/api/method/stock_sync_app.api.get_stock_for_external",
            headers=headers,
            params=params,
            timeout=30,
            verify=True
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                stock_data = data["data"]
                
                # Clear old data for this site
                frappe.db.sql("""
                    DELETE FROM `tabExternal Stock View` 
                    WHERE source_site = %s
                """, site_name)
                
                # Insert new data
                for item in stock_data:
                    frappe.get_doc({
                        "doctype": "External Stock View",
                        "item_code": item["item_code"],
                        "item_name": item["item_name"],
                        "warehouse": item["warehouse"],
                        "source_site": site_name,
                        "actual_qty": item["actual_qty"] or 0,
                        "reserved_qty": item["reserved_qty"] or 0,
                        "ordered_qty": item["ordered_qty"] or 0,
                        "available_qty": item["available_qty"] or 0,
                        "last_sync": now_datetime()
                    }).insert(ignore_permissions=True)
                
                frappe.db.commit()
                
                # Update log
                log.status = "Success"
                log.items_count = len(stock_data)
                log.save()
                
                # Update site connection
                site.last_sync_time = now_datetime()
                site.connection_status = "Connected"
                site.save()
                
                return {
                    "success": True,
                    "count": len(stock_data),
                    "message": f"Fetched {len(stock_data)} items from {site.site_name}"
                }
            else:
                log.status = "Failed"
                log.error_message = data.get("error", "Unknown error")
                log.save()
                
                site.connection_status = "Failed"
                site.save()
                
                return {"success": False, "error": data.get("error")}
        else:
            log.status = "Failed"
            log.error_message = f"HTTP {response.status_code}"
            log.save()
            
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Fetch Partner Stock Error")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def get_combined_stock_view(item_code=None, warehouse=None):
    """
    Get combined view: Local stock + External stock
    """
    result = []
    
    # 1. Get local stock (from Bin)
    local_filters = {}
    if item_code:
        local_filters["item_code"] = item_code
    if warehouse:
        local_filters["warehouse"] = warehouse
    
    # Local stock
    local_stock = frappe.db.sql("""
        SELECT 
            bin.item_code,
            item.item_name,
            bin.warehouse,
            'Local' as source_site,
            bin.actual_qty,
            bin.reserved_qty,
            bin.ordered_qty,
            (bin.actual_qty - bin.reserved_qty) as available_qty,
            NOW() as last_sync
        FROM `tabBin` bin
        LEFT JOIN `tabItem` item ON item.name = bin.item_code
        WHERE bin.actual_qty > 0
        {item_filter} {warehouse_filter}
    """.format(
        item_filter="AND bin.item_code = %(item_code)s" if item_code else "",
        warehouse_filter="AND bin.warehouse = %(warehouse)s" if warehouse else ""
    ), local_filters, as_dict=1)
    
    result.extend(local_stock)
    
    # 2. Get external stock
    external_filters = {}
    if item_code:
        external_filters["item_code"] = item_code
    if warehouse:
        external_filters["warehouse"] = warehouse
    
    external_stock = frappe.get_all("External Stock View",
                                   filters=external_filters,
                                   fields=["item_code", "item_name", "warehouse",
                                          "source_site", "actual_qty", "reserved_qty",
                                          "ordered_qty", "available_qty", "last_sync"])
    
    result.extend(external_stock)
    
    return result