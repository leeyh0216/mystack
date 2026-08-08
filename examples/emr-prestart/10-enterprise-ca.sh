# This file is sourced as trusted root code. Review it before use.
# Java keytool: https://docs.oracle.com/en/java/javase/17/docs/specs/man/keytool.html
# Replace this path and alias with your operator-controlled certificate and stable identifier.
certificate=/operator-input/company-root-ca.crt
alias=company-root-ca

keytool -importcert -noprompt -trustcacerts \
  -alias "$alias" \
  -file "$certificate" \
  -keystore "$JAVA_HOME/lib/security/cacerts" \
  -storepass changeit
install -m 0644 "$certificate" "/etc/pki/ca-trust/source/anchors/${alias}.crt"
update-ca-trust extract

# Python 3.11 in this image uses the system OpenSSL trust paths. These explicit values also cover
# libraries that honor the standard override variables.
export SSL_CERT_FILE=/etc/pki/tls/cert.pem
export REQUESTS_CA_BUNDLE=/etc/pki/tls/cert.pem
export AWS_CA_BUNDLE=/etc/pki/tls/cert.pem
