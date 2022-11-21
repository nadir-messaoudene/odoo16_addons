# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class TendersLost(models.TransientModel):
    _name = 'tender.lost'
    _description = 'Get Lost Reason'

    lost_reason_id = fields.Many2one('crm.lost.reason', 'Lost Reason')
    code = fields.Char(string='code')
    price_unit = fields.Float('Prix concurrent', digits=dp.get_precision('Product Price'), default=0.0)
    conditionnement = fields.Char(string='Conditionnement')

    def action_lost_reason_apply(self):
        leads = self.env['crm.lead'].browse(self.env.context.get('active_ids'))
        leads.write({'lost_reason_id': self.lost_reason_id.id})
        if self.lost_reason_id.code != 'multi' :
            leads.tender_line.write({'lost_reason_id': self.lost_reason_id.id})
        return leads.action_set_tender_lost()

    def action_lost_reason_apply_without_reason(self):
        leads = self.env['crm.lead'].browse(self.env.context.get('active_ids'))
        return leads.action_set_tender_lost()

    def action_lost_reason_apply_from_line(self):
        _logger.warning('self.env.context %s',self.env.context)
        tender_line = self.env['tender.line'].browse(self.env.context.get('active_ids'))
        if tender_line.state not in ('lost','partial_won'):
            raise UserError(_('Vous ne pouvez indiquer le motif de la perte que pour les lignes non retenues ou partiellement retenues.'))
        tender_line.write({'lost_reason_id': self.lost_reason_id.id, 'code': self.code, 'concurrent_price_unit': self.price_unit, 'conditionnement': self.conditionnement})
        return
    
    @api.onchange('lost_reason_id')
    def lost_reason_id_change(self):
        _logger.error(' IN invoicing_change')
        if self.lost_reason_id :
            self.code =  self.lost_reason_id.code
