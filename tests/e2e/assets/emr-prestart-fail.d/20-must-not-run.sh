# Docker ENTRYPOINT exit contract: https://docs.docker.com/reference/dockerfile/#entrypoint
printf 'this script must never run\n' > /tmp/mystack-prestart-should-not-exist
