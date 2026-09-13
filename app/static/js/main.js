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

    // 2. Real-time deterministic cost estimator in Waste Logging Form
    const weightInput = document.getElementById('weight_kg');
    const categorySelect = document.getElementById('waste_category');
    const foodItemInput = document.querySelector('input[name="food_item"]');
    const costEstimateDisplay = document.getElementById('cost_preview');
    const formulaTextDisplay = document.getElementById('calc_formula_text');

    if (weightInput && costEstimateDisplay) {
        const categoryFallbackRates = {
            'Plate Waste': 60,
            'Prep Waste': 30,
            'Spoilage': 75,
            'Buffet Leftover': 55
        };

        const foodItemBenchmarks = {
            'rice': 35,
            'biryani': 45,
            'pulao': 40,
            'khichdi': 35,
            'idli': 35,
            'dosa': 40,
            'dal': 60,
            'sambhar': 50,
            'sambar': 50,
            'rajma': 65,
            'chole': 65,
            'lentil': 60,
            'roti': 40,
            'chapati': 40,
            'naan': 50,
            'paratha': 45,
            'bread': 40,
            'puri': 45,
            'paneer': 180,
            'cheese': 220,
            'butter': 250,
            'curd': 55,
            'milk': 60,
            'veg': 45,
            'vegetable': 45,
            'sabzi': 45,
            'bhindi': 40,
            'aloo': 30,
            'potato': 30,
            'gobi': 40,
            'curry': 50,
            'chicken': 160,
            'egg': 90,
            'mutton': 350,
            'fish': 200,
            'meat': 220,
            'kheer': 80,
            'halwa': 90,
            'gulab jamun': 110,
            'sweet': 90,
            'dessert': 90,
            'peel': 25,
            'trimming': 25,
            'scrap': 25
        };

        const resolveClientRate = (foodText, category) => {
            const cleaned = (foodText || '').toLowerCase().trim();
            const fallback = categoryFallbackRates[category] || 50;
            if (!cleaned) {
                return { rate: fallback, basis: `${category} Category Benchmark` };
            }

            // Split on delimiters: comma, &, +, /, and
            const tokens = cleaned.split(/[,&+/]|\band\b/).map(t => t.trim()).filter(t => t.length > 0);
            const matchedItems = [];
            const matchedRates = [];

            const sortedKeys = Object.keys(foodItemBenchmarks).sort((a, b) => b.length - a.length);

            tokens.forEach(token => {
                for (const key of sortedKeys) {
                    if (token.includes(key)) {
                        const capitalized = key.charAt(0).toUpperCase() + key.slice(1);
                        matchedItems.push(capitalized);
                        matchedRates.push(foodItemBenchmarks[key]);
                        break;
                    }
                }
            });

            if (matchedRates.length > 0) {
                const avg = matchedRates.reduce((a, b) => a + b, 0) / matchedRates.length;
                const roundedRate = Math.round(avg * 100) / 100;
                const basis = matchedRates.length > 1
                    ? `Blended Benchmark (${matchedItems.join(', ')})`
                    : `${matchedItems[0]} Benchmark`;
                return { rate: roundedRate, basis };
            }

            return { rate: fallback, basis: `${category} Stream Fallback` };
        };

        const updateCost = () => {
            const rawWeight = parseFloat(weightInput.value);
            const weight = (!isNaN(rawWeight) && rawWeight > 0) ? rawWeight : 0;
            const category = categorySelect ? categorySelect.value : 'Plate Waste';
            const foodText = foodItemInput ? foodItemInput.value : '';

            const { rate, basis } = resolveClientRate(foodText, category);
            const estimated = (weight * rate).toFixed(2);
            costEstimateDisplay.textContent = `₹${estimated}`;

            if (formulaTextDisplay) {
                if (weight > 0) {
                    formulaTextDisplay.textContent = `${weight.toFixed(1)} kg × ₹${rate.toFixed(2)}/kg [${basis}] = ₹${estimated}`;
                } else {
                    formulaTextDisplay.textContent = `Basis: ₹${rate.toFixed(2)}/kg (${basis})`;
                }
            }
        };

        weightInput.addEventListener('input', updateCost);
        if (categorySelect) categorySelect.addEventListener('change', updateCost);
        if (foodItemInput) foodItemInput.addEventListener('input', updateCost);
        updateCost();
    }

    // 3. Show / Hide Password Toggle
    document.querySelectorAll('.toggle-password').forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const targetSelector = button.getAttribute('data-target');
            const targetInput = targetSelector ? document.querySelector(targetSelector) : null;
            if (!targetInput) return;

            const icon = button.querySelector('i');
            const isPassword = targetInput.type === 'password';
            targetInput.type = isPassword ? 'text' : 'password';

            if (icon) {
                if (isPassword) {
                    icon.classList.remove('bi-eye');
                    icon.classList.add('bi-eye-slash');
                    button.setAttribute('aria-label', 'Hide password');
                } else {
                    icon.classList.remove('bi-eye-slash');
                    icon.classList.add('bi-eye');
                    button.setAttribute('aria-label', 'Show password');
                }
            }
        });
    });

    // 4. Client-side Form Validation for All Ecosystem Forms
    const interactiveForms = document.querySelectorAll('.needs-validation, #login_form, #register_form, #log_waste_form, #add_inventory_form, #list_surplus_form');
    interactiveForms.forEach(form => {
        form.addEventListener('submit', event => {
            let isValid = true;
            const requiredInputs = form.querySelectorAll('input[required], select[required], textarea[required]');

            requiredInputs.forEach(input => {
                if (input.type === 'checkbox') {
                    if (!input.checked) {
                        input.classList.add('is-invalid');
                        isValid = false;
                    } else {
                        input.classList.remove('is-invalid');
                    }
                    input.addEventListener('change', () => {
                        if (input.checked) input.classList.remove('is-invalid');
                    });
                    return;
                }

                if (input.type === 'radio') {
                    const name = input.name;
                    const isChecked = form.querySelector(`input[name="${name}"]:checked`);
                    const feedback = document.getElementById(`${name}_feedback`);
                    if (!isChecked) {
                        isValid = false;
                        if (feedback) feedback.classList.remove('d-none');
                    } else {
                        if (feedback) feedback.classList.add('d-none');
                    }
                    input.addEventListener('change', () => {
                        if (feedback) feedback.classList.add('d-none');
                    });
                    return;
                }

                const val = input.value ? input.value.trim() : '';
                const minLen = input.getAttribute('minlength') ? parseInt(input.getAttribute('minlength'), 10) : 0;
                const minVal = input.getAttribute('min') !== null ? parseFloat(input.getAttribute('min')) : null;
                const maxVal = input.getAttribute('max') !== null ? parseFloat(input.getAttribute('max')) : null;

                if (!val) {
                    input.classList.add('is-invalid');
                    isValid = false;
                } else if (minLen > 0 && val.length < minLen) {
                    input.classList.add('is-invalid');
                    isValid = false;
                } else if (minVal !== null && (parseFloat(val) < minVal || isNaN(parseFloat(val)))) {
                    input.classList.add('is-invalid');
                    isValid = false;
                } else if (maxVal !== null && parseFloat(val) > maxVal) {
                    input.classList.add('is-invalid');
                    isValid = false;
                } else if (input.type === 'number' && (isNaN(parseFloat(val)) || parseFloat(val) <= 0)) {
                    input.classList.add('is-invalid');
                    isValid = false;
                } else if (input.type === 'email' && (!val.includes('@') || !val.split('@')[1].includes('.'))) {
                    input.classList.add('is-invalid');
                    isValid = false;
                } else {
                    input.classList.remove('is-invalid');
                }

                input.addEventListener('input', () => {
                    input.classList.remove('is-invalid');
                }, { once: true });
            });

            if (!isValid) {
                event.preventDefault();
                event.stopPropagation();
            }
        });
    });
});

