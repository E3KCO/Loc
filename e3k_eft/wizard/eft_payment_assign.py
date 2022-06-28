# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MergePayment(models.TransientModel):
    _name = 'eft.payment.assign'
    _description = 'eft payment assign'

    def _count_payments(self):
        self.count = len(self.payment_ids)

    def _get_default_eft(self):
        eft = self.env['eft.bank'].search([('company_id' ,'=', self.env.company.id)], order='sequence', limit=1)
        if not eft:
           raise ValidationError(_('Please Create Your Company bank account %s.') % '!')
        return eft.id

    payment_ids = fields.Many2many(
        comodel_name='account.payment'
    )
    count = fields.Integer(
        compute='_count_payments',
        strimng='Number of payments'
    )
    eft_bank = fields.Many2one(
        'eft.bank',
        string='EFT Bank',
        required=True,
        default=_get_default_eft
    )
    payment_type = fields.Selection(
        [
            ('inbound', 'Customer'),
            ('outbound', 'Supplier'),
        ],
        required=True,
        string="Payment Type"
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env['res.company']._company_default_get('eft.payment.assign')
    )

    @api.model
    def default_get(self, fields):
        res = super(MergePayment, self).default_get(fields)
        payment_id = self.env['account.payment'].browse(self.env.context['active_ids'][0])
        res['payment_type'] = payment_id.payment_type
        return res

    def action_assign(self):
        if not self.eft_bank.institution or len(self.eft_bank.institution) != 4  or not self.eft_bank.account_number:
            raise ValidationError(_('Please check Your bank account of %s.') % self.eft_bank.name)

        payment_ids = self.payment_ids._create_eft_payment(self.payment_type, self.eft_bank)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eft.payment',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': payment_ids.id,
            'views': [(self.env.ref('e3k_eft.view_eft_payment_form').id, 'form'), (False, 'tree')],
        }




    def action_compute(self):
        paymend_id = self.env['account.payment'].browse(self._context.get('active_ids', [])
                                                        ).filtered(
            lambda s: s.transaction_id.id == False and s.state not in ['draft', 'cancelled']
        )
        self.payment_ids = paymend_id.ids
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eft.payment.assign',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self._context,
        }
