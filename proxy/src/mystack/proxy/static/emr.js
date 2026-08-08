/*
 * EMR operations and state vocabulary:
 * https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
 * https://docs.aws.amazon.com/emr/latest/APIReference/API_StepStatus.html
 */

import {ApiError, lines, pairs} from "./api.js";

const ACTIVE_STEPS = new Set(["PENDING", "CANCEL_PENDING", "RUNNING"]);
const TERMINAL_CLUSTERS = new Set(["TERMINATED", "TERMINATED_WITH_ERRORS"]);
const LOG_BUFFER_BYTES = Number(
  document.querySelector('meta[name="mystack-log-buffer-bytes"]').content,
);

export class EmrConsole {
  constructor(api, {notify, afterMutation, activateTab}) {
    this.api = api;
    this.notify = notify;
    this.afterMutation = afterMutation;
    this.activateTab = activateTab;
    this.document = null;
    this.clusterId = null;
    this.stepId = null;
    this.clusterQuery = "";
    this.stepQuery = "";
    this.logIdentity = null;
    this.logController = null;
    this.logPaused = false;
    this.logComplete = false;
    this.stdoutOffset = 0;
    this.stderrOffset = 0;
    this.stdoutContent = "";
    this.stderrContent = "";
    this._bind();
  }

  _bind() {
    byId("clusterSearch").addEventListener("input", event => {
      this.clusterQuery = event.target.value.toLowerCase();
      this._renderClusters();
    });
    byId("stepSearch").addEventListener("input", event => {
      this.stepQuery = event.target.value.toLowerCase();
      this._renderSteps();
    });
    byId("addStep").addEventListener("click", () => byId("stepDialog").showModal());
    byId("terminateCluster").addEventListener("click", () => this.terminate());
    byId("terminationProtection").addEventListener("click", () => this.toggleProtection());
    byId("cancelStep").addEventListener("click", () => this.cancelSelectedStep());
    byId("toggleLogFollow").addEventListener("click", () => this.toggleLogFollow());
    byId("downloadLogs").addEventListener("click", () => this.downloadLogs());
    byId("clusterForm").addEventListener("submit", event => this.create(event));
    byId("stepForm").addEventListener("submit", event => this.addStep(event));
  }

  setDocument(document) {
    this.document = document;
    this._renderReleaseOptions();
    const clusters = this.clusters;
    if (this.clusterId && !clusters.some(cluster => cluster.id === this.clusterId)) {
      this._stopLogStream();
      this.clusterId = null;
      this.stepId = null;
    }
    this._renderClusters();
    this._renderDetail();
  }

  get clusters() {
    return this.document?.resources?.clusters || [];
  }

  get selectedCluster() {
    return this.clusters.find(cluster => cluster.id === this.clusterId) || null;
  }

  get selectedStep() {
    return this.selectedCluster?.steps?.find(step => step.id === this.stepId) || null;
  }

  async create(event) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const instances = {
        InstanceCount: Number(form.get("instanceCount")),
        KeepJobFlowAliveWhenNoSteps: form.has("keepAlive"),
        TerminationProtected: form.has("terminationProtected"),
      };
      const payload = {
        Name: required(form, "name"),
        ReleaseLabel: required(form, "releaseLabel"),
        Instances: instances,
        Applications: [{Name: "Spark"}],
        VisibleToAllUsers: form.has("visibleToAllUsers"),
        StepConcurrencyLevel: Number(form.get("stepConcurrency")),
      };
      const serviceRole = text(form, "serviceRole");
      if (serviceRole) payload.ServiceRole = serviceRole;
      const logUri = text(form, "logUri");
      if (logUri) payload.LogUri = logUri;
      const bootstrapPath = text(form, "bootstrapPath");
      if (bootstrapPath) {
        payload.BootstrapActions = [{
          Name: "Console bootstrap",
          ScriptBootstrapAction: {
            Path: bootstrapPath,
            Args: lines(form.get("bootstrapArgs")),
          },
        }];
      }
      const tags = pairs(form.get("tags"), "Tags");
      if (tags.length) payload.Tags = tags.map(([Key, Value]) => ({Key, Value}));
      this.notify("Creating cluster…");
      const result = await this.api.aws("emr", "RunJobFlow", payload);
      this.clusterId = result.JobFlowId;
      this.stepId = null;
      formElement.closest("dialog").close();
      formElement.reset();
      formElement.elements.releaseLabel.value = this.document.emulator.default_release_label;
      formElement.elements.instanceCount.value = "1";
      formElement.elements.stepConcurrency.value = "1";
      formElement.elements.keepAlive.checked = true;
      formElement.elements.visibleToAllUsers.checked = true;
      await this.afterMutation(`Cluster ${result.JobFlowId} created`);
    } catch (error) {
      this.notifyError(error);
    }
  }

  async addStep(event) {
    event.preventDefault();
    if (!this.selectedCluster) return;
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    try {
      const properties = pairs(form.get("properties"), "Spark properties")
        .map(([Key, Value]) => ({Key, Value}));
      const args = [
        "spark-submit",
        ...lines(form.get("submitOptions")),
        required(form, "application"),
        ...lines(form.get("applicationArgs")),
      ];
      const hadoop = {Jar: "command-runner.jar", Args: args};
      if (properties.length) hadoop.Properties = properties;
      const payload = {
        JobFlowId: this.selectedCluster.id,
        Steps: [{
          Name: required(form, "name"),
          ActionOnFailure: text(form, "actionOnFailure") || "CONTINUE",
          HadoopJarStep: hadoop,
        }],
      };
      this.notify("Submitting Step…");
      const result = await this.api.aws("emr", "AddJobFlowSteps", payload);
      this.stepId = result.StepIds[0];
      formElement.closest("dialog").close();
      formElement.reset();
      await this.afterMutation(`Step ${this.stepId} submitted`);
      this.activateTab("steps");
    } catch (error) {
      this.notifyError(error);
    }
  }

  async terminate() {
    const cluster = this.selectedCluster;
    if (!cluster || TERMINAL_CLUSTERS.has(cluster.state)) return;
    if (!window.confirm(`Terminate cluster ${cluster.name} (${cluster.id})?`)) return;
    try {
      this.notify("Terminating cluster…");
      await this.api.aws("emr", "TerminateJobFlows", {JobFlowIds: [cluster.id]});
      await this.afterMutation("Termination submitted");
    } catch (error) {
      this.notifyError(error);
    }
  }

  async toggleProtection() {
    const cluster = this.selectedCluster;
    if (!cluster || TERMINAL_CLUSTERS.has(cluster.state)) return;
    try {
      const enabled = !cluster.termination_protected;
      this.notify(enabled ? "Enabling termination protection…" : "Disabling termination protection…");
      await this.api.aws("emr", "SetTerminationProtection", {
        JobFlowIds: [cluster.id],
        TerminationProtected: enabled,
      });
      await this.afterMutation(enabled ? "Termination protection enabled" : "Termination protection disabled");
    } catch (error) {
      this.notifyError(error);
    }
  }

  async cancelSelectedStep() {
    const cluster = this.selectedCluster;
    const step = this.selectedStep;
    if (!cluster || !step || !ACTIVE_STEPS.has(step.state)) return;
    try {
      this.notify("Cancelling Step…");
      await this.api.aws("emr", "CancelSteps", {
        ClusterId: cluster.id,
        StepIds: [step.id],
      });
      await this.afterMutation("Step cancellation submitted");
    } catch (error) {
      this.notifyError(error);
    }
  }

  async refreshLogs() {
    const cluster = this.selectedCluster;
    const step = this.selectedStep;
    if (!cluster || !step) {
      this._stopLogStream();
      this.logIdentity = null;
      byId("logEmpty").hidden = false;
      byId("logContent").hidden = true;
      return;
    }
    const identity = `${cluster.id}/${step.id}`;
    try {
      byId("logEmpty").hidden = true;
      byId("logContent").hidden = false;
      byId("logStepName").textContent = step.name;
      byId("logStepIdentity").textContent = `${step.id} · ${step.state}${step.recovered ? " · recovered logs" : ""}`;
      byId("cancelStep").disabled = !ACTIVE_STEPS.has(step.state);
      if (this.logIdentity === identity) return;
      this._stopLogStream();
      this.logIdentity = identity;
      this.logPaused = false;
      this.logComplete = false;
      this.stdoutOffset = 0;
      this.stderrOffset = 0;
      this.stdoutContent = "";
      this.stderrContent = "";
      this._renderLogText();
      this._renderFollowState("Connecting…", "live");
      const logs = await this.api.logs(cluster.id, step.id);
      if (this.logIdentity !== identity) return;
      renderPublication(byId("logPublication"), logs.log_publication || {status: "unavailable"});
      this._startLogStream(identity);
    } catch (error) {
      if (this.logIdentity === identity) this.logIdentity = null;
      byId("logEmpty").hidden = false;
      byId("logEmpty").textContent = error instanceof ApiError ? error.display() : String(error);
      byId("logContent").hidden = true;
    }
  }

  toggleLogFollow() {
    if (!this.logIdentity || this.logComplete) return;
    if (this.logPaused) {
      this.logPaused = false;
      this._renderFollowState("Reconnecting…", "live");
      this._startLogStream(this.logIdentity);
      return;
    }
    this.logPaused = true;
    this._stopLogStream();
    this._renderFollowState("Paused", "paused");
  }

  downloadLogs() {
    const step = this.selectedStep;
    if (!step) return;
    const content = [
      `Mystack EMR Step ${step.id}`,
      "",
      "===== stdout =====",
      this.stdoutContent,
      "",
      "===== stderr =====",
      this.stderrContent,
      "",
    ].join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([content], {type: "text/plain;charset=utf-8"}));
    link.download = `${step.id}-logs.txt`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async _startLogStream(identity) {
    if (this.logController || this.logPaused || this.logComplete || identity !== this.logIdentity) return;
    const [clusterId, stepId] = identity.split("/");
    const controller = new AbortController();
    this.logController = controller;
    this._renderFollowState("Following live output", "live");
    try {
      const result = await this.api.streamLogs(clusterId, stepId, {
        stdoutOffset: this.stdoutOffset,
        stderrOffset: this.stderrOffset,
        signal: controller.signal,
        onEvent: document => this._appendLogEvent(identity, document),
      });
      if (identity !== this.logIdentity) return;
      this.logComplete = result.complete;
      if (result.complete) this._renderFollowState("Complete", "");
      else this._renderFollowState("Reconnecting…", "live");
    } catch (error) {
      if (error.name === "AbortError") return;
      if (identity !== this.logIdentity) return;
      this._renderFollowState("Stream interrupted · retrying", "paused");
      this.notifyError(error);
    } finally {
      if (this.logController === controller) this.logController = null;
    }
    if (!this.logPaused && !this.logComplete && identity === this.logIdentity) {
      window.setTimeout(() => this._startLogStream(identity), 500);
    }
  }

  _appendLogEvent(identity, document) {
    if (identity !== this.logIdentity) return;
    this.stdoutOffset = Number(document.stdout_next_offset ?? this.stdoutOffset);
    this.stderrOffset = Number(document.stderr_next_offset ?? this.stderrOffset);
    this.stdoutContent = trimLogBuffer(this.stdoutContent + (document.stdout || ""));
    this.stderrContent = trimLogBuffer(this.stderrContent + (document.stderr || ""));
    this._renderLogText();
    renderPublication(
      byId("logPublication"),
      document.log_publication || {status: "unavailable"},
    );
    if (document.complete) {
      this.logComplete = true;
      this._renderFollowState("Complete", "");
    }
  }

  _renderLogText() {
    renderFollowedText(byId("stdout"), this.stdoutContent);
    renderFollowedText(byId("stderr"), this.stderrContent);
  }

  _renderFollowState(label, tone) {
    const status = byId("logFollowStatus");
    status.textContent = label;
    status.className = `stream-status${tone ? ` ${tone}` : ""}`;
    const button = byId("toggleLogFollow");
    button.textContent = this.logPaused ? "Resume follow" : "Pause follow";
    button.disabled = this.logComplete || !this.logIdentity;
  }

  _stopLogStream() {
    this.logController?.abort();
    this.logController = null;
  }

  notifyError(error) {
    this.notify(error instanceof ApiError ? error.display() : String(error), true);
  }

  _renderReleaseOptions() {
    const select = byId("clusterForm").elements.releaseLabel;
    const selected = select.value;
    const profiles = this.document?.emulator?.release_profiles || {};
    const fallback = this.document?.emulator?.default_release_label || "";
    select.replaceChildren();
    for (const [label, profile] of Object.entries(profiles)) {
      select.append(node("option", {
        value: label,
        text: `${label} · Spark ${profile.aws_spark_version || "configured"}`,
      }));
    }
    select.value = Object.hasOwn(profiles, selected) ? selected : fallback;
    select.disabled = !select.options.length;
  }

  _renderClusters() {
    const root = byId("clusterList");
    root.replaceChildren();
    const clusters = this.clusters.filter(cluster =>
      `${cluster.name} ${cluster.id} ${cluster.state}`.toLowerCase().includes(this.clusterQuery)
    );
    byId("clusterCount").textContent = String(this.clusters.length);
    if (!clusters.length) {
      root.append(emptyList(this.clusters.length ? "No matching clusters" : "No clusters yet"));
      return;
    }
    for (const cluster of clusters) {
      const button = node("button", {
        className: `resource-item${cluster.id === this.clusterId ? " selected" : ""}`,
        type: "button",
        ariaLabel: `Cluster ${cluster.name}`,
      },
      node("span", {}, node("strong", {text: cluster.name}), node("small", {text: cluster.id})),
      stateBadge(cluster.state));
      button.addEventListener("click", () => {
        this.clusterId = cluster.id;
        this.stepId = null;
        this._renderClusters();
        this._renderDetail();
      });
      root.append(button);
    }
  }

  _renderDetail() {
    const cluster = this.selectedCluster;
    byId("emrEmpty").hidden = Boolean(cluster);
    byId("emrDetail").hidden = !cluster;
    if (!cluster) return;
    byId("clusterDetailHeading").textContent = cluster.name;
    byId("clusterIdentity").textContent = cluster.id;
    byId("terminationProtection").textContent = cluster.termination_protected ? "Unprotect" : "Protect";
    byId("terminateCluster").disabled = TERMINAL_CLUSTERS.has(cluster.state);
    byId("addStep").disabled = !["WAITING", "RUNNING"].includes(cluster.state);
    facts(byId("clusterFacts"), [
      ["State", cluster.state],
      ["Release", cluster.release_label],
      ["Instances", cluster.instance_config?.InstanceCount ?? "—"],
      ["Log URI", cluster.log_uri || "Not configured"],
      ["Step concurrency", cluster.step_concurrency_level],
      ["Service role", cluster.service_role || "Not configured"],
      ["Visible to all users", cluster.visible_to_all_users ? "Yes" : "No"],
      ["Termination protected", cluster.termination_protected ? "Yes" : "No"],
      ["Created", formatTime(cluster.created_at)],
      ["Ready", formatTime(cluster.ready_at)],
    ]);
    keyValues(byId("tagList"), cluster.tags || {}, "No tags");
    listValues(
      byId("bootstrapList"),
      cluster.bootstrap_actions || [],
      action => `${action.name} · ${action.path} · ${action.argument_count} args`,
      "No bootstrap actions",
    );
    renderTimeline(cluster);
    byId("emrRaw").textContent = JSON.stringify(cluster, null, 2);
    this._renderSteps();
    if (this.stepId) this.refreshLogs();
  }

  _renderSteps() {
    const root = byId("stepRows");
    root.replaceChildren();
    const cluster = this.selectedCluster;
    if (!cluster) return;
    const steps = (cluster.steps || []).filter(step =>
      `${step.name} ${step.id} ${step.state}`.toLowerCase().includes(this.stepQuery)
    );
    if (!steps.length) {
      root.append(node("tr", {}, node("td", {text: cluster.steps?.length ? "No matching Steps" : "No Steps submitted", colSpan: "5"})));
      return;
    }
    for (const step of steps) {
      const row = node("tr", {
        className: `selectable${step.id === this.stepId ? " selected" : ""}`,
        tabIndex: "0",
        ariaLabel: `Step ${step.name}`,
      },
      node("td", {}, node("strong", {text: step.name}), node("small", {className: "mono muted", text: step.id})),
      node("td", {}, stateBadge(step.state)),
      node("td", {text: formatTime(step.created_at)}),
      node("td", {text: duration(step.started_at, step.ended_at)}),
      node("td"));
      const select = () => {
        this.stepId = step.id;
        this._renderSteps();
        this.activateTab("logs");
        this.refreshLogs();
      };
      row.addEventListener("click", select);
      row.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          select();
        }
      });
      const actionCell = row.lastElementChild;
      if (ACTIVE_STEPS.has(step.state)) {
        const cancel = node("button", {className: "button danger row-action", type: "button", text: "Cancel"});
        cancel.addEventListener("click", event => {
          event.stopPropagation();
          this.stepId = step.id;
          this.cancelSelectedStep();
        });
        actionCell.append(cancel);
      } else {
        actionCell.textContent = "View logs";
      }
      root.append(row);
    }
  }
}

function byId(id) {
  return document.getElementById(id);
}

function required(form, name) {
  const value = text(form, name);
  if (!value) throw new ApiError(`${name} is required`, {code: "InvalidConsoleInput"});
  return value;
}

function text(form, name) {
  return String(form.get(name) || "").trim();
}

function node(tag, attributes = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (value === undefined || value === null) continue;
    if (key === "className") element.className = value;
    else if (key === "text") element.textContent = String(value);
    else if (key === "ariaLabel") element.setAttribute("aria-label", value);
    else element.setAttribute(key, value);
  }
  element.append(...children);
  return element;
}

function emptyList(message) {
  return node("div", {className: "empty-list", text: message});
}

function stateBadge(state) {
  const normalized = String(state || "UNKNOWN");
  const good = ["WAITING", "RUNNING", "COMPLETED"].includes(normalized);
  const bad = ["FAILED", "CANCELLED", "TERMINATED_WITH_ERRORS"].includes(normalized);
  const tone = good ? "good" : bad ? "bad" : "warn";
  return node("span", {className: `state-badge ${tone}`, text: normalized});
}

function facts(root, values) {
  root.replaceChildren();
  for (const [label, value] of values) {
    root.append(node("div", {}, node("dt", {text: label}), node("dd", {text: value ?? "—"})));
  }
}

function keyValues(root, values, empty) {
  root.replaceChildren();
  const entries = Object.entries(values);
  if (!entries.length) {
    root.append(node("p", {className: "muted", text: empty}));
    return;
  }
  const list = node("dl", {className: "key-value-list"});
  for (const [key, value] of entries) {
    list.append(node("div", {}, node("dt", {text: key}), node("dd", {text: String(value)})));
  }
  root.append(list);
}

function listValues(root, values, render, empty) {
  root.replaceChildren();
  if (!values.length) {
    root.append(node("p", {className: "muted", text: empty}));
    return;
  }
  const list = node("ul");
  for (const value of values) list.append(node("li", {text: render(value)}));
  root.append(list);
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString();
}

function duration(start, end) {
  if (!start) return "—";
  const milliseconds = (end ? new Date(end) : new Date()) - new Date(start);
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "—";
  const seconds = Math.round(milliseconds / 1000);
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

function renderTimeline(cluster) {
  const root = byId("clusterTimeline");
  root.replaceChildren();
  const events = [
    ["Created", cluster.created_at],
    ["Ready", cluster.ready_at],
    ["Ended", cluster.ended_at],
  ].filter(([, value]) => value);
  for (const [label, value] of events) {
    root.append(node("li", {}, node("strong", {text: label}), node("time", {text: formatTime(value)})));
  }
  if (!events.length) root.append(node("li", {text: "Timeline unavailable"}));
}

function renderPublication(root, publication) {
  const values = {
    Status: publication.status,
    "Log URI": publication.log_uri || "—",
    "Published objects": publication.published_keys?.length ?? 0,
    "Exit code": publication.exit_code ?? "—",
    Error: publication.error || publication.reason || "—",
  };
  keyValues(root, values, "Publication unavailable");
  if (publication.published_keys?.length) {
    const details = node("details", {}, node("summary", {text: "Published object keys"}));
    const list = node("ul", {className: "mono"});
    for (const key of publication.published_keys) list.append(node("li", {text: key}));
    details.append(list);
    root.append(details);
  }
}

function trimLogBuffer(value) {
  const encoder = new TextEncoder();
  if (encoder.encode(value).byteLength <= LOG_BUFFER_BYTES) return value;
  const notice = `[older output removed; ${LOG_BUFFER_BYTES} byte browser limit]\n`;
  let tail = value.slice(-Math.max(1, LOG_BUFFER_BYTES - encoder.encode(notice).byteLength));
  while (encoder.encode(notice + tail).byteLength > LOG_BUFFER_BYTES) {
    tail = tail.slice(Math.max(1, Math.floor(tail.length / 20)));
  }
  return notice + tail;
}

function renderFollowedText(root, value) {
  const followsBottom = root.scrollHeight - root.scrollTop - root.clientHeight < 48;
  root.textContent = value || "(waiting for output)";
  if (followsBottom) root.scrollTop = root.scrollHeight;
}
