from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from marshmallow import ValidationError
import os

app = Flask(__name__)

@app.route('/')
def ind():
    return 'test'




#DATABASE-----

basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'db.sqlite')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False



db = SQLAlchemy(app)
ma = Marshmallow(app)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_label = db.Column(db.String(100))
    confidence = db.Column(db.Float)
    timestamp = db.Column(db.String(100))

    def __init__(self, activity_label, confidence, timestamp):
        self.activity_label = activity_label
        self.confidence = confidence
        self.timestamp = timestamp


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    timestamp = db.Column(db.String(100))

    def __init__(self, latitude, longitude, timestamp):
        self.latitude = latitude
        self.longitude = longitude
        self.timestamp = timestamp


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(100))
    timestamp = db.Column(db.String(100))
    status = db.Column(db.Integer)

    def __init__(self, alert_type, timestamp, status):
        self.alert_type = alert_type
        self.timestamp = timestamp
        self.status = status


class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    esp32_status = db.Column(db.Integer)
    mpu_status = db.Column(db.Integer)
    gps_status = db.Column(db.Integer)
    gprs_status = db.Column(db.Integer)
    last_seen = db.Column(db.String(100))

    def __init__(self, esp32_status, mpu_status, gps_status, gprs_status, last_seen):
        self.esp32_status = esp32_status
        self.mpu_status = mpu_status
        self.gps_status = gps_status
        self.gprs_status = gprs_status
        self.last_seen = last_seen


class Walking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(100))
    distance_km = db.Column(db.Float)

    def __init__(self, date, distance_km):
        self.date = date
        self.distance_km = distance_km

with app.app_context():
    db.create_all()


# MARSHMALLOW SCHEMAS

class ActivitySchema(ma.Schema):
    id = ma.Integer(dump_only=True)
    activity_label = ma.String(required=True)
    confidence = ma.Float(required=True)
    timestamp = ma.String(required=True)


class LocationSchema(ma.Schema):
    id = ma.Integer(dump_only=True)
    latitude = ma.Float(required=True)
    longitude = ma.Float(required=True)
    timestamp = ma.String(required=True)


class AlertSchema(ma.Schema):
    id = ma.Integer(dump_only=True)
    alert_type = ma.String(required=True)
    timestamp = ma.String(required=True)
    status = ma.Integer(required=True)


class DeviceSchema(ma.Schema):
    id = ma.Integer(dump_only=True)
    esp32_status = ma.Integer(required=True)
    mpu_status = ma.Integer(required=True)
    gps_status = ma.Integer(required=True)
    gprs_status = ma.Integer(required=True)
    last_seen = ma.String(required=True)


class WalkingSchema(ma.Schema):
    id = ma.Integer(dump_only=True)
    date = ma.String(required=True)
    distance_km = ma.Float(required=True)


# SCHEMA OBJECTS

activity_schema = ActivitySchema()
activities_schema = ActivitySchema(many=True)

location_schema = LocationSchema()
locations_schema = LocationSchema(many=True)

alert_schema = AlertSchema()
alerts_schema = AlertSchema(many=True)

device_schema = DeviceSchema()
devices_schema = DeviceSchema(many=True)

walking_schema = WalkingSchema()
walkings_schema = WalkingSchema(many=True)

#esp->flask

@app.route('/activity', methods=['POST'])
def add_activity():

    # Receive JSON from ESP32
    data = request.get_json()

    # Validate JSON using Marshmallow
    try:
        activity_data = activity_schema.load(data)
    except ValidationError as err:
        return jsonify(err.messages), 400

    # Create database object
    new_activity = Activity(**activity_data)

    # Save into database
    db.session.add(new_activity)
    db.session.commit()

    # Send response
    return jsonify(activity_schema.dump(new_activity)), 201

#flask->web

@app.route('/activity', methods=['GET'])
def get_activities():

    activities = Activity.query.all()

    result = activities_schema.dump(activities)

    return jsonify(result)

#Location - ESP->FLASK

@app.route('/location', methods=['POST'])
def add_location():
    data = request.get_json()

    try:
        location_data = location_schema.load(data)
    except ValidationError as err:
        return jsonify(err.messages), 400

    new_location = Location(**location_data)

    db.session.add(new_location)
    db.session.commit()

    return jsonify(location_schema.dump(new_location)), 201

#FLASK->WEB
@app.route('/location', methods=['GET'])
def get_locations():
    locations = Location.query.all()

    return jsonify(locations_schema.dump(locations)), 200

#ALERT ESP32->FLASK

@app.route('/alert', methods=['POST'])
def add_alert():
    data = request.get_json()

    try:
        alert_data = alert_schema.load(data)
    except ValidationError as err:
        return jsonify(err.messages), 400

    new_alert = Alert(**alert_data)

    db.session.add(new_alert)
    db.session.commit()

    return jsonify(alert_schema.dump(new_alert)), 201

#FLASK->WEB
@app.route('/alert', methods=['GET'])
def get_alerts():
    alerts = Alert.query.all()

    return jsonify(alerts_schema.dump(alerts)), 200

#WEB->FLASK
@app.route('/alert/<int:id>', methods=['PUT'])
def update_alert(id):
    alert = db.session.get(Alert, id)

    if alert is None:
        return jsonify({"error": "Alert not found"}), 404

    data = request.get_json()
    status = data.get('status')

    if status not in [0, 1]:
        return jsonify({"error": "Invalid status"}), 400

    alert.status = status
    db.session.commit()

    return jsonify(alert_schema.dump(alert)), 200

#ESP->FLASK
@app.route('/device', methods=['POST'])
def add_device():
    data = request.get_json()

    try:
        device_data = device_schema.load(data)
    except ValidationError as err:
        return jsonify(err.messages), 400

    new_device = Device(**device_data)

    db.session.add(new_device)
    db.session.commit()

    return jsonify(device_schema.dump(new_device)), 201

#FLASK->WEB
@app.route('/device', methods=['GET'])
def get_devices():
    devices = Device.query.all()

    return jsonify(devices_schema.dump(devices)), 200

#ESP->FLASK
@app.route('/walking', methods=['POST'])
def add_walking():
    data = request.get_json()

    try:
        walking_data = walking_schema.load(data)
    except ValidationError as err:
        return jsonify(err.messages), 400

    new_walking = Walking(**walking_data)

    db.session.add(new_walking)
    db.session.commit()

    return jsonify(walking_schema.dump(new_walking)), 201

#FALSK->WEB
@app.route('/walking', methods=['GET'])
def get_walking():
    walking = Walking.query.all()

    return jsonify(walkings_schema.dump(walking)), 200

if __name__ == "__main__":
    app.run(debug=True)