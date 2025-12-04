# stock_sync/api.py
import frappe
import requests
import json
from frappe import _
from frappe.utils import now_datetime, get_datetime

@frappe.whitelist(allow_guest=False)
def get_stock_for_external():
    """
    API for OTHER sites to fetch THIS site's stock
    """
    try:
        warehouse = frappe.request.args.get('warehouse')
        
        filters = {}
        where_clauses = ["bin.actual_qty > 0"]
        
        if warehouse:
            where_clauses.append("bin.warehouse = %(warehouse)s")
            filters["warehouse"] = warehouse
        
        where_sql = " AND ".join(where_clauses)
        
        stock_data = frappe.db.sql(f"""
            SELECT 
                bin.item_code,
                item.item_name,
                bin.warehouse,
                bin.actual_qty,
                bin.reserved_qty,
                bin.ordered_qty,
                (bin.actual_qty - bin.reserved_qty) as available_qty,
                NOW() as timestamp
            FROM `tabBin` bin
            LEFT JOIN `tabItem` item ON item.name = bin.item_code
            WHERE {where_sql}
            ORDER BY item.item_code, bin.warehouse
        """, filters, as_dict=1)
        
        return {
            "success": True,
            "data": stock_data,
            "site": frappe.local.site,
            "timestamp": now_datetime().isoformat(),
            "count": len(stock_data)
        }
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Stock Export API Error")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def fetch_from_site(site_name, warehouse=None):
    """
    Fetch stock from partner site and store in External Stock View
    """
    try:
        site = frappe.get_doc("Site Connection", site_name)
        
        if not site.is_active:
            return {"success": False, "error": "Site connection is disabled"}
        
        # Create log
        log = frappe.new_doc("Stock Sync Log")
        log.site = site_name
        log.sync_date = now_datetime()
        log.status = "In Progress"
        log.insert()
        
        # Call partner site
        headers = {
            "Authorization": f"token {site.api_key}:{site.api_secret or ''}"
        }
        
        params = {}
        if warehouse:
            params["warehouse"] = warehouse
        
        response = requests.get(
            f"{site.site_url}/api/method/stock_sync.api.get_stock_for_external",
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                stock_data = data["data"]
                
                # Clear old data
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
                        "actual_qty": item.get("actual_qty", 0),
                        "reserved_qty": item.get("reserved_qty", 0),
                        "ordered_qty": item.get("ordered_qty", 0),
                        "available_qty": item.get("available_qty", 0),
                        "last_sync": now_datetime()
                    }).insert(ignore_permissions=True)
                
                frappe.db.commit()
                
                # Update log
                log.status = "Success"
                log.items_count = len(stock_data)
                log.save()
                
                # Update site
                site.last_sync_time = now_datetime()
                site.connection_status = "Connected"
                site.save()
                
                return {
                    "success": True,
                    "count": len(stock_data),
                    "message": f"Fetched {len(stock_data)} items"
                }
            
            else:
                log.status = "Failed"
                log.error_message = data.get("error")
                log.save()
                return {"success": False, "error": data.get("error")}
                
        else:
            log.status = "Failed"
            log.error_message = f"HTTP {response.status_code}"
            log.save()
            return {"success": False, "error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Fetch Stock Error")
        return {"success": False, "error": str(e)}