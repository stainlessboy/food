# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Sale Rental Contracts',
    'version': '14.0.1',
    'category': 'Sales',
    'summary': 'Contract for Rental SO',

    'author': 'Colibri',
    'website': 'https://clbr.uz',
    'depends': [
        'sale',
        'sale_contract',
        'sale_renting'
    ],
    'data': [
        'views/sale_contract_views.xml',
    ],
    'qweb': [
    ],
    'application': True,
}
