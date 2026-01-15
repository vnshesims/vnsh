# Anonymous Storefront

A privacy-focused e-commerce storefront designed for Tor hidden services with cryptocurrency payment integration.

## Features

- **Privacy-First Design**: Built for Tor hidden services
- **Cryptocurrency Payments**: Integrated with BTCPayServer for Bitcoin and Monero payments
- **Git-Based Deployment**: Automatic deployment via git push hooks
- **Verifiable Builds**: Users can verify the deployed site matches GitHub source code
- **Responsive Design**: Mobile-friendly layout
- **No Personal Data Collection**: Complete anonymity for customers

## Source Code Verification

This storefront is 100% open source and verifiable. Users can confirm the live site matches the GitHub code:

1. Visit the storefront and click "Verify Source Code" in the footer
2. Compare the commit hash with the latest commit on this repository
3. See [VERIFICATION.md](VERIFICATION.md) for detailed verification instructions

**Onion Address**: `yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion`

## Tech Stack

- HTML5/CSS3/JavaScript
- Nginx web server
- Docker containerization
- BTCPayServer payment processing
- Tor hidden service hosting

## File Structure

```
.
├── index.html          # Main storefront page
├── style.css           # Responsive styling
├── store.js            # BTCPayServer integration
├── version.json        # Auto-generated build version (for verification)
├── update-version.sh   # Script to update version info
├── README.md           # This file
└── VERIFICATION.md     # Detailed verification guide
```

## Configuration

### BTCPayServer Integration

Edit `store.js` and configure:

```javascript
const BTCPAY_URL = 'http://your-btcpay-onion-address.onion';
const STORE_ID = 'YOUR_STORE_ID_HERE';
```

### Adding Products

Edit `index.html` and add product cards:

```html
<div class="product-card">
    <img src="path/to/image.jpg" alt="Product Name" class="product-image">
    <h3>Product Name</h3>
    <p class="description">Product description</p>
    <p class="price">$X.XX</p>
    <button class="buy-btn" onclick="buyProduct('productID', X.XX)">Buy Now</button>
</div>
```

## Deployment

### Git-Based Deployment Setup

1. Set up a bare git repository on your server:
```bash
git init --bare /path/to/storefront.git
```

2. Create a post-receive hook for automatic deployment:
```bash
#!/bin/bash
TARGET="/path/to/public"
GIT_DIR="/path/to/storefront.git"
BRANCH="main"

while read oldrev newrev ref
do
    if [[ $ref = refs/heads/"$BRANCH" ]]; then
        echo "Deploying ${BRANCH} branch to production..."
        git --work-tree=$TARGET --git-dir=$GIT_DIR checkout -f $BRANCH
        echo "Deployment complete!"
    fi
done
```

3. Make the hook executable:
```bash
chmod +x /path/to/storefront.git/hooks/post-receive
```

4. Add the remote and push:
```bash
git remote add production ssh://user@server/path/to/storefront.git
git push production main
```

### Docker Deployment

Example `docker-compose.yml`:

```yaml
version: "3"

services:
  storefront_nginx:
    image: nginx:1.25.3-bookworm
    container_name: storefront_nginx
    restart: unless-stopped
    volumes:
      - ./public:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    expose:
      - "80"
    environment:
      - HIDDENSERVICE_NAME=Storefront
      - HIDDENSERVICE_PORT=80
    networks:
      - tor_network

networks:
  tor_network:
    external: true
```

## Security Considerations

- **Tor-Only Access**: Ensure your web server is only accessible via Tor
- **No Public Ports**: Don't expose ports to the public internet
- **HTTPS/Onion**: Tor provides encryption; additional HTTPS is optional
- **No Logging**: Configure nginx to minimize or disable access logs
- **Payment Security**: All payment processing handled by BTCPayServer

## Customization

### Styling

Edit `style.css` to customize:
- Colors and theme
- Layout and spacing
- Typography
- Responsive breakpoints

### Payment Methods

The storefront supports both Bitcoin and Monero through BTCPayServer. Configure payment methods in your BTCPayServer instance.

## License

MIT License - Feel free to use and modify for your own projects.

## Disclaimer

This software is provided as-is for educational and legitimate e-commerce purposes. Users are responsible for ensuring compliance with all applicable laws and regulations in their jurisdiction.
