import logging
import sys

import click

log = logging.getLogger(__name__)


@click.group()
@click.version_option()
def cli():
    # log to sys out
    logging.basicConfig(
        format='%(asctime)s [%(levelname)s] %(message)s',
        level=logging.INFO,
        stream=sys.stdout)


@click.command("generate")
@click.option("--libraries-key", "-l", required=True, type=click.STRING, help="Libraries.io API Key: https://libraries.io/api")
@click.argument('path', type=click.Path(exists=True))
def generate(path, libraries_key):
    """ Generates a best-of markdown README from a projects.yaml. """
    from best_of import generator
    generator.generate_markdown(path, libraries_key)


cli.add_command(generate)


if __name__ == '__main__':
    cli()
