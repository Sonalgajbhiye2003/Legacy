"""Legacy presentation and mapping controls; actuals use native report engines."""
from copy import deepcopy
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


PL_TYPES = ('income', 'income_other', 'expense', 'expense_direct_cost', 'expense_depreciation')


class AccountReport(models.Model):
    _inherit = 'account.report'

    legacy_kind = fields.Selection([('bs', 'Legacy Balance Sheet'), ('pl', 'Legacy Income Statement')])
    legacy_company_id = fields.Many2one('res.company', string='Legacy report company')
    legacy_notes = fields.Text(string='Finance decisions and source exceptions')
    legacy_prior_basis = fields.Selection([('period', 'Prior-year matching period'), ('ytd', 'Prior-year fiscal YTD')], string='Approved prior-year basis')
    legacy_budget_approved = fields.Boolean(string='Approved native monthly budget source', help='Native external budget values are monthly amounts dated on the first of the month, including the full selected month. Enable only after Finance accepts this basis.')
    legacy_raw_material_category_ids = fields.Many2many(
        'product.category', 'legacy_report_raw_category_rel', 'report_id', 'category_id',
        string='Production raw-material categories',
        help='Historical valuation from completed manufacturing component consumption in these categories is reported as raw materials consumed.',
    )
    legacy_packaging_category_ids = fields.Many2many(
        'product.category', 'legacy_report_pack_category_rel', 'report_id', 'category_id',
        string='Production packaging categories',
        help='Historical valuation from completed manufacturing component consumption in these categories is reported as packaging consumed.',
    )

    @api.constrains('legacy_raw_material_category_ids', 'legacy_packaging_category_ids')
    def _check_legacy_material_categories(self):
        for report in self.filtered(lambda item: item.legacy_kind == 'pl'):
            for raw in report.legacy_raw_material_category_ids:
                for packaging in report.legacy_packaging_category_ids:
                    if (raw == packaging or raw.parent_path.startswith(packaging.parent_path)
                            or packaging.parent_path.startswith(raw.parent_path)):
                        raise ValidationError(_('Raw-material and packaging categories cannot overlap.'))

    def action_audit_cell(self, options, params):
        if self.legacy_kind:
            self._legacy_check_company()
            if self.env['account.report.line'].browse(params['report_line_id']).report_id != self:
                raise AccessError(_('The audit row must belong to this report.'))
        line = self.env['account.report.line'].browse(params['report_line_id'])
        if self.legacy_kind == 'pl' and line.legacy_production_material_kind:
            self._legacy_check_company()
            label = params.get('expression_label')
            if label not in ('period', 'ytd'):
                raise AccessError(_('Only actual production-material columns can be audited.'))
            column_options = self._get_column_group_options(options, params['column_group_key']) if params.get('column_group_key') else options
            start, end, _ = self._get_date_bounds_info(column_options, 'strict_range' if label == 'period' else 'from_fiscalyear')
            moves, _amount, _pending = self.env['legacy.financial.report.handler']._legacy_production_material_data(self, start, end, line.legacy_production_material_kind)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Manufacturing component moves',
                'res_model': 'stock.move',
                'views': [(False, 'list'), (False, 'form')],
                'domain': [('id', 'in', moves.ids)],
                'context': {'create': False, 'edit': False, 'delete': False},
            }
        action = super().action_audit_cell(options, params)
        if self.legacy_kind:
            action['domain'] = action.get('domain', []) + [('company_id', '=', self.legacy_company_id.id)]
        return action

    def _get_options_domain(self, options, date_scope):
        domain = super()._get_options_domain(options, date_scope)
        if self.legacy_kind:
            self._legacy_check_company()
            domain += [('company_id', '=', self.legacy_company_id.id), ('parent_state', '=', 'posted')]
        return domain

    def _legacy_check_company(self):
        self.ensure_one()
        if not self.legacy_company_id or self.legacy_company_id not in self.env.companies:
            raise AccessError(_('Select the authorized company configured for this Legacy report.'))
        if self.env.company != self.legacy_company_id:
            raise AccessError(_('Make the Legacy report company your active company before opening this report.'))

    def _inject_report_into_xlsx_sheet(self, options, workbook, sheet):
        if not self.legacy_kind:
            return super()._inject_report_into_xlsx_sheet(options, workbook, sheet)
        lines = self._filter_out_folded_children(self.with_context(no_format=True)._get_lines(options))
        offset = self._inject_columns_and_headers_in_sheet(workbook, sheet, options, lines)
        self._inject_lines_into_xlsx_sheet(workbook, sheet, lines, options, offset)
        sheet.set_column(0, 0, 48)
        sheet.set_column(1, len(options['columns']), 22)
        sheet.freeze_panes(offset, 1)
        sheet.fit_to_pages(1, 0)
        if self.legacy_kind == 'pl':
            sheet.set_landscape()
        note_format = workbook.add_format({'text_wrap': True, 'font_color': '#805300', 'font_size': 10})
        # Native export inserts a spacer before each level-zero line.
        # Account for those rows so the disclaimer never overwrites totals.
        note_row = offset + len(lines) + sum(line.get('level') == 0 for line in lines) + 2
        sheet.merge_range(note_row, 0, note_row + 6, len(options['columns']),
                          'PROVISIONAL: ' + options.get('legacy_diagnostic', ''), note_format)
        sheet.set_print_scale(85)

    def _get_html_data_for_pdf_export(self, options):
        for bodies, footer, landscape in super()._get_html_data_for_pdf_export(options):
            if self.legacy_kind:
                footer = self.env['ir.actions.report']._render_template(
                    'legacy_financial_reports.pdf_footer', {'company': self.legacy_company_id})
            yield bodies, footer, landscape

    def legacy_diagnostics(self, options):
        """Read-only, record-rule-aware coverage, including offsetting omissions."""
        self.ensure_one()
        self._legacy_check_company()
        scope = 'from_beginning' if self.legacy_kind == 'bs' else 'from_fiscalyear'
        domain = self._get_options_domain(options, scope)
        if self.legacy_kind == 'pl':
            domain += [('account_id.account_type', 'in', PL_TYPES)]
        else:
            domain += [('account_id.account_type', 'not in', PL_TYPES + ('off_balance',))]
        rows = self.env['account.move.line'].read_group(
            domain, ['account_id', 'product_id', 'debit:sum', 'credit:sum', 'balance:sum'],
            ['account_id', 'product_id'], lazy=False)
        mapped_accounts = set(self.line_ids.filtered(lambda l: l.legacy_source == 'account' and l.legacy_mapping_confirmed).legacy_account_ids.ids)
        mapped_products = set(self.line_ids.filtered(lambda l: l.legacy_source == 'product' and l.legacy_mapping_confirmed).legacy_product_ids.ids)
        accounts = self.env['account.account'].browse([r['account_id'][0] for r in rows])
        types = {a.id: a.account_type for a in accounts}
        uncovered = []
        for row in rows:
            aid = row['account_id'][0]
            # Earnings account is explicitly included via native unallocated earnings.
            earnings = self.legacy_kind == 'bs' and types[aid] == 'equity_unaffected'
            product_covered = self.legacy_kind == 'pl' and types[aid] == 'income' and row['product_id'] and row['product_id'][0] in mapped_products
            if aid not in mapped_accounts and not product_covered and not earnings:
                uncovered.append(row)
        return {
            'unmapped': uncovered,
            'unmapped_debit': sum(r['debit'] for r in uncovered),
            'unmapped_credit': sum(r['credit'] for r in uncovered),
            'unmapped_balance': sum(r['balance'] for r in uncovered),
            'pending_rows': self.line_ids.filtered(lambda l: l.legacy_source in ('account', 'product') and not l.legacy_mapping_confirmed).mapped('name'),
        }


class AccountReportLine(models.Model):
    _inherit = 'account.report.line'

    legacy_source = fields.Selection([('account', 'Account'), ('product', 'Product revenue'), ('production_material', 'Production materials'), ('total', 'Subtotal'), ('ratio', 'Margin'), ('heading', 'Heading')])
    legacy_mapping_company_id = fields.Many2one(
        related='report_id.legacy_company_id',
        string='Company',
        readonly=True,
    )
    legacy_report_kind = fields.Selection(
        related='report_id.legacy_kind',
        string='Legacy Report Type',
        readonly=True,
    )
    legacy_section_name = fields.Char(
        string='Report Section',
        compute='_compute_legacy_mapping_destination',
        help='The visible report heading under which this mapped balance is displayed.',
    )
    legacy_destination_label = fields.Char(
        string='Report Destination',
        compute='_compute_legacy_mapping_destination',
        help='The exact Report > Section > Row destination of this mapping.',
    )
    legacy_production_material_kind = fields.Selection([
        ('raw', 'Raw materials consumed'),
        ('packaging', 'Packaging consumed'),
        ('total', 'Total production material cost'),
    ], string='Production material calculation')
    legacy_account_ids = fields.Many2many('account.account', 'legacy_finance_line_account_rel', 'line_id', 'account_id', string='Mapped accounts')
    legacy_product_ids = fields.Many2many('product.product', 'legacy_finance_line_product_rel', 'line_id', 'product_id', string='Approved revenue variants')
    legacy_mapping_confirmed = fields.Boolean(string='Mapping verified', default=False)
    legacy_note = fields.Text(string='Mapping evidence / unresolved decision')
    legacy_source_row = fields.Integer(string='Customer spreadsheet row')
    legacy_percent_basis = fields.Selection([('revenue', 'YTD revenue'), ('costs', 'YTD cost of sales plus operating expenses')], string='Approved contribution denominator')
    legacy_variance_basis = fields.Selection([('actual_budget', 'Actual less budget'), ('budget_actual', 'Budget less actual')], string='Approved variance sign')

    @api.depends('report_id', 'report_id.line_ids.sequence', 'report_id.line_ids.name', 'report_id.line_ids.legacy_source', 'sequence', 'name', 'code')
    def _compute_legacy_mapping_destination(self):
        for line in self:
            line.legacy_section_name = False
            line.legacy_destination_label = False
        for report in self.mapped('report_id').filtered('legacy_kind'):
            current_heading = self.env['account.report.line']
            last_boundary = self.env['account.report.line']
            requested = self.filtered(lambda item: item.report_id == report)
            for line in report.line_ids.sorted(lambda item: (item.sequence, item.id)):
                if line.legacy_source == 'heading':
                    current_heading = line
                    last_boundary = self.env['account.report.line']
                if line in requested:
                    if last_boundary:
                        section = _('Unsectioned after %s', last_boundary.name.strip() or last_boundary.code)
                    elif current_heading:
                        section = current_heading.name.strip() or current_heading.code
                    else:
                        section = _('Top level')
                    line.legacy_section_name = section
                    line.legacy_destination_label = '%s > %s > %s (%s)' % (
                        report.name,
                        section,
                        line.name.strip() or _('Unnamed row'),
                        line.code,
                    )
                if line.legacy_source == 'total' and line.hierarchy_level == 0:
                    last_boundary = line

    @api.constrains('legacy_account_ids', 'legacy_product_ids', 'legacy_mapping_confirmed')
    def _legacy_check_mapping(self):
        for line in self.filtered(lambda l: l.report_id.legacy_kind):
            # Serialize configuration changes per report. This lock touches no ledger
            # data and runs under the native report manager's write permissions.
            self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', [170921, line.report_id.id])
            company = line.report_id.legacy_company_id
            if line.legacy_account_ids.filtered(lambda a: a.company_id != company):
                raise ValidationError(_('Mapped accounts must belong to the report company.'))
            if line.legacy_product_ids.filtered(lambda p: p.company_id and p.company_id != company):
                raise ValidationError(_('Mapped products must belong to the report company or be shared.'))
            if line.legacy_source not in ('account', 'product'):
                if line.legacy_account_ids or line.legacy_product_ids:
                    raise ValidationError(_('Only detail rows can own account/product mappings.'))
                continue
            others = line.report_id.line_ids - line
            others.invalidate_recordset(['legacy_account_ids', 'legacy_product_ids'])
            if line.legacy_account_ids & others.legacy_account_ids:
                raise ValidationError(_('An account cannot belong to two detail rows of the same report.'))
            if line.legacy_product_ids & others.legacy_product_ids:
                raise ValidationError(_('A revenue variant cannot belong to two detail rows.'))
            if line.legacy_source == 'account' and line.report_id.legacy_kind == 'pl' and line.legacy_account_ids.filtered(lambda a: a.account_type == 'income'):
                raise ValidationError(_('Revenue must be mapped by approved product variant, to avoid overlapping SKU totals.'))

    def write(self, vals):
        result = super().write(vals)
        if {'legacy_account_ids', 'legacy_product_ids', 'legacy_mapping_confirmed'} & vals.keys():
            self._legacy_sync_domains()
        if {'legacy_percent_basis', 'legacy_variance_basis'} & vals.keys():
            self._legacy_sync_ratios()
        return result

    def _legacy_sync_ratios(self):
        for line in self.filtered(lambda l: l.report_id.legacy_kind == 'pl' and l.legacy_source != 'heading'):
            formulas = {}
            if line.legacy_percent_basis:
                denominator = 'LIS47.ytd' if line.legacy_percent_basis == 'revenue' else '(LIS61.ytd + LIS78.ytd)'
                formulas['contribution'] = (f'{line.code}.ytd / {denominator} * 100', 'percentage')
            if line.legacy_variance_basis:
                formula = f'{line.code}.ytd - {line.code}.budget' if line.legacy_variance_basis == 'actual_budget' else f'{line.code}.budget - {line.code}.ytd'
                formulas['variance'] = (formula, 'monetary')
                formulas['variance_pct'] = (f'{line.code}.variance / {line.code}.budget * 100', 'percentage')
            for label in ('contribution', 'variance', 'variance_pct'):
                expression = line.expression_ids.filtered(lambda e: e.label == label)
                if label in formulas:
                    values = {'engine':'aggregation', 'formula':formulas[label][0], 'figure_type':formulas[label][1], 'date_scope':'strict_range'}
                    if expression:
                        expression.write(values)
                    else:
                        self.env['account.report.expression'].create(dict(values, report_line_id=line.id, label=label))
                elif expression:
                    expression.unlink()

    def _legacy_sync_domains(self):
        for line in self.filtered(lambda l: l.legacy_source in ('account', 'product')):
            if not line.legacy_mapping_confirmed:
                domain = [('id', '=', 0)]
            elif line.legacy_source == 'product':
                domain = [('account_id.account_type', '=', 'income'), ('product_id', 'in', line.legacy_product_ids.ids)]
            else:
                domain = [('account_id', 'in', line.legacy_account_ids.ids)]
            line.expression_ids.filtered(lambda e: e.engine == 'domain').write({'formula': repr(domain)})


class LegacyReportHandler(models.AbstractModel):
    _name = 'legacy.financial.report.handler'
    _inherit = 'account.report.custom.handler'
    _description = 'Legacy native financial report presentation'

    def _custom_options_initializer(self, report, options, previous_options=None):
        report._legacy_check_company()
        company = report.legacy_company_id
        options['companies'] = [{'id': company.id, 'name': company.name, 'currency_id': company.currency_id.id}]
        if options.get('analytic_accounts') or options.get('analytic_groupby_option'):
            raise ValidationError(_('Analytic splits have not been approved for these Legacy statements. Use the unsplit company ledger until Finance approves an allocation specification.'))
        options['all_entries'] = False
        options['unfold_all'] = False
        options['legacy_notes'] = report.legacy_notes or ''
        options['legacy_provisional'] = True
        if report.legacy_kind == 'pl' and report.legacy_prior_basis:
            prior = deepcopy(options['date'])
            for key in ('date_from', 'date_to'):
                prior[key] = fields.Date.to_string(fields.Date.to_date(prior[key]) - relativedelta(years=1))
            key = 'legacy_prior_year'
            options['column_groups'][key] = {'forced_options': {'date': prior}, 'forced_domain': []}
            for column in options['columns']:
                if column['expression_label'] == 'prior':
                    column.update(column_group_key=key, expression_label=report.legacy_prior_basis)

    def _budget_available(self, report, options):
        if not report.legacy_budget_approved:
            return set()
        start, end, _dummy = report._get_date_bounds_info(options, 'from_fiscalyear')
        start, end = fields.Date.to_date(start), fields.Date.to_date(end)
        months = set()
        cursor = start.replace(day=1)
        while cursor <= end:
            months.add(cursor)
            cursor += relativedelta(months=1)
        values = self.env['account.report.external.value'].search([
            ('company_id', '=', report.legacy_company_id.id),
            ('target_report_expression_id', 'in', report.line_ids.expression_ids.filtered(lambda e: e.label == 'budget' and e.engine == 'external').ids),
            ('date', '>=', start), ('date', '<=', end),
        ])
        dates = {}
        for value in values:
            dates.setdefault(value.target_report_expression_id.id, set()).add(value.date)
        return {eid for eid, present in dates.items() if months <= present}

    def _get_custom_display_config(self):
        return {'css_custom_class': 'legacy_financial_report', 'pdf_export': {'pdf_export_main': 'legacy_financial_reports.pdf_main'}}

    def _legacy_production_material_data(self, report, date_from, date_to, kind):
        """Return completed component moves, historical cost, and valuation completeness."""
        raw_categories = report.legacy_raw_material_category_ids
        packaging_categories = report.legacy_packaging_category_ids
        if not raw_categories or not packaging_categories:
            return self.env['stock.move'], None, True
        category_ids = {
            'raw': raw_categories.ids,
            'packaging': packaging_categories.ids,
            'total': (raw_categories | packaging_categories).ids,
        }[kind]
        if not category_ids:
            return self.env['stock.move'], None, True
        moves = self.env['stock.move'].search([
            ('company_id', '=', report.legacy_company_id.id),
            ('state', '=', 'done'),
            ('date', '>=', fields.Datetime.to_datetime(date_from)),
            ('date', '<', fields.Datetime.to_datetime(date_to) + relativedelta(days=1)),
            ('product_id.categ_id', 'child_of', category_ids),
            '|', ('raw_material_production_id', '!=', False),
                 ('origin_returned_move_id.raw_material_production_id', '!=', False),
        ])
        if not moves:
            return moves, 0.0, False
        layers = self.env['stock.valuation.layer'].sudo().search([
            ('company_id', '=', report.legacy_company_id.id), ('stock_move_id', 'in', moves.ids),
        ])
        layers_by_move = {}
        for layer in layers:
            layers_by_move.setdefault(layer.stock_move_id.id, self.env['stock.valuation.layer'])
            layers_by_move[layer.stock_move_id.id] |= layer
        for move in moves:
            move_layers = layers_by_move.get(move.id, self.env['stock.valuation.layer'])
            if not move_layers or all(not layer.value and not layer.unit_cost for layer in move_layers):
                return moves, None, True
        return moves, -sum(layers.mapped('value')), False

    def _legacy_production_material_result(self, options, date_scope, kind, current_groupby, next_groupby):
        if current_groupby or next_groupby:
            raise ValidationError(_('Production material actuals do not support grouping.'))
        report = self.env['account.report'].browse(options['report_id'])
        report._legacy_check_company()
        start, end, _ = report._get_date_bounds_info(options, date_scope)
        _moves, amount, _pending = self._legacy_production_material_data(report, start, end, kind)
        if kind == 'total':
            _raw_moves, raw_amount, raw_pending = self._legacy_production_material_data(report, start, end, 'raw')
            _pack_moves, pack_amount, pack_pending = self._legacy_production_material_data(report, start, end, 'packaging')
            amount = None if raw_pending or pack_pending else raw_amount + pack_amount
        return {'result': amount}

    def _report_custom_engine_legacy_raw_material_consumed(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        return self._legacy_production_material_result(options, date_scope, 'raw', current_groupby, next_groupby)

    def _report_custom_engine_legacy_packaging_consumed(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        return self._legacy_production_material_result(options, date_scope, 'packaging', current_groupby, next_groupby)

    def _report_custom_engine_legacy_production_material_total(self, expressions, options, date_scope, current_groupby, next_groupby, offset=0, limit=None, warnings=None):
        return self._legacy_production_material_result(options, date_scope, 'total', current_groupby, next_groupby)

    def _custom_line_postprocessor(self, report, options, lines, warnings=None):
        diagnostic = report.legacy_diagnostics(options)
        notes = [report.legacy_notes or '',
                 _('Unmapped posted entries: debit %(debit).2f; credit %(credit).2f; net %(net).2f (company currency).',
                   debit=diagnostic['unmapped_debit'], credit=diagnostic['unmapped_credit'], net=diagnostic['unmapped_balance'])]
        if diagnostic['pending_rows']:
            notes.append(_('Mapping pending: %s', ', '.join(diagnostic['pending_rows'])))
        if diagnostic['unmapped']:
            notes.append(_('Unmapped accounts: %s', '; '.join(
                '%s (debit %.2f, credit %.2f)' % (r['account_id'][1], r['debit'], r['credit'])
                for r in diagnostic['unmapped'])))
        if report.legacy_kind == 'bs':
            line_by_id = {line['id']: line for line in lines}
            amounts = {}
            for code in ('LBS20', 'LBS45'):
                record = report.line_ids.filtered(lambda l: l.code == code)
                rendered = line_by_id.get(report._get_generic_line_id('account.report.line', record.id))
                amounts[code] = rendered['columns'][0].get('no_format', 0) if rendered else 0
            notes.append(_('Assets less equity and liabilities: %.2f', amounts['LBS20'] - amounts['LBS45']))
        if warnings is not None:
            warnings['legacy_financial_reports.warning'] = {'message': ' '.join(notes), 'alert_type': 'warning'}
        options['legacy_diagnostic'] = ' '.join(notes)
        report_lines = {str(l.id): l for l in report.line_ids}
        available_budgets = self._budget_available(report, options) if report.legacy_kind == 'pl' else set()
        for line in lines:
            model, rid = report._get_model_info_from_id(line['id'])
            definition = report_lines.get(str(rid)) if model == 'account.report.line' else None
            if not definition:
                continue
            if definition.legacy_production_material_kind:
                for column in line['columns']:
                    if column.get('expression_label') in ('period', 'ytd') and column.get('no_format') is None:
                        column.update(name='Pending valuation', auditable=False)
            line['class'] = (line.get('class', '') + ' legacy_row_' + str(definition.legacy_source_row)).strip()
            unresolved = definition.legacy_source in ('account', 'product') and not definition.legacy_mapping_confirmed
            budget = definition.expression_ids.filtered(lambda e: e.label == 'budget')
            budget_leaves = budget._expand_aggregations().filtered(lambda e: e.engine == 'external') if budget else budget
            budget_missing = not budget_leaves or not set(budget_leaves.ids) <= available_budgets
            for column in line['columns']:
                label = column.get('expression_label')
                if unresolved and label in ('balance', 'period', 'ytd'):
                    column.update(name='Pending mapping', no_format=None, auditable=False)
                if budget_missing and label in ('budget', 'variance', 'variance_pct'):
                    column.update(name='', no_format=None, auditable=False, edit_popup_data={})
                if label == 'variance_pct':
                    budget_column = next((c for c in line['columns'] if c.get('expression_label') == 'budget'), {})
                    if not budget_column.get('no_format'):
                        column.update(name='', no_format=None, auditable=False)
                if label == 'contribution' and definition.legacy_percent_basis:
                    denominator_codes = ('LIS47',) if definition.legacy_percent_basis == 'revenue' else ('LIS61', 'LIS78')
                    denominator = 0
                    for code in denominator_codes:
                        record = report.line_ids.filtered(lambda l: l.code == code)
                        rendered = next((r for r in lines if r['id'] == report._get_generic_line_id('account.report.line', record.id)), None)
                        if rendered:
                            denominator += next((c.get('no_format') or 0 for c in rendered['columns'] if c.get('expression_label') == 'ytd'), 0)
                    if not denominator:
                        column.update(name='', no_format=None, auditable=False)
            if definition.legacy_source == 'ratio':
                # No ratio is meaningful when the native revenue denominator is zero.
                revenue = next((r for r in lines if r['id'] == report._get_generic_line_id('account.report.line', report.line_ids.filtered(lambda l: l.code == 'LIS47').id)), None)
                if revenue:
                    for index, column in enumerate(line['columns']):
                        if not revenue['columns'][index].get('no_format'):
                            column.update(name='', no_format=None, auditable=False)
        return lines


class AccountReportExpression(models.Model):
    _inherit = 'account.report.expression'

    @api.depends('engine', 'report_line_id.legacy_production_material_kind')
    def _compute_auditable(self):
        super()._compute_auditable()
        for expression in self.filtered(lambda item: item.engine == 'custom' and item.report_line_id.legacy_production_material_kind):
            expression.auditable = True


class LegacyBudgetValue(models.Model):
    _inherit = 'account.report.external.value'

    legacy_budget_key = fields.Char(compute='_compute_legacy_budget_key', store=True, index=True)
    _sql_constraints = [('legacy_budget_unique', 'unique(legacy_budget_key)', 'One monthly budget value per Legacy company and report row is allowed. Edit the existing value instead.')]

    @api.depends('company_id', 'date', 'target_report_expression_id')
    def _compute_legacy_budget_key(self):
        for value in self:
            expression = value.target_report_expression_id
            value.legacy_budget_key = '%s:%s:%s' % (value.company_id.id, expression.id, value.date.strftime('%Y-%m')) if expression.report_line_id.report_id.legacy_kind and value.date else False

    @api.constrains('date', 'company_id', 'target_report_expression_id', 'foreign_vat_fiscal_position_id')
    def _check_legacy_budget(self):
        for value in self:
            expression = value.target_report_expression_id
            report = expression.report_line_id.report_id
            if report.legacy_kind:
                if expression.label != 'budget' or expression.engine != 'external':
                    raise ValidationError(_('External values cannot replace Legacy ledger actuals.'))
                if value.company_id != report.legacy_company_id or value.date.day != 1 or value.foreign_vat_fiscal_position_id:
                    raise ValidationError(_('Legacy budgets must use the report company, first day of month, and no foreign VAT position.'))
