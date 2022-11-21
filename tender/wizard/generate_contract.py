# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
import logging

_logger = logging.getLogger(__name__)


class GenerateContractWiz(models.TransientModel):
    _name = 'generate.contract.wiz'
    _description = 'Generate Contract Wizard'

    name = fields.Char('Contrat N°', required=True)
    begin_date = fields.Date(string='Date début', required=True)
    end_date = fields.Date(string='Date fin', required=True)
    signed_date = fields.Date(string='Date de signature')

    def action_generate_contract(self):
        leads = self.env['crm.lead'].browse(self.env.context.get('active_ids'))
        for lead in leads:
            pricelist_vals = {'name': str(self.name) + " " + str(lead.partner_id.name)}

            pricelist = self.env['product.pricelist'].create(pricelist_vals)
            lead.write({'pricelist_id': pricelist.id})
            lead.partner_id.write({'property_product_pricelist': pricelist})
            vals = {'name': self.name,
                    'partner_id': lead.partner_id.id,
                    'begin_date': self.begin_date,
                    'end_date': self.end_date,
                    'signed_date': self.signed_date,
                    'signed_date': self.signed_date,
                    'lead_id': lead.id,
                    'pricelist_id': pricelist.id,
                    'contract_type': lead.contract_type,
                    'contract_length': lead.contract_length,
                    }
            contract = self.env['tender.contract'].create(vals)

            designation_list_vals = {'name': str(self.name) + " " + str(lead.partner_id.name),
                                     'tender_id': contract.id}
            designation_list = self.env['designation.list'].create(designation_list_vals)
            equipment_vals = []
            for equipment in lead.equipment_id:
                equipment_vals.append({
                    'tender_id': contract.id,
                    'name': equipment.name,
                    'product_id': equipment.product_id.id,
                    'depreciation': equipment.depreciation,
                    'real_standard_price': equipment.real_standard_price,
                    'year_number': equipment.year_number,
                })
            self.env['equipment.template'].create(equipment_vals)
            for line in lead.tender_line:
                if line.won_uom_qty > 0.0:
                    line_vals = {'tender_id': contract.id,
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
                                 # 'product_updatable': line.product_updatable,
                                 'product_uom_qty': line.won_uom_qty,

                                 'product_min_qty': line.min_uom_qty,
                                 'product_max_qty': line.max_uom_qty,

                                 'product_uom': line.product_uom.id,
                                 'salesman_id': line.salesman_id.id,
                                 'company_id': line.company_id.id,
                                 'currency_id': line.currency_id.id,
                                 'order_partner_id': line.order_partner_id.id,
                                 'display_type': line.display_type,
                                 'state': 'draft',
                                 'order_partner_id': line.order_partner_id.id,
                                 'tax_id': [[6, False, line.tax_id.ids]],
                                 'invoicing': line.invoicing,
                                 'pattern_not_invoicing': line.pattern_not_invoicing,
                                 'is_reactif_dedie': line.is_reactif_dedie,
                                 'is_reactif_manuel': line.is_reactif_manuel,
                                 'standard_ids': [[6, False, line.standard_ids.ids]],
                                 'tender_line_id': line.id,
                                 }

                    pricelist_item_vals = {
                        'pricelist_id': pricelist.id,
                        'product_tmpl_id': line.product_id.product_tmpl_id.id,
                        # 'product_uom': line.product_uom.id,
                        'applied_on': '1_product',
                        'base': 'list_price',
                        'date_start': self.begin_date,
                        'date_end': self.end_date,
                        'compute_price': 'fixed',
                        'fixed_price': line.price_unit,
                        # 'note': lead.name
                    }

                    designation_item_vals = {
                        'designation_list_id': designation_list.id,
                        'product_tmpl_id': line.product_id.product_tmpl_id.id,
                        # 'product_uom': line.product_uom.id,
                        'designation': line.name,
                    }
                    self.env['designation.items'].create(designation_item_vals)
                    self.env['contract.lines'].create(line_vals)
                    self.env['product.pricelist.item'].create(pricelist_item_vals)
        return True
