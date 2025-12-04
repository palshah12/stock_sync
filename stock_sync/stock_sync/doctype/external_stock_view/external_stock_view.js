// Copyright (c) 2025, Pal Shah and contributors
// For license information, please see license.txt

frappe.ui.form.on('External Stock View', {
    refresh: function(frm) {
        // Add fetch button in list view
        if (!frm.is_new()) {
            frm.add_custom_button(__('Refresh from Source'), function() {
                frappe.call({
                    method: 'stock_sync.api.fetch_partner_stock',
                    args: {
                        site_name: frm.doc.source_site
                    },
                    callback: function(r) {
                        if (r.message.success) {
                            frappe.show_alert({
                                message: __('Refreshed {0} items', [r.message.count]),
                                indicator: 'green'
                            });
                            frappe.set_route('List', 'External Stock View');
                        }
                    }
                });
            });
        }
    }
});

// List view button
frappe.listview_settings['External Stock View'] = {
    add_fields: ["source_site", "last_sync"],
    get_indicator: function(doc) {
        // Show age of data
        var hours = frappe.datetime.get_hour_diff(frappe.datetime.now_datetime(), doc.last_sync);
        if (hours > 24) {
            return [__("Stale"), "red", "last_sync,<,Now"];
        } else if (hours > 6) {
            return [__("Old"), "orange", "last_sync,<,Now"];
        } else {
            return [__("Fresh"), "green", "last_sync,<,Now"];
        }
    },
    
    onload: function(listview) {
        // Add bulk refresh button
        listview.page.add_menu_item(__('Refresh All Sites'), function() {
            frappe.call({
                method: 'stock_sync.api.refresh_all_sites',
                callback: function(r) {
                    if (r.message.success) {
                        listview.refresh();
                    }
                }
            });
        });
    }
};
