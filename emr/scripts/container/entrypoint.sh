#!/usr/bin/env bash
# Trusted root pre-start boundary followed by an exec-style privilege drop.
# Docker ENTRYPOINT: https://docs.docker.com/reference/dockerfile/#entrypoint
# Python setuid/exec: https://docs.python.org/3.11/library/os.html#os.setuid

set -Eeuo pipefail

mystack_json_escape() {
  local value=${1-}
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}
  value=${value//$'\r'/\\r}
  printf '%s' "$value"
}

mystack_log() {
  local level=$1
  shift
  local event=$1
  shift
  local output
  output="{\"timestamp\":\"$(/usr/bin/date -u +%Y-%m-%dT%H:%M:%S.%3NZ)\",\"level\":\"$(mystack_json_escape "$level")\",\"service\":\"emr-entrypoint\",\"event\":\"$(mystack_json_escape "$event")\""
  while (($#)); do
    local key=$1
    local value=$2
    shift 2
    output+=",\"$(mystack_json_escape "$key")\":\"$(mystack_json_escape "$value")\""
  done
  printf '%s}\n' "$output" >&2
}

mystack_fail() {
  local message=$1
  local fix_hint=$2
  mystack_log "ERROR" "emr.entrypoint.failed" \
    "reason" "$message" \
    "fix_hint" "$fix_hint"
  exit 1
}

mystack_command=("$@")
if ((${#mystack_command[@]} == 0)); then
  mystack_command=(mystack-emr --config /etc/mystack/mystack.yaml)
elif [[ ${mystack_command[0]} == -* ]]; then
  mystack_command=(mystack-emr "${mystack_command[@]}")
fi

if [[ $(/usr/bin/id -u) != 0 ]]; then
  mystack_fail \
    "The EMR entrypoint must begin as root before dropping to hadoop" \
    "Do not override the container user; the final service and workloads still run as hadoop."
fi

mystack_enabled=${MYSTACK_EMR_PRESTART_ENABLED:-false}
mystack_directory=${MYSTACK_EMR_PRESTART_DIR:-/etc/mystack/emr-prestart.d}
case ${mystack_enabled,,} in
  1 | true | yes | on) mystack_enabled=true ;;
  0 | false | no | off) mystack_enabled=false ;;
  *)
    mystack_fail \
      "MYSTACK_EMR_PRESTART_ENABLED must be a boolean" \
      "Use true to opt in or false to keep trusted root initialization disabled."
    ;;
esac

mystack_scripts=()
mystack_working_directory=$PWD
if [[ $mystack_enabled == true ]]; then
  [[ -d $mystack_directory && ! -L $mystack_directory ]] || mystack_fail \
    "The enabled pre-start path is not a real directory" \
    "Mount one operator-controlled directory read-only at MYSTACK_EMR_PRESTART_DIR."

  mystack_directory_mode=$(/usr/bin/stat -c '%a' "$mystack_directory")
  if (((8#$mystack_directory_mode & 0022) != 0)); then
    mystack_fail \
      "The pre-start directory is writable by its group or other users" \
      "Remove group/world write permission and mount the reviewed directory read-only."
  fi

  mystack_previous_lc_all=${LC_ALL-}
  mystack_lc_all_was_set=${LC_ALL+x}
  export LC_ALL=C
  shopt -s nullglob
  mystack_scripts=("$mystack_directory"/*.sh)
  shopt -u nullglob
  if [[ -n $mystack_lc_all_was_set ]]; then
    export LC_ALL=$mystack_previous_lc_all
  else
    unset LC_ALL
  fi

  mystack_log "INFO" "emr.prestart.scan.before" \
    "directory" "$mystack_directory" \
    "script_count" "${#mystack_scripts[@]}"
  for mystack_script in "${mystack_scripts[@]}"; do
    mystack_name=${mystack_script##*/}
    [[ $mystack_name =~ ^[A-Za-z0-9][A-Za-z0-9._-]*\.sh$ ]] || mystack_fail \
      "A pre-start script name is outside the safe allowlist" \
      "Use an alphanumeric prefix and only letters, digits, dot, underscore, or hyphen."
    [[ -f $mystack_script && ! -L $mystack_script ]] || mystack_fail \
      "A pre-start entry is not a regular non-symlink file" \
      "Mount reviewed regular .sh files; links, devices, directories, and sockets are rejected."
    mystack_mode=$(/usr/bin/stat -c '%a' "$mystack_script")
    if (((8#$mystack_mode & 0022) != 0)); then
      mystack_fail \
        "A pre-start script is writable by its group or other users" \
        "Remove group/world write permission before mounting the script directory."
    fi

    mystack_uid=$(/usr/bin/stat -c '%u' "$mystack_script")
    mystack_gid=$(/usr/bin/stat -c '%g' "$mystack_script")
    mystack_digest=$(/usr/bin/sha256sum "$mystack_script")
    mystack_digest=${mystack_digest%% *}
    mystack_started_ms=$(/usr/bin/date +%s%3N)
    mystack_current_script=$mystack_name
    mystack_current_digest=${mystack_digest:0:16}
    trap 'mystack_status=$?; if [[ -n ${mystack_current_script:-} ]]; then mystack_log "ERROR" "emr.prestart.script.failed" "script" "$mystack_current_script" "sha256_prefix" "$mystack_current_digest" "exit_code" "$mystack_status" "fix_hint" "Inspect the named operator-controlled script; its contents and environment values were not logged."; fi' EXIT
    mystack_log "INFO" "emr.prestart.script.before" \
      "script" "$mystack_name" \
      "sha256_prefix" "${mystack_digest:0:16}" \
      "mode" "$mystack_mode" \
      "uid" "$mystack_uid" \
      "gid" "$mystack_gid"
    # Source in this process so reviewed exports reach the service, bootstrap, and Spark children.
    # This is intentionally arbitrary root code and must never receive untrusted workload files.
    source "$mystack_script"
    mystack_duration_ms=$(( $(/usr/bin/date +%s%3N) - mystack_started_ms ))
    mystack_log "INFO" "emr.prestart.script.after" \
      "script" "$mystack_name" \
      "sha256_prefix" "${mystack_digest:0:16}" \
      "duration_ms" "$mystack_duration_ms"
    mystack_current_script=
    trap - EXIT
  done
  mystack_log "INFO" "emr.prestart.scan.after" \
    "directory" "$mystack_directory" \
    "completed_script_count" "${#mystack_scripts[@]}"
else
  mystack_log "INFO" "emr.prestart.disabled" \
    "directory" "$mystack_directory" \
    "fix_hint" "Set MYSTACK_EMR_PRESTART_ENABLED=true only for reviewed operator scripts."
fi

IFS=$' \t\n'
cd "$mystack_working_directory"
export HOME=/home/hadoop
export USER=hadoop
export LOGNAME=hadoop
mystack_log "INFO" "emr.entrypoint.privilege_drop.before" \
  "source_uid" "0" \
  "target_user" "hadoop" \
  "command_argument_count" "${#mystack_command[@]}" \
  "side_effect" "true"

# The fixed Python adapter changes supplementary groups/GID/UID and execs without forking. PID 1
# and reviewed exported values therefore reach the hadoop service directly.
exec /usr/local/bin/mystack-emr-run-as-hadoop "${mystack_command[@]}"
