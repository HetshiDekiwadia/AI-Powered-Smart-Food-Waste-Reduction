/**
 * EcoPlate AI - Main Frontend Utilities
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Auto-dismiss flash alerts after 5s
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            try {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } catch (e) {
                alert.style.display = 'none';
            }
        }, 5000);
    });

    // 2. Real-time cost estimator in Waste Logging Form
    const weightInput = document.getElementById('weight_kg');
    const categorySelect = document.getElementById('waste_category');
    const costEstimateDisplay = document.getElementById('cost_preview');

    if (weightInput && costEstimateDisplay) {
        const costMultipliers = {
            'Plate Waste': 60,
            'Prep Waste': 30,
            'Spoilage': 75,
            'Buffet Leftover': 55
        };

        const updateCost = () => {
            const weight = parseFloat(weightInput.value) || 0;
            const category = categorySelect ? categorySelect.value : 'Plate Waste';
            const rate = costMultipliers[category] || 50;
            const estimated = (weight * rate).toFixed(2);
            costEstimateDisplay.textContent = `₹${estimated}`;
        };

        weightInput.addEventListener('input', updateCost);
        if (categorySelect) categorySelect.addEventListener('change', updateCost);
        updateCost();
    }
});
