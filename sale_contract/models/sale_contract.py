# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
import logging

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import format_datetime, format_date, float_compare

from num2words.lang_RU import Num2Word_RU
from num2words.lang_EN import Num2Word_EN

_logger = logging.getLogger(__name__)

Num2Word_RU.CURRENCY_FORMS['USD'] = (('доллар', 'доллара', 'долларов'), ('цент', 'центы', 'центов'))
Num2Word_RU.CURRENCY_FORMS['UZS'] = (('сум', 'сума', 'сумов'), ('тиин', 'тиины', 'тиинов'))
Num2Word_EN.CURRENCY_FORMS['UZS'] = (('sum', 'sum', 'sum'), ('tiin', 'tiin', 'tiin'))


class SaleContract(models.Model):
    _name = "sale.contract"
    _description = "Contract"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True

    def _get_default_pricelist(self):
        return self.env['product.pricelist'].search([('currency_id', '=', self.env.company.currency_id.id)], limit=1).id

    name = fields.Char(string='Number', required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True, copy=False, index=True, tracking=3, default='draft')

    date_confirmed = fields.Datetime(string='Confirmed Date', required=True, readonly=True, index=True, states={'draft': [('readonly', False)], 'done': [('readonly', False)]}, copy=False, default=fields.Datetime.now)

    company_id = fields.Many2one('res.company', string="Company", default=lambda s: s.env.company, required=True)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True, auto_join=True, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    date_start = fields.Date(string='Start Date', default=fields.Date.today)
    date_end = fields.Date(string='End Date', tracking=True)

    update_contract_lines = fields.Boolean(
        default=True,
        tracking=True,
        string='Update contract lines from confirmed SO'
    )

    is_recurring = fields.Boolean(default=False, tracking=True)
    recurring_rule_type = fields.Selection([('daily', 'Days'), ('weekly', 'Weeks'),
                                            ('monthly', 'Months'), ('yearly', 'Years'), ],
                                           string='Recurrence', required=True,
                                           help="Invoice automatically repeat at specified interval",
                                           default='monthly', tracking=True)
    recurring_interval = fields.Integer(string="Invoicing Period", help="Repeat every (Days/Week/Month/Year)",
                                        required=True, default=1, tracking=True)

    recurring_next_date = fields.Date(string='Date of Next Invoice', default=fields.Date.today,
                                      help="The next invoice will be created on this date then the period will be extended.")
    recurring_invoice_day = fields.Integer('Recurring Invoice Day', copy=False,
                                           default=lambda e: fields.Date.today().day)

    description = fields.Text()
    user_id = fields.Many2one('res.users', string='Salesperson', tracking=True, default=lambda self: self.env.user)

    invoice_count = fields.Integer(compute='_compute_invoice_count')
    country_id = fields.Many2one('res.country', related='partner_id.country_id', store=True, readonly=False, compute_sudo=True)

    pricelist_id = fields.Many2one('product.pricelist',
                                   domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
                                   string='Pricelist', default=_get_default_pricelist, required=True,
                                   check_company=True)
    currency_id = fields.Many2one('res.currency', related='pricelist_id.currency_id', string='Currency', readonly=True)
    contract_line_ids = fields.One2many('sale.contract.line', 'contract_id', string='Contract Lines', copy=True)

    sale_order_ids = fields.One2many('sale.order', 'contract_id', string='Orders')
    sale_order_count = fields.Integer(compute='_compute_sale_order_count', readonly=True)

    contract_total = fields.Float(compute='_compute_contract_total', string="Contract Price", store=True, tracking=True, digits='Account')
    contract_tax_total = fields.Float(compute='_compute_contract_tax_total', string="Contract Taxes", digits='Account')

    subcontract_ids = fields.One2many('sale.subcontract', 'contract_id', string='Subcontracts', copy=True)

    external_id = fields.Char(required=False)
    external_balance = fields.Float(required=False)

    @api.depends('contract_line_ids', 'contract_line_ids.quantity', 'contract_line_ids.price_subtotal')
    def _compute_contract_total(self):
        for account in self:
            account.contract_total = sum(line.price_total for line in account.contract_line_ids)

    @api.depends('contract_line_ids', 'contract_line_ids.quantity', 'contract_line_ids.price_subtotal')
    def _compute_contract_tax_total(self):
        for account in self:
            account.contract_tax_total = sum(line.price_tax for line in account.contract_line_ids)

    def _compute_sale_order_count(self):
        for contract in self:
            contract.sale_order_count = len(contract.sale_order_ids)

    def _compute_invoice_count(self):
        Invoice = self.env['account.move']
        can_read = Invoice.check_access_rights('read', raise_exception=False)
        for contract in self:
            contract.invoice_count = can_read and Invoice.search_count([('contract_id', '=', contract.id)]) or 0

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id.user_id:
            self.user_id = self.partner_id.user_id

    def name_get(self):
        res = []
        for contract in self.filtered('id'):
            contract_name = _('№%s of %s') % (contract.name, format_date(self.env, contract.date_start))
            res.append((contract.id, contract_name))
        return res

    def _get_forbidden_state_confirm(self):
        return {'done', 'cancel'}

    def _get_forbidden_state_done(self):
        return {'draft', 'cancel'}

    def action_confirm(self):
        if self._get_forbidden_state_confirm() & set(self.mapped('state')):
            raise UserError(_(
                'It is not allowed to confirm an contract in the following states: %s'
            ) % (', '.join(self._get_forbidden_state_confirm())))

        self.write({
            'state': 'confirmed',
            'date_confirmed': fields.Datetime.now()
        })

    def action_done(self):
        if self._get_forbidden_state_done() & set(self.mapped('state')):
            raise UserError(_(
                'It is not allowed to done an contract in the following states: %s'
            ) % (', '.join(self._get_forbidden_state_done())))

        self.write({
            'state': 'done',
        })

    def action_cancel(self):
        return self.write({'state': 'cancel'})

    def action_draft(self):
        orders = self.filtered(lambda s: s.state in ['cancel', 'confirmed'])
        return orders.write({
            'state': 'draft',
        })

    @api.model
    def _get_recurring_next_date(self, interval_type, interval, current_date, recurring_invoice_day):
        """
        This method is used for calculating next invoice date for a contract
        :params interval_type: type of interval i.e. yearly, monthly, weekly etc.
        :params interval: number of interval i.e. 2 week, 1 month, 6 month, 1 year etc.
        :params current_date: date from which next invoice date is to be calculated
        :params recurring_invoice_day: day on which next invoice is to be generated in future
        :returns: date on which invoice will be generated
        """
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        interval_type = periods[interval_type]
        recurring_next_date = fields.Date.from_string(current_date) + relativedelta(**{interval_type: interval})
        if interval_type == 'months':
            last_day_of_month = recurring_next_date + relativedelta(day=31)
            if last_day_of_month.day >= recurring_invoice_day:
                # In cases where the next month does not have same day as of previous recurrent invoice date, we set the last date of next month
                # Example: current_date is 31st January then next date will be 28/29th February
                return recurring_next_date.replace(day=recurring_invoice_day)
            # In cases where the contract was created on the last day of a particular month then it should stick to last day for all recurrent monthly invoices
            # Example: 31st January, 28th February, 31st March, 30 April and so on.
            return last_day_of_month
        # Return the next day after adding interval
        return recurring_next_date

    def _prepare_invoice_data(self):
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_("You must first select a Customer for Subscription %s!", self.name))

        company = self.env.company or self.company_id

        journal = self.env['account.journal'].search([('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
        if not journal:
            raise UserError(_('Please define a sale journal for the company "%s".') % (company.name or '', ))

        next_date = self.recurring_next_date
        if not next_date:
            raise UserError(_('Please define Date of Next Invoice of "%s".') % (self.display_name,))

        recurring_next_date = self._get_recurring_next_date(self.recurring_rule_type, self.recurring_interval, next_date, next_date.day)

        end_date = fields.Date.from_string(recurring_next_date) - relativedelta(days=1)     # remove 1 day as normal people thinks in term of inclusive ranges.
        addr = self.partner_id.address_get(['delivery', 'invoice'])

        sale_order = self.env['sale.order'].search([('contract_id', 'in', self.ids)], order="id desc", limit=1)
        use_sale_order = sale_order and sale_order.partner_id == self.partner_id
        partner_id = sale_order.partner_id.id if use_sale_order else self.partner_id.id or addr['invoice']
        partner_shipping_id = sale_order.partner_id.id if use_sale_order else self.partner_id.id or addr['delivery']
        fpos = self.env['account.fiscal.position'].with_company(company).get_fiscal_position(self.partner_id.id, partner_shipping_id)

        narration = _("This invoice covers the following period: %s - %s") % (format_date(self.env, next_date), format_date(self.env, end_date))
        if self.env['ir.config_parameter'].sudo().get_param('account.use_invoice_terms') and self.company_id.invoice_terms:
            narration += '\n' + self.company_id.invoice_terms
        res = {
            'move_type': 'out_invoice',
            'invoice_date': next_date,
            'partner_id': partner_id,
            'contract_id': self.id,
            'partner_shipping_id': partner_shipping_id,
            'currency_id': self.pricelist_id.currency_id.id,
            'journal_id': journal.id,
            'invoice_origin': self.name,
            'fiscal_position_id': fpos.id,
            'invoice_payment_term_id': self.partner_id.property_payment_term_id.id,
            'narration': narration,
            'invoice_user_id': self.user_id.id,
            'partner_bank_id': company.partner_id.bank_ids.filtered(lambda b: not b.company_id or b.company_id == company)[:1].id,
        }

        return res

    def _prepare_invoice_line(self, line, fiscal_position):
        company = self.env.company or line.analytic_account_id.company_id
        tax_ids = line.product_id.taxes_id.filtered(lambda t: t.company_id == company)
        if fiscal_position:
            tax_ids = self.env['account.fiscal.position'].browse(fiscal_position).map_tax(tax_ids)

        price_unit = line.price_unit

        return {
            'name': line.product_id.name,
            'price_unit': price_unit or 0.0,
            'discount': line.discount,
            'quantity': line.quantity,
            'product_uom_id': line.uom_id.id,
            'product_id': line.product_id.id,
            'tax_ids': [(6, 0, tax_ids.ids)],
        }

    def _prepare_invoice_lines(self, fiscal_position):
        self.ensure_one()
        return [(0, 0, self._prepare_invoice_line(line, fiscal_position)) for line in self.contract_line_ids]

    def _prepare_invoice(self):
        invoice = self._prepare_invoice_data()
        invoice['invoice_line_ids'] = self._prepare_invoice_lines(invoice['fiscal_position_id'])
        return invoice

    def _recurring_create_invoice(self, automatic=False):
        auto_commit = self.env.context.get('auto_commit', True)
        cr = self.env.cr
        invoices = self.env['account.move']
        current_date = datetime.date.today()

        if len(self) > 0:
            subscriptions = self
        else:
            domain = [('recurring_next_date', '<=', current_date)]
            subscriptions = self.search(domain)

        if subscriptions:
            sub_data = subscriptions.read(fields=['id', 'company_id'])
            for company_id in set(data['company_id'][0] for data in sub_data):
                sub_ids = [s['id'] for s in sub_data if s['company_id'][0] == company_id]
                subs = self.with_company(company_id).with_context(company_id=company_id).browse(sub_ids)
                Invoice = self.env['account.move'].with_context(move_type='out_invoice', company_id=company_id).with_company(company_id)
                for subscription in subs:
                    subscription = subscription[0]
                    if automatic and auto_commit:
                        cr.commit()

                    # if we reach the end date of the subscription then we skip it
                    if automatic and subscription.date_end and subscription.date_end <= current_date:
                        continue

                    # invoice only
                    try:
                        if subscription.date_end and subscription.recurring_next_date >= subscription.date_end:
                            return

                        invoice_values = subscription.with_context(lang=subscription.partner_id.lang)._prepare_invoice()
                        new_invoice = Invoice.create(invoice_values)
                        new_invoice.message_post_with_view(
                            'mail.message_origin_link',
                            values={'self': new_invoice, 'origin': subscription},
                            subtype_id=self.env.ref('mail.mt_note').id)
                        invoices += new_invoice

                        next_date = subscription.recurring_next_date or current_date
                        rule, interval = subscription.recurring_rule_type, subscription.recurring_interval
                        new_date = subscription._get_recurring_next_date(rule, interval, next_date,
                                                                         next_date.day)
                        # When `recurring_next_date` is updated by cron or by `Generate Invoice` action button,
                        # write() will skip resetting `recurring_invoice_day` value based on this context value
                        subscription.with_context(skip_update_recurring_invoice_day=True).write(
                            {'recurring_next_date': new_date})
                        if automatic and auto_commit:
                            cr.commit()
                    except Exception as e:
                        if automatic and auto_commit:
                            cr.rollback()
                            _logger.exception('Fail to create recurring invoice for contract %s', subscription.name)
                        else:
                            raise
        return invoices

    @api.model
    def _cron_recurring_create_invoice(self):
        return self._recurring_create_invoice(automatic=True)

    def action_subscription_invoice(self):
        self.ensure_one()
        invoices = self.env['account.move'].search([('contract_id', 'in', self.ids)])
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action["context"] = {"create": False}
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def recurring_invoice(self):
        self._recurring_create_invoice()
        return self.action_subscription_invoice()


class SaleContractLine(models.Model):
    _name = "sale.contract.line"
    _description = "Contract Line"
    _check_company_auto = True

    product_id = fields.Many2one(
        'product.product', string='Product', check_company=True, required=True)
    categ_id = fields.Many2one(related='product_id.categ_id', required=False, readonly=True)
    contract_id = fields.Many2one('sale.contract', string='Contract', ondelete='cascade')
    company_id = fields.Many2one('res.company', related='contract_id.company_id', stored=True, index=True)
    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(string='Quantity', help="Quantity that will be invoiced.", default=1.0, digits='Product Unit of Measure')
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True, domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', readonly=True)
    price_unit = fields.Float(string='Unit Price', required=True, digits='Product Price')
    discount = fields.Float(string='Discount (%)', digits='Discount')

    tax_id = fields.Many2many('account.tax', string='Taxes', domain=['|', ('active', '=', False), ('active', '=', True)])

    price_subtotal = fields.Float(compute='_compute_amount', string='Subtotal', digits='Account', readonly=True, store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Total Tax', digits='Account', readonly=True, store=True)
    price_total = fields.Float(compute='_compute_amount', string='Total', digits='Account', readonly=True, store=True)

    external_id = fields.Char(required=False)

    @api.depends('quantity', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.contract_id.currency_id, line.quantity, product=line.product_id, partner=line.contract_id.partner_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.onchange('product_id')
    def onchange_product_id(self):
        product = self.product_id
        partner = self.contract_id.partner_id
        if partner.lang:
            product = product.with_context(lang=partner.lang)

        self.name = product.get_product_multiline_description_sale()
        self.uom_id = product.uom_id.id

    @api.onchange('product_id', 'quantity')
    def onchange_product_quantity(self):
        contract = self.contract_id
        company_id = contract.company_id.id
        pricelist_id = contract.pricelist_id.id
        context = dict(self.env.context, company_id=company_id, force_company=company_id, pricelist=pricelist_id,
                       quantity=self.quantity)
        if not self.product_id:
            self.price_unit = 0.0
        else:
            partner = contract.partner_id.with_context(context)
            if partner.lang:
                context.update({'lang': partner.lang})

            product = self.product_id.with_context(context)
            if contract.pricelist_id and contract.pricelist_id.discount_policy == "without_discount":
                if contract.pricelist_id.currency_id != self.product_id.currency_id:
                    self.price_unit = self.product_id.currency_id._convert(
                        self.product_id.lst_price,
                        contract.pricelist_id.currency_id,
                        self.product_id.product_tmpl_id._get_current_company(pricelist=contract.pricelist_id),
                        fields.Date.today()
                    )
                else:
                    self.price_unit = product.lst_price
                if float_compare(self.price_unit, product.price,
                                 precision_rounding=contract.pricelist_id.currency_id.rounding) == 1:
                    self.discount = (self.price_unit - product.price) / self.price_unit * 100
                else:
                    self.discount = 0
            else:
                self.price_unit = product.price

            if not self.uom_id or product.uom_id.category_id.id != self.uom_id.category_id.id:
                self.uom_id = product.uom_id.id
            if self.uom_id.id != product.uom_id.id:
                self.price_unit = product.uom_id._compute_price(self.price_unit, self.uom_id)

    @api.onchange('uom_id')
    def onchange_uom_id(self):
        if not self.uom_id:
            self.price_unit = 0.0
        else:
            return self.onchange_product_quantity()

    @api.model
    def create(self, values):
        if values.get('product_id') and not values.get('name'):
            line = self.new(values)
            line.onchange_product_id()
            values['name'] = line._fields['name'].convert_to_write(line['name'], line)
        return super(SaleContractLine, self).create(values)


class SaleSubContractType(models.Model):
    _name = "sale.subcontract.type"
    name = fields.Char(string='Name', required=True, tracking=True)


class SaleSubContract(models.Model):
    _name = "sale.subcontract"
    contract_id = fields.Many2one('sale.contract', string='Contract', ondelete='cascade')
    sale_order_id = fields.Many2one('sale.order', string='Parent Sale Order', ondelete='cascade')
    subcontract_type = fields.Many2one('sale.subcontract.type', string='Subcontract type')

    name = fields.Char(string='Name', required=True, tracking=True)

    external_id = fields.Integer(required=False)
