#!/usr/bin/env bash
# Build and start a throwaway Neo4j + GDS for integration tests.
#   tools/embedded-neo4j/run.sh [data-dir] [port]
# Requires Java 21+ and Maven. Data lives in a fresh temp dir by default.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
home="${1:-$(mktemp -d -t bionexus-neo4j-XXXXXX)}"
port="${2:-7687}"
build="$here/target"

mvn -q -B -f "$here/pom.xml" compile dependency:build-classpath -Dmdep.outputFile="$build/classpath.txt"

# GDS procedures must be discovered from the plugin directory.
plugins="$build/plugins"
mkdir -p "$plugins"
tr ':' '\n' < "$build/classpath.txt" | grep '/org/neo4j/gds/' | xargs -I{} cp -f {} "$plugins/"

echo "Neo4j home: $home"
exec java -cp "$build/classes:$(cat "$build/classpath.txt")" emb.Main "$home" "$plugins" "$port"
