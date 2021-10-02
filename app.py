from datetime import datetime
from flask_restful.utils import http_status_message
import redis
import json
import hashlib
from flask import request
from flask_restful import Resource,Api
from flask import Flask
from typing import Dict
from flask import Flask
import random
import string
import requests

from werkzeug.http import HTTP_STATUS_CODES

gestor_seguridad_url = "http://miso-gestorseguridad.herokuapp.com/gestorSeguridad"

redisInstance = redis.Redis(
    host='ec2-50-19-196-205.compute-1.amazonaws.com', 
    port=17830,
    password="p8246bd54e4335f5d4001090409c247e242ebbc0d28a3a9a8f92400e7b9e1d178",
    ssl=True,
    ssl_cert_reqs=None,
    charset="utf-8",
    decode_responses=True
    )

#tabla historias clinicas
tbl_historia_clinica = redisInstance.hgetall("tbl_historia_clinica")

def searchByField(collection, searchForCollection, field1, valueToSearch1,field2=None, valueToSearch2=None):
    output=[]
    for value in collection:
        item=json.loads(collection[value])
        if item[field1]==valueToSearch1:
            if field2 is None:
                if searchForCollection==True:
                    output.append(item)
                else:
                    return item
            else:
                if item[field2]==valueToSearch2:
                    if searchForCollection==True:
                        output.append(item)
                    else:
                        return item
            
    if searchForCollection==True:
        return output
    else:
        return None

PREFIX = 'Bearer'

def get_token(header):
    bearer, _, token = header.partition(' ')
    if bearer != PREFIX:
        raise ValueError('Invalid token')

    return token

def validarToken():
    token = get_token(request.headers.get('Authorization'))
    response = requests.post(gestor_seguridad_url+'/authorizeToken', json={"token": token})
    if response.status_code == 200:
        data = response.json()
        return data["id"]
    else: 
        return None

def validarAccion(accion_id, usuario_id):
    response = requests.post(gestor_seguridad_url+'/authorizeAction', json={"usuarioId": usuario_id, "accionId": accion_id})
    if response.status_code == 200:
        data = response.json()
        return bool(data["autorization"])
    else: 
        return False

def firmaHash(contenido, usuarioId):
    response = requests.post(gestor_seguridad_url+'/hashContent', json={"usuarioId": usuarioId, "contenido": contenido})
    data = response.json()
    return bool(data["hash"])

class GestorPaciente(Resource):
    def post(self, id_paciente):       
        data={
            "id" : id_paciente,
            "nombre" : request.json["nombre"],
            "documento" : request.json["documento"]
        }
        return data


    def get(self, id_paciente):
        data={
            "id" : id_paciente,
            "nombre" : random.choice(string.ascii_letters),
            "documento" : random.randint(1, 999999999)
        }
        return data
 

class HealthCheck(Resource):    

    def get(self):
        data={
            "echo" : "ok"
        }
        return data

class HistoriaClinica(Resource):
    def get(self, id_paciente):
        usuario_id = validarToken()
        print(str(usuario_id))
        if usuario_id is None:
            return ('Autenticacion no válida', 403)
        autoriza = validarAccion(1000, usuario_id)
        if autoriza == False:
            return ('Usuario no autorizado para realizar esta acción', 403)
        return {"historia" : searchByField(tbl_historia_clinica, True, "usuarioId", id_paciente)}

class ModificarHistoriaClinica(Resource):

    def put(self, id_paciente, id_entrada):
        usuario_id = validarToken()
        if usuario_id is None:
            return ('Autenticacion no válida', 403)
        autoriza = validarAccion(1001, usuario_id)
        if autoriza == False: 
            return ('Usuario no autorizado para realizar esta acción', 403)
        entrada = searchByField(tbl_historia_clinica, False, "usuarioId", id_paciente, "id", id_entrada)
        notaHistoria = request.json["notaHistoria"]
        if entrada is None:
            return ('Entrada no encontrada', 404)
        else:
            if (entrada['creadoPorUsuarioId'] == usuario_id):
                entrada['notaHistoria'] = entrada['notaHistoria']+ "-"+ notaHistoria
                entrada['firmaHash'] = firmaHash(entrada['notaHistoria'], usuario_id)
                redisInstance.hset("tbl_historia_clinica",entrada["id"],json.dumps(entrada))
                entrada = searchByField(tbl_historia_clinica, False, "usuarioId", id_paciente, "id", id_entrada)
                return (entrada)
            else:
                return ('Usuario no autorizado para modificar esta entrada')
        

app = Flask(__name__) 
app_context = app.app_context()
app_context.push()


api = Api(app)
api.add_resource(GestorPaciente, "/paciente/<int:id_paciente>")
api.add_resource(HealthCheck, "/paciente/healthCheck")
api.add_resource(HistoriaClinica, "/paciente/<int:id_paciente>/historia")
api.add_resource(ModificarHistoriaClinica, "/paciente/<int:id_paciente>/historia/<int:id_entrada>")


if __name__ == '__main__':
    app.run()