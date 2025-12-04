import frappe
import requests
from frappe.model.document import Document

class SiteConnection(Document):
    @frappe.whitelist()
    def test_connection(self):
        """Test connection to the site"""
        try:
            headers = {
                "Authorization": f"token {self.api_key}:{self.api_secret or ''}"
            }
            
            response = requests.get(
                f"{self.site_url}/api/method/frappe.auth.get_logged_user",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                self.connection_status = "Connected"
                self.save()
                return {"success": True, "message": "Connection successful"}
            else:
                self.connection_status = "Failed"
                self.save()
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            self.connection_status = "Failed"
            self.save()
            frappe.log_error(frappe.get_traceback(), "Connection Test Failed")
            return {"success": False, "error": str(e)}