from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree

from odoo import Command
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, ValidationError
from psycopg2 import IntegrityError


@tagged('legacy_finance_dev', '-standard', '-at_install', 'post_install')
class TestLegacyFinance(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls.env.cr.dbname != 'legacy_finance_validation_20260921':
            raise AssertionError('Fixture tests are restricted to the disposable local validation database')
        cls.bs = cls.env.ref('legacy_financial_reports.legacy_bs')
        cls.pl = cls.env.ref('legacy_financial_reports.legacy_pl')
        cls.accounts = {}
        for code, kind in [('CASH', 'asset_cash'), ('PPE', 'asset_fixed'), ('DEPR', 'asset_fixed'), ('REV', 'income'), ('COST', 'expense_direct_cost')]:
            cls.accounts[code] = cls.env['account.account'].create({'name': 'Finance fixture '+code, 'code': 'LF'+code, 'account_type': kind, 'company_id': cls.env.company.id})
        cls.journal = cls.env['account.journal'].create({'name': 'Finance fixture', 'code': 'LFTST', 'type': 'general', 'company_id': cls.env.company.id})
        cls.product = cls.env['product.product'].create({'name': 'Finance fixture SKU', 'type': 'service'})
        for kind, row, names in [('bs', 17, ['CASH']), ('bs', 9, ['PPE', 'DEPR']), ('pl', 52, ['COST'])]:
            cls.env.ref(f'legacy_financial_reports.legacy_{kind}_row_{row}').write({'legacy_account_ids': [Command.set([cls.accounts[n].id for n in names])], 'legacy_mapping_confirmed': True})
        cls.env.ref('legacy_financial_reports.legacy_pl_row_9').write({'legacy_product_ids': [Command.set(cls.product.ids)], 'legacy_mapping_confirmed': True})

    def post(self, date, debit, credit, amount, product=False, draft=False):
        move = self.env['account.move'].create({'journal_id': self.journal.id, 'date': date, 'line_ids': [
            Command.create({'name':'Fixture debit','account_id':self.accounts[debit].id,'debit':amount,'product_id':product.id if product else False}),
            Command.create({'name':'Fixture credit','account_id':self.accounts[credit].id,'credit':amount,'product_id':product.id if product else False}),
        ]})
        if not draft:
            move.action_post()
        return move

    def options(self, report, start='2024-02-01', end='2024-02-29'):
        return report.get_options({'date': {'date_from':start,'date_to':end,'filter':'custom','mode':'range' if report.legacy_kind=='pl' else 'single'}})

    def values(self, report, options):
        lines=report._get_lines(options)
        result={}
        for line in lines:
            model,rid=report._get_model_info_from_id(line['id'])
            if model=='account.report.line':
                code=self.env[model].browse(rid).code
                result[code]={c['expression_label']:c.get('no_format') for c in line['columns']}
        return result

    def test_signed_asof_ytd_and_native_earnings(self):
        self.post('2023-01-15','CASH','REV',400,self.product)
        self.post('2024-01-15','CASH','REV',1000,self.product)
        self.post('2024-02-15','REV','CASH',200,self.product)
        self.post('2024-02-16','PPE','CASH',500)
        self.post('2024-02-17','CASH','DEPR',50)
        self.post('2025-01-15','CASH','REV',999,self.product)
        self.post('2024-02-18','CASH','REV',777,self.product,draft=True)
        actual=self.values(self.pl,self.options(self.pl))
        self.assertEqual(actual['LIS9']['period'],-200)
        self.assertEqual(actual['LIS9']['ytd'],800)
        bs=self.values(self.bs,self.options(self.bs))
        self.assertEqual(bs['LBS9']['balance'],450)
        self.assertEqual(bs['LBS17']['balance'],750)
        self.assertEqual(bs['LBS26']['balance'],1200)
        self.assertEqual(bs['LBS20']['balance'],bs['LBS45']['balance'])

    def test_offsetting_unmapped_postings_are_visible(self):
        self.post('2024-02-15','CASH','REV',77)
        self.post('2024-02-15','REV','CASH',77)
        check=self.pl.legacy_diagnostics(self.options(self.pl))
        self.assertEqual(check['unmapped_debit'],77)
        self.assertEqual(check['unmapped_credit'],77)
        self.assertEqual(check['unmapped_balance'],0)

    def test_duplicate_mapping_rejected(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env.ref('legacy_financial_reports.legacy_bs_row_15').write({'legacy_account_ids':[Command.set(self.accounts['CASH'].ids)],'legacy_mapping_confirmed':True})

    def test_mapping_configuration_identifies_report_section_and_destination(self):
        cash = self.env.ref('legacy_financial_reports.legacy_bs_row_17')
        interest = self.env.ref('legacy_financial_reports.legacy_pl_row_83')
        self.assertEqual(cash.legacy_section_name, 'Current Assets')
        self.assertIn('Legacy Balance Sheet > Current Assets > Cash and Cash Equivalent', cash.legacy_destination_label)
        self.assertEqual(interest.legacy_section_name, 'FINANCE COSTS')
        self.assertIn('Interest on OD', interest.legacy_destination_label)

    def test_company_isolation(self):
        other=self.env['res.company'].create({'name':'Finance isolated fixture company','currency_id':self.env.company.currency_id.id,'sequence_prefix':'LFT'})
        with self.assertRaises(AccessError):
            self.bs.with_company(other).with_context(allowed_company_ids=other.ids).get_options()

    def test_unconfirmed_account_mapping_remains_uncovered(self):
        self.post('2024-02-10', 'CASH', 'REV', 100, self.product)
        line = self.bs.line_ids.filtered(lambda item: self.accounts['CASH'] in item.legacy_account_ids)
        self.assertTrue(line)
        line.legacy_mapping_confirmed = False
        diagnostic = self.bs.legacy_diagnostics(self.options(self.bs))
        self.assertIn(self.accounts['CASH'].id, [item['account_id'][0] for item in diagnostic['unmapped']])

    def test_missing_budget_and_zero_denominator_are_blank(self):
        vals=self.values(self.pl,self.options(self.pl))
        self.assertIsNone(vals['LIS64']['period'])
        self.assertIsNone(vals['LIS9']['budget'])
        self.assertIsNone(vals['LIS9']['variance'])

    def test_report_generation_does_not_post(self):
        before={m:self.env[m].search_count([]) for m in ['account.move','stock.move','stock.valuation.layer']}
        for report in (self.bs,self.pl):
            options=self.options(report)
            report.get_report_information(options)
            exported=report.export_to_xlsx(options)
            self.assertTrue(exported['file_content'].startswith(b'PK'))
        after={m:self.env[m].search_count([]) for m in before}
        self.assertEqual(before,after)

    def test_budget_missing_zero_and_duplicate(self):
        line=self.env.ref('legacy_financial_reports.legacy_pl_row_9')
        expression=line.expression_ids.filtered(lambda e:e.label=='budget')
        self.pl.legacy_budget_approved=True
        budget={'company_id':self.env.company.id,'target_report_expression_id':expression.id,'date':'2024-01-01','value':0,'name':'Fixture January'}
        self.env['account.report.external.value'].create(budget)
        self.assertIsNone(self.values(self.pl,self.options(self.pl))['LIS9']['budget'])
        self.env['account.report.external.value'].create(dict(budget,date='2024-02-01',name='Fixture February'))
        self.assertEqual(self.values(self.pl,self.options(self.pl))['LIS9']['budget'],0)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env['account.report.external.value'].create(budget)

    def test_xlsx_disclaimer_does_not_overwrite_report_rows(self):
        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        for report in (self.bs, self.pl):
            options = self.options(report)
            expected = [line['name'] for line in report._get_lines(options) if line['name'].strip()]
            with ZipFile(BytesIO(report.export_to_xlsx(options)['file_content'])) as archive:
                strings = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
                texts = [''.join(item.itertext()) for item in strings]
                sheet = ElementTree.fromstring(archive.read('xl/worksheets/sheet1.xml'))
                labels = [texts[int(cell.find('s:v', ns).text)]
                          for cell in sheet.findall('.//s:c', ns)
                          if cell.get('r', '').startswith('A') and cell.get('t') == 's']
            cursor = 0
            for name in expected:
                cursor = labels.index(name, cursor) + 1
            self.assertTrue(any(label.startswith('PROVISIONAL:') for label in labels[cursor:]))

    def test_external_value_cannot_override_actuals(self):
        expression=self.env.ref('legacy_financial_reports.legacy_pl_row_9_period')
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env['account.report.external.value'].create({'name':'Forbidden override','company_id':self.env.company.id,'date':'2024-01-01','target_report_expression_id':expression.id,'value':99})

    def test_prior_year_basis_and_drilldown(self):
        self.post('2023-01-10','CASH','REV',120,self.product)
        self.post('2023-02-10','CASH','REV',30,self.product)
        self.pl.legacy_prior_basis='period'
        options=self.options(self.pl)
        lines=self.pl._get_lines(options)
        definition=self.env.ref('legacy_financial_reports.legacy_pl_row_9')
        rendered=next(l for l in lines if l['id']==self.pl._get_generic_line_id('account.report.line',definition.id))
        self.assertEqual(rendered['columns'][-1]['no_format'],30)
        action=self.pl.action_audit_cell(options,{'report_line_id':definition.id,'expression_label':'period','column_group_key':'legacy_prior_year','calling_line_dict_id':rendered['id']})
        self.assertEqual(sum(self.env['account.move.line'].search(action['domain']).mapped('balance')),-30)
        self.pl.legacy_prior_basis='ytd'
        lines=self.pl._get_lines(self.options(self.pl))
        rendered=next(l for l in lines if l['id']==self.pl._get_generic_line_id('account.report.line',definition.id))
        self.assertEqual(rendered['columns'][-1]['no_format'],150)

    def test_approved_contribution_is_ratio_not_sum(self):
        self.post('2024-02-10','CASH','REV',100,self.product)
        line=self.env.ref('legacy_financial_reports.legacy_pl_row_9')
        line.legacy_percent_basis='revenue'
        self.assertEqual(self.values(self.pl,self.options(self.pl))['LIS9']['contribution'],100)

    def test_production_materials_use_historical_valuation_and_are_auditable(self):
        company = self.env.company
        raw_category = self.env['product.category'].create({'name': 'Finance raw fixture'})
        pack_category = self.env['product.category'].create({'name': 'Finance packaging fixture'})
        self.pl.write({
            'legacy_raw_material_category_ids': [Command.set(raw_category.ids)],
            'legacy_packaging_category_ids': [Command.set(pack_category.ids)],
        })
        raw = self.env['product.product'].create({'name': 'Finance raw material', 'type': 'product', 'categ_id': raw_category.id})
        pack = self.env['product.product'].create({'name': 'Finance packaging', 'type': 'product', 'categ_id': pack_category.id})
        finished = self.env['product.product'].create({'name': 'Finance manufactured fixture', 'type': 'product'})
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'mrp_operation'), ('company_id', '=', company.id)], limit=1)
        production = self.env['mrp.production'].create({
            'product_id': finished.id, 'product_qty': 1, 'product_uom_id': finished.uom_id.id,
            'picking_type_id': picking_type.id, 'company_id': company.id,
        })
        internal = self.env['stock.location'].create({'name': 'Finance fixture stock', 'usage': 'internal', 'company_id': company.id})
        production_location = self.env['stock.location'].create({'name': 'Finance fixture production', 'usage': 'production'})

        def component_move(product, amount, valued=True):
            move = self.env['stock.move'].create({
                'name': 'Finance production component fixture',
                'product_id': product.id, 'product_uom_qty': 1, 'product_uom': product.uom_id.id,
                'quantity': 1, 'location_id': internal.id, 'location_dest_id': production_location.id,
                'company_id': company.id, 'raw_material_production_id': production.id,
                'state': 'done', 'date': '2024-02-15 12:00:00',
            })
            self.env['stock.valuation.layer'].create({
                'company_id': company.id, 'product_id': product.id,
                'quantity': -1, 'unit_cost': amount if valued else 0,
                'value': -amount if valued else 0, 'stock_move_id': move.id,
                'description': 'Finance historical valuation fixture',
            })
            return move

        raw_move = component_move(raw, 10)
        component_move(pack, 2)
        return_move = self.env['stock.move'].create({
            'name': 'Finance production return fixture', 'product_id': raw.id,
            'product_uom_qty': 0.3, 'product_uom': raw.uom_id.id, 'quantity': 0.3,
            'location_id': production_location.id, 'location_dest_id': internal.id,
            'company_id': company.id, 'origin_returned_move_id': raw_move.id,
            'state': 'done', 'date': '2024-02-20 12:00:00',
        })
        self.env['stock.valuation.layer'].create({
            'company_id': company.id, 'product_id': raw.id, 'quantity': 0.3,
            'unit_cost': 10, 'value': 3, 'stock_move_id': return_move.id,
            'description': 'Finance production return valuation fixture',
        })
        amounts = self.values(self.pl, self.options(self.pl))
        self.assertEqual(amounts['LIS90']['period'], 7)
        self.assertEqual(amounts['LIS91']['period'], 2)
        self.assertEqual(amounts['LIS92']['period'], 9)
        action = self.pl.action_audit_cell(self.options(self.pl), {
            'report_line_id': self.env.ref('legacy_financial_reports.legacy_pl_row_90').id,
            'expression_label': 'period',
        })
        self.assertEqual(action['res_model'], 'stock.move')
        audit_moves = self.env['stock.move'].search(action['domain'])
        self.assertEqual(sum(self.env['stock.valuation.layer'].search([('stock_move_id', 'in', audit_moves.ids)]).mapped('value')), -7)
        no_activity = self.values(self.pl, self.options(self.pl, '2024-03-01', '2024-03-31'))
        self.assertEqual(no_activity['LIS90']['period'], 0)
        self.assertEqual(self.env.ref('legacy_financial_reports.legacy_pl_row_63_period').formula, 'LIS47.period - LIS61.period')
        self.assertEqual(self.env.ref('legacy_financial_reports.legacy_pl_row_63_ytd').formula, 'LIS47.ytd - LIS61.ytd')

        component_move(raw, 0, valued=False)
        pending = self.values(self.pl, self.options(self.pl))
        self.assertIsNone(pending['LIS90']['period'])
        self.assertIsNone(pending['LIS92']['period'])
        lines = self.pl._get_lines(self.options(self.pl))
        rendered = next(line for line in lines if line['id'] == self.pl._get_generic_line_id(
            'account.report.line', self.env.ref('legacy_financial_reports.legacy_pl_row_90').id))
        self.assertTrue(any(column.get('name') == 'Pending valuation' for column in rendered['columns']))
