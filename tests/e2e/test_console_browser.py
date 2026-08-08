"""Browser-driven service Console, AWS-operation, and accessibility contracts.

References:
- https://playwright.dev/python/docs/accessibility-testing
- https://www.w3.org/WAI/ARIA/apg/patterns/tabs/
- https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- https://docs.aws.amazon.com/emr/latest/APIReference/Welcome.html
- https://docs.aws.amazon.com/glue/latest/dg/aws-glue-api-catalog.html
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright


@pytest.mark.e2e
@pytest.mark.browser
def test_console_service_workflows_and_accessibility(
    aws_clients: dict[str, Any],
    e2e_settings: Any,
) -> None:
    glue = aws_clients["glue"]
    s3 = aws_clients["s3"]
    suffix = uuid.uuid4().hex
    bucket = f"mystack-console-{suffix}"
    table_name = f"console_events_{suffix}"
    s3.create_bucket(Bucket=bucket)
    s3.upload_file(
        str(Path(__file__).parent / "assets" / "console_long_step.py"),
        bucket,
        "jobs/console_long_step.py",
    )
    _create_glue_fixture(glue, bucket, table_name)

    required = os.getenv(e2e_settings.browser_required_environment_variable, "").lower() in {
        "1",
        "true",
        "yes",
    }
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except PlaywrightError:
            if required:
                raise
            pytest.skip("Chromium is not installed; install it with Playwright")
        page = browser.new_page()
        page.set_default_timeout(e2e_settings.browser_action_timeout_seconds * 1000)
        browser_errors: list[str] = []
        page.on(
            "console",
            lambda message: browser_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        try:
            page.goto(f"{e2e_settings.endpoint_url}/_mystack/console", wait_until="networkidle")
            _assert_shell(page)
            cluster_name = f"console-created-{suffix}"
            _create_cluster_in_console(page, cluster_name, bucket)
            cluster = page.get_by_role("button", name=f"Cluster {cluster_name}")
            expect(cluster).to_be_visible(timeout=e2e_settings.timeout_seconds * 1000)
            cluster.click()
            expect(page.get_by_role("heading", name=cluster_name, exact=True)).to_be_visible()
            expect(page.get_by_text("emr-7.8.0", exact=True)).to_be_visible()
            expect(page.get_by_text(f"s3://{bucket}/logs/", exact=True)).to_be_visible()

            add_step = page.get_by_role("button", name="Add Step", exact=True)
            expect(add_step).to_be_enabled(timeout=e2e_settings.timeout_seconds * 1000)
            _add_step_in_console(page, bucket)
            steps_tab = page.get_by_role("tab", name="Steps", exact=True)
            expect(steps_tab).to_have_attribute("aria-selected", "true")
            row = page.get_by_role("row", name="Step console-long-step")
            expect(row).to_be_visible(timeout=e2e_settings.timeout_seconds * 1000)
            expect(row).to_contain_text("RUNNING", timeout=e2e_settings.timeout_seconds * 1000)
            row.click()
            expect(page.get_by_role("tab", name="Logs", exact=True)).to_have_attribute(
                "aria-selected", "true"
            )
            expect(page.get_by_role("heading", name="S3 LogUri publication")).to_be_visible()
            expect(page.locator("#logPublication")).to_contain_text("pending")
            page.get_by_role("button", name="Cancel Step", exact=True).click()
            expect(page.locator("#logStepIdentity")).to_contain_text(
                "CANCELLED",
                timeout=e2e_settings.timeout_seconds * 1000,
            )
            expect(page.locator("#logPublication")).to_contain_text(
                "published",
                timeout=e2e_settings.timeout_seconds * 1000,
            )

            page.once("dialog", lambda dialog: dialog.accept())
            page.get_by_role("button", name="Terminate", exact=True).click()
            expect(page.get_by_text("TERMINATED", exact=True).first).to_be_visible(
                timeout=e2e_settings.timeout_seconds * 1000
            )

            _assert_glue_explorer(page, table_name)
            _assert_system_diagnostics(page)
            _assert_keyboard_contract(page)
            for control in page.get_by_role("button").all():
                assert control.get_attribute("aria-label") or control.inner_text().strip()
            assert not browser_errors
            e2e_settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(
                path=e2e_settings.artifacts_dir / "mystack-console.png",
                full_page=True,
            )
        finally:
            browser.close()


def _assert_shell(page: Page) -> None:
    expect(page.get_by_role("heading", name="Clusters", exact=True, level=1)).to_be_visible()
    expect(page.get_by_role("status")).to_have_attribute("aria-live", "polite")
    expect(page.get_by_role("textbox", name="Management token", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="EMR Clusters & Steps")).to_have_attribute(
        "aria-current", "page"
    )


def _create_cluster_in_console(page: Page, name: str, bucket: str) -> None:
    page.get_by_role("button", name="Create cluster", exact=True).click()
    dialog = page.get_by_role("dialog", name="Create cluster")
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label("Release label")).to_have_value("emr-7.8.0")
    dialog.get_by_label("Cluster name *").fill(name)
    dialog.get_by_label("S3 LogUri").fill(f"s3://{bucket}/logs/")
    dialog.get_by_label("Tags").fill("created-by=console-e2e")
    dialog.get_by_role("button", name="Create cluster", exact=True).click()
    expect(dialog).to_be_hidden()


def _add_step_in_console(page: Page, bucket: str) -> None:
    page.get_by_role("button", name="Add Step", exact=True).click()
    dialog = page.get_by_role("dialog", name="Add Step")
    dialog.get_by_label("Step name *").fill("console-long-step")
    dialog.get_by_label("Application resource *").fill(f"s3://{bucket}/jobs/console_long_step.py")
    dialog.get_by_label("Application arguments").fill("--sleep-seconds\n120")
    dialog.get_by_role("button", name="Add Step", exact=True).click()
    expect(dialog).to_be_hidden()


def _assert_glue_explorer(page: Page, table_name: str) -> None:
    page.get_by_role("button", name="Glue Data Catalog").click()
    expect(page.get_by_role("heading", name="Data Catalog", exact=True)).to_be_visible()
    database = page.get_by_role("button", name="Database default")
    expect(database).to_be_visible()
    database.click()
    table = page.get_by_role("button", name=f"Table {table_name}")
    expect(table).to_be_visible()
    table.click()
    expect(page.get_by_role("heading", name=table_name, exact=True)).to_be_visible()
    expect(page.locator("#columnRows")).to_contain_text("event_id")
    expect(page.locator("#columnRows")).to_contain_text("bigint")
    expect(page.locator("#partitionKeyList")).to_contain_text("event_day")
    page.get_by_role("tab", name="Partitions", exact=True).click()
    expect(page.locator("#partitionRows")).to_contain_text("2026-08-08")
    expect(page.locator("#partitionRows")).to_contain_text("s3://")


def _assert_system_diagnostics(page: Page) -> None:
    page.get_by_role("button", name="System Routes & diagnostics").click()
    expect(page.get_by_role("heading", name="System diagnostics", exact=True)).to_be_visible()
    expect(page.locator("#routes")).to_contain_text('"name": "emr"')
    page.get_by_role("tab", name="Thread stacks").click()
    expect(page.locator("#threads")).to_contain_text('"thread_count"')
    page.get_by_role("tab", name="Asyncio tasks").click()
    expect(page.locator("#tasks")).to_contain_text('"task_count"')


def _assert_keyboard_contract(page: Page) -> None:
    page.get_by_role("button", name="Glue Data Catalog").click()
    schema = page.get_by_role("tab", name="Schema", exact=True)
    schema.focus()
    schema.press("ArrowRight")
    expect(page.get_by_role("tab", name="Partitions", exact=True)).to_have_attribute(
        "aria-selected", "true"
    )


def _create_glue_fixture(glue: Any, bucket: str, table_name: str) -> None:
    glue.create_table(
        DatabaseName="default",
        TableInput={
            "Name": table_name,
            "Description": "Console exploration fixture",
            "TableType": "EXTERNAL_TABLE",
            "Parameters": {"classification": "parquet", "fixture": "console-e2e"},
            "PartitionKeys": [{"Name": "event_day", "Type": "string", "Comment": "Partition date"}],
            "StorageDescriptor": {
                "Columns": [
                    {"Name": "event_id", "Type": "bigint", "Comment": "Event identifier"},
                    {"Name": "payload", "Type": "struct<name:string,count:int>"},
                ],
                "Location": f"s3://{bucket}/catalog/{table_name}/",
                "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                "OutputFormat": ("org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"),
                "SerdeInfo": {
                    "SerializationLibrary": (
                        "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
                    )
                },
            },
        },
    )
    glue.create_partition(
        DatabaseName="default",
        TableName=table_name,
        PartitionInput={
            "Values": ["2026-08-08"],
            "StorageDescriptor": {
                "Columns": [
                    {"Name": "event_id", "Type": "bigint"},
                    {"Name": "payload", "Type": "struct<name:string,count:int>"},
                ],
                "Location": f"s3://{bucket}/catalog/{table_name}/event_day=2026-08-08/",
            },
        },
    )
