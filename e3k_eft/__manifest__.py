# -*- coding: utf-8 -*-
#################################################
{
    "name": "E3K EFT",
    "summary": "E3K EFT",
    "category": "",
    "version": "15.0.1",
    "author": "E3k Solutions",
    "website": "http://www.e3k.co",
    "description": '''
             ''',
    "live_test_url": "",
    "depends": ['account_accountant', 'account_payment'],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",

        "data/ir_sequence_data.xml",
        "data/account_payment_method.xml",
        "data/eft_bank.xml",
	    # "views/ir_sequence.xml",
        "views/eft_payment_view.xml",
        "views/res_partner.xml",
        "views/eft_bank.xml",
        "views/account_payment_view.xml",
        "views/account_move.xml",
        "wizard/eft_payment_assign_views.xml",

        "actions/actions.xml",
        "menus/menus.xml"
    ],
    "images": [],
    "application": True,
    "installable": True,
    "auto_install": False,
}
