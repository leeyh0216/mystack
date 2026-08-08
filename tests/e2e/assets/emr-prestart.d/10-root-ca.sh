# Docker-only disposable CA contract for the trusted root boundary.
# Java keytool: https://docs.oracle.com/en/java/javase/17/docs/specs/man/keytool.html
test "$(id -u)" = "0"

prestart_e2e_key_store=/tmp/mystack-prestart-source.p12
prestart_e2e_certificate=/tmp/mystack-prestart-ca.crt
prestart_e2e_java_store=/var/lib/mystack/emr/prestart-e2e-cacerts
keytool -genkeypair -noprompt \
  -alias mystack-prestart-source \
  -dname "CN=Mystack Prestart E2E CA" \
  -keyalg RSA \
  -ext bc=ca:true \
  -ext ku=keyCertSign,cRLSign \
  -validity 1 \
  -storetype PKCS12 \
  -keystore "$prestart_e2e_key_store" \
  -storepass mystack-e2e \
  -keypass mystack-e2e
keytool -exportcert -rfc \
  -alias mystack-prestart-source \
  -keystore "$prestart_e2e_key_store" \
  -storepass mystack-e2e \
  -file "$prestart_e2e_certificate"

cp "$JAVA_HOME/lib/security/cacerts" "$prestart_e2e_java_store"
keytool -importcert -noprompt -trustcacerts \
  -alias mystack-prestart-e2e \
  -file "$prestart_e2e_certificate" \
  -keystore "$prestart_e2e_java_store" \
  -storepass changeit
install -m 0644 "$prestart_e2e_certificate" \
  /etc/pki/ca-trust/source/anchors/mystack-prestart-e2e.crt
update-ca-trust extract

python3.11 - <<'PY'
import ssl
from pathlib import Path

pem = Path("/tmp/mystack-prestart-ca.crt").read_text(encoding="utf-8")
expected = ssl.PEM_cert_to_DER_cert(pem)
trusted = ssl.create_default_context().get_ca_certs(binary_form=True)
if expected not in trusted:
    raise SystemExit("generated E2E CA was not installed in Python's system trust")
PY

printf '10-root-ca\n' >> /var/lib/mystack/emr/prestart-e2e-order.txt
rm -f "$prestart_e2e_key_store" "$prestart_e2e_certificate"
export JAVA_TOOL_OPTIONS="-Djavax.net.ssl.trustStore=$prestart_e2e_java_store ${JAVA_TOOL_OPTIONS:-}"
