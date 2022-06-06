# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.osv import expression


class Project(models.Model):
    _inherit = "project.project"
