# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    contract_id = fields.Many2one('tender.contract', string='Contrat', readonly=True)
    lead_tender_id = fields.Many2one('crm.lead', string='Appel d\'offre', readonly=True)
    designation_list_id = fields.Many2one('designation.list', string='Designation list',
                                          compute='_get_designation_list')

    def action_invoice_create(self, grouped=False, final=False):
        for order in self:
            invoices = super(SaleOrder, self).action_invoice_create(grouped, final)
            if order.contract_id:
                for invoice in invoices:
                    self.env['account.mve'].browse(invoice).write({'contract_id': order.contract_id.id})
            return invoices

    @api.depends('contract_id')
    def _get_designation_list(self):
        self.designation_list_id = self.env['designation.list'].search([('tender_id', '=', self.contract_id.id)])


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    contract_line_id = fields.Many2one('contract.lines', string='Contrat line')

    is_standard = fields.Boolean(string='Is Standart', default=False, store=True)
    is_reactif_dedie = fields.Boolean(string='Is Standart', default=False, store=True)
    is_reactif_manuel = fields.Boolean(string='Is Standart', default=False, store=True)

    qty_invoiced_validated = fields.Float(string="Qté facturée validée", compute="_get_invoice_validated_qty",
                                          readonly=True)

    # qty_invoiced_validated = fields.Float(string="Qté facturée validée",
    #                                       readonly=True)

    @api.onchange('product_id')
    def product_id_change(self):
        if self.product_id.product_tmpl_id:
            for designation_items in self.order_id.designation_list_id.designation_item_id:
                if self.product_id.product_tmpl_id.id == designation_items.product_tmpl_id.id:
                    self.update({'name': designation_items.designation})

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
    def _get_invoice_validated_qty(self):
        for line in self:
            qty_invoiced_validated = 0.0
            for invoice_line in line.invoice_lines:
                if invoice_line.move_id.state != 'cancel' and invoice_line.move_id.state != 'draft':
                    if invoice_line.move_id.type == 'out_invoice':
                        qty_invoiced_validated += invoice_line.uom_id._compute_quantity(invoice_line.quantity,
                                                                                        line.product_uom)
                    elif invoice_line.move_id.type == 'out_refund':
                        qty_invoiced_validated -= invoice_line.uom_id._compute_quantity(invoice_line.quantity,
                                                                                        line.product_uom)
            line.qty_invoiced_validated = qty_invoiced_validated

    @api.model
    def create(self, vals):
        _logger.warning('Begin create')
        if vals.get('order_id', False) and vals.get('product_id', False):
            order = self.env['sale.order'].browse(vals.get('order_id', False))
            if order.contract_id:
                for line in order.contract_id.contract_lines:
                    if line.product_id.id == vals.get('product_id', False):
                        vals['contract_line_id'] = line.id
                        break
        result = super(SaleOrderLine, self).create(vals)
        return result
