"""File-mapped EMR policy values with no YAML dependency.

Release version source:
https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-release-app-versions-7.x.html
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReleaseProfile:
    release_label: str
    runtime_profile: str
    aws_spark_version: str
    source: str


@dataclass(frozen=True, slots=True)
class EmrPolicy:
    api_page_size: int
    max_active_steps: int
    default_release_label: str
    release_profiles: dict[str, ReleaseProfile]
