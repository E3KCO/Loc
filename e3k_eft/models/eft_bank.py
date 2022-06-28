# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re



class Eftbank(models.Model):
    _name = "eft.bank"
    _description = "EFT bank"
    
    name = fields.Char(
        string="Bank name", required=True
    )

    bank_name = fields.Selection(
        [   ('bambora','Bambora'),
            ('desjardin', 'Desjardins'),
            ('cibc', 'CIBC'),
            ('bnc','BNC'),
        ], string='Bank name'
    )
    issuer_number = fields.Char(
        string="Issuer Number" ,size=10
    )

    institution = fields.Char(
        string="Financial institution", size=4
    )
    branch = fields.Char(
        string="Branch number"
    )

    bank_center_transit = fields.Char(
        string="Banking Center Transit", size=5
    )

    issuer_short_name = fields.Char(
        string="Issuer Short Name", size=15
    )

    issuer_long_name = fields.Char(
        string="Issuer Long Name", size=30
    )


    account_number = fields.Char(
        string="Account Number"
    )

    # sequence_id = fields.Many2one(
    #     comodel_name="ir.sequence",
    #     string="Sequence",
    #     copy=False,
    # )

    lot_operation_code = fields.Char(
        string="Operation Code", size=3
    )

    other_info_lot = fields.Char(
        string="others info", size=10
    )
    payment_passcode = fields.Char(
        string="Payment Passocde"
    )
    sequence = fields.Integer(
        string="Sequence"
    )
    filename = fields.Char(
        string="Name of the file to export", defaut='TF0380000000'
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env['res.company']._company_default_get('eft.bank')
    )
    
    required_approval = fields.Boolean(string="approval required",default=False)
    required_approval_number = fields.Integer(string="Number of approvals required")
    approval_users = fields.Many2many('res.users',
                                      string="Users who can approve",
                    domain=lambda self: [( "groups_id", "=", self.env.ref( "e3k_eft.eft_manager").id)])

    journal_ids = fields.Many2many('account.journal' , string="Journal")


    supplier_sequence_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Sequence Paiement Fournisseur",
        copy=False,
    )
    client_sequence_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Sequence Paiement Client ",
        copy=False,
    )


    merchant_id = fields.Char(
        string="MerchantID"
    )
    batch_file_upload = fields.Char(
        string="Batch File Upload"
    )

    bank_url = fields.Char(string='Url')

    @api.constrains('institution')
    def _check_type_institution(self):
        institution = self.sudo().institution
        if institution:
            str_institution = re.findall("\d", institution)
            if len(str_institution) != len(institution):
                raise ValidationError(_('Field institution is contain %s, it must be an integer') % self.institution)


    @api.constrains('account')
    def _check_type_account(self):
        account = self.sudo().account_number

        if account:
            str_account = re.findall("\d", account)
            if len(str_account) != len(account):
                raise ValidationError(_('Field account is contain %s, it must be an integer') % self.account)
    
    
    
