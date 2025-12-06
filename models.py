from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class Movie(db.Model):
    __tablename__ = 'movies'
    
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(500), nullable=False)
    file_id = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(50), nullable=False)
    channel_id = db.Column(db.String(100))
    message_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'name': self.name,
            'file_id': self.file_id,
            'file_type': self.file_type,
            'channel_id': self.channel_id,
            'message_id': self.message_id
        }
