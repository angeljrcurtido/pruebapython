from flask import Flask, request, jsonify
from pymongo import MongoClient
from flask_cors import CORS  # Importar CORS
import base64
from bson.objectid import ObjectId
import tensorflow as tf
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input, decode_predictions
from tensorflow.keras.preprocessing import image
import numpy as np
import io
from googletrans import Translator

app = Flask(__name__)
CORS(app)  # Habilitar CORS en la aplicación Flask

# Conexión a MongoDB Atlas
client = MongoClient("mongodb+srv://angeljrcurtido:curtidobenitez082@cluster0.j3h8cfj.mongodb.net/Sistema83?retryWrites=true&w=majority&appName=Cluster0")
db = client['nombre_base_datos']
productos_collection = db['productos']

# Cargar el modelo preentrenado MobileNetV2
model = MobileNetV2(weights='imagenet')

# Inicializar el traductor de Google
translator = Translator()
# Función para predecir la clase de la imagen y traducir
def reconocer_objeto(img):
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)
    predicciones = model.predict(img_array)
    resultados = decode_predictions(predicciones, top=3)[0]

    objetos_reconocidos = []
    for _, clase, puntuacion in resultados:
        # Traducir la clase al español
        clase_traducida = translator.translate(clase, src='en', dest='es').text
        objetos_reconocidos.append({
            "clase": clase_traducida,
            "probabilidad": f"{puntuacion * 100:.2f}%"
        })

    return objetos_reconocidos

# Endpoint para reconocimiento de imágenes
@app.route('/reconocer-imagen', methods=['POST'])
def reconocer_imagen():
    imagen = request.files.get('imagen')
    if not imagen:
        return jsonify({'error': 'No se ha proporcionado una imagen.'}), 400

    try:
        img = image.load_img(io.BytesIO(imagen.read()), target_size=(224, 224))
        objetos_reconocidos = reconocer_objeto(img)
        return jsonify({'objetos_reconocidos': objetos_reconocidos}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Esquema de validación
def validar_producto(data):
    if 'nombre' not in data or not isinstance(data['nombre'], str):
        return False, "El campo 'nombre' es obligatorio y debe ser un string."
    if 'unidadMedida' not in data or not isinstance(data['unidadMedida'], str):
        return False, "El campo 'unidadMedida' es obligatorio y debe ser un string."
    if 'precioVenta' not in data or not isinstance(data['precioVenta'], (int, float)):
        return False, "El campo 'precioVenta' es obligatorio y debe ser un número."
    if 'precioCompra' not in data or not isinstance(data['precioCompra'], (int, float)):
        return False, "El campo 'precioCompra' es obligatorio y debe ser un número."
    if 'CantidadActual' not in data or not isinstance(data['CantidadActual'], int):
        return False, "El campo 'CantidadActual' es obligatorio y debe ser un entero."
    if 'CantidadMinima' not in data or not isinstance(data['CantidadMinima'], int):
        return False, "El campo 'CantidadMinima' es obligatorio y debe ser un entero."
    if 'Proveedor' not in data or not isinstance(data['Proveedor'], str):
        return False, "El campo 'Proveedor' es obligatorio y debe ser un string."
    if 'Categoria' not in data or not isinstance(data['Categoria'], str):
        return False, "El campo 'Categoria' es obligatorio y debe ser un string."
    return True, ""

    # Esquema de Compras
compras_collection = db['compras']

def validar_compra(data):
    # Validar campos del proveedor
    if 'nombreProveedor' not in data or not isinstance(data['nombreProveedor'], str):
        return False, "El campo 'nombreProveedor' es obligatorio y debe ser un string."
    if 'rucProveedor' not in data or not isinstance(data['rucProveedor'], str):
        return False, "El campo 'rucProveedor' es obligatorio y debe ser un string."
    if 'telefonoProveedor' not in data or not isinstance(data['telefonoProveedor'], str):
        return False, "El campo 'telefonoProveedor' es obligatorio y debe ser un string."

    # Validar campos de productos
    if 'productos' not in data or not isinstance(data['productos'], list):
        return False, "El campo 'productos' es obligatorio y debe ser una lista de productos."
    for producto in data['productos']:
        if 'nombreProducto' not in producto or not isinstance(producto['nombreProducto'], str):
            return False, "Cada producto debe tener un 'nombreProducto' válido."
        if 'precioCompra' not in producto or not isinstance(producto['precioCompra'], (int, float)):
            return False, "Cada producto debe tener un 'precioCompra' válido."
        if 'cantidadComprada' not in producto or not isinstance(producto['cantidadComprada'], int):
            return False, "Cada producto debe tener una 'cantidadComprada' válida."
    
    # Validar la fecha de compra
    if 'fechaCompra' not in data or not isinstance(data['fechaCompra'], str):
        return False, "El campo 'fechaCompra' es obligatorio y debe ser un string de fecha."
    
    return True, ""


# Ruta para crear una compra
@app.route('/compras', methods=['POST'])
def crear_compra():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()

    # Validar los campos de la compra
    valido, mensaje = validar_compra(data)
    if not valido:
        return jsonify({'error': mensaje}), 400

    # Crear la estructura de la compra
    nueva_compra = {
        'nombreProveedor': data['nombreProveedor'],
        'rucProveedor': data['rucProveedor'],
        'telefonoProveedor': data['telefonoProveedor'],
        'productos': data['productos'],
        'fechaCompra': data['fechaCompra'],
        'estado': 'activo'  # Estado por defecto
    }

    # Iterar sobre los productos comprados y actualizar sus datos en la base de datos
    for producto in data['productos']:
        # Verificar si el ID del producto existe
        producto_id = producto.get('idProducto')
        if not producto_id:
            return jsonify({'error': 'Cada producto debe tener un ID de producto válido.'}), 400
        
        # Buscar el producto en la base de datos
        producto_existente = productos_collection.find_one({'_id': ObjectId(producto_id)})

        if producto_existente:
            # Actualizar el precio de compra y la cantidad actual
            nuevo_precio_compra = producto['precioCompra']
            nueva_cantidad = producto_existente['CantidadActual'] + producto['cantidadComprada']

            # Actualizar el producto en la base de datos
            productos_collection.update_one(
                {'_id': ObjectId(producto_id)},
                {'$set': {'precioCompra': nuevo_precio_compra, 'CantidadActual': nueva_cantidad}}
            )
        else:
            return jsonify({'error': f'El producto con ID {producto_id} no existe.'}), 404

    # Insertar la compra en la base de datos
    resultado = compras_collection.insert_one(nueva_compra)
    nueva_compra['_id'] = str(resultado.inserted_id)
    return jsonify(nueva_compra), 201


# Ruta para anular una compra
@app.route('/compras/anular/<compra_id>', methods=['PUT'])
def anular_compra(compra_id):
    # Buscar la compra por su ID
    compra = compras_collection.find_one({'_id': ObjectId(compra_id)})

    if not compra:
        return jsonify({'error': 'La compra no existe.'}), 404

    # Verificar si la compra ya está anulada
    if compra['estado'] == 'anulado':
        return jsonify({'error': 'La compra ya está anulada.'}), 400

    # Cambiar el estado de la compra a 'anulado'
    compras_collection.update_one(
        {'_id': ObjectId(compra_id)},
        {'$set': {'estado': 'anulado'}}
    )

    # Revertir la cantidad de los productos comprados
    for producto in compra['productos']:
        producto_id = producto['idProducto']
        cantidad_comprada = producto['cantidadComprada']

        # Buscar el producto en la base de datos
        producto_existente = productos_collection.find_one({'_id': ObjectId(producto_id)})

        if producto_existente:
            # Restar la cantidad comprada de la cantidad actual
            nueva_cantidad = producto_existente['CantidadActual'] - cantidad_comprada

            # Actualizar el producto en la base de datos
            productos_collection.update_one(
                {'_id': ObjectId(producto_id)},
                {'$set': {'CantidadActual': nueva_cantidad}}
            )

    return jsonify({'message': 'La compra ha sido anulada y las cantidades revertidas.'}), 200

# Ruta para obtener todas las compras
@app.route('/compras', methods=['GET'])
def obtener_compras():
    compras = list(compras_collection.find())
    for compra in compras:
        compra['_id'] = str(compra['_id'])
    return jsonify(compras), 200


#=================================INICO PRODUCTOS=============================
# Ruta para crear un producto sin procesar la imagen
@app.route('/productos', methods=['POST'])
def crear_producto():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()

    # Convertir los campos numéricos manualmente antes de la validación
    try:
        data['precioVenta'] = float(data['precioVenta'])
        data['precioCompra'] = float(data['precioCompra'])
        data['CantidadActual'] = int(data['CantidadActual'])
        data['CantidadMinima'] = int(data['CantidadMinima'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Algunos campos numéricos no tienen el formato correcto.'}), 400

    # Validar los campos del producto
    valido, mensaje = validar_producto(data)
    if not valido:
        return jsonify({'error': mensaje}), 400

    # Verificar que el campo Iva esté presente y sea un string
    iva = data.get('Iva')
    if not iva or not isinstance(iva, str):
        return jsonify({'error': "El campo 'Iva' es obligatorio y debe ser un string."}), 400

    # Crear el nuevo producto con estado 'activo' por defecto
    nuevo_producto = {
        'nombre': data['nombre'],
        'unidadMedida': data['unidadMedida'],
        'precioVenta': data['precioVenta'],
        'precioCompra': data['precioCompra'],
        'CantidadActual': data['CantidadActual'],
        'CantidadMinima': data['CantidadMinima'],
        'Proveedor': data['Proveedor'],
        'Categoria': data['Categoria'],
        'Iva': iva,
        'descripcion': data.get('descripcion', ''),
        'estado': 'activo'  # Estado por defecto al crear
    }

    # Insertar el producto en la base de datos
    resultado = productos_collection.insert_one(nuevo_producto)
    nuevo_producto['_id'] = str(resultado.inserted_id)
    return jsonify(nuevo_producto), 201


# Ruta para anular un producto
@app.route('/productos/anular/<producto_id>', methods=['PUT'])
def anular_producto(producto_id):
    # Buscar el producto por su ID
    producto = productos_collection.find_one({'_id': ObjectId(producto_id)})

    if not producto:
        return jsonify({'error': 'El producto no existe.'}), 404

    # Verificar si el producto ya está anulado
    if producto['estado'] == 'anulado':
        return jsonify({'error': 'El producto ya está anulado.'}), 400

    # Cambiar el estado del producto a 'anulado'
    productos_collection.update_one(
        {'_id': ObjectId(producto_id)},
        {'$set': {'estado': 'anulado'}}
    )

    return jsonify({'message': 'El producto ha sido anulado exitosamente.'}), 200


# Ruta para reactivar un producto
@app.route('/productos/reactivar/<producto_id>', methods=['PUT'])
def reactivar_producto(producto_id):
    # Buscar el producto por su ID
    producto = productos_collection.find_one({'_id': ObjectId(producto_id)})

    if not producto:
        return jsonify({'error': 'El producto no existe.'}), 404

    # Verificar si el producto ya está activo
    if producto['estado'] == 'activo':
        return jsonify({'error': 'El producto ya está activo.'}), 400

    # Cambiar el estado del producto a 'activo'
    productos_collection.update_one(
        {'_id': ObjectId(producto_id)},
        {'$set': {'estado': 'activo'}}
    )

    return jsonify({'message': 'El producto ha sido reactivado exitosamente.'}), 200


# Ruta para obtener todos los productos
@app.route('/productos', methods=['GET'])
def obtener_productos():
    try:
        # Obtener todos los productos de la colección
        productos = list(productos_collection.find())

        # Convertir los ObjectId a string para poder enviar en la respuesta JSON
        for producto in productos:
            producto['_id'] = str(producto['_id'])

        return jsonify(productos), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Ruta para obtener todos los productos con estado 'activo'
@app.route('/productos/activos', methods=['GET'])
def obtener_productos_activos():
    try:
        # Obtener todos los productos con estado 'activo'
        productos = list(productos_collection.find({'estado': 'activo'}))
        
        # Convertir los ObjectId a string para poder enviar en la respuesta JSON
        for producto in productos:
            producto['_id'] = str(producto['_id'])
        
        return jsonify(productos), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Ruta para obtener todos los productos con estado 'anulado'
@app.route('/productos/anulados', methods=['GET'])
def obtener_productos_anulados():
    try:
        # Obtener todos los productos con estado 'anulado'
        productos = list(productos_collection.find({'estado': 'anulado'}))
        
        # Convertir los ObjectId a string para poder enviar en la respuesta JSON
        for producto in productos:
            producto['_id'] = str(producto['_id'])
        
        return jsonify(productos), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ====================================INICIO VENTAS=============================

# Esquema de Ventas y Contadores
ventas_collection = db['ventas']
counters_collection = db['counters']

# Función para obtener y actualizar el contador de un campo específico
def get_next_sequence(name):
    counter = counters_collection.find_one_and_update(
        {'_id': name},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True
    )
    return counter['seq']

def validar_venta(data):
    # Validar los campos de la venta
    required_fields = [
        'nombreEmpresa', 'rucEmpresa', 'direccionEmpresa', 'timbradoEmpresa', 
        'nombreCliente', 'rucCliente', 'fechaVenta'
    ]

    # Validar los campos que deben ser strings
    for field in required_fields:
        if field not in data or not isinstance(data[field], str):
            return False, f"El campo '{field}' es obligatorio y debe ser un string."
    
    # Validar que 'productos' sea una lista
    if 'productos' not in data or not isinstance(data['productos'], list):
        return False, "El campo 'productos' debe ser una lista de productos."

    # Validar cada producto dentro de la lista 'productos'
    for producto in data['productos']:
        if 'idProducto' not in producto or not isinstance(producto['idProducto'], str):
            return False, "Cada producto debe tener un 'idProducto' válido."
        if 'cantidadVendida' not in producto or not isinstance(producto['cantidadVendida'], int):
            return False, "Cada producto debe tener una 'cantidadVendida' válida."
    
    return True, ""

# Ruta para crear una venta
@app.route('/ventas', methods=['POST'])
def crear_venta():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()

    # Validar los campos de la venta
    valido, mensaje = validar_venta(data)
    if not valido:
        return jsonify({'error': mensaje}), 400

    # Obtener los valores auto-incrementales para facturaNumero y numeroInterno
    factura_numero = get_next_sequence('facturaNumero')
    numero_interno = get_next_sequence('numeroInterno')

    # Crear la estructura de la venta
    nueva_venta = {
        'nombreEmpresa': data['nombreEmpresa'],
        'rucEmpresa': data['rucEmpresa'],
        'direccionEmpresa': data['direccionEmpresa'],
        'timbradoEmpresa': data['timbradoEmpresa'],
        'facturaNumero': f"001-001-{factura_numero:07d}",  # Formato ajustado
        'numeroInterno': numero_interno,
        'nombreCliente': data['nombreCliente'],
        'rucCliente': data['rucCliente'],
        'fechaVenta': data['fechaVenta'],
        'productos': data['productos'],
        'estado': 'activo'  # Estado por defecto
    }

    # Iterar sobre los productos vendidos y actualizar sus datos en la base de datos
    for producto in data['productos']:
        # Verificar si el ID del producto existe
        producto_id = producto.get('idProducto')
        cantidad_vendida = producto.get('cantidadVendida')

        # Buscar el producto en la base de datos
        producto_existente = productos_collection.find_one({'_id': ObjectId(producto_id)})

        if producto_existente:
            cantidad_actual = producto_existente['CantidadActual']

            # Verificar si hay suficiente stock
            if cantidad_vendida > cantidad_actual:
                return jsonify({'error': f'No hay suficiente stock para el producto con ID {producto_id}.'}), 400
            
            # Restar la cantidad vendida de la cantidad actual
            nueva_cantidad = cantidad_actual - cantidad_vendida

            # Actualizar el producto en la base de datos
            productos_collection.update_one(
                {'_id': ObjectId(producto_id)},
                {'$set': {'CantidadActual': nueva_cantidad}}
            )
        else:
            return jsonify({'error': f'El producto con ID {producto_id} no existe.'}), 404

    # Insertar la venta en la base de datos
    resultado = ventas_collection.insert_one(nueva_venta)
    nueva_venta['_id'] = str(resultado.inserted_id)
    return jsonify(nueva_venta), 201

# Ruta para anular una venta
@app.route('/ventas/anular/<venta_id>', methods=['PUT'])
def anular_venta(venta_id):
    # Buscar la venta por su ID
    venta = ventas_collection.find_one({'_id': ObjectId(venta_id)})

    if not venta:
        return jsonify({'error': 'La venta no existe.'}), 404

    # Verificar si la venta ya está anulada
    if venta['estado'] == 'anulado':
        return jsonify({'error': 'La venta ya está anulada.'}), 400

    # Cambiar el estado de la venta a 'anulado'
    ventas_collection.update_one(
        {'_id': ObjectId(venta_id)},
        {'$set': {'estado': 'anulado'}}
    )

    # Revertir la cantidad de los productos vendidos
    for producto in venta['productos']:
        producto_id = producto['idProducto']
        cantidad_vendida = producto['cantidadVendida']

        # Buscar el producto en la base de datos
        producto_existente = productos_collection.find_one({'_id': ObjectId(producto_id)})

        if producto_existente:
            # Sumar la cantidad vendida de vuelta a la cantidad actual
            nueva_cantidad = producto_existente['CantidadActual'] + cantidad_vendida

            # Actualizar el producto en la base de datos
            productos_collection.update_one(
                {'_id': ObjectId(producto_id)},
                {'$set': {'CantidadActual': nueva_cantidad}}
            )

    return jsonify({'message': 'La venta ha sido anulada y las cantidades revertidas.'}), 200

# ====================================INICIO DE CLIENTE ====================================
# Conexión a la colección de clientes
clientes_collection = db['clientes']

# Función para validar los datos del cliente
def validar_cliente(data):
    required_fields = ['nombreCliente', 'rucCliente', 'telefonoCliente']

    for field in required_fields:
        if field not in data or not isinstance(data[field], str):
            return False, f"El campo '{field}' es obligatorio y debe ser un string."
    return True, ""
# Ruta para crear un cliente
@app.route('/clientes', methods=['POST'])
def crear_cliente():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()

    # Validar los campos del cliente
    valido, mensaje = validar_cliente(data)
    if not valido:
        return jsonify({'error': mensaje}), 400

    # Crear el nuevo cliente
    nuevo_cliente = {
        'nombreCliente': data['nombreCliente'],
        'rucCliente': data['rucCliente'],
        'telefonoCliente': data['telefonoCliente']
    }

    # Insertar el cliente en la base de datos
    resultado = clientes_collection.insert_one(nuevo_cliente)
    nuevo_cliente['_id'] = str(resultado.inserted_id)
    return jsonify(nuevo_cliente), 201
# Ruta para obtener todos los clientes
@app.route('/clientes', methods=['GET'])
def obtener_clientes():
    try:
        # Obtener todos los clientes de la colección
        clientes = list(clientes_collection.find())

        # Convertir los ObjectId a string para enviar en la respuesta JSON
        for cliente in clientes:
            cliente['_id'] = str(cliente['_id'])

        return jsonify(clientes), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ======================INICIO EMPRESAS ======================
# Conexión a la colección de empresas
empresas_collection = db['empresas']

# Función para validar los datos de la empresa
def validar_empresa(data):
    required_fields = ['nombreEmpresa', 'rucEmpresa', 'direccionEmpresa', 'timbradoEmpresa']

    for field in required_fields:
        if field not in data or not isinstance(data[field], str):
            return False, f"El campo '{field}' es obligatorio y debe ser un string."
    return True, ""
# Ruta para crear una empresa
@app.route('/empresas', methods=['POST'])
def crear_empresa():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()

    # Validar los campos de la empresa
    valido, mensaje = validar_empresa(data)
    if not valido:
        return jsonify({'error': mensaje}), 400

    # Crear la nueva empresa
    nueva_empresa = {
        'nombreEmpresa': data['nombreEmpresa'],
        'rucEmpresa': data['rucEmpresa'],
        'direccionEmpresa': data['direccionEmpresa'],
        'timbradoEmpresa': data['timbradoEmpresa']
    }

    # Insertar la empresa en la base de datos
    resultado = empresas_collection.insert_one(nueva_empresa)
    nueva_empresa['_id'] = str(resultado.inserted_id)
    return jsonify(nueva_empresa), 201
# Ruta para obtener todas las empresas
@app.route('/empresas', methods=['GET'])
def obtener_empresas():
    try:
        # Obtener todas las empresas de la colección
        empresas = list(empresas_collection.find())

        # Convertir los ObjectId a string para enviar en la respuesta JSON
        for empresa in empresas:
            empresa['_id'] = str(empresa['_id'])

        return jsonify(empresas), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ================= INICIO PROVEEDOR =======================

proveedores_collection = db['proveedores']

# Función para validar los datos del proveedor
def validar_proveedor(data):
    required_fields = ['nombreProveedor', 'rucProveedor', 'direccionProveedor', 'telefonoProveedor']
    for field in required_fields:
        if field not in data or not isinstance(data[field], str):
            return False, f"El campo '{field}' es obligatorio y debe ser un string."
    return True, ""

# Ruta para crear un proveedor
@app.route('/proveedores', methods=['POST'])
def crear_proveedor():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()

    # Validar los campos del proveedor
    valido, mensaje = validar_proveedor(data)
    if not valido:
        return jsonify({'error': mensaje}), 400

    # Crear el nuevo proveedor
    nuevo_proveedor = {
        'nombreProveedor': data['nombreProveedor'],
        'rucProveedor': data['rucProveedor'],
        'direccionProveedor': data['direccionProveedor'],
        'telefonoProveedor': data['telefonoProveedor'],
        'estado': 'activo'  # Estado por defecto
    }

    # Insertar el proveedor en la base de datos
    resultado = proveedores_collection.insert_one(nuevo_proveedor)
    nuevo_proveedor['_id'] = str(resultado.inserted_id)
    return jsonify(nuevo_proveedor), 201

# Ruta para obtener todos los proveedores
@app.route('/proveedores', methods=['GET'])
def obtener_proveedores():
    try:
        # Obtener todos los proveedores de la colección
        proveedores = list(proveedores_collection.find())

        # Convertir los ObjectId a string para enviar en la respuesta JSON
        for proveedor in proveedores:
            proveedor['_id'] = str(proveedor['_id'])

        return jsonify(proveedores), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# Ruta para obtener solo los proveedores con estado activo
@app.route('/proveedores/activos', methods=['GET'])
def obtener_proveedores_activos():
    try:
        # Obtener solo los proveedores que tienen estado 'activo'
        proveedores_activos = list(proveedores_collection.find({'estado': 'activo'}))

        # Convertir los ObjectId a string para enviar en la respuesta JSON
        for proveedor in proveedores_activos:
            proveedor['_id'] = str(proveedor['_id'])

        # Devolver un array vacío si no hay proveedores activos
        return jsonify(proveedores_activos if proveedores_activos else []), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

# Ruta para obtener solo los proveedores con estado anulado
@app.route('/proveedores/anulados', methods=['GET'])
def obtener_proveedores_anulados():
    try:
        # Obtener solo los proveedores que tienen estado 'anulado'
        proveedores_anulados = list(proveedores_collection.find({'estado': 'anulado'}))

        # Convertir los ObjectId a string para enviar en la respuesta JSON
        for proveedor in proveedores_anulados:
            proveedor['_id'] = str(proveedor['_id'])

        # Devolver un array vacío si no hay proveedores anulados
        return jsonify(proveedores_anulados if proveedores_anulados else []), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

# Ruta para anular un proveedor
@app.route('/proveedores/anular/<proveedor_id>', methods=['PUT'])
def anular_proveedor(proveedor_id):
    # Buscar el proveedor por su ID
    proveedor = proveedores_collection.find_one({'_id': ObjectId(proveedor_id)})

    if not proveedor:
        return jsonify({'error': 'El proveedor no existe.'}), 404

    # Verificar si el proveedor ya está anulado
    if proveedor['estado'] == 'anulado':
        return jsonify({'error': 'El proveedor ya está anulado.'}), 400

    # Cambiar el estado del proveedor a 'anulado'
    proveedores_collection.update_one(
        {'_id': ObjectId(proveedor_id)},
        {'$set': {'estado': 'anulado'}}
    )

    return jsonify({'message': 'El proveedor ha sido anulado exitosamente.'}), 200

# =================== INICIO CATEGORIAS =====================
# Conexión a la colección de categorías
# Conexión a la colección de categorías
categorias_collection = db['categorias']

# Modificación en la validación y creación de categoría
def validar_categoria(data):
    if 'nombreCategoria' not in data or not isinstance(data['nombreCategoria'], str):
        return False, "El campo 'nombreCategoria' es obligatorio y debe ser un string."
    return True, ""

# Ruta para crear una categoría con estado 'activo'
@app.route('/categorias', methods=['POST'])
def crear_categoria():
    if request.is_json:
        data = request.json
    else:
        data = request.form.to_dict()

    # Validar los campos de la categoría
    valido, mensaje = validar_categoria(data)
    if not valido:
        return jsonify({'error': mensaje}), 400

    # Verificar si la categoría ya existe
    categoria_existente = categorias_collection.find_one({'nombreCategoria': data['nombreCategoria']})
    if categoria_existente:
        return jsonify({'error': 'La categoría con este nombre ya existe.'}), 400

    # Crear la nueva categoría con estado 'activo'
    nueva_categoria = {
        'nombreCategoria': data['nombreCategoria'],
        'estado': 'activo'  # Estado por defecto al crear
    }

    # Insertar la categoría en la base de datos
    resultado = categorias_collection.insert_one(nueva_categoria)
    nueva_categoria['_id'] = str(resultado.inserted_id)
    return jsonify(nueva_categoria), 201

# Ruta para obtener todas las categorías
@app.route('/categorias', methods=['GET'])
def obtener_categorias():
    try:
        # Obtener todas las categorías de la colección
        categorias = list(categorias_collection.find())
        
        # Convertir los ObjectId a string para poder enviar en la respuesta JSON
        for categoria in categorias:
            categoria['_id'] = str(categoria['_id'])
        
        return jsonify(categorias), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para anular una categoría
@app.route('/categorias/anular/<categoria_id>', methods=['PUT'])
def anular_categoria(categoria_id):
    # Buscar la categoría por su ID
    categoria = categorias_collection.find_one({'_id': ObjectId(categoria_id)})

    if not categoria:
        return jsonify({'error': 'La categoría no existe.'}), 404

    # Verificar si la categoría ya está anulada
    if categoria['estado'] == 'anulado':
        return jsonify({'error': 'La categoría ya está anulada.'}), 400

    # Cambiar el estado de la categoría a 'anulado'
    categorias_collection.update_one(
        {'_id': ObjectId(categoria_id)},
        {'$set': {'estado': 'anulado'}}
    )

    return jsonify({'message': 'La categoría ha sido anulada exitosamente.'}), 200
# Ruta para obtener todas las categorías activas
@app.route('/categorias/activas', methods=['GET'])
def obtener_categorias_activas():
    try:
        # Obtener solo las categorías con estado 'activo'
        categorias_activas = list(categorias_collection.find({'estado': 'activo'}))
        
        # Convertir los ObjectId a string para poder enviar en la respuesta JSON
        for categoria in categorias_activas:
            categoria['_id'] = str(categoria['_id'])
        
        return jsonify(categorias_activas), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para obtener todas las categorías anuladas
@app.route('/categorias/anuladas', methods=['GET'])
def obtener_categorias_anuladas():
    try:
        # Obtener solo las categorías con estado 'anulado'
        categorias_anuladas = list(categorias_collection.find({'estado': 'anulado'}))
        
        # Convertir los ObjectId a string para poder enviar en la respuesta JSON
        for categoria in categorias_anuladas:
            categoria['_id'] = str(categoria['_id'])
        
        return jsonify(categorias_anuladas), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
if __name__ == '__main__':
    app.run(debug=True)
