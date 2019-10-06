import yaml
from addict import Dict
from tqdm import tqdm

import requirements
from best_of import projects_collection


def requirements_to_yaml(requirements_path: str, yaml_output_path: str):
    requirements_projects = []
    with open(requirements_path, 'r') as fd:
        for req in tqdm(requirements.parse(fd)):
            project = Dict()
            project.pypi_id = req.name
            projects_collection.update_via_pypi(project)
            requirements_projects.append(project)

    output_yaml = []
    for project in requirements_projects:
        project_output = {}

        if project.name:
            project_output["name"] = project.name

        if project.pypi_id:
            if not project.name:
                project_output["name"] = project.pypi_id
            project_output["pypi_id"] = project.pypi_id

        if project.github_id:
            project_output["github_id"] = project.github_id

        output_yaml.append(project_output)

    # define a custom representer for strings
    #def quoted_presenter(dumper, data):
    #    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')

    #yaml.add_representer(str, quoted_presenter)

    with open(yaml_output_path, 'w') as f:
        yaml.dump(output_yaml, f, default_flow_style=False, sort_keys=False)
