import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sih-smart-food-waste-2026-secret-key-secure')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'database.sqlite')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Application specific parameters
    ML_MODEL_PATH = os.path.join(BASE_DIR, 'ml_models', 'demand_forecaster.pkl')
    DATASET_PATH = os.path.join(BASE_DIR, 'ml_models', 'sample_cafeteria_data.csv')
    
    # Impact benchmarks (Based on FAO / UNEP food waste metrics)
    CO2_PER_KG_FOOD = 2.5      # ~2.5 kg CO2 equivalent per 1 kg food waste avoided
    WATER_PER_KG_FOOD = 1000   # ~1,000 liters of water embedded per 1 kg food
    AVG_COST_PER_MEAL = 45     # INR average savings per un-wasted portion
