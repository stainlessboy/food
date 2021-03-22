# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"
    contract_id = fields.Many2one('sale.contract', 'Contract', copy=False, check_company=True)
    is_subcontract = fields.Boolean(default=False)
    subcontract_type = fields.Many2one('sale.subcontract.type', 'Subcontract Type', copy=False)

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
        })

    def update_existing_contracts(self):
        """
        Update contracts already linked to the order by updating or creating lines.

        :rtype: list(integer)
        :return: ids of modified contracts
        """
        res = []
        for order in self:
            if order.contract_id and order.contract_id.update_contract_lines:
                res.append(order.contract_id)
            else:
                continue

            contract = order.contract_id
            contract_lines = order.order_line

            contract.write({'contract_line_ids': [(5, 0, 0)]})
            contract.write({'contract_line_ids': [self._prepare_contract_line_data(line) for line in contract_lines]})

            subcontract_count = self.env['sale.subcontract'].search_count([
                ('contract_id', '=', contract.id),
                ('sale_order_id', '=', order.id),
            ])
            if order.is_subcontract and subcontract_count == 0:
                self.env['sale.subcontract'].create({
                    'contract_id': contract.id,
                    'sale_order_id': order.id,
                    'subcontract_type': order.subcontract_type.id,
                    'name': self.env['sale.subcontract'].search_count([('contract_id', '=', contract.id)]) + 1
                })

        return res

    def _action_confirm(self):
        """Update and/or create subscriptions on order confirmation."""
        res = super(SaleOrder, self)._action_confirm()
        self.update_existing_contracts()
        return res

    def action_confirm(self):
        if self.filtered(lambda s: not s.contract_id):
            raise UserError(_('Cannot confirm order without contract'))
        res = super(SaleOrder, self).action_confirm()
        return res

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        invoice_vals['contract_id'] = self.contract_id
        return invoice_vals
