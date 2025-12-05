# stock_sync/stock_sync/api.py - LOCAL APP (not dashqube.com)
import frappe
import requests
import json
from frappe import _
from frappe.utils import now_datetime, get_datetime, cstr
from requests.exceptions import RequestException, Timeout, SSLError, ConnectionError
from urllib.parse import urljoin
import traceback
import urllib3

@frappe.whitelist(allow_guest=False)
def get_stock_for_external(warehouse=None, item_code=None):
    """
    API for OTHER sites to fetch THIS site's stock
    This should be on dashqube.com (which is working fine)
    """
    try:
        # Security check - ensure API key is provided
        auth_header = frappe.request.headers.get('Authorization', '')
        if not auth_header.startswith('token '):
            frappe.throw(_("Authentication required"), frappe.AuthenticationError)
        
        warehouse = frappe.form_dict.get('warehouse')
        item_code = frappe.form_dict.get('item_code')
        
        filters = {}
        where_clauses = ["bin.actual_qty > 0"]
        
        if warehouse:
            where_clauses.append("bin.warehouse = %(warehouse)s")
            filters["warehouse"] = warehouse
        
        if item_code:
            where_clauses.append("bin.item_code = %(item_code)s")
            filters["item_code"] = item_code
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Get stock data
        stock_data = frappe.db.sql(f"""
            SELECT 
                bin.item_code,
                item.item_name,
                item.description,
                bin.warehouse,
                warehouse.warehouse_name,
                bin.actual_qty,
                bin.reserved_qty,
                bin.ordered_qty,
                (bin.actual_qty - bin.reserved_qty) as available_qty,
                item.stock_uom,
                NOW() as timestamp
            FROM `tabBin` bin
            LEFT JOIN `tabItem` item ON item.name = bin.item_code
            LEFT JOIN `tabWarehouse` warehouse ON warehouse.name = bin.warehouse
            WHERE {where_sql}
            ORDER BY item.item_code, bin.warehouse
        """, filters, as_dict=1)
        
        return {
            "success": True,
            "data": stock_data,
            "site": frappe.local.site,
            "timestamp": now_datetime().isoformat(),
            "count": len(stock_data),
            "message": f"Found {len(stock_data)} items"
        }
        
    except frappe.AuthenticationError:
        frappe.log_error(
            title="Stock API Authentication Failed",
            message="Authentication failed for external stock API"
        )
        return {
            "success": False,
            "error": "Authentication failed",
            "status_code": 401
        }
        
    except Exception as e:
        error_message = f"Stock Export API Error: {str(e)}"
        frappe.log_error(
            title="Stock Export API Error",
            message=f"{error_message}\n{traceback.format_exc()}"
        )
        return {
            "success": False,
            "error": error_message,
            "status_code": 500
        }

@frappe.whitelist()
def fetch_from_site(site_name, warehouse=None, item_code=None):
    """
    Fetch stock from partner site and store in External Stock View
    FIXED VERSION - Properly handles dashqube.com response format
    """
    log_doc = None
    
    try:
        # Get site connection
        site = frappe.get_doc("Site Connection", site_name)
        
        if not site.is_active:
            return {
                "success": False,
                "error": "Site connection is disabled",
                "site": site_name
            }
        
        # Create sync log
        log_doc = frappe.get_doc({
            "doctype": "Stock Sync Log",
            "site": site_name,
            "sync_date": now_datetime(),
            "status": "Started"
        })
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        # Prepare request
        headers = {
            "Authorization": f"token {site.api_key}:{site.api_secret or ''}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        params = {}
        if warehouse:
            params["warehouse"] = warehouse
        if item_code:
            params["item_code"] = item_code
        
        endpoint = urljoin(site.site_url, "api/method/stock_sync.api.get_stock_for_external")
        
        # SSL verification
        verify_ssl = not site.get("disable_ssl_verification", False)
        timeout = site.get("timeout") or 45
        
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Make API call
        log_doc.status = "Fetching"
        log_doc.save(ignore_permissions=True)
        
        response = requests.get(
            endpoint,
            headers=headers,
            params=params,
            timeout=timeout,
            verify=verify_ssl
        )
        
        log_doc.status = "Processing"
        log_doc.save(ignore_permissions=True)
        
        # Handle response - FIXED THIS PART
        if response.status_code == 200:
            try:
                response_data = response.json()
                
                # CRITICAL FIX: dashqube.com returns data in response.json()["message"]
                # Check if data is in "message" field
                if "message" in response_data:
                    # The actual API response is inside "message"
                    data = response_data["message"]
                    
                    # Check if data has "success" field (some APIs nest it)
                    if isinstance(data, dict) and "success" in data:
                        # This is the format dashqube.com uses
                        if data.get("success"):
                            stock_data = data.get("data", [])
                        else:
                            # API returned success=False
                            error_msg = data.get("error", "Unknown API error")
                            log_doc.status = "Failed"
                            log_doc.error_message = error_msg
                            log_doc.response_data = json.dumps(data)
                            log_doc.save(ignore_permissions=True)
                            
                            site.connection_status = "Failed"
                            site.save(ignore_permissions=True)
                            
                            return {
                                "success": False,
                                "error": error_msg,
                                "api_response": data,
                                "site": site_name
                            }
                    else:
                        # Direct data response
                        stock_data = data if isinstance(data, list) else []
                else:
                    # Some APIs return data directly
                    data = response_data
                    if data.get("success"):
                        stock_data = data.get("data", [])
                    else:
                        error_msg = data.get("error", "Unknown API error")
                        log_doc.status = "Failed"
                        log_doc.error_message = error_msg
                        log_doc.response_data = json.dumps(data)
                        log_doc.save(ignore_permissions=True)
                        
                        site.connection_status = "Failed"
                        site.save(ignore_permissions=True)
                        
                        return {
                            "success": False,
                            "error": error_msg,
                            "api_response": data,
                            "site": site_name
                        }
                
                # Clear old data for this site
                frappe.db.sql("""
                    DELETE FROM `tabExternal Stock View` 
                    WHERE source_site = %s
                """, site_name)
                
                # Insert new data
                inserted_count = 0
                for item in stock_data:
                    try:
                        external_stock = frappe.get_doc({
                            "doctype": "External Stock View",
                            "item_code": cstr(item.get("item_code")),
                            "item_name": cstr(item.get("item_name", "")),
                            "warehouse": cstr(item.get("warehouse", "")),
                            "source_site": site_name,
                            "actual_qty": float(item.get("actual_qty", 0)),
                            "reserved_qty": float(item.get("reserved_qty", 0)),
                            "ordered_qty": float(item.get("ordered_qty", 0)),
                            "available_qty": float(item.get("available_qty", 0)),
                            "stock_uom": cstr(item.get("stock_uom", "")),
                            "last_sync": now_datetime()
                        })
                        external_stock.insert(ignore_permissions=True)
                        inserted_count += 1
                        
                    except Exception as item_error:
                        frappe.log_error(
                            title="External Stock Insert Error",
                            message=f"Failed to insert item {item.get('item_code')}: {str(item_error)}"
                        )
                        continue
                
                frappe.db.commit()
                
                # Update log
                log_doc.status = "Success"
                log_doc.items_count = inserted_count
                log_doc.error_message = None
                log_doc.response_data = json.dumps({
                    "received_count": len(stock_data),
                    "inserted_count": inserted_count,
                    "timestamp": data.get("timestamp") if isinstance(data, dict) else None
                })
                log_doc.save(ignore_permissions=True)
                
                # Update site status
                site.last_sync_time = now_datetime()
                site.connection_status = "Connected"
                site.last_sync_count = inserted_count
                site.save(ignore_permissions=True)
                
                return {
                    "success": True,
                    "count": inserted_count,
                    "received": len(stock_data),
                    "message": f"Successfully synchronized {inserted_count} items",
                    "site": site_name
                }
                
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON response: {str(e)}"
                log_doc.status = "Failed"
                log_doc.error_message = error_msg
                log_doc.response_data = response.text[:1000] if response.text else ""
                log_doc.save(ignore_permissions=True)
                
                return {
                    "success": False,
                    "error": error_msg,
                    "raw_response": response.text[:500],
                    "site": site_name
                }
                
        else:
            # HTTP error
            error_details = f"HTTP {response.status_code}"
            try:
                error_data = response.json()
                if "message" in error_data:
                    error_details += f": {error_data['message']}"
                elif "exc" in error_data:
                    error_details += f": {error_data['exc']}"
            except:
                error_details += f": {response.text[:500]}"
            
            log_doc.status = "Failed"
            log_doc.error_message = error_details
            if response.text:
                log_doc.response_data = response.text[:1000]
            log_doc.save(ignore_permissions=True)
            
            site.connection_status = "Failed"
            site.save(ignore_permissions=True)
            
            return {
                "success": False,
                "error": error_details,
                "status_code": response.status_code,
                "site": site_name
            }
            
    except Timeout as e:
        error_msg = f"Request timeout after {timeout} seconds"
        if log_doc:
            log_doc.status = "Failed"
            log_doc.error_message = error_msg
            log_doc.save(ignore_permissions=True)
        
        if 'site' in locals():
            site.connection_status = "Failed"
            site.save(ignore_permissions=True)
        
        frappe.log_error(
            title="Stock Sync Timeout",
            message=f"Timeout fetching from {site_name}: {str(e)}"
        )
        
        return {
            "success": False,
            "error": error_msg,
            "type": "timeout",
            "site": site_name
        }
        
    except SSLError as e:
        error_msg = f"SSL Error: {str(e)}"
        if log_doc:
            log_doc.status = "Failed"
            log_doc.error_message = error_msg
            log_doc.save(ignore_permissions=True)
        
        if 'site' in locals():
            site.connection_status = "Failed"
            site.save(ignore_permissions=True)
        
        return {
            "success": False,
            "error": error_msg,
            "type": "ssl_error",
            "suggestion": "Try enabling 'Disable SSL Verification' in site connection settings",
            "site": site_name
        }
        
    except ConnectionError as e:
        error_msg = f"Connection Error: {str(e)}"
        if log_doc:
            log_doc.status = "Failed"
            log_doc.error_message = error_msg
            log_doc.save(ignore_permissions=True)
        
        if 'site' in locals():
            site.connection_status = "Failed"
            site.save(ignore_permissions=True)
        
        return {
            "success": False,
            "error": error_msg,
            "type": "connection_error",
            "site": site_name
        }
        
    except RequestException as e:
        error_msg = f"Request Exception: {str(e)}"
        if log_doc:
            log_doc.status = "Failed"
            log_doc.error_message = error_msg
            log_doc.save(ignore_permissions=True)
        
        if 'site' in locals():
            site.connection_status = "Failed"
            site.save(ignore_permissions=True)
        
        frappe.log_error(
            title="Stock Sync Request Error",
            message=f"Error fetching from {site_name}: {str(e)}"
        )
        
        return {
            "success": False,
            "error": error_msg,
            "type": "request_error",
            "site": site_name
        }
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        if log_doc:
            log_doc.status = "Failed"
            log_doc.error_message = error_msg
            log_doc.save(ignore_permissions=True)
        
        if 'site' in locals():
            site.connection_status = "Failed"
            site.save(ignore_permissions=True)
        
        frappe.log_error(
            title="Stock Sync Unexpected Error",
            message=f"Unexpected error fetching from {site_name}:\n{traceback.format_exc()}"
        )
        
        return {
            "success": False,
            "error": error_msg,
            "type": "unexpected_error",
            "site": site_name
        }

@frappe.whitelist()
def fetch_all_sites(warehouse=None):
    """
    Fetch from all active sites
    """
    try:
        active_sites = frappe.get_all("Site Connection",
                                     filters={"is_active": 1},
                                     fields=["name", "site_name"])
        
        if not active_sites:
            return {
                "success": False,
                "error": "No active sites found"
            }
        
        results = []
        successful = 0
        failed = 0
        
        for site in active_sites:
            result = fetch_from_site(site.name, warehouse=warehouse)
            
            results.append({
                "site": site.site_name,
                "site_name": site.name,
                "success": result.get("success"),
                "count": result.get("count", 0),
                "received": result.get("received", 0),
                "error": result.get("error"),
                "type": result.get("type")
            })
            
            if result.get("success"):
                successful += 1
            else:
                failed += 1
        
        return {
            "success": True,
            "results": results,
            "summary": {
                "total_sites": len(active_sites),
                "successful": successful,
                "failed": failed
            }
        }
        
    except Exception as e:
        frappe.log_error(
            title="Bulk Sync Error",
            message=f"Error in fetch_all_sites:\n{traceback.format_exc()}"
        )
        return {
            "success": False,
            "error": str(e)
        }