#!/usr/bin/env python3

# set server timezone in UTC before time module imported
__import__('os').environ['TZ'] = 'UTC'
import odoo

if __name__ == "__main__":
    print("---------------------------------------------------")
    print("Odoo Server is starting...")
    print("Access the system at: http://localhost:8069")
    print("---------------------------------------------------")
    odoo.cli.main()