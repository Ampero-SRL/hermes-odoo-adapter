# -*- coding: utf-8 -*-
{
    'name': 'HERMES Manufacturing Theme',
    'version': '1.0',
    'category': 'Theme',
    'summary': 'Custom theme and configurations for HERMES demo',
    'description': """
        HERMES Manufacturing Demo Theme
        ================================
        * Custom company branding
        * Simplified UI for demo purposes
        * Pre-configured settings
    """,
    'author': 'HERMES Team',
    'depends': ['base', 'web', 'stock', 'mrp'],
    'data': [
        'data/company_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
