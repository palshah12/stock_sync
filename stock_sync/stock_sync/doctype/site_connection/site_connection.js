// stock_sync/stock_sync/doctype/site_connection/site_connection.js
frappe.ui.form.on('Site Connection', {
    refresh: function(frm) {
        // Add Test Connection button
        frm.add_custom_button(__('Test Connection'), function() {
            frm.dirty();
            frm.save().then(() => {
                frappe.show_alert({
                    message: __('Testing connection...'),
                    indicator: 'blue'
                });
                
                frm.call('test_connection').then(r => {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Connection successful'),
                            indicator: 'green'
                        });
                        frm.reload_doc();
                    } else {
                        let error_msg = r.message.error || __('Unknown error');
                        let error_type = r.message.type || 'unknown';
                        
                        // Show detailed error dialog
                        frappe.msgprint({
                            title: __('Connection Failed'),
                            indicator: 'red',
                            message: `
                                <div style="padding: 15px;">
                                    <h4>${__('Connection Test Failed')}</h4>
                                    <p><strong>${__('Error Type')}:</strong> ${error_type}</p>
                                    <p><strong>${__('Error Message')}:</strong> ${error_msg}</p>
                                    ${r.message.suggestion ? `<p><strong>${__('Suggestion')}:</strong> ${r.message.suggestion}</p>` : ''}
                                    ${r.message.details ? `<p><strong>${__('Details')}:</strong> ${r.message.details}</p>` : ''}
                                </div>
                            `,
                            primary_action: {
                                label: __('Retry'),
                                action: function() {
                                    frm.trigger('refresh');
                                }
                            }
                        });
                    }
                }).catch(e => {
                    frappe.msgprint({
                        title: __('Error'),
                        indicator: 'red',
                        message: e.message || __('Unknown error occurred')
                    });
                });
            });
        }, __('Actions'));
        
        // Add Fetch Stock button
        if (!frm.is_new()) {
            frm.add_custom_button(__('Fetch Stock'), function() {
                frappe.prompt({
                    fieldname: 'warehouse',
                    label: __('Warehouse (Optional)'),
                    fieldtype: 'Link',
                    options: 'Warehouse',
                    description: __('Leave empty to fetch all warehouses')
                }, function(values) {
                    frappe.show_alert({
                        message: __('Fetching stock data...'),
                        indicator: 'blue'
                    });
                    
                    frappe.call({
                        method: 'stock_sync.api.fetch_from_site',
                        args: {
                            site_name: frm.doc.name,
                            warehouse: values.warehouse
                        },
                        callback: function(r) {
                            if (r.message && r.message.success) {
                                frappe.show_alert({
                                    message: __('Successfully fetched {0} items', [r.message.count]),
                                    indicator: 'green'
                                });
                                
                                // Refresh External Stock View list
                                frappe.set_route('List', 'External Stock View', {
                                    source_site: frm.doc.name
                                });
                            } else {
                                frappe.msgprint({
                                    title: __('Fetch Failed'),
                                    indicator: 'red',
                                    message: `
                                        <div style="padding: 15px;">
                                            <h4>${__('Failed to fetch stock')}</h4>
                                            <p><strong>${__('Error')}:</strong> ${r.message.error || __('Unknown error')}</p>
                                            ${r.message.suggestion ? `<p><strong>${__('Suggestion')}:</strong> ${r.message.suggestion}</p>` : ''}
                                            ${r.message.type ? `<p><strong>${__('Error Type')}:</strong> ${r.message.type}</p>` : ''}
                                        </div>
                                    `
                                });
                            }
                        },
                        error: function(e) {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: e.message || __('Unknown error occurred')
                            });
                        }
                    });
                }, __('Fetch Stock'), __('Fetch'));
            }, __('Actions'));
            
            // Add Fetch All Sites button
            frm.add_custom_button(__('Fetch All Sites'), function() {
                frappe.confirm(
                    __('Are you sure you want to fetch stock from all active sites?'),
                    function() {
                        frappe.show_alert({
                            message: __('Fetching from all sites...'),
                            indicator: 'blue'
                        });
                        
                        frappe.call({
                            method: 'stock_sync.api.fetch_all_sites',
                            callback: function(r) {
                                if (r.message && r.message.success) {
                                    let summary = r.message.summary;
                                    frappe.msgprint({
                                        title: __('Bulk Sync Complete'),
                                        indicator: 'green',
                                        message: `
                                            <div style="padding: 15px;">
                                                <h4>${__('Sync Results')}</h4>
                                                <p><strong>${__('Total Sites')}:</strong> ${summary.total_sites}</p>
                                                <p><strong>${__('Successful')}:</strong> ${summary.successful}</p>
                                                <p><strong>${__('Failed')}:</strong> ${summary.failed}</p>
                                            </div>
                                        `,
                                        primary_action: {
                                            label: __('View Logs'),
                                            action: function() {
                                                frappe.set_route('List', 'Stock Sync Log');
                                            }
                                        }
                                    });
                                } else {
                                    frappe.msgprint({
                                        title: __('Bulk Sync Failed'),
                                        indicator: 'red',
                                        message: r.message.error || __('Unknown error')
                                    });
                                }
                            }
                        });
                    }
                );
            }, __('Actions'));
            
            // Add View Sync Logs button
            frm.add_custom_button(__('View Sync Logs'), function() {
                frappe.set_route('List', 'Stock Sync Log', {
                    site: frm.doc.name
                });
            }, __('Actions'));
        }
    },
    
    // Auto-test connection when site URL or API keys change
    site_url: function(frm) {
        if (frm.doc.site_url && frm.doc.api_key) {
            setTimeout(() => {
                if (!frm.is_dirty()) {
                    frm.trigger('test_connection_auto');
                }
            }, 1000);
        }
    },
    
    api_key: function(frm) {
        if (frm.doc.site_url && frm.doc.api_key) {
            setTimeout(() => {
                if (!frm.is_dirty()) {
                    frm.trigger('test_connection_auto');
                }
            }, 1000);
        }
    },
    
    test_connection_auto: function(frm) {
        if (frm.doc.site_url && frm.doc.api_key && !frm.is_new()) {
            frm.call('test_connection', null, null, true).then(r => {
                if (r.message && r.message.success) {
                    frm.set_value('connection_status', 'Connected');
                } else {
                    frm.set_value('connection_status', 'Failed');
                }
                frm.refresh();
            });
        }
    }
});