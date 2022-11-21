# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, Warning

import logging

_logger = logging.getLogger(__name__)


class LinkSelesOrderWiz(models.TransientModel):
    _name = 'link.sales.order.wiz'
    _description = 'Link Sales Order Wizard'

    order_ids = fields.Many2many(
        comodel_name='sale.order',
        string='Sales Orders',
        required=True,
    )

    def action_link_sales_order(self):
        contract_id = self.env['tender.contract']\
            .search([('id', 'in', self.env.context.get('active_ids'))])

        for order_ctr in self.order_ids:
            if order_ctr.partner_id.id != contract_id.partner_id.id:
                message = _(
                    "The partner (%s) is not the owner of this contract" % order_ctr.partner_id.name)
                raise UserError(message)
            if order_ctr.contract_id:
                message = _(
                    "The (%s) is already linked to contract named (%s) " % (order_ctr.name, order_ctr.contract_id.name))
                raise UserError(message)
            msg = ""
            for line in order_ctr.order_line:
                if line.qty_invoiced > 0:
                    msg += "- " + line.name + "\n"

            if msg != "":
                message = _(
                    "The (%s) has items invoiced:\n%s " % (order_ctr.name, msg))
                raise UserError(message)

        for order in self.order_ids:
            order.write({'contract_id': contract_id.id})
            for line in contract_id.contract_lines:
                for order_line in order.order_line:
                    if line.product_id.id == order_line.product_id.id:
                        order_line.write({'contract_line_id': line.id})
