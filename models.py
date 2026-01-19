from datetime import datetime

from peewee import Model, IntegerField, BooleanField, DateTimeField, TextField, CharField, FloatField, ForeignKeyField, \
    DateField, TimeField

from config import DATABASE, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DEFAULT_LANGUAGE
from routing import can_driver_pick_passenger
from utils import MySQLDatabaseReconnected

db = MySQLDatabaseReconnected(DATABASE, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)


class BaseModel(Model):
    class Meta:
        database = db


class Users(BaseModel):
    id: int
    language: str = CharField(null=True)
    telegram_username: str = CharField(null=True)
    telegram_id: int = IntegerField(null=False)
    telegram_full_name = CharField(null=True)
    is_baned: bool = BooleanField(default=False)
    is_admin: bool = BooleanField(default=False)

    @property
    def lang(self):
        return self.language if self.language else DEFAULT_LANGUAGE


class Trips(BaseModel):
    id: int
    user = ForeignKeyField(Users, on_delete="CASCADE", null=False)
    role = CharField(null=False)
    from_location_latitude = FloatField(null=True)
    from_location_longitude = FloatField(null=True)
    to_location_latitude = FloatField(null=True)
    to_location_longitude = FloatField(null=True)
    start_date = DateField(null=True)
    start_time = TimeField(null=True)
    place_count = IntegerField(null=True)
    from_text = TextField(null=True)
    to_text = TextField(null=True)
    passenger_role = TextField(null=True)
    created = DateTimeField(default=datetime.now)
    status = IntegerField(default=0)

    def on_route(self, record):
        return can_driver_pick_passenger(
            ((record.from_location_latitude, record.from_location_longitude),
             (record.to_location_latitude, record.to_location_longitude)),
            ((self.from_location_latitude, self.from_location_longitude),
             (self.to_location_latitude, self.to_location_longitude)))

    def duplicate(self):
        data = self.__data__.copy()
        data.pop('id', None)
        data.update({"status": 0, "created": datetime.now(), "start_date": None, "start_time": None})
        return self.__class__.create(**data)


class TakeASeat(BaseModel):
    id: int
    passenger_trip = ForeignKeyField(Trips, on_delete="CASCADE", null=False)
    driver_trip = ForeignKeyField(Trips, on_delete="CASCADE", null=False)


class Presets(BaseModel):
    id: int
    name = CharField(null=False)
    user = ForeignKeyField(Users, on_delete="CASCADE", null=False)
    trips = ForeignKeyField(Trips, on_delete="CASCADE", null=True)


db.create_tables([Users, Trips, Presets, TakeASeat], safe=True)
