import json
import logging
import os
from collections import OrderedDict
from datetime import datetime
from urllib.parse import urlparse

import numpy as np
import pypistats
import requests
from addict import Dict
from dateutil.parser import parse
from pybraries.search import Search
from tqdm import tqdm

from best_of import utils
from best_of.license import get_license

log = logging.getLogger(__name__)

MIN_PROJECT_DESC_LENGTH = 10
DEFAULT_OTHERS_CATEGORY_ID = "others"


def update_package_via_libio(project_info: Dict, package_info: Dict):
    if not project_info or not package_info:
        return

    if not project_info.homepage:
        if package_info.homepage and package_info.homepage.lower() != "unknown":
            project_info.homepage = package_info.homepage
        elif package_info.repository_url and package_info.repository_url.lower() != "unknown":
            project_info.homepage = package_info.repository_url
        elif package_info.package_manager_url and package_info.package_manager_url.lower() != "unknown":
            project_info.homepage = package_info.package_manager_url

    if not project_info.name and package_info.name:
        project_info.name = package_info.name

    if not project_info.github_id and package_info.repository_url:
        if "github" in package_info.repository_url and urlparse(package_info.repository_url).path:
            project_info.github_id = urlparse(
                package_info.repository_url).path.strip("/")
            project_info.github_url = package_info.repository_url

    if not project_info.license and package_info.normalized_licenses:
        if len(package_info.normalized_licenses) > 1:
            log.info("Package " + package_info.name +
                     "has more than one license.")
        # Always take the first license
        project_info.license = package_info.normalized_licenses[0]
        if project_info.license.lower() == "other":
            # if licenses is other, set to None
            project_info.license = None

    if package_info.latest_release_published_at:
        try:
            updated_at = parse(str(package_info.latest_release_published_at))
            if not project_info.updated_at:
                project_info.updated_at = updated_at
            elif project_info.updated_at < updated_at:
                # always use the latest available date
                project_info.updated_at = updated_at
        except Exception as ex:
            log.warning("Failed to parse timestamp: " +
                        str(package_info.latest_release_published_at), exc_info=ex)

    if package_info.versions and len(package_info.versions) > 0:
        try:
            updated_at = parse(str(package_info.versions[0].published_at))
            if not project_info.updated_at:
                project_info.updated_at = updated_at
            elif project_info.updated_at < updated_at:
                # always use the latest available date
                project_info.updated_at = updated_at
        except Exception as ex:
            log.warning("Failed to parse timestamp: " +
                        str(package_info.versions[0].published_at), exc_info=ex)

    if package_info.stars:
        star_count = int(package_info.stars)
        if not project_info.star_count:
            project_info.star_count = star_count
        elif int(project_info.star_count) < star_count:
            # always use the highest number
            project_info.star_count = star_count

    if package_info.forks:
        fork_count = int(package_info.forks)
        if not project_info.fork_count:
            project_info.fork_count = fork_count
        elif int(project_info.fork_count) < fork_count:
            # always use the highest number
            project_info.fork_count = fork_count

    if package_info.rank:
        sourcerank = int(package_info.rank)
        if not project_info.sourcerank:
            project_info.sourcerank = sourcerank
        elif int(project_info.sourcerank) < sourcerank:
            # always use the highest number
            project_info.sourcerank = sourcerank

    if (not project_info.description or len(project_info.description) < MIN_PROJECT_DESC_LENGTH) and package_info.description:
        description = utils.process_description(package_info.description)
        if description:
            project_info.description = description


def update_via_conda(project_info: Dict):
    if not project_info.conda_id:
        return

    search = Search()
    conda_info = search.project(manager="conda", package=project_info.conda_id)

    if not conda_info:
        return

    conda_info = Dict(conda_info)

    if not project_info.conda_url:
        project_info.conda_url = "https://anaconda.org/anaconda/" + project_info.conda_id

    update_package_via_libio(project_info, conda_info)


def update_via_npm(project_info: Dict):
    if not project_info.npm_id:
        return

    search = Search()
    npm_info = search.project(manager="npm", package=project_info.npm_id)

    if not npm_info:
        log.info("Unable to find npm package: " + project_info.npm_id)
        return

    npm_info = Dict(npm_info)

    if not project_info.npm_url:
        project_info.npm_url = "https://www.npmjs.com/package/" + project_info.npm_id

    update_package_via_libio(project_info, npm_info)


def update_via_dockerhub(project_info: Dict):
    if not project_info.dockerhub_id:
        return

    if not project_info.dockerhub_url:
        project_info.dockerhub_url = "https://hub.docker.com/r/" + project_info.dockerhub_id

    try:
        request = requests.get(
            'https://hub.docker.com/v2/repositories/' + project_info.dockerhub_id)
        if request.status_code != 200:
            log.info("Unable to find image via dockerhub api: " +
                     project_info.dockerhub_id + "(" + str(request.status_code) + ")")
            return
        dockerhub_info = Dict(request.json())
    except Exception as ex:
        log.info("Failed to request docker iamge via dockerhub api: " +
                 project_info.dockerhub_id, exc_info=ex)
        return

    if dockerhub_info.last_updated:
        try:
            updated_at = parse(str(dockerhub_info.last_updated))
            if not project_info.updated_at:
                project_info.updated_at = updated_at
            elif project_info.updated_at < updated_at:
                # always use the latest available date
                project_info.updated_at = updated_at
        except Exception as ex:
            log.warning("Failed to parse timestamp: " +
                        str(project_info.last_updated), exc_info=ex)

    if dockerhub_info.star_count:
        project_info.dockerhub_stars = dockerhub_info.star_count

    if dockerhub_info.pull_count:
        project_info.dockerhub_pulls = dockerhub_info.pull_count

    if (not project_info.description or len(project_info.description) < MIN_PROJECT_DESC_LENGTH) and dockerhub_info.description:
        description = utils.process_description(dockerhub_info.description)
        if description:
            project_info.description = description


def update_via_pypi(project_info: Dict):
    if not project_info.pypi_id:
        return

    search = Search()
    pypi_info = search.project(manager="pypi", package=project_info.pypi_id)

    if not pypi_info:
        log.info("Unable to find pypi package: " + project_info.pypi_id)
        return

    pypi_info = Dict(pypi_info)

    if not project_info.pypi_url:
        project_info.pypi_url = "https://pypi.org/project/" + project_info.pypi_id

    update_package_via_libio(project_info, pypi_info)

    try:
        # get download count from pypi stats
        project_info.pypi_monthly_downloads = json.loads(
            pypistats.recent(project_info.pypi_id, "month", format="json")
        )["data"]["last_month"]
    except Exception:
        pass


def update_via_github_api(project_info: Dict):
    if not project_info.github_id:
        return

    github_api_token = os.getenv("GITHUB_API_KEY")
    if not github_api_token:
        return

    if '/' not in project_info.github_id:
        log.info("The github project id is not valid: " +
                 project_info.github_id)
        return

    owner = project_info.github_id.split('/')[0]
    repo = project_info.github_id.split('/')[1]

    # GraphQL query
    query = """
query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    name
    description
    url
    homepageUrl
    createdAt
    updatedAt
    pushedAt
    diskUsage
    primaryLanguage {
      name
    }
    licenseInfo {
      spdxId
    }
    stargazers {
      totalCount
    }
    pullRequests {
      totalCount
    }
    forks {
      totalCount
    }
    watchers {
      totalCount 
    }
    repositoryTopics(first: 100) {
      nodes {
        topic {
          name
        }
      }
    }
    issues(states: [OPEN]) {
      totalCount
    }
  }
}
"""

    headers = {"Authorization": "token " + github_api_token}
    variables = {
        "owner": owner,
        "repo": repo
    }

    try:
        request = requests.post('https://api.github.com/graphql',
                                json={'query': query, 'variables': variables}, headers=headers)
        if request.status_code != 200:
            log.info("Unable to find github repo via github api: " +
                     project_info.github_id + "(" + str(request.status_code) + ")")
            return
        github_info = Dict(request.json()["data"]["repository"])
    except Exception as ex:
        log.info("Failed to request github repo via github api: " +
                 project_info.github_id, exc_info=ex)
        return

    if not project_info.github_url and github_info.url:
        project_info.github_url = github_info.url

    if not project_info.homepage:
        project_info.homepage = project_info.github_url

    if not project_info.license and github_info.licenseInfo and github_info.licenseInfo.spdxId:
        # if licenses is noassertion, then it is not provided
        if github_info.licenseInfo.spdxId.lower() != "noassertion":
            project_info.license = github_info.licenseInfo.spdxId

    if github_info.createdAt:
        try:
            created_at = parse(str(github_info.createdAt))
            if not project_info.created_at:
                project_info.created_at = created_at
            elif project_info.created_at > created_at:
                # always use the oldest available date
                project_info.created_at = created_at
        except Exception as ex:
            log.warning("Failed to parse timestamp: " +
                        str(github_info.createdAt), exc_info=ex)
    # pushed_at is the last github push, updated_at is the last sync?
    if github_info.pushedAt:
        try:
            updated_at = parse(str(github_info.pushedAt))
            if not project_info.updated_at:
                project_info.updated_at = updated_at
            elif project_info.updated_at < updated_at:
                # always use the latest available date
                project_info.updated_at = updated_at
        except Exception as ex:
            log.warning("Failed to parse timestamp: " +
                        str(github_info.pushedAt), exc_info=ex)

    if github_info.forks and github_info.forks.totalCount:
        fork_count = int(github_info.forks.totalCount)
        if not project_info.fork_count:
            project_info.fork_count = fork_count
        elif int(project_info.fork_count) < fork_count:
            # always use the highest number
            project_info.fork_count = fork_count

    if github_info.issues and github_info.issues.totalCount:
        open_issue_count = int(github_info.issues.totalCount)
        if not project_info.open_issue_count:
            project_info.open_issue_count = open_issue_count
        elif int(project_info.open_issue_count) < open_issue_count:
            # always use the highest number
            project_info.open_issue_count = open_issue_count

    if github_info.stargazers and github_info.stargazers.totalCount:
        star_count = int(github_info.stargazers.totalCount)
        if not project_info.star_count:
            project_info.star_count = star_count
        elif int(project_info.star_count) < star_count:
            # always use the highest number
            project_info.star_count = star_count

    if (not project_info.description or len(project_info.description) < MIN_PROJECT_DESC_LENGTH) and github_info.description:
        description = utils.process_description(github_info.description)
        if description:
            project_info.description = description


def update_repo_via_libio(project_info: Dict):
    if not project_info.github_id:
        return

    if '/' not in project_info.github_id:
        log.info("The github project id is not valid: " +
                 project_info.github_id)
        return

    owner = project_info.github_id.split('/')[0]
    repo = project_info.github_id.split('/')[1]

    search = Search()
    github_info = search.repository(host="github", owner=owner, repo=repo)

    if not github_info:
        log.info("Unable to find github repo via libraries.io: " +
                 project_info.github_id)
        return

    github_info = Dict(github_info)

    if not project_info.github_url:
        project_info.github_url = "https://github.com/" + project_info.github_id

    if not project_info.homepage:
        project_info.homepage = project_info.github_url

    if not project_info.license and github_info.license and github_info.license.lower() != "other":
        # some unknown licenses are returned as other
        project_info.license = github_info.license

    if github_info.created_at:
        try:
            created_at = parse(str(github_info.created_at))
            if not project_info.created_at:
                project_info.created_at = created_at
            elif project_info.created_at > created_at:
                # always use the oldest available date
                project_info.created_at = created_at
        except Exception as ex:
            log.warning("Failed to parse timestamp: " +
                        str(github_info.created_at), exc_info=ex)
    # pushed_at is the last github push, updated_at is the last sync?
    if github_info.pushed_at:
        try:
            updated_at = parse(str(github_info.pushed_at))
            if not project_info.updated_at:
                project_info.updated_at = updated_at
            elif project_info.updated_at < updated_at:
                # always use the latest available date
                project_info.updated_at = updated_at
        except Exception as ex:
            log.warning("Failed to parse timestamp: " +
                        str(github_info.pushed_at), exc_info=ex)

    if github_info.rank:
        sourcerank = int(github_info.rank)
        if not project_info.sourcerank:
            project_info.sourcerank = sourcerank
        elif int(project_info.sourcerank) < sourcerank:
            # always use the highest number
            project_info.sourcerank = sourcerank

    if github_info.forks_count:
        fork_count = int(github_info.forks_count)
        if not project_info.fork_count:
            project_info.fork_count = fork_count
        elif int(project_info.fork_count) < fork_count:
            # always use the highest number
            project_info.fork_count = fork_count

    if github_info.contributions_count:
        contributor_count = int(github_info.contributions_count)
        if not project_info.contributor_count:
            project_info.contributor_count = contributor_count
        elif int(project_info.contributor_count) < contributor_count:
            # always use the highest number
            project_info.contributor_count = contributor_count

    if github_info.open_issues_count:
        open_issue_count = int(github_info.open_issues_count)
        if not project_info.open_issue_count:
            project_info.open_issue_count = open_issue_count
        elif int(project_info.open_issue_count) < open_issue_count:
            # always use the highest number
            project_info.open_issue_count = open_issue_count

    if github_info.stargazers_count:
        star_count = int(github_info.stargazers_count)
        if not project_info.star_count:
            project_info.star_count = star_count
        elif int(project_info.star_count) < star_count:
            # always use the highest number
            project_info.star_count = star_count

    if (not project_info.description or len(project_info.description) < MIN_PROJECT_DESC_LENGTH) and github_info.description:
        description = utils.process_description(github_info.description)
        if description:
            project_info.description = description


def update_via_github(project_info: Dict):
    update_via_github_api(project_info)
    update_repo_via_libio(project_info)


def calc_sourcerank_placing(projects: list):
    sourcerank_placing = {}
    # Collet all sourceranks
    for project in projects:
        project = Dict(project)
        if not project.category or not project.sourcerank:
            continue

        if project.category not in sourcerank_placing:
            sourcerank_placing[project.category] = []

        sourcerank_placing[project.category].append(int(project.sourcerank))

    # Calculate sourcerank placing
    for project in projects:
        if "sourcerank" not in project or not project["sourcerank"]:
            continue

        if "category" not in project or not project["category"]:
            continue

        category = project["category"]
        if category in sourcerank_placing:
            placing_1 = np.percentile(
                np.sort(np.array(sourcerank_placing[category]))[::-1], 90)
            placing_2 = np.percentile(
                np.sort(np.array(sourcerank_placing[category]))[::-1], 60)

            if project["sourcerank"] >= placing_1:
                project["sourcerank_placing"] = 1
            elif project["sourcerank"] >= placing_2:
                project["sourcerank_placing"] = 2
            else:
                project["sourcerank_placing"] = 3


def categorize_projects(projects: list, categories: OrderedDict):
    for project in projects:
        project = Dict(project)

        if not project.name:
            log.info("A project name is required. Ignoring project.")
            continue
        if not project.homepage:
            log.info(
                "A project homepage is required. Ignoring project: " + project.name)
            continue
        if not project.description or len(project.description) < MIN_PROJECT_DESC_LENGTH:
            # project desc should also be longer than 10 chars
            log.info("A project description is required with atleast " +
                     str(MIN_PROJECT_DESC_LENGTH) + " chars. Ignoring project: " + project.name)
            continue

        if project.show:
            if not categories[project.category].projects:
                categories[project.category].projects = []
            categories[project.category].projects.append(project)
        else:
            if not categories[project.category].hidden_projects:
                categories[project.category].hidden_projects = []
            categories[project.category].hidden_projects.append(project)


def update_project_category(project_info: Dict, categories: OrderedDict):
    if not project_info.category:
        # if category is not provided, put into others category
        project_info.category = DEFAULT_OTHERS_CATEGORY_ID

    if project_info.category not in categories:
        log.info("Category " + project_info.category +
                 " is not listed in the categories configuration.")
        project_info.category = DEFAULT_OTHERS_CATEGORY_ID


def prepare_categories(input_categories: dict) -> OrderedDict:
    categories = OrderedDict()
    for category in input_categories:
        categories[category["category"]] = Dict(category)

    if DEFAULT_OTHERS_CATEGORY_ID not in categories:
        # Add others category at the last position
        categories[DEFAULT_OTHERS_CATEGORY_ID] = Dict({
            "title": "Others"
        })
    return categories


def prepare_configuration(config: dict) -> OrderedDict:
    config = Dict(config)

    if "project_inactive_months" not in config:
        config.project_inactive_months = 6

    if "project_dead_months" not in config:
        config.project_dead_months = 12

    if "project_new_months" not in config:
        config.project_new_months = 6

    if "min_sourcerank" not in config:
        config.min_sourcerank = 5

    if "min_stars" not in config:
        config.min_stars = 100

    if "require_license" not in config:
        config.require_license = True

    if "require_pypi" not in config:
        config.require_pypi = False

    if "require_github" not in config:
        config.require_github = False

    if "require_npm" not in config:
        config.require_npm = False

    if "require_conda" not in config:
        config.require_conda = False

    if "markdown_output_file" not in config:
        config.markdown_output_file = "README.md"

    if "generate_badges" not in config:
        config.generate_badges = False

    if "generate_install_hints" not in config:
        config.generate_install_hints = True

    if "generate_toc" not in config:
        config.generate_toc = True

    if "generate_link_shortcuts" not in config:
        config.generate_link_shortcuts = False

    if "generate_legend" not in config:
        config.generate_legend = True

    if "sort_by" not in config:
        config.sort_by = "sourcerank"

    if "allowed_licenses" not in config:
        config.allowed_licenses = []
        from best_of.license import licenses
        for license in licenses:
            config.allowed_licenses.append(license["spdx_id"])

    return config


def sort_projects(projects: list, configuration: Dict):
    def sort_project_list(project):
        project = Dict(project)
        sourcerank = 0
        star_count = 0

        if project.sourcerank:
            sourcerank = int(project.sourcerank)

        if project.star_count:
            star_count = int(project.star_count)

        if not configuration.sort_by or configuration.sort_by == "sourcerank":
            # this is also the default if nothing is set
            return (sourcerank, star_count)
        elif configuration.sort_by == "star_count":
            return (star_count, sourcerank)

    return sorted(projects, key=sort_project_list, reverse=True)


def apply_filters(project_info: Dict, configuration: Dict):
    project_info.show = True

    # Project should have atleast name, homepage, and an description longer than a few chars
    if not project_info.name or not project_info.homepage or not project_info.description or len(project_info.description) < MIN_PROJECT_DESC_LENGTH:
        project_info.show = False

    # Do not show if project sourcerank less than min_sourcerank
    if configuration.min_sourcerank and project_info.sourcerank \
            and int(project_info.sourcerank) < int(configuration.min_sourcerank):
        project_info.show = False

    # Do not show if project stars less than min_stars
    if configuration.min_stars and project_info.star_count \
            and int(project_info.star_count) < int(configuration.min_stars):
        project_info.show = False

    # Do not show if license was not found
    if not project_info.license and configuration.require_license:
        project_info.show = False

    # Check platform requires
    if configuration.require_pypi and not project_info.pypi_url:
        project_info.show = False

    if configuration.require_github and not project_info.github_url:
        project_info.show = False

    if configuration.require_npm and not project_info.npm_url:
        project_info.show = False

    if configuration.require_conda and not project_info.conda_url:
        project_info.show = False

    if configuration.require_dockerhub and not project_info.dockerhub_url:
        project_info.show = False

    # Do not show if license is not in allowed_licenses
    if configuration.allowed_licenses and project_info.license:
        project_license = utils.simplify_str(project_info.license)
        project_license_metadata = get_license(project_info.license)
        if project_license_metadata:
            project_license = utils.simplify_str(
                project_license_metadata["spdx_id"])

        allowed_licenses = [utils.simplify_str(
            license) for license in configuration.allowed_licenses]
        for license in configuration.allowed_licenses:
            license_metadata = get_license(license)
            if license_metadata:
                allowed_licenses.append(
                    utils.simplify_str(license_metadata["spdx_id"]))

        if project_license not in set(allowed_licenses):
            project_info.show = False

    # Do not show if project is dead
    if project_info.updated_at:
        project_inactive_month = utils.diff_month(
            datetime.now(), project_info.updated_at)
        if configuration.project_dead_months and int(configuration.project_dead_months) < project_inactive_month:
            project_info.show = False


def collect_projects_info(projects: list, categories: OrderedDict, configuration: Dict):
    projects_processed = []
    unique_projects = set()
    for project in tqdm(projects):
        project_info = Dict(project)

        if project_info.name.lower() in unique_projects:
            log.info("Project " + project_info.name + " is duplicated.")
            continue
        unique_projects.add(project_info.name.lower())

        update_via_github(project_info)
        update_via_pypi(project_info)
        update_via_conda(project_info)
        update_via_npm(project_info)
        update_via_dockerhub(project_info)

        if not project_info.updated_at and project_info.created_at:
            # set update at if created at is available
            project_info.updated_at = project_info.created_at

        # set the show flag for every project, if not shown it will be moved to the More section
        apply_filters(project_info, configuration)

        # make sure that all defined values (but not category) are guaranteed to be used
        project_info.update(project)

        # Check and update the project category
        update_project_category(project_info, categories)

        projects_processed.append(project_info.to_dict())

    projects_processed = sort_projects(projects_processed, configuration)
    calc_sourcerank_placing(projects_processed)

    return projects_processed
