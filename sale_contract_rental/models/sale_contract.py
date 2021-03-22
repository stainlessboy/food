# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from odoo import api, fields, models, _
_logger = logging.getLogger(__name__)


class SaleContract(models.Model):
    _inherit = "sale.contract"

    invoice_amount_type = fields.Selection([
        ('period', 'Rental line period'),
        ('full', 'Full line amount'),
    ], string='Invoice amount', default='period')

    def _prepare_invoice_line(self, line, fiscal_position):
        company = self.env.company or line.analytic_account_id.company_id
        tax_ids = line.product_id.taxes_id.filtered(lambda t: t.company_id == company)
        if fiscal_position:
            tax_ids = self.env['account.fiscal.position'].browse(fiscal_position).map_tax(tax_ids)

        price_unit = line.price_unit

        if hasattr(line, 'is_rental') and line.is_rental and line.contract_id.invoice_amount_type == 'period':
            if hasattr(line, 'pickup_date') and hasattr(line, 'return_date'):
                pricing_id = line.product_id._get_best_pricing_rule(
                    pickup_date=line.pickup_date,
                    return_date=line.return_date,
                    pricelist=line.contract_id.pricelist_id,
                    company=line.contract_id.company_id
                )
                if pricing_id:
                    price_unit = pricing_id.price

        return {
            'name': line.product_id.name,
            'price_unit': price_unit or 0.0,
            'discount': line.discount,
            'quantity': line.quantity,
            'product_uom_id': line.uom_id.id,
            'product_id': line.product_id.id,
            'tax_ids': [(6, 0, tax_ids.ids)],
        }


class SaleContractLine(models.Model):
    _inherit = "sale.contract.line"

    is_rental = fields.Boolean(default=False)
    pickup_date = fields.Datetime(string="Pickup")
    return_date = fields.Datetime(string="Return")
