import sys

project_home = '/var/www/CarteiraAppFinanceApi/'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

from api import app as application