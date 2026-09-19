from cc_cost.config import Config, ProjectGroup
from cc_cost.grouping import group_projects
from cc_cost.scanner import ProjectKey


def _config(project_groups: list[ProjectGroup]) -> Config:
    return Config(
        usd_to_jpy=150.0,
        project_groups=project_groups,
        models={},
        roots=[],
        web_search_price_per_1k_requests=None,
    )


def test_group_projects_sums_web_search_requests_across_merged_projects() -> None:
    import re

    config = _config([ProjectGroup(pattern=re.compile("^proj-"), name="merged")])
    usage_by_project = {
        ProjectKey(dir_name="proj-a"): {},
        ProjectKey(dir_name="proj-b"): {},
    }
    web_search_by_project = {
        ProjectKey(dir_name="proj-a"): {"today": 3},
        ProjectKey(dir_name="proj-b"): {"today": 2},
    }

    grouped = group_projects(usage_by_project, web_search_by_project, config)

    ((group_name, _periods_usage, periods_web_search),) = grouped
    assert group_name == "merged"
    assert periods_web_search["today"] == 5
