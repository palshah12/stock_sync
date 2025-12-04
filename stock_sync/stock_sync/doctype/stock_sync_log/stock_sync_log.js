// stock_sync/doctypes/stock_sync_log/stock_sync_log.js
frappe.ui.form.on('Stock Sync Log', {
    refresh: function(frm) {
        // Add Retry button for failed syncs
        if (frm.doc.status === 'Failed') {
            frm.add_custom_button(__('Retry Sync'), function() {
                frappe.call({
                    method: 'stock_sync.api.fetch_from_site',
                    args: {
                        site_name: frm.doc.site
                    },
                    callback: function(r) {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __('Sync retried successfully'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        } else {
                            frappe.msgprint({
                                title: __('Retry Failed'),
                                indicator: 'red',
                                message: r.message.error || __('Unknown error')
                            });
                        }
                    }
                });
            }, __('Actions'));
        }
        
        // Add View External Stock button
        if (frm.doc.site) {
            frm.add_custom_button(__('View External Stock'), function() {
                frappe.set_route('List', 'External Stock View', {
                    source_site: frm.doc.site
                });
            }, __('Actions'));
        }
        
        // Add Copy Error button for failed syncs
        if (frm.doc.status === 'Failed' && frm.doc.error_message) {
            frm.add_custom_button(__('Copy Error'), function() {
                navigator.clipboard.writeText(frm.doc.error_message).then(function() {
                    frappe.show_alert(__('Error copied to clipboard'));
                });
            }, __('Actions'));
        }
    },
    
    onload: function(frm) {
        // Set default sync date to now if new
        if (frm.is_new()) {
            frm.set_value('sync_date', frappe.datetime.now_datetime());
        }
    }
});

// List view enhancements


// Custom formatter for list view
