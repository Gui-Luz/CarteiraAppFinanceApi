from flask import Flask
from flask_restful import Resource, reqparse, Api
import configparser
import os
from integration_engine import main

config_file = configparser.ConfigParser()
config_file.read(os.path.dirname(__file__) + '/config.ini')

#ENV
DEBUG = bool(config_file['ENV']['debug'])
PORT = int(config_file['ENV']['port'])
TOKEN = int(config_file['API INTEGRATION']['finance'])

app = Flask(__name__)
app.config['SECRET-KEY'] = config_file['APP']['key']
api_server = Api(app)

parser = reqparse.RequestParser()
parser.add_argument('token', type=int, default=None)


class GetStocks(Resource):

    def __init__(self):
        args = parser.parse_args()
        self.token = args.get('token')

    def get(self):
        if self.token == TOKEN:
            main()
            return {'Code': 200, 'Alert': 'Success',}
        else:
            return {'Code': 400, 'Alert': 'Fail', 'Message': 'invalid token'}


api_server.add_resource(GetStocks, config_file['ENDPOINTS']['get_stocks'])

if __name__ == '__main__':
    app.run(debug=DEBUG, port=PORT)