// Copyright (c) 2025, Pal Shah and contributors
// For license information, please see license.txt

// stock_sync/doctypes/site_connection/site_connection.js
frappe.ui.form.on('Site Connection', {
    refresh: function(frm) {
        // Add Test Connection button
        frm.add_custom_button(__('Test Connection'), function() {
            frm.call('test_connection').then(r => {
                if (r.message && r.message.success) {
                    frappe.show_alert({
                        message: __('Connection successful'),
                        indicator: 'green'
                    });
                    frm.reload_doc();
                } else {
                    frappe.msgprint({
                        title: __('Connection Failed'),
                        indicator: 'red',
                        message: r.message.error || __('Unknown error')
                    });
                }
            });
        }, __('Actions'));
        
        // Add Fetch Stock button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Fetch Stock'), function() {
                frappe.call({
                    method: 'stock_sync.api.fetch_from_site',
                    args: {
                        site_name: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('Fetched {0} items', [r.message.count]),
                                indicator: 'green'
                            });
                        } else {
                            frappe.msgprint({
                                title: __('Fetch Failed'),
                                indicator: 'red',
                                message: r.message.error || __('Unknown error')
                            });
                        }
                    }
                });
            }, __('Actions'));
        }
    }
});
