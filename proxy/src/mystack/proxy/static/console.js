/*
 * Console shell and accessible tabs:
 * https://www.w3.org/WAI/ARIA/apg/patterns/tabs/
 * Dialog keyboard contract:
 * https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
 */

import {ApiError, MystackApi} from "./api.js";
import {EmrConsole} from "./emr.js";
import {GlueExplorer} from "./glue.js";

const refreshInterval = Number(
  document.querySelector('meta[name="mystack-refresh-interval-ms"]').content,
);
const state = {component: "emr", busy: false, queuedRefresh: null, resources: null};
const api = new MystackApi(() => byId("token").value);

const emr = new EmrConsole(api, {
  notify,
  afterMutation: async message => {
    await refresh({message});
  },
  activateTab: name => activateNamedTab("[data-emr-tab]", "data-emr-tab", name),
});
const glue = new GlueExplorer();

bootstrap();

async function bootstrap() {
  bindShell();
  setupTabs("[data-emr-tab]", "data-emr-tab");
  setupTabs("[data-glue-tab]", "data-glue-tab");
  setupTabs("[data-system-tab]", "data-system-tab");
  try {
    const components = await api.components();
    const available = new Set(components.components);
    document.querySelectorAll("[data-component]").forEach(button => {
      button.hidden = !available.has(button.dataset.component);
    });
    if (!available.has(state.component)) state.component = components.components[0] || "proxy";
    selectComponent(state.component);
  } catch (error) {
    showError(error);
  }
  window.setInterval(() => {
    if (!document.hidden && !state.busy) refresh({quiet: true});
  }, refreshInterval);
}

function bindShell() {
  document.querySelectorAll("[data-component]").forEach(button => {
    button.addEventListener("click", () => selectComponent(button.dataset.component));
  });
  byId("refresh").addEventListener("click", () => refresh());
  byId("primaryAction").addEventListener("click", () => {
    if (state.component === "emr") byId("clusterDialog").showModal();
  });
  byId("token").addEventListener("change", () => refresh());
  document.querySelectorAll("[data-close-dialog]").forEach(button => {
    button.addEventListener("click", () => byId(button.dataset.closeDialog).close());
  });
  document.querySelectorAll("dialog").forEach(dialog => {
    dialog.addEventListener("click", event => {
      if (event.target === dialog) dialog.close();
    });
  });
}

function selectComponent(component) {
  state.component = component;
  document.querySelectorAll("[data-component]").forEach(button => {
    const selected = button.dataset.component === component;
    button.classList.toggle("selected", selected);
    if (selected) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  byId("emrView").hidden = component !== "emr";
  byId("glueView").hidden = component !== "glue";
  byId("systemView").hidden = component !== "proxy";
  const content = {
    emr: {
      eyebrow: "Amazon EMR emulator",
      title: "Clusters",
      description: "Create local Spark clusters, submit Steps, and inspect their output.",
      action: "Create cluster",
    },
    glue: {
      eyebrow: "AWS Glue Data Catalog emulator",
      title: "Data Catalog",
      description: "Explore databases, tables, schemas, partition keys, and storage metadata.",
      action: null,
    },
    proxy: {
      eyebrow: "Mystack routing plane",
      title: "System diagnostics",
      description: "Inspect registered routes, Python threads, and asyncio tasks.",
      action: null,
    },
  }[component];
  byId("serviceEyebrow").textContent = content.eyebrow;
  byId("pageTitle").textContent = content.title;
  byId("pageDescription").textContent = content.description;
  byId("primaryAction").hidden = !content.action;
  if (content.action) byId("primaryAction").textContent = content.action;
  refresh();
}

async function refresh({quiet = false, message = null} = {}) {
  if (state.busy) {
    state.queuedRefresh = {quiet, message};
    return;
  }
  const component = state.component;
  state.busy = true;
  if (!quiet) notify("Refreshing…");
  try {
    const document = await api.resources(component);
    if (component !== state.component) return;
    state.resources = document;
    renderSummary(document);
    if (component === "emr") {
      emr.setDocument(document);
    } else if (component === "glue") {
      glue.setDocument(document);
    } else {
      await refreshSystem();
    }
    byId("lastUpdated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
    hideAlert();
    notify(message || "Healthy");
  } catch (error) {
    if (component === state.component) showError(error);
  } finally {
    state.busy = false;
    const queued = state.queuedRefresh;
    state.queuedRefresh = null;
    if (queued || component !== state.component) {
      window.queueMicrotask(() => refresh(queued || {quiet: true}));
    }
  }
}

async function refreshSystem() {
  const [routes, threads, tasks] = await Promise.all([
    api.routes(),
    api.diagnostics("proxy", "threads"),
    api.diagnostics("proxy", "tasks"),
  ]);
  byId("routes").textContent = JSON.stringify(routes, null, 2);
  byId("threads").textContent = JSON.stringify(threads, null, 2);
  byId("tasks").textContent = JSON.stringify(tasks, null, 2);
}

function renderSummary(document) {
  byId("modeValue").textContent = document.emulator?.mode || "Router";
  const compatibility = document.compatibility || {};
  byId("compatibilityValue").textContent =
    compatibility.implemented_operation_count === undefined
      ? compatibility.classification || "ROUTER"
      : `${compatibility.classification} · ${compatibility.implemented_operation_count}/${compatibility.model_operation_count}`;
  byId("notice").textContent = document.emulator?.notice || "";
  const counts = document.counts || {};
  if (state.component === "emr") {
    metric("Clusters", counts.clusters || 0, "Steps", counts.steps || 0);
  } else if (state.component === "glue") {
    metric("Databases", counts.databases || 0, "Tables / partitions", `${counts.tables || 0} / ${counts.partitions || 0}`);
  } else {
    metric("Routes", counts.routes || 0, "Configuration", document.emulator?.config_fingerprint?.slice(0, 10) || "—");
  }
}

function metric(oneLabel, oneValue, twoLabel, twoValue) {
  byId("metricOneLabel").textContent = oneLabel;
  byId("metricOneValue").textContent = String(oneValue);
  byId("metricTwoLabel").textContent = twoLabel;
  byId("metricTwoValue").textContent = String(twoValue);
}

function notify(message, error = false) {
  byId("status").textContent = message;
  byId("healthDot").className = `health-dot ${error ? "bad" : "ok"}`;
  if (error) {
    byId("alert").textContent = message;
    byId("alert").hidden = false;
  }
}

function showError(error) {
  const message = error instanceof ApiError ? error.display() : String(error);
  notify(message, true);
}

function hideAlert() {
  byId("alert").hidden = true;
  byId("alert").textContent = "";
}

function setupTabs(selector, attribute) {
  const tabs = [...document.querySelectorAll(selector)];
  for (const [index, tab] of tabs.entries()) {
    tab.addEventListener("click", () => activateTab(tabs, tab, attribute, false));
    tab.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const target = event.key === "Home"
        ? 0
        : event.key === "End"
          ? tabs.length - 1
          : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
      activateTab(tabs, tabs[target], attribute, true);
    });
  }
}

function activateNamedTab(selector, attribute, name) {
  const tabs = [...document.querySelectorAll(selector)];
  const tab = tabs.find(value => value.getAttribute(attribute) === name);
  if (tab) activateTab(tabs, tab, attribute, false);
}

function activateTab(tabs, selected, attribute, focus) {
  for (const tab of tabs) {
    const active = tab === selected;
    tab.setAttribute("aria-selected", String(active));
    tab.tabIndex = active ? 0 : -1;
    byId(tab.getAttribute("aria-controls")).hidden = !active;
  }
  if (focus) selected.focus();
  if (selected.getAttribute(attribute) === "logs") emr.refreshLogs();
}

function byId(id) {
  return document.getElementById(id);
}
