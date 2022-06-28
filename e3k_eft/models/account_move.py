# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    eft = fields.Boolean(
        string="TFE", related='partner_id.fte', store=True
    )
