"""Browser-driven resource console and accessibility contracts.

References:
- https://playwright.dev/python/docs/accessibility-testing
- https://www.w3.org/WAI/ARIA/apg/patterns/tabs/
- https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-manage-view-web-log-files.html
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright


@pytest.mark.e2e
@pytest.mark.browser
def test_console_resource_navigation_and_accessibility(
    aws_clients: dict[str, Any],
    e2e_settings: Any,
) -> None:
    emr = aws_clients["emr"]
    s3 = aws_clients["s3"]
    bucket = f"mystack-console-{uuid.uuid4().hex}"
    s3.create_bucket(Bucket=bucket)
    cluster_id = emr.run_job_flow(
        Name="console-log-cluster",
        LogUri=f"s3://{bucket}/logs/",
        Instances={"InstanceCount": 1, "KeepJobFlowAliveWhenNoSteps": True},
    )["JobFlowId"]
    _wait_for_state(
        lambda: emr.describe_cluster(ClusterId=cluster_id)["Cluster"]["Status"]["State"],
        {"WAITING"},
        e2e_settings,
    )
    step_id = emr.add_job_flow_steps(
        JobFlowId=cluster_id,
        Steps=[
            {
                "Name": "console-log-step",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": ["spark-submit", f"s3://{bucket}/missing.py"],
                },
            }
        ],
    )["StepIds"][0]
    _wait_for_state(
        lambda: emr.describe_step(ClusterId=cluster_id, StepId=step_id)["Step"]["Status"]["State"],
        {"FAILED"},
        e2e_settings,
    )

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
            pytest.skip("Chromium is not installed; run `uv run playwright install chromium`")
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
            expect(
                page.get_by_role("heading", name="Service resources", exact=True)
            ).to_be_visible()
            expect(page.get_by_role("status")).to_have_attribute("aria-live", "polite")
            component = page.get_by_role("combobox", name="Component", exact=True)
            expect(component).to_be_visible()
            expect(page.get_by_role("textbox", name="Management token", exact=True)).to_be_visible()

            component.select_option("emr")
            expect(page.get_by_role("status")).to_have_text("Healthy")
            page.get_by_role("button", name="Step console-log-step").click()
            page.get_by_role("tab", name="Logs").click()
            expect(page.get_by_role("heading", name="S3 LogUri publication")).to_be_visible()
            expect(page.locator("#logPublicationDetail")).to_contain_text('"status": "published"')
            expect(page.locator("#logPublicationDetail")).to_contain_text("controller.gz")
            page.get_by_role("tab", name="Resources").click()

            component.select_option("glue")
            expect(page.get_by_role("status")).to_have_text("Healthy")
            expect(page.get_by_text("Glue Data Catalog", exact=True)).to_be_visible()
            database = page.get_by_role("button", name="Database default")
            expect(database).to_be_visible()
            database.click()
            expect(page.locator("#resourceDetail")).to_contain_text('"name": "default"')

            resources_tab = page.get_by_role("tab", name="Resources")
            resources_tab.focus()
            resources_tab.press("ArrowRight")
            expect(page.get_by_role("tab", name="Logs")).to_have_attribute("aria-selected", "true")
            page.get_by_role("tab", name="Thread stacks").click()
            expect(page.locator("#threads")).to_contain_text('"thread_count"')

            for control in page.get_by_role("button").all():
                assert control.get_attribute("aria-label") or control.inner_text().strip()
            assert not browser_errors
            page.get_by_role("tab", name="Resources").click()
            e2e_settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=e2e_settings.artifacts_dir / "mystack-console.png",
                full_page=True,
            )
        finally:
            browser.close()


def _wait_for_state(read_state: Callable[[], str], expected: set[str], settings: Any) -> str:
    deadline = time.monotonic() + settings.timeout_seconds
    while time.monotonic() < deadline:
        state = read_state()
        if state in expected:
            return state
        time.sleep(settings.poll_interval_seconds)
    raise TimeoutError(f"Resource did not enter {sorted(expected)}")
