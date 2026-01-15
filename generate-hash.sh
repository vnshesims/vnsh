#!/bin/bash
# Generate verification hash of public site files
# Users can run this against the GitHub repo to verify the live site matches

cd /home/admin/storefront

# Generate hash of all public files EXCEPT version.json (sorted for consistency)
HASH=$(find public -type f \( -name "*.html" -o -name "*.css" -o -name "*.js" \) ! -name "version.json" | sort | xargs cat | sha256sum | cut -d' ' -f1)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Update version.json (commit is for display only, not part of hash verification)
cat > public/version.json << EOF
{
  "hash": "${HASH}",
  "commit": "${COMMIT}",
  "generated": "${TIMESTAMP}",
  "verify": "find public -type f \\( -name '*.html' -o -name '*.css' -o -name '*.js' \\) ! -name 'version.json' | sort | xargs cat | sha256sum"
}
EOF

echo "Hash generated: ${HASH}"
echo "Commit: ${COMMIT}"
echo "Timestamp: ${TIMESTAMP}"
