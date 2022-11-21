# -*- coding: utf-8 -*-

{
    'name': 'Tenders management system',
    'version': '1.0',
    'category': 'CRM',
    'author': "Nadir MESSAOUDENE",

    'description': """
Gestion des appels d\'offres clients
==================
    """,

    'depends': ['sale', 'crm', 'sale_crm', 'hr'],
    'data': [
        'data/crm_lead_data.xml',
        'security/tenders_security.xml',
        'security/ir.model.access.csv',
        'wizard/tender_lost_views.xml',
        'wizard/tender_partial_won_views.xml',
        'wizard/generate_contract_views.xml',
        'wizard/link_sales_order_views.xml',
        'views/sale_order_views.xml',
        'views/menu_views.xml',
        'views/lost_reason_views.xml',
        'views/tender_contract_view.xml',
        'views/tender_tender_view.xml',
        'views/private_mad_contract_view.xml',
        'views/designations_view.xml',
        'views/product_template_view.xml',

    ],
    'auto_install': True,
    'installable': True,
}
