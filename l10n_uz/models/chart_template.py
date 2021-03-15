# coding: utf-8
from odoo import models, api, _


class AccountChartTemplate(models.Model):
    _inherit = "account.chart.template"

    @api.model
    def _get_default_bank_journals_data(self):
        if self.env.company.country_id and self.env.company.country_id.code.upper() == 'UZ':
            return [
                {'acc_name': 'Касса организации', 'account_type': 'cash'},
                {'acc_name': 'Расчетные счета', 'account_type': 'bank'}
            ]
        return super(AccountChartTemplate, self)._get_default_bank_journals_data()
