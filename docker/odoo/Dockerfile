FROM odoo:16

# Copy configuration and custom modules
COPY odoo.conf /etc/odoo/odoo.conf
COPY custom_addons /mnt/extra-addons
COPY --chmod=755 entrypoint.sh /entrypoint-hermes.sh

ENV ODOO_RC=/etc/odoo/odoo.conf \
    HERMES_INIT_MODULE=hermes_electrical_seed

ENTRYPOINT ["/entrypoint-hermes.sh"]
CMD ["odoo"]
