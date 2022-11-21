from odoo import exceptions, fields, models, api, _

class MachineTemplate(models.Model):
    _name = 'equipment.template'

    tender_id = fields.Many2one('crm.lead')
    product_id = fields.Many2one('product.template', domain="[('product_type', 'in', ['equipment'])]", required=True,
                                 related=False, store=True, readonly=False)
    name = fields.Text(compute='_get_name',
                       required=True, related=False, store=False, readonly=False)
    depreciation = fields.Float(compute='_get_depreciation', readonly=True, required=True)
    standard_price = fields.Float(compute='_get_standard_price', readonly=True)
    real_standard_price = fields.Float(required=True)
    year_number = fields.Selection([
        ('1', 1),
        ('2', 2),
        ('3', 3),
        ('4', 4),
        ('5', 5),
        ('6', 6),
        ('7', 7),
    ], copy=False, index=True, required=True, default='3')

    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], default=False, help="Technical field for UX purpose.")

    @api.depends('product_id')
    def _get_standard_price(self):
        for line in self:
            line.standard_price = line.product_id.standard_price

    @api.depends('product_id')
    def _get_name(self):
        for line in self:
            line.name = line.product_id.name

    @api.depends('year_number', 'product_id', 'real_standard_price')
    def _get_depreciation(self):
        for line in self:
            line.depreciation = line.real_standard_price / int(line.year_number)
