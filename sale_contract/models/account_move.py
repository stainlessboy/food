# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"
    contract_id = fields.Many2one('sale.contract', 'Contract', copy=False, check_company=True)
