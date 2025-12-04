frappe.listview_settings['Stock Sync Log'] = {
    add_fields: ["status", "site", "items_count"],
    get_indicator: function(doc) {
        // Color indicators based on status
        var colors = {
            "Success": "green",
            "Failed": "red",
            "In Progress": "orange",
            "Partial": "yellow"
        };
        return [__(doc.status), colors[doc.status] || "blue", "status,=," + doc.status];
    },
    
    onload: function(listview) {
        // Add bulk retry button
        listview.page.add_menu_item(__('Retry Failed Syncs'), function() {
            let failed_syncs = listview.get_checked_items().filter(doc => doc.status === 'Failed');
            
            if (failed_syncs.length === 0) {
                frappe.msgprint(__('No failed syncs selected'));
                return;
            }
            
            frappe.confirm(
                __('Retry {0} failed sync(s)?', [failed_syncs.length]),
                function() {
                    // Yes - retry
                    failed_syncs.forEach(doc => {
                        frappe.call({
                            method: 'stock_sync.api.fetch_from_site',
                            args: { site_name: doc.site },
                            callback: function(r) {
                                if (!r.exc) {
                                    frappe.show_alert(__('Retrying sync for {0}', [doc.site]));
                                }
                            }
                        });
                    });
                    
                    // Refresh after 2 seconds
                    setTimeout(() => listview.refresh(), 2000);
                }
            );
        });
        
        // Add filter by site button
        listview.page.add_menu_item(__('Filter by Site'), function() {
            let sites = [...new Set(listview.data.map(doc => doc.site))].sort();
            
            let dialog = new frappe.ui.Dialog({
                title: __('Filter by Site'),
                fields: [
                    {
                        label: __('Site'),
                        fieldname: 'site',
                        fieldtype: 'Select',
                        options: sites
                    }
                ],
                primary_action_label: __('Filter'),
                primary_action(values) {
                    if (values.site) {
                        listview.filter_area.set_filter_value('site', values.site);
                    }
                    dialog.hide();
                }
            });
            
            dialog.show();
        });
    },
        items_count: function(value) {
        if (value > 0) {
            return `<span class="badge badge-info">${value} items</span>`;
        }
        return value;
    },
    
    sync_date: function(value) {
        if (value) {
            return frappe.datetime.prettyDate(value);
        }
        return value;
    },
    button: {
        // Add custom button to each row
        show(doc) {
            return doc.status === 'Failed';
        },
        get_label() {
            return __('Retry');
        },
        get_description() {
            return __('Retry this sync');
        },
        action(doc) {
            frappe.call({
                method: 'stock_sync.api.fetch_from_site',
                args: { site_name: doc.site },
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert(__('Sync retried for {0}', [doc.site]));
                        frappe.route_options = {
                            site: doc.site
                        };
                        frappe.set_route('List', 'Stock Sync Log');
                    }
                }
            });
        }
    }
};