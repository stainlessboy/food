# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Sale Contracts',
    'version': '14.0.1',
    'category': 'Sales',
    'summary': 'Sale Contracts',

    'author': 'Colibri',
    'website': 'https://clbr.uz',
    'depends': [
        'sale',
    ],
    'data': [
        'data/sale_contract_data.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/sale_contract_views.xml',
        'views/res_partner_views.xml',
        'security/ir.model.access.csv'
    ],
    'qweb': [
    ],
    'application': True,
}
