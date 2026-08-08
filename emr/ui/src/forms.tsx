/** Official RunJobFlow/AddJobFlowSteps shapes: https://docs.aws.amazon.com/emr/latest/APIReference/API_RunJobFlow.html */
import {Button, Checkbox, Dialog, Input, lines, pairs, Select, Textarea} from "@mystack/ui";
import type {FormEvent} from "react";

export function CreateClusterDialog({open, releaseProfiles, defaultRelease, onClose, onSubmit}: {open: boolean; releaseProfiles: Record<string, {aws_spark_version: string}>; defaultRelease: string; onClose: () => void; onSubmit: (payload: unknown) => Promise<void>}) {
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") || "").trim();
    const release = String(form.get("releaseLabel") || "").trim();
    if (!name || !release) return;
    const payload: Record<string, unknown> = {
      Name: name,
      ReleaseLabel: release,
      Instances: {
        KeepJobFlowAliveWhenNoSteps: form.has("keepAlive"),
        TerminationProtected: form.has("terminationProtected"),
      },
      Applications: [{Name: "Spark"}],
      StepConcurrencyLevel: Number(form.get("stepConcurrency")),
    };
    const optional = (name: string) => String(form.get(name) || "").trim();
    if (optional("logUri")) payload.LogUri = optional("logUri");
    if (optional("bootstrapPath")) payload.BootstrapActions = [{Name: "Console bootstrap", ScriptBootstrapAction: {Path: optional("bootstrapPath"), Args: lines(form.get("bootstrapArgs"))}}];
    const tags = pairs(form.get("tags"), "Tags");
    if (tags.length) payload.Tags = tags.map(([Key, Value]) => ({Key, Value}));
    await onSubmit(payload);
  };
  return <Dialog open={open} title="Create cluster" eyebrow="Amazon EMR compatible" onClose={onClose} actions={<><Button type="button" onClick={onClose}>Cancel</Button><Button variant="primary" type="submit" form="create-cluster-form">Create cluster</Button></>}>
    <form id="create-cluster-form" onSubmit={event => void submit(event)} className="grid gap-4 sm:grid-cols-2">
      <Input label="Cluster name *" name="name" required maxLength={256} autoComplete="off" />
      <Select label="Release label" name="releaseLabel" required defaultValue={defaultRelease}>{Object.entries(releaseProfiles).map(([label, profile]) => <option key={label} value={label}>{label} · Spark {profile.aws_spark_version}</option>)}</Select>
      <Input label="Step concurrency" name="stepConcurrency" type="number" min={1} defaultValue={1} required />
      <Input label="S3 LogUri" name="logUri" placeholder="s3://existing-bucket/logs/" />
      <Checkbox label="Keep cluster alive when no Steps remain" name="keepAlive" defaultChecked />
      <Checkbox label="Enable termination protection" name="terminationProtected" />
      <Input label="Bootstrap script S3 URI" name="bootstrapPath" placeholder="s3://bucket/bootstrap.sh" className="sm:col-span-2" />
      <Textarea label="Bootstrap arguments" hint="One argument per line" name="bootstrapArgs" rows={3} className="sm:col-span-2" />
      <Textarea label="Tags" hint="One key=value pair per line" name="tags" rows={3} className="sm:col-span-2" />
    </form>
  </Dialog>;
}

export function AddStepDialog({open, commandAliases, onClose, onSubmit}: {open: boolean; commandAliases: string[]; onClose: () => void; onSubmit: (payload: {name: string; action: string; hadoop: Record<string, unknown>}) => Promise<void>}) {
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get("name") || "").trim();
    const command = lines(form.get("command"));
    const control = event.currentTarget.elements.namedItem("command") as HTMLTextAreaElement;
    const validation = command.length < 2
      ? "Provide a command and an application resource as separate lines."
      : !commandAliases.includes(command[0])
        ? `Supported first command: ${commandAliases.join(", ")}`
        : "";
    control.setCustomValidity(validation);
    if (validation) { control.reportValidity(); return; }
    if (!name) return;
    const hadoop: Record<string, unknown> = {Jar: "command-runner.jar", Args: command};
    await onSubmit({name, action: String(form.get("actionOnFailure") || "CONTINUE"), hadoop});
  };
  return <Dialog open={open} title="Add Step" eyebrow="Spark 3.5 Step" onClose={onClose} actions={<><Button type="button" onClick={onClose}>Cancel</Button><Button variant="primary" type="submit" form="add-step-form">Add Step</Button></>}>
    <form id="add-step-form" onSubmit={event => void submit(event)} className="grid gap-4 sm:grid-cols-2">
      <Input label="Step name *" name="name" required maxLength={256} className="sm:col-span-2" />
      <Select label="Action on failure" name="actionOnFailure" defaultValue="CONTINUE"><option>CONTINUE</option><option>CANCEL_AND_WAIT</option><option>TERMINATE_CLUSTER</option></Select>
      <Textarea label="Full command argument vector *" hint="One argument per line. Use spark-submit with an s3://...py application for PySpark; the interactive pyspark shell is not an EMR Step." name="command" rows={10} required defaultValue={`${commandAliases[0] || "spark-submit"}\n`} onInput={event => event.currentTarget.setCustomValidity("")} className="sm:col-span-2" />
    </form>
  </Dialog>;
}
