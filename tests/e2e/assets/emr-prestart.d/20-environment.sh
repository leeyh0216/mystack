# Docker ENTRYPOINT environment contract: https://docs.docker.com/reference/dockerfile/#entrypoint
test "$(tail -n 1 /var/lib/mystack/emr/prestart-e2e-order.txt)" = "10-root-ca"
keytool -list \
  -alias mystack-prestart-e2e \
  -keystore /var/lib/mystack/emr/prestart-e2e-cacerts \
  -storepass changeit >/dev/null
printf '20-environment\n' >> /var/lib/mystack/emr/prestart-e2e-order.txt
export MYSTACK_PRESTART_E2E_MARKER=trusted-root-environment-reached-hadoop
