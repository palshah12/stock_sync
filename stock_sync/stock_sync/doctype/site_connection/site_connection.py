# stock_sync/stock_sync/doctype/site_connection/site_connection.py
import frappe
import requests
from frappe.model.document import Document
from frappe import _
from requests.exceptions import RequestException, Timeout, SSLError, ConnectionError
import json
import ssl
from urllib.parse import urljoin

class SiteConnection(Document):
    def validate(self):
        """Validate site connection settings"""
        if not self.site_url:
            frappe.throw(_("Site URL is required"))
        
        # Ensure URL ends with /
        if not self.site_url.endswith('/'):
            self.site_url = self.site_url + '/'
    
    @frappe.whitelist()
    def test_connection(self):
        """Test connection to the site with detailed error handling"""
        try:
            if not self.site_url:
                return {
                    "success": False,
                    "error": "Site URL is required"
                }
            
            if not self.api_key:
                return {
                    "success": False,
                    "error": "API Key is required"
                }
            
            # Prepare headers
            headers = {
                "Authorization": f"token {self.api_key}:{self.api_secret or ''}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Prepare URL
            endpoint = urljoin(self.site_url, "api/method/frappe.auth.get_logged_user")
            
            # SSL verification
            verify_ssl = not self.get("disable_ssl_verification", False)
            timeout = self.get("timeout") or 30
            
            # Suppress SSL warnings if verification is disabled
            if not verify_ssl:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Make request
            response = requests.get(
                endpoint,
                headers=headers,
                timeout=timeout,
                verify=verify_ssl
            )
            
            # Check response
            if response.status_code == 200:
                data = response.json()
                if data and data.get("message"):
                    self.connection_status = "Connected"
                    self.save(ignore_permissions=True)
                    frappe.db.commit()
                    
                    return {
                        "success": True,
                        "message": "Connection successful",
                        "user": data.get("message")
                    }
                else:
                    self.connection_status = "Failed"
                    self.save(ignore_permissions=True)
                    
                    return {
                        "success": False,
                        "error": "Invalid response format",
                        "details": data
                    }
            else:
                self.connection_status = "Failed"
                self.save(ignore_permissions=True)
                
                # Try to parse error message
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_msg += f": {error_data['message']}"
                    elif "exc" in error_data:
                        error_msg += f": {error_data['exc']}"
                except:
                    error_msg += f": {response.text[:200]}"
                
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code
                }
                
        except Timeout:
            self.connection_status = "Failed"
            self.save(ignore_permissions=True)
            
            return {
                "success": False,
                "error": "Connection timeout. Please check network or increase timeout.",
                "type": "timeout"
            }
            
        except SSLError as e:
            self.connection_status = "Failed"
            self.save(ignore_permissions=True)
            
            return {
                "success": False,
                "error": f"SSL certificate error: {str(e)}",
                "type": "ssl_error",
                "suggestion": "You can disable SSL verification in connection settings"
            }
            
        except ConnectionError as e:
            self.connection_status = "Failed"
            self.save(ignore_permissions=True)
            
            return {
                "success": False,
                "error": f"Cannot connect to server: {str(e)}",
                "type": "connection_error"
            }
            
        except RequestException as e:
            self.connection_status = "Failed"
            self.save(ignore_permissions=True)
            
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "type": "request_error"
            }
            
        except Exception as e:
            self.connection_status = "Failed"
            self.save(ignore_permissions=True)
            
            frappe.log_error(
                title="Connection Test Failed",
                message=frappe.get_traceback()
            )
            
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "type": "unexpected_error"
            }