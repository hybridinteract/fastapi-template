"""
SQLAlchemy Base Model.

This module provides the declarative base for all SQLAlchemy models.
All models should inherit from this Base class.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    All models should inherit from this class:
        from app.core.models import Base
        
        class User(Base):
            __tablename__ = "users"
            ...
    """
    pass
