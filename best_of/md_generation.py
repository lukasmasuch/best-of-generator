import logging
import os
import urllib.parse
from collections import OrderedDict
from datetime import datetime

from addict import Dict

from best_of import utils
from best_of.license import get_license

log = logging.getLogger(__name__)


def generate_metrics_info(project: Dict, configuration: Dict) -> str:
    metrics_md = ""

    if project.sourcerank:
        placing_emoji = "🥉"
        if project.sourcerank_placing:
            if project.sourcerank_placing == 1:
                placing_emoji = "🥇"
            elif project.sourcerank_placing == 2:
                placing_emoji = "🥈"

        metrics_md += " " + placing_emoji + str(project.sourcerank)

    if project.star_count:
        if metrics_md:
            metrics_md += " · "
        metrics_md += " ⭐ " + str(utils.simplify_number(project.star_count))

    status_md = ""
    project_total_month = None
    if project.created_at:
        project_total_month = utils.diff_month(
            datetime.now(), project.created_at)

    project_inactive_month = None
    if project.updated_at:
        project_inactive_month = utils.diff_month(
            datetime.now(), project.updated_at)

    if project_inactive_month and configuration.project_dead_months and int(configuration.project_dead_months) < project_inactive_month:
        status_md = "💀"
    elif project_inactive_month and configuration.project_inactive_months and int(configuration.project_inactive_months) < project_inactive_month:
        status_md = "💤"
    elif project_total_month and configuration.project_new_months and int(configuration.project_new_months) >= project_total_month:
        status_md = "🐣"
    elif project.commercial:
        status_md = "💲"
    # TODO: add support for trending (📈) and new addition (➕)

    if status_md and metrics_md:
        metrics_md = metrics_md + " · " + status_md
    elif status_md:
        metrics_md = " " + status_md

    if metrics_md:
        # add divider if metrics are available
        metrics_md = "(" + metrics_md + ")"
        # remove unneccesary whitespaces
        utils.clean_whitespaces(metrics_md)
        # Add whitespace
        metrics_md = metrics_md + " "

    return metrics_md


def generate_license_info(project: Dict, configuration: Dict) -> str:
    license_md = ""
    if project.license:
        licenses_name = project.license
        licenses_warning = True
        licenses_url = "https://tldrlegal.com/search?q=" + \
            urllib.parse.quote(project.license)
        license_metadata = get_license(licenses_name)

        if license_metadata:
            license_metadata = Dict(license_metadata)
            if license_metadata.name:
                licenses_name = license_metadata.name
            if license_metadata.url:
                licenses_url = license_metadata.url
            if "warning" in license_metadata:
                licenses_warning = license_metadata.warning

        if licenses_warning:
            licenses_name = "❗️" + licenses_name

        license_template = ' <code><a href="{url}" target="_blank">{text}</a></code>'
        license_md += license_template.format(
            url=licenses_url, text=licenses_name)
    else:
        license_md += ' <code>❗️Unlicensed</code>'
    return license_md


def generate_links_list(project: Dict, configuration: Dict) -> str:
    links_md = ""
    link_template = ' <code><a href="{url}" target="_blank">{text}</a></code>'
    if project.github_url and project.homepage != project.github_url:
        links_md += link_template.format(url=project.npm_url, text="github")

    if project.dockerhub_url and project.homepage != project.dockerhub_url:
        links_md += link_template.format(url=project.dockerhub_url,
                                         text="dockerhub")

    if project.docs_url and project.homepage != project.docs_url:
        links_md += link_template.format(url=project.docs_url, text="docs")

    if project.pypi_url and project.homepage != project.conda_url:
        links_md += link_template.format(url=project.pypi_url, text="pypi")

    if project.conda_url and project.homepage != project.conda_url:
        links_md += link_template.format(url=project.conda_url, text="conda")

    if project.npm_url and project.homepage != project.npm_url:
        links_md += link_template.format(url=project.npm_url, text="npm")

    return links_md


def generate_pypi_details(project: Dict, configuration: Dict) -> str:
    pypi_id = project.pypi_id
    if not pypi_id:
        return ""

    metrics_md = ""
    if project.pypi_monthly_downloads:
        if metrics_md:
            metrics_md += " · "
        metrics_md += "📥 " + \
            str(utils.simplify_number(project.pypi_monthly_downloads)) + " / month"

    if metrics_md:
        metrics_md = " (" + metrics_md + ")"

    pypi_url = ""
    if project.pypi_url:
        pypi_url = project.pypi_url

    # https://badgen.net/#pypi
    details_md = "- **[PyPi](" + pypi_url + ")**" + metrics_md + ":\n"
    if configuration.generate_badges:
        details_md += "![PyPI Version](https://img.shields.io/pypi/v/{pypi_id}?style=social&logo=python&logoColor=black) "
        details_md += "![PyPI Downloads](https://img.shields.io/pypi/dm/{pypi_id}?style=social&logo=python&logoColor=black) "
        # Tool Slow: details_md += "![Libraries.io SourceRank](https://img.shields.io/librariesio/sourcerank/pypi/{pypi_id}?color=informational&logo=python&logoColor=white) "
        # Tool Slow: details_md += "![Libraries.io dependency status for latest release](https://img.shields.io/librariesio/release/pypi/{pypi_id}?color=informational&logo=python&logoColor=white) "
        details_md += "![PyPI Status](https://img.shields.io/pypi/status/{pypi_id}?color=informational&logo=python&logoColor=white) "
        details_md += "![PyPI Python Version](https://img.shields.io/pypi/pyversions/{pypi_id}?color=informational&logo=python&logoColor=white) "
        details_md += "![PyPI Format](https://img.shields.io/pypi/format/{pypi_id}?color=informational&logo=python&logoColor=white) "
        details_md += "![Dependent repos](https://img.shields.io/librariesio/dependent-repos/pypi/{pypi_id}?color=informational&logo=python&logoColor=white) "
        details_md += "![PyPI License](https://img.shields.io/pypi/l/{pypi_id}?color=informational&logo=python&logoColor=white) "

    details_md += "\n\t```bash\n\tpip install {pypi_id}\n\t```\n"
    return details_md.format(pypi_id=pypi_id)


def generate_conda_details(project: Dict, configuration: Dict) -> str:
    conda_id = project.conda_id
    if not conda_id:
        return ""

    # https://anaconda.org/anaconda/anaconda/badges
    metrics_md = ""

    conda_url = ""
    if project.conda_url:
        conda_url = project.conda_url

    details_md = "- **[Conda](" + conda_url + ")**" + metrics_md + ":\n"
    if configuration.generate_badges:
        details_md += "![Conda Version](https://img.shields.io/conda/v/anaconda/{conda_id}?style=social) "
        details_md += "![Conda Downloads](https://img.shields.io/conda/dn/anaconda/{conda_id}?style=social) "
        details_md += "![Supported Platforms](https://img.shields.io/conda/pn/anaconda/{conda_id}?color=informational) "

    details_md += "\n\t```bash\n\tconda install -c anaconda {conda_id}\n\t```\n"
    return details_md.format(conda_id=conda_id)


def generate_dockerhub_details(project: Dict, configuration: Dict) -> str:
    dockerhub_id = project.dockerhub_id
    if not dockerhub_id:
        return ""

    metrics_md = ""

    dockerhub_url = ""
    if project.dockerhub_url:
        dockerhub_url = project.dockerhub_url

    # https://badgen.net/#docker
    details_md = "- **[Dockerhub](" + dockerhub_url + \
        ")**" + metrics_md + ":\n"
    if configuration.generate_badges:
        details_md += "![Docker Pulls](https://img.shields.io/docker/pulls/{dockerhub_id}?logo=docker&label=pulls&color=informational&logoColor=white) "
        details_md += "![Docker Stars](https://img.shields.io/docker/stars/{dockerhub_id}?logo=docker&label=stars&color=informational&logoColor=white) "
        details_md += "![Docker Build](https://img.shields.io/docker/automated/{dockerhub_id}?logo=docker&label=build&color=informational&logoColor=white) "
        details_md += "![Docker Version](https://images.microbadger.com/badges/version/{dockerhub_id}.svg) "
        details_md += "![Docker License](https://images.microbadger.com/badges/license/{dockerhub_id}.svg) "
        details_md += "![Docker Commit](https://images.microbadger.com/badges/commit/{dockerhub_id}.svg) "
        details_md += "![MicroBadger Layers](https://img.shields.io/microbadger/layers/{dockerhub_id}?logo=docker&color=informational&logoColor=white) "
        details_md += "![MicroBadger Size](https://img.shields.io/microbadger/image-size/{dockerhub_id}?logo=docker&color=informational&logoColor=white) "

    details_md += "\n\t```bash\n\tdocker pull {dockerhub_id}\n\t```\n"
    return details_md.format(dockerhub_id=dockerhub_id)


def generate_npm_details(project: Dict, configuration: Dict) -> str:
    npm_id = project.npm_id
    if not npm_id:
        return ""

    metrics_md = ""

    npm_url = ""
    if project.npm_url:
        npm_url = project.npm_url

    # https://badgen.net/#npm
    details_md = "- **[NPM](" + npm_url + ")**" + metrics_md + ":\n"
    if configuration.generate_badges:
        details_md += "![NPM Version](https://img.shields.io/npm/v/{npm_id}?style=social&logo=node.js&logoColor=black) "
        details_md += "![NPM Downloads](https://img.shields.io/npm/dm/{npm_id}?style=social&logo=node.js&logoColor=black) "
        details_md += "![NPM License](https://img.shields.io/npm/l/{npm_id}?color=informational&logo=node.js&logoColor=white) "
        details_md += "![Node Version](https://img.shields.io/node/v/{npm_id}?color=informational&logo=node.js&logoColor=white) "
        details_md += "![NPM Type Definitions](https://img.shields.io/npm/types/{npm_id}?color=informational&logo=node.js&logoColor=white) "
        details_md += "![NPM Collaborators](https://img.shields.io/npm/collaborators/{npm_id}?color=informational&logo=node.js&logoColor=white) "
        details_md += "![NPM Bundle Size](https://img.shields.io/bundlephobia/min/{npm_id}?color=informational&logo=node.js&logoColor=white) "
        details_md += "![NPM Intstall Size](https://badgen.net/packagephobia/install/{npm_id}?color=blue&icon=npm) "
        details_md += "![NPM Snyk Vulnerabilities](https://img.shields.io/snyk/vulnerabilities/npm/{npm_id}?color=informational&logo=snyk&logoColor=white) "
        details_md += "![NPM JsDelivr Hits](https://img.shields.io/jsdelivr/npm/hm/{npm_id}?color=informational&logo=jsdelivr&logoColor=white) "

    details_md += "\n\t```bash\n\tnpm install {npm_id}\n\t```\n"
    return details_md.format(npm_id=npm_id)


def generate_github_details(project: Dict, configuration: Dict) -> str:
    github_id = project.github_id
    if not github_id:
        return ""

    metrics_md = ""
    if project.contributor_count:
        if metrics_md:
            metrics_md += " · "
        metrics_md += "👨‍💻 " + \
            str(utils.simplify_number(project.contributor_count))

    if project.fork_count:
        if metrics_md:
            metrics_md += " · "
        metrics_md += "🔀 " + str(utils.simplify_number(project.fork_count))

    if metrics_md:
        metrics_md = " (" + metrics_md + ")"

    github_url = ""
    if project.github_url:
        github_url = project.github_url

    # https://badgen.net/#github
    details_md = "- **[GitHub](" + github_url + ")**" + metrics_md + ":\n"
    if configuration.generate_badges:
        details_md += "![GitHub Stars](https://img.shields.io/github/stars/{github_id}?style=social) "
        details_md += "![GitHub Forks](https://img.shields.io/github/forks/{github_id}?style=social) "
        details_md += "![GitHub Contributors](https://img.shields.io/github/contributors/{github_id}?style=social&logo=github) "
        details_md += "![GitHub Watchers](https://img.shields.io/github/watchers/{github_id}?style=social) "
        details_md += "![GitHub Last Commit](https://img.shields.io/github/last-commit/{github_id}?color=informational&logo=github&logoColor=white) "
        # Too Slow:  details_md += "![Libraries.io Dependency Status](https://img.shields.io/librariesio/github/{github_id}?color=informational&logo=github&logoColor=white) "
        details_md += "![GitHub License](https://img.shields.io/github/license/{github_id}?color=informational&logo=github&logoColor=white) "
        details_md += "![GitHub Commit Activity](https://img.shields.io/github/commit-activity/m/{github_id}?color=informational&logo=github&logoColor=white) "
        details_md += "![GitHub Open Issues](https://img.shields.io/github/issues-raw/{github_id}?color=informational&logo=github&logoColor=white) "
        details_md += "![GitHub Closed Issues](https://img.shields.io/github/issues-closed-raw/{github_id}?color=informational&logo=github&logoColor=white) "
        details_md += "![GitHub Pull Requests](https://badgen.net/github/prs/{github_id}?color=blue&icon=github) "
        details_md += "![Github Commits](https://badgen.net/github/commits/{github_id}?color=blue&icon=github) "
        details_md += "![Github Repo Dependents](https://badgen.net/github/dependents-repo/{github_id}?color=blue&icon=github) "
        details_md += "![Github Pkgs Dependents](https://badgen.net/github/dependents-pkg/{github_id}?color=blue&icon=github) "
        details_md += "![GitHub Language Count](https://img.shields.io/github/languages/count/{github_id}?color=informational&logo=github&logoColor=white) "
        details_md += "![GitHub Top Language](https://img.shields.io/github/languages/top/{github_id}?color=informational&logo=github&logoColor=white) "
        details_md += "![GitHub Release](https://badgen.net/github/release/{github_id}/stable?color=blue&icon=github) "
        # details_md += "![GitHub Downloads](https://img.shields.io/github/downloads/{github_id}/total?color=informational) "
        # Github API Limit: details_md += "![Average time to resolve an issue](http://isitmaintained.com/badge/resolution/{github_id}.svg) "
        # Github API Limit: details_md += "![Percentage of issues still open](http://isitmaintained.com/badge/open/{github_id}.svg) "

    details_md += "\n\t```bash\n\tgit clone https://github.com/{github_id}\n\t```\n"
    return details_md.format(github_id=github_id)


def generate_project_body(project: Dict, configuration: Dict):
    body_md = ""

    if project.github_id:
        body_md += generate_github_details(project, configuration)

    if project.pypi_id:
        body_md += generate_pypi_details(project, configuration)

    if project.npm_id:
        body_md += generate_npm_details(project, configuration)

    if project.conda_id:
        body_md += generate_conda_details(project, configuration)

    if project.dockerhub_id:
        body_md += generate_dockerhub_details(project, configuration)

    if not body_md:
        # show message if no information is available
        body_md = "- _No project information available._"

    body_md = "\n\n" + body_md
    return body_md


def generate_project_md(project: Dict, configuration: Dict):
    project_md = ""
    metrics_md = generate_metrics_info(project, configuration)
    license_md = generate_license_info(project, configuration)
    links_md = generate_links_list(project, configuration)

    metadata_md = ""
    if license_md and links_md:
        metadata_md = license_md + " · " + links_md
    elif license_md:
        metadata_md = license_md
    elif links_md:
        metadata_md = links_md

    body_md = generate_project_body(project, configuration)

    project_md = '<details><summary><a href="{homepage}" target="_blank"><b>{name}</b></a> {metrics}- {description}{metadata}</summary>{body}</details>'.format(
        homepage=project.homepage,
        name=project.name,
        description=project.description,
        metrics=metrics_md,
        metadata=metadata_md,
        body=body_md)

    return project_md


def generate_category_md(category: Dict, configuration: Dict, title_md_prefix="##"):
    category_md = ""

    category_md += title_md_prefix + " " + category.title + "\n\n"
    # <span align="right" style="float:right;"><a href="#"><sup>▴ Back to top</sup></a></span>
    # **[`^        back to top        ^`](#)**\n\n
    category_md += '<a href="#"><img align="right" width="15" height="15" src="https://i.ibb.co/2PS8bhR/up-arrow.png" alt="Back to top"></a>\n\n'

    if category.subtitle:
        category_md += "_" + category.subtitle + "_\n\n"

    if category.projects:
        for project in category.projects:
            project_md = generate_project_md(project, configuration)
            category_md += project_md + "\n"

    if category.hidden_projects:
        category_md += "<details><summary>Show " + \
            str(len(category.hidden_projects)) + \
            " hidden projects...</summary>\n<br>"
        for project in category.hidden_projects:
            project_md = generate_project_md(project, configuration)
            category_md += project_md + "\n"
        category_md += "</details>\n"

    return category_md


def generate_legend(configuration: Dict, title_md_prefix="##"):
    legend_md = title_md_prefix + " Explanation\n"
    legend_md += "- 🥇🥈🥉 [SourceRank](https://docs.libraries.io/overview.html#sourcerank) from Libraries.io\n"
    legend_md += "- ⭐️ Star count from Github\n"
    legend_md += "- 🐣 New project _(less than " + \
        str(configuration.project_new_months) + " month old)_\n"
    legend_md += "- 💤 Inactive project _(" + str(
        configuration.project_inactive_months) + " month no activity)_\n"
    legend_md += "- 💀 Dead project _(" + str(
        configuration.project_dead_months) + " year no activity)_\n"
    legend_md += "- ❗️ Warning _(e.g. missing/risky license)_\n"
    legend_md += "- 👨‍💻 Contributors count from Github\n"
    legend_md += "- 🔀 Fork count from Github\n"
    legend_md += "- 📥 Download count from package manager\n"
    legend_md += "- 📦 Number of dependent projects\n"
    legend_md += "- 📈 Trending project\n"
    legend_md += "- 💲 Commercial project\n"
    return legend_md


def generate_toc(categories: OrderedDict):
    toc_md = "## Contents\n\n"
    for category in categories:
        title = categories[category]["title"]
        url = "#" + title.lower().replace(" ", "-")
        toc_md += "- [{title}]({url})\n".format(
            title=categories[category]["title"], url=url)
    return toc_md


def generate_md(categories: OrderedDict, configuration: Dict):
    full_markdown = ""

    if configuration.markdown_header_file:
        if os.path.exists(configuration.markdown_header_file):
            with open(configuration.markdown_header_file, 'r') as f:
                full_markdown += str(f.read()) + "\n"
        else:
            log.warning("The markdown header file does not exist: " +
                        os.path.abspath(configuration.markdown_header_file))

    if configuration.generate_toc:
        full_markdown += generate_toc(categories) + "\n"

    if configuration.generate_legend:
        full_markdown += generate_legend(configuration) + "\n"

    for category in categories:
        full_markdown += generate_category_md(
            categories[category], configuration) + "\n\n"

    if configuration.markdown_footer_file:
        if os.path.exists(configuration.markdown_footer_file):
            with open(configuration.markdown_footer_file, 'r') as f:
                full_markdown += str(f.read())
        else:
            log.warning("The markdown footer file does not exist: " +
                        os.path.abspath(configuration.markdown_footer_file))

    return full_markdown
