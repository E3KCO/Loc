# -*- coding: utf-8 -*-

import time
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError,UserError

import base64
import platform
# from PyRTF import *
import os
import tempfile
import zipfile
import re
import csv
import io
import unidecode
import logging
_logger = logging.getLogger(__name__)
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


def convert_ascii(string):
    string = unidecode.unidecode(string)
    mapping = [(u'²', '2'), (u'é', 'e'), (u'è', 'e'),
               (u'à', 'a'), (u'Ç', 'c'), (u'ç', 'c'),
               (u'ô', 'o'), (u'\n', ' '), (u'°', 'd ')
               ]
    for k, v in mapping:
        string = string.replace(k, v)
    return str(string)


class EftPayment(models.Model):
    _inherit = 'eft.payment'

    advice = fields.Text(
        "Informations",
        readonly=True
    )
    data = fields.Binary(
        'File',
        readonly=True
    )
    content = fields.Binary(
        'FileTxt',
        readonly=True
    )
    filename = fields.Char(
        'Filename', readonly=True
    )


    def get_file_name(self):
        this = self.sudo()
        if this.related_bank_name in ['desjardin','bnc']:
            this = self.sudo()
            separator = self.eft_bank.filename or str(
                this.payment_date
            ).replace('-', '') + this.eft_bank.name + this.company_id.name
            return separator + ".txt"
        if this.related_bank_name == 'bambora':
            separator = self.eft_bank.filename or str(
                this.payment_date
            ).replace('-', '') + "_BamborA_" + this.company_id.name
            return separator + ".txt"
        if this.related_bank_name == 'cibc':
            this = self.sudo()
            separator = self.eft_bank.filename or  str(
                this.payment_date
            ).replace('-', '') + this.eft_bank.name + this.company_id.name
            return separator + ".dat"

    def render_flat_file(self, keys, sizes, lines, align):
        output = ""
        for line in lines:
            for k in keys:
                if line[k] == None:
                    line[k] = ""
                else:
                    line[k] = convert_ascii((line[k]))
                sizes[k] = len(line[k])
                if (align[k] == 'l'):
                    output += line[k][:sizes[k]].upper().ljust(sizes[k])
                else:
                    output += line[k][:sizes[k]].upper().rjust(sizes[k])
                output += ','
            if self.related_bank_name != 'bambora':
                output += '\n'
            else:
                output += '\r\n'
        return output

    def createZipFile(self, files, fileName):
        f = zipfile.ZipFile(fileName, 'w', zipfile.ZIP_DEFLATED)
        for file_ in files:
            f.write(file_, os.path.basename(file_))
            f.close()
            break

        ofi = open(fileName, 'rb')
        t = ofi.read()
        ofi.close()

        return t

    def create_file(self, filename):
        f = open(filename, 'w')
        return f

    def get_company_params(self):
        this = self
        params_obj = this

        res = {
            'description': '1464 VER 2.0',
            'payments': params_obj,
            'eft_bank': params_obj.eft_bank
        }
        return res
    def action_file(self):
        if self.related_bank_name == 'bambora':
            this = self
            dirname = tempfile.mkdtemp()
            content_file = self.create_bambora_content_file(
                dirname
            )
            # if i want to add header
            files = []
            files.append(
                content_file
            )
            fileName = os.path.join(
                dirname, _('Bambora_payment.zip')
            )
            output = self.createZipFile(
                files, fileName
            )
            out = base64.encodestring(output)

            ofi = open(content_file, 'rb')
            ff = ofi.read()
            self.message_post(
                body="EFT File Generated",
                attachments=[
                    (
                        _('Bambora_payment.txt'),
                        ff
                    )
                ]
            )

            if self.eft_bank.bank_url and self.eft_bank:
                self.message_post(
                    body="""Lien vers la banque   --> <a href="{}">{}</a> """.format(self.eft_bank.bank_url,self.eft_bank.bank_url),
                )
            advice = _("Your file has been exported.\nyou can download it")
            self.write(
                {
                    'data': out, 'advice': advice,
                    'filename': _('Bambora_payment.txt')
                }

            )
            self.file_generated = True
            return True
        if self.related_bank_name in ['desjardin','bnc']:
            _logger.warn('\n\n action_file ----> %s \n\n')
            eft_bank = self.eft_bank
            _logger.warn('\n\n eft_bank ----> %s \n\n', eft_bank)
            if not eft_bank or not eft_bank.issuer_number or not eft_bank.institution or not eft_bank.bank_center_transit or not eft_bank.account_number:
                raise ValidationError(_('Please check the bank configuration of %s.') % '!')

            for pay in self.payment_ids:
                if not pay.partner_id.fte:
                    raise ValidationError(_('Please Configure EFT information of this partner %s.') % (pay.partner_id.name))
            return self.Generate1464ActionFile()

        if self.related_bank_name == 'cibc':
            print('cibc')
            return self.cibcActionFile()



    def cibc_render_flat_file(self, keys, sizes, lines, align, retu=0, Diff=0):
        output = ""

        for l in lines:
            for k in keys:
                if l[k] == None:
                    l[k] = ""
                else:
                    l[k] = convert_ascii((l[k]))
                if (align[k] == 'l'):
                    output += l[k][:sizes[k]].upper().ljust(sizes[k])
                else:
                    output += l[k][:sizes[k]].upper().rjust(sizes[k])

        if Diff:
            output += Diff * ' '

        if not retu:
            output += '\n'
        return output


    def cibcActionFile(self):
        dirname = tempfile.mkdtemp()
        header_file = self.create_cibc_header_file(dirname)
        content_file = self.create_Cibc_lot_file_header(dirname, header_file)
        end_file = self.create_end_file_cibc(dirname, content_file)
        files = []
        files.append(header_file)
        files.append(content_file)
        files.append(end_file)

        name = 'CIBC %s' % (re.findall(r'\d+', self.name)[0].zfill(4))

        fileName = os.path.join(
            dirname, _('%s%s' % (name, '.zip'))
        )

        output = self.createZipFile(
            files, fileName
        )

        out = base64.encodestring(output)

        ofi = open(content_file, 'rb')
        ff = ofi.read()

        self.message_post(
            body="EFT File Generated",
            attachments=[
                (
                    _('%s%s' % (name, '.dat')),
                    ff
                )
            ]
        )
        if self.eft_bank.bank_url and self.eft_bank:
            self.message_post(
                body="""Lien vers la banque   --> <a href="{}">{}</a> """.format(self.eft_bank.bank_url,
                                                                                 self.eft_bank.bank_url),
            )
        advice = u"Your file has been exported.\nyou can download it"
        self.write(
            {
                'state': 'send',
                'data': out, 'advice': advice,
                'filename': _('%s%s' % ("CIBC", '.dat')),
            }
        )
        return True


    #################### 1464 cibc #########
    
    
    
    def create_cibc_header_file(self, dirname):
        
        
        _logger.warn(' \n\n create_cibc_header_file \n\n')
        keys, header_size, header_line, header_align = self.getCibcHeaderContent()
        _logger.warn(' \n\n hahaha \n\n')
        output = self.cibc_render_flat_file(keys, header_size, header_line, header_align)
        fileName = self.get_1464_file_name()
        fileName = os.path.join(dirname, fileName)
        f = self.create_file(fileName)

        f.write(output)
        f.close();
        return fileName
    
    def create_Cibc_lot_file_header(self, dirname, files):
        this = self.sudo()
        params = this.get_company_params()

        cd = 'C'
        if this.payment_type != 'outbound':
            cd = 'D'
        self.create_header_lot_detailed_cibc(dirname, files, cd, this.payment_ids)
        #         self.create_end_file_cibc(dirname, files,cd, this.payment_ids )
        return files
    
    def getCibcHeaderContent(self):
        _logger.warn('\n\n getCibcHeaderContent ----> %s \n\n')
        params = self.get_company_params()
        amounts = params['payments'].amount

        ##################################################################################
        # 01    Genre d’enregistrement: Toujours A                                       #
        # 09    Numéro de séquence: Toujours «000000001»                                 #
        # 10    Numéro de l’usager: Attribué par la Banque                               #
        # 04    Numéro de création du fichier: Augmenter de « 1  »  après chaque fichier #
        # 06    Date de créationFormat: 0AAJJJ                                           #
        # 05    DestinataireToujours «00610»                                             #
        # 20    Réservé: Rempli deblancs                                                 #
        # 03    Code de devise: CAD ou USD                                               #
        # 1406  Réservé: Rempli deblancs                                                 #
        ##################################################################################

        this = self
        keys = ['code',
                'logical_record_count',
                'issuer_number',
                'file_creation_number',
                'creation_date',
                'dest_data_center',
                'bl1',
                'currency',
                'bl2',
                'version_number',
                'nbr_set_account',
                '12a',
                '12b',
                'bl3',
                ]

        header_size = {
            'code': 1,
            'logical_record_count': 9,
            'issuer_number': 10,
            'file_creation_number': 4,
            'creation_date': 6,
            'dest_data_center': 5,
            'bl1': 20,
            'currency': 3,
            'bl2': 1190,
            'version_number': 4,
            'nbr_set_account': 2,
            '12a': 9,
            '12b': 12,
            'bl3': 189,

        }
        header_align = {
            'code': "l",
            'logical_record_count': "l",
            'issuer_number': "l",
            'file_creation_number': "l",
            'creation_date': "l",
            'dest_data_center': "l",
            'bl1': "l",
            'currency': "l",
            'bl2': "l",
            'version_number': "l",
            'nbr_set_account': "l",
            '12a': "l",
            '12b': "l",
            'bl3': '',

        }


        # sequence = params['eft_bank'].sequence_id
        payment_name = ''.join(filter(str.isdigit, self.name))
        print('payment_name',payment_name)

        header_line = [{
            'code': 'A',
            'logical_record_count': '000000001',
            'issuer_number': str(params['eft_bank'].issuer_number).zfill(10),
            'file_creation_number':payment_name or "0000",
            'creation_date': '0' + self.eft_date.strftime('%y%j'),
            'dest_data_center': str(params['eft_bank'].issuer_number[0:5]),
            'bl1': '',
            'currency': str(params['payments'].currency_id.name),
            'bl2': '',  # str(params['eft_bank'].institution),
            'version_number': "0001",
            'nbr_set_account': "01",
            '12a': str(params['eft_bank'].institution) + str(params['eft_bank'].bank_center_transit),
            '12b': str(params['eft_bank'].account_number),
            'bl3': '',

        }]
        _logger.warn('\n\n keys ----> %s \n\n', keys)
        _logger.warn('\n\n header_line ----> %s \n\n', header_line)
        return keys, header_size, header_line, header_align
    
    def create_header_lot_detailed_cibc(self, dirname, files, cd, lines):
        final_string = ''
        sum = 0
        nbr_record = 0
        params = self.get_company_params()
        # sequence = params['eft_bank'].sequence_id
        payment_name = ''.join(filter(str.isdigit, self.name))
        print('payment_name',payment_name)
        iss_nbr = params['eft_bank'].issuer_number
        if len(params['eft_bank'].issuer_number) == 10:
            iss_nbr = params['eft_bank'].issuer_number
        else:
            for i in range(0, 10 - len(params['eft_bank'].issuer_number)):
                iss_nbr += ' '

        nbr_rec = nbr_record + 1
        str_nbr = ''
        for i in range(0, 9 - len(str(nbr_rec))):
            str_nbr += '0'
        cpt_line = 2
        keys0 = ['cd',
                 'record_count',
                 'control_number', ]
        header_size0 = {
            'cd': 1,
            'record_count': 9,
            'control_number': 14, }
        header_align0 = {
            'cd': "l",
            'record_count': "l",
            'control_number': "l", }
        header_line0 = [{
            'cd': cd,
            'record_count': str(str(cpt_line).zfill(9)),
            'control_number': payment_name or "0000", }]
        final_string += self.cibc_render_flat_file(keys0, header_size0, header_line0, header_align0, retu=1)
        cpt = 1
        for rec in lines:
            keys = [
                'transaction_type',
                'amount',
                'value_date',
                'bank_id_trasit',
                'account_number',
                'bl1',
                'stored_trans',
                'orig_name',
                'receive_name',
                'orig_long_name',
                'issuer_number',
                'cross_ref',
                'returnid_transit',
                'return_cibc',
                'sundary',
                'bl2',
                'account_setl',
                'invalid_field',

            ]
            header_size = {
                'transaction_type': 3,
                'amount': 10,
                'value_date': 6,
                'bank_id_trasit': 9,
                'account_number': 12,
                'bl1': 22,
                'stored_trans': 3,
                'orig_name': 15,
                'receive_name': 30,
                'orig_long_name': 30,
                'issuer_number': 10,
                'cross_ref': 19,
                'returnid_transit': 9,
                'return_cibc': 12,
                'sundary': 15,
                'bl2': 22,
                'account_setl': 2,
                'invalid_field': 11,

            }
            header_align = {
                'transaction_type': "l",
                'amount': "l",
                'value_date': "l",
                'bank_id_trasit': "l",
                'account_number': "l",
                'bl1': "l",
                'stored_trans': "l",
                'orig_name': "l",
                'receive_name': "l",
                'orig_long_name': "l",
                'issuer_number': "l",
                'cross_ref': "l",
                'returnid_transit': "l",
                'return_cibc': "l",
                'sundary': "l",
                'bl2': "l",
                'account_setl': "l",
                'invalid_field': "l",

            }
            mont = str(('%.2f' % rec.amount).replace('.', ''))

            header_line = [{
                'transaction_type': "331",
                'amount': str(mont.zfill(10)),
                'value_date': '0' + rec.date.strftime('%y%j') or False,
                'bank_id_trasit': str(rec.partner_id.code) + str(rec.partner_id.number_transit_client),
                'account_number': str(rec.partner_id.account),
                'bl1': '0'.zfill(22),
                'stored_trans': '0'.zfill(3),
                'client_name': str(rec.partner_id.name),
                'orig_name': params['eft_bank'].issuer_short_name,
                'receive_name': str(rec.partner_id.name),
                'orig_long_name': params['eft_bank'].issuer_long_name,
                'issuer_number': str(params['eft_bank'].issuer_number),
                'cross_ref': rec.name,
                'returnid_transit': str(params['eft_bank'].institution) + str(
                    params['eft_bank'].bank_center_transit),
                'return_cibc': str(params['eft_bank'].account_number[0:7]) if len(params['eft_bank'].account_number)>7 else str(params['eft_bank'].account_number),
                'sundary': "",
                'bl2': "",
                'account_setl': "01",
                'invalid_field': '0'.zfill(11),

            }]
            if cpt % 6 == 0 and cpt < len(lines):
                cpt_line += 1
                final_string += self.cibc_render_flat_file(keys, header_size, header_line, header_align, retu=0)
                keys2 = ['cd',
                         'record_count',
                         'control_number', ]
                header_size2 = {
                    'cd': 1,
                    'record_count': 9,
                    'control_number': 14, }
                header_align2 = {
                    'cd': "l",
                    'record_count': "l",
                    'control_number': "l", }
                header_line2 = [{
                    'cd': cd,
                    'record_count': str(str(cpt_line).zfill(9)),
                    'control_number':payment_name or  "0000", }]
                final_string += self.cibc_render_flat_file(keys2, header_size2, header_line2, header_align2,
                                                                   retu=1)
            else:
                final_string += self.cibc_render_flat_file(keys, header_size, header_line, header_align, retu=1)

            cpt += 1

        _logger.warn('\n\n info> final_string -----> %s  \n\n', final_string)

        with open(files, 'a') as f:
            f.write(final_string)
            f.close();
        return files
    
    
    def create_end_file_cibc(self, dirname, files):
        params = self.get_company_params()
        this = self.sudo()
        cd = 'C'
        if this.payment_type != 'outbound':
            cd = 'D'
        # sequence = params['eft_bank'].sequence_id
        payment_name = ''.join(filter(str.isdigit, self.name))
        print('payment_name',payment_name)
        iss_nbr = params['eft_bank'].issuer_number
        total_amount = sum(this.payment_ids.mapped('amount'))
        _logger.warn('\n\n info> total_amount ---> %s \n\n', total_amount)
        mont_total = str(('%.2f' % total_amount).replace('.', ''))
        _logger.warn('\n\n info> mont_total ---> %s \n\n', mont_total)
        end_lint_cpt = 3
        cpt_end = 1
        for payment in this.payment_ids:
            if cpt_end % 6 == 0 and cpt_end < len(this.payment_ids):
                end_lint_cpt += 1
            cpt_end += 1

        if len(params['eft_bank'].issuer_number) == 10:
            iss_nbr = params['eft_bank'].issuer_number
        else:
            for i in range(0, 10 - len(params['eft_bank'].issuer_number)):
                _logger.warn('\n\n i -----> %s', i)
                iss_nbr += ' '
        _logger.warn('\n\n iss_nbr -----> %s', iss_nbr)

        keys = ['code',
                'record_count',
                'control_nbr',
                'total_value',
                'nbr_debit_trans',
                'total_value_cred',
                'nbr_credit_trans',
                'bl1',

                ]
        header_size = {
            'code': 1,
            'record_count': 9,
            'control_nbr': 14,
            'total_value': 14,
            'nbr_debit_trans': 8,
            'total_value_cred': 14,
            'nbr_credit_trans': 8,
            'bl1': 1396,

        }
        header_align = {
            'code': "l",
            'record_count': "l",
            'control_nbr': "l",
            'total_value': "l",
            'nbr_debit_trans': "l",
            'total_value_cred': "l",
            'nbr_credit_trans': "l",
            'bl1': "l",

        }

        header_line = [{
            'code': 'Z',
            'record_count': str(str(end_lint_cpt).zfill(9)),
            'control_nbr': payment_name or "0000",
            'total_value': mont_total.zfill(14) if cd == 'D' else '0'.zfill(14),
            'nbr_debit_trans': str(len(this.payment_ids)).zfill(8) if cd == 'D' else '0'.zfill(8),
            'total_value_cred': mont_total.zfill(14) if cd == 'C' else '0'.zfill(14),
            'nbr_credit_trans': str(len(this.payment_ids)).zfill(8) if cd == 'C' else '0'.zfill(8),
            'bl1': '',

        }]

        segments = '\n' + self.cibc_render_flat_file(keys, header_size, header_line, header_align)
        _logger.warn('\n\n last segelmnts -----> %s', segments)
        with open(files, 'a') as f:
            f.write(segments)
            f.close();
        return files
    
    
    
    ############################################1464#####################################

    def Generate1464ActionFile(self):
        this = self.sudo()
        EftBank = this.eft_bank
        if  not EftBank.institution or not EftBank.issuer_short_name or not EftBank.name or not EftBank.account_number:
           raise ValidationError(_('Please check the bank configuration of %s.') % '!')

        # if not EftBank.sequence_id:
        #     raise UserError('please add a sequence for the EFT BANK')
        dirname = tempfile.mkdtemp()
        header_file = self.create_1464_header_file(dirname)
        content_file = self.create_1464_lot_file_header(dirname, header_file)
        end_file = self.create_end_file_1464(dirname, content_file)
        files = []
        files.append(header_file)
        files.append(content_file)
        files.append(end_file)
        # payment_name =
        name = self.eft_bank.filename or ''.join(filter(str.isdigit, self.name))

        fileName = os.path.join(
            dirname, _('%s%s' % (name, '.zip'))
        )

        output = self.createZipFile(
            files, fileName
        )

        out = base64.encodestring(output)

        ofi = open(content_file, 'rb')
        ff = ofi.read()

        self.message_post(
            body="EFT File Generated",
            attachments=[
                (
                    _('%s%s' % (name, '.txt')),
                    ff
                )
            ]
        )
        if self.eft_bank.bank_url and self.eft_bank:
            self.message_post(
                body="""Lien vers la banque   --> <a href="{}">{}</a> """.format(self.eft_bank.bank_url,
                                                                                 self.eft_bank.bank_url),
            )
        advice = u"Your file has been exported.\nyou can download it"
        self.write(
            {
                'state': 'send',
                'data': out, 'advice': advice,
                'filename': name,
            }
        )
        # EftBank.sequence_id.next_by_id()
        return True

    def get_1464_file_name(self):
        this = self.sudo()
        separator = '%s' % (self.eft_bank.filename or this.eft_bank.name)
        return separator + ".txt"

    def create_1464_header_file(self, dirname):
        keys, header_size, header_line, header_align = self.get1464HeaderContent()
        output = self.generate1464_render_flat_file(keys, header_size, header_line, header_align)
        fileName = self.get_1464_file_name()
        fileName = os.path.join(dirname, fileName)
        f = self.create_file(fileName)

        f.write(output)
        f.close();
        return fileName

    def generate1464_render_flat_file(self, keys, sizes, lines, align, retu=0, Diff=0):
        output = ""

        for l in lines:
            for k in keys:
                if l[k] == None:
                    l[k] = ""
                else:
                    l[k] = convert_ascii((l[k]))
                if (align[k] == 'l'):
                    output += l[k][:sizes[k]].upper().ljust(sizes[k])
                else:
                    output += l[k][:sizes[k]].upper().rjust(sizes[k])

        if Diff:
            output += Diff * ' '

        if not retu:
            output += '\n'
        return output

    ####### HEADER RECORD~##################

    def get1464HeaderContent(self):
        params = self.get_company_params()
        amounts = params['payments'].amount
        count = params['payments'].count

        ##################################################################################
        # 01    Genre d’enregistrement: Toujours A                                       #
        # 09    Numéro de séquence: Toujours «000000001»                                 #
        # 10    Numéro de l’usager: Attribué par la Banque                               #
        # 04    Numéro de création du fichier: Augmenter de « 1  »  après chaque fichier #
        # 06    Date de créationFormat: 0AAJJJ                                           #
        # 05    DestinataireToujours «00610»                                             #
        # 20    Réservé: Rempli deblancs                                                 #
        # 03    Code de devise: CAD ou USD                                               #
        # 1406  Réservé: Rempli deblancs                                                 #
        ##################################################################################

        this = self
        keys = ['code',
                'logical_record_count',
                'issuer_number',
                'file_creation_number',
                'creation_date',
                'dest_data_center',
                'bl1',
                'currency',
                'bl2',
                ]

        header_size = {
            'code': 1,
            'logical_record_count': 9,
            'issuer_number': 10,
            'file_creation_number': 4,
            'creation_date': 6,
            'dest_data_center': 5,
            'bl1': 20,
            'currency': 3,
            'bl2': 1406,
        }
        header_align = {
            'code': "l",
            'logical_record_count': "l",
            'issuer_number': "l",
            'file_creation_number': "l",
            'creation_date': "l",
            'dest_data_center': "l",
            'bl1': "l",
            'currency': "l",
            'bl2': "l",
        }

        # sequence = params['eft_bank'].sequence_id
        if params['eft_bank'].bank_name == 'bnc':
            payment_name = params['eft_bank'].supplier_sequence_id.number_next_actual
        else:
            payment_name = ''.join(filter(str.isdigit, self.name))

        header_line = [{
            'code': 'A',
            'logical_record_count': '000000001',
            'issuer_number': str(params['eft_bank'].issuer_number),
            'file_creation_number': str(payment_name).zfill(4) or "0000" ,
            'creation_date': '0' + self.eft_date.strftime('%y%j'),
            'dest_data_center': "00610" if self.eft_bank.bank_name == 'bnc' else "81510",
            'bl1': '',
            'currency': str(params['payments'].currency_id.name),
            'bl2': '',  # str(params['eft_bank'].institution),

        }]

        return keys, header_size, header_line, header_align

    def create_1464_lot_file_header(self, dirname, files):
        this = self.sudo()
        params = this.get_company_params()

        cd = 'C'
        if this.payment_type != 'outbound':
            cd = 'D'
        self.create_header_lot_detailed_1464(dirname, files, cd, this.payment_ids)

        return files

    def create_header_lot_detailed_1464(self, dirname, files, cd, lines):
        final_string = ''
        payment_name = ''.join(filter(str.isdigit, self.name))
        print('payment_name',payment_name)
        sum = 0
        nbr_record = 0
        params = self.get_company_params()
        # sequence = params['eft_bank'].sequence_id
        iss_nbr = params['eft_bank'].issuer_number
        if len(params['eft_bank'].issuer_number) == 10:
            iss_nbr = params['eft_bank'].issuer_number
        else:
            for i in range(0, 10 - len(params['eft_bank'].issuer_number)):
                iss_nbr += ' '

        nbr_rec = nbr_record + 1
        str_nbr = ''
        for i in range(0, 9 - len(str(nbr_rec))):
            str_nbr += '0'
        cpt_line=2
        keys0 = ['cd',
                 'record_count',
                 'control_number',
                 'number_file',]
        header_size0 = {
            'cd': 1,
            'record_count': 9,
            'control_number': 10,
            'number_file':4,}
        header_align0 = {
            'cd': "l",
            'record_count': "l",
            'control_number': "l",
            'number_file':4,}
        header_line0 = [{
            'cd': cd,
            'record_count': str(str(cpt_line).zfill(9)),
            'control_number': params['eft_bank'].issuer_number,
            'number_file': payment_name or "0000",}]
        final_string += self.generate1464_render_flat_file(keys0, header_size0, header_line0, header_align0, retu=1)
        cpt = 1
        for rec in lines:
            keys = [
                'transaction_type',
                'amount',
                'value_date',
                'bank_id_trasit',
                'account_number',
                'bl1',
                'stored_trans',
                'orig_name',
                'receive_name',
                'orig_long_name',
                'issuer_number',
                'cross_ref',
                'returnid_transit',
                'return_account',
                'sundary',
                'bl2',
                'account_setl',
                'invalid_field',

            ]
            header_size = {
                'transaction_type': 3,
                'amount': 10,
                'value_date': 6,
                'bank_id_trasit': 9,
                'account_number': 12,
                'bl1': 22,
                'stored_trans': 3,
                'orig_name': 15,
                'receive_name': 30,
                'orig_long_name': 30,
                'issuer_number': 10,
                'cross_ref': 19,
                'returnid_transit': 9,
                'return_account': 12,
                'sundary': 15,
                'bl2': 22,
                'account_setl': 2,
                'invalid_field': 11,

            }
            header_align = {
                'transaction_type': "l",
                'amount': "l",
                'value_date': "l",
                'bank_id_trasit': "l",
                'account_number': "l",
                'bl1': "l",
                'stored_trans': "l",
                'orig_name': "l",
                'receive_name': "l",
                'orig_long_name': "l",
                'issuer_number': "l",
                'cross_ref': "l",
                'returnid_transit': "l",
                'return_account': "l",
                'sundary': "l",
                'bl2': "l",
                'account_setl': "l",
                'invalid_field': "l",

            }

            mont = str(('%.2f' % rec.amount).replace('.', ''))

            header_line = [{
                'transaction_type': params['eft_bank'].lot_operation_code or '',
                'amount': str(mont.zfill(10)),
                'value_date': '0' + fields.Date.today().strftime('%y%j'),
                'bank_id_trasit': '0'+ str(rec.partner_id.institution or '') + str(rec.partner_id.branch or ''),
                'account_number': str(rec.partner_id.account or ''),
                'bl1': '0'.zfill(22),
                'stored_trans': '0'.zfill(3),
                'orig_name': params['eft_bank'].issuer_short_name or '',
                'receive_name': str(rec.partner_id.name or ''),
                'orig_long_name': params['eft_bank'].issuer_long_name or '',
                'issuer_number': str(params['eft_bank'].issuer_number or ''),
                'cross_ref': rec.name,
                'returnid_transit': str(params['eft_bank'].institution or '') + str(
                    params['eft_bank'].bank_center_transit or ''),
                'return_account': str(params['eft_bank'].account_number or ''),
                'sundary': "",
                'bl2': "",
                'account_setl': "01",
                'invalid_field': '0'.zfill(11),

            }]
            if self.eft_bank.bank_name == 'bnc':
                keys.append('bl6')
                header_size['bl6'] = 1200
                header_line['bl6'] = ''
                header_align[0]['bl6'] = 'l'



            if cpt % 6 == 0 and cpt < len(lines):
                cpt_line += 1
                final_string += self.generate1464_render_flat_file(keys, header_size, header_line, header_align, retu=0)
                keys2 = ['cd',
                         'record_count',
                         'control_number',
                         'number_file', ]
                header_size2 = {
                    'cd': 1,
                    'record_count': 9,
                    'control_number': 10,
                    'number_file': 4, }
                header_align2 = {
                    'cd': "l",
                    'record_count': "l",
                    'control_number': "l",
                    'number_file': 4, }
                header_line2 = [{
                    'cd': cd,
                    'record_count': str(str(cpt_line).zfill(9)),
                    'control_number': params['eft_bank'].issuer_number,
                    'number_file': payment_name or "0000", }]

                final_string += self.generate1464_render_flat_file(keys2, header_size2, header_line2, header_align2,
                                                                   retu=1)
            else:

                final_string += self.generate1464_render_flat_file(keys, header_size, header_line, header_align, retu=1)
            cpt += 1


        with open(files, 'a') as f:
            f.write(final_string)
            f.close();
        return files

    def create_end_file_1464(self, dirname, files):
        payment_name = ''.join(filter(str.isdigit, self.name))
        print('payment_name',payment_name)
        params = self.get_company_params()
        this = self.sudo()
        cd = 'C'
        if this.payment_type != 'outbound':
            cd = 'D'
        # sequence = params['eft_bank'].sequence_id
        iss_nbr = params['eft_bank'].issuer_number
        total_amount = sum(this.payment_ids.mapped('amount'))
        mont_total = str(('%.2f' % total_amount).replace('.', ''))
        end_lint_cpt = 3
        cpt_end = 1
        for payment in this.payment_ids:
            if cpt_end % 6 == 0 and cpt_end < len(this.payment_ids):
                end_lint_cpt += 1
            cpt_end += 1
        if len(params['eft_bank'].issuer_number) == 10:
            iss_nbr = params['eft_bank'].issuer_number
        else:
            for i in range(0, 10 - len(params['eft_bank'].issuer_number)):
                iss_nbr += ' '

        keys = ['code',
                'record_count',
                'control_nbr',
                'nbr_file',
                'total_value',
                'nbr_debit_trans',
                'total_value_cred',
                'nbr_credit_trans',
                'zero_fill',
                'bl1',

                ]
        header_size = {
            'code': 1,
            'record_count': 9,
            'control_nbr': 10,
            'nbr_file':4,
            'total_value': 14,
            'nbr_debit_trans': 8,
            'total_value_cred': 14,
            'nbr_credit_trans': 8,
            'zero_fill': 44,
            'bl1': 1352,

        }
        header_align = {
            'code': "l",
            'record_count': "l",
            'control_nbr': "l",
            'nbr_file': "l",
            'total_value': "l",
            'nbr_debit_trans': "l",
            'total_value_cred': "l",
            'nbr_credit_trans': "l",
            'zero_fill':"l",
            'bl1': "l",

        }

        header_line = [{
            'code': 'Z',
            'record_count': str(str(end_lint_cpt).zfill(9)),
            'control_nbr': str(params['eft_bank'].issuer_number),
            'nbr_file': payment_name or "0000",
            'total_value': mont_total.zfill(14) if cd == 'D' else '0'.zfill(14),
            'nbr_debit_trans': str(len(this.payment_ids)).zfill(8) if cd == 'D' else '0'.zfill(8),
            'total_value_cred': mont_total.zfill(14) if cd == 'C' else '0'.zfill(14),
            'nbr_credit_trans': str(len(this.payment_ids)).zfill(8) if cd == 'C' else '0'.zfill(8),
            'zero_fill':  "0".zfill(44),
            'bl1': '',

        }]

        segments = '\n' + self.generate1464_render_flat_file(keys, header_size, header_line, header_align)
        with open(files, 'a') as f:
            f.write(segments)
            f.close();
        return files





    ################## BAMBORA  #########
    def create_bambora_content_file(self, dirname):
        this = self
        sorted_lines = this.payment_ids.sorted(key=lambda r: r.partner_id.id)

        keys = ['e',
                'cd',
                'fin',
                'btn',
                'ban',
                'totalamount',
                'irn',
                'fullname',
                'customercode',
                'dynamicdescriptor',

                ]
        header_size = {
            'e': 2,
            'cd': 2,
            'fin': 4,
            'btn': 6,
            'ban': 'X',
            'totalamount': 'X',
            'irn': 'X',
            'fullname': 'X',
            'customercode': 'X',
            'dynamicdescriptor': 'X'

        }
        header_align = {
            'e': 'l',
            'cd': 'l',
            'fin': 'l',
            'btn': 'l',
            'ban': 'l',
            'totalamount': 'l',
            'irn': 'l',
            'fullname': 'l',
            'customercode': 'l',
            'dynamicdescriptor': 'l',
        }
        lines = []
        i = 0

        val = {}
        vals = {}
        res = []

        obj = self.env['account.payment']
        for line in sorted_lines:
            if not line.partner_id.institution or len(
                    line.partner_id.institution) != 3 or not line.partner_id.branch or len(
                    line.partner_id.branch) != 5 or not line.partner_id.account:  # or len(line.partner_id.account) != 12:
                raise ValidationError(_('Please check the bank account of %s.') % line.partner_id.name)

            res.append(line)
            if val.get(line.partner_id):
                val[line.partner_id] += line.amount
            else:
                val[line.partner_id] = line.amount
            vals[line.partner_id] = res

        cd = 'C'
        if this.payment_type != 'outbound':
            cd = 'D'

        for key, value in val.items():
            lines.append({
                'e': 'E',
                'cd': cd,
                'fin': str(key.institution),
                'btn': str(key.branch),
                'ban': str(key.account),
                'totalamount': ('%.2f' % value).replace('.', ''),
                'irn': '0',
                'fullname': key.name,
                'customercode': (key.code and key.code[:31] or '0'),
                'dynamicdescriptor': self.name
            })
            i = i + 1

        output = self.render_flat_file(keys, header_size, lines, header_align)
        fileName = self.get_file_name()
        fileName = os.path.join(dirname, fileName)
        fi = self.create_file(fileName)
        # f.write('Bambora' + '\n')

        fi.write(output)
        fi.close();
        return fileName

    def create_bambora_send_content_file(self):
        this = self
        sorted_lines = this.payment_ids.sorted(key=lambda r: r.partner_id.id)
        lines = ""
        i = 0
        val = {}
        vals = {}
        res = []
        obj = self.env['account.payment']
        for line in sorted_lines:
            if not line.partner_id.institution or \
                    len(line.partner_id.institution) != 3 or not line.partner_id.branch or len(
                line.partner_id.branch) != 5 or not line.partner_id.account:
                raise ValidationError(_('Please check the bank account of %s.') % line.partner_id.name)

            res.append(line)
            if val.get(line.partner_id):
                val[line.partner_id] += line.amount
            else:
                val[line.partner_id] = line.amount
            vals[line.partner_id] = res

        for key, value in val.items():
            lines = lines + 'E,' + 'C,' + str(key.institution) + ',' + str(key.branch) + ',' + str(key.account) + ',' + \
                    ('%.2f' % value).replace('.', '') + ',' + '0' + ',' + key.name + ',' + (
                                key.code and key.code[:31] or '0') + \
                    ',' + self.name + '\r\n'

            i = i + 1
        return lines


    ##############  1664 CIBC format ############