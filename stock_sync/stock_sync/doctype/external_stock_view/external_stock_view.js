// stock_sync/doctypes/external_stock_view/external_stock_view.js
frappe.ui.form.on('External Stock View', {
    refresh: function(frm) {
        if (frm.doc.source_site) {
            frm.add_custom_button(__('Refresh from Source'), function() {
                frappe.call({
                    method: 'stock_sync.api.fetch_from_site',
                    args: {
                        site_name: frm.doc.source_site
                    },
                    callback: function(r) {
                        if (r.message.success) {
                            frappe.show_alert(__('Refreshed successfully'));
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
    }
});