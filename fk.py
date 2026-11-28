from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from marshmallow import ValidationError
from datetime import datetime,timezone
import os

app = Flask(__name__)

@app.route('/')
def ind():
    return 'test'




#DATABASE-----

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("postgresql://", "postgresql+psycopg2://")
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
    esp32_status = db.Column(db.Integer, default=0)
    mpu_status = db.Column(db.Integer)
    gps_status = db.Column(db.Integer)
    timestamp = db.Column(db.String(100))

    def __init__(self, esp32_status, mpu_status, gps_status, timestamp):
        self.esp32_status = esp32_status
        self.mpu_status = mpu_status
        self.gps_status = gps_status
        self.timestamp = timestamp


class Walking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(100))
    distance_km = db.Column(db.Float)

    def __init__(self, date, distance_km):
        self.date = date
        self.distance_km = distance_km


class DeviceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(50), nullable=False)
    event = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.String(50), nullable=False)

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
    esp32_status = ma.Integer(dump_only=True)
    mpu_status = ma.Integer(required=True)
    gps_status = ma.Integer(required=True)
    timestamp = ma.String(dump_only=True)


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

    # Select ONLY activity-related data
    activity_data = {
        "activity_label": data["activity_label"],
        "confidence": data["confidence"],
        "timestamp": data["timestamp"]
    }

    # Validate JSON using Marshmallow
    try:
        activity_data = activity_schema.load(activity_data)
    except ValidationError as err:
        return jsonify(err.messages), 400

    # Create database object
    new_activity = Activity(**activity_data)
    db.session.add(new_activity)

    # Automatically create alert for FALL
    if new_activity.activity_label == "FALL":

        new_alert = Alert(
            alert_type="FALL",
            timestamp=new_activity.timestamp,
            status=1
        )

        db.session.add(new_alert)

    # Save both records together
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
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

    # Extract location data from combined JSON
    location_data = {
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "timestamp": data["timestamp"]
    }
    try:
        location_data = location_schema.load(location_data)
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


#FLASK->WEB
@app.route('/alert', methods=['GET'])
def get_alerts():
    alerts = Alert.query.all()

    return jsonify(alerts_schema.dump(alerts)), 200

@app.route('/alert/pending', methods=['GET'])
def get_pending_alerts():
    alerts = Alert.query.filter_by(status=1).all()
    return jsonify(alerts_schema.dump(alerts)), 200

#WEB->FLASK
@app.route('/alert/<int:id>', methods=['PUT'])
def update_alert(id):
    alert = db.session.get(Alert, id)

    if alert is None:
        return jsonify({"error": "butAlert not found"}), 404

    data = request.get_json()

    if not data or "status" not in data:
        return jsonify({"error": "Status is required"}), 400
    
    status = data.get('status')

    if status not in [0, 1]:
        return jsonify({"error": "Invalid status"}), 400
    alert.status = status
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
    return jsonify(alert_schema.dump(alert)), 200
    
@app.route('/alert/resolve-pending', methods=['PUT'])
def resolve_pending_alerts():
    alerts = Alert.query.filter_by(status=1).all()

    for alert in alerts:
        alert.status = 0

    db.session.commit()

    return jsonify({
        "message": "All pending alerts resolved",
        "resolved_count": len(alerts)
    }), 200

#ESP->FLASK
@app.route('/device', methods=['POST'])
def add_device():
    data = request.get_json()

    try:
        device_data = device_schema.load(data, unknown="exclude")
    except ValidationError as err:
        return jsonify(err.messages), 400

    # Server reception time
    current_time = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    # Check existing device
    device = Device.query.first()

    if device:
        old_mpu = device.mpu_status
        old_gps = device.gps_status

        new_mpu = data["mpu_status"]
        new_gps = data["gps_status"]

        device.mpu_status = new_mpu
        device.gps_status = new_gps

        log_device_change("MPU6050", old_mpu, new_mpu)
        log_device_change("GPS", old_gps, new_gps)
        device.timestamp = current_time
        device.esp32_status = 1

    else:
        device = Device(
            esp32_status=1,
            mpu_status=device_data["mpu_status"],
            gps_status=device_data["gps_status"],
            timestamp=current_time
        )
        db.session.add(device)
        log_device_change("ESP32", 0, 1)
        log_device_change("MPU6050", 0, device.mpu_status)
        log_device_change("GPS", 0, device.gps_status)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(device_schema.dump(device)), 200

#helper fun
def log_device_change(device_name, old_status, new_status):
    if old_status == new_status:
        return

    event = "CONNECTED" if new_status == 1 else "DISCONNECTED"

    history = DeviceHistory(
        device_name=device_name,
        event=event,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    db.session.add(history)

#FLASK->WEB
@app.route('/device', methods=['GET'])
def get_devices():
    devices = Device.query.all()

    return jsonify(devices_schema.dump(devices)), 200

#FLASK->WEB(CHECKS STATUS)
@app.route('/device/status', methods=['GET'])
def device_status():

    device = Device.query.first()

    if not device:
        return jsonify({
            "esp32_status": 0,
            "mpu_status": 0,
            "gps_status": 0
        }), 200

    last_seen = datetime.fromisoformat(device.timestamp)

    elapsed = (
        datetime.now(timezone.utc) - last_seen
    ).total_seconds()

    # 10-second timeout
    old_status = device.esp32_status
    new_status = 1 if elapsed < 20 else 0

    device.esp32_status = new_status
    log_device_change("ESP32", old_status, new_status)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(device_schema.dump(device)), 200


@app.route('/device/history', methods=['GET'])
def get_device_history():
    history = DeviceHistory.query.order_by(
        DeviceHistory.id.desc()
    ).limit(50).all()

    return jsonify([
        {
            "device_name": item.device_name,
            "event": item.event,
            "timestamp": item.timestamp
        }
        for item in history
    ]), 200

#ESP->FLASK

WALKING_SPEED = 4  # km/hour


@app.route('/walking', methods=['POST'])
def add_walking():
    data = request.get_json()

    # Check activity
    if data.get("activity_label") != "WALK":
        return jsonify({"message": "Not walking"}), 200

    # Extract RTC date
    try:
        walk_date = datetime.strptime(
            data["timestamp"], "%Y-%m-%d %H:%M:%S"
        ).date()
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid timestamp"}), 400

    # Find existing date
    walking_record = Walking.query.filter_by(
        date=str(walk_date)
    ).first()

    # Distance for 1 second
    new_distance = WALKING_SPEED / 3600

    if walking_record:
        walking_record.distance_km += new_distance
    else:
        walking_record = Walking(
            date=str(walk_date),
            distance_km=new_distance
        )
        db.session.add(walking_record)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(walking_schema.dump(walking_record)), 200



#FALSK->WEB
@app.route('/walking', methods=['GET'])
def get_walking():
    walking = Walking.query.all()

    return jsonify(walkings_schema.dump(walking)), 200

if __name__ == "__main__":
    app.run(debug=True)
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from marshmallow import ValidationError
from datetime import datetime,timezone
import os

app = Flask(__name__)

@app.route('/')
def ind():
    return 'test'




#DATABASE-----

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("postgresql://", "postgresql+psycopg2://")
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
    esp32_status = db.Column(db.Integer, default=0)
    mpu_status = db.Column(db.Integer)
    gps_status = db.Column(db.Integer)
    timestamp = db.Column(db.String(100))

    def __init__(self, esp32_status, mpu_status, gps_status, timestamp):
        self.esp32_status = esp32_status
        self.mpu_status = mpu_status
        self.gps_status = gps_status
        self.timestamp = timestamp


class Walking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(100))
    distance_km = db.Column(db.Float)

    def __init__(self, date, distance_km):
        self.date = date
        self.distance_km = distance_km


class DeviceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_name = db.Column(db.String(50), nullable=False)
    event = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.String(50), nullable=False)

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
    esp32_status = ma.Integer(dump_only=True)
    mpu_status = ma.Integer(required=True)
    gps_status = ma.Integer(required=True)
    timestamp = ma.String(dump_only=True)


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

    # Select ONLY activity-related data
    activity_data = {
        "activity_label": data["activity_label"],
        "confidence": data["confidence"],
        "timestamp": data["timestamp"]
    }

    # Validate JSON using Marshmallow
    try:
        activity_data = activity_schema.load(activity_data)
    except ValidationError as err:
        return jsonify(err.messages), 400

    # Create database object
    new_activity = Activity(**activity_data)
    db.session.add(new_activity)

    # Automatically create alert for FALL
    if new_activity.activity_label == "FALL":

        new_alert = Alert(
            alert_type="FALL",
            timestamp=new_activity.timestamp,
            status=1
        )

        db.session.add(new_alert)

    # Save both records together
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
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

    # Extract location data from combined JSON
    location_data = {
        "latitude": data["latitude"],
        "longitude": data["longitude"],
        "timestamp": data["timestamp"]
    }
    try:
        location_data = location_schema.load(location_data)
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


#FLASK->WEB
@app.route('/alert', methods=['GET'])
def get_alerts():
    alerts = Alert.query.all()

    return jsonify(alerts_schema.dump(alerts)), 200

@app.route('/alert/pending', methods=['GET'])
def get_pending_alerts():
    alerts = Alert.query.filter_by(status=1).all()
    return jsonify(alerts_schema.dump(alerts)), 200

#WEB->FLASK
@app.route('/alert/<int:id>', methods=['PUT'])
def update_alert(id):
    alert = db.session.get(Alert, id)

    if alert is None:
        return jsonify({"error": "butAlert not found"}), 404

    data = request.get_json()

    if not data or "status" not in data:
        return jsonify({"error": "Status is required"}), 400
    
    status = data.get('status')

    if status not in [0, 1]:
        return jsonify({"error": "Invalid status"}), 400
    alert.status = status
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
    return jsonify(alert_schema.dump(alert)), 200
    
@app.route('/alert/resolve-pending', methods=['PUT'])
def resolve_pending_alerts():
    alerts = Alert.query.filter_by(status=1).all()

    for alert in alerts:
        alert.status = 0

    db.session.commit()

    return jsonify({
        "message": "All pending alerts resolved",
        "resolved_count": len(alerts)
    }), 200

#ESP->FLASK
@app.route('/device', methods=['POST'])
def add_device():
    data = request.get_json()

    try:
        device_data = device_schema.load(data, unknown="exclude")
    except ValidationError as err:
        return jsonify(err.messages), 400

    # Server reception time
    current_time = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    # Check existing device
    device = Device.query.first()

    if device:
        old_mpu = device.mpu_status
        old_gps = device.gps_status

        new_mpu = data["mpu_status"]
        new_gps = data["gps_status"]

        device.mpu_status = new_mpu
        device.gps_status = new_gps

        log_device_change("MPU6050", old_mpu, new_mpu)
        log_device_change("GPS", old_gps, new_gps)
        device.timestamp = current_time
        device.esp32_status = 1

    else:
        device = Device(
            esp32_status=1,
            mpu_status=device_data["mpu_status"],
            gps_status=device_data["gps_status"],
            timestamp=current_time
        )
        db.session.add(device)
        log_device_change("ESP32", 0, 1)
        log_device_change("MPU6050", 0, device.mpu_status)
        log_device_change("GPS", 0, device.gps_status)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(device_schema.dump(device)), 200

#helper fun
def log_device_change(device_name, old_status, new_status):
    if old_status == new_status:
        return

    event = "CONNECTED" if new_status == 1 else "DISCONNECTED"

    history = DeviceHistory(
        device_name=device_name,
        event=event,
        timestamp=datetime.now(timezone.utc).isoformat()
    )

    db.session.add(history)

#FLASK->WEB
@app.route('/device', methods=['GET'])
def get_devices():
    devices = Device.query.all()

    return jsonify(devices_schema.dump(devices)), 200

#FLASK->WEB(CHECKS STATUS)
@app.route('/device/status', methods=['GET'])
def device_status():

    device = Device.query.first()

    if not device:
        return jsonify({
            "esp32_status": 0,
            "mpu_status": 0,
            "gps_status": 0
        }), 200

    last_seen = datetime.fromisoformat(device.timestamp)

    elapsed = (
        datetime.now(timezone.utc) - last_seen
    ).total_seconds()

    # 10-second timeout
    old_status = device.esp32_status
    new_status = 1 if elapsed < 10 else 0

    device.esp32_status = new_status
    log_device_change("ESP32", old_status, new_status)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(device_schema.dump(device)), 200


@app.route('/device/history', methods=['GET'])
def get_device_history():
    history = DeviceHistory.query.order_by(
        DeviceHistory.id.desc()
    ).limit(50).all()

    return jsonify([
        {
            "device_name": item.device_name,
            "event": item.event,
            "timestamp": item.timestamp
        }
        for item in history
    ]), 200

#ESP->FLASK

WALKING_SPEED = 4  # km/hour


@app.route('/walking', methods=['POST'])
def add_walking():
    data = request.get_json()

    # Check activity
    if data.get("activity_label") != "WALK":
        return jsonify({"message": "Not walking"}), 200

    # Extract RTC date
    try:
        walk_date = datetime.strptime(
            data["timestamp"], "%Y-%m-%d %H:%M:%S"
        ).date()
    except (KeyError, ValueError):
        return jsonify({"error": "Invalid timestamp"}), 400

    # Find existing date
    walking_record = Walking.query.filter_by(
        date=str(walk_date)
    ).first()

    # Distance for 1 second
    new_distance = WALKING_SPEED / 3600

    if walking_record:
        walking_record.distance_km += new_distance
    else:
        walking_record = Walking(
            date=str(walk_date),
            distance_km=new_distance
        )
        db.session.add(walking_record)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify(walking_schema.dump(walking_record)), 200



#FALSK->WEB
@app.route('/walking', methods=['GET'])
def get_walking():
    walking = Walking.query.all()

    return jsonify(walkings_schema.dump(walking)), 200

if __name__ == "__main__":
    app.run(debug=True)
