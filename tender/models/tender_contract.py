# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare
from odoo.addons import decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)


class TenderContract(models.Model):
    _name = "tender.contract"
    _description = "Tender contract"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    equipment_id = fields.One2many('equipment.template',string='Equipment', compute='_get_equipments', readonly=True,
                                   help="Equipments mis a dispositions ou vendus relatif a l'appel d'offre.")

    designation_list_id = fields.Many2one('designation.list', string='designation list', compute='_get_designation',
                                          readonly=True,
                                          help="Machines mises a dispositions relatif a l'appel d'offre.")

    annual_depreciation = fields.Float(compute='_get_annual_depreciation', readonly=True)
    global_cost = fields.Float(compute='_get_global_cost', readonly=True)
    total_directe_charges = fields.Float(compute='_get_total_directe_charges', readonly=True)

    exploitation_total_charges = fields.Float(compute='_get_exploitation_total_charges', readonly=True)

    global_charges = fields.Float(compute='_get_global_charges', readonly=True)

    exploitation_margin = fields.Float(compute='_get_exploitation_margin', readonly=True)
    net_margin = fields.Float(compute='_get_net_margin', readonly=True)

    ratio_exploitation_margin = fields.Float(compute='_get_ratio_exploitation_margin', readonly=True, store=True)
    ratio_net_margin = fields.Float(compute='_get_ratio_net_margin', readonly=True, store=True)

    tender_indirect_cost = fields.Float(required=True, readonly=False, default=0.00)
    financial_charges = fields.Float(required=True, readonly=False, default=0.00)
    active = fields.Boolean('Active', default=True, track_visibility=True)
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')
    company_id = fields.Many2one('res.company', string='Company', index=True,
                                 default=lambda self: self.env.user.company_id.id)
    user_id = fields.Many2one('res.users', string='Salesperson', track_visibility='onchange',
                              default=lambda self: self.env.user)
    description = fields.Text('Notes')
    name = fields.Char('Contract N°', required=True, index=True)
    partner_id = fields.Many2one('res.partner', required=True, string='Customer', track_visibility='onchange',
                                 track_sequence=1, index=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('running', 'En cours'),
        ('done', 'Ctôturé'),
        ('suspended', 'Suspendu'),
        ('cancel', 'Annulé'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', track_sequence=3,
        default='draft')

    contract_lines = fields.One2many('contract.lines', 'tender_id', string='Participations')
    currency_id = fields.Many2one("res.currency", related='company_id.currency_id', string="Currency", required=True)
    amount_untaxed = fields.Monetary(string='Montant HT', store=True, readonly=True, compute='_amount_all',
                                     track_visibility='onchange', track_sequence=5)
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all',
                                   track_visibility='always', track_sequence=6)
    begin_date = fields.Date(string='Begin date', required=True)
    end_date = fields.Date(string='Closed date', required=True)
    signed_date = fields.Date(string='Date de signature', readonly=True, states={'draft': [('readonly', False)]})
    lead_id = fields.Many2one('crm.lead', string='Appel d\'offre', readonly=True, track_visibility='onchange',
                              track_sequence=1, index=True)
    company_currency = fields.Many2one(string='Currency', related='company_id.currency_id', readonly=True,
                                       relation="res.currency")
    sale_number = fields.Integer(compute='_compute_sale_amount_total', string="Number of Quotations")
    order_ids = fields.One2many('sale.order', 'contract_id', string='Orders', readonly=True)
    invoice_ids = fields.One2many('account.move', 'contract_id', string='Factures', readonly=True)
    contract_extra_lines = fields.One2many('contract.extra.lines', 'tender_id', string='Participations', readonly=True)

    amount_total_contract_to_invoice = fields.Monetary(string='Total à facturer ', store=False, readonly=True,
                                                       compute='_amount_all_contract_values')
    amount_total_contract_invoiced = fields.Monetary(string='Total factures brouillons', store=False, readonly=True,
                                                     compute='_amount_all_contract_values')

    amount_total_contract_invoiced_validated = fields.Monetary(string='Total factures validées', store=False,
                                                               readonly=True,
                                                               compute='_amount_all_contract_values')

    amount_total_contract_follow = fields.Monetary(string='Total encours ', store=False, readonly=True,
                                                   compute='_amount_all_contract_values', track_visibility='always',
                                                   track_sequence=6)
    percentage_of_target = fields.Float(compute='_amount_all_contract_values', string='Objectif(%)', store=True,
                                        readonly=True)

    percentage_of_target_hors = fields.Float(
        compute='_amount_all_contract_values', string='Objectif(%)', store=True, readonly=True)
    amount_total_hors_contract_to_invoice = fields.Monetary(string='Total à facturer ', store=False, readonly=True,
                                                            compute='_amount_all_contract_values')
    amount_total_hors_contract_invoiced = fields.Monetary(string='Total factures brouillons', store=False,
                                                          readonly=True,
                                                          compute='_amount_all_contract_values')
    amount_total_hors_contract_invoiced_validated = fields.Monetary(string='Total factures validées', store=False,
                                                                    readonly=True,
                                                                    compute='_amount_all_contract_values')
    amount_total_hors_contract_follow = fields.Monetary(string='Total encours ', store=False, readonly=True,
                                                        compute='_amount_all_contract_values',
                                                        track_visibility='always', track_sequence=6)

    amount_total_to_invoice = fields.Monetary(string='Total à facturer ', store=False, readonly=True,
                                              compute='_amount_all_contract_values')
    amount_total_invoiced_validated = fields.Monetary(string='Total factures validées ', store=False, readonly=True,
                                                      compute='_amount_all_contract_values')
    amount_total_invoiced = fields.Monetary(string='Total factures brouillon', store=False, readonly=True,
                                            compute='_amount_all_contract_values')
    amount_total_follow = fields.Monetary(string='Total encours ', store=False, readonly=True,
                                          compute='_amount_all_contract_values', track_visibility='always',
                                          track_sequence=6)
    global_percentage_of_target = fields.Float(compute='_amount_all_contract_values', string='Objectif(%)', store=True,
                                               readonly=True)

    total_invoice_validated = fields.Monetary(compute='_amount_all_contract_values', string='Total factures validés',
                                              store=True,
                                              readonly=True)

    amount_to_invoice = fields.Monetary(store=True, readonly=True, track_sequence=6)

    contract_type = fields.Selection([
        ('ao_sale', 'Vente'),
        ('ao_mad', 'MAD'),
        ('prived_mad', 'MAD PRIVE'),
        ('consultation', 'Consultation'),
    ], string='Type du contrat ', required=True)

    contract_length = fields.Selection([
        ('1', '3 mois'),
        ('2', '6 mois'),
        ('3', '1 an'),
        ('4', '2 ans'),
        ('5', '3 ans'),
        ('6', '4 ans'),
        ('7', '5 ans')

    ], string='Durée du contrat')

    blocked = fields.Boolean(compute='_compute_blocked', string="Contrat bloqué")

    @api.depends('order_ids')
    def _get_global_cost(self):
        global_cost = 0.0
        for order in self.order_ids:
            for line in order.order_line:
                global_cost += line.product_id.standard_price * line.qty_delivered
        self.global_cost = global_cost

    @api.depends('net_margin', 'amount_total_invoiced')
    def _get_ratio_net_margin(self):
        if self.amount_total_invoiced != 0.0:
            self.ratio_net_margin = (self.net_margin / self.amount_total_invoiced) * 100

    @api.depends('exploitation_margin', 'amount_total_invoiced')
    def _get_ratio_exploitation_margin(self):
        self.ratio_exploitation_margin = 0.0
        if self.amount_total_invoiced != 0.0:
            self.ratio_exploitation_margin = (self.exploitation_margin / self.amount_total_invoiced) * 100

    @api.depends('exploitation_total_charges', 'amount_total_invoiced', 'financial_charges')
    def _get_net_margin(self):
        self.net_margin = self.amount_total_invoiced_validated - self.exploitation_total_charges - self.financial_charges

    @api.depends('exploitation_total_charges', 'amount_total_invoiced_validated')
    def _get_exploitation_margin(self):
        self.exploitation_margin = self.amount_total_invoiced_validated - self.exploitation_total_charges

    @api.depends('exploitation_total_charges', 'financial_charges')
    def _get_global_charges(self):
        self.global_charges = 0.0
        self.global_charges = self.exploitation_total_charges + self.financial_charges

    @api.depends('equipment_id')
    def _get_annual_depreciation(self):
        annual_depreciation = 0.0
        for line in self.equipment_id:
            annual_depreciation += line.depreciation
        self.annual_depreciation = annual_depreciation

    @api.depends('annual_depreciation', 'global_cost')
    def _get_total_directe_charges(self):
        self.total_directe_charges = self.annual_depreciation + self.global_cost

    @api.depends('total_directe_charges', 'tender_indirect_cost', 'annual_depreciation')
    def _get_exploitation_total_charges(self):
        self.exploitation_total_charges = self.total_directe_charges + self.tender_indirect_cost

    def _get_equipments(self):
        self.equipment_id = self.env['equipment.template'].search([('tender_contract_id', '=', self.id)])

    def _get_designation(self):
        self.designation_list_id = self.env['designation.list'].search([('tender_id', '=', self.id)])

    @api.depends('contract_lines.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.contract_lines:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })

    def _compute_blocked(self):
        for contract in self:
            contract.blocked = False
            if contract.amount_total_follow >= contract.amount_total:
                contract.blocked = True

    @api.depends('contract_lines.qty_delivered', 'contract_lines.qty_invoiced', 'contract_lines.qty_invoiced_validated',
                 'contract_extra_lines', 'contract_lines.subtotal_invoiced', 'contract_lines.subtotal_to_invoice')
    def _amount_all_contract_values(self):
        for contract in self:
            amount_total_to_invoice_hors = 0.0
            amount_total_invoiced_hors = 0.0
            amount_total_invoiced_hors_validated = 0.0
            amount_untaxed_hors = 0.0

            for extra_line in contract.contract_extra_lines:
                amount_total_to_invoice_hors += extra_line.price_reduce_taxinc * extra_line.qty_to_invoice
                amount_total_invoiced_hors_validated += extra_line.price_reduce_taxinc * extra_line.qty_invoiced_validated
                amount_total_invoiced_hors += extra_line.price_reduce_taxinc * extra_line.qty_invoiced - amount_total_invoiced_hors_validated
                amount_untaxed_hors += extra_line.price_subtotal

            amount_total_invoiced = 0.0
            amount_total_to_invoice = 0.0
            amount_total_invoiced_draft = 0.0
            amount_total_invoiced_untaxed = 0.0

            for invoice in contract.invoice_ids.filtered(lambda inv: inv.state in ('open', 'in_payment', 'paid')):
                amount_total_invoiced += invoice.amount_total
                amount_total_invoiced_untaxed += invoice.amount_untaxed_invoice_signed

            for invoice in contract.invoice_ids.filtered(lambda inv: inv.state in 'draft'):
                amount_total_invoiced_draft += invoice.amount_total
            for contract_line in contract.contract_lines:
                amount_total_to_invoice += contract_line.subtotal_to_invoice

            contract.update({
                'amount_total_hors_contract_to_invoice': amount_total_to_invoice_hors,
                'amount_total_hors_contract_invoiced': amount_total_invoiced_hors,
                'amount_total_hors_contract_invoiced_validated': amount_total_invoiced_hors_validated,
                'amount_total_hors_contract_follow': amount_total_to_invoice_hors +
                                                     amount_total_invoiced_hors +
                                                     amount_total_invoiced_hors_validated,
                'percentage_of_target_hors': 100 * (amount_total_invoiced - amount_total_invoiced_hors_validated) / contract.amount_total
                if contract.amount_total > 0.0 else 0.0,

                'amount_total_contract_to_invoice': amount_total_to_invoice,
                'amount_total_contract_invoiced_validated': amount_total_invoiced - amount_total_invoiced_hors_validated,
                'amount_total_contract_invoiced': amount_total_invoiced_draft - amount_total_invoiced_hors,
                'amount_total_contract_follow': (amount_total_invoiced - amount_total_invoiced_hors_validated) +
                                                (amount_total_invoiced_draft - amount_total_invoiced_hors) +
                                                amount_total_to_invoice,
                'percentage_of_target': 100 * ((amount_total_invoiced - amount_total_invoiced_hors_validated) +
                                               amount_total_to_invoice) / contract.amount_total
                if contract.amount_total > 0.0 else 0.0,

                'amount_total_to_invoice': amount_total_to_invoice_hors + amount_total_to_invoice,
                'amount_total_invoiced': (amount_total_invoiced_draft - amount_total_invoiced_hors) +
                                         amount_total_invoiced_hors,
                'amount_total_follow': amount_total_invoiced + amount_total_invoiced_draft + amount_total_to_invoice +
                                       amount_total_to_invoice_hors,
                'global_percentage_of_target': 100 * (amount_total_invoiced + amount_total_invoiced_draft)
                                               / contract.amount_total if contract.amount_total > 0.0 else 0.0,
                'amount_total_invoiced_validated': (amount_total_invoiced - amount_total_invoiced_hors_validated) +
                                                   amount_total_invoiced_hors_validated
            })

    _sql_constraints = [
        ('name_company_uniq', 'unique (name,company_id)', 'The name of the contract must be unique per company !')
    ]

    def _compute_sale_amount_total(self):
        for contract in self:
            nbr = 0
            for order in contract.order_ids:
                if order.state != 'cancel':
                    nbr += 1
            contract.sale_number = nbr

    def copy_data(self, default=None):
        if not self.contract_type == 'prived_mad':
            raise UserError(_('Il n\'est pas possible de dupliquer le contrat, veuillez créer un nouveau'))
        default = dict(default or {}, name=_("%s (Copy)") % self.name)
        if 'contract_lines' not in default:
            default['contract_lines'] = [(0, 0, line.copy_data()[0]) for line in
                                         self.contract_lines.filtered(lambda l: l.pattern_not_invoicing != 'std')]
        return super(TenderContract, self).copy_data(default=default)

    def unlink(self):
        for contract in self:
            if contract.state not in ('draft', 'cancel'):
                raise UserError(_('Vous ne pouvez supprimer que les contrats à l\'état brouillon ou annulé.'))
        return super(TenderContract, self).unlink()

    @api.onchange('begin_date')
    def _onchange_begin_date(self):
        res = {}
        if self.begin_date and self.end_date and self.end_date <= self.begin_date:
            self.begin_date = ''
            res['warning'] = {
                'title': _('La date demandée est incorrecte.'),
                'message': _("La date début du contrat est ultérieure ou égale à la date fin.")
            }
        return res

    @api.onchange('end_date')
    def _onchange_end_date(self):
        res = {}
        if self.end_date and self.begin_date and self.end_date <= self.begin_date:
            self.end_date = ''
            res['warning'] = {
                'title': _('La date demandée est incorrecte.'),
                'message': _("La date fin du contrat est antérieure ou égale à la date début.")
            }
        return res

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        values = {}
        if self.partner_id.team_id:
            values['team_id'] = self.partner_id.team_id.id
        values[
            'user_id'] = self.partner_id.user_id.id or self.partner_id.commercial_partner_id.user_id.id or self.env.uid
        self.update(values)

    def action_confirm(self):
        for lead in self:
            if not lead.contract_lines:
                raise UserError(_('Veuillez ajouter au moins une ligne au contrat'))
            lead.write({'state': 'confirmed'})
            for line in lead.contract_lines:
                line.write({'state': 'confirmed'})

    def action_running(self):
        for lead in self:
            lead.write({'state': 'running'})
            for line in lead.contract_lines:
                line.write({'state': 'running'})

    def action_done(self):
        for lead in self:
            lead.write({'state': 'done'})
            for line in lead.contract_lines:
                line.write({'state': 'done'})

    def action_suspended(self):
        for lead in self:
            lead.write({'state': 'suspended'})
            for line in lead.contract_lines:
                line.write({'state': 'suspended'})

    def action_cancel(self):
        for contract in self:
            contract.write({'state': 'cancel'})
            for line in contract.contract_lines:
                line.write({'state': 'cancel'})

    def action_generate_extra_lines(self):
        self.contract_extra_lines.unlink()
        for order in self.order_ids:
            for line in order.order_line.filtered(lambda so: so.state != 'cancel'):
                if not line.contract_line_id:
                    line_vals = {'tender_id': self.id,
                                 'name': line.name,
                                 'sequence': line.sequence,
                                 'price_unit': line.price_unit,
                                 'price_subtotal': line.price_subtotal,
                                 'price_tax': line.price_tax,
                                 'price_total': line.price_total,
                                 'price_reduce': line.price_reduce,
                                 'price_reduce_taxinc': line.price_reduce_taxinc,
                                 'price_reduce_taxexcl': line.price_reduce_taxexcl,
                                 'discount': line.discount,
                                 'product_id': line.product_id.id,
                                 'product_uom_qty': line.product_uom_qty,
                                 'product_uom': line.product_uom.id,
                                 'untaxed_amount_invoiced': line.qty_invoiced * line.price_reduce_taxexcl,
                                 'untaxed_amount_to_invoice': line.qty_to_invoice * line.price_reduce_taxexcl,
                                 'subtotal_encours': line.qty_invoiced * line.price_reduce_taxexcl + line.qty_to_invoice * line.price_reduce_taxexcl,
                                 'salesman_id': line.salesman_id.id,
                                 'company_id': line.company_id.id,
                                 'currency_id': line.currency_id.id,
                                 'order_partner_id': line.order_partner_id.id,
                                 'display_type': line.display_type,
                                 'order_partner_id': line.order_partner_id.id,
                                 'order_id': line.order_id.id,
                                 'qty_delivered': line.qty_delivered,
                                 'qty_invoiced': line.qty_invoiced,
                                 'qty_invoiced_validated': line.qty_invoiced_validated,
                                 'qty_to_invoice': line.qty_to_invoice,
                                 'tax_id': [[6, False, line.tax_id.ids]],
                                 }
                    self.env['contract.extra.lines'].create(line_vals)

    def generate_pricelist(self):
        for contract in self:
            pricelist_vals = {'name': str(contract.name), 'partner_id': contract.partner_id.id}
            pricelist = self.env['product.pricelist'].create(pricelist_vals)
            contract.write({'pricelist_id': pricelist.id})
            for line in contract.contract_lines.filtered(lambda l: l.invoicing == 'to_invoice'):
                pricelist_item_vals = {'pricelist_id': pricelist.id,
                                       'product_tmpl_id': line.product_id.product_tmpl_id.id,
                                       'product_uom': line.product_uom.id,
                                       'applied_on': '1_product',
                                       'base': 'list_price',
                                       'date_start': self.begin_date,
                                       'date_end': self.end_date,
                                       'compute_price': 'fixed',
                                       'fixed_price': line.price_unit,
                                       'note': contract.name
                                       }

                self.env['product.pricelist.item'].create(pricelist_item_vals)
