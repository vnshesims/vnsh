#!/bin/bash
# Update version.json with current git commit hash and timestamp

COMMIT_HASH=$(git rev-parse HEAD)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

cat > version.json << EOF
{
  "commit": "${COMMIT_HASH}",
  "updated": "${TIMESTAMP}",
  "repository": "https://github.com/vnshesims/vnsh",
  "verification": "Compare this commit hash with the latest commit on GitHub to verify authenticity"
}
EOF

echo "Updated version.json with commit ${COMMIT_HASH}"
