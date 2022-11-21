from odoo import exceptions, fields, models, api, _

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_standard = fields.Boolean(string='Is Standart', default=False, store=True)
    is_reactif_dedie = fields.Boolean(string='Is Standart', default=False, store=True)
    is_reactif_manuel = fields.Boolean(string='Is Standart', default=False, store=True)

    _type_selection_list = [('none', 'NONE'), ('equipment', 'Equipment')]
    product_type = fields.Selection(_type_selection_list, string='Type', default='none', store=True)