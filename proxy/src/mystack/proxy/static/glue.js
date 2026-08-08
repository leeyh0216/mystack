/*
 * Glue Data Catalog resource model and type strings:
 * https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
 * https://docs.aws.amazon.com/glue/latest/dg/glue-types.html
 */

export class GlueExplorer {
  constructor() {
    this.document = null;
    this.databaseName = null;
    this.tableId = null;
    this.databaseQuery = "";
    this.tableQuery = "";
    this.partitionQuery = "";
    this._bind();
  }

  _bind() {
    bindSearch("databaseSearch", value => {
      this.databaseQuery = value;
      this._renderDatabases();
    });
    bindSearch("tableSearch", value => {
      this.tableQuery = value;
      this._renderTables();
    });
    bindSearch("partitionSearch", value => {
      this.partitionQuery = value;
      this._renderPartitions();
    });
  }

  setDocument(document) {
    this.document = document;
    if (this.databaseName && !this.databases.some(database => database.name === this.databaseName)) {
      this.databaseName = null;
      this.tableId = null;
    }
    if (!this.databaseName && this.databases.length) this.databaseName = this.databases[0].name;
    if (this.tableId && !this.selectedDatabase?.tables.some(table => table.id === this.tableId)) {
      this.tableId = null;
    }
    this._renderDatabases();
    this._renderTables();
    this._renderDetail();
  }

  get databases() {
    return this.document?.resources?.databases || [];
  }

  get selectedDatabase() {
    return this.databases.find(database => database.name === this.databaseName) || null;
  }

  get selectedTable() {
    return this.selectedDatabase?.tables.find(table => table.id === this.tableId) || null;
  }

  _renderDatabases() {
    const root = byId("databaseList");
    root.replaceChildren();
    byId("databaseCount").textContent = String(this.databases.length);
    const values = this.databases.filter(database =>
      `${database.name} ${database.description || ""} ${database.location_uri || ""}`
        .toLowerCase().includes(this.databaseQuery)
    );
    if (!values.length) {
      root.append(emptyList(this.databases.length ? "No matching databases" : "No databases"));
      return;
    }
    for (const database of values) {
      const button = resourceButton({
        title: database.name,
        subtitle: `${database.tables.length} tables`,
        selected: database.name === this.databaseName,
        label: `Database ${database.name}`,
      });
      button.addEventListener("click", () => {
        this.databaseName = database.name;
        this.tableId = null;
        this._renderDatabases();
        this._renderTables();
        this._renderDetail();
      });
      root.append(button);
    }
  }

  _renderTables() {
    const root = byId("tableList");
    root.replaceChildren();
    const database = this.selectedDatabase;
    byId("selectedDatabaseLabel").textContent = database ? database.name : "Select database";
    byId("tableCount").textContent = String(database?.tables.length || 0);
    if (!database) {
      root.append(emptyList("Select a database"));
      return;
    }
    const values = database.tables.filter(table =>
      `${table.name} ${table.table_type || ""} ${table.location || ""}`
        .toLowerCase().includes(this.tableQuery)
    );
    if (!values.length) {
      root.append(emptyList(database.tables.length ? "No matching tables" : "No tables"));
      return;
    }
    for (const table of values) {
      const button = resourceButton({
        title: table.name,
        subtitle: `${table.table_type || "TABLE"} · ${table.columns.length} columns`,
        selected: table.id === this.tableId,
        label: `Table ${table.name}`,
      });
      button.addEventListener("click", () => {
        this.tableId = table.id;
        this._renderTables();
        this._renderDetail();
      });
      root.append(button);
    }
  }

  _renderDetail() {
    const database = this.selectedDatabase;
    const table = this.selectedTable;
    byId("glueEmpty").hidden = Boolean(table);
    byId("glueDetail").hidden = !table;
    if (!table) return;
    byId("tableDatabase").textContent = database.name;
    byId("tableDetailHeading").textContent = table.name;
    byId("tableIdentity").textContent = table.id;
    byId("tableType").textContent = table.table_type || "TABLE";
    facts(byId("tableFacts"), [
      ["Location", table.location || "Not configured"],
      ["Version", table.version_id],
      ["Columns", table.columns.length],
      ["Partitions", table.partitions.length],
      ["Archived versions", table.archived_version_count],
      ["Created", formatTime(table.created_at)],
      ["Updated", formatTime(table.updated_at)],
      ["Classification", table.parameters?.classification || "—"],
    ]);
    this._renderColumns();
    this._renderPartitionKeys();
    this._renderPartitions();
    keyValues(byId("parameterList"), table.parameters || {}, "No table parameters");
    byId("glueRaw").textContent = JSON.stringify({
      database: {
        name: database.name,
        description: database.description,
        location_uri: database.location_uri,
        parameters: database.parameters,
      },
      table,
    }, null, 2);
  }

  _renderColumns() {
    const root = byId("columnRows");
    root.replaceChildren();
    const columns = this.selectedTable?.columns || [];
    if (!columns.length) {
      root.append(node("tr", {}, node("td", {text: "No columns", colSpan: "4"})));
      return;
    }
    columns.forEach((column, index) => {
      root.append(node("tr", {},
        node("td", {text: index + 1}),
        node("td", {}, node("strong", {text: column.Name || ""})),
        node("td", {className: "mono", text: column.Type || ""}),
        node("td", {className: "column-comment", text: column.Comment || "—"}),
      ));
    });
  }

  _renderPartitionKeys() {
    const root = byId("partitionKeyList");
    root.replaceChildren();
    const keys = this.selectedTable?.partition_keys || [];
    if (!keys.length) {
      root.append(node("p", {className: "muted", text: "This table is not partitioned."}));
      return;
    }
    const list = node("div", {className: "partition-keys"});
    for (const key of keys) {
      list.append(node("span", {className: "schema-chip"},
        node("b", {text: key.Name || ""}),
        document.createTextNode(` · ${key.Type || ""}`),
      ));
    }
    root.append(list);
  }

  _renderPartitions() {
    const head = byId("partitionHead");
    const body = byId("partitionRows");
    head.replaceChildren();
    body.replaceChildren();
    const table = this.selectedTable;
    if (!table) return;
    const keys = table.partition_keys || [];
    const header = node("tr");
    if (keys.length) {
      for (const key of keys) header.append(node("th", {text: key.Name || "Value"}));
    } else {
      header.append(node("th", {text: "Values"}));
    }
    header.append(node("th", {text: "Location"}), node("th", {text: "Updated"}));
    head.append(header);

    const partitions = table.partitions.filter(partition =>
      JSON.stringify(partition.values).toLowerCase().includes(this.partitionQuery)
    );
    byId("partitionSummary").textContent =
      `${table.partitions.length} partition${table.partitions.length === 1 ? "" : "s"}`;
    if (!partitions.length) {
      body.append(node("tr", {}, node("td", {
        text: table.partitions.length ? "No matching partitions" : "No partitions",
        colSpan: String(Math.max(keys.length, 1) + 2),
      })));
      return;
    }
    for (const partition of partitions) {
      const row = node("tr");
      if (keys.length) {
        for (let index = 0; index < keys.length; index += 1) {
          row.append(node("td", {className: "mono", text: partition.values[index] ?? "—"}));
        }
      } else {
        row.append(node("td", {className: "mono", text: partition.values.join("/") || "—"}));
      }
      row.append(
        node("td", {className: "mono", text: partition.definition?.StorageDescriptor?.Location || "—"}),
        node("td", {text: formatTime(partition.updated_at)}),
      );
      body.append(row);
    }
  }
}

function bindSearch(id, callback) {
  byId(id).addEventListener("input", event => callback(event.target.value.toLowerCase()));
}

function byId(id) {
  return document.getElementById(id);
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

function resourceButton({title, subtitle, selected, label}) {
  return node("button", {
    className: `resource-item${selected ? " selected" : ""}`,
    type: "button",
    ariaLabel: label,
  }, node("span", {}, node("strong", {text: title}), node("small", {text: subtitle})));
}

function emptyList(message) {
  return node("div", {className: "empty-list", text: message});
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
    list.append(node("div", {}, node("dt", {text: key}), node("dd", {className: "mono", text: String(value)})));
  }
  root.append(list);
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleString();
}
