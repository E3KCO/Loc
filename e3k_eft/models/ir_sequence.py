# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class IrSeqeunce(models.Model):
    _inherit = 'ir.sequence'

    bank_name = fields.Selection(
        [
            ('bambora' ,'Bambora'),
            ('desjardin' ,'Desjardins'),
            ('bnc', 'BNC'),
        ], string='Bank name'
    )
    types =  fields.Selection(
        [
            ('customer' ,'Customer'),
            ('supplier' ,'Supplier')
        ], string='Type'
    )
