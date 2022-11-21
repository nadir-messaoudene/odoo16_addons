# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)

class TenderLinesWizard(models.TransientModel):
    _name = 'tender.line.wizard'
    _description = 'Tender Line Wizard'
    
    name = fields.Text(string='Description', readonly=True )
    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    product_uom_qty = fields.Float(string='Ordered Quantity', readonly=True, digits=dp.get_precision('Product Unit of Measure'))
    won_product_uom_qty = fields.Float(string='Quantité retenue', digits=dp.get_precision('Product Unit of Measure'))
    product_uom = fields.Many2one('uom.uom', readonly=True, string='Unit of Measure')
    tender_line_id = fields.Many2one('tender.line', string='Ligne de l\'appel d\offre')

class TendersPartialWon(models.TransientModel):
    _name = 'tender.partial.won'
    _description = 'Partial Won'

    tender_lines = fields.Many2many('tender.line.wizard', 'tender_partial_won_wiz_rel', 'tender_id', 'wiz_id', string='Participations',
                                    domain="[('tender_line_id', 'in', tender_lines_)]") 
    generated_lines = fields.Boolean('field used for technical purpose', default = False)
    lead_id = fields.Many2one('crm.lead', string='Tender')
    tender_lines_ = fields.Many2many('tender.line', 'tender_partial_won_line_rel', 'line_id', 'wiz_id', string='used for technical purpose')

    def action_partial_won_apply(self):
        lead = self.lead_id
        for line in self.tender_lines : 
            if line.won_product_uom_qty == line.tender_line_id.product_uom_qty :
                line.tender_line_id.write({'state': 'won','won_uom_qty':line.won_product_uom_qty})
            else:
                if line.won_product_uom_qty == 0.0 : 
                    line.tender_line_id.write({'state': 'lost','won_uom_qty':0.0})
                    
                elif line.won_product_uom_qty < line.tender_line_id.product_uom_qty :
                    line.tender_line_id.write({'state': 'partial_won','won_uom_qty':line.won_product_uom_qty})
                    
        
        for lead_line in lead.tender_line :
            if lead_line.state == 'sent' : 
                lead_line.write({'state': 'lost'})
                    
        if all(lead_line.state == 'won' for lead_line in  lead.tender_line): 
            lead.write({'state': 'won'})
        elif all(lead_line.state == 'lost' for lead_line in  lead.tender_line): 
            lead.write({'state': 'lost'})
        else : 
            lead.write({'state': 'partial_won'})
                
        tender_line_wizard = self.env['tender.line.wizard'].search([])
        tender_line_wizard.unlink()
        return True
    
    def generate_lines_buttom(self):
        leads = self.env['crm.lead'].browse(self.env.context.get('active_ids'))
        for lead in leads :
            for line in lead.tender_line : 
                already_created = self.env['tender.line.wizard'].search([('tender_line_id','=',line.id)])
                _logger.error('already_created %s',already_created)
                
                if not already_created and line.display_type ==False: 
                    vals = {'name':line.name,
                            'product_id':line.product_id.id,
                            'product_uom_qty':line.product_uom_qty,
                            'won_product_uom_qty':line.product_uom_qty,
                            'product_uom':line.product_uom.id,
                            'tender_line_id':line.id,
                            }
                    self.env['tender.line.wizard'].create(vals)
                self.generated_lines=True
                
            self.lead_id=lead.id
            
        ir_model_data = self.env['ir.model.data']
        view_id = ir_model_data.get_object_reference('tenders', 'tender_partial_won_view_form')[1]
        
        self.tender_lines_ = lead.tender_line.ids
        return {   
            'name':_("Partial won"),
            'view_mode': 'form',
            'res_id': self.id,
            'view_id': view_id,
            'view_type': 'form',
            'res_model': 'tender.partial.won',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            }
