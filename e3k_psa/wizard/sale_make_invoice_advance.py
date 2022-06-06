# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.osv import expression
from odoo.addons.sale_timesheet_enterprise.models.sale import DEFAULT_INVOICED_TIMESHEET


class ExpensePSA(models.TransientModel):
    _name = "hr.expense.psa"
    _description = "hr.expense.psa"

    date = fields.Date(
        string='Date'
    )
    name = fields.Char(
        string='Name'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee'
    )
    expense_id = fields.Many2one(
        'hr.expense',
        string='Expense'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product'
    )
    quantity = fields.Float(
        string='Quantity'
    )
    total_amount = fields.Float(
        string='Amount'
    )


class AccountAnalyticLinePsa(models.TransientModel):
    _name = "account.analytic.line.psa"
    _description = "Account analytic line psa"

    date = fields.Date(
        string='Date'
    )
    name = fields.Char(
        string='name'
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee'
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project'
    )
    task_id = fields.Many2one(
        'project.task',
        string='Task'
    )
    unit_amount = fields.Float(
        string='Qty'
    )
    is_billable = fields.Boolean(
        string='Billable'
    )
    account_analytic_line_id = fields.Many2one(
        'account.analytic.line',
        string='Analytic Line'
    )
    so_line = fields.Many2one(
        'sale.order.line',
        string='Order Line'
    )
    to_invoice = fields.Boolean(
        string='To invoice',
        default=True
    )

    @api.onchange('is_billable')
    def onchange_is_billable(self):
        if self.is_billable:
            self.so_line.qty_psa += self.unit_amount
        else:
            self.so_line.qty_psa -= self.unit_amount

        self.account_analytic_line_id.is_billable = self.is_billable


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    advance_payment_method = fields.Selection(
        selection_add=[('tec', 'Bill TEC')], ondelete={'tec': 'cascade'}
    )
    payment_tec = fields.Boolean(
        'Bill TEC'
    )
    date_filter = fields.Date(
        string='Filter date'
    )
    so_line_ids = fields.Many2many(
        'account.analytic.line.psa',
        string='Account analytic line Item'
    )
    hr_expense_line_ids = fields.Many2many(
        'hr.expense.psa',
        string='Hr expense Item'
    )

    @api.onchange('payment_tec')
    def onchange_payment_tec(self):
        advance_payment_method = self.advance_payment_method
        if self.payment_tec:
            self.advance_payment_method = 'tec'
        else:
            self.advance_payment_method = advance_payment_method

    @api.onchange('date_filter')
    def onchange_invoice_timesheets_at_date(self):
        """Getting default values for timesheet invoices at date """
        hr_expense_line_ids = []
        self.write(
            {
                'so_line_ids': [(2, line.id) for line in self.so_line_ids]
            }
        )
        self.write(
            {
                'hr_expense_line_ids': [(2, line.id) for line in self.hr_expense_line_ids]
            }
        )
        if not self.date_filter:
            return

        domain_timesheets = []
        active_id = self._context.get('active_ids', [])

        sale_ids = self.env['sale.order'].browse(active_id)
        res_t = []
        res_e = []
        for order in sale_ids:
            for line in order.order_line.filtered(lambda sol: sol.qty_to_invoice):
                line.sudo().no_bill = False
                if line.product_id.service_type == 'timesheet':
                    domain = [
                        ('so_line', '=', line.id),
                        ('date', '<=', self.date_filter),
                        ('timesheet_invoice_id', '=', False),
                    ]
                    param_invoiced_timesheet = self.env['ir.config_parameter'].sudo(

                    ).get_param('sale.invoiced_timesheet', DEFAULT_INVOICED_TIMESHEET
                                )

                    if param_invoiced_timesheet == 'approved':
                        domain = expression.AND([domain, [('validated', '=', True)]])

                    timesheet_line_ids = self.env['account.analytic.line'].search(
                        domain
                    )
                    if not timesheet_line_ids:
                        line.sudo().qty_psa = 0
                        continue

                    qty_psa = sum(
                        [
                            li.unit_amount for li in timesheet_line_ids if
                            not li.timesheet_invoice_id
                            and li.date <= self.date_filter
                        ]
                    )
                    no_qty_psa = sum(
                        [
                            li.unit_amount for li in timesheet_line_ids if
                            not li.timesheet_invoice_id and not li.is_billable
                            and li.date <= self.date_filter
                        ]
                    )

                    if not qty_psa:
                        line.sudo().no_bill = True

                    line.sudo().qty_psa = 0

                    qty_psa_time_sheet = 0.0

                    for timesheet in timesheet_line_ids:
                        qty_psa_time_sheet += timesheet.unit_amount
                        if line.qty_to_invoice:
                            val_t = (0, 0, {
                                'date': timesheet.date,
                                'name': timesheet.name,
                                'employee_id': timesheet.employee_id.id,
                                'project_id': timesheet.project_id.id,
                                'task_id': timesheet.task_id.id,
                                'unit_amount': timesheet.unit_amount,
                                'is_billable': timesheet.is_billable,
                                'account_analytic_line_id': timesheet.id,
                                'so_line': line.id

                            })
                            res_t.append(val_t)
                            domain_timesheets += timesheet
                    so_line_ids = [l.id for l in domain_timesheets]
                    line.sudo().timesheet_ids = so_line_ids

                # Check Expenses
                if line.product_id.can_be_expensed:
                    expense_line_id = self.env['hr.expense'].search(
                        [
                            ('sale_order_id', '=', line.order_id.id),
                            ('account_invoice_id', '=', False),
                            ('date', '<=', self.date_filter),
                            ('product_id', '=', line.product_id.id),
                            ('id', '!=', line.id)

                        ], limit=int(line.qty_delivered)
                    )
                    if not expense_line_id:
                        line.sudo().no_bill = False
                        continue
                    line.sudo().no_bill = False
                    for expense in expense_line_id:
                        vals_e = (0, 0, {
                            'date': expense.date,
                            'name': expense.name,
                            'employee_id': expense.employee_id.id,
                            'product_id': expense.product_id.id,
                            'quantity': expense.quantity,
                            'total_amount': expense.total_amount,
                            'expense_id': expense.id
                        })

                        hr_expense_line_ids += expense_line_id.ids
                        res_e.append(vals_e)

            self.so_line_ids = res_t
            self.hr_expense_line_ids = res_e

    def create_invoices(self):
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        if self.advance_payment_method != 'tec':
            """Getting default values for timesheet invoices at date """

            domaine_sale_ids = self._context.get('active_ids', [])

            sale_ids = self.env['sale.order'].browse(
                domaine_sale_ids
            )

            for sale_id in sale_ids:
                for line in sale_id.order_line:
                    line.sudo().qty_psa = 0.0
                    line.sudo().timesheet_ids = False
                    line.sudo().no_bill = False
            return super(SaleAdvancePaymentInv, self).create_invoices()
        else:
            for line in self.so_line_ids:
                if line.account_analytic_line_id.is_billable:
                    line.so_line.qty_psa += line.account_analytic_line_id.unit_amount
                    line.account_analytic_line_id.reported = True
            invoice = sale_orders.with_context(invoice_date=self.date_filter)._psa_create_invoices()
            for line_2 in self.so_line_ids:
                    line_2.account_analytic_line_id.timesheet_invoice_id = invoice.id
            invoice.sudo().invoice_date = invoice.sudo().date = self.date_filter
            for expense_line in self.hr_expense_line_ids:
                expense_line.expense_id.update({'account_invoice_id': invoice.id})
            action = self.env.ref('account.action_move_out_invoice_type').read()[0]
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoice.id

            return action
