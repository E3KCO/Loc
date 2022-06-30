# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # eft = fields.Boolean(
    #     string="EFT"
    # )
    fte = fields.Boolean(
        string="TFE"
    )
    code = fields.Char(
        string="Code",
        size=4
    )
    institution = fields.Char(
        string='Institution Code',
        size=4
    )
    number_transit_client = fields.Char(
        string='Number Transit',
        size=5
    )

    referal_number = fields.Char(
        string='Referal Number',
        size=13
    )
    account = fields.Char(
        string='Account Number',
        size=12
    )

    institution = fields.Char(
        string='Institution',
        size=3
    )
    branch = fields.Char(
        string='Branch',
        size=5
    )
    customer_name = fields.Char(
        string="Customer name"
    )
    unit = fields.Char(
        string="Unit"
    )

    @api.constrains('fte')
    def _check_type_fte(self):
        fte = self.fte
        if fte:
            if not self.account:
                raise ValidationError(_('Please fill in the bank details before'))

    # @api.constrains('institution')
    # def _check_type_institution(self):
    #     institution = self.institution
    #     if institution:
    #         str_institution = re.findall("\d", institution)
    #         if len(str_institution) != len(institution):
    #             raise ValidationError(_('Field institution is contain %s, it must be an integer') % self.institution)

    @api.constrains('account')
    def _check_type_account(self):
        account = self.account

        if account:
            str_account = re.findall("\d", account)
            if len(str_account) != len(account):
                raise ValidationError(_('Field account is contain %s, it must be an integer') % self.account)