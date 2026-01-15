# Source Code Verification Guide

This guide explains how to verify that the PrivateSIM storefront you're accessing matches the open-source code published on GitHub.

## Why Verify?

When dealing with cryptocurrency payments and privacy-focused services, it's crucial to verify that the website you're using hasn't been tampered with or modified to include malicious code.

## Verification Methods

### Method 1: Check Version File (Easiest)

1. Visit the storefront on Tor
2. Click "Verify Source Code" link in the footer
3. Note the `commit` hash shown (e.g., `b6d18e23a29056e14062d1cc665baf30099c3b7d`)
4. Visit the [GitHub repository](https://github.com/vnshesims/vnsh)
5. Click on the commit history
6. Verify the commit hash matches the latest commit on the `main` branch

### Method 2: Clone and Compare

For advanced users who want to verify the entire codebase:

```bash
# 1. Clone the repository
git clone https://github.com/vnshesims/vnsh.git
cd anonymous-storefront

# 2. Get the commit hash from the live site
curl http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion/version.json

# 3. Checkout that specific commit
git checkout <commit-hash-from-step-2>

# 4. Download the live site files
mkdir live-site
cd live-site
curl -O http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion/index.html
curl -O http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion/style.css
curl -O http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion/store.js

# 5. Compare files
cd ..
diff -r . live-site/
```

If there are no differences (except for version.json), the site matches the GitHub source.

### Method 3: Hash Verification

```bash
# Clone the repo
git clone https://github.com/vnshesims/vnsh.git
cd anonymous-storefront

# Get the commit hash from live site
LIVE_COMMIT=$(curl -s http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion/version.json | grep -o '"commit": "[^"]*' | cut -d'"' -f4)

# Checkout that commit
git checkout $LIVE_COMMIT

# Generate hash of critical files
sha256sum index.html style.css store.js

# Download and hash live files
curl -s http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion/index.html | sha256sum
curl -s http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion/style.css | sha256sum
curl -s http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion/store.js | sha256sum
```

The SHA256 hashes should match exactly.

## What to Look For

When verifying, ensure:

1. **Commit Hash Matches**: The version.json commit matches the latest GitHub commit
2. **No Extra Files**: The live site doesn't include files not in the repository
3. **No Modified Code**: HTML, CSS, and JavaScript files match exactly
4. **BTCPay Configuration**: The BTCPayServer URL in store.js matches the expected onion address

## Red Flags

**DO NOT USE THE SITE** if you notice:

- Version.json missing or returning errors
- Commit hash doesn't exist in GitHub repository
- Commit hash is older than several days
- File hashes don't match
- Extra JavaScript files not in the repository
- Different BTCPayServer URL than documented

## Reporting Issues

If you discover discrepancies between the live site and GitHub:

1. **DO NOT make a payment**
2. Contact the operator via the official communication channels
3. Report the issue on [GitHub Issues](https://github.com/vnshesims/vnsh/issues)

## Transparency Commitment

All code changes are:
- Publicly committed to GitHub before deployment
- Automatically deployed from git with version tracking
- Verifiable by anyone at any time

## Technical Details

The deployment process works as follows:

1. Code is committed to GitHub repository
2. Developer pushes to production git server
3. Post-receive hook automatically deploys to web server
4. `version.json` is automatically generated with commit hash and timestamp
5. Nginx serves the files over Tor hidden service

This ensures that the live site always corresponds to a specific git commit that can be verified on GitHub.

## Automated Verification Script

For convenience, here's a complete verification script:

```bash
#!/bin/bash
# verify-storefront.sh - Automated storefront verification

ONION_URL="http://yftwmwb4oro3fbrljt4db24b2gbfmh4t4nxcq73z4blha2sx272aubyd.onion"
GITHUB_REPO="https://github.com/vnshesims/vnsh.git"

echo "=== PrivateSIM Storefront Verification ==="
echo ""

# Get live commit hash
echo "[1/5] Fetching version from live site..."
LIVE_COMMIT=$(curl -s --socks5-hostname localhost:9050 ${ONION_URL}/version.json | grep -o '"commit": "[^"]*' | cut -d'"' -f4)

if [ -z "$LIVE_COMMIT" ]; then
    echo "ERROR: Could not fetch version.json from live site"
    exit 1
fi

echo "Live site commit: ${LIVE_COMMIT}"
echo ""

# Clone repository
echo "[2/5] Cloning GitHub repository..."
rm -rf /tmp/storefront-verify
git clone --quiet $GITHUB_REPO /tmp/storefront-verify
cd /tmp/storefront-verify

# Checkout specific commit
echo "[3/5] Checking out commit ${LIVE_COMMIT}..."
git checkout --quiet $LIVE_COMMIT 2>/dev/null

if [ $? -ne 0 ]; then
    echo "ERROR: Commit ${LIVE_COMMIT} not found in GitHub repository"
    echo "This could indicate the live site is running unreleased or malicious code"
    exit 1
fi

echo ""

# Download and compare files
echo "[4/5] Comparing critical files..."
ERRORS=0

for FILE in index.html style.css store.js; do
    echo -n "Checking ${FILE}... "

    GITHUB_HASH=$(sha256sum $FILE | cut -d' ' -f1)
    LIVE_HASH=$(curl -s --socks5-hostname localhost:9050 ${ONION_URL}/${FILE} | sha256sum | cut -d' ' -f1)

    if [ "$GITHUB_HASH" = "$LIVE_HASH" ]; then
        echo "✓ MATCH"
    else
        echo "✗ MISMATCH"
        echo "  GitHub: ${GITHUB_HASH}"
        echo "  Live:   ${LIVE_HASH}"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# Results
echo "[5/5] Verification Results:"
if [ $ERRORS -eq 0 ]; then
    echo "✓ SUCCESS: All files match GitHub repository"
    echo "✓ The live site is running authentic, unmodified code"
    echo ""
    echo "Commit details:"
    git log -1 --pretty=format:"  Author: %an%n  Date: %ad%n  Message: %s%n" $LIVE_COMMIT
else
    echo "✗ FAILURE: ${ERRORS} file(s) do not match"
    echo "✗ DO NOT USE THIS SITE - it may have been compromised"
fi

echo ""

# Cleanup
cd /
rm -rf /tmp/storefront-verify
