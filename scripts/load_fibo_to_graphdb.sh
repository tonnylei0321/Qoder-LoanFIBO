#!/usr/bin/env bash
# Load FIBO 2025Q4 RDF files into GraphDB
# Usage: bash scripts/load_fibo_to_graphdb.sh

set -euo pipefail

GRAPHDB_URL="${GRAPHDB_URL:-http://localhost:7200}"
REPO_ID="fibo-2025q4"
FIBO_DIR="$(cd "$(dirname "$0")/.." && pwd)/docs/fibo-master_2025Q4"

echo "=== Loading FIBO 2025Q4 into GraphDB ==="
echo "  GraphDB: $GRAPHDB_URL"
echo "  FIBO dir: $FIBO_DIR"

# --- 1. Wait for GraphDB to be ready ---
echo "[1/4] Waiting for GraphDB..."
for i in $(seq 1 30); do
  if curl -sf "$GRAPHDB_URL/rest/repositories" > /dev/null 2>&1; then
    echo "  GraphDB is ready."
    break
  fi
  echo "  Waiting... ($i/30)"
  sleep 5
done

# --- 2. Create repository if not exists ---
echo "[2/4] Creating repository '$REPO_ID' (OWL-Horst reasoning)..."
REPO_EXISTS=$(curl -sf "$GRAPHDB_URL/rest/repositories" | python3 -c "
import json,sys
repos = json.load(sys.stdin)
print('yes' if any(r.get('id') == '$REPO_ID' for r in repos) else 'no')
" 2>/dev/null || echo "no")

if [ "$REPO_EXISTS" = "yes" ]; then
  echo "  Repository '$REPO_ID' already exists, skipping creation."
else
  CONFIG_TTL=$(cat <<'EOF'
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
@prefix rep:  <http://www.openrdf.org/config/repository#>.
@prefix sr:   <http://www.openrdf.org/config/repository/sail#>.
@prefix sail: <http://www.openrdf.org/config/sail#>.
@prefix owlim:<http://www.ontotext.com/trree/owlim#>.

[] a rep:Repository ;
   rep:repositoryID "fibo-2025q4" ;
   rdfs:label "FIBO 2025Q4 International Financial Ontology" ;
   rep:repositoryImpl [
      rep:repositoryType "graphdb:SailRepository" ;
      sr:sailImpl [
         sail:sailType "graphdb:Sail" ;
         owlim:ruleset "owl-horst-optimized" ;
         owlim:check-for-inconsistencies "false" ;
         owlim:entity-index-size "10000000" ;
         owlim:cache-memory "512m"
      ]
   ] .
EOF
)
  echo "$CONFIG_TTL" > /tmp/fibo-repo-config.ttl
  curl -sf -X POST "$GRAPHDB_URL/rest/repositories" \
    -H "Content-Type: multipart/form-data" \
    -F "config=@/tmp/fibo-repo-config.ttl;type=text/turtle"
  echo "  Repository created."
fi

# --- 3. Load RDF files (skip *Individuals*, *Metadata*, *All*.rdf) ---
echo "[3/4] Loading FIBO RDF files..."

LOAD_ORDER=(FND FBC LOAN SEC DER IND MD CAE BP ACTUS)
SKIP_PATTERNS=("Individuals" "Metadata" "^All")

loaded=0
skipped=0

for module in "${LOAD_ORDER[@]}"; do
  module_dir="$FIBO_DIR/$module"
  [ -d "$module_dir" ] || continue

  while IFS= read -r -d '' rdf_file; do
    fname=$(basename "$rdf_file")

    # Skip large/noisy files
    skip=false
    for pat in "${SKIP_PATTERNS[@]}"; do
      if echo "$fname" | grep -qE "$pat"; then
        skip=true
        break
      fi
    done
    if $skip; then
      skipped=$((skipped + 1))
      continue
    fi

    # Upload via GraphDB REST API (named graph = file URI)
    named_graph="urn:fibo:$(echo "$fname" | sed 's/.rdf$//')"
    http_status=$(curl -s -o /dev/null -w "%{http_code}" \
      -X POST "$GRAPHDB_URL/repositories/$REPO_ID/rdf-graphs/service?graph=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$named_graph', safe=''))")" \
      -H "Content-Type: application/rdf+xml" \
      --data-binary "@$rdf_file")

    if [ "$http_status" -ge 200 ] && [ "$http_status" -lt 300 ]; then
      echo "  Loaded: $fname"
      loaded=$((loaded + 1))
    else
      echo "  WARN: Failed to load $fname (HTTP $http_status)"
    fi
  done < <(find "$module_dir" -name "*.rdf" -print0 | sort -z)
done

echo "  Done: $loaded loaded, $skipped skipped."

# --- 4. Verify ---
echo "[4/4] Verifying class count..."
CLASS_COUNT=$(curl -sf \
  -H "Accept: application/sparql-results+json" \
  "$GRAPHDB_URL/repositories/$REPO_ID?query=$(python3 -c "import urllib.parse; print(urllib.parse.quote('SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?c a <http://www.w3.org/2002/07/owl#Class> . FILTER(STRSTARTS(STR(?c), \"https://spec.edmcouncil.org/fibo/\")) }', safe=''))")" \
  | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['results']['bindings'][0]['n']['value'])" 2>/dev/null || echo "unknown")

echo "  FIBO classes indexed: $CLASS_COUNT"
echo "=== GraphDB load complete. ==="
echo "  Access UI: $GRAPHDB_URL"
echo "  Repository: $REPO_ID"
