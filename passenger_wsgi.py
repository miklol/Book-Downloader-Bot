import sys
import os

# Add the current directory to sys.path
sys.path.insert(0, os.path.dirname(__file__))

# Import the Flask app
from app import app as application

# Passenger expects 'application'
