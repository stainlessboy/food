# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _prepare_contract_line_data(self, order_line):
        """Prepare a dictionnary of values to add lines to a contract."""

        return (0, False, {
            'product_id': order_line.product_id.id,
            'name': order_line.name,
            'quantity': order_line.product_uom_qty,
            'uom_id': order_line.product_uom.id,
            'price_unit': order_line.price_unit,
            'tax_id': order_line.tax_id,
            'discount': order_line.discount,
            'is_rental': order_line.is_rental if hasattr(order_line, 'is_rental') else False,
            'pickup_date': order_line.pickup_date if hasattr(order_line, 'pickup_date') else False,
            'return_date': order_line.return_date if hasattr(order_line, 'return_date') else False,
        })
