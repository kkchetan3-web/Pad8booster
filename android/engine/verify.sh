#!/usr/bin/env bash
# Verify the PADFINITY engine without an Android SDK.
#
# Requires only a JDK (17+) and the Kotlin compiler on PATH. This is how the
# engine's 135 checks are executed in environments that have no Android SDK,
# no Gradle and no access to Maven repositories.
set -euo pipefail
cd "$(dirname "$0")"

KC="${KOTLINC:-kotlinc}"
OUT="engine-tests.jar"

echo "compiling engine + tests with $KC"
"$KC" src/main/kotlin src/test/kotlin -include-runtime -d "$OUT" 2>&1 | grep -v '^warning:' || true

echo "running checks"
java -jar "$OUT"
