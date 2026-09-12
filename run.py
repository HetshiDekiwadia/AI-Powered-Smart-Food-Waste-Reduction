import os
from app import create_app, db
from app.models import User, WasteLog, InventoryItem, SurplusListing, Claim

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'WasteLog': WasteLog,
        'InventoryItem': InventoryItem,
        'SurplusListing': SurplusListing,
        'Claim': Claim
    }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Run development server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
