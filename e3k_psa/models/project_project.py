# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.osv import expression


class ProjectExpense(models.Model):
    _name = 'project.expense'
    _description = 'Project expense'

    expense_id = fields.Many2one(
        'project.project',
        name='Expense',
        required=True,
        ondelete='cascade',
        index=True,
        copy=False
    )
    product_id = fields.Many2one(
        'product.product',
        name='Product'
    )
    partner_id = fields.Many2one(
        'res.partner',
        related='expense_id.partner_id',
        store=True
    )
    percent = fields.Float(
        name='Percent'
    )
    oldpercent = fields.Float(
        name='Percent'
    )


class Project(models.Model):
    _inherit = 'project.project'

    def action_reset_percent(self):
        """ Write `percent` to zero on the selected records. """
        self.expense_ids.write({'percent': 0})

    def update_expense(self):
        """ Update `percent`. """
        obj = self.env['product.product']
        # Search product with boolean can_be_expensed
        products = obj.search([('can_be_expensed', '=', True)])
        # Check whether the existing expenditure lines
        project_product = self.expense_ids
        res = []
        expense_percent = 0.0
        for product in products:
            line = project_product.filtered(lambda l: l.product_id.id == product.id)
            expense_percent = (self.expense_percent - self.oldexpense_percent)
            if line:
                expense_percent = line.percent + expense_percent

            values = (0, 0, {
                'product_id': product.id,
                'percent': expense_percent,
            })
            res.append(values)

        self.expense_ids.unlink()
        self.update({'expense_ids': res, 'oldexpense_percent': expense_percent})

    non_billable_project = fields.Boolean(
        'Non Billable Project',
        default=False
    )
    expense_percent = fields.Float(
        name='Additional percentage expenses'
    )
    oldexpense_percent = fields.Float(
        name='old Additional percentage expenses'
    )
    expense_ids = fields.One2many(
        comodel_name="project.expense",
        inverse_name="expense_id",
        string="Expense",
        required=False
    )

    sale_line_department_ids = fields.One2many('project.sale.line.department.map', 'project_id',
                                               "Sale line/Department map",
                                               copy=False)

    # TO DO : TO REVIEW THIS FUNCTION
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if not args:
            args = []
        if name:
            positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
            project_ids = []
            if operator in positive_operators:
                partners = self.env['res.partner']._search([('name', 'ilike', name)], access_rights_uid=name_get_uid)
                project_ids = list(
                    self._search([('partner_id.id', 'in', partners)] + args, limit=limit, access_rights_uid=name_get_uid))
            if not project_ids and operator not in expression.NEGATIVE_TERM_OPERATORS:
                if not limit or len(project_ids) < limit:
                    limit2 = (limit - len(project_ids)) if limit else False
                    project2_ids = self._search(args + [('name', operator, name), ('id', 'not in', project_ids)],
                                                limit=limit2, access_rights_uid=name_get_uid)
                    project_ids.extend(project2_ids)
            elif not project_ids and operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = expression.OR([
                    [('name', operator, name)],
                ])
                domain = expression.AND([args, domain])
                project_ids = list(self._search(domain, limit=limit, access_rights_uid=name_get_uid))

        else:
            project_ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        return project_ids
