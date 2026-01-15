/**
 * VNSH Dynamic Pricing
 * Fetches pricing from API and updates purchase options
 */

const BTCPAY_URL = 'http://4yl2utzotn5uuoy6exiyr3gk2bt4ohnzmmb42ms7hvm57tp5et36ggad.onion';
const STORE_ID = 'YOUR_STORE_ID'; // Configure this in BTCPay

// DOM elements
const purchaseOptions = document.querySelector('.purchase-options');
const countrySelect = document.getElementById('country-select');

/**
 * Format price for display
 */
function formatPrice(price) {
    return '$' + parseFloat(price).toFixed(0);
}

/**
 * Generate checkout URL for BTCPay
 */
function getCheckoutUrl(plan) {
    const itemDesc = `${plan.duration_days}d-${plan.data_gb}gb`;
    return `${BTCPAY_URL}/checkout?storeId=${STORE_ID}&price=${plan.price_usd}&currency=USD&itemDesc=${itemDesc}`;
}

/**
 * Render pricing options
 */
function renderPricing(plans) {
    if (!purchaseOptions) return;

    purchaseOptions.innerHTML = plans.map(plan => {
        const isFeatured = plan.featured === 1;
        return `
            <a href="${getCheckoutUrl(plan)}" class="purchase-option${isFeatured ? ' featured' : ''}">
                ${isFeatured ? '<div class="option-badge">Best Value</div>' : ''}
                <div class="option-duration">${plan.plan_name}</div>
                <div class="option-details">
                    <span class="option-data">${plan.data_gb} GB</span>
                    <span class="option-price">${formatPrice(plan.price_usd)}</span>
                </div>
            </a>
        `;
    }).join('');
}

/**
 * Fetch pricing from API
 */
async function fetchPricing(countryCode = null) {
    try {
        const url = countryCode ? `/api/pricing?country=${countryCode}` : '/api/pricing';
        const response = await fetch(url);
        const data = await response.json();
        renderPricing(data.plans);
    } catch (error) {
        console.error('Failed to fetch pricing:', error);
    }
}

/**
 * Fetch and populate country selector
 */
async function fetchCountries() {
    if (!countrySelect) return;

    try {
        const response = await fetch('/api/countries');
        const data = await response.json();

        countrySelect.innerHTML = data.countries.map(c =>
            `<option value="${c.code}">${c.name}</option>`
        ).join('');

        // Listen for country changes
        countrySelect.addEventListener('change', (e) => {
            fetchPricing(e.target.value);
        });
    } catch (error) {
        console.error('Failed to fetch countries:', error);
    }
}

/**
 * Initialize on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    fetchPricing();
    fetchCountries();
});
