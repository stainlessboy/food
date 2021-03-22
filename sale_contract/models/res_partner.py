# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    contract_count = fields.Integer(compute='_compute_contract_count', string='Contract Count')
    contract_ids = fields.One2many('sale.contract', 'partner_id', 'Contract')

    def _compute_contract_count(self):
        # retrieve all children partners and prefetch 'parent_id' on them
        all_partners = self.with_context(active_test=False).search([('id', 'child_of', self.ids)])
        all_partners.read(['parent_id'])
        _logger.warning(all_partners)
        sale_contract_groups = self.env['sale.contract'].read_group(
            domain=[('partner_id', 'in', all_partners.ids)],
            fields=['partner_id'], groupby=['partner_id']
        )
        _logger.warning(sale_contract_groups)
        partners = self.browse()
        for group in sale_contract_groups:
            partner = self.browse(group['partner_id'][0])
            while partner:
                if partner in self:
                    partner.contract_count += group['partner_id_count']
                    partners |= partner
                partner = partner.parent_id
        (self - partners).contract_count = 0
