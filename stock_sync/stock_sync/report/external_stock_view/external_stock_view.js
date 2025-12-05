// Copyright (c) 2025, Pal Shah and contributors
// For license information, please see license.txt

// frappe.query_reports["External Stock View"] = {
// 	"filters": [

// 	]
// };

// stock_sync/report/external_stock_view/external_stock_view.js

frappe.query_reports["External Stock View"] = {
    "filters": [
        {
            "fieldname": "source_site",
            "label": __("Source Site"),
            "fieldtype": "Link",
            "options": "Site Connection",
            "width": "100"
        },
        {
            "fieldname": "item_code",
            "label": __("Item Code"),
            "fieldtype": "Data",
            "width": "100"
        },
        {
            "fieldname": "warehouse",
            "label": __("Warehouse"),
            "fieldtype": "Data",
            "width": "100"
        },
        {
            "fieldname": "last_sync_from",
            "label": __("Last Sync From"),
            "fieldtype": "Date",
            "width": "80",
            "default": frappe.datetime.add_days(frappe.datetime.get_today(), -7)
        },
        {
            "fieldname": "last_sync_to",
            "label": __("Last Sync To"),
            "fieldtype": "Date",
            "width": "80",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "show_only_available",
            "label": __("Show Only Available Stock"),
            "fieldtype": "Check",
            "default": 0
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        // Color code based on available quantity
        if (column.fieldname == "available_qty") {
            if (data.available_qty <= 0) {
                value = `<span style="color: red; font-weight: bold;">${value}</span>`;
            } else if (data.available_qty < 5) {
                value = `<span style="color: orange; font-weight: bold;">${value}</span>`;
            } else {
                value = `<span style="color: green; font-weight: bold;">${value}</span>`;
            }
        }
        
        // Color code for last sync time
        if (column.fieldname == "last_sync") {
            var sync_date = frappe.datetime.str_to_obj(data.last_sync);
            var now = frappe.datetime.str_to_obj(frappe.datetime.now_datetime());
            var diff_hours = frappe.datetime.get_hour_diff(now, sync_date);
            
            if (diff_hours > 24) {
                value = `<span style="color: red; font-weight: bold;">${value}</span>`;
            } else if (diff_hours > 12) {
                value = `<span style="color: orange; font-weight: bold;">${value}</span>`;
            } else {
                value = `<span style="color: green; font-weight: bold;">${value}</span>`;
            }
        }
        
        // Make item code clickable
        if (column.fieldname == "item_code" && data.item_code) {
            value = `<a href="/app/item/${data.item_code}" style="text-decoration: none;">${value}</a>`;
        }
        
        return value;
    },
    
    "onload": function(report) {
        // Add custom button to refresh data from sites
        report.page.add_inner_button(__("Refresh All Sites"), function() {
            frappe.call({
                method: "stock_sync.api.fetch_all_sites",
                args: {},
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __("Refreshed {0} sites. {1} successful, {2} failed", 
                                [r.message.summary.total_sites, 
                                 r.message.summary.successful, 
                                 r.message.summary.failed]),
                            indicator: "green"
                        });
                        report.refresh();
                    } else {
                        frappe.msgprint({
                            title: __("Refresh Failed"),
                            message: r.message.error || __("Unknown error"),
                            indicator: "red"
                        });
                    }
                },
                error: function(e) {
                    frappe.msgprint({
                        title: __("Error"),
                        message: e.message,
                        indicator: "red"
                    });
                }
            });
        }, __("Actions"));
        
        // Add custom button to refresh specific site
        report.page.add_inner_button(__("Refresh Selected Site"), function() {
            var filters = report.get_values();
            if (filters.source_site) {
                frappe.call({
                    method: "stock_sync.api.fetch_from_site",
                    args: {
                        site_name: filters.source_site
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __("Refreshed {0} items from {1}", 
                                    [r.message.count, filters.source_site]),
                                indicator: "green"
                            });
                            report.refresh();
                        } else {
                            frappe.msgprint({
                                title: __("Refresh Failed"),
                                message: r.message.error || __("Unknown error"),
                                indicator: "red"
                            });
                        }
                    }
                });
            } else {
                frappe.msgprint({
                    title: __("Warning"),
                    message: __("Please select a Source Site first"),
                    indicator: "orange"
                });
            }
        }, __("Actions"));
    }
};