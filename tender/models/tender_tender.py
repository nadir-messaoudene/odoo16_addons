from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class LeadTender(models.Model):
    _inherit = 'crm.lead'
    _description = "Tender"

    contract_number = fields.Integer(compute='_compute_contracts', string="Number of Contracts")
    tender_line = fields.One2many('tender.line', 'tender_id', string='Participations', readonly=True,
                                  states={'draft': [('readonly', False)]}, copy=True, auto_join=True)

    # Equipment
    equipment_id = fields.One2many('equipment.template', 'tender_id', string='Equipment')
    annual_depreciation = fields.Float(compute='_get_annual_depreciation', readonly=True)
    global_cost = fields.Float(compute='_get_global_cost', readonly=True)
    # ===================================================================================================================
    # Profitability
    total_directe_charges = fields.Float(compute='_get_total_directe_charges', readonly=True)
    indirect_cost = fields.Float(required=True)
    exploitation_total_charges = fields.Float(compute='_get_exploitation_total_charges', readonly=True)
    financial_charges = fields.Float(required=True)
    global_charges = fields.Float(compute='_get_global_charges', readonly=True)
    exploitation_margin = fields.Float(compute='_get_exploitation_margin', readonly=True)
    net_margin = fields.Float(compute='_get_net_margin', readonly=True)
    ratio_exploitation_margin = fields.Float(compute='_get_ratio_exploitation_margin', readonly=True, store=True)
    ratio_net_margin = fields.Float(compute='_get_ratio_net_margin', readonly=True, store=True)
    # ===================================================================================================================
    type = fields.Selection(selection_add=[('tenders', 'Appel d\'offre')],
                            ondelete={'tenders': 'set default'})
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', readonly=True,
                                   help="Pricelist for current sales order.")
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('sent', 'Envoyé'),
        ('won', 'Retenu'),
        ('partial_won', 'Partiellement Retenu'),
        ('lost', 'Non Retenu'),
        ('cancel', 'Annulé'),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', track_sequence=3,
        default='draft')

    currency_id = fields.Many2one("res.currency", related='company_id.currency_id', string="Currency", readonly=True,
                                  required=True)
    amount_untaxed = fields.Monetary(string='Montant HT', store=True, readonly=True, compute='_amount_all',
                                     track_visibility='onchange', track_sequence=5)
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all',
                                   track_visibility='always', track_sequence=6)
    date_order = fields.Date(string='Date', index=True, copy=False, readonly=True,
                             states={'draft': [('readonly', False)]})  # string='Date de l\'appel d\'offre'
    date_closed_tender = fields.Date(string='Date de clôture', index=True, copy=False, readonly=True,
                                     states={'draft': [('readonly', False)]})
    tender_type = fields.Selection([
        ('AO', 'Appel d\'offre'),
        ('consultation', 'Consultation'),
    ], string='Type', required=True, readonly=True)
    contract_type = fields.Selection([
        ('ao_sale', 'Vente'),
        ('ao_mad', 'Mise a disposition'),
    ], string='Type du contrat ', readonly=True, states={'draft': [('readonly', False)]})

    contract_length = fields.Selection([
        ('1', '3 mois'),
        ('2', '6 mois'),
        ('3', '1 an'),
        ('4', '2 ans'),
        ('5', '3 ans'),
        ('6', '4 ans'),
        ('7', '5 ans')
    ], string='Durée du contrat', readonly=True, states={'draft': [('readonly', False)]})

    @api.depends('net_margin', 'amount_untaxed')
    def _get_ratio_net_margin(self):
        if self.amount_untaxed != 0.0:
            self.ratio_net_margin = (self.net_margin / self.amount_untaxed) * 100

    @api.depends('exploitation_margin', 'amount_untaxed')
    def _get_ratio_exploitation_margin(self):
        if self.amount_untaxed != 0.0:
            self.ratio_exploitation_margin = (self.exploitation_margin / self.amount_untaxed) * 100

    @api.depends('exploitation_total_charges', 'amount_untaxed', 'financial_charges')
    def _get_net_margin(self):
        self.net_margin = self.amount_untaxed - self.exploitation_total_charges - self.financial_charges

    @api.depends('exploitation_total_charges', 'amount_untaxed')
    def _get_exploitation_margin(self):
        self.exploitation_margin = self.amount_untaxed - self.exploitation_total_charges

    @api.depends('exploitation_total_charges', 'financial_charges')
    def _get_global_charges(self):
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

    @api.depends('total_directe_charges', 'indirect_cost')
    def _get_exploitation_total_charges(self):
        self.exploitation_total_charges = self.total_directe_charges + self.indirect_cost

    @api.depends('tender_line')
    def _get_global_cost(self):
        global_cost = 0.0
        for line in self.tender_line:
            global_cost += line.product_id.standard_price * line.product_uom_qty
        self.global_cost = global_cost

    @api.depends('tender_line.price_total')
    def _amount_all(self):
        for order in self:
            amount_untaxed = amount_tax = 0.0
            for line in order.tender_line:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        raise UserError(_('Il n\'est pas possible de dupliquer l\'appel d\'offre, veuillez créer un nouveau'))

    def _compute_contracts(self):
        for lead in self:
            contracts = self.env['tender.contract'].search([('lead_id', '=', self.id), ('state', '!=', 'cancel')])
            lead.contract_number = len(contracts)

    def _all_compute_contracts(self):
        for lead in self:
            contracts = self.env['tender.contract'].search([('lead_id', '=', self.id)])
            lead.contract_number = len(contracts)

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        values = self._onchange_partner_id_values(self.partner_id.id if self.partner_id else False)
        if self.partner_id.team_id:
            values['team_id'] = self.partner_id.team_id.id
        values[
            'user_id'] = self.partner_id.user_id.id or self.partner_id.commercial_partner_id.user_id.id or self.env.uid
        self.update(values)

    def _onchange_partner_id_values(self, partner_id):
        """ returns the new values when partner_id has changed """
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)

            partner_name = partner.parent_id.name
            if not partner_name and partner.is_company:
                partner_name = partner.name

            return {
                'partner_name': partner_name,
                'contact_name': partner.name if not partner.is_company else False,
                'title': partner.title.id,
                'street': partner.street,
                'street2': partner.street2,
                'city': partner.city,
                'state_id': partner.state_id.id,
                'country_id': partner.country_id.id,
                'email_from': partner.email,
                'phone': partner.phone,
                'mobile': partner.mobile,
                'zip': partner.zip,
                'function': partner.function,
                'website': partner.website,
            }
        return {}

    def action_confirm(self):
        for lead in self:
            if not lead.tender_line:
                if lead.tender_type == 'AO':
                    raise UserError(_('Veuillez ajouter au moins une ligne à l\'appel d\'offre.'))
                elif lead.tender_type == 'consultation':
                    raise UserError(_('Veuillez ajouter au moins une ligne à la consultation.'))

            lead.write({'state': 'confirmed'})
            for line in lead.tender_line:
                line.write({'state': 'confirmed'})

    def action_sent(self):
        for lead in self:
            lead.write({'state': 'sent'})
            for line in lead.tender_line:
                line.write({'state': 'sent'})

    def action_won(self):
        for lead in self:
            lead.write({'state': 'won'})
            for line in lead.tender_line:
                line.write({'state': 'won', 'won_uom_qty': line.product_uom_qty})

    def action_partial_won(self):
        for lead in self:
            lead.write({'state': 'partial_won'})

    def action_cancel(self):
        for lead in self:
            lead.write({'state': 'cancel'})
            for line in lead.tender_line:
                line.write({'state': 'cancel'})

    def set_draft(self):
        for lead in self:
            lead.write({'state': 'draft'})
            for line in lead.tender_line:
                line.write({'state': 'draft'})

    def action_set_tender_lost(self):
        for lead in self:
            lead.write({'state': 'lost'})
            for line in lead.tender_line:
                line.write({'state': 'lost'})

    def unlink(self):
        for tender in self:
            if tender.type == 'tenders' and tender.state not in ('draft', 'cancel'):
                raise UserError(_('Vous ne pouvez supprimer que les appels d\'offres à l\'état brouillon ou annulé.'))
        return super(LeadTender, self).unlink()


class LostReason(models.Model):
    _inherit = "crm.lost.reason"

    type = fields.Selection([
        ('CRM', 'CRM'),
        ('AO', 'AO')
    ], string='Type')

    code = fields.Selection([
        ('tech', 'Technique'),
        ('finance', 'Finance'),
        ('multi', 'Plusieurs'),
        ('other', 'Autres'),
        ('over', 'Surestimation')
    ], string='Code')
