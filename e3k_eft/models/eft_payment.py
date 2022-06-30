# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import requests
import csv
import base64
import json
import random
import string
import os
from odoo.exceptions import UserError, ValidationError
import json
import io
from binascii import a2b_base64
import logging
import tempfile
_logger = logging.getLogger(__name__)
from odoo.http import request


class EftPayment(models.Model):
    _name = 'eft.payment'
    _description = 'eft payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.depends('payment_ids', 'payment_ids.amount')
    def _count_amount(self):
        self.amount = sum(
            [r.amount for r in self.payment_ids]
        )
        self.count = len(self.payment_ids)

    name = fields.Char(
        string='Name',
        states={'draft': [('readonly', False)]}, copy=False,
        required=True,
        index=True, default=lambda self: _('New')
    )
    payment_date = fields.Date(
        string='Date',
        default=fields.Date.today(),
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]}, copy=False,
        tracking=True
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        states={'draft': [('readonly', False)]}, copy=False,
        default=lambda self: self.env['res.company']._company_default_get('eft.payment')
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirm', 'Confirmed'),
            ('request_to_approuve', 'application for approval'),
            ('waiting_approuve', 'Waiting'),
            ('approuved', 'Approuved'),
            ('send', 'Send'),
            ('cancelled', 'Cancelled')
        ],
        readonly=True,
        default='draft',
        copy=False,
        tracking=True,
        string="Status"
    )
    payment_type = fields.Selection(
        [
            ('inbound', 'Customer'),
            ('outbound', 'Supplier'),
        ],
        required=True,
        default='outbound',
        string="Payment Type"
    )
    amount = fields.Monetary(
        string='Total Amount',
        compute='_count_amount',
        store=True
    )
    count = fields.Integer(
        string='Count',
        compute='_count_amount',
        store=True
    )
    line_total = fields.Integer(
        string='Lines total'
    )
    last_sequence = fields.Integer(
        string='Last Sequence'
    )

    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='company_id.currency_id',
        store=True
    )
    note = fields.Text(
        string='Internal Notes',
        tracking=True
    )
    payment_ids = fields.Many2many(
        comodel_name="account.payment",
        inverse_name="transaction_id",
        column1="transaction_id", column2="payment_id",
        string="Payments"
    )
    eft_bank = fields.Many2one(
        'eft.bank', string='EFT Bank',
        readonly=True,
        states={'draft': [('readonly', False)]}
    )

    batch_id = fields.Char('Bambora batch id')

    number_of_approval = fields.Integer(string='Number success approval', readonly=True)
    display_approuved_button = fields.Boolean(string='Display Approuved button',
                                         compute="compute_display_aprouved_button",default=False)

    related_required_approval = fields.Boolean(string='Require approbation',
                                               related="eft_bank.required_approval", readonly=True)
    success_approval_users = fields.Many2many('res.users', string="Success Users",tracking=True)

    file_generated = fields.Boolean(string='Generated File',
                                               default=False)

    message_info = fields.Char(string='Message',compute="get_message_info",store=True)

    display_post_button = fields.Boolean(string='Display Post button',
                                         compute="compute_display_post_button")

    related_journal =  fields.Many2many('account.journal' , related="eft_bank.journal_ids", string="Journal")
    related_bank_name = fields.Selection(
            related="eft_bank.bank_name", string='Bank name'
    )
    succees_transfert_message = fields.Char(
        string='Succes Message',
        tracking=True)

    eft_date = fields.Date(
        string='Eft Date',
        default=fields.Date.today(),
        required=True,
        copy=False,
        tracking=True
    )

    def post_payment(self):
        url = 'https://api.na.bambora.com/v1/batchpayments'

        if not self.eft_bank.merchant_id or not self.eft_bank.batch_file_upload:
            raise UserError(_('You must configure bambora Merchant Id and batch file Upload'))

        headers = self._get_headers(self.eft_bank.merchant_id,self.eft_bank.batch_file_upload)

        data = "--CHEESE\r\nContent-Disposition: form-data;" \
               " name=\"criteria\"\r\nContent-Type: application/json" \
               "\r\n\r\n{\r\n\"process_now\": 1\r\n}\r\n--CHEESE\r\n" \
               "Content-Disposition: form-data; name=\"testdata\"; "

        filename="filename=\""+self.get_file_name()+"\"\r\nContent-Type: text/plain\r\n\r\n"

        transaction_lines=self.create_bambora_send_content_file()
        end = "--CHEESE--\r\n"

        response = requests.post(url, data=data+filename+transaction_lines+end,headers=headers)
        if response.status_code == 200:
            self.write({'state':'send',
                        'batch_id': response.json()['batch_id'],
                        'succees_transfert_message':_('Lot transferred')})
            if not self.file_generated:
                self.action_file()
        else :
            raise UserError(_('Error %s  Message %s')% (str(response.status_code),str(response.json()['message'])))

    def _get_headers(self, merchant_id, payment_api_passcode):
        authorize = base64.b64encode((str(merchant_id)+':'+str(payment_api_passcode)).encode('utf-8'))
        passcode = 'Passcode ' + str(authorize.decode('utf-8'))
        return {
            'Authorization': passcode,
            'Content-Type': 'multipart/form-data; boundary=CHEESE',
            'filetype': 'STD'
        }


    def approval_application(self):
        recipients = []
        subject = _('Approuval Email')
        for rec in self.eft_bank.approval_users:
            base_url = request.env['ir.config_parameter'].get_param('web.base.url')
            base_url += '/web#id=%d&view_type=form&model=%s' % (self.id, self._name)
            message_body = """<div>"""
            message_body += _('Dear ')+str(rec.name)+ """<br/><br/>""" + _('Please approve the payment')+"""<br/>"""
            message_body +=""" <div style="margin: 16px 0px 16px 0px;">
                                <a href= """ +"\" " +base_url+ "\""

            message_body += """style="background-color: #875A7B; 
                                padding: 8px 16px 8px 16px; text-decoration: none;
                                 color: #fff; border-radius: 5px; font-size:13px;">
                                """ + _("Click Here") + """</a> </div> <br/>""" +_('Thanks')+"""</div>"""

            template_obj = self.env['mail.mail']
            template_data = {
                'subject': subject,
                'body_html': message_body,
                'email_to': rec.email
            }
            template_id = template_obj.create(template_data)
            template_obj.send(template_id)
            template_id.send()

        self.write({'state':'waiting_approuve'})

    def compute_display_post_button(self):
        for rec in self:
            if rec.related_required_approval:
                if rec.state not in ['approuved']:
                    rec.display_post_button = False
                else:
                    rec.display_post_button = True
            else:
                if rec.state in ['confirm']:
                    rec.display_post_button = True
                else:
                    rec.display_post_button = False

    def approuve(self):
        if self.related_required_approval:
            if self.env.user.id in self.success_approval_users.ids:
                raise UserError(_("You have already approved"))
            else:
                if self.env.user.id in self.eft_bank.approval_users.ids:
                    copy_line = self.eft_bank.approval_users.filtered(lambda r: r.id == self.env.user.id)
                    self.success_approval_users += copy_line
                    self.number_of_approval += 1
                    if self.eft_bank.required_approval_number>1\
                            and len(self.success_approval_users)<self.eft_bank.required_approval_number:
                        self.post_approuve_message()
                    if self.number_of_approval >= self.eft_bank.required_approval_number:
                        self.write({'state': 'approuved',
                                    })
                else :
                    raise UserError(_("You don't have the right to approve"))

        else :
            self.write({'state':'approuved'})

    @api.depends('state','number_of_approval','eft_bank')
    def get_message_info(self):
        for rec in self:
            rec.message_info = str(len(rec.success_approval_users))+_(" approvals in ") \
                               + str(rec.eft_bank.required_approval_number) +  _(" required")


    def post_approuve_message(self):
        print ('post_approuve_message')
        self.env['mail.message'].create(
            {'model': 'eft.payment',
             'res_id':self._origin.id,
             'body': _('i approved'),
             'message_type':'notification'})


    def compute_display_aprouved_button(self):

        for rec in self:
            if rec.related_required_approval:
                if rec.env.user.id not in rec.eft_bank.approval_users.ids:
                    rec.display_approuved_button = False
                else:
                    if rec.env.user.id in rec.success_approval_users.ids:
                        rec.display_approuved_button = False
                    else:
                        rec.display_approuved_button = True
            else:
                rec.display_approuved_button = True

    @api.model
    def create(self, vals):
        bank_eft_obj = self.env['eft.bank'].search([('id', '=', vals.get('eft_bank'))])
        company_id = bank_eft_obj.company_id.id or False
        supplier_sequence = bank_eft_obj.supplier_sequence_id
        customer_sequence = bank_eft_obj.client_sequence_id
        if not supplier_sequence or not customer_sequence:
            raise UserError(_("Plase configure your bank Sequence."))

        if vals.get('name', _('New')) == _('New'):
            # supplier_sequence = self.env.ref('e3k_eft.seq_e3k_eft_payment_supplier_td')
            # print('supplier_sequence', supplier_sequence)
            # customer_sequence = self.env.ref('e3k_eft.seq_e3k_eft_payment_customer_td')
            # print('customer_sequence', customer_sequence)
            if 'company_id' in vals:
                if vals.get('payment_type') == 'outbound':
                    vals['name'] = supplier_sequence.with_context(
                        force_company=vals['company_id']
                    ).next_by_id() or _('New')
                else:
                    vals['name'] = customer_sequence.with_context(
                        force_company=vals['company_id']
                    ).next_by_id() or _('New')

            else:
                if vals.get('payment_type') == 'outbound':
                    vals['name'] = supplier_sequence.next_by_id() or _('New')
                else:
                    vals['name'] = customer_sequence.next_by_id() or _('New')
        result = super(EftPayment, self).create(vals)
        return result


    def unlink(self):
        if any(rec.state != 'cancelled' for rec in self):
            raise UserError(_("You cannot delete a payment that is already posted."))
        return super(EftPayment, self).unlink()

    def action_confirm(self):
        self.write(
            {'state': 'confirm'}
        )

    def action_draft(self):
        self.success_approval_users = False
        self.display_post_button = False
        self.number_of_approval = 0
        self.file_generated = False
        self.write(
            {'state': 'draft'}
        )

    def action_cancel(self):
        self.write(
            {'state': 'cancelled'}
        )
        for payment in self.payment_ids:
            payment.transaction_id = False

    def action_send(self):
        if self.related_bank_name == 'bambora':
            self.post_payment()
        else:
            self.write(
                {'state': 'send',
                 'file_generated':True}
            )


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('transaction_id', 'transaction_id.state')
    def _compute_payed(self):
        for payment in self:
            rec = False
            if payment.transaction_id.state == 'posted':
                payment.sent = True

    transaction_id = fields.Many2many(
        comodel_name='eft.payment',
        inverse_name='transaction_id',
        column2="transaction_id", column1="payment_id",
        string="Payments"
    )
    sent = fields.Boolean(
        compute="_compute_payed"
    )
    eft_bank = fields.Many2one(
        'eft.bank', string='EFT Bank'
    )

    def _create_eft_payment(self, payment_type, eft_bank):
        eft_obj = self.env['eft.payment']
        eft_id = eft_obj.create(
            {
                'payment_type': payment_type,
                'eft_bank': eft_bank.id,
                'company_id': self.company_id.id
            }
        )
        for payment in self:
            if payment.transaction_id:
                continue
            payment.transaction_id = eft_id.ids

        return eft_id





# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['EFT'] = {'mode': 'unique', 'domain': [('type', '=', 'bank')]}
        return res


