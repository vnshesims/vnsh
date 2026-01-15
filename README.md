# Anonymous Storefront

Privacy-focused e-commerce storefront with BTCPayServer integration.

## Onion Addresses

- **Storefront**: http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion
- **BTCPayServer**: http://4yl2utzotn5uuoy6exiyr3gk2bt4ohnzmmb42ms7hvm57tp5et36ggad.onion

## Git-Based Deployment

All changes are deployed via Git. To update the website:

```bash
# Clone the repository (first time only)
git clone /home/admin/storefront/git/storefront.git
cd storefront

# Make your changes
# Edit index.html, style.css, store.js, etc.

# Commit and push (auto-deploys)
git add .
git commit -m "Your commit message"
git push origin main
```

The post-receive hook automatically deploys to `/home/admin/storefront/public`.

## BTCPayServer Integration

### Step 1: Create Store in BTCPayServer

1. Access BTCPayServer via Tor browser
2. Create account and store
3. Enable BTC and XMR payment methods
4. Get your Store ID from Settings

### Step 2: Update Website Configuration

Edit `store.js` and replace:
- `STORE_ID`: Your BTCPayServer store ID

### Step 3: Generate Payment Buttons

**Option A: Simple Button Integration (Recommended)**

1. In BTCPayServer, go to: Plugins → Point of Sale
2. Create a new Point of Sale app
3. Add your products with prices
4. Get the embed code for each product
5. Replace the `onclick` handlers in `index.html`

Example:
```html
<button onclick="window.location.href='http://4yl2utzotn5uuoy6exiyr3gk2bt4ohnzmmb42ms7hvm57tp5et36ggad.onion/apps/APPID/pos/cart/PRODUCTID'">
    Buy Now
</button>
```

**Option B: API Integration (Advanced)**

1. Create API key in BTCPayServer (Settings → Access Tokens)
2. Implement server-side proxy to handle API calls
3. Use the invoice creation API

## File Structure

```
/home/admin/storefront/
├── docker-compose.yml       # Container configuration
├── nginx.conf               # Nginx web server config
├── git/
│   └── storefront.git/      # Git repository (bare)
└── public/                  # Web root (auto-deployed from git)
    ├── index.html
    ├── style.css
    └── store.js
```

## Customization

### Adding Products

Edit `index.html` and add product cards:

```html
<div class="product-card">
    <img src="path/to/image.jpg" alt="Product Name">
    <h3>Product Name</h3>
    <p class="description">Product description</p>
    <p class="price">$X.XX</p>
    <button class="buy-btn" onclick="buyProduct('productX', X.XX)">Buy Now</button>
</div>
```

### Changing Styles

Edit `style.css` to customize colors, fonts, layout, etc.

### Adding Pages

1. Create new HTML file in repository
2. Update navigation links
3. Commit and push

## Security Notes

- Website is only accessible via Tor
- No public ports exposed
- All payments processed through BTCPayServer
- No customer data stored locally

## Management Commands

```bash
# View website
docker logs storefront_nginx

# Restart website
docker restart storefront_nginx

# View recent git deployments
cd /home/admin/storefront/git/storefront.git
git log

# Check Tor hidden service
docker exec tor cat /var/lib/tor/hidden_services/Storefront/hostname
```

## Monero Wallet Info

Monero wallet for receiving payments:
- Address: `45pzPmTrqtS2MS2t2AYYW6afdwFTijjeLaHwk2eczziY6DjWuu6hYNUUB54r8w1MNP3EBAc9rNKbHBWeRECnfpB2SsXvgAb`
- Password: `btcpayserver` (stored in `/home/admin/storefront/WALLET_BACKUP.txt`)

**IMPORTANT**: Back up the Monero wallet seed phrase from initial setup!

## Troubleshooting

**Website not loading:**
```bash
docker ps | grep storefront
docker logs storefront_nginx
```

**Changes not deploying:**
```bash
cd /home/admin/storefront/git/storefront.git
cat hooks/post-receive
chmod +x hooks/post-receive
```

**Onion address not working:**
```bash
docker exec tor cat /usr/local/etc/tor/torrc-2 | grep -A 3 Storefront
docker restart tor
```
