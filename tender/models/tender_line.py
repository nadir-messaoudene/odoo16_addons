from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from odoo.addons import decimal_precision as dp


class TenderLines(models.Model):
    _name = 'tender.line'
    _description = 'Tender Line'

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.tender_id.currency_id, line.product_uom_qty,
                                            product=line.product_id, partner=line.tender_id.partner_id)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    @api.depends('product_id', 'tender_id.state')
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ['done', 'cancel'] or (
                    line.state == 'sale' and (line.qty_invoiced > 0 or line.qty_delivered > 0)):
                line.product_updatable = False
            else:
                line.product_updatable = True

    @api.depends('price_unit', 'discount')
    def _get_price_reduce(self):
        for line in self:
            line.price_reduce = line.price_unit * (1.0 - line.discount / 100.0)

    @api.depends('price_total', 'product_uom_qty')
    def _get_price_reduce_tax(self):
        for line in self:
            line.price_reduce_taxinc = line.price_total / line.product_uom_qty if line.product_uom_qty else 0.0

    @api.depends('price_subtotal', 'product_uom_qty')
    def _get_price_reduce_notax(self):
        for line in self:
            line.price_reduce_taxexcl = line.price_subtotal / line.product_uom_qty if line.product_uom_qty else 0.0

    def _compute_tax_id(self):
        for line in self:
            fpos = line.tender_id.partner_id.property_account_position_id
            taxes = line.product_id.taxes_id.filtered(lambda r: not line.company_id or r.company_id == line.company_id)
            line.tax_id = fpos.map_tax(taxes, line.product_id, line.tender_id.partner_id) if fpos else taxes

    @api.model
    def _get_purchase_price(self, pricelist, product, product_uom, date):
        return {}

    @api.model
    def _prepare_add_missing_fields(self, values):
        res = {}
        onchange_fields = ['name', 'price_unit', 'product_uom', 'tax_id']
        if values.get('tender_id') and values.get('product_id') and any(f not in values for f in onchange_fields):
            line = self.new(values)
            line.product_id_change()
            for field in onchange_fields:
                if field not in values:
                    res[field] = line._fields[field].convert_to_write(line[field], line)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        vals_ls = []
        for values in vals_list:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(product_id=False, price_unit=0, product_uom_qty=0, product_uom=False, customer_lead=0)

            values.update(self._prepare_add_missing_fields(values))

        for vals in vals_list:
            if vals.get('is_reactif_dedie', False) or vals.get('is_reactif_manuel', False):
                template_obj = self.env['product.template']
                reactif_obj = template_obj.browse(vals.get('product_id', False))
                vals['standard_ids'] = [(6, 0, reactif_obj.standard_ids.ids)]
            vals_ls.append(vals)

        lines = super().create(vals_ls)

        for line in lines:
            if line.is_reactif_dedie or line.is_reactif_manuel:
                for std in reactif_obj.standard_ids:
                    product = self.env['product.product'].search([('product_tmpl_id', '=', std.id)])
                    standard_vals = {'display_type': False,
                                     'sequence': 9,
                                     'qty_delivered_manual': 0,
                                     'product_uom_qty': line.product_uom_qty,
                                     'price_unit': 0,
                                     'discount': 0,
                                     'product_packaging': False,
                                     'product_id': product.id,
                                     'product_uom': product.uom_id.id,
                                     'tax_id': [[6, False, []]],
                                     'name': self.get_sale_order_line_multiline_description_sale(product),
                                     'tender_id': line.tender_id.id,
                                     'invoicing': 'do_not_invoice',
                                     'pattern_not_invoicing': 'std'}
                    super().create(standard_vals)

        return lines

    _sql_constraints = [
        ('accountable_required_fields',
         "CHECK(display_type IS NOT NULL OR (product_id IS NOT NULL AND product_uom IS NOT NULL))",
         "Missing required fields on accountable tender line."),
        ('non_accountable_null_fields',
         "CHECK(display_type IS NULL OR (product_id IS NULL AND price_unit = 0 AND product_uom_qty = 0 AND product_uom IS NULL))",
         "Forbidden values on non-accountable tender line"),
    ]

    def _update_line_quantity(self, values):
        orders = self.mapped('tender_id')
        for order in orders:
            order_lines = self.filtered(lambda x: x.tender_id == order)
            msg = "<b>The uantity has been updated.</b><ul>"
            for line in order_lines:
                msg += "<li> %s:" % (line.product_id.display_name,)
                msg += "<br/>" + _("Quantité") + ": %s -> %s <br/>" % (
                    line.product_uom_qty, float(values['product_uom_qty']),)
                if line.product_id.type in ('consu', 'product'):
                    msg += _("Delivered Quantity") + ": %s <br/>" % (line.qty_delivered,)
                msg += _("Invoiced Quantity") + ": %s <br/>" % (line.qty_invoiced,)
            msg += "</ul>"
            order.message_post(body=msg)

    def write(self, values):
        if 'display_type' in values and self.filtered(lambda line: line.display_type != values.get('display_type')):
            raise UserError(
                "You cannot change the type of a sale order line. Instead you should delete the current line and create a new line of the proper type.")

        if 'product_uom_qty' in values:
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            self.filtered(
                lambda r: r.state == 'sale' and float_compare(r.product_uom_qty, values['product_uom_qty'],
                                                              precision_digits=precision) != 0)._update_line_quantity(
                values)

        # Prevent writing on a locked SO.
        protected_fields = self._get_protected_fields()
        if 'done' in self.mapped('tender_id.state') and any(f in values.keys() for f in protected_fields):
            protected_fields_modified = list(set(protected_fields) & set(values.keys()))
            fields = self.env['ir.model.fields'].search([
                ('name', 'in', protected_fields_modified), ('model', '=', self._name)
            ])
            raise UserError(
                _('It is forbidden to modify the following fields in a locked order:\n%s')
                % '\n'.join(fields.mapped('field_description'))
            )

        result = super(TenderLines, self).write(values)
        return result

    tender_id = fields.Many2one('crm.lead', string='Appel d\offre', required=True, ondelete='cascade',
                                index=True, copy=False)
    name = fields.Text(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    price_unit = fields.Float('Unit Price', required=True, digits=dp.get_precision('Product Price'), default=0.0)
    price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', readonly=True, store=True)
    price_tax = fields.Float(compute='_compute_amount', string='Total Tax', readonly=True, store=True)
    price_total = fields.Monetary(compute='_compute_amount', string='Total', readonly=True, store=True)
    price_reduce = fields.Float(compute='_get_price_reduce', string='Price Reduce',
                                digits=dp.get_precision('Product Price'), readonly=True, store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes',
                              domain=['|', ('active', '=', False), ('active', '=', True)])
    price_reduce_taxinc = fields.Monetary(compute='_get_price_reduce_tax', string='Price Reduce Tax inc', readonly=True,
                                          store=True)
    price_reduce_taxexcl = fields.Monetary(compute='_get_price_reduce_notax', string='Price Reduce Tax excl',
                                           readonly=True, store=True)
    discount = fields.Float(string='Discount (%)', digits=dp.get_precision('Discount'), default=0.0)
    product_id = fields.Many2one('product.product', string='Product', domain=[('sale_ok', '=', True)],
                                 change_default=True, ondelete='restrict')
    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can Edit Product', readonly=True,
                                       default=True)
    product_uom_qty = fields.Float(string='Qté', digits=dp.get_precision('Product Unit of Measure'), required=True,
                                   default=1.0)
    won_uom_qty = fields.Float(string='Qté retenue', digits=dp.get_precision('Product Unit of Measure'))
    min_uom_qty = fields.Float(string='Qté min', digits=dp.get_precision('Product Unit of Measure'))
    max_uom_qty = fields.Float(string='Qté max', digits=dp.get_precision('Product Unit of Measure'))

    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')

    salesman_id = fields.Many2one(related='tender_id.user_id', store=True, string='Salesperson', readonly=True)
    company_id = fields.Many2one(related='tender_id.company_id', string='Company', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency",
                                  readonly=True)
    order_partner_id = fields.Many2one(related='tender_id.partner_id', store=True, string='Customer', readonly=False)
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('sent', 'Envoyé'),
        ('won', 'Retenu'),
        ('partial_won', 'Partiellement Retenu'),
        ('lost', 'Non Retenu'),
        ('cancel', 'Annulé'),
    ], string='Etat', readonly=True, copy=False, default='draft')

    invoicing = fields.Selection([
        ('to_invoice', 'Applicable'),
        ('do_not_invoice', 'Non applicable')
    ], string='Facturation', default='to_invoice')

    pattern_not_invoicing = fields.Selection([
        ('starter_kit', 'Kit de démarrage'),
        ('mad', 'MAD'),
        ('warranty', 'Garantie'),
        ('loan_refund', 'Retour emprunt'),
        ('replacement', 'Remplacement'),
        ('commercial_gesture', 'Geste commercial'),
        ('promotional_offer', 'Offre promotionnelle'),
        ('std', 'Standard(s)'),
        ('accessory', 'Accessoire(s)')
    ], string='Motif de facturation non applicable', default='')

    is_reactif_dedie = fields.Boolean(string='Réactif dédié')
    is_reactif_manuel = fields.Boolean(string='Réactif manuel')
    standard_ids = fields.Many2many('product.template', 'tender_line_reactif_standards_rel', 'reactif_id',
                                    'standard_id', string='Standards',
                                    domain=[('is_standard', '=', True)])

    related_line_id = fields.Many2one('tender.line', string='Related line')

    lost_reason_id = fields.Many2one('crm.lost.reason', string='Motifs du refus', index=True,
                                     track_visibility='onchange')
    code = fields.Char(string='code')
    concurrent_price_unit = fields.Float('Prix concurrent', digits=dp.get_precision('Product Price'), default=0.0)
    conditionnement = fields.Char(string='Conditionnement')

    def _get_display_price(self, product):
        if self.tender_id.pricelist_id.discount_policy == 'with_discount':
            return product.with_context(pricelist=self.tender_id.pricelist_id.id).price
        product_context = dict(self.env.context, partner_id=self.tender_id.partner_id.id,
                               date=self.tender_id.date_order, uom=self.product_uom.id)

        final_price, rule_id = self.tender_id.pricelist_id.with_context(product_context).get_product_price_rule(
            self.product_id, self.product_uom_qty or 1.0, self.tender_id.partner_id)
        base_price, currency = self.with_context(product_context)._get_real_price_currency(product, rule_id,
                                                                                           self.product_uom_qty,
                                                                                           self.product_uom,
                                                                                           self.tender_id.pricelist_id.id)
        if currency != self.tender_id.pricelist_id.currency_id:
            base_price = currency._convert(
                base_price, self.tender_id.pricelist_id.currency_id,
                self.tender_id.company_id, self.tender_id.date_order or fields.Date.today())
        return max(base_price, final_price)

    @api.onchange('product_id')
    def product_id_change(self):
        if not self.product_id:
            return {'domain': {'product_uom': []}}
        vals = {}
        domain = {'product_uom': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
        if not self.product_uom or (self.product_id.uom_id.id != self.product_uom.id):
            vals['product_uom'] = self.product_id.uom_id
            vals['product_uom_qty'] = self.product_uom_qty or 1.0
        product = self.product_id.with_context(
            lang=self.tender_id.partner_id.lang,
            partner=self.tender_id.partner_id,
            quantity=vals.get('product_uom_qty') or self.product_uom_qty,
            date=self.tender_id.date_order,
            pricelist=self.tender_id.pricelist_id.id,
            uom=self.product_uom.id
        )
        result = {'domain': domain}
        name = self.get_sale_order_line_multiline_description_sale(product)
        vals.update(name=name)
        self._compute_tax_id()
        if self.tender_id.pricelist_id and self.tender_id.partner_id:
            vals['price_unit'] = self.env['account.tax']._fix_tax_included_price_company(
                self._get_display_price(product), product.taxes_id, self.tax_id, self.company_id)
        self.update(vals)
        title = False
        message = False
        warning = {}
        if product.sale_line_warn != 'no-message':
            title = _("Warning for %s") % product.name
            message = product.sale_line_warn_msg
            warning['title'] = title
            warning['message'] = message
            result = {'warning': warning}
            if product.sale_line_warn == 'block':
                self.product_id = False

        # if self.product_id.is_reactif_dedie :
        #     self.is_reactif_dedie =True
        #     self.standard_ids = [(6,0,self.product_id.standard_ids.ids)]
        #     self.is_reactif_manuel =False
        # else :
        #     self.is_reactif_dedie =False

        # if self.product_id.is_reactif_manuel :
        #     self.is_reactif_manuel =True
        #     self.standard_ids = [(6,0,self.product_id.standard_ids.ids)]
        #     self.is_reactif_dedie =False

        # else :
        #     self.is_reactif_manuel =False

        return result

    @api.onchange('product_uom', 'product_uom_qty')
    def product_uom_change(self):
        if not self.product_uom or not self.product_id:
            self.price_unit = 0.0
            return
        if self.tender_id.pricelist_id and self.tender_id.partner_id:
            product = self.product_id.with_context(
                lang=self.tender_id.partner_id.lang,
                partner=self.tender_id.partner_id,
                quantity=self.product_uom_qty,
                date=self.tender_id.date_order,
                pricelist=self.tender_id.pricelist_id.id,
                uom=self.product_uom.id,
                fiscal_position=self.env.context.get('fiscal_position')
            )
            self.price_unit = self.env['account.tax']._fix_tax_included_price_company(self._get_display_price(product),
                                                                                      product.taxes_id, self.tax_id,
                                                                                      self.company_id)

    def name_get(self):
        result = []
        for so_line in self.sudo():
            name = '%s - %s' % (so_line.tender_id.name, so_line.name.split('\n')[0] or so_line.product_id.name)
            if so_line.order_partner_id.ref:
                name = '%s (%s)' % (name, so_line.order_partner_id.ref)
            result.append((so_line.id, name))
        return result

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if operator in ('ilike', 'like', '=', '=like', '=ilike'):
            args = expression.AND([
                args or [],
                ['|', ('tender_id.name', operator, name), ('name', operator, name)]
            ])
        return super(TenderLines, self)._name_search(name, args=args, operator=operator, limit=limit,
                                                     name_get_uid=name_get_uid)

    def _get_real_price_currency(self, product, rule_id, qty, uom, pricelist_id):
        PricelistItem = self.env['product.pricelist.item']
        field_name = 'lst_price'
        currency_id = None
        product_currency = None
        if rule_id:
            pricelist_item = PricelistItem.browse(rule_id)
            if pricelist_item.pricelist_id.discount_policy == 'without_discount':
                while pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id and pricelist_item.base_pricelist_id.discount_policy == 'without_discount':
                    price, rule_id = pricelist_item.base_pricelist_id.with_context(uom=uom.id).get_product_price_rule(
                        product, qty, self.tender_id.partner_id)
                    pricelist_item = PricelistItem.browse(rule_id)

            if pricelist_item.base == 'standard_price':
                field_name = 'standard_price'
            if pricelist_item.base == 'pricelist' and pricelist_item.base_pricelist_id:
                field_name = 'price'
                product = product.with_context(pricelist=pricelist_item.base_pricelist_id.id)
                product_currency = pricelist_item.base_pricelist_id.currency_id
            currency_id = pricelist_item.pricelist_id.currency_id

        product_currency = product_currency or (
                product.company_id and product.company_id.currency_id) or self.env.user.company_id.currency_id
        if not currency_id:
            currency_id = product_currency
            cur_factor = 1.0
        else:
            if currency_id.id == product_currency.id:
                cur_factor = 1.0
            else:
                cur_factor = currency_id._get_conversion_rate(product_currency, currency_id,
                                                              self.company_id or self.env.user.company_id,
                                                              self.tender_id.date_order or fields.Date.today())

        product_uom = self.env.context.get('uom') or product.uom_id.id
        if uom and uom.id != product_uom:
            uom_factor = uom._compute_price(1.0, product.uom_id)
        else:
            uom_factor = 1.0

        return product[field_name] * uom_factor * cur_factor, currency_id

    def _get_protected_fields(self):
        return [
            'product_id', 'name', 'price_unit', 'product_uom', 'product_uom_qty',
            'tax_id'
        ]

    @api.onchange('product_id', 'price_unit', 'product_uom', 'product_uom_qty', 'tax_id')
    def _onchange_discount(self):
        if not (self.product_id and self.product_uom and
                self.tender_id.partner_id and self.tender_id.pricelist_id and
                self.tender_id.pricelist_id.discount_policy == 'without_discount' and
                self.env.user.has_group('sale.group_discount_per_so_line')):
            return
        self.discount = 0.0
        product = self.product_id.with_context(
            lang=self.tender_id.partner_id.lang,
            partner=self.tender_id.partner_id,
            quantity=self.product_uom_qty,
            date=self.tender_id.date_order,
            pricelist=self.tender_id.pricelist_id.id,
            uom=self.product_uom.id,
            fiscal_position=self.env.context.get('fiscal_position')
        )
        product_context = dict(self.env.context, partner_id=self.tender_id.partner_id.id,
                               date=self.tender_id.date_order, uom=self.product_uom.id)
        price, rule_id = self.tender_id.pricelist_id.with_context(product_context).get_product_price_rule(
            self.product_id, self.product_uom_qty or 1.0, self.tender_id.partner_id)
        new_list_price, currency = self.with_context(product_context)._get_real_price_currency(product, rule_id,
                                                                                               self.product_uom_qty,
                                                                                               self.product_uom,
                                                                                               self.tender_id.pricelist_id.id)
        if new_list_price != 0:
            if self.tender_id.pricelist_id.currency_id != currency:
                new_list_price = currency._convert(
                    new_list_price, self.tender_id.pricelist_id.currency_id,
                    self.tender_id.company_id, self.tender_id.date_order or fields.Date.today())
            discount = (new_list_price - price) / new_list_price * 100
            if discount > 0:
                self.discount = discount

    def get_sale_order_line_multiline_description_sale(self, product):
        return product.get_product_multiline_description_sale()
