from odoo import exceptions, fields, models, api, _


class DesignationTemplate(models.Model):
    _name = 'designation.list'
    _description = "Article description"

    name = fields.Text()
    tender_id = fields.Many2one('tender.contract')
    designation_item_id = fields.One2many('designation.items', 'designation_list_id', string='Designation')


class DesignationTemplateItem(models.Model):
    _name = 'designation.items'
    _description = "Article description items"

    product_tmpl_id = fields.Many2one('product.template', string='Product')
    designation_list_id = fields.Many2one('designation.list', string='Designation list')
    designation = fields.Text(string='Designation')
