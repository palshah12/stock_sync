// Copyright (c) 2025, Pal Shah and contributors
// For license information, please see license.txt

// public/js/stock_sync.js
frappe.ready(function() {
    // Add refresh button to workspace
    if ($('#quick-stock-actions').length) {
        $('#quick-stock-actions').html(`
            <button class="btn btn-primary btn-sm" id="refresh-all">
                <i class="fa fa-refresh"></i> Refresh All Sites
            </button>
        `);
        
        $('#refresh-all').click(function() {
            frappe.call({
                method: 'stock_sync.api.fetch_all_sites',
                callback: function(r) {
                    if (r.message.success) {
                        frappe.show_alert(__('All sites refreshed'));
                    }
                }
            });
        });
    }
});
